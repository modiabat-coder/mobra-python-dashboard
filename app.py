"""Streamlit front end for the MOBRA computational verification prototype."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from mobra.charts import bri_gauge, domain_figure, heatmap_figure, risk_counts_figure
from mobra.decisions import deployment_decision
from mobra.io import list_excel_sheets, read_data_file, source_name, split_unified_file
from mobra.readiness import calculate_bri, data_quality_summary, domain_readiness, failed_critical_controls
from mobra.reporting import make_html_report
from mobra.risk import RISK_LEVELS, assert_heatmap_total, classify_risk, heatmap_total
from mobra.validation import ValidationResult, normalise_columns, validate_hazards, validate_requirements

# Backward-compatible names used by the original prototype and notebooks.
read_uploaded_file = read_data_file
make_heatmap = heatmap_figure
make_bri_gauge = bri_gauge


APP_TITLE = "MOBRA — Mobile Operational Biosecurity Readiness Assessment"
BASE_DIR = Path(__file__).resolve().parent


def csv_bytes(df: pd.DataFrame) -> bytes:
    """Serialize an analysis copy as UTF-8 with a BOM for Windows Excel."""
    return df.to_csv(index=False).encode("utf-8-sig")


def excel_bytes(hazards: pd.DataFrame, requirements: pd.DataFrame, summary: dict[str, Any]) -> bytes:
    """Create a portable Excel workbook containing analyzed data and summary."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        hazards.to_excel(writer, sheet_name="Analyzed_Hazards", index=False)
        requirements.to_excel(writer, sheet_name="Analyzed_Requirements", index=False)
        pd.DataFrame([summary]).to_excel(writer, sheet_name="Summary", index=False)
    return buffer.getvalue()


def _file_selector(label: str, file: Any) -> tuple[pd.DataFrame | None, str]:
    """Read one uploaded file, allowing robust Excel sheet selection."""
    if file is None:
        return None, ""
    name = source_name(file)
    sheet: str | int = 0
    sheets = list_excel_sheets(file)
    if sheets:
        sheet = st.selectbox(f"Excel sheet — {name}", sheets, key=f"sheet_{label}_{name}")
    try:
        return read_data_file(file, sheet_name=sheet), name
    except Exception as exc:  # pragma: no cover - displayed by Streamlit
        st.error(f"Could not read {name}: {exc}")
        return None, name


def _mapping_controls(df: pd.DataFrame, kind: str) -> dict[str, str]:
    """Render manual overrides for the required fields while retaining auto-mapping."""
    normalized = normalise_columns(df)
    targets = {"hazards": ["hazard", "likelihood", "consequence"], "requirements": ["requirement", "observed_score", "maximum_score"]}[kind]
    overrides: dict[str, str] = {}
    with st.expander(f"Optional {kind} column overrides", expanded=False):
        st.caption("Automatic aliases are applied first. Choose a source column only when automatic mapping needs help.")
        for target in targets:
            options = ["(automatic)", *normalized.columns.tolist()]
            selected = st.selectbox(target, options, key=f"override_{kind}_{target}")
            if selected != "(automatic)":
                overrides[target] = selected
    return overrides


def _preview_editor(df: pd.DataFrame, label: str) -> pd.DataFrame:
    """Offer an explicit, optional editable preview before validation."""
    st.caption(f"{label}: {len(df)} rows × {len(df.columns)} columns")
    if st.checkbox(f"Enable editable preview for {label}", value=False, key=f"edit_{label}"):
        return st.data_editor(df, num_rows="dynamic", use_container_width=True, key=f"editor_{label}")
    st.dataframe(df.head(20), use_container_width=True, hide_index=True)
    return df


def _show_validation(result: ValidationResult, label: str) -> None:
    with st.expander(f"{label} validation details", expanded=bool(result.errors or result.warnings)):
        if result.errors:
            for message in result.errors:
                st.error(message)
        if result.warnings:
            for message in result.warnings:
                st.warning(message)
        st.json(result.quality)


def _load_inputs() -> tuple[pd.DataFrame | None, pd.DataFrame | None, str, str]:
    with st.sidebar:
        st.header("Data input")
        mode = st.radio("Input mode", ["Included demonstration data", "Two files", "One unified file"], index=0)
        if mode == "Included demonstration data":
            return (
                pd.read_csv(BASE_DIR / "sample_data" / "hazards_sample.csv"),
                pd.read_csv(BASE_DIR / "sample_data" / "requirements_sample.csv"),
                "hazards_sample.csv",
                "requirements_sample.csv",
            )
        if mode == "Two files":
            hazard_file = st.file_uploader("Hazard register", type=["csv", "xlsx", "xls"], key="hazard_upload")
            requirement_file = st.file_uploader("Operational requirements / ORL", type=["csv", "xlsx", "xls"], key="requirements_upload")
            hazard_df, hazard_name = _file_selector("hazard", hazard_file)
            requirement_df, requirement_name = _file_selector("requirement", requirement_file)
            return hazard_df, requirement_df, hazard_name, requirement_name
        unified_file = st.file_uploader("Unified hazard + requirements file", type=["csv", "xlsx", "xls"], key="unified_upload")
        unified_df, unified_name = _file_selector("unified", unified_file)
        if unified_df is None:
            return None, None, unified_name, unified_name
        try:
            hazards, requirements = split_unified_file(unified_df)
            return hazards, requirements, unified_name, unified_name
        except ValueError as exc:
            st.error(str(exc))
            return None, None, unified_name, unified_name


def main() -> None:
    st.set_page_config(page_title="MOBRA Dashboard", page_icon="🧬", layout="wide")
    st.markdown("<style>.block-container{padding-top:1.5rem}.stMetric{background:#f8fafc;border:1px solid #e2e8f0;padding:12px;border-radius:10px}</style>", unsafe_allow_html=True)
    st.title("🧬 MOBRA Dashboard")
    st.caption("Upload laboratory hazard and ORL data, validate records, calculate risk and readiness, and export a standalone report.")
    st.info("Prototype scope: external-dataset-based computational verification. Outputs do not establish clinical, operational, or regulatory validation.")

    hazards_raw, requirements_raw, hazard_filename, requirements_filename = _load_inputs()
    if hazards_raw is None or requirements_raw is None:
        st.info("Provide both datasets to begin the assessment.")
        return

    st.subheader("1. Preview and column mapping")
    hazard_overrides = _mapping_controls(hazards_raw, "hazards")
    requirement_overrides = _mapping_controls(requirements_raw, "requirements")
    col1, col2 = st.columns(2)
    with col1:
        hazards_raw = _preview_editor(hazards_raw, "Hazards")
    with col2:
        requirements_raw = _preview_editor(requirements_raw, "Requirements")
    hazard_result = validate_hazards(hazards_raw, hazard_overrides)
    requirement_result = validate_requirements(requirements_raw, requirement_overrides)
    _show_validation(hazard_result, "Hazard")
    _show_validation(requirement_result, "Requirement")
    all_messages = [*hazard_result.errors, *hazard_result.warnings, *requirement_result.errors, *requirement_result.warnings]
    if hazard_result.errors or requirement_result.errors:
        st.error("Analysis is paused until validation errors are corrected. Invalid input rows remain visible for download and review.")
        return

    hazards = hazard_result.data
    requirements = requirement_result.data
    with st.sidebar:
        st.divider()
        selected_levels = st.multiselect("Risk categories shown in charts", RISK_LEVELS, default=RISK_LEVELS)
    filtered_hazards = hazards[hazards["risk_category"].isin(selected_levels)].copy()
    bri = calculate_bri(requirements)
    domains = domain_readiness(requirements)
    decision, reasons = deployment_decision(hazards, requirements, bri)
    quality = data_quality_summary(hazards, requirements)
    assert_heatmap_total(filtered_hazards)

    st.subheader("2. Executive dashboard")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Overall BRI", "N/A" if pd.isna(bri) else f"{bri:.1f}%")
    k2.metric("Filtered hazards", len(filtered_hazards), f"of {len(hazards)} total")
    k3.metric("High + Extreme (filtered)", int(filtered_hazards["risk_category"].isin(["High", "Extreme"]).sum()))
    k4.metric("Failed critical controls", len(failed_critical_controls(requirements)))
    if decision == "READY FOR DEPLOYMENT":
        st.success(f"Decision: {decision}")
    elif decision == "CONDITIONAL DEPLOYMENT":
        st.warning(f"Decision: {decision}")
    else:
        st.error(f"Decision: {decision}")
    st.write(" ".join(reasons))

    tab1, tab2, tab3, tab4 = st.tabs(["Executive dashboard", "Hazard analysis", "Readiness analysis", "Data & exports"])
    with tab1:
        left, right = st.columns(2)
        left.plotly_chart(bri_gauge(bri), use_container_width=True, key="executive_bri")
        right.plotly_chart(risk_counts_figure(filtered_hazards), use_container_width=True, key="executive_risk_counts")
        st.plotly_chart(domain_figure(domains), use_container_width=True, key="executive_domains")
    with tab2:
        st.plotly_chart(heatmap_figure(filtered_hazards), use_container_width=True, key="hazard_heatmap")
        st.caption(f"Heat-map cell counts verified: {heatmap_total(filtered_hazards)} cells represent {len(filtered_hazards)} filtered valid hazards.")
        st.dataframe(filtered_hazards.sort_values("risk_score", ascending=False), use_container_width=True, hide_index=True)
        st.subheader("Top risks")
        st.dataframe(filtered_hazards.nlargest(10, "risk_score"), use_container_width=True, hide_index=True)
    with tab3:
        st.plotly_chart(domain_figure(domains), use_container_width=True, key="readiness_domains")
        st.dataframe(domains, use_container_width=True, hide_index=True)
        st.subheader("Mission-critical controls")
        st.dataframe(requirements[requirements["critical_control"]], use_container_width=True, hide_index=True)
        st.subheader("Failed critical controls")
        st.dataframe(failed_critical_controls(requirements), use_container_width=True, hide_index=True)
    with tab4:
        st.subheader("Validated data and quality")
        st.json(quality)
        st.dataframe(hazards, use_container_width=True, hide_index=True)
        st.dataframe(requirements, use_container_width=True, hide_index=True)
        summary = {
            "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
            "hazard_file": hazard_filename,
            "requirements_file": requirements_filename,
            "bri_pct": None if pd.isna(bri) else round(float(bri), 2),
            "decision": decision,
            "decision_reasons": reasons,
            "hazard_count_total": len(hazards),
            "hazard_count_filtered": len(filtered_hazards),
            "risk_counts_filtered": filtered_hazards["risk_category"].value_counts().reindex(RISK_LEVELS, fill_value=0).astype(int).to_dict(),
            "heatmap_cell_total": heatmap_total(filtered_hazards),
            "failed_critical_controls": len(failed_critical_controls(requirements)),
            "data_quality": quality,
            "validation_messages": all_messages,
        }
        html = make_html_report(hazards, requirements, bri, decision, reasons, hazard_filename=hazard_filename, requirements_filename=requirements_filename, validation_messages=all_messages, filtered_hazards=filtered_hazards)
        st.download_button("Download standalone HTML report", html.encode("utf-8"), "MOBRA_Report.html", "text/html")
        st.download_button("Download analyzed hazards (CSV)", csv_bytes(hazards), "MOBRA_Analyzed_Hazards.csv", "text/csv")
        st.download_button("Download analyzed requirements (CSV)", csv_bytes(requirements), "MOBRA_Analyzed_Requirements.csv", "text/csv")
        st.download_button("Download summary (JSON)", json.dumps(summary, indent=2, ensure_ascii=False).encode("utf-8"), "MOBRA_Summary.json", "application/json")
        st.download_button("Download analyzed workbook (XLSX)", excel_bytes(hazards, requirements, summary), "MOBRA_Analyzed_Data.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.download_button("Download hazard template (CSV)", (BASE_DIR / "sample_data" / "hazards_template.csv").read_bytes(), "MOBRA_Hazards_Template.csv", "text/csv")
        st.download_button("Download requirements template (CSV)", (BASE_DIR / "sample_data" / "requirements_template.csv").read_bytes(), "MOBRA_Requirements_Template.csv", "text/csv")


if __name__ == "__main__":
    main()
