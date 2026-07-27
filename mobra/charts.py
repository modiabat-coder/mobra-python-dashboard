"""Consistent Plotly visualizations for the MOBRA interface and reports."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .config import (
    ACCENT_COLOR,
    BORDER_COLOR,
    DANGER_COLOR,
    MUTED_TEXT_COLOR,
    PRIMARY_COLOR,
    PRIMARY_DARK,
    RISK_COLORS,
    RISK_LEVELS,
    RISK_TEXT_COLORS,
    SECONDARY_COLOR,
    SURFACE_COLOR,
    TEXT_COLOR,
)
from .risk import classify_risk, heatmap_counts


def apply_chart_theme(
    figure: go.Figure,
    *,
    height: int = 380,
    title: str | None = None,
) -> go.Figure:
    """Apply the shared MOBRA chart typography, spacing, and background."""
    figure.update_layout(
        title=title,
        title_font={"size": 18, "color": PRIMARY_COLOR, "family": "Inter, Segoe UI, Arial"},
        font={"size": 12, "color": TEXT_COLOR, "family": "Inter, Segoe UI, Arial"},
        paper_bgcolor=SURFACE_COLOR,
        plot_bgcolor=SURFACE_COLOR,
        height=height,
        margin={"l": 48, "r": 24, "t": 62 if title else 28, "b": 48},
        hoverlabel={"bgcolor": PRIMARY_COLOR, "font_color": "#FFFFFF"},
        legend={
            "title": None,
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.01,
            "xanchor": "right",
            "x": 1,
        },
    )
    figure.update_xaxes(
        showgrid=False,
        linecolor=BORDER_COLOR,
        tickfont={"color": MUTED_TEXT_COLOR},
        automargin=True,
    )
    figure.update_yaxes(
        gridcolor="#EAF0F2",
        linecolor=BORDER_COLOR,
        tickfont={"color": MUTED_TEXT_COLOR},
        automargin=True,
    )
    return figure


def risk_counts_figure(hazards: pd.DataFrame) -> go.Figure:
    """Show hazard counts by fixed risk category."""
    counts = (
        hazards.get("risk_category", pd.Series(dtype=str))
        .value_counts()
        .reindex(RISK_LEVELS, fill_value=0)
        .rename_axis("risk_category")
        .reset_index(name="count")
    )
    figure = px.bar(
        counts,
        x="risk_category",
        y="count",
        color="risk_category",
        text="count",
        category_orders={"risk_category": RISK_LEVELS},
        color_discrete_map=RISK_COLORS,
        labels={"risk_category": "Risk Category", "count": "Hazard Count"},
    )
    figure.update_traces(
        textposition="outside",
        cliponaxis=False,
        hovertemplate="<b>%{x}</b><br>Hazards: %{y}<extra></extra>",
    )
    figure.update_layout(showlegend=False)
    return apply_chart_theme(figure, title="Risk Category Distribution")


def initial_residual_figure(hazards: pd.DataFrame) -> go.Figure:
    """Compare initial and residual category counts when residual data exist."""
    frames: list[pd.DataFrame] = []
    for column, label in (
        ("risk_category", "Initial Risk"),
        ("residual_risk_category", "Residual Risk"),
    ):
        if column not in hazards.columns:
            continue
        series = hazards[column]
        series = series[series.isin(RISK_LEVELS)]
        if series.empty and label == "Residual Risk":
            continue
        counts = (
            series.value_counts()
            .reindex(RISK_LEVELS, fill_value=0)
            .rename_axis("risk_category")
            .reset_index(name="count")
        )
        counts["assessment_stage"] = label
        frames.append(counts)
    data = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["risk_category", "count", "assessment_stage"]
    )
    figure = px.bar(
        data,
        x="risk_category",
        y="count",
        color="assessment_stage",
        barmode="group",
        text="count",
        category_orders={"risk_category": RISK_LEVELS},
        color_discrete_map={
            "Initial Risk": PRIMARY_COLOR,
            "Residual Risk": ACCENT_COLOR,
        },
        labels={
            "risk_category": "Risk Category",
            "count": "Hazard Count",
            "assessment_stage": "Assessment Stage",
        },
    )
    figure.update_traces(textposition="outside", cliponaxis=False)
    return apply_chart_theme(figure, title="Initial versus Residual Risk")


def hazards_by_domain_figure(hazards: pd.DataFrame) -> go.Figure:
    """Show hazard volume by operational domain."""
    counts = (
        hazards.get("domain", pd.Series(dtype="string"))
        .replace("Not provided", pd.NA)
        .dropna()
        .value_counts()
        .head(12)
        .sort_values()
        .rename_axis("domain")
        .reset_index(name="count")
    )
    figure = px.bar(
        counts,
        x="count",
        y="domain",
        orientation="h",
        text="count",
        color_discrete_sequence=[SECONDARY_COLOR],
        labels={"domain": "Operational Domain", "count": "Hazard Count"},
    )
    figure.update_traces(
        textposition="outside",
        cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>Hazards: %{x}<extra></extra>",
    )
    return apply_chart_theme(figure, title="Hazards by Domain", height=420)


def top_hazards_figure(hazards: pd.DataFrame, limit: int = 10) -> go.Figure:
    """Show the highest scored hazards in descending priority."""
    if hazards.empty or "risk_score" not in hazards.columns:
        return go.Figure()
    data = hazards.nlargest(limit, "risk_score").sort_values("risk_score")
    name_column = "hazard" if "hazard" in data.columns else "hazard_id"
    figure = px.bar(
        data,
        x="risk_score",
        y=name_column,
        orientation="h",
        color="risk_category",
        text="risk_score",
        color_discrete_map=RISK_COLORS,
        category_orders={"risk_category": RISK_LEVELS},
        labels={name_column: "Hazard", "risk_score": "Risk Score"},
    )
    figure.update_traces(
        textposition="outside",
        cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>Risk score: %{x}<extra></extra>",
    )
    figure.update_layout(showlegend=False)
    return apply_chart_theme(figure, title="Top High-Risk Hazards", height=440)


def _risk_colorscale() -> list[list[float | str]]:
    """Build discrete threshold stops across a 1–25 continuous heatmap scale."""
    # Plotly normalizes z using (score - 1) / 24.
    boundaries = [
        (1, 4.499, RISK_COLORS["Low"]),
        (4.5, 9.499, RISK_COLORS["Moderate"]),
        (9.5, 16.499, RISK_COLORS["High"]),
        (16.5, 25, RISK_COLORS["Extreme"]),
    ]
    stops: list[list[float | str]] = []
    for start, end, color in boundaries:
        stops.append([max(0, (start - 1) / 24), color])
        stops.append([min(1, (end - 1) / 24), color])
    return stops


def heatmap_figure(
    hazards: pd.DataFrame,
    title: str = "5 × 5 Hazard Risk Matrix",
) -> go.Figure:
    """Render the approved consequence × likelihood matrix using real counts."""
    likelihood_values = [5, 4, 3, 2, 1]
    consequence_values = [1, 2, 3, 4, 5]
    counts = heatmap_counts(hazards)
    scores = np.array(
        [
            [likelihood * consequence for consequence in consequence_values]
            for likelihood in likelihood_values
        ]
    )
    categories = np.vectorize(classify_risk)(scores)
    cell_records = np.empty((5, 5), dtype=object)
    for row_index, likelihood in enumerate(likelihood_values):
        for column_index, consequence in enumerate(consequence_values):
            assigned = hazards[
                hazards["likelihood"].eq(likelihood)
                & hazards["consequence"].eq(consequence)
            ]
            labels: list[str] = []
            for _, row in assigned.head(6).iterrows():
                identifier = row.get("hazard_id", "")
                name = row.get("hazard", "")
                labels.append(
                    f"{identifier}: {name}".strip(": ")
                    or "Unnamed hazard"
                )
            if len(assigned) > 6:
                labels.append(f"+{len(assigned) - 6} more")
            cell_records[row_index, column_index] = (
                "<br>".join(labels) if labels else "No hazards assigned"
            )
    custom = np.empty((5, 5, 3), dtype=object)
    custom[:, :, 0] = categories
    custom[:, :, 1] = counts.to_numpy()
    custom[:, :, 2] = cell_records
    figure = go.Figure(
        go.Heatmap(
            z=scores,
            x=consequence_values,
            y=likelihood_values,
            customdata=custom,
            colorscale=_risk_colorscale(),
            zmin=1,
            zmax=25,
            showscale=False,
            hovertemplate=(
                "<b>Risk matrix cell</b><br>"
                "Likelihood: %{y}<br>"
                "Consequence: %{x}<br>"
                "Risk Score: %{z}<br>"
                "Risk Category: %{customdata[0]}<br>"
                "Hazard Count: %{customdata[1]}<br>"
                "Assigned Records:<br>%{customdata[2]}<extra></extra>"
            ),
        )
    )
    for row_index, likelihood in enumerate(likelihood_values):
        for column_index, consequence in enumerate(consequence_values):
            category = str(categories[row_index, column_index])
            figure.add_annotation(
                x=consequence,
                y=likelihood,
                text=f"<b>{int(counts.iloc[row_index, column_index])}</b>",
                showarrow=False,
                font={
                    "size": 18,
                    "color": RISK_TEXT_COLORS.get(category, "#FFFFFF"),
                },
            )
    for category in RISK_LEVELS:
        figure.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker={"size": 10, "color": RISK_COLORS[category], "symbol": "square"},
                name=category,
                hoverinfo="skip",
            )
        )
    figure.update_xaxes(
        title="Consequence",
        tickmode="array",
        tickvals=consequence_values,
        range=[0.5, 5.5],
        fixedrange=True,
    )
    figure.update_yaxes(
        title="Likelihood",
        tickmode="array",
        tickvals=[1, 2, 3, 4, 5],
        range=[0.5, 5.5],
        fixedrange=True,
    )
    return apply_chart_theme(figure, title=title, height=560)


def bri_progress_figure(bri: float) -> go.Figure:
    """Render Overall BRI as a compact horizontal progress indicator."""
    value = 0.0 if pd.isna(bri) else float(bri)
    display = "N/A" if pd.isna(bri) else f"{value:.1f}%"
    figure = go.Figure(
        go.Indicator(
            mode="number+gauge",
            value=value,
            number={"suffix": "%", "font": {"size": 34, "color": PRIMARY_COLOR}},
            title={"text": "Overall BRI", "font": {"size": 16, "color": MUTED_TEXT_COLOR}},
            gauge={
                "shape": "bullet",
                "axis": {"range": [0, 100], "tickvals": [0, 50, 70, 85, 100]},
                "bar": {"color": SECONDARY_COLOR, "thickness": 0.55},
                "bgcolor": "#E8EFF1",
                "borderwidth": 0,
                "threshold": {
                    "line": {"color": PRIMARY_COLOR, "width": 3},
                    "value": 85,
                },
            },
        )
    )
    figure.update_layout(
        annotations=[
            {
                "text": display,
                "x": 0.98,
                "y": 0.95,
                "xref": "paper",
                "yref": "paper",
                "showarrow": False,
                "font": {"color": PRIMARY_COLOR, "size": 1},
            }
        ]
    )
    return apply_chart_theme(figure, height=220)


def bri_gauge(bri: float) -> go.Figure:
    """Backward-compatible alias for the compact BRI indicator."""
    return bri_progress_figure(bri)


def executive_radial_gauge(
    value: float,
    title: str,
    *,
    higher_is_better: bool = True,
) -> go.Figure:
    """Render one contextual 0–100 executive indicator.

    These bands are presentation cues only. They do not replace the MOBRA
    deployment rules, Critical Control override, or fixed risk matrix.
    """
    numeric = 0.0 if pd.isna(value) else float(np.clip(value, 0, 100))
    if higher_is_better:
        steps = [
            {"range": [0, 50], "color": "#F9DEDC"},
            {"range": [50, 70], "color": "#FCE8D4"},
            {"range": [70, 85], "color": "#FFF4C2"},
            {"range": [85, 100], "color": "#DDF1E4"},
        ]
    else:
        steps = [
            {"range": [0, 25], "color": "#DDF1E4"},
            {"range": [25, 50], "color": "#FFF4C2"},
            {"range": [50, 75], "color": "#FCE8D4"},
            {"range": [75, 100], "color": "#F9DEDC"},
        ]
    figure = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=numeric,
            number={
                "suffix": "%",
                "valueformat": ".1f",
                "font": {"size": 30, "color": PRIMARY_COLOR},
            },
            title={
                "text": title,
                "font": {"size": 15, "color": MUTED_TEXT_COLOR},
            },
            gauge={
                "shape": "angular",
                "axis": {
                    "range": [0, 100],
                    "tickvals": [0, 25, 50, 75, 100],
                    "tickfont": {"size": 10, "color": MUTED_TEXT_COLOR},
                },
                "bar": {"color": SECONDARY_COLOR, "thickness": 0.28},
                "bgcolor": "#E8EFF1",
                "borderwidth": 0,
                "steps": steps,
                "threshold": {
                    "line": {"color": PRIMARY_COLOR, "width": 3},
                    "thickness": 0.8,
                    "value": numeric,
                },
            },
        )
    )
    figure.update_layout(
        height=255,
        margin={"l": 22, "r": 22, "t": 55, "b": 16},
        paper_bgcolor=SURFACE_COLOR,
        font={"family": "Inter, Segoe UI, Arial", "color": TEXT_COLOR},
    )
    return figure


def primary_bri_dial_figure(
    bri: float,
    *,
    critical_override_active: bool,
) -> go.Figure:
    """Render the primary BRI dial without changing deployment semantics."""
    value = 0.0 if pd.isna(bri) else float(np.clip(bri, 0, 100))
    if value < 50:
        readiness = "LOW READINESS"
    elif value < 70:
        readiness = "LIMITED READINESS"
    elif value < 85:
        readiness = "MODERATE READINESS"
    else:
        readiness = "HIGH READINESS"
    status = (
        f"{readiness} — CRITICAL OVERRIDE ACTIVE"
        if critical_override_active
        else readiness
    )
    figure = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={
                "suffix": "%",
                "valueformat": ".1f",
                "font": {"size": 48, "color": PRIMARY_COLOR},
            },
            title={
                "text": "<b>BIOSECURITY READINESS INDEX</b>",
                "font": {"size": 17, "color": PRIMARY_COLOR},
            },
            gauge={
                "shape": "angular",
                "axis": {
                    "range": [0, 100],
                    "tickmode": "array",
                    "tickvals": [0, 20, 40, 60, 80, 100],
                    "ticktext": ["0", "20", "40", "60", "80", "100"],
                    "tickwidth": 1,
                    "tickcolor": MUTED_TEXT_COLOR,
                    "tickfont": {"size": 12, "color": MUTED_TEXT_COLOR},
                },
                "bar": {
                    "color": PRIMARY_COLOR,
                    "thickness": 0.22,
                },
                "bgcolor": "#EDF3F4",
                "borderwidth": 1,
                "bordercolor": BORDER_COLOR,
                "steps": [
                    {"range": [0, 50], "color": "#F5C9C6"},
                    {"range": [50, 70], "color": "#F8D7B5"},
                    {"range": [70, 85], "color": "#F9E89A"},
                    {"range": [85, 100], "color": "#CFE8D7"},
                ],
                "threshold": {
                    "line": {"color": PRIMARY_DARK, "width": 5},
                    "thickness": 0.9,
                    "value": value,
                },
            },
            domain={"x": [0.08, 0.92], "y": [0.2, 1]},
        )
    )
    figure.add_annotation(
        x=0.5,
        y=0.07,
        xref="paper",
        yref="paper",
        text=f"<b>{status}</b>",
        showarrow=False,
        font={
            "size": 13,
            "color": DANGER_COLOR if critical_override_active else PRIMARY_COLOR,
        },
        align="center",
    )
    figure.update_layout(
        height=355,
        margin={"l": 24, "r": 24, "t": 62, "b": 28},
        paper_bgcolor=SURFACE_COLOR,
        font={"family": "Inter, Segoe UI, Arial", "color": TEXT_COLOR},
    )
    return figure


def domain_figure(domains: pd.DataFrame) -> go.Figure:
    """Show score-ratio readiness for each available operational domain."""
    data = domains.sort_values("readiness_pct", ascending=True)
    figure = px.bar(
        data,
        x="readiness_pct",
        y="domain",
        orientation="h",
        text="readiness_pct",
        range_x=[0, 100],
        color_discrete_sequence=[SECONDARY_COLOR],
        labels={"readiness_pct": "Domain Readiness (%)", "domain": "Operational Domain"},
    )
    figure.update_traces(
        texttemplate="%{text:.1f}%",
        textposition="outside",
        cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>Readiness: %{x:.1f}%<extra></extra>",
    )
    height = max(360, min(760, 170 + 22 * len(data)))
    return apply_chart_theme(figure, title="Domain Readiness Overview", height=height)


def action_status_figure(actions: pd.DataFrame) -> go.Figure:
    """Show corrective-action status counts when action records exist."""
    counts = (
        actions.get("status", pd.Series(dtype="string"))
        .fillna("Not specified")
        .value_counts()
        .rename_axis("status")
        .reset_index(name="count")
    )
    figure = px.bar(
        counts,
        x="status",
        y="count",
        text="count",
        color_discrete_sequence=[SECONDARY_COLOR],
        labels={"status": "Action Status", "count": "Actions"},
    )
    figure.update_traces(textposition="outside", cliponaxis=False)
    return apply_chart_theme(figure, title="Corrective Action Status")
