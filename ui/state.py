"""Session-state helpers for active MOBRA datasets and navigation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from mobra.config import PROJECT_ROOT, SYNTHETIC_DATA_LABEL


PENDING_PAGE_KEY = "mobra_pending_page"
SCROLL_TO_TOP_KEY = "mobra_scroll_to_top"


def initialize_session_state() -> None:
    """Load the clearly labelled synthetic demonstration dataset on first run."""
    hazards_path = PROJECT_ROOT / "sample_data" / "hazards_sample.csv"
    requirements_path = PROJECT_ROOT / "sample_data" / "requirements_sample.csv"
    mapping_path = PROJECT_ROOT / "sample_data" / "requirement_hazard_mapping.csv"
    critical_profile_path = PROJECT_ROOT / "sample_data" / "critical_control_profile.csv"
    if "mobra_data" not in st.session_state:
        st.session_state.mobra_data = {
            "hazards_raw": pd.read_csv(hazards_path),
            "requirements_raw": pd.read_csv(requirements_path),
            "hazard_filename": hazards_path.name,
            "requirements_filename": requirements_path.name,
            "source_label": SYNTHETIC_DATA_LABEL,
            "source_kind": "synthetic",
            "file_size": hazards_path.stat().st_size + requirements_path.stat().st_size,
            "selected_sheet": "Not applicable",
            "last_updated": datetime.now().isoformat(timespec="seconds"),
            "confirmed": True,
        }
    if "mobra_supporting_data" not in st.session_state:
        st.session_state.mobra_supporting_data = {
            "mapping_raw": pd.read_csv(mapping_path),
            "mapping_filename": mapping_path.name,
            "critical_profile_raw": pd.read_csv(critical_profile_path),
            "critical_profile_filename": critical_profile_path.name,
            "source_kind": "synthetic",
        }
    st.session_state.setdefault("hazard_mapping", {})
    st.session_state.setdefault("requirement_mapping", {})
    st.session_state.setdefault("active_page", "Home")


def set_active_data(
    hazards: pd.DataFrame,
    requirements: pd.DataFrame,
    *,
    hazard_filename: str,
    requirements_filename: str,
    source_label: str,
    source_kind: str = "uploaded",
    file_size: int = 0,
    selected_sheet: str = "Not applicable",
) -> None:
    """Replace the active analysis copy after explicit user confirmation."""
    st.session_state.mobra_data = {
        "hazards_raw": hazards.copy(),
        "requirements_raw": requirements.copy(),
        "hazard_filename": Path(hazard_filename).name,
        "requirements_filename": Path(requirements_filename).name,
        "source_label": source_label,
        "source_kind": source_kind,
        "file_size": int(file_size),
        "selected_sheet": selected_sheet,
        "last_updated": datetime.now().isoformat(timespec="seconds"),
        "confirmed": True,
    }


def active_data() -> dict[str, Any]:
    """Return the active session dataset metadata and raw frames."""
    initialize_session_state()
    return st.session_state.mobra_data


def active_supporting_data() -> dict[str, Any]:
    """Return optional mapping and critical-control governance datasets."""
    initialize_session_state()
    return st.session_state.mobra_supporting_data


def set_supporting_data(
    mapping: pd.DataFrame,
    critical_profile: pd.DataFrame,
    *,
    mapping_filename: str,
    critical_profile_filename: str,
    source_kind: str = "uploaded",
) -> None:
    """Replace the optional supporting datasets without changing assessment scores."""
    st.session_state.mobra_supporting_data = {
        "mapping_raw": mapping.copy(),
        "mapping_filename": Path(mapping_filename).name,
        "critical_profile_raw": critical_profile.copy(),
        "critical_profile_filename": Path(critical_profile_filename).name,
        "source_kind": source_kind,
    }


def navigate_to(page: str) -> None:
    """Set the requested page and rerun the application."""
    st.session_state[PENDING_PAGE_KEY] = page
    st.session_state[SCROLL_TO_TOP_KEY] = True
    st.rerun()
