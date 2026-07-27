"""Optional secrets-backed authentication for the MOBRA Streamlit app."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import streamlit as st

from .config import APP_FULL_NAME, APP_NAME, LOGO_PATH
from ui.components import render_logo

PBKDF2_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = 600_000
HASH_PREFIX = "pbkdf2_sha256"
AUTHENTICATED_KEY = "mobra_authenticated"
AUTH_USER_KEY = "mobra_authenticated_user"
AUTH_TIME_KEY = "mobra_authenticated_at"


@dataclass(frozen=True)
class AuthConfig:
    """Validated runtime authentication configuration."""

    enabled: bool = False
    username: str = ""
    password_hash: str = ""
    session_timeout_minutes: int = 60

    @property
    def ready(self) -> bool:
        return bool(self.username and self.password_hash)


def hash_password(
    password: str,
    *,
    iterations: int = PBKDF2_ITERATIONS,
    salt: bytes | None = None,
) -> str:
    """Return a salted PBKDF2 password hash suitable for Streamlit Secrets."""
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string.")
    if iterations < 100_000:
        raise ValueError("PBKDF2 iterations must be at least 100,000.")
    salt_bytes = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt_bytes,
        iterations,
    )
    return f"{HASH_PREFIX}${iterations}${salt_bytes.hex()}${digest.hex()}"


def verify_password(password: str, encoded_hash: str) -> bool:
    """Verify a password without leaking timing information."""
    try:
        prefix, iterations_text, salt_hex, expected_hex = encoded_hash.split("$", 3)
        if prefix != HASH_PREFIX:
            return False
        iterations = int(iterations_text)
        if iterations < 100_000:
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hex)
        actual = hashlib.pbkdf2_hmac(
            PBKDF2_ALGORITHM,
            password.encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(actual, expected)
    except (AttributeError, TypeError, ValueError):
        return False


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _secret_auth_mapping() -> Mapping[str, Any]:
    try:
        value = st.secrets.get("auth", {})
        return dict(value) if value else {}
    except (FileNotFoundError, KeyError, OSError, TypeError):
        return {}


def load_auth_config(
    *,
    environ: Mapping[str, str] | None = None,
    secret_auth: Mapping[str, Any] | None = None,
) -> AuthConfig:
    """Load authentication from Streamlit Secrets with environment fallbacks.

    Authentication remains open when no credentials are configured. Supplying
    both a username and password hash enables the gate by default; an explicit
    ``enabled`` setting can override that behavior.
    """
    env = environ if environ is not None else os.environ
    configured = dict(secret_auth if secret_auth is not None else _secret_auth_mapping())
    username = str(
        env.get("MOBRA_AUTH_USERNAME", configured.get("username", ""))
    ).strip()
    password_hash = str(
        env.get("MOBRA_AUTH_PASSWORD_HASH", configured.get("password_hash", ""))
    ).strip()
    enabled_value = env.get("MOBRA_AUTH_ENABLED", configured.get("enabled"))
    enabled = _as_bool(enabled_value, default=bool(username and password_hash))
    timeout_raw = env.get(
        "MOBRA_AUTH_SESSION_TIMEOUT_MINUTES",
        configured.get("session_timeout_minutes", 60),
    )
    try:
        timeout = max(5, min(int(timeout_raw), 1_440))
    except (TypeError, ValueError):
        timeout = 60
    return AuthConfig(
        enabled=enabled,
        username=username,
        password_hash=password_hash,
        session_timeout_minutes=timeout,
    )


def _session_is_valid(config: AuthConfig) -> bool:
    if not st.session_state.get(AUTHENTICATED_KEY, False):
        return False
    authenticated_at = float(st.session_state.get(AUTH_TIME_KEY, 0) or 0)
    if time.time() - authenticated_at > config.session_timeout_minutes * 60:
        clear_auth_session()
        return False
    return st.session_state.get(AUTH_USER_KEY) == config.username


def clear_auth_session() -> None:
    """Remove only MOBRA authentication state."""
    for key in (AUTHENTICATED_KEY, AUTH_USER_KEY, AUTH_TIME_KEY):
        st.session_state.pop(key, None)


def authentication_gate(config: AuthConfig | None = None) -> bool:
    """Render the branded login gate and return whether the app may continue."""
    auth = config or load_auth_config()
    if not auth.enabled:
        return True
    if not auth.ready:
        _, center, _ = st.columns([1, 1.35, 1])
        with center, st.container(border=True):
            if Path(LOGO_PATH).is_file():
                render_logo(width=520)
            st.error(
                "Authentication is enabled but not fully configured. Add the "
                "username and PBKDF2 password hash to Streamlit Secrets."
            )
            st.caption("No default or hardcoded MOBRA credentials exist.")
        return False
    if _session_is_valid(auth):
        return True

    left, center, right = st.columns([1, 1.35, 1])
    with center:
        with st.container(border=True):
            if Path(LOGO_PATH).is_file():
                render_logo(width=520)
            st.markdown(
                f'<div class="mobra-login-brand">'
                '<div class="mobra-login-lock" aria-hidden="true">◆</div>'
                "<h2>Authorized access</h2>"
                f"<p>{APP_NAME} · {APP_FULL_NAME}</p></div>",
                unsafe_allow_html=True,
            )
            st.caption(
                "Enter the username and password assigned by the MOBRA administrator."
            )
            with st.form("mobra_login_form", clear_on_submit=False):
                username = st.text_input(
                    "Username",
                    key="mobra_login_username",
                    max_chars=128,
                    autocomplete="username",
                    placeholder="Enter your MOBRA username",
                    help="Use the username assigned to your authorized account.",
                )
                password = st.text_input(
                    "Password",
                    key="mobra_login_password",
                    type="password",
                    max_chars=256,
                    autocomplete="current-password",
                    placeholder="Enter your password",
                    help="Your password is masked and is not written to assessment data.",
                )
                submitted = st.form_submit_button(
                    "Sign in",
                    type="primary",
                    width="stretch",
                )
            if submitted:
                valid_user = hmac.compare_digest(
                    username.strip().encode("utf-8"),
                    auth.username.encode("utf-8"),
                )
                valid_password = verify_password(password, auth.password_hash)
                if valid_user and valid_password:
                    st.session_state[AUTHENTICATED_KEY] = True
                    st.session_state[AUTH_USER_KEY] = auth.username
                    st.session_state[AUTH_TIME_KEY] = time.time()
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
            st.markdown(
                """
                <div class="mobra-login-assurance">
                  <strong>Protected session</strong>
                  <span>Credentials are verified securely and are never added to assessment records.</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
    return False


def render_logout_control(config: AuthConfig | None = None) -> None:
    """Show the authenticated identity and an explicit logout action."""
    auth = config or load_auth_config()
    if not auth.enabled or not _session_is_valid(auth):
        return
    with st.sidebar:
        st.caption(f"Signed in as {st.session_state.get(AUTH_USER_KEY, auth.username)}")
        if st.button("Log out", key="mobra_logout", width="stretch"):
            clear_auth_session()
            st.rerun()
