"""Plotly visualizations used by the dashboard and report."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .risk import RISK_COLORS, RISK_LEVELS, heatmap_counts


def risk_counts_figure(
    hazards: pd.DataFrame,
    *,
    category_column: str = "risk_category",
    title: str = "Hazards by Inherent Risk Category",
) -> go.Figure:
    counts = (
        hazards.get(category_column, pd.Series(dtype=str))
        .value_counts()
        .reindex(RISK_LEVELS, fill_value=0)
        .reset_index()
    )
    counts.columns = ["risk_category", "count"]
    fig = px.bar(
        counts,
        x="risk_category",
        y="count",
        color="risk_category",
        text_auto=True,
        category_orders={"risk_category": RISK_LEVELS},
        color_discrete_map=RISK_COLORS,
        title=title,
    )
    xaxis_title = (
        "Decision-support risk category" if category_column == "decision_risk_category" else "Inherent risk category"
    )
    fig.update_layout(showlegend=False, xaxis_title=xaxis_title, yaxis_title="Hazard count")
    return fig


def heatmap_figure(hazards: pd.DataFrame, title: str = "5 × 5 Inherent Hazard Risk Heat Map") -> go.Figure:
    counts = heatmap_counts(hazards)
    score_matrix = np.array(
        [[likelihood * consequence for likelihood in range(1, 6)] for consequence in [5, 4, 3, 2, 1]]
    )
    colorscale = [
        [0.0, RISK_COLORS["Low"]],
        [4 / 25, RISK_COLORS["Low"]],
        [4.01 / 25, RISK_COLORS["Moderate"]],
        [9 / 25, RISK_COLORS["Moderate"]],
        [9.01 / 25, RISK_COLORS["High"]],
        [16 / 25, RISK_COLORS["High"]],
        [16.01 / 25, RISK_COLORS["Extreme"]],
        [1.0, RISK_COLORS["Extreme"]],
    ]
    fig = go.Figure(
        go.Heatmap(
            z=score_matrix,
            x=[1, 2, 3, 4, 5],
            y=[5, 4, 3, 2, 1],
            text=counts.to_numpy(),
            texttemplate="<b>%{text}</b>",
            textfont={"size": 18, "color": "white"},
            colorscale=colorscale,
            zmin=1,
            zmax=25,
            showscale=False,
            hovertemplate="Likelihood (L)=%{x}<br>Consequence (C)=%{y}<br>Hazard count=%{text}<extra></extra>",
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Likelihood (L) — probability of occurrence",
        yaxis_title="Consequence (C) — severity of impact",
        height=540,
        margin={"l": 55, "r": 30, "t": 70, "b": 70},
    )
    return fig


def mapping_sankey_figure(mapping_details: pd.DataFrame, hazard_id: str) -> go.Figure:
    """Show a readable requirement-to-hazard diagram for one selected hazard."""
    if mapping_details.empty:
        figure = go.Figure()
        figure.add_annotation(text="No mapping links for the selected hazard.", showarrow=False)
        return figure
    requirement_ids = mapping_details["requirement_id"].astype(str).tolist()
    hazard_name = str(mapping_details["hazard_name"].iloc[0]) if "hazard_name" in mapping_details else hazard_id
    labels = [*requirement_ids, f"{hazard_id}: {hazard_name}"]
    requirement_wording = (
        mapping_details.get("requirement_wording", pd.Series("", index=mapping_details.index)).astype(str).tolist()
    )
    rationales = (
        mapping_details.get("mapping_rationale", pd.Series("", index=mapping_details.index)).astype(str).tolist()
    )
    target = len(requirement_ids)
    figure = go.Figure(
        go.Sankey(
            arrangement="snap",
            node={
                "label": labels,
                "pad": 18,
                "thickness": 18,
                "customdata": [*requirement_wording, hazard_name],
                "hovertemplate": "%{label}<br>%{customdata}<extra></extra>",
            },
            link={
                "source": list(range(len(requirement_ids))),
                "target": [target] * len(requirement_ids),
                "value": [1] * len(requirement_ids),
                "customdata": rationales,
                "hovertemplate": "%{customdata}<extra></extra>",
            },
        )
    )
    figure.update_layout(title=f"Requirement links for {hazard_id}", height=max(360, 70 * len(requirement_ids)))
    return figure


def bri_gauge(bri: float) -> go.Figure:
    value = 0 if pd.isna(bri) else float(bri)
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={"suffix": "%", "font": {"size": 42}},
            title={"text": "Biosecurity Readiness Index (BRI)"},
            gauge={
                "axis": {"range": [0, 100]},
                "steps": [
                    {"range": [0, 50], "color": "#ffcdd2"},
                    {"range": [50, 70], "color": "#ffe0b2"},
                    {"range": [70, 85], "color": "#fff9c4"},
                    {"range": [85, 100], "color": "#c8e6c9"},
                ],
                "threshold": {"line": {"color": "black", "width": 4}, "value": 70},
            },
        )
    )
    fig.update_layout(height=320, margin={"l": 30, "r": 30, "t": 70, "b": 20})
    return fig


def domain_figure(domains: pd.DataFrame) -> go.Figure:
    fig = px.bar(
        domains,
        x="readiness_pct",
        y="domain",
        orientation="h",
        text_auto=".1f",
        range_x=[0, 100],
        title="Readiness by Operational Domain",
    )
    fig.update_layout(xaxis_title="Domain BRI (%)", yaxis_title="Operational domain")
    return fig
