"""Manifest and packaging helpers for original MOBRA educational posters."""

from __future__ import annotations

import io
import json
import re
import zipfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
MEDIA_MANIFEST = ROOT / "config" / "educational_media.json"

REQUIRED_FIELDS = (
    "media_id",
    "title",
    "topic",
    "description",
    "svg_path",
    "png_path",
    "pdf_path",
    "source_resource_ids",
    "educational_status",
    "copyright_note",
    "last_updated",
)


def load_educational_media(path: Path | None = None) -> list[dict[str, Any]]:
    source = path or MEDIA_MANIFEST
    payload = json.loads(source.read_text(encoding="utf-8"))
    records = payload.get("media", payload) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise ValueError("Educational media manifest must contain a list.")
    errors = validate_educational_media(records)
    if errors:
        raise ValueError("; ".join(errors))
    return records


def validate_educational_media(records: Iterable[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for index, record in enumerate(records, start=1):
        missing = [field for field in REQUIRED_FIELDS if field not in record]
        if missing:
            errors.append(f"Media {index} is missing fields: {', '.join(missing)}")
            continue
        media_id = str(record["media_id"])
        if media_id in seen:
            errors.append(f"Duplicate media_id: {media_id}")
        seen.add(media_id)
        for field in ("svg_path", "png_path", "pdf_path"):
            path = ROOT / str(record[field])
            if not path.is_file() or path.stat().st_size == 0:
                errors.append(f"{media_id} asset is missing or empty: {record[field]}")
        if not record["source_resource_ids"]:
            errors.append(f"{media_id} needs at least one source resource id")
        claim_text = f"{record['description']} {record['copyright_note']}".lower()
        if re.search(r"\b(endorsed by|certified by|approved by)\b", claim_text):
            errors.append(f"{media_id} must not contain endorsement claims")
    return errors


def educational_media_package(records: Iterable[dict[str, Any]] | None = None) -> bytes:
    """Package only MOBRA-created SVG/PNG/PDF files, never third-party PDFs."""
    media = list(records or load_educational_media())
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "README.txt",
            "MOBRA Educational Media Package\n"
            "Original MOBRA-created educational summaries only.\n"
            "These materials are educational summaries. No endorsement is claimed by any referenced organization.\n",
        )
        for filename in (
            "MOBRA_Information_Poster.svg",
            "MOBRA_Information_Poster.png",
            "MOBRA_Information_Poster.pdf",
        ):
            path = ROOT / "assets" / "posters" / filename
            if path.is_file():
                archive.write(path, arcname=f"assets/posters/{filename}")
        for record in media:
            for field in ("svg_path", "png_path", "pdf_path"):
                path = ROOT / str(record[field])
                archive.write(
                    path,
                    arcname=path.relative_to(ROOT).as_posix(),
                )
    return buffer.getvalue()


def media_summary(records: Iterable[dict[str, Any]] | None = None) -> dict[str, Any]:
    media = list(records or load_educational_media())
    return {
        "educational_media_count": len(media),
        "educational_media_ids": [record["media_id"] for record in media],
        "educational_media_manifest": "config/educational_media.json",
    }
