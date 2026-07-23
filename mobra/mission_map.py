"""Synthetic, interactive mission-workflow map for MOBRA."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pydeck as pdk

from .config import (
    DECISION_CONDITIONAL,
    DECISION_DO_NOT_DEPLOY,
    DECISION_READY,
)

STATUS_COLORS = {
    "Completed": [35, 122, 69, 220],
    "In progress": [20, 125, 133, 220],
    "Conditional": [178, 94, 9, 220],
    "Blocked": [180, 35, 24, 230],
    "Not started": [123, 139, 145, 205],
    "Ready": [35, 122, 69, 220],
}


def synthetic_mission_stages(
    decision: str,
    bri: float,
    failed_controls: int,
    hazard_count: int,
) -> pd.DataFrame:
    """Build a clearly synthetic four-gate mission workflow.

    Coordinates are illustrative only. They do not identify a laboratory,
    incident, route, or operational site.
    """
    if decision == DECISION_READY:
        statuses = ["Completed", "Completed", "Ready", "Ready"]
        progress = [100, 100, 100, 100]
    elif decision == DECISION_CONDITIONAL:
        statuses = ["Completed", "Completed", "Conditional", "Not started"]
        progress = [100, 100, 75, 20]
    else:
        statuses = ["Completed", "In progress", "Blocked", "Not started"]
        progress = [100, 65, 35, 0]
    stages = [
        ("1", "Pre-deployment planning", "Review scope, hazards, requirements, and evidence.", 31.960, 35.845),
        ("2", "Mobilization readiness", "Confirm personnel, equipment, logistics, and controls.", 31.985, 35.895),
        ("3", "Site setup gate", "Apply non-bypassable Critical Control and risk gates.", 31.940, 35.955),
        ("4", "Operational activation", "Activate only when the formal deployment decision permits.", 31.900, 36.015),
    ]
    records: list[dict[str, Any]] = []
    for index, (stage_id, stage, description, latitude, longitude) in enumerate(stages):
        status = statuses[index]
        records.append(
            {
                "stage_id": stage_id,
                "stage": stage,
                "description": description,
                "status": status,
                "progress_pct": progress[index],
                "latitude": latitude,
                "longitude": longitude,
                "color": STATUS_COLORS[status],
                "radius": 620 + progress[index] * 3,
                "bri": round(float(bri), 1),
                "failed_controls": int(failed_controls),
                "hazard_count": int(hazard_count),
                "decision": decision,
            }
        )
    return pd.DataFrame(records)


def mission_map_deck(stages: pd.DataFrame) -> pdk.Deck:
    """Return an interactive PyDeck view with workflow nodes and tooltips."""
    if stages.empty:
        raise ValueError("Mission workflow requires at least one stage.")
    path = stages[["longitude", "latitude"]].values.tolist()
    path_layer = pdk.Layer(
        "PathLayer",
        data=[{"path": path, "color": [20, 125, 133, 150]}],
        get_path="path",
        get_color="color",
        width_scale=16,
        width_min_pixels=3,
        get_width=4,
        pickable=False,
    )
    node_layer = pdk.Layer(
        "ScatterplotLayer",
        data=stages,
        get_position="[longitude, latitude]",
        get_fill_color="color",
        get_line_color=[255, 255, 255, 245],
        get_radius="radius",
        line_width_min_pixels=2,
        stroked=True,
        filled=True,
        pickable=True,
        auto_highlight=True,
    )
    label_layer = pdk.Layer(
        "TextLayer",
        data=stages,
        get_position="[longitude, latitude]",
        get_text="stage_id",
        get_color=[255, 255, 255, 255],
        get_size=16,
        get_alignment_baseline="'center'",
        get_text_anchor="'middle'",
        pickable=False,
    )
    view_state = pdk.ViewState(
        latitude=float(stages["latitude"].mean()),
        longitude=float(stages["longitude"].mean()),
        zoom=10.2,
        pitch=25,
        bearing=-8,
    )
    tooltip = {
        "html": (
            "<b>Stage {stage_id}: {stage}</b><br/>"
            "Status: {status}<br/>Progress: {progress_pct}%<br/>"
            "BRI: {bri}% · Failed critical controls: {failed_controls}<br/>"
            "Hazards reviewed: {hazard_count}<br/><br/>{description}"
        ),
        "style": {
            "backgroundColor": "#103B4D",
            "color": "#FFFFFF",
            "fontSize": "12px",
        },
    }
    return pdk.Deck(
        layers=[path_layer, node_layer, label_layer],
        initial_view_state=view_state,
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        tooltip=tooltip,
    )
