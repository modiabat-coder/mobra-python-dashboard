"""Startup and presentation contracts for hosted Streamlit deployments."""

from __future__ import annotations

import importlib

import pandas as pd
from streamlit.testing.v1 import AppTest

from mobra.config import MANUSCRIPT_FILENAME, MANUSCRIPT_SHA256, MANUSCRIPT_VERSION_NOTE
from mobra.manuscript import manuscript_download_bytes, manuscript_is_current, manuscript_metadata
from mobra.ui import NAVIGATION_ITEMS, friendly_frame, validation_importance_summary


def test_all_app_startup_modules_import_without_circular_dependency() -> None:
    modules = (
        "mobra.config",
        "mobra.manuscript",
        "mobra.reporting",
        "mobra.validation",
        "mobra.validation_findings",
        "mobra.operational_tools",
        "app",
    )
    for module in modules:
        assert importlib.import_module(module) is not None


def test_manuscript_symbols_and_download_contract_are_available() -> None:
    assert MANUSCRIPT_FILENAME.endswith(".pdf")
    assert len(MANUSCRIPT_SHA256) == 64
    assert MANUSCRIPT_VERSION_NOTE
    metadata = manuscript_metadata()
    assert metadata["manuscript_available"] is True
    assert manuscript_is_current() is True
    assert manuscript_download_bytes().startswith(b"%PDF")


def test_primary_navigation_and_standard_table_labels_are_stable() -> None:
    assert NAVIGATION_ITEMS == (
        "Home",
        "Assessment",
        "Validation",
        "Readiness",
        "Hazards",
        "Mapping",
        "Critical Controls",
        "Reports",
        "Resources",
    )
    table = friendly_frame(pd.DataFrame({"hazard_id": ["H001"], "risk_score": [15]}))
    assert list(table.columns) == ["Hazard ID", "Risk score"]


def test_validation_importance_groups_keep_blocking_alerts_bounded() -> None:
    class Finding:
        def __init__(self, severity: str, blocks_analysis: bool) -> None:
            self.severity = severity
            self.blocks_analysis = blocks_analysis

    findings = [
        Finding("Error", True),
        Finding("Error", False),
        Finding("Warning", False),
        Finding("Information", False),
    ]
    assert validation_importance_summary(findings) == {
        "Critical": 1,
        "Action required": 1,
        "Review recommended": 1,
        "Informational": 1,
    }


def test_streamlit_primary_navigation_smoke_covers_each_page() -> None:
    app = AppTest.from_file("app.py")
    app.run(timeout=30)
    assert not app.exception
    for route in NAVIGATION_ITEMS[1:]:
        app.radio[0].set_value(route).run(timeout=30)
        assert not app.exception
        assert app.tabs == []
