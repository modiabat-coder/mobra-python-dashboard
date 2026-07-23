"""Presentation helpers for the MOBRA professional interface.

The functions in this module intentionally contain no risk or readiness logic.
They only shape navigation, validation summaries, and human-readable tables so
that the Streamlit layer can present the existing verified outputs clearly.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

import pandas as pd

NAVIGATION_ITEMS: tuple[str, ...] = (
    "Home",
    "Assessment",
    "Validation",
    "Readiness",
    "Hazards",
    "Mapping",
    "Critical Controls",
    "Reports",
    "Resources",
)

DISPLAY_MODES: tuple[str, ...] = ("Standard", "Technical")

FRIENDLY_COLUMN_LABELS: Mapping[str, str] = {
    "hazard_id": "Hazard ID",
    "hazard_name": "Hazard",
    "hazard_description": "Description",
    "likelihood": "Likelihood",
    "consequence": "Consequence",
    "risk_score": "Risk score",
    "risk_category": "Risk category",
    "inherent_risk_score": "Inherent score",
    "inherent_risk_category": "Inherent category",
    "residual_risk_score": "Residual score",
    "residual_risk_category": "Residual category",
    "requirement_id": "Requirement ID",
    "requirement_wording": "Requirement",
    "requirement_domain": "Domain",
    "observed_score": "Observed score",
    "maximum_score": "Maximum score",
    "readiness_pct": "Readiness (%)",
    "mapping_id": "Mapping ID",
    "relationship_type": "Relationship",
    "mapping_rationale": "Rationale",
    "critical_link": "Critical link",
    "finding_id": "Finding ID",
    "dataset_type": "Dataset",
    "row_index": "Source row",
    "record_id": "Record ID",
    "column": "Column",
    "original_value": "Original value",
    "severity": "Severity",
    "code": "Finding code",
    "message": "Finding",
    "suggested_action": "Suggested action",
    "blocks_analysis": "Blocks analysis",
}


def friendly_frame(frame: pd.DataFrame, *, columns: Iterable[str] | None = None) -> pd.DataFrame:
    """Return a display copy with concise human-readable column labels."""

    selected = list(columns) if columns is not None else list(frame.columns)
    selected = [column for column in selected if column in frame.columns]
    return frame.loc[:, selected].rename(columns=lambda column: FRIENDLY_COLUMN_LABELS.get(column, column))


def validation_severity_summary(findings: Iterable[object]) -> dict[str, int]:
    """Count findings by the stable severity labels used by MOBRA validation."""

    counts = {"Error": 0, "Warning": 0, "Information": 0}
    for finding in findings:
        severity = getattr(finding, "severity", None)
        if severity in counts:
            counts[severity] += 1
    return counts


def validation_importance_summary(findings: Iterable[object]) -> dict[str, int]:
    """Group findings into user-facing action bands without changing severity."""

    groups = {
        "Critical": 0,
        "Action required": 0,
        "Review recommended": 0,
        "Informational": 0,
    }
    for finding in findings:
        severity = getattr(finding, "severity", "Information")
        blocks = bool(getattr(finding, "blocks_analysis", False))
        if severity == "Error" and blocks:
            groups["Critical"] += 1
        elif severity == "Error":
            groups["Action required"] += 1
        elif severity == "Warning":
            groups["Review recommended"] += 1
        else:
            groups["Informational"] += 1
    return groups


def prioritized_findings(
    findings: Iterable[object], *, critical_limit: int = 3, important_limit: int = 5
) -> list[object]:
    """Return a bounded alert list for the page header.

    Full findings remain available in the Validation page and its downloads.
    """

    critical: list[object] = []
    important: list[object] = []
    for finding in findings:
        severity = getattr(finding, "severity", "Information")
        if severity == "Error" and bool(getattr(finding, "blocks_analysis", False)):
            critical.append(finding)
        elif severity in {"Error", "Warning"}:
            important.append(finding)
    return [*critical[:critical_limit], *important[:important_limit]]
