"""Streamlit entry point for the MOBRA assessment application."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from mobra.auth import authentication_gate, load_auth_config, render_logout_control
from mobra.charts import bri_gauge, heatmap_figure
from mobra.config import APP_FULL_NAME, APP_NAME, FAVICON_PATH
from mobra.io import read_data_file
from mobra.reporting import csv_bytes
from mobra.security import spreadsheet_safe_frame
from ui.components import render_scroll_to_top
from ui.layout import render_sidebar
from ui.pages import build_assessment_context, render_page
from ui.state import SCROLL_TO_TOP_KEY, active_data, initialize_session_state
from ui.styles import apply_global_styles


# Backward-compatible public names used by the original prototype and notebooks.
read_uploaded_file = read_data_file
make_heatmap = heatmap_figure
make_bri_gauge = bri_gauge
APP_TITLE = f"{APP_NAME} — {APP_FULL_NAME}"
BASE_DIR = Path(__file__).resolve().parent


def excel_bytes(
    hazards: pd.DataFrame,
    requirements: pd.DataFrame,
    summary: dict[str, Any],
) -> bytes:
    """Preserve the original three-sheet workbook helper for external callers."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        spreadsheet_safe_frame(hazards).to_excel(
            writer,
            sheet_name="Analyzed_Hazards",
            index=False,
        )
        spreadsheet_safe_frame(requirements).to_excel(
            writer,
            sheet_name="Analyzed_Requirements",
            index=False,
        )
        spreadsheet_safe_frame(pd.DataFrame([summary])).to_excel(
            writer,
            sheet_name="Summary",
            index=False,
        )
    return buffer.getvalue()


def main() -> None:
    """Configure and render the current MOBRA page."""
    page_icon: str | Path = FAVICON_PATH if FAVICON_PATH.exists() else "🛡️"
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon=str(page_icon),
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            "About": (
                f"{APP_NAME} — {APP_FULL_NAME}. "
                "Scientific decision support for mobile laboratory readiness and biosecurity."
            )
        },
    )
    apply_global_styles()
    auth_config = load_auth_config()
    if not authentication_gate(auth_config):
        return
    initialize_session_state()
    meta = active_data()
    context = build_assessment_context(meta)
    page = render_sidebar(
        meta,
        context.hazard_result,
        context.requirement_result,
    )
    render_logout_control(auth_config)
    should_scroll_to_top = bool(st.session_state.pop(SCROLL_TO_TOP_KEY, False))
    render_page(page, context)
    if should_scroll_to_top:
        render_scroll_to_top()


if __name__ == "__main__":
    main()
