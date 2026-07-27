"""Application shell and sidebar navigation for MOBRA."""

from __future__ import annotations

from datetime import datetime
from html import escape

import pandas as pd
import streamlit as st

from mobra.config import (
    APP_NAME,
    count_phrase,
)
from mobra.validation import ValidationResult
from ui.components import render_logo
from ui.state import PENDING_PAGE_KEY, SCROLL_TO_TOP_KEY


PAGE_GROUPS = {
    "Overview": ["Home"],
    "Data": ["Data Import", "Data Validation"],
    "Assessment": ["Requirements Assessment", "Hazard Register"],
    "Analysis": ["Risk Analysis", "Readiness Dashboard", "Mission Map"],
    "Decision": ["Deployment Decision", "Corrective Actions"],
    "Reporting": ["Reports and Export"],
    "System Information": ["Methodology", "Research and References", "About MOBRA"],
}
PAGE_ICONS = {
    "Home": "\u2302",
    "Data Import": "\u21e7",
    "Data Validation": "\u2713",
    "Requirements Assessment": "\u25a4",
    "Hazard Register": "\u26a0",
    "Risk Analysis": "\u25a6",
    "Readiness Dashboard": "\u25d4",
    "Mission Map": "\u2316",
    "Deployment Decision": "\u25c6",
    "Corrective Actions": "\u21bb",
    "Reports and Export": "\u21e9",
    "Methodology": "\u2211",
    "Research and References": "\u25a1",
    "About MOBRA": "\u24d8",
}
PAGE_LABELS = {
    "Home": "Overview",
    "Data Import": "Data Import",
    "Data Validation": "Data Validation",
    "Requirements Assessment": "Requirements",
    "Hazard Register": "Hazard Register",
    "Risk Analysis": "Risk Matrix & Heatmap",
    "Readiness Dashboard": "Readiness Analysis",
    "Mission Map": "Mission Map",
    "Deployment Decision": "Deployment Decision",
    "Corrective Actions": "Corrective Actions",
    "Reports and Export": "Reports and Export",
    "Methodology": "Methodology",
    "Research and References": "Research & Manuscript",
    "About MOBRA": "About MOBRA",
}
PAGE_ORDER = [page for pages in PAGE_GROUPS.values() for page in pages]
PAGE_TO_GROUP = {page: group for group, pages in PAGE_GROUPS.items() for page in pages}


def render_sidebar(
    data_meta: dict,
    hazard_result: ValidationResult,
    requirement_result: ValidationResult,
) -> str:
    """Render concise navigation and the active-dataset summary."""
    if st.session_state.pop("mobra_refresh_notice", False):
        st.toast("View refreshed. Assessment data preserved.", icon="🔄")
    pending_page = st.session_state.pop(PENDING_PAGE_KEY, None)
    if pending_page in PAGE_ORDER:
        st.session_state.active_page = pending_page
        st.session_state.mobra_navigation = pending_page
    current = st.session_state.get("active_page", "Home")
    if current not in PAGE_ORDER:
        current = "Home"
    with st.sidebar:
        render_logo(dark_background=True, width=280)
        st.markdown('<div class="mobra-sidebar-rule"></div>', unsafe_allow_html=True)
        selected = st.radio(
            "Navigation",
            PAGE_ORDER,
            index=PAGE_ORDER.index(current),
            format_func=lambda page: f"{PAGE_ICONS[page]}  {PAGE_LABELS[page]}",
            key="mobra_navigation",
        )
        if selected != current:
            st.session_state[SCROLL_TO_TOP_KEY] = True
        st.session_state.active_page = selected
        st.markdown('<div class="mobra-sidebar-rule"></div>', unsafe_allow_html=True)
        st.markdown("#### Active dataset")
        source_label = str(data_meta.get("source_label", "No data"))
        st.markdown(
            f'<div class="mobra-sidebar-source">{escape(source_label)}</div>',
            unsafe_allow_html=True,
        )
        filenames = {
            str(data_meta.get("hazard_filename", "")),
            str(data_meta.get("requirements_filename", "")),
        }
        filenames.discard("")
        st.caption("File")
        st.markdown(
            f'<div class="mobra-sidebar-file">{escape(" / ".join(sorted(filenames)) or "Not available")}</div>',
            unsafe_allow_html=True,
        )
        hazard_rows = len(data_meta.get("hazards_raw", pd.DataFrame()))
        requirement_rows = len(data_meta.get("requirements_raw", pd.DataFrame()))
        st.caption("Records")
        st.write(
            f"{count_phrase(hazard_rows, 'hazard')} \u00b7 "
            f"{count_phrase(requirement_rows, 'requirement')}"
        )
        updated_raw = data_meta.get("last_updated")
        try:
            updated = datetime.fromisoformat(str(updated_raw)).strftime("%Y-%m-%d %H:%M")
        except (TypeError, ValueError):
            updated = "Not available"
        st.caption("Last update")
        st.write(updated)
        errors = len(hazard_result.errors) + len(requirement_result.errors)
        warnings = len(hazard_result.warnings) + len(requirement_result.warnings)
        if errors:
            st.error(f"Validation: {count_phrase(errors, 'error')}")
        elif warnings:
            st.warning(f"Validation: Passed with {count_phrase(warnings, 'warning')}")
        else:
            st.success("Validation: Passed")
        if st.button(
            "↻ Refresh View",
            key="mobra_refresh_view",
            width="stretch",
            help="Rerun the interface without clearing the active assessment.",
        ):
            st.session_state.mobra_view_refreshed_at = datetime.now().isoformat(
                timespec="microseconds"
            )
            st.session_state.mobra_refresh_notice = True
            st.rerun()
        st.markdown('<div class="mobra-sidebar-rule"></div>', unsafe_allow_html=True)
        st.caption(f"{APP_NAME} \u00b7 Scientific decision support")
        st.caption("Synthetic data are always labelled and never represented as operational evidence.")
    return selected
