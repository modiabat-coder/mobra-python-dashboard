"""Small notification helpers that avoid toast spam on Streamlit reruns."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any


def notification_once(
    session_state: MutableMapping[str, Any],
    key: str,
    message: str,
    *,
    level: str = "info",
) -> bool:
    """Mark a notification once and return whether it should be rendered."""
    seen = session_state.setdefault("_mobra_notifications_seen", set())
    if key in seen:
        return False
    seen.add(key)
    return True


def emit_notification(
    st_module: Any, session_state: MutableMapping[str, Any], key: str, message: str, *, level: str = "info"
) -> bool:
    """Render a single notification using toast when available and banners otherwise."""
    if not notification_once(session_state, key, message, level=level):
        return False
    if callable(getattr(st_module, "toast", None)):
        st_module.toast(message, icon={"success": "✅", "warning": "⚠️", "error": "❌"}.get(level, "ℹ️"))
        return True
    renderer = getattr(st_module, level, st_module.info)
    renderer(message)
    return True


def clear_notification_flags(session_state: MutableMapping[str, Any]) -> None:
    session_state.pop("_mobra_notifications_seen", None)
