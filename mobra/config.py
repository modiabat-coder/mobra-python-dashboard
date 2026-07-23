"""Central application, branding, risk, and decision constants for MOBRA."""

from __future__ import annotations

from pathlib import Path


APP_NAME = "MOBRA"
APP_FULL_NAME = "Mobile Operational Biosecurity Readiness Assessment"
APP_DESCRIPTION = (
    "Scientific decision support for mobile laboratory biosecurity, "
    "operational readiness, risk assessment, and deployment governance."
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = PROJECT_ROOT / "assets"
LOGO_PATH = ASSETS_DIR / "mobra_logo.svg"
LOGO_DARK_PATH = ASSETS_DIR / "mobra_logo_dark.svg"
ICON_PATH = ASSETS_DIR / "mobra_icon.svg"
FAVICON_PATH = ASSETS_DIR / "favicon.png"

# Design tokens. User-facing pages and the standalone report use this palette.
PRIMARY_COLOR = "#103B4D"
PRIMARY_DARK = "#082A38"
SECONDARY_COLOR = "#147D85"
ACCENT_COLOR = "#39A7A0"
BACKGROUND_COLOR = "#F4F7F8"
SURFACE_COLOR = "#FFFFFF"
SURFACE_ALT_COLOR = "#EDF3F4"
TEXT_COLOR = "#152C35"
MUTED_TEXT_COLOR = "#5F747C"
BORDER_COLOR = "#D9E4E7"
BORDER_STRONG_COLOR = "#B8CCD1"
SIDEBAR_TEXT_COLOR = "#F3F8F9"
SIDEBAR_MUTED_COLOR = "#C5D5DA"
SUCCESS_COLOR = "#237A45"
WARNING_COLOR = "#B25E09"
DANGER_COLOR = "#B42318"
INFO_COLOR = "#1D6A8A"

RISK_COLORS = {
    "Low": "#2E7D32",
    "Moderate": "#F2C94C",
    "High": "#E67E22",
    "Extreme": "#C62828",
    "Unknown": "#7B8B91",
    "Invalid": "#7B8B91",
}
RISK_TEXT_COLORS = {
    "Low": "#FFFFFF",
    "Moderate": "#3D3100",
    "High": "#FFFFFF",
    "Extreme": "#FFFFFF",
    "Unknown": "#FFFFFF",
    "Invalid": "#FFFFFF",
}

# Decision terminology is defined once and reused by logic, UI, reports, and tests.
DECISION_DO_NOT_DEPLOY = "DO NOT DEPLOY"
DECISION_CONDITIONAL = "CONDITIONAL DEPLOYMENT"
DECISION_READY = "READY TO DEPLOY"
DECISION_LABELS = (
    DECISION_DO_NOT_DEPLOY,
    DECISION_CONDITIONAL,
    DECISION_READY,
)
DECISION_COLORS = {
    DECISION_DO_NOT_DEPLOY: DANGER_COLOR,
    DECISION_CONDITIONAL: WARNING_COLOR,
    DECISION_READY: SUCCESS_COLOR,
}
DECISION_ICONS = {
    DECISION_DO_NOT_DEPLOY: "\u26d4",
    DECISION_CONDITIONAL: "\u26a0",
    DECISION_READY: "\u2713",
}

RISK_LEVELS = ["Low", "Moderate", "High", "Extreme"]
RISK_RANGES = {
    "Low": "1\u20134",
    "Moderate": "5\u20139",
    "High": "10\u201316",
    "Extreme": "17\u201325",
}

SUPPORTED_EXTENSIONS = (".csv", ".xlsx", ".xls", ".json")
SYNTHETIC_DATA_LABEL = "Synthetic Demonstration Data"
UPLOADED_DATA_LABEL = "Uploaded Assessment Data"


def pluralize(count: int, singular: str, plural: str | None = None) -> str:
    """Return the noun form for ``count`` without placeholder grammar."""
    return singular if int(count) == 1 else (plural or f"{singular}s")


def count_phrase(count: int, singular: str, plural: str | None = None) -> str:
    """Return a count and its correctly inflected noun."""
    return f"{int(count)} {pluralize(count, singular, plural)}"
