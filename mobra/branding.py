"""Central MOBRA visual identity helpers.

The palette and asset paths live in the repository so the Streamlit app, reports,
forms, posters, and backup packages use one auditable visual language.  The
assets are original MOBRA artwork and do not reproduce third-party marks.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
BRANDING_DIR = ROOT / "assets" / "branding"
POSTERS_DIR = ROOT / "assets" / "posters"
PALETTE_PATH = BRANDING_DIR / "brand_palette.json"


def load_brand_palette(path: Path | None = None) -> dict[str, Any]:
    """Load and validate the central accessible colour palette."""
    source = path or PALETTE_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not payload.get("colors"):
        raise ValueError("MOBRA brand palette must contain a colors object.")
    for name, value in payload["colors"].items():
        if not isinstance(value, str) or not value.startswith("#") or len(value) not in {4, 7}:
            raise ValueError(f"Invalid HEX colour for {name}.")
    return payload


def asset_path(filename: str) -> Path:
    """Return an asset path while preventing traversal outside the asset roots."""
    candidate = (BRANDING_DIR / filename).resolve()
    root = BRANDING_DIR.resolve()
    if candidate.parent != root:
        raise ValueError("Branding asset must be a direct child of assets/branding.")
    return candidate


def poster_path(filename: str) -> Path:
    """Return a poster asset path while preventing path traversal."""
    candidate = (POSTERS_DIR / filename).resolve()
    root = POSTERS_DIR.resolve()
    if candidate.parent != root:
        raise ValueError("Poster asset must be a direct child of assets/posters.")
    return candidate


def asset_data_uri(filename: str) -> str:
    """Return a small local asset as a data URI for self-contained HTML."""
    path = asset_path(filename)
    if not path.is_file():
        return ""
    mime = {".png": "image/png", ".svg": "image/svg+xml"}.get(path.suffix.lower(), "application/octet-stream")
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def logo_available() -> bool:
    return all(asset_path(name).is_file() for name in ("mobra_logo_horizontal.svg", "mobra_favicon.png"))


def brand_summary() -> dict[str, Any]:
    """Return metadata suitable for Summary JSON and reports."""
    palette = load_brand_palette()
    return {
        "branding_version": palette.get("version", "1.0.0"),
        "logo_available": logo_available(),
        "brand_palette": palette["colors"],
        "brand_guidelines": "assets/branding/mobra_brand_guidelines.pdf",
    }
