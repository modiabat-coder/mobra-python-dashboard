"""Standalone HTML report generation."""

from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from jinja2 import Template

from .acceptance import (
    RISK_ACCEPTANCE_LIMITATION,
    RiskAcceptancePolicy,
    apply_risk_acceptance,
    risk_acceptance_summary,
    risk_acceptance_summary_table,
)
from .charts import bri_gauge, domain_figure, heatmap_figure, risk_counts_figure
from .critical_controls import (
    CRITICAL_CONTROL_LIMITATION,
    CriticalControlAssessment,
    critical_control_summary_table,
)
from .mapping import (
    coverage_by_requirement_domain,
    enrich_mapping,
    hazards_without_requirements,
    mapping_coverage_summary,
    requirements_without_hazards,
)
from .readiness import data_quality_summary, failed_critical_controls
from .risk import heatmap_total
from .validation_findings import (
    VALIDATION_LIMITATION,
    ValidationFinding,
    findings_frame,
    summaries_frame,
    validation_overview,
)


def make_html_report(
    hazards: pd.DataFrame,
    requirements: pd.DataFrame,
    bri: float,
    decision: str,
    reasons: list[str],
    *,
    hazard_filename: str = "hazards",
    requirements_filename: str = "requirements",
    validation_messages: list[str] | None = None,
    filtered_hazards: pd.DataFrame | None = None,
    mapping: pd.DataFrame | None = None,
    mapping_validation_messages: list[str] | None = None,
    risk_acceptance_policy: RiskAcceptancePolicy | None = None,
    critical_profile: pd.DataFrame | None = None,
    critical_control_assessment: CriticalControlAssessment | None = None,
    critical_profile_validation_messages: list[str] | None = None,
    validation_findings: list[ValidationFinding] | None = None,
    validation_summaries: list[dict[str, Any]] | None = None,
    validation_reference_date: str | None = None,
) -> str:
    """Build a self-contained HTML report with escaped data tables and inline Plotly."""
    acceptance_policy = risk_acceptance_policy or RiskAcceptancePolicy()
    hazards = apply_risk_acceptance(hazards, acceptance_policy)
    filtered = apply_risk_acceptance(
        filtered_hazards if filtered_hazards is not None else hazards,
        acceptance_policy,
    )
    acceptance = risk_acceptance_summary(hazards, acceptance_policy)
    source_summary = acceptance["risk_source_summary"]
    acceptance_counts = pd.DataFrame(
        [
            {"Acceptance status": status, "Hazard count": count}
            for status, count in acceptance["acceptance_status_counts"].items()
        ]
    )
    acceptance_policy_table = risk_acceptance_summary_table(hazards, acceptance_policy)
    corrective_hazards = hazards.loc[hazards["corrective_action_required"]]
    approval_hazards = hazards.loc[hazards["formal_approval_required"]]
    missing_residual_hazards = hazards.loc[hazards["residual_assessment_missing"]]
    domains = (
        requirements.groupby("domain", dropna=False)
        .agg(observed_score=("observed_score", "sum"), maximum_score=("maximum_score", "sum"))
        .reset_index()
        if {"domain", "observed_score", "maximum_score"}.issubset(requirements.columns)
        else pd.DataFrame(columns=["domain", "observed_score", "maximum_score"])
    )
    if not domains.empty:
        domains["readiness_pct"] = 100 * domains["observed_score"] / domains["maximum_score"]
    critical_governance_available = bool(
        critical_profile is not None and critical_control_assessment is not None and critical_control_assessment.ok
    )
    if critical_governance_available and critical_control_assessment is not None:
        failed = critical_control_assessment.deployment_blocking_failures
        critical_summary = critical_control_assessment.summary
        critical_summary_export = critical_control_summary_table(critical_control_assessment)
        critical_assessment_data = critical_control_assessment.data
        conditional_critical_gaps = critical_control_assessment.conditional_gaps
        important_critical_gaps = critical_control_assessment.important_gaps
        evidence_deficiencies = critical_control_assessment.evidence_deficiencies
        incomplete_critical_records = critical_control_assessment.incomplete_records
        manual_review_items = critical_control_assessment.manual_review_items
    else:
        failed = failed_critical_controls(requirements)
        critical_summary = {}
        critical_summary_export = pd.DataFrame()
        critical_assessment_data = pd.DataFrame()
        conditional_critical_gaps = pd.DataFrame()
        important_critical_gaps = pd.DataFrame()
        evidence_deficiencies = pd.DataFrame()
        incomplete_critical_records = pd.DataFrame()
        manual_review_items = pd.DataFrame()
    quality = data_quality_summary(hazards, requirements)
    structured_findings = list(validation_findings or [])
    structured_summaries = list(validation_summaries or [])
    validation_metrics = validation_overview(structured_summaries, structured_findings)
    validation_findings_data = findings_frame(structured_findings)
    validation_summaries_data = summaries_frame(structured_summaries)
    important_validation_warnings = (
        validation_findings_data.loc[validation_findings_data["severity"].eq("Warning")].head(25)
        if not validation_findings_data.empty
        else pd.DataFrame()
    )
    mapping_available = mapping is not None
    mapping_summary: dict[str, int | float] = {}
    mapping_details = pd.DataFrame()
    unmapped_hazards = pd.DataFrame()
    unmapped_requirements = pd.DataFrame()
    mapping_domain_coverage = pd.DataFrame()
    critical_mapping_links = pd.DataFrame()
    if mapping_available:
        mapping_summary = mapping_coverage_summary(mapping, requirements, hazards)
        mapping_details = enrich_mapping(mapping, requirements, hazards)
        unmapped_hazards = hazards_without_requirements(mapping, hazards)
        unmapped_requirements = requirements_without_hazards(mapping, requirements)
        mapping_domain_coverage = coverage_by_requirement_domain(mapping, requirements)
        critical_mapping_links = mapping_details.loc[mapping_details["critical_link"].fillna(False).astype(bool)]

    def table_or_message(data: pd.DataFrame, columns: list[str], empty_message: str = "None.") -> str:
        available = [column for column in columns if column in data.columns]
        if data.empty:
            return f"<p>{escape(empty_message)}</p>"
        return data[available].to_html(index=False, escape=True, border=0)

    template = Template(
        """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>MOBRA — Mobile Operational Biosecurity Readiness Assessment Report</title><style>
body{font-family:Arial,sans-serif;margin:0;background:#f5f7fa;color:#17202a}header{background:#0b3954;color:#fff;padding:28px 5%}main{max-width:1250px;margin:auto;padding:24px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px}.card{background:#fff;border-radius:12px;padding:18px;box-shadow:0 2px 10px #0001;margin-bottom:18px}.metric{font-size:30px;font-weight:700}.label{color:#5d6d7e}.decision{font-size:22px;font-weight:700}table{border-collapse:collapse;width:100%;font-size:12px;display:block;overflow-x:auto}th,td{border:1px solid #ddd;padding:6px;text-align:left;white-space:nowrap}th{background:#eaf2f8}.plot{overflow-x:auto}.note{color:#5d6d7e;font-size:13px}</style></head>
<body><header><h1>MOBRA — Mobile Operational Biosecurity Readiness Assessment Report</h1><p>Computational verification prototype</p></header><main>
<div class="grid"><div class="card"><div class="label">Overall BRI</div><div class="metric">{{ bri_display }}%</div></div><div class="card"><div class="label">Hazards analyzed</div><div class="metric">{{ hazard_count }}</div></div><div class="card"><div class="label">Unacceptable hazards</div><div class="metric">{{ unacceptable_count }}</div></div><div class="card"><div class="label">Decision</div><div class="decision">{{ decision }}</div></div></div>
<div class="card"><h2>Analysis metadata</h2><p>Generated: {{ generated }}<br>Hazard file: {{ hazard_filename }} ({{ hazard_rows }} rows × {{ hazard_columns }} columns)<br>Requirements file: {{ requirements_filename }} ({{ requirement_rows }} rows × {{ requirement_columns }} columns)</p></div>
<div class="card"><h2>Decision rationale</h2><ul>{% for reason in reasons %}<li>{{ reason }}</li>{% endfor %}</ul></div>
<div class="card"><h2>Risk Acceptance</h2><p><strong>{{ acceptance_limitation }}</strong></p><div class="grid"><div><div class="label">Risk source used</div><div class="metric">{{ risk_source_display }}</div></div><div><div class="label">Corrective action required</div><div class="metric">{{ corrective_count }}</div></div><div><div class="label">Formal approval required</div><div class="metric">{{ approval_count }}</div></div><div><div class="label">Missing residual assessment</div><div class="metric">{{ missing_residual_count }}</div></div></div>{% if inherent_screening_count %}<p>Inherent risk was used for screening for {{ inherent_screening_count }} hazard(s) because residual assessment was not provided. These records are not described as residual risk.</p>{% endif %}<h3>Provisional acceptance-status counts</h3>{{ acceptance_counts_table }}<h3>Risk-acceptance policy summary</h3>{{ acceptance_policy_table }}</div>
<div class="card"><h2>Risk-acceptance action lists</h2><h3>Hazards requiring corrective action</h3>{{ corrective_hazards_table }}<h3>Hazards requiring formal approval</h3>{{ approval_hazards_table }}<h3>Hazards missing residual assessment</h3>{{ missing_residual_hazards_table }}</div>
<div class="card"><h2>Per-hazard Risk Acceptance</h2>{{ acceptance_hazards_table }}</div>
<div class="card"><h2>Critical-Control Governance</h2><p><strong>{{ critical_control_limitation }}</strong></p><p>A high BRI cannot override a deployment-blocking critical-control failure.</p>{% if critical_governance_available %}<div class="grid"><div><div class="label">Deployment-blocking controls</div><div class="metric">{{ criticality_counts["Deployment-blocking"] }}</div></div><div><div class="label">Conditional controls</div><div class="metric">{{ criticality_counts["Conditional"] }}</div></div><div><div class="label">Important controls</div><div class="metric">{{ criticality_counts["Important"] }}</div></div><div><div class="label">Passed controls</div><div class="metric">{{ critical_outcome_counts["Pass"] }}</div></div><div><div class="label">Blocking failures</div><div class="metric">{{ blocking_failure_count }}</div></div><div><div class="label">Conditional gaps</div><div class="metric">{{ conditional_gap_count }}</div></div><div><div class="label">Evidence deficiencies</div><div class="metric">{{ evidence_deficiency_count }}</div></div><div><div class="label">Manual-review items</div><div class="metric">{{ manual_review_count }}</div></div></div><h3>Governance summary</h3>{{ critical_summary_table }}{% if critical_profile_validation_messages %}<h3>Profile validation findings</h3><ul>{% for message in critical_profile_validation_messages %}<li>{{ message }}</li>{% endfor %}</ul>{% endif %}{% else %}<p>No valid critical-control profile was supplied. Structured governance analysis and Critical-control failures are unavailable.</p>{% endif %}</div>
{% if critical_governance_available %}<div class="card"><h2>Critical-control findings</h2><h3>Critical-control failures — Deployment-blocking</h3>{{ blocking_failures_table }}<h3>Conditional gaps</h3>{{ conditional_gaps_table }}<h3>Important corrective-action findings</h3>{{ important_gaps_table }}<h3>Evidence deficiencies</h3>{{ evidence_deficiencies_table }}<h3>Incomplete critical records</h3>{{ incomplete_critical_records_table }}<h3>Manual-review items</h3>{{ manual_review_items_table }}</div><div class="card"><h2>Appendix: Critical-Control Profile</h2>{{ critical_profile_table }}</div><div class="card"><h2>Appendix: Full Critical-Control Assessment</h2>{{ critical_assessment_table }}</div>{% endif %}
<div class="card"><h2>Validation and data quality</h2><p>Missing values: {{ quality.missing_values }} ({{ quality.missing_value_pct }}%) · Missing evidence: {{ quality.missing_evidence }} · Incomplete requirements: {{ quality.incomplete_requirements }} · Heat-map cells: {{ heatmap_total }} records</p>{% if validation_messages %}<ul>{% for message in validation_messages %}<li>{{ message }}</li>{% endfor %}</ul>{% else %}<p>No validation errors or warnings were supplied.</p>{% endif %}</div>
<div class="card"><h2>Data Validation</h2><p><strong>Validation reference date:</strong> {{ validation_reference_date }}</p><div class="grid"><div><div class="label">Errors</div><div class="metric">{{ validation_metrics.finding_counts_by_severity.Error }}</div></div><div><div class="label">Warnings</div><div class="metric">{{ validation_metrics.finding_counts_by_severity.Warning }}</div></div><div><div class="label">Information</div><div class="metric">{{ validation_metrics.finding_counts_by_severity.Information }}</div></div><div><div class="label">Included records</div><div class="metric">{{ validation_metrics.analysis_eligible_records }}</div></div><div><div class="label">Excluded records</div><div class="metric">{{ validation_metrics.excluded_records }}</div></div><div><div class="label">Blocking findings</div><div class="metric">{{ validation_metrics.blocking_finding_count }}</div></div></div><p><strong>Invalid rows were retained for review and excluded from relevant calculations that require valid fields.</strong></p><p class="note">{{ validation_limitation }}</p><h3>Dataset summaries</h3>{{ validation_summary_table }}<h3>Important warnings</h3>{{ important_validation_warnings_table }}</div>
<div class="card"><h2>Appendix: Validation Findings</h2>{{ validation_findings_table }}</div>
<div class="card plot">{{ gauge_html }}</div><div class="card plot">{{ heatmap_html }}</div><div class="card plot">{{ domain_html }}</div><div class="card plot">{{ risk_html }}</div>
<div class="card"><h2>Requirement-to-Hazard Mapping</h2><p class="note">Operational Requirement ↔ Objective Evidence ↔ Representative Hazard. The included links are representative demonstration mappings for software verification and methodology illustration. They have not undergone expert content-validity assessment and do not imply scientific or institutional validation. Future expert review may add, remove, or modify relationships.</p>
{% if mapping_available %}<div class="grid"><div><div class="label">Mapping links</div><div class="metric">{{ mapping_summary.mapping_links }}</div></div><div><div class="label">Hazards mapped</div><div class="metric">{{ mapping_summary.hazards_mapped }}/{{ mapping_summary.hazards_total }}</div><div class="note">{{ mapping_summary.hazard_coverage_pct }}%</div></div><div><div class="label">Requirements mapped</div><div class="metric">{{ mapping_summary.requirements_mapped }}/{{ mapping_summary.requirements_total }}</div><div class="note">{{ mapping_summary.requirement_coverage_pct }}%</div></div><div><div class="label">Critical links</div><div class="metric">{{ mapping_summary.critical_links }}</div></div></div>
{% if mapping_validation_messages %}<h3>Mapping validation findings</h3><ul>{% for message in mapping_validation_messages %}<li>{{ message }}</li>{% endfor %}</ul>{% endif %}
{% else %}<p>No requirement-to-hazard mapping dataset was supplied for this report.</p>{% endif %}</div>
{% if mapping_available %}<div class="card"><h2>Mapping coverage</h2><h3>Unmapped hazards</h3>{{ unmapped_hazards_table }}<h3>Unmapped requirements</h3>{{ unmapped_requirements_table }}<h3>Coverage by requirement domain</h3>{{ mapping_domain_coverage_table }}</div>
<div class="card"><h2>Critical requirement-to-hazard links</h2>{{ critical_mapping_links_table }}</div>
<div class="card"><h2>Appendix: Representative Requirement-to-Hazard Mapping</h2>{{ mapping_table }}</div>{% endif %}
<div class="card"><h2>Hazard register (calculated fields included)</h2>{{ hazards_table }}</div><div class="card"><h2>Operational requirements (calculated fields included)</h2>{{ requirements_table }}</div>
<div class="card"><h2>Methodology and limitations</h2><p>Risk Score = Likelihood x Consequence. Categories remain Low 1-4, Moderate 5-9, High 10-16, and Extreme 17-25. Inherent risk is calculated from the original likelihood and consequence. Residual risk is used only when valid residual data or a valid calculated residual category is available for that hazard. Under the default missing-residual policy, inherent risk is a screening substitute and is explicitly labeled as such. BRI (%) remains sum of observed requirement scores divided by sum of maximum requirement scores x 100. Critical-control governance is a separate override layer and does not remove low-scoring controls from BRI. Score status, required evidence, and record completeness are assessed independently. Deployment-blocking failures override a high BRI; Conditional gaps and Manual review prevent automatic READY. A READY result does not imply that missing residual assessments were completed. Critical-control classifications and thresholds are provisional rather than universal, regulatory, or institutionally approved. This is external-dataset-based computational verification of the MOBRA prototype, not clinical, operational, regulatory, or field validation. The application does not replace risk acceptance by authorized and accountable institutional personnel.</p></div>
<p class="note">Generated with UTF-8. Source data are not overwritten; calculated columns are added to the downloaded analysis copies.</p></main></body></html>"""
    )
    domain_plot = domain_figure(domains) if not domains.empty else go.Figure()
    return template.render(
        bri_display="N/A" if pd.isna(bri) else f"{bri:.1f}",
        hazard_count=len(filtered),
        unacceptable_count=acceptance["unacceptable_hazard_count"],
        decision=decision,
        reasons=reasons,
        acceptance_limitation=RISK_ACCEPTANCE_LIMITATION,
        risk_source_display=source_summary["risk_source_display"],
        inherent_screening_count=source_summary["inherent_screening_hazard_count"],
        corrective_count=acceptance["corrective_action_required_count"],
        approval_count=acceptance["formal_approval_required_count"],
        missing_residual_count=acceptance["missing_residual_assessment_count"],
        acceptance_counts_table=acceptance_counts.to_html(index=False, escape=True, border=0),
        acceptance_policy_table=acceptance_policy_table.to_html(index=False, escape=True, border=0),
        corrective_hazards_table=table_or_message(
            corrective_hazards,
            [
                "hazard_id",
                "hazard",
                "decision_risk_category",
                "decision_risk_source",
                "risk_acceptance_status",
                "acceptance_action_required",
                "responsible_person",
                "due_date",
                "status",
            ],
            "No hazards require corrective action under the configured policy.",
        ),
        approval_hazards_table=table_or_message(
            approval_hazards,
            [
                "hazard_id",
                "hazard",
                "decision_risk_category",
                "decision_risk_source",
                "risk_acceptance_status",
                "acceptance_action_required",
                "responsible_person",
                "due_date",
                "status",
            ],
            "No hazards require formal approval under the configured policy.",
        ),
        missing_residual_hazards_table=table_or_message(
            missing_residual_hazards,
            [
                "hazard_id",
                "hazard",
                "risk_score",
                "risk_category",
                "decision_risk_category",
                "decision_risk_source",
                "risk_acceptance_status",
                "acceptance_reason",
            ],
            "All hazards have a valid residual assessment.",
        ),
        acceptance_hazards_table=table_or_message(
            hazards,
            [
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
            ],
        ),
        critical_governance_available=critical_governance_available,
        critical_control_limitation=CRITICAL_CONTROL_LIMITATION,
        criticality_counts=critical_summary.get("criticality_level_counts", {}),
        critical_outcome_counts=critical_summary.get("critical_control_outcome_counts", {}),
        blocking_failure_count=critical_summary.get("deployment_blocking_failure_count", 0),
        conditional_gap_count=critical_summary.get("conditional_gap_count", 0),
        evidence_deficiency_count=critical_summary.get("evidence_deficiency_count", 0),
        manual_review_count=critical_summary.get("manual_review_count", 0),
        critical_profile_validation_messages=[
            escape(str(message)) for message in (critical_profile_validation_messages or [])
        ],
        critical_summary_table=table_or_message(critical_summary_export, ["metric", "value"]),
        blocking_failures_table=table_or_message(
            failed,
            [
                "requirement_id",
                "requirement",
                "domain",
                "observed_score",
                "maximum_score",
                "minimum_acceptable_score",
                "score_status",
                "evidence_status",
                "completion_status",
                "critical_control_outcome",
                "critical_control_disposition",
                "critical_control_reason",
            ],
            "No deployment-blocking failures.",
        ),
        conditional_gaps_table=table_or_message(
            conditional_critical_gaps,
            [
                "requirement_id",
                "requirement",
                "domain",
                "observed_score",
                "maximum_score",
                "minimum_acceptable_score",
                "evidence_status",
                "critical_control_outcome",
                "critical_control_disposition",
                "critical_control_reason",
                "rationale",
            ],
            "No Conditional gaps.",
        ),
        important_gaps_table=table_or_message(
            important_critical_gaps,
            [
                "requirement_id",
                "requirement",
                "domain",
                "observed_score",
                "maximum_score",
                "minimum_acceptable_score",
                "evidence_status",
                "critical_control_outcome",
                "critical_control_disposition",
                "critical_control_reason",
                "rationale",
            ],
            "No Important corrective-action findings.",
        ),
        evidence_deficiencies_table=table_or_message(
            evidence_deficiencies,
            [
                "requirement_id",
                "requirement",
                "criticality_level",
                "objective_evidence",
                "evidence_status",
                "critical_control_outcome",
                "critical_control_disposition",
                "critical_control_reason",
            ],
            "No required-evidence deficiencies.",
        ),
        incomplete_critical_records_table=table_or_message(
            incomplete_critical_records,
            [
                "requirement_id",
                "requirement",
                "criticality_level",
                "score_status",
                "evidence_status",
                "completion_status",
                "critical_control_disposition",
                "critical_control_reason",
            ],
            "No incomplete critical records.",
        ),
        manual_review_items_table=table_or_message(
            manual_review_items,
            [
                "requirement_id",
                "requirement",
                "criticality_level",
                "score_status",
                "evidence_status",
                "completion_status",
                "critical_control_disposition",
                "critical_control_reason",
            ],
            "No manual-review items.",
        ),
        critical_profile_table=table_or_message(
            critical_profile if critical_profile is not None else pd.DataFrame(),
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
            ],
            "No valid critical-control profile supplied.",
        ),
        critical_assessment_table=table_or_message(
            critical_assessment_data,
            [
                "requirement_id",
                "requirement",
                "domain",
                "observed_score",
                "maximum_score",
                "minimum_acceptable_score",
                "objective_evidence",
                "evidence_status",
                "score_status",
                "completion_status",
                "criticality_level",
                "critical_control_outcome",
                "critical_control_disposition",
                "critical_control_reason",
                "requires_manual_review",
                "compensating_control_required",
                "formal_approval_required",
                "rationale",
                "approval_status",
                "source_status",
            ],
            "No valid critical-control assessment supplied.",
        ),
        generated=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        hazard_filename=escape(str(hazard_filename)),
        requirements_filename=escape(str(requirements_filename)),
        hazard_rows=len(hazards),
        hazard_columns=len(hazards.columns),
        requirement_rows=len(requirements),
        requirement_columns=len(requirements.columns),
        quality=quality,
        heatmap_total=heatmap_total(filtered),
        validation_reference_date=escape(str(validation_reference_date or datetime.now().date().isoformat())),
        validation_metrics=validation_metrics,
        validation_limitation=VALIDATION_LIMITATION,
        validation_summary_table=table_or_message(
            validation_summaries_data,
            [
                "dataset_type",
                "filename",
                "sheet_name",
                "rows",
                "columns",
                "required_columns_found",
                "missing_columns",
                "duplicate_ids",
                "invalid_rows",
                "missing_values",
                "analysis_eligible_records",
                "excluded_records",
                "validation_status",
            ],
            "No structured dataset summaries were supplied.",
        ),
        important_validation_warnings_table=table_or_message(
            important_validation_warnings,
            ["dataset_type", "code", "message", "record_id", "column", "suggested_action"],
            "No structured warnings.",
        ),
        validation_findings_table=table_or_message(
            validation_findings_data,
            [
                "finding_id",
                "dataset_type",
                "severity",
                "code",
                "message",
                "row_index",
                "record_id",
                "column",
                "original_value",
                "normalized_value",
                "suggested_action",
                "blocks_analysis",
            ],
            "No structured validation findings.",
        ),
        validation_messages=[escape(str(message)) for message in (validation_messages or [])],
        mapping_available=mapping_available,
        mapping_summary=mapping_summary,
        mapping_validation_messages=[escape(str(message)) for message in (mapping_validation_messages or [])],
        unmapped_hazards_table=table_or_message(
            unmapped_hazards,
            ["hazard_id", "hazard", "domain"],
            "All hazards have at least one linked requirement.",
        ),
        unmapped_requirements_table=table_or_message(
            unmapped_requirements,
            ["requirement_id", "requirement", "domain", "objective_evidence", "evidence"],
            "All requirements have at least one linked hazard.",
        ),
        mapping_domain_coverage_table=table_or_message(
            mapping_domain_coverage,
            ["requirement_domain", "requirements_linked", "requirements_total", "coverage_pct", "mapping_links"],
        ),
        critical_mapping_links_table=table_or_message(
            critical_mapping_links,
            ["mapping_id", "requirement_id", "hazard_id", "relationship_type", "mapping_rationale", "control_role"],
        ),
        mapping_table=table_or_message(
            mapping_details,
            [
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
            ],
        ),
        gauge_html=bri_gauge(bri).to_html(full_html=False, include_plotlyjs="inline"),
        heatmap_html=heatmap_figure(filtered).to_html(full_html=False, include_plotlyjs=False),
        domain_html=domain_plot.to_html(full_html=False, include_plotlyjs=False),
        risk_html=risk_counts_figure(filtered).to_html(full_html=False, include_plotlyjs=False),
        failed_table=failed.to_html(index=False, escape=True, border=0),
        hazards_table=hazards.to_html(index=False, escape=True, border=0),
        requirements_table=requirements.to_html(index=False, escape=True, border=0),
    )
