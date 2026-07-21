"""Standalone HTML report generation."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from html import escape

import pandas as pd
from jinja2 import Template
import plotly.graph_objects as go

from .charts import bri_gauge, domain_figure, heatmap_figure, risk_counts_figure
from .readiness import data_quality_summary, failed_critical_controls
from .risk import heatmap_total


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
) -> str:
    """Build a self-contained HTML report with escaped data tables and inline Plotly."""
    filtered = filtered_hazards if filtered_hazards is not None else hazards
    domains = (
        requirements.groupby("domain", dropna=False).agg(observed_score=("observed_score", "sum"), maximum_score=("maximum_score", "sum")).reset_index()
        if {"domain", "observed_score", "maximum_score"}.issubset(requirements.columns)
        else pd.DataFrame(columns=["domain", "observed_score", "maximum_score"])
    )
    if not domains.empty:
        domains["readiness_pct"] = 100 * domains["observed_score"] / domains["maximum_score"]
    failed = failed_critical_controls(requirements)
    quality = data_quality_summary(hazards, requirements)
    template = Template(
        """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>MOBRA Assessment Report</title><style>
body{font-family:Arial,sans-serif;margin:0;background:#f5f7fa;color:#17202a}header{background:#0b3954;color:#fff;padding:28px 5%}main{max-width:1250px;margin:auto;padding:24px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px}.card{background:#fff;border-radius:12px;padding:18px;box-shadow:0 2px 10px #0001;margin-bottom:18px}.metric{font-size:30px;font-weight:700}.label{color:#5d6d7e}.decision{font-size:22px;font-weight:700}table{border-collapse:collapse;width:100%;font-size:12px;display:block;overflow-x:auto}th,td{border:1px solid #ddd;padding:6px;text-align:left;white-space:nowrap}th{background:#eaf2f8}.plot{overflow-x:auto}.note{color:#5d6d7e;font-size:13px}</style></head>
<body><header><h1>MOBRA Assessment Report</h1><p>Mobile Operational Biosecurity Readiness Assessment · Computational verification prototype</p></header><main>
<div class="grid"><div class="card"><div class="label">Overall BRI</div><div class="metric">{{ bri_display }}%</div></div><div class="card"><div class="label">Hazards analyzed</div><div class="metric">{{ hazard_count }}</div></div><div class="card"><div class="label">Extreme risks</div><div class="metric">{{ extreme_count }}</div></div><div class="card"><div class="label">Decision</div><div class="decision">{{ decision }}</div></div></div>
<div class="card"><h2>Analysis metadata</h2><p>Generated: {{ generated }}<br>Hazard file: {{ hazard_filename }} ({{ hazard_rows }} rows × {{ hazard_columns }} columns)<br>Requirements file: {{ requirements_filename }} ({{ requirement_rows }} rows × {{ requirement_columns }} columns)</p></div>
<div class="card"><h2>Decision rationale</h2><ul>{% for reason in reasons %}<li>{{ reason }}</li>{% endfor %}</ul></div>
<div class="card"><h2>Validation and data quality</h2><p>Missing values: {{ quality.missing_values }} ({{ quality.missing_value_pct }}%) · Missing evidence: {{ quality.missing_evidence }} · Incomplete requirements: {{ quality.incomplete_requirements }} · Heat-map cells: {{ heatmap_total }} records</p>{% if validation_messages %}<ul>{% for message in validation_messages %}<li>{{ message }}</li>{% endfor %}</ul>{% else %}<p>No validation errors or warnings were supplied.</p>{% endif %}</div>
<div class="card plot">{{ gauge_html }}</div><div class="card plot">{{ heatmap_html }}</div><div class="card plot">{{ domain_html }}</div><div class="card plot">{{ risk_html }}</div>
<div class="card"><h2>Critical-control failures</h2>{{ failed_table }}</div><div class="card"><h2>Hazard register (calculated fields included)</h2>{{ hazards_table }}</div><div class="card"><h2>Operational requirements (calculated fields included)</h2>{{ requirements_table }}</div>
<div class="card"><h2>Methodology and limitations</h2><p>Risk Score = Likelihood × Consequence. Categories are Low 1–4, Moderate 5–9, High 10–16, and Extreme 17–25. BRI (%) = sum of observed requirement scores ÷ sum of maximum requirement scores × 100. Extreme residual risk, failed/incomplete critical controls, validation errors, or an uncomputable BRI override a high BRI and prevent deployment. This is external-dataset-based computational verification of the MOBRA prototype, not clinical, operational, or regulatory validation.</p></div>
<p class="note">Generated with UTF-8. Source data are not overwritten; calculated columns are added to the downloaded analysis copies.</p></main></body></html>"""
    )
    risk_column = "residual_risk_category" if "residual_risk_category" in hazards.columns and hazards["residual_risk_category"].ne("Not provided").any() else "risk_category"
    extreme_count = int(hazards.get(risk_column, pd.Series(dtype=str)).eq("Extreme").sum())
    domain_plot = domain_figure(domains) if not domains.empty else go.Figure()
    return template.render(
        bri_display="N/A" if pd.isna(bri) else f"{bri:.1f}",
        hazard_count=len(filtered),
        extreme_count=extreme_count,
        decision=decision,
        reasons=reasons,
        generated=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        hazard_filename=escape(str(hazard_filename)),
        requirements_filename=escape(str(requirements_filename)),
        hazard_rows=len(hazards),
        hazard_columns=len(hazards.columns),
        requirement_rows=len(requirements),
        requirement_columns=len(requirements.columns),
        quality=quality,
        heatmap_total=heatmap_total(filtered),
        validation_messages=[escape(str(message)) for message in (validation_messages or [])],
        gauge_html=bri_gauge(bri).to_html(full_html=False, include_plotlyjs="inline"),
        heatmap_html=heatmap_figure(filtered).to_html(full_html=False, include_plotlyjs=False),
        domain_html=domain_plot.to_html(full_html=False, include_plotlyjs=False),
        risk_html=risk_counts_figure(filtered).to_html(full_html=False, include_plotlyjs=False),
        failed_table=failed.to_html(index=False, escape=True, border=0),
        hazards_table=hazards.to_html(index=False, escape=True, border=0),
        requirements_table=requirements.to_html(index=False, escape=True, border=0),
    )
