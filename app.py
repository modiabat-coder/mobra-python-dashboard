"""Streamlit front end for the MOBRA computational verification prototype."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from mobra.acceptance import (
    ACCEPTANCE_DISPOSITIONS,
    MISSING_RESIDUAL_POLICIES,
    RISK_ACCEPTANCE_LIMITATION,
    RiskAcceptancePolicy,
    apply_risk_acceptance,
    risk_acceptance_summary,
    risk_acceptance_summary_table,
)
from mobra.branding import asset_path, brand_summary, load_brand_palette
from mobra.charts import bri_gauge, domain_figure, heatmap_figure, mapping_sankey_figure, risk_counts_figure
from mobra.config import (
    APP_TITLE,
    APP_VERSION,
    APPLICATION_DEFINITION,
    AUTHOR_NAME,
    FULL_DISCLAIMER,
    HOW_TO_USE_STEPS,
    INTRODUCTION_COMPONENTS,
    NON_ENDORSEMENT_STATEMENT,
    NORMATIVE_EVIDENCE_WORDING,
    PROTOTYPE_STATUS,
    WHAT_MOBRA_DOES_NOT_DO,
    application_metadata,
    configured_author_email,
)
from mobra.critical_controls import (
    CONTROL_OUTCOMES,
    CRITICAL_CONTROL_LIMITATION,
    CRITICALITY_LEVELS,
    CriticalControlAssessment,
    CriticalControlProfileValidationResult,
    assess_critical_controls,
    critical_control_summary_table,
)
from mobra.decisions import deployment_decision
from mobra.educational_media import educational_media_package, load_educational_media, media_summary
from mobra.export_contracts import EXCEL_SHEETS, EXPORT_FILENAMES
from mobra.help_content import HELP_TOPICS, render_help
from mobra.io import (
    FileValidationError,
    list_excel_sheets,
    read_data_file,
    read_data_file_with_validation,
    source_name,
    split_unified_file,
)
from mobra.manuscript import manuscript_download_bytes, manuscript_is_current, manuscript_metadata
from mobra.mapping import (
    ALLOWED_CONTROL_ROLES,
    ALLOWED_RELATIONSHIP_TYPES,
    MAPPING_REQUIRED_COLUMNS,
    MappingValidationResult,
    coverage_by_requirement_domain,
    enrich_mapping,
    hazard_mapping_ranking,
    hazards_without_requirements,
    mapping_coverage_summary,
    mapping_coverage_table,
    requirement_mapping_ranking,
    requirements_without_hazards,
    validate_mapping,
)
from mobra.notifications import emit_notification
from mobra.operational_tools import (
    MAX_EMAIL_ATTACHMENT_BYTES,
    TEMPLATE_CATALOGUE,
    EmailBackupError,
    EmailConfig,
    build_backup_zip,
    build_field_assessment_package,
    build_hazard_import_template,
    build_hazard_pdf,
    build_hazard_register_workbook,
    build_orl_assessment_workbook,
    build_orl_pdf,
    build_requirements_import_template,
    reset_assessment_state,
    send_email_backup,
    template_catalogue_csv,
)
from mobra.readiness import calculate_bri, data_quality_summary, domain_readiness, failed_critical_controls
from mobra.reporting import make_html_report
from mobra.resources import (
    build_open_access_reference_package,
    catalogue_csv_bytes,
    catalogue_xlsx_bytes,
    load_normative_resources,
    load_supporting_literature,
    resource_catalogue_frame,
)
from mobra.risk import RISK_LEVELS, assert_heatmap_total, heatmap_total
from mobra.validation import ValidationResult, normalise_columns, validate_hazards, validate_requirements
from mobra.validation_exports import invalid_records_workbook_bytes, validation_json_fields, write_validation_sheets
from mobra.validation_findings import (
    VALIDATION_LIMITATION,
    CrossDatasetValidationResult,
    ValidationFinding,
    findings_frame,
    summaries_frame,
    validate_cross_dataset_consistency,
    validation_overview,
    validation_summary,
)

# Backward-compatible names used by the original prototype and notebooks.
read_uploaded_file = read_data_file
make_heatmap = heatmap_figure
make_bri_gauge = bri_gauge


BASE_DIR = Path(__file__).resolve().parent


def csv_bytes(df: pd.DataFrame) -> bytes:
    """Serialize an analysis copy as UTF-8 with a BOM for Windows Excel."""
    return df.to_csv(index=False).encode("utf-8-sig")


def excel_bytes(
    hazards: pd.DataFrame,
    requirements: pd.DataFrame,
    summary: dict[str, Any],
    mapping: pd.DataFrame | None = None,
    risk_acceptance_policy: RiskAcceptancePolicy | None = None,
    critical_profile: pd.DataFrame | None = None,
    critical_control_assessment: CriticalControlAssessment | None = None,
    validation_summaries: list[dict[str, Any]] | None = None,
    validation_findings: list[ValidationFinding] | None = None,
    validation_datasets: dict[str, pd.DataFrame | None] | None = None,
) -> bytes:
    """Create a portable Excel workbook containing analyzed data and summary."""
    acceptance_policy = risk_acceptance_policy or RiskAcceptancePolicy()
    analyzed_hazards = (
        hazards if "risk_acceptance_status" in hazards.columns else apply_risk_acceptance(hazards, acceptance_policy)
    )
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        analyzed_hazards.to_excel(writer, sheet_name=EXCEL_SHEETS["hazards"], index=False)
        requirements.to_excel(writer, sheet_name=EXCEL_SHEETS["requirements"], index=False)
        pd.DataFrame([summary]).to_excel(writer, sheet_name=EXCEL_SHEETS["summary"], index=False)
        if mapping is not None:
            mapping.to_excel(writer, sheet_name=EXCEL_SHEETS["mapping"], index=False)
        risk_acceptance_summary_table(analyzed_hazards, acceptance_policy).to_excel(
            writer,
            sheet_name=EXCEL_SHEETS["risk_acceptance"],
            index=False,
        )
        if critical_profile is not None and critical_control_assessment is not None and critical_control_assessment.ok:
            critical_profile.to_excel(writer, sheet_name=EXCEL_SHEETS["critical_profile"], index=False)
            critical_control_assessment.data.to_excel(
                writer, sheet_name=EXCEL_SHEETS["critical_assessment"], index=False
            )
            critical_control_summary_table(critical_control_assessment).to_excel(
                writer,
                sheet_name=EXCEL_SHEETS["critical_summary"],
                index=False,
            )
        write_validation_sheets(
            writer,
            validation_summaries or [],
            validation_findings or [],
            validation_datasets
            or {
                "Hazards": hazards,
                "Requirements": requirements,
                "Mapping": mapping,
                "Critical-Control Profile": critical_profile,
            },
        )
    return buffer.getvalue()


def _file_selector(label: str, file: Any) -> tuple[pd.DataFrame | None, str]:
    """Read one uploaded file, allowing robust Excel sheet selection."""
    if file is None:
        return None, ""
    name = source_name(file)
    sheet: str | int = 0
    try:
        sheets = list_excel_sheets(file)
        if sheets:
            sheet = st.selectbox(f"Excel sheet — {name}", sheets, key=f"sheet_{label}_{name}")
        result = read_data_file_with_validation(file, sheet_name=sheet)
        st.session_state.setdefault("_mobra_file_findings", []).extend(result.findings)
        st.session_state.setdefault("_mobra_file_sheets", {})[name] = result.sheet_name
        for warning in result.warnings[:5]:
            st.warning(warning)
        if result.errors:
            for message in result.errors[:5]:
                st.error(message)
            return None, name
        return result.data, name
    except (FileValidationError, ValueError, OSError) as exc:  # pragma: no cover - displayed by Streamlit
        fallback = read_data_file_with_validation(file, sheet_name=0)
        st.session_state.setdefault("_mobra_file_findings", []).extend(fallback.findings)
        st.error(f"Could not read {name}: {exc}")
        return None, name


def _mapping_controls(df: pd.DataFrame, kind: str) -> dict[str, str]:
    """Render manual overrides for the required fields while retaining auto-mapping."""
    normalized = normalise_columns(df)
    targets = {
        "hazards": ["hazard", "likelihood", "consequence"],
        "requirements": ["requirement", "observed_score", "maximum_score"],
    }[kind]
    overrides: dict[str, str] = {}
    with st.expander(f"Optional {kind} column overrides", expanded=False):
        st.caption(
            "Automatic aliases are applied first. Choose a source column only when automatic mapping needs help."
        )
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


def _show_validation(
    result: ValidationResult | MappingValidationResult | CriticalControlProfileValidationResult,
    label: str,
) -> None:
    with st.expander(f"{label} validation details", expanded=bool(result.errors or result.warnings)):
        if result.errors:
            for message in result.errors[:10]:
                st.error(message)
            if len(result.errors) > 10:
                st.caption(f"{len(result.errors) - 10} additional errors are available in validation downloads.")
        if result.warnings:
            for message in result.warnings[:10]:
                st.warning(message)
            if len(result.warnings) > 10:
                st.caption(f"{len(result.warnings) - 10} additional warnings are available in validation downloads.")
        information = getattr(result, "information", [])
        for message in information[:5]:
            st.info(message)
        if getattr(result, "findings", None):
            st.dataframe(findings_frame(result.findings), use_container_width=True, hide_index=True)
        st.json(result.quality)


def _load_inputs() -> tuple[
    pd.DataFrame | None,
    pd.DataFrame | None,
    pd.DataFrame | None,
    pd.DataFrame | None,
    str,
    str,
    str,
    str,
]:
    with st.sidebar:
        st.header("Data input")
        mode = st.radio("Input mode", ["Included demonstration data", "Two files", "One unified file"], index=0)
        st.subheader("Assessment metadata")
        st.session_state["_mobra_assessment_metadata"] = {
            "Laboratory or mission": st.text_input("Laboratory or mission", key="assessment_mission"),
            "Location": st.text_input("Location", key="assessment_location"),
            "Assessment date": st.date_input("Assessment date", value=None, key="assessment_date"),
            "Assessor": st.text_input("Assessor", key="assessment_assessor"),
            "Reviewers": st.text_input("Reviewers", key="assessment_reviewers"),
            "Mission type": st.text_input("Mission type", key="assessment_mission_type"),
            "Notes": st.text_area("Assessment notes", key="assessment_notes"),
        }
        mapping_file = st.file_uploader(
            "Requirement–hazard mapping (optional override)",
            type=["csv", "xlsx", "xls"],
            key="mapping_upload",
        )
        profile_file = st.file_uploader(
            "Critical-control profile (optional override)",
            type=["csv", "xlsx", "xls"],
            key="critical_profile_upload",
        )
        if mapping_file is not None:
            mapping_df, mapping_name = _file_selector("mapping", mapping_file)
        elif mode == "Included demonstration data":
            mapping_df = pd.read_csv(BASE_DIR / "sample_data" / "requirement_hazard_mapping.csv")
            mapping_name = "requirement_hazard_mapping.csv"
        else:
            mapping_df, mapping_name = None, ""
        if profile_file is not None:
            profile_df, profile_name = _file_selector("critical_profile", profile_file)
        elif mode == "Included demonstration data":
            profile_df = pd.read_csv(BASE_DIR / "sample_data" / "critical_control_profile.csv")
            profile_name = "critical_control_profile.csv"
        else:
            profile_df, profile_name = None, ""
        if mode == "Included demonstration data":
            return (
                pd.read_csv(BASE_DIR / "sample_data" / "hazards_sample.csv"),
                pd.read_csv(BASE_DIR / "sample_data" / "requirements_sample.csv"),
                mapping_df,
                profile_df,
                "hazards_sample.csv",
                "requirements_sample.csv",
                mapping_name,
                profile_name,
            )
        if mode == "Two files":
            hazard_file = st.file_uploader("Hazard register", type=["csv", "xlsx", "xls"], key="hazard_upload")
            requirement_file = st.file_uploader(
                "Operational requirements / ORL", type=["csv", "xlsx", "xls"], key="requirements_upload"
            )
            hazard_df, hazard_name = _file_selector("hazard", hazard_file)
            requirement_df, requirement_name = _file_selector("requirement", requirement_file)
            return (
                hazard_df,
                requirement_df,
                mapping_df,
                profile_df,
                hazard_name,
                requirement_name,
                mapping_name,
                profile_name,
            )
        unified_file = st.file_uploader(
            "Unified hazard + requirements file", type=["csv", "xlsx", "xls"], key="unified_upload"
        )
        unified_df, unified_name = _file_selector("unified", unified_file)
        if unified_df is None:
            return None, None, mapping_df, profile_df, unified_name, unified_name, mapping_name, profile_name
        try:
            hazards, requirements = split_unified_file(unified_df)
            return hazards, requirements, mapping_df, profile_df, unified_name, unified_name, mapping_name, profile_name
        except ValueError as exc:
            st.error(str(exc))
            return None, None, mapping_df, profile_df, unified_name, unified_name, mapping_name, profile_name


def _render_mapping_analysis(mapping: pd.DataFrame, requirements: pd.DataFrame, hazards: pd.DataFrame) -> None:
    """Render coverage findings filters details and readable mapping analyses."""
    summary = mapping_coverage_summary(mapping, requirements, hazards)
    details = enrich_mapping(mapping, requirements, hazards)
    unmapped_hazards = hazards_without_requirements(mapping, hazards)
    unmapped_requirements = requirements_without_hazards(mapping, requirements)
    st.caption(
        "The included links are representative demonstration mappings for software verification and methodology illustration. "
        "They are not expert-validated scientific or institutional mappings."
    )

    metric1, metric2, metric3, metric4 = st.columns(4)
    metric1.metric("Mapping links", summary["mapping_links"])
    metric2.metric(
        "Hazards mapped",
        f'{summary["hazards_mapped"]} / {summary["hazards_total"]}',
        f'{summary["hazard_coverage_pct"]:.1f}%',
    )
    metric3.metric(
        "Requirements mapped",
        f'{summary["requirements_mapped"]} / {summary["requirements_total"]}',
        f'{summary["requirement_coverage_pct"]:.1f}%',
    )
    metric4.metric("Critical links", summary["critical_links"])

    selected_hazard = st.selectbox(
        "Selected hazard details",
        sorted(hazards["hazard_id"].astype(str).unique()),
        key="mapping_selected_hazard",
    )
    selected_details = details.loc[details["hazard_id"].eq(selected_hazard)].copy()
    if not selected_details.empty:
        hazard_name = selected_details["hazard_name"].iloc[0]
        st.subheader(f"{selected_hazard} — {hazard_name}")
        selected_columns = [
            "requirement_id",
            "requirement_wording",
            "requirement_domain",
            "objective_evidence",
            "relationship_type",
            "mapping_rationale",
            "control_role",
            "critical_link",
        ]
        st.dataframe(selected_details[selected_columns], use_container_width=True, hide_index=True)
        st.plotly_chart(
            mapping_sankey_figure(selected_details, selected_hazard),
            use_container_width=True,
            key="selected_hazard_mapping_sankey",
        )

    st.subheader("Mapping filters and table")
    filter1, filter2, filter3 = st.columns(3)
    with filter1:
        hazard_filter = st.multiselect(
            "Filter by hazard ID",
            sorted(details["hazard_id"].dropna().astype(str).unique()),
            key="mapping_hazard_filter",
        )
        requirement_filter = st.multiselect(
            "Filter by requirement ID",
            sorted(details["requirement_id"].dropna().astype(str).unique()),
            key="mapping_requirement_filter",
        )
    with filter2:
        relationship_filter = st.multiselect(
            "Filter by relationship type",
            list(ALLOWED_RELATIONSHIP_TYPES),
            key="mapping_relationship_filter",
        )
        role_filter = st.multiselect(
            "Filter by control role",
            list(ALLOWED_CONTROL_ROLES),
            key="mapping_role_filter",
        )
    with filter3:
        critical_filter = st.selectbox(
            "Filter by critical link",
            ["All", "TRUE", "FALSE"],
            key="mapping_critical_filter",
        )

    filtered = details.copy()
    if hazard_filter:
        filtered = filtered[filtered["hazard_id"].isin(hazard_filter)]
    if requirement_filter:
        filtered = filtered[filtered["requirement_id"].isin(requirement_filter)]
    if relationship_filter:
        filtered = filtered[filtered["relationship_type"].isin(relationship_filter)]
    if role_filter:
        filtered = filtered[filtered["control_role"].isin(role_filter)]
    if critical_filter != "All":
        filtered = filtered[filtered["critical_link"].eq(critical_filter == "TRUE")]
    mapping_columns = [
        "mapping_id",
        "requirement_id",
        "requirement_wording",
        "requirement_domain",
        "objective_evidence",
        "hazard_id",
        "hazard_name",
        "relationship_type",
        "mapping_rationale",
        "control_role",
        "critical_link",
        "source_status",
    ]
    st.caption(f"Showing {len(filtered)} of {len(details)} mapping links.")
    st.dataframe(filtered[mapping_columns], use_container_width=True, hide_index=True)

    st.subheader("Coverage findings")
    finding1, finding2 = st.columns(2)
    with finding1:
        st.write("Hazards without requirements")
        st.dataframe(
            unmapped_hazards[[column for column in ("hazard_id", "hazard", "domain") if column in unmapped_hazards]],
            use_container_width=True,
            hide_index=True,
        )
    with finding2:
        st.write("Requirements without hazards")
        st.dataframe(
            unmapped_requirements[
                [
                    column
                    for column in ("requirement_id", "requirement", "domain", "objective_evidence", "evidence")
                    if column in unmapped_requirements
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("Link rankings")
    rank1, rank2 = st.columns(2)
    with rank1:
        st.write("Hazards ranked by linked requirements")
        st.dataframe(hazard_mapping_ranking(mapping, hazards), use_container_width=True, hide_index=True)
    with rank2:
        st.write("Requirements ranked by linked hazards")
        st.dataframe(requirement_mapping_ranking(mapping, requirements), use_container_width=True, hide_index=True)

    st.subheader("Coverage by requirement domain")
    st.dataframe(coverage_by_requirement_domain(mapping, requirements), use_container_width=True, hide_index=True)
    st.subheader("Critical-link summary")
    critical_links = details.loc[details["critical_link"].fillna(False).astype(bool)]
    critical_summary = (
        critical_links.groupby(["relationship_type", "control_role"], dropna=False)
        .size()
        .rename("critical_links")
        .reset_index()
        .sort_values("critical_links", ascending=False)
    )
    st.dataframe(critical_summary, use_container_width=True, hide_index=True)
    with st.expander("Critical-link details", expanded=False):
        st.dataframe(critical_links[mapping_columns], use_container_width=True, hide_index=True)


def _render_critical_control_governance(assessment: CriticalControlAssessment) -> None:
    """Render structured score, evidence, completeness, and disposition findings."""
    summary = assessment.summary
    data = assessment.data
    st.warning(CRITICAL_CONTROL_LIMITATION)
    st.info("A high BRI cannot override a deployment-blocking critical-control failure.")

    level_counts = summary["criticality_level_counts"]
    row1 = st.columns(4)
    row1[0].metric("Deployment-blocking controls", level_counts["Deployment-blocking"])
    row1[1].metric("Conditional controls", level_counts["Conditional"])
    row1[2].metric("Important controls", level_counts["Important"])
    row1[3].metric("Passed controls", summary["critical_control_outcome_counts"]["Pass"])
    row2 = st.columns(4)
    row2[0].metric("Deployment-blocking failures", summary["deployment_blocking_failure_count"])
    row2[1].metric("Conditional gaps", summary["conditional_gap_count"])
    row2[2].metric("Evidence deficiencies", summary["evidence_deficiency_count"])
    row2[3].metric("Incomplete records", summary["incomplete_critical_record_count"])
    row3 = st.columns(3)
    row3[0].metric("Manual-review items", summary["manual_review_count"])
    row3[1].metric("Formal approvals required", summary["formal_approval_required_count"])
    row3[2].metric("Compensating controls required", summary["compensating_control_required_count"])

    st.subheader("Governance filters and detailed assessment")
    filters1 = st.columns(3)
    filters2 = st.columns(3)
    with filters1[0]:
        selected_levels = st.multiselect("Criticality level", CRITICALITY_LEVELS, key="governance_level_filter")
    with filters1[1]:
        selected_outcomes = st.multiselect("Outcome", CONTROL_OUTCOMES, key="governance_outcome_filter")
    with filters1[2]:
        selected_dispositions = st.multiselect(
            "Disposition",
            sorted(data["critical_control_disposition"].dropna().astype(str).unique()),
            key="governance_disposition_filter",
        )
    with filters2[0]:
        selected_domains = st.multiselect("Domain", _filter_values(data, "domain"), key="governance_domain_filter")
    with filters2[1]:
        selected_evidence = st.multiselect(
            "Evidence status",
            ["Complete", "Missing", "Incomplete", "Not assessed"],
            key="governance_evidence_filter",
        )
    with filters2[2]:
        selected_ids = st.multiselect(
            "Requirement ID",
            _filter_values(data, "requirement_id"),
            key="governance_requirement_filter",
        )

    filtered = data.copy()
    for column, values in (
        ("criticality_level", selected_levels),
        ("critical_control_outcome", selected_outcomes),
        ("critical_control_disposition", selected_dispositions),
        ("domain", selected_domains),
        ("evidence_status", selected_evidence),
        ("requirement_id", selected_ids),
    ):
        if values:
            filtered = filtered[filtered[column].astype(str).isin(values)]
    columns = [
        "requirement_id",
        "requirement",
        "domain",
        "observed_score",
        "maximum_score",
        "minimum_acceptable_score",
        "objective_evidence",
        "evidence",
        "evidence_status",
        "completion_status",
        "criticality_level",
        "critical_control_outcome",
        "critical_control_disposition",
        "critical_control_reason",
        "rationale",
        "approval_status",
    ]
    st.caption(f"Showing {len(filtered)} of {len(data)} governed requirements.")
    st.dataframe(
        filtered[[column for column in columns if column in filtered]], use_container_width=True, hide_index=True
    )

    finding_tables = (
        ("Deployment-blocking failures", assessment.deployment_blocking_failures),
        ("Conditional gaps", assessment.conditional_gaps),
        ("Important corrective-action findings", assessment.important_gaps),
        ("Evidence deficiencies", assessment.evidence_deficiencies),
        ("Incomplete critical records", assessment.incomplete_records),
        ("Manual-review items", assessment.manual_review_items),
    )
    for title, findings in finding_tables:
        with st.expander(f"{title} ({len(findings)})", expanded=title == "Deployment-blocking failures"):
            st.dataframe(
                findings[[column for column in columns if column in findings]],
                use_container_width=True,
                hide_index=True,
            )


def _risk_acceptance_policy_controls() -> RiskAcceptancePolicy:
    """Expose the two missing-residual controls while retaining safe defaults."""
    with st.sidebar.expander("Risk acceptance policy", expanded=False):
        st.caption("Provisional software rules for decision support; institutional approval is required.")
        missing_policy = st.selectbox(
            "Missing residual-risk policy",
            MISSING_RESIDUAL_POLICIES,
            format_func=lambda value: value.replace("_", " ").capitalize(),
            key="missing_residual_policy",
        )
        require_for_ready = st.checkbox(
            "Require residual assessment for READY",
            value=False,
            key="require_residual_for_ready",
        )
    return RiskAcceptancePolicy(
        missing_residual_policy=missing_policy,
        require_residual_for_ready_decision=require_for_ready,
    )


def _filter_values(data: pd.DataFrame, column: str) -> list[str]:
    if column not in data.columns:
        return []
    return sorted(data[column].dropna().astype(str).unique().tolist())


def _render_risk_acceptance(hazards: pd.DataFrame, policy: RiskAcceptancePolicy) -> None:
    """Render transparent source, disposition, action, and filtering details."""
    summary = risk_acceptance_summary(hazards, policy)
    source = summary["risk_source_summary"]
    st.subheader("Risk Acceptance")
    st.warning(RISK_ACCEPTANCE_LIMITATION)
    metric1, metric2, metric3, metric4, metric5 = st.columns(5)
    metric1.metric("Risk source used", source["risk_source_display"])
    metric2.metric("Corrective action required", summary["corrective_action_required_count"])
    metric3.metric("Formal approval required", summary["formal_approval_required_count"])
    metric4.metric("Missing residual assessment", summary["missing_residual_assessment_count"])
    metric5.metric("Unacceptable hazards", summary["unacceptable_hazard_count"])
    if source["inherent_screening_hazard_count"]:
        st.info(
            f"Inherent risk was used for screening for {source['inherent_screening_hazard_count']} hazard(s); "
            "residual assessment was not provided for those records."
        )

    status_table = pd.DataFrame(
        {
            "risk_acceptance_status": ACCEPTANCE_DISPOSITIONS,
            "hazard_count": [summary["acceptance_status_counts"][status] for status in ACCEPTANCE_DISPOSITIONS],
        }
    )
    st.caption("Hazards by provisional acceptance status")
    st.dataframe(status_table, use_container_width=True, hide_index=True)

    st.caption("Filter the per-hazard risk-acceptance table")
    row1 = st.columns(3)
    row2 = st.columns(3)
    with row1[0]:
        selected_acceptance = st.multiselect(
            "Acceptance status",
            ACCEPTANCE_DISPOSITIONS,
            key="acceptance_status_filter",
        )
    with row1[1]:
        selected_categories = st.multiselect(
            "Decision-risk category",
            [*RISK_LEVELS, "Not assessable"],
            key="decision_category_filter",
        )
    with row1[2]:
        selected_sources = st.multiselect(
            "Risk source (Inherent = screening)",
            ["Residual", "Inherent", "Unavailable"],
            key="decision_source_filter",
        )
    with row2[0]:
        selected_domains = st.multiselect("Domain", _filter_values(hazards, "domain"), key="acceptance_domain_filter")
    with row2[1]:
        selected_owners = st.multiselect(
            "Owner / responsible person",
            _filter_values(hazards, "responsible_person"),
            key="acceptance_owner_filter",
        )
    with row2[2]:
        selected_statuses = st.multiselect(
            "Hazard/action status",
            _filter_values(hazards, "status"),
            key="acceptance_record_status_filter",
        )

    filtered = hazards.copy()
    filters = (
        ("risk_acceptance_status", selected_acceptance),
        ("decision_risk_category", selected_categories),
        ("decision_risk_source", selected_sources),
        ("domain", selected_domains),
        ("responsible_person", selected_owners),
        ("status", selected_statuses),
    )
    for column, values in filters:
        if values and column in filtered.columns:
            filtered = filtered[filtered[column].astype(str).isin(values)]
    columns = [
        "hazard_id",
        "hazard",
        "domain",
        "risk_score",
        "risk_category",
        "residual_risk_score",
        "residual_risk_category",
        "decision_risk_score",
        "decision_risk_category",
        "decision_risk_source",
        "risk_acceptance_status",
        "acceptance_action_required",
        "acceptance_reason",
        "corrective_action_required",
        "formal_approval_required",
        "responsible_person",
        "status",
    ]
    st.caption(f"Showing {len(filtered)} of {len(hazards)} analyzed hazards.")
    st.dataframe(
        filtered[[column for column in columns if column in filtered]], use_container_width=True, hide_index=True
    )


def _render_validation_center(
    summaries: list[dict[str, Any]],
    findings: list[ValidationFinding],
    datasets: dict[str, pd.DataFrame | None],
) -> None:
    """Render auditable validation metrics, filters, inspection, and downloads."""
    overview = validation_overview(summaries, findings)
    counts = overview["finding_counts_by_severity"]
    st.info(VALIDATION_LIMITATION)
    metric_row1 = st.columns(4)
    metric_row1[0].metric("Datasets loaded", overview["total_datasets_loaded"])
    metric_row1[1].metric("Total records", overview["total_records"])
    metric_row1[2].metric("Errors", counts["Error"])
    metric_row1[3].metric("Warnings", counts["Warning"])
    metric_row2 = st.columns(4)
    metric_row2[0].metric("Information", counts["Information"])
    metric_row2[1].metric("Analysis-eligible", overview["analysis_eligible_records"])
    metric_row2[2].metric("Excluded", overview["excluded_records"])
    metric_row2[3].metric(
        "Passing / blocked datasets",
        f'{overview["datasets_passing_validation"]} / {overview["datasets_blocked"]}',
    )

    summary_data = summaries_frame(summaries)
    finding_data = findings_frame(findings)
    st.subheader("Dataset summaries")
    st.dataframe(summary_data, use_container_width=True, hide_index=True)
    st.subheader("Validation findings")
    if finding_data.empty:
        st.success("No structured findings were generated.")
        filtered = finding_data
    else:
        filter_row1 = st.columns(3)
        filter_row2 = st.columns(3)
        with filter_row1[0]:
            dataset_filter = st.multiselect(
                "Dataset type",
                sorted(finding_data["dataset_type"].dropna().astype(str).unique()),
                key="validation_dataset_filter",
            )
        with filter_row1[1]:
            severity_filter = st.multiselect(
                "Severity", ["Error", "Warning", "Information"], key="validation_severity_filter"
            )
        with filter_row1[2]:
            code_filter = st.multiselect(
                "Finding code",
                sorted(finding_data["code"].dropna().astype(str).unique()),
                key="validation_code_filter",
            )
        with filter_row2[0]:
            record_filter = st.text_input("Record ID contains", key="validation_record_filter")
        with filter_row2[1]:
            column_filter = st.multiselect(
                "Column",
                sorted(finding_data["column"].dropna().astype(str).unique()),
                key="validation_column_filter",
            )
        with filter_row2[2]:
            blocks_filter = st.selectbox("Blocks analysis", ["All", "Yes", "No"], key="validation_blocks_filter")
        search_text = st.text_input(
            "Search findings", placeholder="Search message, value, action, code, or ID", key="validation_search"
        )
        filtered = finding_data.copy()
        if dataset_filter:
            filtered = filtered[filtered["dataset_type"].isin(dataset_filter)]
        if severity_filter:
            filtered = filtered[filtered["severity"].isin(severity_filter)]
        if code_filter:
            filtered = filtered[filtered["code"].isin(code_filter)]
        if record_filter:
            filtered = filtered[
                filtered["record_id"].astype("string").str.contains(record_filter, case=False, na=False, regex=False)
            ]
        if column_filter:
            filtered = filtered[filtered["column"].isin(column_filter)]
        if blocks_filter != "All":
            filtered = filtered[filtered["blocks_analysis"].eq(blocks_filter == "Yes")]
        if search_text:
            searchable = filtered[
                ["code", "message", "record_id", "column", "original_value", "suggested_action"]
            ].astype("string")
            filtered = filtered[
                searchable.apply(
                    lambda column: column.str.contains(search_text, case=False, na=False, regex=False)
                ).any(axis=1)
            ]
        display_columns = [
            "finding_id",
            "dataset_type",
            "severity",
            "code",
            "message",
            "row_index",
            "record_id",
            "column",
            "original_value",
            "suggested_action",
            "blocks_analysis",
        ]
        st.caption(f"Showing {len(filtered)} of {len(finding_data)} findings.")
        st.dataframe(filtered[display_columns], use_container_width=True, hide_index=True)

    st.subheader("Affected record inspection")
    inspectable = finding_data.loc[finding_data["row_index"].notna()] if not finding_data.empty else finding_data
    if inspectable.empty:
        st.caption("No row-specific finding is available for record inspection.")
    else:
        selected_finding = st.selectbox(
            "Select finding",
            inspectable["finding_id"].tolist(),
            format_func=lambda finding_id: (
                f"{finding_id} — " f"{inspectable.loc[inspectable['finding_id'].eq(finding_id), 'message'].iloc[0]}"
            ),
            key="validation_record_inspector",
        )
        finding_row = inspectable.loc[inspectable["finding_id"].eq(selected_finding)].iloc[0]
        dataset = datasets.get(str(finding_row["dataset_type"]))
        row_index = int(finding_row["row_index"])
        if dataset is not None and row_index in dataset.index:
            st.dataframe(dataset.loc[[row_index]], use_container_width=True, hide_index=False)
        else:
            st.caption("The finding is cross-dataset/file-level or its source row is not available.")

    st.subheader("Validation downloads")
    download_columns = st.columns(3)
    download_columns[0].download_button(
        EXPORT_FILENAMES["validation_findings_csv"],
        csv_bytes(finding_data),
        EXPORT_FILENAMES["validation_findings_csv"],
        "text/csv",
        key="validation_findings_download",
    )
    download_columns[1].download_button(
        EXPORT_FILENAMES["validation_summary_csv"],
        csv_bytes(summary_data),
        EXPORT_FILENAMES["validation_summary_csv"],
        "text/csv",
        key="validation_summary_download",
    )
    download_columns[2].download_button(
        EXPORT_FILENAMES["invalid_records_workbook"],
        invalid_records_workbook_bytes(summaries, findings, datasets),
        EXPORT_FILENAMES["invalid_records_workbook"],
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="validation_invalid_download",
    )


def _render_session_controls() -> None:
    """Render non-destructive refresh and confirmed full-reset controls."""
    with st.sidebar:
        st.divider()
        st.subheader("Session controls")
        if st.button("Refresh View", use_container_width=True, key="refresh_view"):
            st.rerun()
        if st.button("Reset Assessment", type="secondary", use_container_width=True, key="reset_assessment"):
            st.session_state["_mobra_reset_requested"] = True
        if st.session_state.get("_mobra_reset_requested", False):
            confirmed = st.checkbox(
                "I understand this clears uploaded data, filters, metadata, email fields, and calculated outputs.",
                key="reset_assessment_confirmation",
            )
            if confirmed and st.button("Confirm Reset", type="primary", use_container_width=True, key="confirm_reset"):
                reset_assessment_state(st.session_state)
                st.rerun()
    if st.session_state.pop("_mobra_reset_message", False):
        st.success("The assessment session has been reset.")


def _secrets_mapping() -> dict[str, object]:
    """Read Streamlit secrets defensively without exposing values in the UI."""
    try:
        return {str(key): value for key, value in st.secrets.items()}
    except Exception:  # pragma: no cover - depends on hosting configuration
        return {}


def _render_contextual_explanations(decision: str) -> None:
    st.caption("Contextual help is available as popovers, with expanders as a compatibility fallback.")
    for topic in HELP_TOPICS:
        render_help(topic, st)
    if decision:
        st.caption(
            f"The current result is {decision}. It is generated by configured MOBRA software rules and requires review and authorization by accountable personnel."
        )


def _resource_link(label: str, url: str) -> None:
    if not url:
        return
    if hasattr(st, "link_button"):
        st.link_button(label, url, use_container_width=True)
    else:  # pragma: no cover - compatibility fallback for older Streamlit
        st.markdown(f"[{label}]({url})")


def _render_resources_and_contact(
    requirements: pd.DataFrame,
    hazards: pd.DataFrame,
    report_html: str,
    summary_json: bytes,
    validation_csv: bytes,
    critical_csv: bytes,
    mapping_csv: bytes,
) -> None:
    """Render printable templates, resources, author contact, and optional email backup."""
    st.header("Resources and Contact")
    st.subheader("Contact the Author")
    st.write(f"**Author:** {AUTHOR_NAME}")
    author_email = configured_author_email()
    if author_email:
        st.markdown(f"**Email:** [{author_email}](mailto:{author_email}?subject=MOBRA%20Application%20Inquiry)")
        st.caption(
            "The author contact address is public application metadata; assessment results are never sent automatically."
        )
        st.code(author_email, language="text")
        st.caption(
            "Default subject: MOBRA Application Inquiry. Use the copy control in the code block where supported by your browser."
        )
    else:
        st.info("Author contact email has not yet been configured.")
    st.caption(
        "Suggested subjects: Scientific feedback · Software issue · Collaboration request · Data-integration question · General inquiry."
    )

    st.subheader("Printable Assessment Forms")
    st.write("Download, print, complete manually in the laboratory, and enter the completed values into MOBRA later.")
    form_items = [
        (
            "MOBRA_Printable_ORL_Assessment_Form.xlsx",
            "Full 60-row ORL assessment form",
            build_orl_assessment_workbook(requirements),
            "XLSX",
            True,
        ),
        (
            "MOBRA_Printable_ORL_Assessment_Form.pdf",
            "Readable paper ORL form with repeated table headers",
            build_orl_pdf(requirements),
            "PDF",
            False,
        ),
        (
            "MOBRA_Requirements_Import_Template.xlsx",
            "Blank supported digital ORL import template",
            build_requirements_import_template(),
            "XLSX",
            True,
        ),
        (
            "MOBRA_Printable_Hazard_Register.xlsx",
            "Hazard register with assessor-selected risk fields",
            build_hazard_register_workbook(hazards),
            "XLSX",
            False,
        ),
        (
            "MOBRA_Printable_Hazard_Register.pdf",
            "Readable paper hazard register",
            build_hazard_pdf(hazards),
            "PDF",
            False,
        ),
        (
            "MOBRA_Hazard_Import_Template.xlsx",
            "Blank supported hazard import template",
            build_hazard_import_template(),
            "XLSX",
            True,
        ),
        (
            "MOBRA_Field_Assessment_Package.xlsx",
            "Combined field package with stable sheet names",
            build_field_assessment_package(requirements, hazards),
            "XLSX",
            True,
        ),
    ]
    for index in range(0, len(form_items), 2):
        columns = st.columns(2)
        for column, item in zip(columns, form_items[index : index + 2], strict=False):
            filename, purpose, content, file_format, reupload = item
            with column:
                st.markdown(f"**{filename}**")
                st.caption(
                    f"{purpose} · {file_format} · {'Can be re-uploaded' if reupload else 'Manual entry required'}"
                )
                if file_format == "XLSX":
                    preview = pd.DataFrame(
                        {"Field": ["Requirement ID", "Domain", "Requirement", "Observed Score", "Objective Evidence"]}
                    )
                else:
                    preview = pd.DataFrame({"PDF form": ["Repeated table headers", "Writing space", "Disclaimer"]})
                st.dataframe(preview, hide_index=True, use_container_width=True)
                st.download_button(
                    f"Download {filename}",
                    content,
                    filename,
                    (
                        "application/pdf"
                        if file_format == "PDF"
                        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    ),
                    key=f"resource_form_{filename}",
                )
    st.info(
        "Handwritten PDF forms require manual data entry later. MOBRA does not promise automatic OCR or handwritten-form recognition."
    )
    st.download_button(
        "Download MOBRA_Template_Catalogue.csv",
        template_catalogue_csv(),
        "MOBRA_Template_Catalogue.csv",
        "text/csv",
        key="template_catalogue_csv",
    )

    st.subheader("Educational Posters")
    st.caption(
        "Original MOBRA-created educational summaries. Source standards and guidance are paraphrased at a high level; ISO PDFs and third-party copyrighted figures are not bundled."
    )
    try:
        media = load_educational_media()
        media_topics = sorted({str(item["topic"]) for item in media})
        selected_media_topic = st.selectbox("Poster topic", ["All", *media_topics], key="poster_topic_filter")
        filtered_media = [
            item for item in media if selected_media_topic == "All" or item["topic"] == selected_media_topic
        ]
        for item in filtered_media:
            with st.container(border=True):
                poster_columns = st.columns([1, 2, 1])
                with poster_columns[0]:
                    image_path = BASE_DIR / item["png_path"]
                    if image_path.is_file():
                        st.image(
                            str(image_path),
                            caption=f"{item['title']} — original MOBRA artwork",
                            use_container_width=True,
                        )
                with poster_columns[1]:
                    st.markdown(f"**{item['title']}**")
                    st.write(item["description"])
                    st.caption(f"Source basis: {', '.join(item['source_resource_ids'])}. {item['copyright_note']}")
                    st.caption(
                        "Accessibility: high-contrast poster with text labels; colour is not the only status cue."
                    )
                with poster_columns[2]:
                    st.download_button(
                        "Download PNG",
                        (BASE_DIR / item["png_path"]).read_bytes(),
                        Path(item["png_path"]).name,
                        "image/png",
                        key=f"poster_png_{item['media_id']}",
                    )
                    st.download_button(
                        "Download PDF",
                        (BASE_DIR / item["pdf_path"]).read_bytes(),
                        Path(item["pdf_path"]).name,
                        "application/pdf",
                        key=f"poster_pdf_{item['media_id']}",
                    )
        st.download_button(
            "Download MOBRA Educational Media Package",
            educational_media_package(media),
            "MOBRA_Educational_Media_Package.zip",
            "application/zip",
            key="educational_media_package",
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        st.warning(f"Educational media are unavailable: {exc}")

    st.subheader("Normative Evidence Base and Scientific Resources")
    st.write(
        "The normative evidence base for MOBRA includes international guidance and standards relating to laboratory biosafety, laboratory biosecurity, rapid-response mobile laboratories, infectious-substance transport, biorisk management, general risk management, and biomedical laboratory biosafety practices."
    )
    st.caption(NORMATIVE_EVIDENCE_WORDING)
    st.caption(NON_ENDORSEMENT_STATEMENT)
    try:
        resources = load_normative_resources()
        catalogue = resource_catalogue_frame(resources)
        organization_filter = st.multiselect(
            "Filter by organization", sorted(catalogue["issuing_organization"].unique()), key="resource_org_filter"
        )
        topic_filter = st.multiselect(
            "Filter by topic", sorted(catalogue["topic"].unique()), key="resource_topic_filter"
        )
        access_filter = st.multiselect(
            "Filter by access type", sorted(catalogue["access_type"].unique()), key="resource_access_filter"
        )
        filtered = catalogue.copy()
        if organization_filter:
            filtered = filtered[filtered["issuing_organization"].isin(organization_filter)]
        if topic_filter:
            filtered = filtered[filtered["topic"].isin(topic_filter)]
        if access_filter:
            filtered = filtered[filtered["access_type"].isin(access_filter)]
        st.dataframe(
            filtered[
                [
                    "resource_id",
                    "title",
                    "issuing_organization",
                    "edition",
                    "resource_type",
                    "access_type",
                    "current_status",
                ]
            ],
            hide_index=True,
            use_container_width=True,
        )
        for resource in resources:
            with st.expander(f"{resource['resource_id']} · {resource['title']}", expanded=False):
                st.write(
                    f"**Organization:** {resource['issuing_organization']} · **Edition/year:** {resource['edition']} / {resource['publication_year']}"
                )
                st.write(f"**Topic:** {resource['topic']}\n\n**Relevance:** {resource['relevance_to_mobra']}")
                st.write(f"**Access:** {resource['access_type']} · **Status:** {resource['current_status']}")
                _resource_link("Official source", resource["official_page_url"])
                if resource["official_download_url"]:
                    _resource_link("Official download", resource["official_download_url"])
                else:
                    st.caption("No authorized download is exposed; use the official source page.")
                st.code(resource["citation"], language="text")
                st.caption(resource["licence_or_copyright"])
        st.download_button(
            "Download MOBRA_Normative_Resource_Catalogue.csv",
            catalogue_csv_bytes(resources),
            "MOBRA_Normative_Resource_Catalogue.csv",
            "text/csv",
            key="normative_catalogue_csv",
        )
        st.download_button(
            "Download MOBRA_Normative_Resource_Catalogue.xlsx",
            catalogue_xlsx_bytes(resources),
            "MOBRA_Normative_Resource_Catalogue.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="normative_catalogue_xlsx",
        )
        st.download_button(
            "Download MOBRA_Open_Access_Reference_Package.zip",
            build_open_access_reference_package(resources),
            "MOBRA_Open_Access_Reference_Package.zip",
            "application/zip",
            key="open_access_reference_zip",
        )
        st.caption(
            f"Supporting-literature catalogue entries: {len(load_supporting_literature())}. Publisher PDFs are not bundled."
        )
        st.subheader("Supporting scientific literature")
        for literature in load_supporting_literature():
            with st.container(border=True):
                st.markdown(f"**{literature.get('title', 'Supporting literature')}**")
                st.caption(
                    f"{literature.get('authors', '')} · {literature.get('year', '')} · "
                    f"Evidence role: {literature.get('evidence_role', 'Supporting evidence')}"
                )
                st.write(
                    f"Topic: {literature.get('topic', 'MOBRA context')}. Supporting literature informs context and methodology; it is not normative guidance."
                )
                _resource_link("Official or publisher page", str(literature.get("official_or_publisher_url", "")))
                st.caption("Supporting literature is not normative guidance and does not imply endorsement.")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        st.error(f"Normative resource manifest is unavailable: {exc}")

    st.subheader("Research Manuscript")
    manuscript_path = BASE_DIR / "docs" / "MOBRA_Manuscript.pdf"
    manuscript_info = manuscript_metadata(manuscript_path)
    if manuscript_info["manuscript_available"]:
        st.write("MOBRA Research Manuscript")
        st.caption(
            f"Author: {AUTHOR_NAME} · File size: {manuscript_info['manuscript_size_bytes']:,} bytes · "
            f"Pages: {manuscript_info['manuscript_page_count'] or 'Unavailable'}"
        )
        st.caption(f"SHA-256: {manuscript_info['manuscript_sha256']}")
        st.info(manuscript_info["manuscript_version_note"])
        st.warning(
            "The manuscript contains an earlier illustrative BRI of 81.0%. The current application demonstration produces BRI 86.7%; the two results are intentionally separated."
        )
        st.download_button(
            "Download MOBRA Research Manuscript",
            manuscript_download_bytes(manuscript_path),
            "MOBRA_Manuscript.pdf",
            "application/pdf",
            key="manuscript_download",
        )
        if not manuscript_is_current(manuscript_path):
            st.warning("The checked-in manuscript checksum differs from the author-approved checksum.")
    else:
        st.info("The approved MOBRA research manuscript is unavailable in this build.")

    st.subheader("Email Backup of Assessment Results")
    st.warning(
        "Email transmission may leave the controlled application environment. Confirm institutional authorization, recipient identity, and data classification before sending."
    )
    config = EmailConfig.from_mapping(_secrets_mapping())
    derived_files = {
        "MOBRA_Summary.json": summary_json,
        "MOBRA_Report.html": report_html.encode("utf-8"),
        "MOBRA_Validation_Findings.csv": validation_csv,
        "MOBRA_Critical_Control_Assessment.csv": critical_csv,
        "MOBRA_Requirement_Hazard_Mapping.csv": mapping_csv,
    }
    emit_notification(
        st,
        st.session_state,
        "zip_backup_ready",
        "Derived ZIP backup is ready; original uploads are excluded by default.",
        level="success",
    )
    st.download_button(
        "Download MOBRA_Assessment_Backup.zip",
        build_backup_zip(derived_files),
        "MOBRA_Assessment_Backup.zip",
        "application/zip",
        key="assessment_backup_zip",
    )
    if not config.configured:
        st.info(
            "Email backup is disabled because SMTP settings are not configured. Downloadable backup packages remain available."
        )
        emit_notification(
            st,
            st.session_state,
            "email_disabled",
            "Email backup is disabled; ZIP fallback remains available.",
            level="info",
        )
    else:
        recipient = st.text_input("Recipient email", key="backup_recipient")
        cc = st.text_input("Optional CC email", key="backup_cc")
        assessment_name = st.text_input("Assessment or mission name", key="backup_assessment_name")
        selected = st.multiselect(
            "Attachments",
            list(derived_files),
            default=["MOBRA_Summary.json", "MOBRA_Report.html"],
            key="backup_attachments",
        )
        consent = st.checkbox(
            "I understand the disclaimer and confirm that I am authorized to send these results.", key="backup_consent"
        )
        authorized = st.checkbox(
            "I confirm that institutional authorization permits this transmission.", key="backup_authorized"
        )
        no_sensitive_data = st.checkbox(
            "I confirm that no sensitive or identifiable data are included unless permitted.",
            key="backup_data_classification",
        )
        if sum(len(derived_files[name]) for name in selected) > MAX_EMAIL_ATTACHMENT_BYTES:
            st.error("The selected attachments exceed the total email-size limit.")
        if st.button("Send selected assessment backup", key="send_backup"):
            try:
                send_email_backup(
                    config,
                    recipient=recipient,
                    cc=cc,
                    subject="MOBRA Application Inquiry",
                    assessment_name=assessment_name,
                    attachments={name: derived_files[name] for name in selected},
                    consent=consent,
                    authorized=authorized,
                    no_sensitive_data=no_sensitive_data,
                )
                st.success("Assessment backup email sent after explicit confirmation.")
                emit_notification(
                    st,
                    st.session_state,
                    "email_sent",
                    "Assessment backup email sent after explicit confirmation.",
                    level="success",
                )
            except EmailBackupError as exc:
                st.error(str(exc))

    st.subheader("Disclaimer and Limitation of Liability")
    st.write(FULL_DISCLAIMER)


def main() -> None:
    favicon = asset_path("mobra_favicon.png")
    st.set_page_config(page_title=APP_TITLE, page_icon=str(favicon) if favicon.is_file() else "🧬", layout="wide")
    palette = load_brand_palette()["colors"]
    st.markdown(
        f"<style>.block-container{{padding-top:1.5rem}}.stMetric{{background:{palette['mist']};border:1px solid #cbd5e1;padding:12px;border-radius:10px}}.mobra-brand-card{{border-left:6px solid {palette['teal']};padding:0.5rem 1rem;background:{palette['mist']};border-radius:0.5rem}}</style>",
        unsafe_allow_html=True,
    )
    logo = asset_path("mobra_logo_horizontal.png")
    if logo.is_file():
        st.image(str(logo), width=650)
    st.title(APP_TITLE)
    st.caption(
        f"{APPLICATION_DEFINITION} · Version {APP_VERSION} · {PROTOTYPE_STATUS} · Build {application_metadata()['build_identifier']}"
    )
    st.info(
        "This software is an external-dataset-based computational verification prototype and not clinical, operational, regulatory, or field validation."
    )
    st.markdown(
        '<div class="mobra-brand-card"><strong>Current demonstration outputs</strong>: 24 hazards, 60 requirements, BRI 86.7%, decision DO NOT DEPLOY. These are demonstration records, not a universal conclusion.</div>',
        unsafe_allow_html=True,
    )
    _render_session_controls()
    st.header("About MOBRA")
    st.write(APPLICATION_DEFINITION)
    st.write("It combines: " + "; ".join(INTRODUCTION_COMPONENTS) + ".")
    with st.expander("How to use this application", expanded=False):
        for step_number, step in enumerate(HOW_TO_USE_STEPS, start=1):
            st.markdown(f"{step_number}. {step}")
    with st.expander("What MOBRA does not do", expanded=False):
        st.write("MOBRA does not replace:")
        for item in WHAT_MOBRA_DOES_NOT_DO:
            st.markdown(f"- {item}")
    navigation_labels = [
        "Home",
        "Assessment Setup",
        "Data Validation",
        "Readiness and BRI",
        "Hazard Analysis",
        "Requirement–Hazard Mapping",
        "Critical-Control Governance",
        "Reports and Exports",
        "Resources and Contact",
    ]
    selected_navigation = st.radio("MOBRA navigation", navigation_labels, horizontal=True, key="mobra_navigation")
    st.caption(
        f"Current workflow area: {selected_navigation}. Use the detailed tabs below to inspect each analysis module."
    )
    st.session_state["_mobra_file_findings"] = []
    st.session_state["_mobra_file_sheets"] = {}

    (
        hazards_raw,
        requirements_raw,
        mapping_raw,
        critical_profile_raw,
        hazard_filename,
        requirements_filename,
        mapping_filename,
        critical_profile_filename,
    ) = _load_inputs()
    if hazards_raw is None or requirements_raw is None:
        st.info("Provide both datasets to begin the assessment.")
        return
    emit_notification(
        st, st.session_state, "data_loaded", "Demonstration or uploaded assessment data loaded.", level="success"
    )

    st.subheader("1. Preview and column mapping")
    hazard_overrides = _mapping_controls(hazards_raw, "hazards")
    requirement_overrides = _mapping_controls(requirements_raw, "requirements")
    col1, col2 = st.columns(2)
    with col1:
        hazards_raw = _preview_editor(hazards_raw, "Hazards")
    with col2:
        requirements_raw = _preview_editor(requirements_raw, "Requirements")
    if mapping_raw is not None:
        mapping_raw = _preview_editor(mapping_raw, "Requirement–hazard mapping")
    if critical_profile_raw is not None:
        critical_profile_raw = _preview_editor(critical_profile_raw, "Critical-control profile")
    hazard_result = validate_hazards(hazards_raw, hazard_overrides)
    requirement_result = validate_requirements(requirements_raw, requirement_overrides)
    _show_validation(hazard_result, "Hazard")
    _show_validation(requirement_result, "Requirement")
    all_messages = [
        *hazard_result.errors,
        *hazard_result.warnings,
        *requirement_result.errors,
        *requirement_result.warnings,
    ]
    hazard_eligible = int(hazard_result.data.get("inherent_risk_eligible", pd.Series(dtype=bool)).fillna(False).sum())
    requirement_eligible = int(requirement_result.data.get("bri_eligible", pd.Series(dtype=bool)).fillna(False).sum())
    if (
        hazard_result.dataset_blocked
        or requirement_result.dataset_blocked
        or not hazard_eligible
        or not requirement_eligible
    ):
        st.error(
            "Analysis is paused because a required dataset is structurally blocked or has no eligible records. "
            "Invalid input rows remain visible below and in the validation downloads."
        )
        blocked_summaries = [
            validation_summary(
                dataset_type="Hazards",
                filename=hazard_filename,
                data=hazard_result.data,
                findings=hazard_result.findings,
                required_columns=("hazard", "likelihood", "consequence"),
                missing_columns=hazard_result.missing_columns,
                duplicate_ids=hazard_result.duplicate_ids,
                sheet_name=st.session_state["_mobra_file_sheets"].get(hazard_filename, ""),
                validation_reference_date=hazard_result.validation_reference_date,
            ),
            validation_summary(
                dataset_type="Requirements",
                filename=requirements_filename,
                data=requirement_result.data,
                findings=requirement_result.findings,
                required_columns=("requirement", "observed_score", "maximum_score"),
                missing_columns=requirement_result.missing_columns,
                duplicate_ids=requirement_result.duplicate_ids,
                sheet_name=st.session_state["_mobra_file_sheets"].get(requirements_filename, ""),
                validation_reference_date=requirement_result.validation_reference_date,
            ),
        ]
        blocked_findings = [
            *st.session_state.get("_mobra_file_findings", []),
            *hazard_result.findings,
            *requirement_result.findings,
        ]
        _render_validation_center(
            blocked_summaries,
            blocked_findings,
            {"Hazards": hazard_result.data, "Requirements": requirement_result.data},
        )
        return
    if hazard_result.errors or requirement_result.errors:
        st.warning(
            "Some rows are invalid. They remain visible, are excluded from calculations requiring valid fields, "
            "and prevent an automatic deployment-ready decision."
        )

    acceptance_policy = _risk_acceptance_policy_controls()
    hazards = apply_risk_acceptance(hazard_result.data, acceptance_policy)
    requirements = requirement_result.data
    critical_assessment: CriticalControlAssessment | None = None
    critical_profile_ready = False
    critical_profile_messages: list[str] = []
    if critical_profile_raw is not None:
        critical_assessment = assess_critical_controls(requirements, critical_profile_raw)
        _show_validation(critical_assessment.validation, "Critical-control profile")
        critical_profile_ready = critical_assessment.ok
        critical_profile_messages = [
            *critical_assessment.validation.errors,
            *critical_assessment.validation.warnings,
        ]
        if not critical_profile_ready:
            st.warning(
                "Critical-control governance analysis is paused until profile errors are corrected. "
                "Hazard analysis and raw BRI remain available."
            )
    else:
        st.info(
            "No critical-control profile was supplied. Structured governance analysis is unavailable; "
            "hazard analysis and raw BRI remain available."
        )
    mapping_result: MappingValidationResult | None = None
    mapping = pd.DataFrame(columns=MAPPING_REQUIRED_COLUMNS)
    mapping_ready = False
    mapping_messages: list[str] = []
    if mapping_raw is not None:
        mapping_result = validate_mapping(mapping_raw, requirements, hazards)
        _show_validation(mapping_result, "Requirement–hazard mapping")
        mapping = mapping_result.data
        mapping_ready = mapping_result.ok
        mapping_messages = [*mapping_result.errors, *mapping_result.warnings]
        if not mapping_ready:
            st.warning(
                "Mapping analysis is paused until mapping errors are corrected. "
                "Hazard risk and BRI analysis remain available."
            )
    else:
        st.info("No mapping file was supplied. Hazard risk and BRI analysis remain available without mapping data.")

    profile_validation = critical_assessment.validation if critical_assessment is not None else None
    cross_result: CrossDatasetValidationResult = validate_cross_dataset_consistency(
        hazards,
        requirements,
        mapping_result.data if mapping_result is not None else None,
        profile_validation.data if profile_validation is not None else None,
    )
    file_findings = list(st.session_state.get("_mobra_file_findings", []))
    all_findings: list[ValidationFinding] = [
        *file_findings,
        *hazard_result.findings,
        *requirement_result.findings,
        *(mapping_result.findings if mapping_result is not None else []),
        *(profile_validation.findings if profile_validation is not None else []),
        *cross_result.findings,
    ]
    all_messages = [finding.message for finding in all_findings if finding.severity in {"Error", "Warning"}]
    validation_reference_date = hazard_result.validation_reference_date
    validation_summaries: list[dict[str, Any]] = [
        validation_summary(
            dataset_type="Hazards",
            filename=hazard_filename,
            data=hazard_result.data,
            findings=hazard_result.findings,
            required_columns=("hazard", "likelihood", "consequence"),
            missing_columns=hazard_result.missing_columns,
            duplicate_ids=hazard_result.duplicate_ids,
            sheet_name=st.session_state["_mobra_file_sheets"].get(hazard_filename, ""),
            validation_reference_date=validation_reference_date,
        ),
        validation_summary(
            dataset_type="Requirements",
            filename=requirements_filename,
            data=requirement_result.data,
            findings=requirement_result.findings,
            required_columns=("requirement", "observed_score", "maximum_score"),
            missing_columns=requirement_result.missing_columns,
            duplicate_ids=requirement_result.duplicate_ids,
            sheet_name=st.session_state["_mobra_file_sheets"].get(requirements_filename, ""),
            validation_reference_date=validation_reference_date,
        ),
    ]
    if mapping_result is not None:
        validation_summaries.append(
            validation_summary(
                dataset_type="Mapping",
                filename=mapping_filename,
                data=mapping_result.data,
                findings=mapping_result.findings,
                required_columns=MAPPING_REQUIRED_COLUMNS,
                missing_columns=mapping_result.missing_columns,
                duplicate_ids=mapping_result.duplicate_ids,
                sheet_name=st.session_state["_mobra_file_sheets"].get(mapping_filename, ""),
                validation_reference_date=validation_reference_date,
            )
        )
    if profile_validation is not None:
        validation_summaries.append(
            validation_summary(
                dataset_type="Critical-Control Profile",
                filename=critical_profile_filename,
                data=profile_validation.data,
                findings=profile_validation.findings,
                required_columns=tuple(
                    profile_validation.data.columns.intersection(
                        [
                            "requirement_id",
                            "criticality_level",
                            "failure_disposition",
                            "minimum_acceptable_score",
                            "evidence_required",
                            "incomplete_record_disposition",
                            "rationale",
                            "approval_status",
                            "source_status",
                        ]
                    )
                ),
                missing_columns=profile_validation.missing_columns,
                duplicate_ids=profile_validation.duplicate_ids,
                sheet_name=st.session_state["_mobra_file_sheets"].get(critical_profile_filename, ""),
                validation_reference_date=validation_reference_date,
            )
        )
    validation_datasets: dict[str, pd.DataFrame | None] = {
        "Hazards": hazards,
        "Requirements": requirements,
        "Mapping": mapping_result.data if mapping_result is not None else None,
        "Critical-Control Profile": profile_validation.data if profile_validation is not None else None,
    }
    with st.sidebar:
        st.divider()
        selected_levels = st.multiselect("Inherent risk categories shown in charts", RISK_LEVELS, default=RISK_LEVELS)
    filtered_hazards = hazards[hazards["risk_category"].isin(selected_levels)].copy()
    bri = calculate_bri(requirements)
    domains = domain_readiness(requirements)
    decision, reasons = deployment_decision(
        hazards,
        requirements,
        bri,
        validation_errors=[
            finding.message for finding in all_findings if finding.severity == "Error" and finding.blocks_analysis
        ],
        risk_acceptance_policy=acceptance_policy,
        critical_control_assessment=critical_assessment,
    )
    acceptance_summary_data = risk_acceptance_summary(hazards, acceptance_policy)
    quality = data_quality_summary(hazards, requirements)
    assert_heatmap_total(filtered_hazards)
    emit_notification(
        st,
        st.session_state,
        "validation_completed",
        "Validation completed; review findings before interpreting outputs.",
        level="info",
    )

    st.subheader("2. Executive dashboard")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Overall BRI", "N/A" if pd.isna(bri) else f"{bri:.1f}%")
    k2.metric("Filtered hazards", len(filtered_hazards), f"of {len(hazards)} total")
    k3.metric(
        "High + Extreme inherent (filtered)", int(filtered_hazards["risk_category"].isin(["High", "Extreme"]).sum())
    )
    blocking_failure_count = (
        critical_assessment.summary["deployment_blocking_failure_count"]
        if critical_profile_ready and critical_assessment is not None
        else len(failed_critical_controls(requirements))
    )
    k4.metric("Deployment-blocking failures", blocking_failure_count)
    if decision == "READY FOR DEPLOYMENT":
        st.success(f"Decision: {decision}")
    elif decision == "CONDITIONAL DEPLOYMENT":
        st.warning(f"Decision: {decision}")
    else:
        st.error(f"Decision: {decision}")
    st.write(" ".join(reasons))
    emit_notification(
        st,
        st.session_state,
        "analysis_completed",
        "Analysis completed from the current filtered valid dataset.",
        level="success",
    )
    _render_contextual_explanations(decision)

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(
        [
            "Executive dashboard",
            "Hazard analysis",
            "Readiness analysis",
            "Critical-Control Governance",
            "Requirement–Hazard Mapping",
            "Data Validation Center",
            "Data & exports",
            "Resources and Contact",
        ]
    )
    with tab1:
        left, right = st.columns(2)
        left.plotly_chart(bri_gauge(bri), use_container_width=True, key="executive_bri")
        right.plotly_chart(risk_counts_figure(filtered_hazards), use_container_width=True, key="executive_risk_counts")
        st.plotly_chart(domain_figure(domains), use_container_width=True, key="executive_domains")
    with tab2:
        st.plotly_chart(heatmap_figure(filtered_hazards), use_container_width=True, key="hazard_heatmap")
        st.caption(
            f"Inherent-risk heat-map cell counts verified: {heatmap_total(filtered_hazards)} cells represent "
            f"{len(filtered_hazards)} filtered valid hazards. Cell numbers are hazard frequencies."
        )
        st.dataframe(
            filtered_hazards.sort_values("risk_score", ascending=False), use_container_width=True, hide_index=True
        )
        st.subheader("Top inherent risks")
        st.dataframe(filtered_hazards.nlargest(10, "risk_score"), use_container_width=True, hide_index=True)
        _render_risk_acceptance(hazards, acceptance_policy)
    with tab3:
        st.plotly_chart(domain_figure(domains), use_container_width=True, key="readiness_domains")
        st.dataframe(domains, use_container_width=True, hide_index=True)
        st.subheader("Legacy input critical-control flags")
        st.caption(
            "These source flags are preserved for traceability; governance outcomes come from the separate profile."
        )
        critical_flags = requirements["critical_control"].fillna(False).astype(bool)
        st.dataframe(requirements.loc[critical_flags], use_container_width=True, hide_index=True)
    with tab4:
        if critical_profile_ready and critical_assessment is not None:
            _render_critical_control_governance(critical_assessment)
        elif critical_assessment is not None:
            st.warning("Critical-control governance is unavailable because the profile has validation errors.")
        else:
            st.info("Upload a critical-control profile to enable structured governance analysis.")
    with tab5:
        if mapping_ready:
            _render_mapping_analysis(mapping, requirements, hazards)
        elif mapping_result is not None:
            st.warning("Mapping analysis is unavailable because the mapping dataset has validation errors.")
        else:
            st.info("Upload a separate mapping CSV/XLSX/XLS file to enable mapping analysis.")
    with tab6:
        _render_validation_center(validation_summaries, all_findings, validation_datasets)
    with tab7:
        st.subheader("Validated data and quality")
        st.json(quality)
        st.dataframe(hazards, use_container_width=True, hide_index=True)
        st.dataframe(requirements, use_container_width=True, hide_index=True)
        if profile_validation is not None:
            st.dataframe(profile_validation.data, use_container_width=True, hide_index=True)
            if critical_profile_ready and critical_assessment is not None:
                st.dataframe(critical_assessment.data, use_container_width=True, hide_index=True)
        if mapping_result is not None:
            st.dataframe(mapping_result.data, use_container_width=True, hide_index=True)
        mapping_statistics: dict[str, Any] = {
            "available": mapping_ready,
            "mapping_file": mapping_filename,
            "validation_messages": mapping_messages,
        }
        coverage_export: pd.DataFrame | None = None
        if mapping_ready:
            mapping_statistics.update(mapping_coverage_summary(mapping, requirements, hazards))
            coverage_export = mapping_coverage_table(mapping, requirements, hazards)
        critical_summary_data: dict[str, Any]
        if critical_assessment is not None:
            critical_summary_data = critical_assessment.summary
        else:
            critical_summary_data = {
                "critical_control_profile_status": "Unavailable",
                "criticality_level_counts": {level: 0 for level in CRITICALITY_LEVELS},
                "critical_control_outcome_counts": {outcome: 0 for outcome in CONTROL_OUTCOMES},
                "deployment_blocking_failure_count": 0,
                "conditional_gap_count": 0,
                "important_gap_count": 0,
                "evidence_deficiency_count": 0,
                "incomplete_critical_record_count": 0,
                "manual_review_count": 0,
                "formal_approval_required_count": 0,
                "compensating_control_required_count": 0,
                "blocking_requirement_ids": [],
                "conditional_requirement_ids": [],
                "important_gap_requirement_ids": [],
                "evidence_deficient_requirement_ids": [],
                "manual_review_requirement_ids": [],
                "critical_control_limitations": CRITICAL_CONTROL_LIMITATION,
            }
        summary = {
            **application_metadata(assessment_metadata=st.session_state.get("_mobra_assessment_metadata", {})),
            **brand_summary(),
            **media_summary(),
            **manuscript_metadata(),
            "popover_help_topics": list(HELP_TOPICS),
            "notification_system_enabled": True,
            "template_catalogue": [item["filename"] for item in TEMPLATE_CATALOGUE],
            "current_bri_pct": None if pd.isna(bri) else round(float(bri), 2),
            "historical_manuscript_bri_pct": 81.0,
            "manuscript_current_bri_note": "The manuscript's historical illustrative BRI of 81.0% is not the current application BRI.",
            "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
            "hazard_file": hazard_filename,
            "requirements_file": requirements_filename,
            "bri_pct": None if pd.isna(bri) else round(float(bri), 2),
            "decision": decision,
            "decision_reasons": reasons,
            "hazard_count_total": len(hazards),
            "hazard_count_filtered": len(filtered_hazards),
            "risk_counts_filtered": filtered_hazards["risk_category"]
            .value_counts()
            .reindex(RISK_LEVELS, fill_value=0)
            .astype(int)
            .to_dict(),
            "heatmap_cell_total": heatmap_total(filtered_hazards),
            "failed_critical_controls": blocking_failure_count,
            "data_quality": quality,
            "validation_messages": all_messages,
            "requirement_hazard_mapping": mapping_statistics,
            **acceptance_summary_data,
            "critical_control_profile_status": critical_summary_data["critical_control_profile_status"],
            "criticality_level_counts": critical_summary_data["criticality_level_counts"],
            "critical_control_outcome_counts": critical_summary_data["critical_control_outcome_counts"],
            "deployment_blocking_failure_count": critical_summary_data["deployment_blocking_failure_count"],
            "conditional_gap_count": critical_summary_data["conditional_gap_count"],
            "evidence_deficiency_count": critical_summary_data["evidence_deficiency_count"],
            "incomplete_critical_record_count": critical_summary_data["incomplete_critical_record_count"],
            "manual_review_count": critical_summary_data["manual_review_count"],
            "critical_control_formal_approval_required_count": critical_summary_data["formal_approval_required_count"],
            "compensating_control_required_count": critical_summary_data["compensating_control_required_count"],
            "blocking_requirement_ids": critical_summary_data["blocking_requirement_ids"],
            "conditional_requirement_ids": critical_summary_data["conditional_requirement_ids"],
            "critical_control_limitations": critical_summary_data["critical_control_limitations"],
            "critical_control_governance": critical_summary_data,
            "critical_control_profile_file": critical_profile_filename,
            "critical_control_profile_validation_messages": critical_profile_messages,
            **validation_json_fields(
                validation_summaries,
                all_findings,
                validation_reference_date=validation_reference_date,
            ),
        }
        html = make_html_report(
            hazards,
            requirements,
            bri,
            decision,
            reasons,
            hazard_filename=hazard_filename,
            requirements_filename=requirements_filename,
            validation_messages=all_messages,
            filtered_hazards=filtered_hazards,
            mapping=mapping if mapping_ready else None,
            mapping_validation_messages=mapping_messages,
            risk_acceptance_policy=acceptance_policy,
            critical_profile=(
                profile_validation.data if critical_profile_ready and profile_validation is not None else None
            ),
            critical_control_assessment=critical_assessment if critical_profile_ready else None,
            critical_profile_validation_messages=critical_profile_messages,
            validation_findings=all_findings,
            validation_summaries=validation_summaries,
            validation_reference_date=validation_reference_date,
            author_email=configured_author_email(),
            assessment_metadata=st.session_state.get("_mobra_assessment_metadata", {}),
            manuscript_available=(BASE_DIR / "docs" / "MOBRA_Manuscript.pdf").is_file(),
            manuscript_sha256=manuscript_metadata().get("manuscript_sha256", ""),
            manuscript_version_note=manuscript_metadata().get("manuscript_version_note", ""),
            email_backup_enabled=EmailConfig.from_mapping(_secrets_mapping()).configured,
        )
        emit_notification(
            st, st.session_state, "report_generated", "HTML report and export package generated.", level="success"
        )
        st.download_button(
            "Download standalone HTML report", html.encode("utf-8"), EXPORT_FILENAMES["report"], "text/html"
        )
        st.download_button(
            "Download analyzed hazards (CSV)", csv_bytes(hazards), EXPORT_FILENAMES["hazards_csv"], "text/csv"
        )
        st.download_button(
            "Download analyzed requirements (CSV)",
            csv_bytes(requirements),
            EXPORT_FILENAMES["requirements_csv"],
            "text/csv",
        )
        if mapping_ready:
            st.download_button(
                "Download requirement–hazard mapping (CSV)",
                csv_bytes(mapping),
                EXPORT_FILENAMES["mapping_csv"],
                "text/csv",
            )
        if critical_profile_ready and critical_assessment is not None and critical_profile_raw is not None:
            st.download_button(
                "Download critical-control profile (CSV)",
                csv_bytes(profile_validation.data),
                EXPORT_FILENAMES["critical_profile_csv"],
                "text/csv",
            )
            st.download_button(
                "Download critical-control assessment (CSV)",
                csv_bytes(critical_assessment.data),
                EXPORT_FILENAMES["critical_assessment_csv"],
                "text/csv",
            )
            st.download_button(
                "Download critical-control summary (CSV)",
                csv_bytes(critical_control_summary_table(critical_assessment)),
                EXPORT_FILENAMES["critical_summary_csv"],
                "text/csv",
            )
        if mapping_ready and coverage_export is not None:
            st.download_button(
                "Download mapping coverage (CSV)",
                csv_bytes(coverage_export),
                EXPORT_FILENAMES["mapping_coverage_csv"],
                "text/csv",
            )
        st.download_button(
            "Download summary (JSON)",
            json.dumps(summary, indent=2, ensure_ascii=False).encode("utf-8"),
            EXPORT_FILENAMES["summary_json"],
            "application/json",
        )
        st.download_button(
            "Download validation findings (CSV)",
            csv_bytes(findings_frame(all_findings)),
            EXPORT_FILENAMES["validation_findings_csv"],
            "text/csv",
        )
        st.download_button(
            "Download validation summary (CSV)",
            csv_bytes(summaries_frame(validation_summaries)),
            EXPORT_FILENAMES["validation_summary_csv"],
            "text/csv",
        )
        st.download_button(
            "Download invalid records workbook (XLSX)",
            invalid_records_workbook_bytes(validation_summaries, all_findings, validation_datasets),
            EXPORT_FILENAMES["invalid_records_workbook"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.download_button(
            "Download analyzed workbook (XLSX)",
            excel_bytes(
                hazards,
                requirements,
                summary,
                mapping if mapping_ready else None,
                risk_acceptance_policy=acceptance_policy,
                critical_profile=(
                    profile_validation.data if critical_profile_ready and profile_validation is not None else None
                ),
                critical_control_assessment=critical_assessment if critical_profile_ready else None,
                validation_summaries=validation_summaries,
                validation_findings=all_findings,
                validation_datasets=validation_datasets,
            ),
            EXPORT_FILENAMES["workbook"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.download_button(
            "Download hazard template (CSV)",
            (BASE_DIR / "sample_data" / "hazards_template.csv").read_bytes(),
            "MOBRA_Hazards_Template.csv",
            "text/csv",
        )
        st.download_button(
            "Download requirements template (CSV)",
            (BASE_DIR / "sample_data" / "requirements_template.csv").read_bytes(),
            "MOBRA_Requirements_Template.csv",
            "text/csv",
        )
    with tab8:
        _render_resources_and_contact(
            requirements,
            hazards,
            html,
            json.dumps(summary, indent=2, ensure_ascii=False).encode("utf-8"),
            csv_bytes(findings_frame(all_findings)),
            csv_bytes(critical_assessment.data if critical_assessment is not None else pd.DataFrame()),
            csv_bytes(mapping if mapping_ready else pd.DataFrame()),
        )


if __name__ == "__main__":
    main()
