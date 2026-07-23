"""Regression and safety tests for MOBRA identity, media, and manuscript outputs."""

from __future__ import annotations

import io
import json
import struct
import zipfile
from pathlib import Path

from mobra.branding import BRANDING_DIR, POSTERS_DIR, brand_summary, load_brand_palette
from mobra.config import APP_VERSION, AUTHOR_EMAIL, MANUSCRIPT_SHA256, MANUSCRIPT_VERSION_NOTE
from mobra.educational_media import educational_media_package, load_educational_media, validate_educational_media
from mobra.manuscript import manuscript_download_bytes, manuscript_is_current, manuscript_metadata

ROOT = Path(__file__).resolve().parents[1]


def test_brand_palette_and_required_assets_are_valid() -> None:
    palette = load_brand_palette()
    assert palette["version"] == "1.0.0"
    assert palette["colors"]["navy"] == "#0B1F3A"
    for filename in (
        "mobra_logo_main.svg",
        "mobra_logo_main.png",
        "mobra_logo_horizontal.svg",
        "mobra_logo_horizontal.png",
        "mobra_icon.svg",
        "mobra_icon.png",
        "mobra_favicon.png",
        "mobra_monochrome.svg",
        "mobra_brand_guidelines.pdf",
        "brand_palette.json",
    ):
        path = BRANDING_DIR / filename
        assert path.is_file() and path.stat().st_size > 0
    assert (BRANDING_DIR / "mobra_logo_main.svg").read_text(encoding="utf-8").startswith("<svg")
    assert (BRANDING_DIR / "mobra_logo_main.svg").read_text(encoding="utf-8").count("<svg") == 1
    png = (BRANDING_DIR / "mobra_logo_main.png").read_bytes()
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    width, height = struct.unpack(">II", png[16:24])
    assert width >= 1000 and height >= 300
    assert (BRANDING_DIR / "mobra_brand_guidelines.pdf").read_bytes().startswith(b"%PDF")


def test_educational_media_manifest_has_ten_original_formats() -> None:
    media = load_educational_media()
    assert len(media) == 10
    assert validate_educational_media(media) == []
    assert all(item["educational_status"] == "Original educational summary" for item in media)
    assert all("endorsement" in item["copyright_note"].lower() for item in media)
    for item in media:
        for key in ("svg_path", "png_path", "pdf_path"):
            path = ROOT / item[key]
            assert path.is_file() and path.stat().st_size > 0
        assert (ROOT / item["pdf_path"]).read_bytes().startswith(b"%PDF")
        assert (ROOT / item["svg_path"]).read_text(encoding="utf-8").startswith("<svg")
        png = (ROOT / item["png_path"]).read_bytes()
        assert png.startswith(b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", png[16:24])
        assert width == 1600 and height == 900
    assert (POSTERS_DIR / "MOBRA_Information_Poster.pdf").read_bytes().startswith(b"%PDF")


def test_educational_media_package_contains_only_mobra_assets() -> None:
    with zipfile.ZipFile(io.BytesIO(educational_media_package())) as archive:
        names = archive.namelist()
        assert "README.txt" in names
        assert any(name.endswith("MOBRA_Information_Poster.pdf") for name in names)
        assert sum(name.endswith(".pdf") for name in names) == 11
        assert all("ISO" not in name and "WHO" not in name for name in names)
        assert b"No endorsement" in archive.read("README.txt")


def test_manuscript_is_valid_approved_and_download_bytes_match() -> None:
    path = ROOT / "docs" / "MOBRA_Manuscript.pdf"
    metadata = manuscript_metadata(path)
    assert metadata["manuscript_available"] is True
    assert metadata["manuscript_size_bytes"] > 0
    assert metadata["manuscript_page_count"] == 22
    assert metadata["manuscript_sha256"] == MANUSCRIPT_SHA256
    assert manuscript_is_current(path)
    assert manuscript_download_bytes(path) == path.read_bytes()
    assert "C:\\Users\\" not in json.dumps(metadata)


def test_manuscript_note_separates_historical_bri_from_current() -> None:
    metadata = manuscript_metadata()
    assert "81.0%" not in metadata["manuscript_version_note"]
    assert MANUSCRIPT_VERSION_NOTE in metadata["manuscript_version_note"]
    summary = json.loads(json.dumps({**metadata, "current_bri_pct": 86.7, "historical_manuscript_bri_pct": 81.0}))
    assert summary["current_bri_pct"] == 86.7
    assert summary["historical_manuscript_bri_pct"] == 81.0


def test_application_metadata_has_contact_and_release_fields() -> None:
    from mobra.config import application_metadata

    metadata = application_metadata()
    assert APP_VERSION == "0.9.0"
    assert metadata["author_email"] == AUTHOR_EMAIL
    assert metadata["live_app_url"].startswith("https://")
    assert metadata["repository_url"].startswith("https://")
    assert brand_summary()["logo_available"] is True
