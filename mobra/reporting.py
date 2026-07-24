"""Branded HTML, Excel, JSON, and CSV exports for MOBRA."""

from __future__ import annotations

from datetime import datetime
from html import escape
import io
import json
from pathlib import Path
from typing import Any

from jinja2 import Template
from openpyxl.styles import Font, PatternFill
import pandas as pd
import plotly.graph_objects as go

from .actions import build_corrective_actions
from .charts import (
    bri_progress_figure,
    domain_figure,
    heatmap_figure,
    primary_bri_dial_figure,
    risk_counts_figure,
)
from .config import (
    APP_FULL_NAME,
    APP_NAME,
    BORDER_COLOR,
    DECISION_CONDITIONAL,
    DECISION_DO_NOT_DEPLOY,
    DECISION_READY,
    LOGO_DARK_PATH,
    PRIMARY_COLOR,
    PRIMARY_DARK,
    RISK_COLORS,
    SECONDARY_COLOR,
    SYNTHETIC_DATA_LABEL,
)
from .decisions import decision_risk_column
from .readiness import data_quality_summary, domain_readiness, failed_critical_controls
from .risk import heatmap_counts, heatmap_total


def csv_bytes(frame: pd.DataFrame) -> bytes:
    """Serialize a table as UTF-8 with BOM for reliable Windows Excel display."""
    return frame.to_csv(index=False).encode("utf-8-sig")


def summary_payload(
    hazards: pd.DataFrame,
    requirements: pd.DataFrame,
    bri: float,
    decision: str,
    reasons: list[str],
    *,
    data_source: str,
    hazard_filename: str,
    requirements_filename: str,
    validation_messages: list[str] | None = None,
) -> dict[str, Any]:
    """Build a portable executive-summary dictionary."""
    risk_column = decision_risk_column(hazards)
    risk_counts = (
        hazards.get(risk_column, pd.Series(dtype="string"))
        .value_counts()
        .to_dict()
    )
    return {
        "system": APP_NAME,
        "full_name": APP_FULL_NAME,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "data_source": data_source,
        "hazard_file": hazard_filename,
        "requirements_file": requirements_filename,
        "overall_bri_pct": None if pd.isna(bri) else round(float(bri), 2),
        "deployment_decision": decision,
        "decision_reasons": reasons,
        "hazard_count": len(hazards),
        "requirement_count": len(requirements),
        "risk_basis": risk_column,
        "risk_counts": risk_counts,
        "heatmap_cell_total": heatmap_total(hazards),
        "failed_critical_controls": len(failed_critical_controls(requirements)),
        "data_quality": data_quality_summary(hazards, requirements),
        "validation_messages": validation_messages or [],
    }


def json_bytes(payload: dict[str, Any]) -> bytes:
    """Serialize a summary using UTF-8 and preserved Arabic text."""
    return json.dumps(
        payload,
        indent=2,
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def make_excel_workbook(
    hazards: pd.DataFrame,
    requirements: pd.DataFrame,
    bri: float,
    decision: str,
    reasons: list[str],
    *,
    data_source: str = SYNTHETIC_DATA_LABEL,
    hazard_filename: str = "hazards",
    requirements_filename: str = "requirements",
    validation_issues: pd.DataFrame | None = None,
) -> bytes:
    """Create a branded multi-worksheet MOBRA analysis workbook."""
    payload = summary_payload(
        hazards,
        requirements,
        bri,
        decision,
        reasons,
        data_source=data_source,
        hazard_filename=hazard_filename,
        requirements_filename=requirements_filename,
    )
    executive = pd.DataFrame(
        [
            {"Metric": "System", "Value": APP_NAME},
            {"Metric": "Full Name", "Value": APP_FULL_NAME},
            {"Metric": "Generated", "Value": payload["generated_at"]},
            {"Metric": "Data Source", "Value": data_source},
            {"Metric": "Overall BRI", "Value": payload["overall_bri_pct"]},
            {"Metric": "Deployment Decision", "Value": decision},
            {"Metric": "Decision Reasons", "Value": " | ".join(reasons)},
            {"Metric": "Hazards", "Value": len(hazards)},
            {"Metric": "Requirements", "Value": len(requirements)},
            {
                "Metric": "Failed Critical Controls",
                "Value": payload["failed_critical_controls"],
            },
        ]
    )
    matrix = heatmap_counts(hazards).copy()
    matrix.index.name = "Likelihood"
    actions = build_corrective_actions(hazards, requirements)
    issues = (
        validation_issues
        if validation_issues is not None
        else pd.DataFrame(
            [
                {
                    "severity": "Information",
                    "cause": "No validation issue register was supplied.",
                }
            ]
        )
    )
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        executive.to_excel(writer, sheet_name="Executive Summary", index=False)
        domain_readiness(requirements).to_excel(
            writer,
            sheet_name="Domain Summary",
            index=False,
        )
        requirements.to_excel(writer, sheet_name="Requirements", index=False)
        hazards.to_excel(writer, sheet_name="Hazard Register", index=False)
        matrix.to_excel(writer, sheet_name="Risk Matrix")
        failed_critical_controls(requirements).to_excel(
            writer,
            sheet_name="Critical Controls",
            index=False,
        )
        actions.to_excel(writer, sheet_name="Corrective Actions", index=False)
        issues.to_excel(writer, sheet_name="Validation Issues", index=False)
        workbook = writer.book
        for sheet in workbook.worksheets:
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            sheet.sheet_view.showGridLines = False
            for cell in sheet[1]:
                cell.font = Font(
                    name="Arial",
                    size=11,
                    bold=True,
                    color="FFFFFF",
                )
                cell.fill = PatternFill(
                    "solid",
                    fgColor=PRIMARY_COLOR.replace("#", ""),
                )
            for column_cells in sheet.columns:
                width = min(
                    45,
                    max(11, max(len(str(cell.value or "")) for cell in column_cells) + 2),
                )
                sheet.column_dimensions[column_cells[0].column_letter].width = width
    return buffer.getvalue()


def _logo_markup(path: Path = LOGO_DARK_PATH) -> str:
    """Load the controlled local SVG wordmark for inline report use."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return f"<strong>{APP_NAME}</strong>"


def _table(
    frame: pd.DataFrame,
    columns: list[str] | None = None,
    *,
    limit: int | None = None,
) -> str:
    if columns:
        available = [column for column in columns if column in frame.columns]
        frame = frame[available]
    if limit is not None:
        frame = frame.head(limit)
    if frame.empty:
        return '<p class="empty">No records available for this section.</p>'
    table = frame.to_html(index=False, escape=True, border=0, na_rep="—")
    return f'<div class="table-wrap">{table}</div>'


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
    data_source: str = SYNTHETIC_DATA_LABEL,
) -> str:
    """Build a self-contained, branded, UTF-8, print-ready HTML report."""
    filtered = filtered_hazards if filtered_hazards is not None else hazards
    domains = domain_readiness(requirements)
    failed = failed_critical_controls(requirements)
    quality = data_quality_summary(hazards, requirements)
    actions = build_corrective_actions(hazards, requirements)
    risk_column = decision_risk_column(hazards)
    extreme_count = int(
        hazards.get(risk_column, pd.Series(dtype=str)).eq("Extreme").sum()
    )
    top_hazards = hazards.sort_values("risk_score", ascending=False).head(10)
    bri_display = "N/A" if pd.isna(bri) else f"{bri:.1f}%"
    failed_count = len(failed)
    if failed_count:
        control_word = "control" if failed_count == 1 else "controls"
        decision_note = (
            f"Readiness score: {bri_display}. Deployment remains prohibited "
            f"because {failed_count} mission-critical {control_word} failed."
        )
    else:
        decision_note = (
            f"Readiness score: {bri_display}. Final decision: {decision}. "
            "The readiness category does not replace the formal Deployment Decision."
        )
    primary_gauge_html = primary_bri_dial_figure(
        bri,
        critical_override_active=failed_count > 0,
    ).to_html(
        full_html=False,
        include_plotlyjs="inline",
        config={"displayModeBar": False, "responsive": True},
    )
    gauge_html = bri_progress_figure(bri).to_html(
        full_html=False,
        include_plotlyjs=False,
        config={"displayModeBar": False, "responsive": True},
    )
    heatmap_html = heatmap_figure(filtered).to_html(
        full_html=False,
        include_plotlyjs=False,
        config={"displayModeBar": False, "responsive": True},
    )
    domain_plot = domain_figure(domains) if not domains.empty else go.Figure()
    domain_html = (
        domain_plot.to_html(
            full_html=False,
            include_plotlyjs=False,
            config={"displayModeBar": False, "responsive": True},
        )
        if not domains.empty
        else '<p class="empty">Domain readiness is unavailable.</p>'
    )
    risk_html = risk_counts_figure(filtered).to_html(
        full_html=False,
        include_plotlyjs=False,
        config={"displayModeBar": False, "responsive": True},
    )
    decision_class = {
        DECISION_DO_NOT_DEPLOY: "stop",
        DECISION_CONDITIONAL: "conditional",
        DECISION_READY: "ready",
    }.get(decision, "neutral")
    template = Template(
        """<!doctype html>
<html lang="en" dir="ltr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MOBRA Assessment Report</title>
<style>
:root{--primary:{{ primary }};--primary-dark:{{ primary_dark }};--secondary:{{ secondary }};--border:{{ border }}}
*{box-sizing:border-box}html{background:#f3f6f7}body{margin:0;background:#f3f6f7;color:#18323c;font-family:Aptos,Inter,"Noto Sans Arabic","Segoe UI",Tahoma,Arial,sans-serif;line-height:1.5;overflow-wrap:anywhere}
.report-header{background:var(--primary-dark);color:#fff;padding:28px 5%;border-bottom:5px solid var(--secondary)}
.brand{max-width:1180px;margin:auto;display:flex;align-items:center;justify-content:space-between;gap:28px}.brand>div:first-child{min-width:0;flex:1}.brand svg{display:block;width:460px;max-width:100%;height:auto}.brand-meta{text-align:right;flex:none}.brand-meta strong{display:block;color:#fff;font-size:21px}.brand-meta span{color:#d7e6e9;font-size:13px}
main{max-width:1180px;margin:auto;padding:24px}.section{background:#fff;border:1px solid var(--border);border-radius:12px;padding:20px;margin:0 0 18px;box-shadow:0 2px 9px rgba(8,42,56,.05)}
h1,h2,h3{color:var(--primary);margin-top:0}h2{font-size:20px;border-bottom:1px solid var(--border);padding-bottom:8px}
.report-kpi-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-bottom:18px}.metric{min-width:0;min-height:110px;background:#fff;border:1px solid var(--border);border-top:3px solid var(--secondary);border-radius:10px;padding:14px;overflow-wrap:anywhere}.metric .label{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:#627880;font-weight:700}.metric .value{font-size:26px;line-height:1.18;color:var(--primary);font-weight:800;margin-top:4px;overflow-wrap:anywhere}
.data-label{display:inline-block;max-width:100%;border:1px solid #6fa2aa;border-radius:99px;padding:4px 10px;font-size:12px;font-weight:700;color:var(--primary);overflow-wrap:anywhere}
.decision{border-radius:12px;padding:18px 20px;margin-bottom:18px;border:1px solid;border-left-width:8px}.decision h1{margin:0 0 5px}.decision.stop{background:#fff1f0;border-color:#b42318}.decision.stop h1{color:#b42318}.decision.conditional{background:#fff6e8;border-color:#b25e09}.decision.conditional h1{color:#9a5109}.decision.ready{background:#edf8f1;border-color:#237a45}.decision.ready h1{color:#237a45}.decision.neutral{background:#f0f4f5;border-color:#607d86}
.report-gauge-note{display:flex;align-items:center;gap:10px;margin:4px 0 8px;padding:11px 13px;border:1px solid #e7b8b4;border-left:5px solid #b42318;border-radius:10px;background:#fff4f3}.report-gauge-note p{margin:0;font-size:13px}.report-decision-badge{display:inline-flex;flex:none;border-radius:999px;padding:5px 10px;background:#b42318;color:#fff;font-size:11px;font-weight:800;letter-spacing:.03em;white-space:nowrap}
.table-wrap{width:100%;overflow-x:auto}.table-wrap table{border-collapse:collapse;width:100%;font-size:11px}.table-wrap th,.table-wrap td{border:1px solid #dce5e7;padding:7px;text-align:left;vertical-align:top;white-space:normal;overflow-wrap:anywhere}.table-wrap th{background:var(--primary);color:#fff;position:sticky;top:0}
.plot{overflow:hidden;break-inside:avoid}.plot .plot-container{max-width:100%}.note,.empty{font-size:12px;color:#61767e}.risk-legend{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0 0}.risk-legend span{border:1px solid #667c84;border-radius:99px;padding:4px 9px;font-size:11px;font-weight:700}.page-break{break-before:page}.two{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:18px}footer{color:#667c84;text-align:center;font-size:11px;padding:12px 20px 26px}
@media(max-width:900px){.report-kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.two{grid-template-columns:minmax(0,1fr)}.brand{align-items:flex-start}.brand svg{width:390px}}
@media(max-width:560px){.report-header{padding:20px}.brand{display:block}.brand-meta{text-align:left;margin-top:14px}.report-kpi-grid{grid-template-columns:minmax(0,1fr)}main{padding:14px}.section{padding:15px}.decision{padding:15px}.metric{min-height:96px}.report-gauge-note{align-items:flex-start;flex-direction:column}}
@page{size:A4;margin:14mm}
@media print{*{-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}html,body{background:#fff}.report-header{padding:16px 0}.brand,main{max-width:none;margin:0}.brand svg{width:360px}.section,.metric,.decision{box-shadow:none;break-inside:avoid}.plot{break-inside:avoid}.page-break{break-before:page}.table-wrap{overflow:visible}.table-wrap table{font-size:8.5px;table-layout:fixed}.table-wrap th{position:static}.no-print{display:none}.risk-legend span{border-width:1.5px}}
</style>
</head>
<body>
<header class="report-header"><div class="brand"><div>{{ logo }}</div><div class="brand-meta"><strong>Assessment Report</strong><span>Generated {{ generated }}</span></div></div></header>
<main>
<p><span class="data-label">{{ data_source }}</span></p>
<section class="decision {{ decision_class }}"><div>DEPLOYMENT DECISION</div><h1>{{ decision }}</h1><ul>{% for reason in reasons %}<li>{{ reason }}</li>{% endfor %}</ul></section>
<div class="report-kpi-grid">
<div class="metric"><div class="label">Overall BRI</div><div class="value">{{ bri_display }}</div></div>
<div class="metric"><div class="label">Requirements</div><div class="value">{{ requirement_count }}</div></div>
<div class="metric"><div class="label">Hazards</div><div class="value">{{ hazard_count }}</div></div>
<div class="metric"><div class="label">Failed Critical Controls</div><div class="value">{{ failed_count }}</div></div>
</div>
<section class="section plot"><h2>Biosecurity Readiness Index</h2>{{ primary_gauge_html }}<div class="report-gauge-note"><span class="report-decision-badge">{{ decision }}</span><p>{{ decision_note }}</p></div><p class="note">The gauge reflects the numerical BRI only. It cannot authorize deployment or bypass failed Critical Controls.</p></section>
<section class="section"><h2>Executive Summary</h2><p>MOBRA assessed {{ requirement_count }} operational requirements and {{ hazard_count }} hazards. The Overall BRI is {{ bri_display }}. The deployment decision remains governed by Critical Controls, residual risk, critical data completeness, and required evidence; BRI alone does not authorize deployment.</p><p><strong>Data source:</strong> {{ data_source }}<br><strong>Hazard file:</strong> {{ hazard_filename }}<br><strong>Requirements file:</strong> {{ requirements_filename }}</p></section>
<div class="two"><section class="section plot">{{ gauge_html }}</section><section class="section plot">{{ risk_html }}</section></div>
<section class="section plot"><h2>Domain Readiness</h2>{{ domain_html }}</section>
<section class="section page-break plot"><h2>Risk Heatmap</h2>{{ heatmap_html }}<div class="risk-legend"><span style="background:{{ low }};color:white">Green = Low (1–4)</span><span style="background:{{ moderate }};color:#3d3100">Yellow = Moderate (5–9)</span><span style="background:{{ high }};color:white">Orange = High (10–16)</span><span style="background:{{ extreme }};color:white">Red = Extreme (17–25)</span></div><p class="note">Cell color represents the MOBRA risk category based on Likelihood × Consequence. The number inside each cell represents the count of hazards assigned to that combination. Verified total: {{ heatmap_total }} valid hazards.</p></section>
<section class="section"><h2>Critical-control Findings</h2>{{ critical_table }}</section>
<section class="section"><h2>Top Hazards</h2>{{ top_hazards_table }}</section>
<section class="section"><h2>Corrective Actions</h2>{{ actions_table }}</section>
<section class="section page-break"><h2>Validation Summary</h2><p>Missing values: {{ quality.missing_values }} ({{ quality.missing_value_pct }}%) · Missing evidence: {{ quality.missing_evidence }} · Incomplete requirements: {{ quality.incomplete_requirements }} · Extreme risks: {{ extreme_count }}</p>{% if validation_messages %}<ul>{% for message in validation_messages %}<li>{{ message }}</li>{% endfor %}</ul>{% else %}<p>No validation errors or warnings were recorded.</p>{% endif %}</section>
<section class="section"><h2>Methodology Note</h2><p><strong>Risk Score = Likelihood × Consequence.</strong> Low = 1–4, Moderate = 5–9, High = 10–16, Extreme = 17–25.</p><p><strong>BRI (%) = Sum of Observed Requirement Scores ÷ Sum of Maximum Requirement Scores × 100.</strong></p><p>The decision rules give non-bypassable priority to failed Critical Controls, Extreme residual risk, material critical-data incompleteness, mission-critical failures, and missing evidence for Critical Controls.</p></section>
<section class="section"><h2>Limitations</h2><p>This report is decision support, not clinical, regulatory, or field validation. Synthetic Demonstration Data are representative test records and must not be treated as operational evidence. External incident or index datasets are not connected unless explicitly documented by a future implementation.</p></section>
</main>
<footer>{{ app_name }} · {{ full_name }} · UTF-8 English/Arabic compatible report</footer>
</body></html>"""
    )
    return template.render(
        primary=PRIMARY_COLOR,
        primary_dark=PRIMARY_DARK,
        secondary=SECONDARY_COLOR,
        border=BORDER_COLOR,
        logo=_logo_markup(),
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        data_source=escape(str(data_source)),
        decision=escape(decision),
        decision_class=decision_class,
        reasons=[escape(str(reason)) for reason in reasons],
        bri_display=bri_display,
        requirement_count=len(requirements),
        hazard_count=len(hazards),
        failed_count=failed_count,
        hazard_filename=escape(str(hazard_filename)),
        requirements_filename=escape(str(requirements_filename)),
        primary_gauge_html=primary_gauge_html,
        decision_note=escape(decision_note),
        gauge_html=gauge_html,
        risk_html=risk_html,
        domain_html=domain_html,
        heatmap_html=heatmap_html,
        low=RISK_COLORS["Low"],
        moderate=RISK_COLORS["Moderate"],
        high=RISK_COLORS["High"],
        extreme=RISK_COLORS["Extreme"],
        heatmap_total=heatmap_total(filtered),
        critical_table=_table(
            failed,
            [
                "requirement_id",
                "domain",
                "requirement",
                "observed_score",
                "maximum_score",
                "objective_evidence",
                "responsible_person",
                "due_date",
            ],
        ),
        top_hazards_table=_table(
            top_hazards,
            [
                "hazard_id",
                "hazard",
                "domain",
                "risk_score",
                "risk_category",
                "residual_risk_score",
                "residual_risk_category",
                "corrective_action",
                "responsible_person",
            ],
        ),
        actions_table=_table(actions, limit=25),
        quality=quality,
        extreme_count=extreme_count,
        validation_messages=[
            escape(str(message)) for message in (validation_messages or [])
        ],
        app_name=APP_NAME,
        full_name=APP_FULL_NAME,
    )
