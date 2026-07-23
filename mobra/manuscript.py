"""Author-approved manuscript metadata and safe download helpers."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from .config import (
    AUTHOR_NAME,
    MANUSCRIPT_FILENAME,
    MANUSCRIPT_SHA256,
    MANUSCRIPT_VERSION_NOTE,
)

MANUSCRIPT_PATH = Path(__file__).resolve().parent.parent / "docs" / MANUSCRIPT_FILENAME


def manuscript_page_count(content: bytes) -> int | None:
    """Estimate PDF page count without requiring a runtime PDF dependency.

    A valid PDF page object is represented by ``/Type /Page`` while the page
    tree is ``/Type /Pages``.  The negative look-ahead excludes the latter.
    """
    if not content.startswith(b"%PDF"):
        return None
    matches = re.findall(rb"/Type\s*/Page(?!s)\b", content)
    return len(matches) or None


def manuscript_metadata(path: Path | None = None) -> dict[str, Any]:
    target = path or MANUSCRIPT_PATH
    if not target.is_file() or target.stat().st_size == 0:
        return {
            "manuscript_available": False,
            "manuscript_filename": MANUSCRIPT_FILENAME,
            "manuscript_sha256": "",
            "manuscript_version_note": MANUSCRIPT_VERSION_NOTE,
            "manuscript_download_enabled": False,
            "manuscript_size_bytes": 0,
            "manuscript_page_count": None,
            "manuscript_author": AUTHOR_NAME,
        }
    content = target.read_bytes()
    return {
        "manuscript_available": content.startswith(b"%PDF") and bool(content),
        "manuscript_filename": target.name,
        "manuscript_sha256": hashlib.sha256(content).hexdigest(),
        "manuscript_version_note": MANUSCRIPT_VERSION_NOTE,
        "manuscript_download_enabled": content.startswith(b"%PDF") and bool(content),
        "manuscript_size_bytes": len(content),
        "manuscript_page_count": manuscript_page_count(content),
        "manuscript_author": AUTHOR_NAME,
    }


def manuscript_is_current(path: Path | None = None) -> bool:
    """Confirm the checked-in manuscript matches the author-approved checksum."""
    metadata = manuscript_metadata(path)
    return bool(metadata["manuscript_available"] and metadata["manuscript_sha256"] == MANUSCRIPT_SHA256)


def manuscript_download_bytes(path: Path | None = None) -> bytes:
    target = path or MANUSCRIPT_PATH
    if not target.is_file():
        raise FileNotFoundError(MANUSCRIPT_FILENAME)
    content = target.read_bytes()
    if not content.startswith(b"%PDF") or not content:
        raise ValueError("The manuscript is not a non-empty PDF.")
    return content
