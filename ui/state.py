"""Session-state helpers for active MOBRA datasets and navigation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from mobra.config import PROJECT_ROOT, SYNTHETIC_DATA_LABEL


def initialize_session_state() -> None:
    """Load the clearly labelled synthetic demonstration dataset on first run."""
    if "mobra_data" in st.session_state:
        return
    hazards_path = PROJECT_ROOT / "sample_data" / "hazards_sample.csv"
    requirements_path = PROJECT_ROOT / "sample_data" / "requirements_sample.csv"
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


def navigate_to(page: str) -> None:
    """Set the requested page and rerun the application."""
    st.session_state.active_page = page
    st.rerun()
