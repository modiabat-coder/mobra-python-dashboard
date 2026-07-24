"""Page renderers for the MOBRA Streamlit application."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from mobra.acceptance import (
    RiskAcceptancePolicy,
    apply_risk_acceptance,
    risk_acceptance_summary,
)
from mobra.actions import build_corrective_actions
from mobra.charts import (
    action_status_figure,
    bri_progress_figure,
    domain_figure,
    executive_radial_gauge,
    hazards_by_domain_figure,
    heatmap_figure,
    initial_residual_figure,
    primary_bri_dial_figure,
    risk_counts_figure,
    top_hazards_figure,
)
from mobra.config import (
    APP_DESCRIPTION,
    APP_FULL_NAME,
    APP_NAME,
    AUTHOR_EMAIL,
    AUTHOR_NAME,
    DANGER_COLOR,
    DECISION_COLORS,
    DECISION_DO_NOT_DEPLOY,
    DECISION_READY,
    PRIMARY_COLOR,
    PROJECT_ROOT,
    REPOSITORY_URL,
    RISK_COLORS,
    RISK_LEVELS,
    RISK_RANGES,
    SYNTHETIC_DATA_LABEL,
    UPLOADED_DATA_LABEL,
    count_phrase,
)
from mobra.critical_controls import (
    assess_critical_controls,
    critical_control_summary_table,
    validate_critical_control_profile,
)
from mobra.decisions import decision_risk_column, deployment_decision
from mobra.educational_media import (
    educational_media_package,
    load_educational_media,
    media_summary,
)
from mobra.help_content import help_topics, render_help
from mobra.io import (
    auto_detect_excel_sheet,
    list_excel_sheets,
    read_data_file,
    read_json_collections,
    source_name,
    split_unified_file,
)
from mobra.mapping import (
    hazard_mapping_ranking,
    mapping_coverage_summary,
    mapping_coverage_table,
    requirement_mapping_ranking,
    validate_mapping,
)
from mobra.manuscript import manuscript_download_bytes, manuscript_metadata
from mobra.mission_map import STATUS_COLORS, mission_map_deck, synthetic_mission_stages
from mobra.operational_tools import (
    build_backup_zip,
    build_field_assessment_package,
    build_hazard_import_template,
    build_hazard_pdf,
    build_hazard_register_workbook,
    build_orl_assessment_workbook,
    build_orl_pdf,
    build_requirements_import_template,
    template_catalogue_csv,
)
from mobra.readiness import (
    calculate_bri,
    data_quality_summary,
    domain_readiness,
    failed_critical_controls,
)
from mobra.reporting import (
    csv_bytes,
    json_bytes,
    make_excel_workbook,
    make_html_report,
    summary_payload,
)
from mobra.resources import (
    catalogue_csv_bytes,
    catalogue_xlsx_bytes,
    load_normative_resources,
    load_supporting_literature,
    resource_catalogue_frame,
)
from mobra.risk import assert_heatmap_total, heatmap_total, valid_hazard_count
from mobra.validation import (
    HAZARD_REQUIRED_FIELDS,
    REQUIREMENT_REQUIRED_FIELDS,
    ValidationResult,
    normalise_columns,
    suggest_column_mapping,
    validate_hazards,
    validate_requirements,
    validation_issue_table,
)
from mobra.validation_findings import (
    findings_frame,
    validate_cross_dataset_consistency,
)
from ui.components import (
    logo_data_uri,
    render_decision_banner,
    render_empty_state,
    render_logo,
    render_metric_grid,
    render_page_header,
    render_section_header,
    render_step,
    render_validation_alert,
)
from ui.state import (
    active_supporting_data,
    navigate_to,
    set_active_data,
    set_supporting_data,
)


@dataclass
class AssessmentContext:
    """Validated data and derived values shared by all page renderers."""

    meta: dict[str, Any]
    hazard_result: ValidationResult
    requirement_result: ValidationResult
    hazards: pd.DataFrame
    requirements: pd.DataFrame
    bri: float
    domains: pd.DataFrame
    decision: str
    reasons: list[str]
    quality: dict[str, int | float]
    actions: pd.DataFrame
    validation_errors: list[str]
    validation_warnings: list[str]

    @property
    def ready_for_analysis(self) -> bool:
        return not self.validation_errors


def build_assessment_context(meta: dict[str, Any]) -> AssessmentContext:
    """Validate active raw data and calculate shared assessment outputs."""
    hazard_result = validate_hazards(
        meta.get("hazards_raw", pd.DataFrame()),
        st.session_state.get("hazard_mapping", {}),
    )
    requirement_result = validate_requirements(
        meta.get("requirements_raw", pd.DataFrame()),
        st.session_state.get("requirement_mapping", {}),
    )
    hazards = hazard_result.data
    requirements = requirement_result.data
    errors = [*hazard_result.errors, *requirement_result.errors]
    warnings = [*hazard_result.warnings, *requirement_result.warnings]
    bri = calculate_bri(requirements)
    domains = domain_readiness(requirements)
    decision, reasons = deployment_decision(
        hazards,
        requirements,
        bri,
        validation_errors=errors,
    )
    return AssessmentContext(
        meta=meta,
        hazard_result=hazard_result,
        requirement_result=requirement_result,
        hazards=hazards,
        requirements=requirements,
        bri=bri,
        domains=domains,
        decision=decision,
        reasons=reasons,
        quality=data_quality_summary(hazards, requirements),
        actions=build_corrective_actions(hazards, requirements),
        validation_errors=errors,
        validation_warnings=warnings,
    )


def _format_bri(value: float) -> str:
    return "N/A" if pd.isna(value) else f"{value:.1f}%"


def _meaningful(series: pd.Series) -> pd.Series:
    normalized = series.astype("string").str.strip().str.lower()
    return series.notna() & ~normalized.isin(
        {"", "nan", "none", "not provided", "n/a", "na", "unknown"}
    )


def _analysis_gate(context: AssessmentContext) -> bool:
    if context.ready_for_analysis:
        return True
    render_empty_state(
        "Analysis paused until data issues are resolved",
        "Open Data Validation to review blocking errors, then correct the source file or Column Mapping.",
        icon="!",
    )
    if st.button("Open Data Validation", type="primary"):
        navigate_to("Data Validation")
    return False


def _supporting_results(context: AssessmentContext) -> tuple[Any, Any]:
    """Validate optional supporting datasets without altering canonical scores."""
    supporting = active_supporting_data()
    mapping_result = validate_mapping(
        supporting.get("mapping_raw", pd.DataFrame()),
        context.requirements,
        context.hazards,
    )
    profile_result = validate_critical_control_profile(
        supporting.get("critical_profile_raw", pd.DataFrame()),
        context.requirements,
    )
    return mapping_result, profile_result


def _render_supporting_data_import(context: AssessmentContext) -> None:
    """Import the preserved mapping and critical-control governance datasets."""
    supporting = active_supporting_data()
    with st.expander(
        "Advanced supporting data · requirement–hazard mapping and governance profile",
        expanded=False,
    ):
        st.caption(
            "These optional datasets restore relationship analysis and governance detail. "
            "They never replace the canonical BRI, Risk Score, failed Critical Control count, "
            "or Deployment Decision."
        )
        source_columns = st.columns(2)
        with source_columns[0]:
            st.markdown(
                f"**Active mapping:** `{supporting.get('mapping_filename', 'Not loaded')}`"
            )
            mapping_file = st.file_uploader(
                "Upload requirement–hazard mapping",
                type=["csv", "xlsx", "xls", "json"],
                key="supporting_mapping_upload",
            )
        with source_columns[1]:
            st.markdown(
                "**Active governance profile:** "
                f"`{supporting.get('critical_profile_filename', 'Not loaded')}`"
            )
            profile_file = st.file_uploader(
                "Upload Critical Control governance profile",
                type=["csv", "xlsx", "xls", "json"],
                key="supporting_profile_upload",
            )
        if not mapping_file and not profile_file:
            return
        try:
            mapping = (
                read_data_file(mapping_file)
                if mapping_file
                else supporting.get("mapping_raw", pd.DataFrame())
            )
            profile = (
                read_data_file(profile_file)
                if profile_file
                else supporting.get("critical_profile_raw", pd.DataFrame())
            )
            mapping_result = validate_mapping(
                mapping,
                context.requirements,
                context.hazards,
            )
            profile_result = validate_critical_control_profile(
                profile,
                context.requirements,
            )
        except (ValueError, TypeError) as exc:
            st.error(f"Supporting data could not be read: {exc}")
            return
        render_metric_grid(
            [
                ("Mapping Rows", len(mapping_result.data), "Relationship records"),
                (
                    "Mapping Errors",
                    len(mapping_result.errors),
                    "Must be reviewed",
                    DANGER_COLOR if mapping_result.errors else PRIMARY_COLOR,
                ),
                ("Profile Rows", len(profile_result.data), "Governance records"),
                (
                    "Profile Errors",
                    len(profile_result.errors),
                    "Must be reviewed",
                    DANGER_COLOR if profile_result.errors else PRIMARY_COLOR,
                ),
            ]
        )
        if st.button(
            "Activate Supporting Data",
            type="primary",
            disabled=bool(mapping_result.errors or profile_result.errors),
            width="stretch",
        ):
            set_supporting_data(
                mapping,
                profile,
                mapping_filename=source_name(mapping_file)
                if mapping_file
                else supporting.get("mapping_filename", "mapping"),
                critical_profile_filename=source_name(profile_file)
                if profile_file
                else supporting.get("critical_profile_filename", "critical_profile"),
            )
            st.success("Supporting mapping and governance data are active.")
            st.rerun()


def _render_mapping_analysis(context: AssessmentContext) -> None:
    """Render preserved many-to-many requirement–hazard relationship analysis."""
    mapping_result, _ = _supporting_results(context)
    mapping = mapping_result.data
    render_section_header(
        "Requirement–Hazard Mapping",
        icon="↔",
        help_text=(
            "Relationship analysis is supplementary and does not alter BRI, Risk Scores, "
            "or the Deployment Decision."
        ),
    )
    if mapping.empty:
        render_empty_state(
            "No mapping data are active",
            "Open Data Import and load the optional requirement–hazard mapping dataset.",
            icon="↔",
        )
        return
    coverage = mapping_coverage_summary(
        mapping,
        context.requirements,
        context.hazards,
    )
    render_metric_grid(
        [
            ("Mapping Links", coverage["mapping_links"], "Validated relationships"),
            (
                "Hazard Coverage",
                f"{coverage['hazard_coverage_pct']:.1f}%",
                f"{coverage['hazards_mapped']} of {coverage['hazards_total']}",
            ),
            (
                "Requirement Coverage",
                f"{coverage['requirement_coverage_pct']:.1f}%",
                f"{coverage['requirements_mapped']} of {coverage['requirements_total']}",
            ),
            ("Critical Links", coverage["critical_links"], "Priority relationships"),
        ]
    )
    coverage_tab, hazard_tab, requirement_tab, findings_tab = st.tabs(
        [
            "Coverage",
            "Hazard Link Ranking",
            "Requirement Link Ranking",
            "Mapping Findings",
        ]
    )
    with coverage_tab:
        st.dataframe(
            mapping_coverage_table(
                mapping,
                context.requirements,
                context.hazards,
            ),
            width="stretch",
            hide_index=True,
        )
    with hazard_tab:
        st.dataframe(
            hazard_mapping_ranking(mapping, context.hazards),
            width="stretch",
            hide_index=True,
            height=420,
        )
    with requirement_tab:
        st.dataframe(
            requirement_mapping_ranking(mapping, context.requirements),
            width="stretch",
            hide_index=True,
            height=420,
        )
    with findings_tab:
        finding_data = findings_frame(mapping_result.findings)
        if finding_data.empty:
            st.success("No blocking mapping findings were detected.")
        else:
            st.dataframe(finding_data, width="stretch", hide_index=True)
            st.download_button(
                "Download Mapping Findings",
                csv_bytes(finding_data),
                "MOBRA_Mapping_Findings.csv",
                "text/csv",
                width="stretch",
            )


def _render_critical_control_governance(context: AssessmentContext) -> None:
    """Render profile detail while preserving the canonical 11-control outcome."""
    _, profile_result = _supporting_results(context)
    render_section_header(
        "Critical Control Governance",
        icon="◆",
        help_text=(
            "The governance profile adds classification and approval detail. "
            "The canonical failed Critical Control calculation remains non-bypassable."
        ),
    )
    if profile_result.data.empty:
        render_empty_state(
            "No governance profile is active",
            "Open Data Import and load the optional Critical Control governance profile.",
            icon="◆",
        )
        return
    assessment = assess_critical_controls(context.requirements, profile_result.data)
    canonical_failed = failed_critical_controls(context.requirements)
    failed_ids = set(
        canonical_failed.get("requirement_id", pd.Series(dtype="string"))
        .astype(str)
        .str.strip()
    )
    governance = assessment.data.copy()
    governance["canonical_failed_critical_control"] = (
        governance.get("requirement_id", pd.Series(dtype="string"))
        .astype(str)
        .str.strip()
        .isin(failed_ids)
    )
    render_metric_grid(
        [
            (
                "Failed Critical Controls",
                len(canonical_failed),
                "Canonical deployment blockers",
                DANGER_COLOR,
            ),
            (
                "Evidence Deficiencies",
                len(assessment.evidence_deficiencies),
                "Governance review",
            ),
            (
                "Manual Review Items",
                len(assessment.manual_review_items),
                "Human decision required",
            ),
            (
                "Formal Approval Required",
                int(governance.get("formal_approval_required", pd.Series(dtype=bool)).sum()),
                "Governance workflow",
            ),
        ]
    )
    st.error(
        f"The active assessment contains {len(canonical_failed)} failed Critical Controls. "
        "Supplementary profile classifications cannot reduce or bypass this result."
    )
    display_columns = [
        "requirement_id",
        "domain",
        "requirement",
        "criticality_level",
        "minimum_acceptable_score",
        "observed_score",
        "evidence_status",
        "approval_status",
        "canonical_failed_critical_control",
        "requires_manual_review",
        "formal_approval_required",
        "critical_control_reason",
    ]
    st.dataframe(
        governance[[column for column in display_columns if column in governance.columns]],
        width="stretch",
        hide_index=True,
        height=460,
    )
    with st.expander("Governance summary download", expanded=False):
        st.download_button(
            "Download Governance Summary",
            csv_bytes(critical_control_summary_table(assessment)),
            "MOBRA_Critical_Control_Governance_Summary.csv",
            "text/csv",
            width="stretch",
        )


def _render_risk_acceptance(context: AssessmentContext) -> None:
    """Render provisional acceptance analysis without changing the fixed decision."""
    render_section_header(
        "Risk Acceptance and Approval",
        icon="✓",
        help_text=(
            "This is a supplementary governance view. Fixed risk bands and the "
            "non-bypassable Deployment Decision remain authoritative."
        ),
    )
    policy = RiskAcceptancePolicy()
    assessed = apply_risk_acceptance(context.hazards, policy)
    summary = risk_acceptance_summary(assessed, policy)
    counts = summary.get("acceptance_status_counts", {})
    render_metric_grid(
        [
            ("Acceptable", counts.get("Acceptable", 0), "Low-risk disposition"),
            (
                "Monitoring",
                counts.get("Acceptable with monitoring", 0),
                "Moderate-risk disposition",
            ),
            ("Conditional", counts.get("Conditional", 0), "High-risk review"),
            (
                "Unacceptable",
                counts.get("Unacceptable", 0),
                "Extreme risk remains blocking",
                DANGER_COLOR,
            ),
        ]
    )
    acceptance_columns = [
        "hazard_id",
        "hazard",
        "decision_risk_score",
        "decision_risk_category",
        "decision_risk_source",
        "risk_acceptance_status",
        "acceptance_action_required",
        "formal_approval_required",
        "acceptance_reason",
    ]
    st.dataframe(
        assessed[[column for column in acceptance_columns if column in assessed.columns]],
        width="stretch",
        hide_index=True,
        height=440,
    )


def _risk_category_style(value: object) -> str:
    color = RISK_COLORS.get(str(value))
    if not color:
        return ""
    text = "#3D3100" if str(value) == "Moderate" else "#FFFFFF"
    return f"background-color:{color};color:{text};font-weight:700"


def _file_size_label(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024**2:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024**2:.1f} MB"


def _last_update(meta: dict[str, Any]) -> str:
    raw = meta.get("last_updated")
    try:
        return datetime.fromisoformat(str(raw)).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return "Not available"


def render_home(context: AssessmentContext) -> None:
    """Render the executive summary landing page."""
    logo_uri = logo_data_uri()
    logo_html = (
        f'<img class="mobra-hero-logo" src="{logo_uri}" '
        f'alt="{escape(APP_NAME)} wordmark">'
        if logo_uri
        else f'<div class="mobra-hero-fallback">{escape(APP_NAME)}</div>'
    )
    st.markdown(
        f"""
        <div class="mobra-hero">
          <div class="mobra-hero-brand">
            {logo_html}
            <div class="mobra-hero-copy">
              <div class="mobra-eyebrow">EXECUTIVE OVERVIEW</div>
              <h1>Operational readiness at a glance</h1>
              <h3>{escape(APP_FULL_NAME)}</h3>
              <p>{escape(APP_DESCRIPTION)}</p>
            </div>
          </div>
          <div class="mobra-hero-meta">
            <span><strong>Active source</strong> · {escape(str(context.meta.get("source_label", "No data")))}</span>
            <span><strong>Decision safeguards</strong> · Critical controls remain non-bypassable</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_decision_banner(context.decision, context.reasons)
    failed_count = len(failed_critical_controls(context.requirements))
    render_section_header(
        "Biosecurity Readiness Index",
        icon="◔",
        help_text=(
            "The dial reflects the numerical BRI only. The formal Deployment "
            "Decision and Critical Control overrides remain authoritative."
        ),
    )
    with st.container(border=True):
        st.plotly_chart(
            primary_bri_dial_figure(
                context.bri,
                critical_override_active=failed_count > 0,
            ),
            width="stretch",
            key="home_primary_bri_dial",
        )
        if failed_count:
            control_word = "control" if failed_count == 1 else "controls"
            decision_note = (
                f"Readiness score: {_format_bri(context.bri)}. Deployment remains "
                f"prohibited because {failed_count} mission-critical {control_word} failed."
            )
        else:
            decision_note = (
                f"Readiness score: {_format_bri(context.bri)}. Final decision: "
                f"{context.decision}. The readiness category does not replace "
                "the formal Deployment Decision."
            )
        st.markdown(
            f"""
            <div class="mobra-bri-decision-note" role="note"
                 aria-label="BRI interpretation and final deployment decision">
              <span class="mobra-bri-decision-badge"
                    style="--badge-color:{escape(DECISION_COLORS.get(context.decision, PRIMARY_COLOR))}">
                {escape(context.decision)}
              </span>
              <p>{escape(decision_note)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            "The gauge visualizes weighted readiness only. It cannot authorize "
            "deployment or bypass failed Critical Controls."
        )
    risk_basis = decision_risk_column(context.hazards)
    critical_flags = context.requirements.get(
        "critical_control",
        pd.Series(False, index=context.requirements.index),
    )
    if critical_flags.dtype == bool:
        parsed_critical_flags = critical_flags.fillna(False)
    else:
        parsed_critical_flags = (
            critical_flags.astype("string")
            .str.strip()
            .str.lower()
            .isin(["true", "1", "yes", "y", "critical"])
        )
    critical_total = int(parsed_critical_flags.sum())
    critical_satisfaction = (
        100 * max(critical_total - failed_count, 0) / critical_total
        if critical_total
        else 0.0
    )
    elevated_count = int(
        context.hazards.get(risk_basis, pd.Series(dtype="string"))
        .isin(["High", "Extreme"])
        .sum()
    )
    elevated_load = (
        100 * elevated_count / len(context.hazards)
        if len(context.hazards)
        else 0.0
    )

    render_section_header(
        "Executive Indicators",
        icon="◔",
        help_text=(
            "Contextual visual indicators only. Formal deployment logic and "
            "Critical Control overrides remain authoritative."
        ),
    )
    gauge_columns = st.columns(3)
    with gauge_columns[0]:
        st.plotly_chart(
            executive_radial_gauge(context.bri, "Overall BRI"),
            width="stretch",
            key="home_bri_radial",
        )
        st.caption(
            "Weighted observed score ÷ maximum score. BRI alone never authorizes deployment."
        )
    with gauge_columns[1]:
        st.plotly_chart(
            executive_radial_gauge(
                critical_satisfaction,
                "Critical Controls Satisfied",
            ),
            width="stretch",
            key="home_critical_controls_radial",
        )
        st.caption(
            f"{max(critical_total - failed_count, 0)}/{critical_total} Critical Controls "
            f"satisfied; {failed_count} remain non-bypassable blockers."
        )
    with gauge_columns[2]:
        st.plotly_chart(
            executive_radial_gauge(
                elevated_load,
                "High / Extreme Risk Load",
                higher_is_better=False,
            ),
            width="stretch",
            key="home_elevated_risk_radial",
        )
        st.caption(
            f"{elevated_count}/{len(context.hazards)} hazards are High or Extreme "
            f"using {risk_basis.replace('_', ' ')}."
        )
    st.info(
        "Indicator colors support rapid review only. The formal result remains "
        "governed by validated data, fixed risk thresholds, and the "
        "non-bypassable deployment rules."
    )

    residual_extreme = int(
        context.hazards.get(risk_basis, pd.Series(dtype="string")).eq("Extreme").sum()
    )
    assessed = int(context.requirements.get("observed_score", pd.Series()).notna().sum())
    evidence_complete = int(
        (~context.requirements.get("evidence_missing", pd.Series(False, index=context.requirements.index))).sum()
    )
    data_completeness = 100 - float(context.quality.get("missing_value_pct", 0))
    open_actions = (
        int(
            (
                ~context.actions["status"]
                .astype("string")
                .str.lower()
                .isin(["completed", "closed", "resolved", "compliant"])
            ).sum()
        )
        if not context.actions.empty
        else 0
    )
    metric_values = [
        ("Overall BRI", _format_bri(context.bri), "Weighted observed ÷ maximum score", PRIMARY_COLOR),
        ("Requirements Assessed", f"{assessed}/{len(context.requirements)}", "Operational readiness records", PRIMARY_COLOR),
        ("Total Hazards", len(context.hazards), "Structurally valid imported records", PRIMARY_COLOR),
        ("Extreme Residual Risks", residual_extreme, f"Using {risk_basis.replace('_', ' ')}", RISK_COLORS["Extreme"]),
        ("Failed Critical Controls", failed_count, "Non-bypassable deployment blockers", DECISION_COLORS[DECISION_DO_NOT_DEPLOY]),
        ("Open Corrective Actions", open_actions, "Not completed or closed", RISK_COLORS["High"]),
        ("Data Completeness", f"{max(0, data_completeness):.1f}%", f"Evidence complete: {evidence_complete}/{len(context.requirements)}", PRIMARY_COLOR),
        ("Last Assessment Date", _last_update(context.meta), context.meta.get("source_label", ""), PRIMARY_COLOR),
    ]
    render_metric_grid(metric_values)

    render_section_header("Domain Readiness Overview", icon="◔", help_text="Weighted readiness by operational domain.")
    if context.domains.empty:
        render_empty_state("Domain readiness unavailable", "Validated domain scores are required.")
    else:
        st.plotly_chart(
            domain_figure(context.domains),
            width="stretch",
            key="home_domain_readiness",
        )
        least = context.domains.nsmallest(3, "readiness_pct")
        st.caption(
            "Priority attention: "
            + ", ".join(
                f"{row.domain} ({row.readiness_pct:.1f}%)"
                for row in least.itertuples()
            )
            + "."
        )

    render_section_header("Risk Overview", icon="▦")
    if context.hazards.empty:
        render_empty_state("No hazards available", "Import a hazard register to display risk analysis.")
    else:
        left, right = st.columns(2)
        with left:
            st.plotly_chart(
                risk_counts_figure(context.hazards),
            width="stretch",
                key="home_risk_distribution",
            )
        with right:
            st.plotly_chart(
                top_hazards_figure(context.hazards, limit=7),
            width="stretch",
                key="home_top_hazards",
            )

    render_section_header("Critical Controls and Alerts", icon="!")
    failed = failed_critical_controls(context.requirements)
    if failed.empty and not context.validation_errors:
        st.success("All supplied Critical Controls are satisfied and supported by required evidence.")
    else:
        if context.validation_errors:
            error_count = len(context.validation_errors)
            st.error(
                f"{count_phrase(error_count, 'blocking data-validation error')} "
                f"{'requires' if error_count == 1 else 'require'} resolution."
            )
        if not failed.empty:
            essential = [
                column
                for column in (
                    "requirement_id",
                    "domain",
                    "requirement",
                    "observed_score",
                    "maximum_score",
                    "objective_evidence",
                )
                if column in failed.columns
            ]
            st.dataframe(
                failed[essential].head(12),
            width="stretch",
                hide_index=True,
                height=330,
            )

    render_section_header("Priority Corrective Actions", icon="↻")
    if context.actions.empty:
        render_empty_state("No corrective actions recorded", "Add actions to the hazard or requirement records when needed.")
    else:
        action_columns = [
            "action",
            "related_item",
            "priority",
            "responsible_person",
            "target_date",
            "status",
        ]
        st.dataframe(
            context.actions[action_columns].head(10),
            width="stretch",
            hide_index=True,
            height=330,
        )

    render_section_header("Detailed Analysis and Reports", icon="→")
    button_columns = st.columns(3)
    destinations = [
        ("Open Risk Analysis", "Risk Analysis"),
        ("Open Readiness Dashboard", "Readiness Dashboard"),
        ("Open Mission Map", "Mission Map"),
        ("Review Deployment Decision", "Deployment Decision"),
        ("Open Reports and Export", "Reports and Export"),
        ("Open Research & References", "Research and References"),
    ]
    for index, (label, page) in enumerate(destinations):
        column = button_columns[index % len(button_columns)]
        with column:
            if st.button(label, width="stretch"):
                navigate_to(page)


def _read_uploaded(
    uploaded: Any,
    *,
    kind: str,
    key_prefix: str,
) -> tuple[pd.DataFrame | None, str]:
    """Read one uploader payload with automatic and manual worksheet choice."""
    if uploaded is None:
        return None, "Not applicable"
    if source_name(uploaded).lower().endswith(".xls"):
        st.caption(
            "Legacy XLS selected: MOBRA uses the xlrd compatibility reader for this file."
        )
    sheets = list_excel_sheets(uploaded)
    selected_sheet: str | int = 0
    display_sheet = "Not applicable"
    if sheets:
        detected = auto_detect_excel_sheet(uploaded, kind) or sheets[0]
        selected_sheet = st.selectbox(
            f"Worksheet for {source_name(uploaded)}",
            sheets,
            index=sheets.index(detected),
            key=f"{key_prefix}_sheet_{source_name(uploaded)}",
            help=f"MOBRA detected “{detected}” as the most suitable worksheet. You may override it.",
        )
        display_sheet = str(selected_sheet)
    try:
        with st.spinner(f"Reading {source_name(uploaded)}…"):
            frame = read_data_file(uploaded, sheet_name=selected_sheet)
        if frame.empty:
            st.error("The selected file or worksheet is empty. Choose a populated data table.")
            return None, display_sheet
        return frame, display_sheet
    except (ValueError, OSError, TypeError) as exc:
        st.error(str(exc))
        return None, display_sheet


def _mapping_controls(
    frame: pd.DataFrame,
    *,
    kind: str,
    key_prefix: str,
) -> dict[str, str]:
    """Show detected mappings and collect deliberate required-field overrides."""
    mapping = suggest_column_mapping(frame, kind)
    display = mapping.rename(
        columns={
            "standard_field": "Standard MOBRA field",
            "detected_source_column": "Detected source column",
            "confidence_pct": "Confidence (%)",
            "mapping_status": "Status",
            "required": "Required",
        }
    )
    st.dataframe(display, width="stretch", hide_index=True, height=285)
    st.caption(
        "Confidence indicates technical name matching only: 100% is an exact normalized "
        "match, 90% is a recognized alias, and 0% requires review. It does not confirm "
        "scientific validity."
    )
    required = HAZARD_REQUIRED_FIELDS if kind == "hazards" else REQUIREMENT_REQUIRED_FIELDS
    normalized = normalise_columns(frame)
    overrides: dict[str, str] = {}
    st.caption("Manual override is only needed when automatic detection is incorrect.")
    columns = st.columns(3)
    for column, target in zip(columns, required):
        detected_rows = mapping.loc[mapping["standard_field"].eq(target)]
        detected = (
            str(detected_rows.iloc[0]["detected_source_column"])
            if not detected_rows.empty
            else ""
        )
        options = ["(automatic)", *normalized.columns.tolist()]
        with column:
            selected = st.selectbox(
                target.replace("_", " ").title(),
                options,
                index=0,
                key=f"{key_prefix}_{kind}_{target}",
                help=f"Detected: {detected or 'missing'}",
            )
        if selected != "(automatic)":
            overrides[target] = selected
    return overrides


def _file_summary(
    *,
    filename: str,
    size: int,
    frame: pd.DataFrame,
    sheet: str,
) -> None:
    values = [
        ("File", Path(filename).name, Path(filename).suffix.upper().lstrip(".") or "Unknown"),
        ("File Size", _file_size_label(size), f"{len(frame)} rows"),
        ("Table Shape", f"{len(frame)} × {len(frame.columns)}", f"Worksheet: {sheet}"),
    ]
    render_metric_grid(values, max_columns=3)


def _import_review(
    hazards: pd.DataFrame,
    requirements: pd.DataFrame,
    *,
    hazard_filename: str,
    requirements_filename: str,
    total_size: int,
    selected_sheet: str,
) -> None:
    """Render preview, mapping, validation, and final import confirmation."""
    preview_tab, mapping_tab, confirm_tab = st.tabs(
        ["2 · Preview", "3 · Column Mapping", "4–6 · Validate and Activate"]
    )
    with preview_tab:
        editable = st.checkbox(
            "Enable editable preview",
            value=False,
            help="Edits affect the analysis copy only; the source file is never overwritten.",
        )
        st.caption("Only the first 20 rows are displayed in this preview.")
        left, right = st.columns(2)
        with left:
            st.markdown("#### Hazard Register")
            if editable:
                hazards = st.data_editor(
                    hazards,
                    num_rows="dynamic",
            width="stretch",
                    height=350,
                    key="import_hazard_editor",
                )
            else:
                st.dataframe(hazards.head(20), width="stretch", hide_index=True, height=350)
        with right:
            st.markdown("#### Requirements")
            if editable:
                requirements = st.data_editor(
                    requirements,
                    num_rows="dynamic",
            width="stretch",
                    height=350,
                    key="import_requirement_editor",
                )
            else:
                st.dataframe(requirements.head(20), width="stretch", hide_index=True, height=350)
    with mapping_tab:
        st.markdown("#### Hazard field mapping")
        hazard_mapping = _mapping_controls(
            hazards,
            kind="hazards",
            key_prefix="import",
        )
        st.markdown("#### Requirement field mapping")
        requirement_mapping = _mapping_controls(
            requirements,
            kind="requirements",
            key_prefix="import",
        )
    with confirm_tab:
        hazard_mapping = locals().get("hazard_mapping", st.session_state.get("hazard_mapping", {}))
        requirement_mapping = locals().get(
            "requirement_mapping",
            st.session_state.get("requirement_mapping", {}),
        )
        with st.spinner("Validating MOBRA fields and assessment values…"):
            hazard_result = validate_hazards(hazards, hazard_mapping)
            requirement_result = validate_requirements(requirements, requirement_mapping)
        errors = [*hazard_result.errors, *requirement_result.errors]
        warnings = [*hazard_result.warnings, *requirement_result.warnings]
        render_metric_grid(
            [
                ("Errors", len(errors), "Must be resolved"),
                ("Warnings", len(warnings), "Review recommended"),
                ("Hazards", len(hazard_result.data), "Structurally valid rows"),
                ("Requirements", len(requirement_result.data), "Structurally valid rows"),
            ]
        )
        for message in errors:
            st.error(message)
        for message in warnings:
            st.warning(message)
        missing = [
            *hazard_result.missing_columns,
            *requirement_result.missing_columns,
        ]
        if missing:
            st.error(
                "Analysis cannot begin until these required fields are mapped: "
                + ", ".join(missing)
                + "."
            )
        if st.button(
            "Confirm data for analysis",
            type="primary",
            disabled=bool(errors),
            width="stretch",
        ):
            st.session_state.hazard_mapping = hazard_mapping
            st.session_state.requirement_mapping = requirement_mapping
            set_active_data(
                hazards,
                requirements,
                hazard_filename=hazard_filename,
                requirements_filename=requirements_filename,
                source_label=UPLOADED_DATA_LABEL,
                file_size=total_size,
                selected_sheet=selected_sheet,
            )
            st.success("Uploaded Assessment Data are validated and active.")
            navigate_to("Home")


def render_data_import(context: AssessmentContext) -> None:
    """Render the guided CSV, Excel, and JSON import workflow."""
    render_page_header(
        "Data Import",
        "Load, map, validate, and explicitly confirm assessment data before analysis.",
        icon="⇧",
        status=context.meta.get("source_label"),
    )
    step_columns = st.columns(3)
    steps = [
        (1, "Select and upload", "Choose separate or unified supported files."),
        (2, "Detect structure", "Review detected records and Excel worksheet."),
        (3, "Map columns", "Confirm standard MOBRA fields."),
        (4, "Validate values", "Check required fields and valid ranges."),
        (5, "Review warnings", "Resolve blockers and assess cautions."),
        (6, "Activate data", "Confirm the validated analysis copy."),
    ]
    for index, step in enumerate(steps):
        with step_columns[index % 3]:
            render_step(*step)

    st.info(
        "Minimum hazard fields: Hazard, Likelihood, Consequence. "
        "Minimum requirement fields: Requirement, Observed Score, Maximum Score. "
        "Supported formats are CSV, XLSX, XLS, and JSON; JSON files are limited to 50 MB."
    )
    structure = st.radio(
        "1. Select file structure",
        ["Separate hazard and requirement files", "One unified file"],
        horizontal=True,
    )
    if st.button("Restore Synthetic Demonstration Data"):
        demo_hazards = pd.read_csv(PROJECT_ROOT / "sample_data" / "hazards_sample.csv")
        demo_requirements = pd.read_csv(
            PROJECT_ROOT / "sample_data" / "requirements_sample.csv"
        )
        demo_mapping = pd.read_csv(
            PROJECT_ROOT / "sample_data" / "requirement_hazard_mapping.csv"
        )
        demo_profile = pd.read_csv(
            PROJECT_ROOT / "sample_data" / "critical_control_profile.csv"
        )
        st.session_state.hazard_mapping = {}
        st.session_state.requirement_mapping = {}
        set_active_data(
            demo_hazards,
            demo_requirements,
            hazard_filename="hazards_sample.csv",
            requirements_filename="requirements_sample.csv",
            source_label=SYNTHETIC_DATA_LABEL,
            source_kind="synthetic",
            file_size=0,
        )
        set_supporting_data(
            demo_mapping,
            demo_profile,
            mapping_filename="requirement_hazard_mapping.csv",
            critical_profile_filename="critical_control_profile.csv",
            source_kind="synthetic",
        )
        st.success("Synthetic Demonstration Data restored.")
        navigate_to("Home")

    _render_supporting_data_import(context)

    if structure == "Separate hazard and requirement files":
        upload_columns = st.columns(2)
        with upload_columns[0]:
            hazard_file = st.file_uploader(
                "2. Upload Hazard Register",
                type=["csv", "xlsx", "xls", "json"],
                key="hazard_upload",
                help="Supported formats: CSV, XLSX, XLS, JSON.",
            )
            hazards, hazard_sheet = _read_uploaded(
                hazard_file,
                kind="hazards",
                key_prefix="hazard",
            )
        with upload_columns[1]:
            requirement_file = st.file_uploader(
                "2. Upload Requirements Assessment",
                type=["csv", "xlsx", "xls", "json"],
                key="requirement_upload",
                help="Supported formats: CSV, XLSX, XLS, JSON.",
            )
            requirements, requirement_sheet = _read_uploaded(
                requirement_file,
                kind="requirements",
                key_prefix="requirement",
            )
        if hazards is None or requirements is None:
            render_empty_state(
                "Select both assessment files",
                "Upload one Hazard Register and one Requirements Assessment file to continue.",
                icon="⇧",
            )
            return
        _file_summary(
            filename=source_name(hazard_file),
            size=int(getattr(hazard_file, "size", 0)),
            frame=hazards,
            sheet=hazard_sheet,
        )
        _file_summary(
            filename=source_name(requirement_file),
            size=int(getattr(requirement_file, "size", 0)),
            frame=requirements,
            sheet=requirement_sheet,
        )
        _import_review(
            hazards,
            requirements,
            hazard_filename=source_name(hazard_file),
            requirements_filename=source_name(requirement_file),
            total_size=int(getattr(hazard_file, "size", 0))
            + int(getattr(requirement_file, "size", 0)),
            selected_sheet=f"Hazards: {hazard_sheet}; Requirements: {requirement_sheet}",
        )
        return

    unified_file = st.file_uploader(
        "2. Upload unified MOBRA file",
        type=["csv", "xlsx", "xls", "json"],
        key="unified_upload",
        help="Include a record_type field containing hazard or requirement values.",
    )
    unified, unified_sheet = _read_uploaded(
        unified_file,
        kind="unified",
        key_prefix="unified",
    )
    if unified is None:
        render_empty_state(
            "No unified file selected",
            "Upload a supported unified file to preview and split its records.",
            icon="⇧",
        )
        return
    _file_summary(
        filename=source_name(unified_file),
        size=int(getattr(unified_file, "size", 0)),
        frame=unified,
        sheet=unified_sheet,
    )
    hazards: pd.DataFrame
    requirements: pd.DataFrame
    json_collections: dict[str, pd.DataFrame] = {}
    if unified_file is not None and source_name(unified_file).lower().endswith(".json"):
        try:
            json_collections = read_json_collections(unified_file)
        except ValueError as exc:
            st.error(str(exc))
            return
    if len(json_collections) >= 2:
        structure = pd.DataFrame(
            [
                {
                    "JSON path": path,
                    "Rows": len(frame),
                    "Columns": len(frame.columns),
                    "Sample fields": ", ".join(map(str, frame.columns[:6])),
                }
                for path, frame in json_collections.items()
            ]
        )
        st.markdown("#### Detected JSON structure")
        st.dataframe(structure, width="stretch", hide_index=True)
        paths = list(json_collections)

        def mapping_score(path: str, kind: str) -> int:
            mapping = suggest_column_mapping(json_collections[path], kind)
            return int(
                (
                    mapping["mapping_status"].eq("Matched").astype(int)
                    * (1 + 4 * mapping["required"].astype(int))
                ).sum()
            )

        hazard_default = max(paths, key=lambda path: mapping_score(path, "hazards"))
        requirement_candidates = [path for path in paths if path != hazard_default] or paths
        requirement_default = max(
            requirement_candidates,
            key=lambda path: mapping_score(path, "requirements"),
        )
        collection_columns = st.columns(2)
        with collection_columns[0]:
            hazard_path = st.selectbox(
                "Hazard record collection",
                paths,
                index=paths.index(hazard_default),
            )
        with collection_columns[1]:
            requirement_path = st.selectbox(
                "Requirement record collection",
                paths,
                index=paths.index(requirement_default),
            )
        if hazard_path == requirement_path:
            st.error(
                "Choose two different JSON record collections for hazards and requirements, "
                "or provide one mixed collection with a record_type field."
            )
            return
        hazards = json_collections[hazard_path]
        requirements = json_collections[requirement_path]
    else:
        try:
            hazards, requirements = split_unified_file(unified)
        except ValueError as exc:
            st.error(str(exc))
            return
    _import_review(
        hazards,
        requirements,
        hazard_filename=source_name(unified_file),
        requirements_filename=source_name(unified_file),
        total_size=int(getattr(unified_file, "size", 0)),
        selected_sheet=unified_sheet,
    )


def render_data_validation(context: AssessmentContext) -> None:
    """Render grouped validation metrics, issues, search, and download."""
    render_page_header(
        "Data Validation",
        "Review schema, scoring, completeness, duplicate, and evidence diagnostics.",
        icon="✓",
        status="Passed" if context.ready_for_analysis else "Action required",
    )
    issues = validation_issue_table(
        context.hazard_result,
        context.requirement_result,
    )
    errors = len(context.validation_errors)
    warnings = len(context.validation_warnings)
    missing_critical = int(
        (
            context.requirements.get(
                "critical_control",
                pd.Series(False, index=context.requirements.index),
            ).fillna(False)
            & context.requirements.get(
                "evidence_missing",
                pd.Series(False, index=context.requirements.index),
            ).fillna(False)
        ).sum()
    )
    invalid_scores = len(
        set(context.hazard_result.invalid_rows)
        | set(context.requirement_result.invalid_rows)
    )
    duplicates = len(context.hazard_result.duplicate_ids) + len(
        context.requirement_result.duplicate_ids
    )
    metrics = [
        ("Errors", errors, "Blocking issues"),
        ("Warnings", warnings, "Review recommended"),
        ("Information", int(issues["severity"].eq("Information").sum()), "Validation notes"),
        ("Missing Critical Fields", missing_critical, "Critical evidence"),
        ("Invalid Scores", invalid_scores, "Out-of-range or missing"),
        ("Duplicate Rows", duplicates, "Duplicate identifiers"),
    ]
    render_metric_grid(metrics, max_columns=3)

    if context.ready_for_analysis:
        st.success("Active data passed blocking validation checks.")
    else:
        st.error(
            "Analysis is paused because required fields or values need correction. "
            "No invalid row is silently used in calculations."
        )
    severity_tab, dataset_tab = st.tabs(["Issues by Severity", "Issues by Dataset"])
    with severity_tab:
        severity = st.multiselect(
            "Severity",
            ["Error", "Warning", "Information"],
            default=["Error", "Warning", "Information"],
        )
        search = st.text_input(
            "Search validation issues",
            placeholder="Search cause, dataset, location, or recommended fix",
        )
        filtered = issues[issues["severity"].isin(severity)]
        if search:
            match = filtered.astype(str).apply(
                lambda column: column.str.contains(search, case=False, na=False)
            )
            filtered = filtered[match.any(axis=1)]
        st.dataframe(
            filtered,
            width="stretch",
            hide_index=True,
            height=420,
        )
    with dataset_tab:
        for dataset in issues["dataset"].drop_duplicates():
            with st.expander(str(dataset), expanded=errors > 0):
                st.dataframe(
                    issues.loc[issues["dataset"].eq(dataset)],
            width="stretch",
                    hide_index=True,
                )
    st.download_button(
        "Download Validation Report (CSV)",
        csv_bytes(issues),
        "MOBRA_Validation_Report.csv",
        "text/csv",
        width="stretch",
    )
    mapping_result, profile_result = _supporting_results(context)
    cross_result = validate_cross_dataset_consistency(
        context.hazards,
        context.requirements,
        mapping_result.data,
        profile_result.data,
    )
    structured = findings_frame(
        [
            *mapping_result.findings,
            *profile_result.findings,
            *cross_result.findings,
        ]
    )
    render_section_header(
        "Structured Cross-Dataset Findings",
        icon="↔",
        help_text=(
            "Checks identifiers, relationship coverage, governance-profile references, "
            "and possible duplicates across active datasets."
        ),
    )
    if structured.empty:
        st.success("No structured cross-dataset findings were detected.")
    else:
        structured_severity = st.multiselect(
            "Structured finding severity",
            ["Error", "Warning", "Information"],
            default=["Error", "Warning", "Information"],
            key="structured_validation_severity",
        )
        structured_filtered = structured[
            structured["severity"].isin(structured_severity)
        ]
        st.dataframe(
            structured_filtered,
            width="stretch",
            hide_index=True,
            height=440,
        )
        st.download_button(
            "Download Structured Findings",
            csv_bytes(structured),
            "MOBRA_Structured_Validation_Findings.csv",
            "text/csv",
            width="stretch",
        )


def render_requirements_assessment(context: AssessmentContext) -> None:
    """Render readiness requirements with metrics, filters, and focused detail."""
    render_page_header(
        "Requirements Assessment",
        "Assess operational requirements, Critical Controls, evidence, and corrective actions.",
        icon="▤",
        status=context.meta.get("source_label"),
    )
    if not _analysis_gate(context):
        return
    requirements = context.requirements.copy()
    assessed_mask = requirements["observed_score"].notna()
    evidence_complete = ~requirements.get(
        "evidence_missing",
        pd.Series(False, index=requirements.index),
    ).fillna(False)
    failed = failed_critical_controls(requirements)
    average_score = requirements["observed_score"].mean()
    evidence_rate = 100 * evidence_complete.mean() if len(requirements) else 0
    metrics = [
        ("Total Requirements", len(requirements), "Active requirement records"),
        ("Requirements Assessed", int(assessed_mask.sum()), "Observed score available"),
        ("Not Assessed", int((~assessed_mask).sum()), "Score still required"),
        ("Failed Critical Controls", len(failed), "Deployment blockers"),
        ("Average Score", f"{average_score:.2f}/5" if pd.notna(average_score) else "N/A", "Unweighted item average"),
        ("Evidence Completion", f"{evidence_rate:.1f}%", "Objective Evidence present"),
    ]
    render_metric_grid(metrics, max_columns=3)

    render_section_header("Filter Requirements", icon="⌕")
    requirements["assessment_status"] = assessed_mask.map(
        {True: "Assessed", False: "Not Assessed"}
    )
    requirements["evidence_status"] = evidence_complete.map(
        {True: "Evidence Complete", False: "Evidence Missing"}
    )
    filter_columns = st.columns(5)
    with filter_columns[0]:
        domains = st.multiselect(
            "Domain",
            sorted(requirements["domain"].astype(str).unique()),
            key="requirements_domain_filter",
        )
    with filter_columns[1]:
        stages = st.multiselect(
            "Lifecycle Stage",
            sorted(requirements["lifecycle_stage"].astype(str).unique()),
            key="requirements_stage_filter",
        )
    with filter_columns[2]:
        critical = st.selectbox(
            "Critical Control",
            ["All", "Critical", "Non-critical"],
            key="requirements_critical_filter",
        )
    with filter_columns[3]:
        statuses = st.multiselect(
            "Assessment Status",
            ["Assessed", "Not Assessed"],
            key="requirements_status_filter",
        )
    with filter_columns[4]:
        evidence_statuses = st.multiselect(
            "Evidence Status",
            ["Evidence Complete", "Evidence Missing"],
            key="requirements_evidence_filter",
        )
    filtered = requirements.copy()
    if domains:
        filtered = filtered[filtered["domain"].astype(str).isin(domains)]
    if stages:
        filtered = filtered[filtered["lifecycle_stage"].astype(str).isin(stages)]
    if critical == "Critical":
        filtered = filtered[filtered["critical_control"].fillna(False)]
    elif critical == "Non-critical":
        filtered = filtered[~filtered["critical_control"].fillna(False)]
    if statuses:
        filtered = filtered[filtered["assessment_status"].isin(statuses)]
    if evidence_statuses:
        filtered = filtered[filtered["evidence_status"].isin(evidence_statuses)]

    render_section_header(f"Requirement Register · {len(filtered)} records", icon="▤")
    columns = [
        "requirement_id",
        "domain",
        "requirement",
        "observed_score",
        "maximum_score",
        "item_readiness_pct",
        "critical_control",
        "compliance_status",
        "evidence_status",
    ]
    st.dataframe(
        filtered[[column for column in columns if column in filtered.columns]],
            width="stretch",
        hide_index=True,
        height=460,
        column_config={
            "item_readiness_pct": st.column_config.ProgressColumn(
                "Item Readiness",
                min_value=0,
                max_value=100,
                format="%.1f%%",
            ),
            "critical_control": st.column_config.CheckboxColumn("Critical Control"),
        },
    )
    if filtered.empty:
        return
    render_section_header("Requirement Detail", icon="→")
    selected_id = st.selectbox(
        "Select a requirement",
        filtered["requirement_id"].astype(str).tolist(),
        format_func=lambda value: (
            f"{value} · "
            + str(
                filtered.loc[
                    filtered["requirement_id"].astype(str).eq(value),
                    "requirement",
                ].iloc[0]
            )[:90]
        ),
    )
    record = filtered.loc[
        filtered["requirement_id"].astype(str).eq(selected_id)
    ].iloc[0]
    with st.expander(f"{selected_id} · Full assessment detail", expanded=True):
        detail_columns = st.columns(2)
        with detail_columns[0]:
            st.markdown(f"**Requirement**  \n{record.get('requirement', '—')}")
            st.markdown(f"**Domain**  \n{record.get('domain', '—')}")
            st.markdown(
                f"**Score**  \n{record.get('observed_score', '—')} / {record.get('maximum_score', '—')}"
            )
            st.markdown(f"**Critical Control**  \n{'Yes' if record.get('critical_control', False) else 'No'}")
        with detail_columns[1]:
            st.markdown(f"**Objective Evidence**  \n{record.get('objective_evidence', '—')}")
            st.markdown(f"**Notes**  \n{record.get('notes', '—')}")
            st.markdown(f"**Corrective Action**  \n{record.get('corrective_action', '—')}")
            st.markdown(
                f"**Responsible / Target**  \n{record.get('responsible_person', '—')} · {record.get('due_date', '—')}"
            )
    _render_mapping_analysis(context)
    _render_critical_control_governance(context)


def render_hazard_register(context: AssessmentContext) -> None:
    """Render the hazard register as a focused table with detailed drill-down."""
    render_page_header(
        "Hazard Register",
        "Review initial and residual risk, controls, ownership, and corrective actions.",
        icon="⚠",
        status=f"{len(context.hazards)} hazards",
    )
    if not _analysis_gate(context):
        return
    hazards = context.hazards.copy()
    render_section_header("Filter and Sort", icon="⌕")
    filter_columns = st.columns(5)
    with filter_columns[0]:
        domains = st.multiselect(
            "Domain",
            sorted(hazards["domain"].astype(str).unique()),
            key="hazard_domain_filter",
        )
    with filter_columns[1]:
        categories = st.multiselect(
            "Risk Category",
            RISK_LEVELS,
            default=RISK_LEVELS,
            key="hazard_risk_filter",
        )
    with filter_columns[2]:
        statuses = st.multiselect(
            "Status",
            sorted(hazards["status"].astype(str).unique()),
            key="hazard_status_filter",
        )
    with filter_columns[3]:
        owners = st.multiselect(
            "Responsible Person",
            sorted(hazards["responsible_person"].astype(str).unique()),
            key="hazard_owner_filter",
        )
    with filter_columns[4]:
        action_status = st.selectbox(
            "Corrective Action",
            ["All", "Defined", "Missing"],
            key="hazard_action_filter",
        )
    filtered = hazards.copy()
    if domains:
        filtered = filtered[filtered["domain"].astype(str).isin(domains)]
    if categories:
        filtered = filtered[filtered["risk_category"].isin(categories)]
    else:
        filtered = filtered.iloc[0:0]
    if statuses:
        filtered = filtered[filtered["status"].astype(str).isin(statuses)]
    if owners:
        filtered = filtered[filtered["responsible_person"].astype(str).isin(owners)]
    action_present = _meaningful(filtered["corrective_action"])
    if action_status == "Defined":
        filtered = filtered[action_present]
    elif action_status == "Missing":
        filtered = filtered[~action_present]
    sort_basis = st.radio(
        "Sort risk",
        ["Highest initial risk first", "Highest residual risk first"],
        horizontal=True,
    )
    sort_column = (
        "residual_risk_score"
        if sort_basis.startswith("Highest residual")
        and filtered.get("residual_risk_score", pd.Series()).notna().any()
        else "risk_score"
    )
    filtered = filtered.sort_values(sort_column, ascending=False)
    render_section_header(f"Risk Register · {len(filtered)} records", icon="▤")
    essential = [
        "hazard_id",
        "hazard",
        "domain",
        "likelihood",
        "consequence",
        "risk_score",
        "risk_category",
        "residual_risk_score",
        "residual_risk_category",
        "status",
        "responsible_person",
    ]
    table = filtered[[column for column in essential if column in filtered.columns]]
    styled = table.style.map(
        _risk_category_style,
        subset=[
            column
            for column in ("risk_category", "residual_risk_category")
            if column in table.columns
        ],
    )
    st.dataframe(
        styled,
            width="stretch",
        hide_index=True,
        height=480,
    )
    if filtered.empty:
        render_empty_state("No hazards match the selected filters", "Adjust the filters to display hazard records.")
        return
    render_section_header("Hazard Detail", icon="→")
    selected_id = st.selectbox(
        "Select a hazard",
        filtered["hazard_id"].astype(str).tolist(),
        format_func=lambda value: (
            f"{value} · "
            + str(
                filtered.loc[
                    filtered["hazard_id"].astype(str).eq(value),
                    "hazard",
                ].iloc[0]
            )[:90]
        ),
    )
    record = filtered.loc[
        filtered["hazard_id"].astype(str).eq(selected_id)
    ].iloc[0]
    with st.expander(f"{selected_id} · Full hazard detail", expanded=True):
        left, right = st.columns(2)
        with left:
            st.markdown(f"**Hazard**  \n{record.get('hazard', '—')}")
            st.markdown(f"**Description / Cause**  \n{record.get('cause', '—')}")
            st.markdown(f"**Activity / Domain**  \n{record.get('activity', '—')} · {record.get('domain', '—')}")
            st.markdown(f"**Existing Controls**  \n{record.get('existing_controls', '—')}")
            st.markdown(f"**Objective Evidence**  \n{record.get('objective_evidence', '—')}")
        with right:
            st.markdown(
                f"**Initial Risk**  \nL {record.get('likelihood', '—')} × C {record.get('consequence', '—')} = {record.get('risk_score', '—')} ({record.get('risk_category', '—')})"
            )
            st.markdown(
                f"**Residual Risk**  \nL {record.get('residual_likelihood', '—')} × C {record.get('residual_consequence', '—')} = {record.get('residual_risk_score', '—')} ({record.get('residual_risk_category', '—')})"
            )
            st.markdown(f"**Corrective Action**  \n{record.get('corrective_action', '—')}")
            st.markdown(
                f"**Responsible / Target**  \n{record.get('responsible_person', '—')} · {record.get('due_date', '—')}"
            )
            st.markdown(f"**Status**  \n{record.get('status', '—')}")


def render_risk_analysis(context: AssessmentContext) -> None:
    """Render ordered risk analytics and the validated 5 × 5 matrix."""
    render_page_header(
        "Risk Analysis",
        "Analyze category distribution, control effect, operational concentration, and matrix placement.",
        icon="▦",
        status=context.meta.get("source_label"),
    )
    if not _analysis_gate(context):
        return
    hazards = context.hazards
    risk_counts = hazards["risk_category"].value_counts()
    risk_basis = decision_risk_column(hazards)
    residual_extreme = int(
        hazards.get(risk_basis, pd.Series(dtype="string")).eq("Extreme").sum()
    )
    average = hazards["risk_score"].mean()
    metrics = [
        ("Total Hazards", len(hazards), "Valid risk records"),
        ("Low", int(risk_counts.get("Low", 0)), "Scores 1–4"),
        ("Moderate", int(risk_counts.get("Moderate", 0)), "Scores 5–9"),
        ("High", int(risk_counts.get("High", 0)), "Scores 10–16"),
        ("Extreme", int(risk_counts.get("Extreme", 0)), "Scores 17–25"),
        ("Residual Extreme", residual_extreme, f"Decision basis: {risk_basis.replace('_', ' ')}"),
        ("Average Risk Score", f"{average:.1f}" if pd.notna(average) else "N/A", "Initial calculated score"),
    ]
    render_metric_grid(
        [
            (
                metric[0],
                metric[1],
                metric[2],
                RISK_COLORS.get(
                    metric[0].replace("Residual ", ""),
                    PRIMARY_COLOR,
                ),
            )
            for metric in metrics
        ]
    )
    render_section_header("Risk Category Distribution", icon="▥")
    st.plotly_chart(
        risk_counts_figure(hazards),
            width="stretch",
        key="risk_distribution",
    )
    st.caption("The distribution uses the approved MOBRA risk thresholds and calculated initial Risk Scores.")

    render_section_header("Initial versus Residual Risk", icon="↘")
    if (
        "residual_risk_category" in hazards
        and hazards["residual_risk_category"].isin(RISK_LEVELS).any()
    ):
        st.plotly_chart(
            initial_residual_figure(hazards),
            width="stretch",
            key="initial_residual_risk",
        )
        st.caption("Compare the number of hazards in each category before and after documented controls.")
    else:
        render_empty_state(
            "Residual risk data are not available",
            "Add Residual Likelihood and Residual Consequence to compare control effectiveness.",
            icon="↘",
        )

    render_section_header("Hazards by Domain", icon="▤")
    if _meaningful(hazards["domain"]).any():
        st.plotly_chart(
            hazards_by_domain_figure(hazards),
            width="stretch",
            key="hazards_by_domain",
        )
        st.caption("Operational domains with larger hazard volumes may require concentrated control review.")

    render_section_header("Top High-Risk Hazards", icon="!")
    st.plotly_chart(
        top_hazards_figure(hazards),
            width="stretch",
        key="top_high_risk_hazards",
    )
    st.caption("Ranking is based on calculated initial Risk Score; inspect residual values before deciding control adequacy.")

    render_section_header(
        "Risk Heatmap",
        icon="▦",
        help_text="X-axis is Consequence; Y-axis is Likelihood. Each cell shows its actual hazard count.",
    )
    expected = valid_hazard_count(hazards)
    try:
        assert_heatmap_total(hazards)
    except AssertionError as exc:
        render_validation_alert(
            "The heatmap was not displayed because its record count could not be verified.",
            severity="error",
            details=str(exc),
        )
    else:
        actual = heatmap_total(hazards)
        if actual != expected:
            st.error(
                f"Heatmap validation failed: cells contain {actual} records but {expected} valid hazards were expected."
            )
        else:
            st.plotly_chart(
                heatmap_figure(hazards),
            width="stretch",
                key="risk_heatmap",
            )
            st.markdown(
                "**Legend:** "
                "🟩 Green = Low (1–4) · "
                "🟨 Yellow = Moderate (5–9) · "
                "🟧 Orange = High (10–16) · "
                "🟥 Red = Extreme (17–25)"
            )
            st.caption(
                "Cell color represents the MOBRA risk category based on Likelihood × "
                "Consequence. The number inside each cell represents the count of hazards "
                "assigned to that combination. "
                f"Verified total: {count_phrase(actual, 'hazard')}."
            )
    _render_risk_acceptance(context)


def render_readiness_dashboard(context: AssessmentContext) -> None:
    """Render Overall BRI, domain readiness, and action-oriented priorities."""
    render_page_header(
        "Readiness Dashboard",
        "Evaluate weighted operational readiness without bypassing risk or Critical Control rules.",
        icon="◔",
        status=f"Overall BRI: {_format_bri(context.bri)}",
    )
    if not _analysis_gate(context):
        return
    left, right = st.columns([1.15, 1.85])
    with left:
        st.plotly_chart(
            bri_progress_figure(context.bri),
            width="stretch",
            key="readiness_bri",
        )
        st.caption(
            "BRI (%) = Sum of Observed Requirement Scores ÷ Sum of Maximum Requirement Scores × 100."
        )
    with right:
        st.info(
            "A high Overall BRI is not automatic deployment authorization. "
            "Critical Controls, Extreme residual risk, critical data completeness, "
            "and Objective Evidence govern the final Deployment Decision."
        )
        assessed = int(context.requirements["observed_score"].notna().sum())
        scored_max = context.requirements["maximum_score"].sum()
        st.markdown(
            f"**Scoring coverage:** {assessed}/{len(context.requirements)} requirements  \n"
            f"**Maximum points represented:** {scored_max:.0f}  \n"
            f"**Critical Controls failed:** {len(failed_critical_controls(context.requirements))}"
        )

    render_section_header("Readiness by Domain", icon="▤")
    if context.domains.empty:
        render_empty_state(
            "Domain readiness unavailable",
            "Valid domain, observed-score, and maximum-score fields are required.",
        )
        return
    st.plotly_chart(
        domain_figure(context.domains),
            width="stretch",
        key="readiness_domains",
    )
    st.caption(
        "Domain values use the same weighted formula as Overall BRI and are sorted from least to most ready."
    )

    render_section_header("Least-Ready Domains and Recommended Focus", icon="↻")
    priority_domains = context.domains.nsmallest(5, "readiness_pct")
    for row in priority_domains.itertuples():
        domain_requirements = context.requirements[
            context.requirements["domain"].astype(str).eq(str(row.domain))
        ]
        missing_evidence = int(
            domain_requirements.get(
                "evidence_missing",
                pd.Series(False, index=domain_requirements.index),
            )
            .fillna(False)
            .sum()
        )
        below = int(
            (
                domain_requirements["observed_score"]
                < domain_requirements["maximum_score"]
            ).sum()
        )
        recommendation = f"Close {count_phrase(below, 'scored gap')}"
        if missing_evidence:
            recommendation += (
                " and complete Objective Evidence for "
                f"{count_phrase(missing_evidence, 'record')}"
            )
        recommendation += " before reassessment."
        st.markdown(
            f"""
            <div class="mobra-metric-card" style="min-height:auto;--metric-accent:{PRIMARY_COLOR}">
              <div class="mobra-metric-label">{escape(str(row.domain))}</div>
              <div class="mobra-metric-value" style="font-size:1.35rem">{row.readiness_pct:.1f}%</div>
              <div class="mobra-metric-note">{escape(recommendation)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _blocking_issues(context: AssessmentContext) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for message in context.validation_errors:
        records.append(
            {
                "Blocking Issue": message,
                "Source": "Data Validation",
                "Responsible Person": "Data owner",
                "Target Date": "Before reassessment",
            }
        )
    failed = failed_critical_controls(context.requirements)
    for _, row in failed.iterrows():
        records.append(
            {
                "Blocking Issue": f"Critical Control not satisfied: {row.get('requirement', row.get('requirement_id', 'Requirement'))}",
                "Source": row.get("requirement_id", "Requirement"),
                "Responsible Person": row.get("responsible_person", "Not provided"),
                "Target Date": row.get("due_date", "Not provided"),
            }
        )
    risk_column = decision_risk_column(context.hazards)
    extreme = context.hazards[
        context.hazards.get(risk_column, pd.Series(dtype="string")).eq("Extreme")
    ]
    for _, row in extreme.iterrows():
        records.append(
            {
                "Blocking Issue": f"Extreme risk: {row.get('hazard', row.get('hazard_id', 'Hazard'))}",
                "Source": row.get("hazard_id", "Hazard"),
                "Responsible Person": row.get("responsible_person", "Not provided"),
                "Target Date": row.get("due_date", "Not provided"),
            }
        )
    return pd.DataFrame(records)


def render_deployment_decision(context: AssessmentContext) -> None:
    """Render the final decision, evidence, blockers, and reassessment conditions."""
    render_page_header(
        "Deployment Decision",
        "Apply non-bypassable MOBRA safety rules and document the evidence for action.",
        icon="◆",
        status=context.meta.get("source_label"),
    )
    render_decision_banner(context.decision, context.reasons)
    failed_count = len(failed_critical_controls(context.requirements))
    if failed_count:
        st.error(
            f"The active dataset contains {count_phrase(failed_count, 'failed critical control')}. "
            "DO NOT DEPLOY remains mandatory regardless of the Overall BRI."
        )

    primary, evidence = st.columns([1.1, 1.9])
    with primary:
        render_section_header("Primary Reasons", icon="→")
        for reason in context.reasons:
            st.markdown(f"- {reason}")
        st.markdown(f"**Overall BRI:** {_format_bri(context.bri)}")
        st.markdown(
            f"**Risk basis:** {decision_risk_column(context.hazards).replace('_', ' ').title()}"
        )
    with evidence:
        render_section_header("Supporting Evidence", icon="✓")
        risk_column = decision_risk_column(context.hazards)
        render_metric_grid(
            [
                (
                    "Failed Critical Controls",
                    failed_count,
                    "Non-bypassable override",
                ),
                (
                    "Extreme Risks",
                    int(
                    context.hazards.get(
                        risk_column,
                        pd.Series(dtype="string"),
                    )
                    .eq("Extreme")
                    .sum()
                ),
                    "Decision risk basis",
                ),
                (
                    "Validation Errors",
                    len(context.validation_errors),
                    "Material data completeness",
                ),
            ],
            max_columns=3,
        )

    blockers = _blocking_issues(context)
    render_section_header("Required Actions", icon="↻")
    st.markdown("#### Blocking issues")
    if blockers.empty:
        st.success("No blocking issue is present in the active validated dataset.")
    else:
        st.dataframe(
            blockers,
            width="stretch",
            hide_index=True,
            height=360,
        )

    st.markdown("#### Priority corrective actions")
    priorities = context.actions[
        context.actions["priority"].astype(str).isin(["Critical", "High"])
    ] if not context.actions.empty else context.actions
    if priorities.empty:
        st.info("No Critical or High corrective-action record is available.")
    else:
        st.dataframe(
            priorities[
                [
                    "action",
                    "related_item",
                    "priority",
                    "responsible_person",
                    "target_date",
                    "status",
                ]
            ],
            width="stretch",
            hide_index=True,
            height=380,
        )

    render_section_header("Decision Logic", icon="✓")
    st.caption("Conditions required before the deployment decision can be reassessed.")
    conditions = [
        "All Critical Controls are satisfied and supported by required Objective Evidence.",
        "No Extreme residual risk remains.",
        "Material validation errors are resolved and critical data are complete.",
        "Required corrective actions have responsible persons, target dates, and completion evidence.",
        "Overall BRI and domain readiness are recalculated from the corrected records.",
    ]
    for condition in conditions:
        st.checkbox(condition, value=False, disabled=True)


def render_corrective_actions(context: AssessmentContext) -> None:
    """Render corrective-action status, priorities, dates, and completion evidence."""
    render_page_header(
        "Corrective Actions",
        "Track risk and readiness actions through assignment, target date, status, and evidence.",
        icon="↻",
        status=f"{len(context.actions)} actions",
    )
    if not _analysis_gate(context):
        return
    actions = context.actions.copy()
    if actions.empty:
        render_empty_state(
            "No corrective actions available",
            "Add Corrective Action fields to hazard or requirement records.",
            icon="↻",
        )
        return
    normalized_status = actions["status"].astype("string").str.lower()
    completed_mask = normalized_status.isin(
        ["completed", "closed", "resolved", "compliant"]
    )
    open_mask = ~completed_mask
    overdue = actions["overdue"].fillna(False).astype(bool)
    high_priority = actions["priority"].astype(str).isin(["Critical", "High"])
    values = [
        ("Open Actions", int(open_mask.sum()), "Not completed or closed"),
        ("Completed Actions", int(completed_mask.sum()), "Completion status recorded"),
        ("Overdue Actions", int(overdue.sum()), "Target date has passed"),
        ("High-Priority Actions", int(high_priority.sum()), "Critical or High"),
    ]
    render_metric_grid(values)
    filter_columns = st.columns(4)
    with filter_columns[0]:
        priority = st.multiselect(
            "Priority",
            ["Critical", "High", "Medium", "Low"],
            default=["Critical", "High", "Medium", "Low"],
        )
    with filter_columns[1]:
        owners = st.multiselect(
            "Responsible Person",
            sorted(actions["responsible_person"].astype(str).unique()),
        )
    with filter_columns[2]:
        statuses = st.multiselect(
            "Status",
            sorted(actions["status"].astype(str).unique()),
        )
    with filter_columns[3]:
        overdue_only = st.checkbox("Overdue only")
    filtered = actions[actions["priority"].astype(str).isin(priority)]
    if owners:
        filtered = filtered[filtered["responsible_person"].astype(str).isin(owners)]
    if statuses:
        filtered = filtered[filtered["status"].astype(str).isin(statuses)]
    if overdue_only:
        filtered = filtered[filtered["overdue"].fillna(False)]
    st.dataframe(
        filtered,
            width="stretch",
        hide_index=True,
        height=470,
        column_config={
            "overdue": st.column_config.CheckboxColumn("Overdue"),
            "target_date": st.column_config.DateColumn("Target Date", format="YYYY-MM-DD"),
        },
    )
    date_count = pd.to_datetime(actions["target_date"], errors="coerce").notna().sum()
    if date_count >= 3:
        render_section_header("Action Status Overview", icon="▥")
        st.plotly_chart(
            action_status_figure(actions),
            width="stretch",
            key="action_status_distribution",
        )
        st.caption(
            f"{date_count} action records include usable dates; use the table to review individual deadlines."
        )


def render_reports_export(context: AssessmentContext) -> None:
    """Render branded report previews and all supported export formats."""
    render_page_header(
        "Reports and Export",
        "Generate institutionally branded analysis outputs for review, printing, and audit.",
        icon="⇩",
        status=context.meta.get("source_label"),
    )
    if not _analysis_gate(context):
        return
    issues = validation_issue_table(
        context.hazard_result,
        context.requirement_result,
    )
    with st.spinner("Preparing the branded MOBRA report and export packages…"):
        payload = summary_payload(
            context.hazards,
            context.requirements,
            context.bri,
            context.decision,
            context.reasons,
            data_source=context.meta.get("source_label", "Assessment Data"),
            hazard_filename=context.meta.get("hazard_filename", "hazards"),
            requirements_filename=context.meta.get(
                "requirements_filename",
                "requirements",
            ),
            validation_messages=[
                *context.validation_errors,
                *context.validation_warnings,
            ],
        )
        html = make_html_report(
            context.hazards,
            context.requirements,
            context.bri,
            context.decision,
            context.reasons,
            hazard_filename=context.meta.get("hazard_filename", "hazards"),
            requirements_filename=context.meta.get(
                "requirements_filename",
                "requirements",
            ),
            validation_messages=[
                *context.validation_errors,
                *context.validation_warnings,
            ],
            data_source=context.meta.get("source_label", "Assessment Data"),
        )
        workbook = make_excel_workbook(
            context.hazards,
            context.requirements,
            context.bri,
            context.decision,
            context.reasons,
            data_source=context.meta.get("source_label", "Assessment Data"),
            hazard_filename=context.meta.get("hazard_filename", "hazards"),
            requirements_filename=context.meta.get(
                "requirements_filename",
                "requirements",
            ),
            validation_issues=issues,
        )
    report_metrics = [
        ("Data Status", context.meta.get("source_label", "—"), "Clearly labelled in every export"),
        ("Decision", context.decision, "Non-bypassable rule output"),
        ("Overall BRI", _format_bri(context.bri), "Weighted readiness"),
        ("Generated", datetime.now().strftime("%Y-%m-%d %H:%M"), "Local system time"),
    ]
    render_metric_grid(report_metrics)

    render_section_header("Export Packages", icon="⇩")
    row_one = st.columns(4)
    downloads = [
        (
            "HTML Report",
            html.encode("utf-8"),
            "MOBRA_Assessment_Report.html",
            "text/html",
        ),
        (
            "Excel Workbook",
            workbook,
            "MOBRA_Assessment_Export.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        (
            "Summary JSON",
            json_bytes(payload),
            "MOBRA_Assessment_Summary.json",
            "application/json",
        ),
        (
            "Validation CSV",
            csv_bytes(issues),
            "MOBRA_Validation_Report.csv",
            "text/csv",
        ),
    ]
    for column, download in zip(row_one, downloads):
        with column:
            st.download_button(
                f"Download {download[0]}",
                download[1],
                download[2],
                download[3],
            width="stretch",
            )
    row_two = st.columns(4)
    data_downloads = [
        (
            "Hazards CSV",
            csv_bytes(context.hazards),
            "MOBRA_Hazard_Register.csv",
            "text/csv",
        ),
        (
            "Requirements CSV",
            csv_bytes(context.requirements),
            "MOBRA_Requirements.csv",
            "text/csv",
        ),
        (
            "Corrective Actions CSV",
            csv_bytes(context.actions),
            "MOBRA_Corrective_Actions.csv",
            "text/csv",
        ),
        (
            "Templates",
            (PROJECT_ROOT / "sample_data" / "hazards_template.csv").read_bytes(),
            "MOBRA_Hazards_Template.csv",
            "text/csv",
        ),
    ]
    for column, download in zip(row_two, data_downloads):
        with column:
            st.download_button(
                f"Download {download[0]}",
                download[1],
                download[2],
                download[3],
            width="stretch",
            )
    st.caption(
        "The Excel workbook includes Executive Summary, Domain Summary, Requirements, "
        "Hazard Register, Risk Matrix, Critical Controls, Corrective Actions, and Validation Issues worksheets."
    )
    render_section_header("Advanced Analysis Exports", icon="↔")
    mapping_result, profile_result = _supporting_results(context)
    governance = assess_critical_controls(
        context.requirements,
        profile_result.data,
    )
    accepted_hazards = apply_risk_acceptance(
        context.hazards,
        RiskAcceptancePolicy(),
    )
    advanced_downloads = [
        (
            "Mapping CSV",
            csv_bytes(mapping_result.data),
            "MOBRA_Requirement_Hazard_Mapping.csv",
        ),
        (
            "Mapping Coverage CSV",
            csv_bytes(
                mapping_coverage_table(
                    mapping_result.data,
                    context.requirements,
                    context.hazards,
                )
            ),
            "MOBRA_Mapping_Coverage.csv",
        ),
        (
            "Governance Assessment CSV",
            csv_bytes(governance.data),
            "MOBRA_Critical_Control_Assessment.csv",
        ),
        (
            "Risk Acceptance CSV",
            csv_bytes(accepted_hazards),
            "MOBRA_Risk_Acceptance.csv",
        ),
    ]
    for column, download in zip(st.columns(4), advanced_downloads):
        with column:
            st.download_button(
                f"Download {download[0]}",
                download[1],
                download[2],
                "text/csv",
                width="stretch",
            )

    render_section_header("Field and Import Tools", icon="⇩")
    field_downloads = [
        (
            "Field Assessment Package",
            build_field_assessment_package(
                context.requirements,
                context.hazards,
            ),
            "MOBRA_Field_Assessment_Package.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        (
            "ORL Workbook",
            build_orl_assessment_workbook(context.requirements),
            "MOBRA_Printable_ORL_Assessment_Form.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        (
            "Hazard Workbook",
            build_hazard_register_workbook(context.hazards),
            "MOBRA_Printable_Hazard_Register.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        (
            "Requirements Template",
            build_requirements_import_template(),
            "MOBRA_Requirements_Import_Template.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        (
            "Hazard Template",
            build_hazard_import_template(),
            "MOBRA_Hazard_Import_Template.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        (
            "Printable ORL PDF",
            build_orl_pdf(context.requirements),
            "MOBRA_Printable_ORL_Assessment_Form.pdf",
            "application/pdf",
        ),
        (
            "Printable Hazard PDF",
            build_hazard_pdf(context.hazards),
            "MOBRA_Printable_Hazard_Register.pdf",
            "application/pdf",
        ),
        (
            "Template Catalogue",
            template_catalogue_csv(),
            "MOBRA_Template_Catalogue.csv",
            "text/csv",
        ),
    ]
    field_columns = st.columns(4)
    for index, download in enumerate(field_downloads):
        with field_columns[index % 4]:
            st.download_button(
                f"Download {download[0]}",
                download[1],
                download[2],
                download[3],
                width="stretch",
                key=f"field_download_{index}",
            )

    render_section_header("Normative Resource Catalogue", icon="□")
    try:
        resources = load_normative_resources()
        resource_downloads = [
            (
                "Resource Catalogue CSV",
                catalogue_csv_bytes(resources),
                "MOBRA_Normative_Resources.csv",
                "text/csv",
            ),
            (
                "Resource Catalogue XLSX",
                catalogue_xlsx_bytes(resources),
                "MOBRA_Normative_Resources.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        ]
        for column, download in zip(st.columns(2), resource_downloads):
            with column:
                st.download_button(
                    f"Download {download[0]}",
                    download[1],
                    download[2],
                    download[3],
                    width="stretch",
                )
    except ValueError as exc:
        st.warning(f"Resource catalogue unavailable: {exc}")
    render_section_header("Derived Assessment Backup", icon="⇩")
    backup = build_backup_zip(
        {
            "MOBRA_Assessment_Report.html": html.encode("utf-8"),
            "MOBRA_Assessment_Export.xlsx": workbook,
            "MOBRA_Assessment_Summary.json": json_bytes(payload),
            "MOBRA_Hazard_Register.csv": csv_bytes(context.hazards),
            "MOBRA_Requirements.csv": csv_bytes(context.requirements),
            "MOBRA_Validation_Report.csv": csv_bytes(issues),
        }
    )
    st.download_button(
        "Download Derived Assessment Backup (ZIP)",
        backup,
        "MOBRA_Derived_Assessment_Backup.zip",
        "application/zip",
        width="stretch",
    )
    st.caption(
        "The backup contains selected derived outputs and SHA-256 checksums. "
        "Original uploaded files and local secrets are excluded."
    )
    render_section_header("HTML Report Preview", icon="□")
    st.components.v1.html(html, height=780, scrolling=True)


def render_mission_map(context: AssessmentContext) -> None:
    """Render the synthetic deployment workflow as an interactive map."""
    render_page_header(
        "Mission Map",
        "Interactive, synthetic mission gates linked to the active MOBRA assessment.",
        icon="⌖",
        status="Illustrative workflow",
    )
    st.warning(
        "This map is a synthetic workflow visualization. Coordinates and routes "
        "are illustrative only and do not represent a real laboratory, incident, "
        "deployment site, or operational movement."
    )
    failed_count = len(failed_critical_controls(context.requirements))
    stages = synthetic_mission_stages(
        context.decision,
        context.bri,
        failed_count,
        len(context.hazards),
    )
    render_metric_grid(
        [
            ("Workflow Stages", len(stages), "Synthetic decision gates", PRIMARY_COLOR),
            ("Overall BRI", _format_bri(context.bri), "Weighted readiness", PRIMARY_COLOR),
            (
                "Failed Critical Controls",
                failed_count,
                "Non-bypassable blockers",
                DANGER_COLOR,
            ),
            (
                "Deployment Decision",
                context.decision,
                "Canonical MOBRA rule output",
                DECISION_COLORS.get(context.decision, PRIMARY_COLOR),
            ),
        ]
    )
    render_decision_banner(context.decision, context.reasons)
    render_section_header(
        "Interactive Mission Workflow",
        icon="⌖",
        help_text="Hover over a numbered gate for status, progress, and active-assessment context.",
    )
    try:
        st.pydeck_chart(
            mission_map_deck(stages),
            width="stretch",
            height=560,
            key="mobra_mission_workflow_map",
        )
    except (ValueError, TypeError) as exc:
        render_empty_state(
            "Mission workflow unavailable",
            f"The synthetic workflow could not be rendered: {exc}",
            icon="⌖",
        )
    legend_items = []
    for status in stages["status"].drop_duplicates():
        red, green, blue, _ = STATUS_COLORS[str(status)]
        legend_items.append(
            '<span class="mobra-map-legend-item">'
            f'<i style="background:rgb({red},{green},{blue})"></i>{escape(str(status))}'
            "</span>"
        )
    st.markdown(
        '<div class="mobra-map-legend" aria-label="Mission map status legend">'
        + "".join(legend_items)
        + "</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Map status is derived only from the existing MOBRA Deployment Decision. "
        "It does not create a new scientific score or override the decision engine."
    )
    render_section_header("Gate Detail", icon="□")
    st.dataframe(
        stages[
            [
                "stage_id",
                "stage",
                "status",
                "progress_pct",
                "description",
            ]
        ],
        width="stretch",
        hide_index=True,
        column_config={
            "stage_id": st.column_config.TextColumn("Gate"),
            "stage": st.column_config.TextColumn("Workflow Stage"),
            "status": st.column_config.TextColumn("Status"),
            "progress_pct": st.column_config.ProgressColumn(
                "Progress",
                min_value=0,
                max_value=100,
                format="%d%%",
            ),
            "description": st.column_config.TextColumn("Interpretation"),
        },
    )


def render_methodology(context: AssessmentContext) -> None:
    """Explain fixed formulas, terms, and deployment rules."""
    render_page_header(
        "Methodology",
        "Transparent calculation rules and interpretation boundaries for MOBRA.",
        icon="∑",
        status="Fixed scientific rules",
    )
    render_section_header("Biosecurity Readiness Index (BRI)", icon="◔")
    st.latex(
        r"\mathrm{BRI}(\%) = "
        r"\frac{\sum \mathrm{Observed\ Requirement\ Scores}}"
        r"{\sum \mathrm{Maximum\ Requirement\ Scores}} \times 100"
    )
    st.info(
        "Only valid records contribute to the denominator. A zero denominator returns N/A. "
        "BRI does not override Critical Controls or residual risk."
    )
    render_section_header("Risk Matrix", icon="▦")
    st.latex(r"\mathrm{Risk\ Score} = \mathrm{Likelihood} \times \mathrm{Consequence}")
    render_metric_grid(
        [
            (
                category,
                RISK_RANGES[category],
                f"{category} risk",
                RISK_COLORS[category],
            )
            for category in RISK_LEVELS
        ]
    )
    st.markdown(
        "**Matrix convention:** X-axis = Consequence (1–5); Y-axis = Likelihood (1–5). "
        "Every heatmap cell displays the actual number of valid hazards assigned to that combination."
    )
    render_section_header("Deployment Decision Rules", icon="◆")
    st.error(
        "**DO NOT DEPLOY** when a Critical Control is not satisfied, an Extreme residual risk exists, "
        "critical data are materially incomplete, a mission-critical requirement failed, "
        "or required Critical Control evidence is missing."
    )
    st.warning(
        "**CONDITIONAL DEPLOYMENT** when Critical Controls are satisfied and no Extreme residual risk exists, "
        "but manageable High risks or readiness improvements remain with documented actions."
    )
    st.success(
        f"**{DECISION_READY}** only when Critical Controls are satisfied, no Extreme residual risk exists, "
        "residual risk is acceptable, data and evidence are complete, and core readiness is met."
    )
    render_section_header("Technical Terms", icon="ⓘ")
    terms = {
        "Residual Risk": "Risk remaining after existing controls are considered.",
        "Critical Control": "A mission-essential control whose failure can block deployment regardless of BRI.",
        "Objective Evidence": "Verifiable documentation or observation supporting an assessment score.",
        "Technical Verification": "Testing that software calculations and workflows operate as specified; it is not scientific or regulatory validation.",
    }
    for term, definition in terms.items():
        with st.expander(term):
            st.write(definition)
    render_section_header("Contextual Help", icon="?")
    st.caption(
        "Concise explanations preserved from the original MOBRA workflow."
    )
    help_columns = st.columns(2)
    for index, topic in enumerate(help_topics()):
        with help_columns[index % 2]:
            render_help(topic, st)


def render_research_references(context: AssessmentContext) -> None:
    """Expose the manuscript, normative references, and supporting literature."""
    manuscript = manuscript_metadata()
    try:
        resources = load_normative_resources()
    except ValueError as exc:
        resources = []
        st.warning(f"Normative resource catalogue unavailable: {exc}")
    try:
        literature = load_supporting_literature()
    except (ValueError, OSError) as exc:
        literature = []
        st.warning(f"Supporting literature unavailable: {exc}")

    render_page_header(
        "Research and References",
        "MOBRA manuscript access, priority normative sources, and supporting scientific literature.",
        icon="□",
        status="Research transparency",
    )
    render_metric_grid(
        [
            (
                "Manuscript",
                "Available" if manuscript["manuscript_download_enabled"] else "Unavailable",
                manuscript["manuscript_filename"],
                PRIMARY_COLOR,
            ),
            (
                "Normative Sources",
                len(resources),
                "Official-page links and citations",
                PRIMARY_COLOR,
            ),
            (
                "Supporting Studies",
                len(literature),
                "Scientific literature catalogue",
                PRIMARY_COLOR,
            ),
            (
                "Current Assessment",
                context.decision,
                f"BRI {_format_bri(context.bri)}",
                DECISION_COLORS.get(context.decision, PRIMARY_COLOR),
            ),
        ]
    )
    manuscript_tab, normative_tab, literature_tab = st.tabs(
        ["Research Manuscript", "Normative References", "Supporting Literature"]
    )
    with manuscript_tab:
        render_section_header("MOBRA Research Manuscript", icon="□")
        if manuscript["manuscript_download_enabled"]:
            manuscript_columns = st.columns(3)
            manuscript_columns[0].metric(
                "Pages",
                manuscript["manuscript_page_count"] or "N/A",
            )
            manuscript_columns[1].metric(
                "File Size",
                _file_size_label(manuscript["manuscript_size_bytes"]),
            )
            manuscript_columns[2].metric(
                "Author",
                manuscript["manuscript_author"],
            )
            st.info(manuscript["manuscript_version_note"])
            st.download_button(
                "Download MOBRA Research Manuscript (PDF)",
                manuscript_download_bytes(),
                manuscript["manuscript_filename"],
                "application/pdf",
                width="stretch",
                key="research_manuscript_download",
            )
        else:
            render_empty_state(
                "Research manuscript not included",
                "A manuscript placeholder is active for this deployment. Add the approved PDF under docs to enable download.",
                icon="□",
            )

    with normative_tab:
        render_section_header(
            "Priority Normative References",
            icon="□",
            help_text=(
                "Official source links for the primary biosafety, biosecurity, "
                "mobile-laboratory, biorisk, and risk-management references."
            ),
        )
        priority_ids = [
            "WHO-01",
            "WHO-02",
            "WHO-03",
            "WHO-04",
            "BMBL-01",
            "ISO-01",
            "ISO-02",
        ]
        priority_order = {resource_id: index for index, resource_id in enumerate(priority_ids)}
        ordered_resources = sorted(
            resources,
            key=lambda item: (
                priority_order.get(str(item.get("resource_id")), len(priority_order)),
                str(item.get("title", "")),
            ),
        )
        for resource in ordered_resources:
            label = (
                f"{resource.get('resource_id', '')} · "
                f"{resource.get('title', 'Untitled reference')}"
            )
            with st.expander(label, expanded=False):
                st.markdown(f"**Citation**  \n{resource.get('citation', 'Not available')}")
                st.markdown(
                    f"**Relevance to MOBRA**  \n"
                    f"{resource.get('relevance_to_mobra', 'Not documented')}"
                )
                st.caption(
                    f"{resource.get('issuing_organization', '')} · "
                    f"{resource.get('edition', '')} · "
                    f"{resource.get('access_type', '')} · "
                    f"{resource.get('redistribution_status', '')}"
                )
                official_url = str(resource.get("official_page_url", ""))
                if official_url:
                    st.link_button(
                        "Open official source",
                        official_url,
                        width="stretch",
                    )
        if resources:
            st.download_button(
                "Download Normative Reference Catalogue (CSV)",
                catalogue_csv_bytes(resources),
                "MOBRA_Normative_Resources.csv",
                "text/csv",
                width="stretch",
                key="research_reference_catalogue",
            )
        st.caption(
            "Official links and citations do not imply endorsement, certification, "
            "accreditation, or scientific validation by WHO, CDC, NIH, ISO, or any "
            "other issuing organization. Copyrighted ISO documents are not redistributed."
        )

    with literature_tab:
        render_section_header("Supporting Scientific Literature", icon="□")
        if literature:
            literature_frame = pd.DataFrame(literature)
            visible_columns = [
                "citation_id",
                "title",
                "authors",
                "year",
                "journal",
                "evidence_role",
                "official_or_publisher_url",
                "access_type",
            ]
            st.dataframe(
                literature_frame[
                    [column for column in visible_columns if column in literature_frame.columns]
                ],
                width="stretch",
                hide_index=True,
                height=440,
                column_config={
                    "official_or_publisher_url": st.column_config.LinkColumn(
                        "Publisher / DOI",
                        display_text="Open source",
                    )
                },
            )
            with st.expander("Citation details", expanded=False):
                for item in literature:
                    st.markdown(
                        f"**{item.get('citation_id', '')} · {item.get('title', '')}**  \n"
                        f"{item.get('authors', '')} ({item.get('year', '')}). "
                        f"*{item.get('journal', '')}*. DOI: `{item.get('doi', 'Not available')}`"
                    )
        else:
            render_empty_state(
                "Supporting literature unavailable",
                "No supporting-literature catalogue is included in this deployment.",
                icon="□",
            )
        st.caption(
            "Supporting literature informs interpretation and future validation work; "
            "it does not change the current MOBRA formulas, thresholds, or decision rules."
        )


def render_about(context: AssessmentContext) -> None:
    """Render institutional identity, scope, provenance, and future-data boundaries."""
    render_page_header(
        "About MOBRA",
        "Purpose, identity, technical scope, and responsible-use limitations.",
        icon="ⓘ",
        status="Prototype decision support",
    )
    brand, description = st.columns([1.2, 2.8], vertical_alignment="center")
    with brand:
        render_logo(width=300)
    with description:
        st.markdown(
            f"### {APP_FULL_NAME}\n\n"
            "MOBRA is a scientific and operational decision-support application for assessing "
            "mobile biological laboratory readiness and biosecurity. Its shield represents "
            "protection and containment; the structured grid represents risk assessment; "
            "the check mark represents verified readiness criteria."
        )
    render_section_header("Responsible Use and Validation Boundary", icon="!")
    st.warning(
        "MOBRA outputs support structured review. They do not constitute clinical approval, "
        "regulatory authorization, field validation, or final scientific validation of the methodology."
    )
    st.markdown(
        "The included dataset is always labelled **Synthetic Demonstration Data**. "
        "Use of other datasets should be described as technical verification, prototype testing, "
        "preliminary analytical validation, or external-data compatibility assessment."
    )
    render_section_header("Future External-Data Compatibility", icon="↗")
    st.write(
        "The architecture is prepared for import testing and comparative analysis with datasets such as:"
    )
    future_sources = [
        "Canadian Laboratory Incident Data",
        "Exposure Incident Notification Data",
        "Exposure Incident Follow-up Data",
        "Non-exposure Incident Data",
        "Other Event Data",
        "Global Health Security Index 2021",
        "High-risk Pathogen Exposure Events",
    ]
    st.markdown("\n".join(f"- {source}" for source in future_sources))
    st.info(
        "No external source listed above is currently connected. A future connection must be explicitly implemented, documented, and validated."
    )
    render_section_header("Educational Media", icon="▣")
    try:
        media = load_educational_media()
        summary = media_summary(media)
        media_preview, media_details = st.columns([1.1, 1.9])
        with media_preview:
            st.image(
                str(PROJECT_ROOT / media[0]["png_path"]),
                caption=media[0]["title"],
                width="stretch",
            )
        with media_details:
            st.markdown(
                f"**{summary['educational_media_count']} original MOBRA educational posters** "
                "are available in SVG, PNG, and printable PDF formats."
            )
            st.dataframe(
                pd.DataFrame(media)[
                    [
                        "media_id",
                        "title",
                        "topic",
                        "educational_status",
                        "last_updated",
                    ]
                ],
                width="stretch",
                hide_index=True,
                height=330,
            )
            st.download_button(
                "Download Educational Media Package (ZIP)",
                educational_media_package(media),
                "MOBRA_Educational_Media_Package.zip",
                "application/zip",
                width="stretch",
            )
        st.caption(
            "These are original MOBRA educational summaries. Referenced organizations "
            "do not endorse, certify, approve, or validate the application."
        )
    except ValueError as exc:
        st.warning(f"Educational media unavailable: {exc}")

    render_section_header("Research Manuscript", icon="□")
    manuscript = manuscript_metadata()
    if manuscript["manuscript_download_enabled"]:
        manuscript_columns = st.columns(3)
        manuscript_columns[0].metric(
            "Pages",
            manuscript["manuscript_page_count"] or "N/A",
        )
        manuscript_columns[1].metric(
            "File Size",
            _file_size_label(manuscript["manuscript_size_bytes"]),
        )
        manuscript_columns[2].metric(
            "Author",
            manuscript["manuscript_author"],
        )
        st.info(manuscript["manuscript_version_note"])
        st.download_button(
            "Download MOBRA Research Manuscript (PDF)",
            manuscript_download_bytes(),
            manuscript["manuscript_filename"],
            "application/pdf",
            width="stretch",
        )
    else:
        st.warning("The research manuscript is not available in this deployment.")
    render_section_header("Normative Evidence Catalogue", icon="□")
    try:
        resource_frame = resource_catalogue_frame(load_normative_resources())
        resource_columns = [
            "resource_id",
            "title",
            "issuing_organization",
            "edition",
            "publication_year",
            "topic",
            "official_page_url",
            "access_type",
            "redistribution_status",
            "current_status",
        ]
        st.dataframe(
            resource_frame[
                [column for column in resource_columns if column in resource_frame.columns]
            ],
            width="stretch",
            hide_index=True,
            height=420,
            column_config={
                "official_page_url": st.column_config.LinkColumn(
                    "Official Source",
                    display_text="Open official page",
                )
            },
        )
        st.caption(
            "Links identify source material and do not imply endorsement, certification, "
            "accreditation, or scientific validation by an issuing organization."
        )
    except ValueError as exc:
        st.warning(f"Resource catalogue unavailable: {exc}")

    render_section_header("Project and Contact", icon="↗")
    contact_columns = st.columns(3)
    with contact_columns[0]:
        st.markdown(f"**Author**  \n{AUTHOR_NAME}")
    with contact_columns[1]:
        st.markdown(f"**Contact**  \n[{AUTHOR_EMAIL}](mailto:{AUTHOR_EMAIL})")
    with contact_columns[2]:
        st.markdown(f"**Source repository**  \n[GitHub]({REPOSITORY_URL})")
    render_section_header("Current Assessment Context", icon="□")
    st.json(
        {
            "data_source": context.meta.get("source_label"),
            "hazard_file": context.meta.get("hazard_filename"),
            "requirements_file": context.meta.get("requirements_filename"),
            "hazard_records": len(context.hazards),
            "requirement_records": len(context.requirements),
            "last_update": _last_update(context.meta),
        },
        expanded=False,
    )


PAGE_RENDERERS = {
    "Home": render_home,
    "Data Import": render_data_import,
    "Data Validation": render_data_validation,
    "Requirements Assessment": render_requirements_assessment,
    "Hazard Register": render_hazard_register,
    "Risk Analysis": render_risk_analysis,
    "Readiness Dashboard": render_readiness_dashboard,
    "Mission Map": render_mission_map,
    "Deployment Decision": render_deployment_decision,
    "Corrective Actions": render_corrective_actions,
    "Reports and Export": render_reports_export,
    "Methodology": render_methodology,
    "Research and References": render_research_references,
    "About MOBRA": render_about,
}


def render_page(page: str, context: AssessmentContext) -> None:
    """Dispatch one known page while retaining session state."""
    renderer = PAGE_RENDERERS.get(page, render_home)
    renderer(context)
