"""Corrective-action normalization across hazards and requirements."""

from __future__ import annotations

import pandas as pd

from .readiness import failed_critical_controls


def _field(
    frame: pd.DataFrame,
    name: str,
    default: object = "Not provided",
) -> pd.Series:
    if name in frame.columns:
        return frame[name]
    return pd.Series(default, index=frame.index)


def _priority_from_risk(category: object) -> str:
    return {
        "Extreme": "Critical",
        "High": "High",
        "Moderate": "Medium",
        "Low": "Low",
    }.get(str(category), "Medium")


def build_corrective_actions(
    hazards: pd.DataFrame,
    requirements: pd.DataFrame,
) -> pd.DataFrame:
    """Build one structured action register without fabricating source values."""
    records: list[dict[str, object]] = []
    risk_column = (
        "residual_risk_category"
        if "residual_risk_category" in hazards.columns
        and hazards["residual_risk_category"].isin(
            ["Low", "Moderate", "High", "Extreme"]
        ).any()
        else "risk_category"
    )
    for index, row in hazards.iterrows():
        action = row.get("corrective_action", "Not provided")
        category = row.get(risk_column, row.get("risk_category", "Unknown"))
        if str(action).strip().lower() in {"", "nan", "none", "not provided"} and category not in {
            "High",
            "Extreme",
        }:
            continue
        target = row.get("due_date", pd.NA)
        records.append(
            {
                "action_id": f"HA-{row.get('hazard_id', index + 1)}",
                "action": action,
                "related_item": row.get("hazard", row.get("hazard_id", "Hazard")),
                "source_type": "Hazard",
                "priority": _priority_from_risk(category),
                "responsible_person": row.get("responsible_person", "Not provided"),
                "target_date": target,
                "status": row.get("status", "Not provided"),
                "overdue": bool(row.get("overdue", False)),
                "evidence_of_completion": row.get("objective_evidence", "Not provided"),
            }
        )

    failed = failed_critical_controls(requirements)
    failed_ids = set(failed.index)
    for index, row in requirements.iterrows():
        action = row.get("corrective_action", "Not provided")
        action_present = str(action).strip().lower() not in {
            "",
            "nan",
            "none",
            "not provided",
        }
        if not action_present and index not in failed_ids:
            continue
        records.append(
            {
                "action_id": f"RA-{row.get('requirement_id', index + 1)}",
                "action": action,
                "related_item": row.get(
                    "requirement",
                    row.get("requirement_id", "Requirement"),
                ),
                "source_type": "Requirement",
                "priority": "Critical" if index in failed_ids else "Medium",
                "responsible_person": row.get("responsible_person", "Not provided"),
                "target_date": row.get("due_date", pd.NA),
                "status": row.get("compliance_status", "Not provided"),
                "overdue": bool(row.get("overdue", False)),
                "evidence_of_completion": row.get("objective_evidence", "Not provided"),
            }
        )
    columns = [
        "action_id",
        "action",
        "related_item",
        "source_type",
        "priority",
        "responsible_person",
        "target_date",
        "status",
        "overdue",
        "evidence_of_completion",
    ]
    actions = pd.DataFrame(records, columns=columns)
    if actions.empty:
        return actions
    priority_order = pd.CategoricalDtype(
        ["Critical", "High", "Medium", "Low"],
        ordered=True,
    )
    actions["priority"] = actions["priority"].astype(priority_order)
    return actions.sort_values(
        ["priority", "overdue"],
        ascending=[True, False],
    ).reset_index(drop=True)
