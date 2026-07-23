"""Transparent, provisional risk-acceptance rules for MOBRA decision support."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from .risk import RISK_LEVELS, classify_risk, valid_scale

ACCEPTANCE_DISPOSITIONS = (
    "Acceptable",
    "Acceptable with monitoring",
    "Conditional",
    "Unacceptable",
    "Not assessable",
)
MISSING_RESIDUAL_POLICIES = (
    "use_inherent_for_screening",
    "require_residual_assessment",
    "not_assessable",
)
RISK_ACCEPTANCE_LIMITATION = (
    "Risk-acceptance dispositions are provisional MOBRA decision-support rules. "
    "They require institutional approval and expert validation before operational use."
)


@dataclass(frozen=True)
class RiskAcceptancePolicy:
    """Configurable provisional dispositions without changing risk boundaries."""

    low_disposition: str = "Acceptable"
    moderate_disposition: str = "Acceptable with monitoring"
    high_disposition: str = "Conditional"
    extreme_disposition: str = "Unacceptable"
    high_requires_corrective_action: bool = True
    high_requires_formal_approval: bool = True
    extreme_blocks_deployment: bool = True
    missing_residual_policy: str = "use_inherent_for_screening"
    require_residual_for_ready_decision: bool = False

    def __post_init__(self) -> None:
        dispositions = {
            self.low_disposition,
            self.moderate_disposition,
            self.high_disposition,
            self.extreme_disposition,
        }
        invalid = dispositions.difference(ACCEPTANCE_DISPOSITIONS)
        if invalid:
            raise ValueError(f"Unsupported risk-acceptance disposition(s): {', '.join(sorted(invalid))}.")
        if self.missing_residual_policy not in MISSING_RESIDUAL_POLICIES:
            raise ValueError("missing_residual_policy must be one of: " + ", ".join(MISSING_RESIDUAL_POLICIES) + ".")
        if not self.extreme_blocks_deployment:
            raise ValueError("Extreme residual risk is a mandatory non-bypassable deployment block.")

    def disposition_for(self, category: str) -> str:
        """Return the configured disposition for a fixed MOBRA risk category."""
        return {
            "Low": self.low_disposition,
            "Moderate": self.moderate_disposition,
            "High": self.high_disposition,
            "Extreme": self.extreme_disposition,
        }.get(category, "Not assessable")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe policy representation."""
        return asdict(self)


def _valid_category(value: object) -> bool:
    return isinstance(value, str) and value.strip() in RISK_LEVELS


def _valid_score(value: object) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return np.isfinite(number) and 1 <= number <= 25


def _value(row: pd.Series, column: str) -> object:
    return row[column] if column in row.index else None


def _risk_from_pair(row: pd.Series, likelihood_column: str, consequence_column: str) -> tuple[float, str] | None:
    likelihood = _value(row, likelihood_column)
    consequence = _value(row, consequence_column)
    if not (valid_scale(likelihood) and valid_scale(consequence)):
        return None
    score = float(likelihood) * float(consequence)
    return score, classify_risk(score)


def _risk_from_calculated(row: pd.Series, score_column: str, category_column: str) -> tuple[float, str] | None:
    category = _value(row, category_column)
    score = _value(row, score_column)
    if not _valid_category(category):
        return None
    return (float(score) if _valid_score(score) else float("nan"), str(category).strip())


def _risk_source_for_row(row: pd.Series) -> tuple[float, str, str]:
    residual_allowed = "residual_risk_eligible" not in row.index or bool(row.get("residual_risk_eligible", False))
    residual = _risk_from_pair(row, "residual_likelihood", "residual_consequence") if residual_allowed else None
    if residual is None and residual_allowed:
        residual = _risk_from_calculated(row, "residual_risk_score", "residual_risk_category")
    if residual is not None:
        return residual[0], residual[1], "Residual"

    inherent_allowed = "inherent_risk_eligible" not in row.index or bool(row.get("inherent_risk_eligible", False))
    inherent = _risk_from_pair(row, "likelihood", "consequence") if inherent_allowed else None
    if inherent is None and inherent_allowed:
        inherent = _risk_from_calculated(row, "risk_score", "risk_category")
    if inherent is not None:
        return inherent[0], inherent[1], "Inherent"
    return float("nan"), "Not assessable", "Unavailable"


def _action_for(category: str, source: str, policy: RiskAcceptancePolicy) -> str:
    if source == "Unavailable":
        return "Provide valid inherent data and complete a residual-risk assessment before acceptance"
    if source == "Inherent" and policy.missing_residual_policy != "use_inherent_for_screening":
        return "Complete a valid residual-risk assessment before acceptance"
    if category == "High":
        if policy.high_requires_corrective_action and policy.high_requires_formal_approval:
            return (
                "Corrective action, documented responsible person, target date, and formal approval before acceptance"
            )
        if policy.high_requires_corrective_action:
            return "Corrective action, documented responsible person, and target date before acceptance"
        if policy.high_requires_formal_approval:
            return "Documented formal approval before acceptance"
        return "Maintain controls, monitor indicators, and document the acceptance decision"
    return {
        "Low": "Routine controls and periodic review",
        "Moderate": "Maintain controls, monitor indicators, and review changes",
        "Extreme": "Stop or prohibit deployment/activity until risk is reduced and formally reassessed",
    }.get(category, "Complete a valid risk assessment before acceptance")


def _reason_for(category: str, source: str, status: str, policy: RiskAcceptancePolicy) -> str:
    if source == "Residual":
        return f"Valid residual-risk data produced a {category} decision-support category; provisional disposition: {status}."
    if source == "Inherent":
        screening = f"Inherent risk produced a {category} screening category because residual scoring was not supplied."
        if policy.missing_residual_policy == "use_inherent_for_screening":
            return f"{screening} Provisional screening disposition: {status}."
        if policy.missing_residual_policy == "require_residual_assessment":
            return f"{screening} Policy requires a residual assessment, so acceptance is Not assessable."
        return f"{screening} Policy marks hazards without residual assessment as Not assessable."
    return "No valid inherent or residual risk category is available; acceptance is Not assessable."


def apply_risk_acceptance(
    hazards: pd.DataFrame,
    policy: RiskAcceptancePolicy | None = None,
) -> pd.DataFrame:
    """Return an analysis copy with explicit source and provisional acceptance fields."""
    policy = policy or RiskAcceptancePolicy()
    analyzed = hazards.copy()
    records: list[dict[str, object]] = []
    for _, row in analyzed.iterrows():
        score, category, source = _risk_source_for_row(row)
        if source == "Inherent" and policy.missing_residual_policy != "use_inherent_for_screening":
            status = "Not assessable"
        elif source == "Unavailable":
            status = "Not assessable"
        else:
            status = policy.disposition_for(category)
        high = category == "High" and source != "Unavailable"
        extreme = category == "Extreme" and source != "Unavailable"
        records.append(
            {
                "decision_risk_score": score,
                "decision_risk_category": category,
                "decision_risk_source": source,
                "risk_acceptance_status": status,
                "acceptance_action_required": _action_for(category, source, policy),
                "acceptance_reason": _reason_for(category, source, status, policy),
                "corrective_action_required": bool(extreme or (high and policy.high_requires_corrective_action)),
                "formal_approval_required": bool(extreme or (high and policy.high_requires_formal_approval)),
                "residual_assessment_missing": source != "Residual",
            }
        )
    calculated_columns = [
        "decision_risk_score",
        "decision_risk_category",
        "decision_risk_source",
        "risk_acceptance_status",
        "acceptance_action_required",
        "acceptance_reason",
        "corrective_action_required",
        "formal_approval_required",
        "residual_assessment_missing",
    ]
    calculated = pd.DataFrame(records, index=analyzed.index, columns=calculated_columns)
    for column in calculated.columns:
        analyzed[column] = calculated[column]
    return analyzed


def risk_source_summary(hazards: pd.DataFrame) -> dict[str, Any]:
    """Summarize per-hazard sources without silently combining them."""
    sources = hazards.get("decision_risk_source", pd.Series("Unavailable", index=hazards.index, dtype=str))
    counts = sources.value_counts().reindex(["Residual", "Inherent", "Unavailable"], fill_value=0).astype(int)
    present = [source for source in ("Residual", "Inherent", "Unavailable") if counts[source] > 0]
    if not present:
        overall = "Unavailable"
    elif len(present) == 1:
        overall = present[0]
    else:
        overall = "Mixed"
    display = "Inherent screening" if overall == "Inherent" else overall
    return {
        "risk_source_used": overall,
        "risk_source_display": display,
        "residual_hazard_count": int(counts["Residual"]),
        "inherent_screening_hazard_count": int(counts["Inherent"]),
        "unavailable_hazard_count": int(counts["Unavailable"]),
    }


def acceptance_status_counts(hazards: pd.DataFrame) -> dict[str, int]:
    """Return all controlled dispositions in stable display order."""
    statuses = hazards.get("risk_acceptance_status", pd.Series(dtype=str))
    return statuses.value_counts().reindex(ACCEPTANCE_DISPOSITIONS, fill_value=0).astype(int).to_dict()


def risk_acceptance_summary(hazards: pd.DataFrame, policy: RiskAcceptancePolicy) -> dict[str, Any]:
    """Build the stable summary used by UI, JSON, Excel, and reporting."""
    source = risk_source_summary(hazards)
    return {
        "risk_source_summary": source,
        "acceptance_status_counts": acceptance_status_counts(hazards),
        "unacceptable_hazard_count": int(
            hazards.get("risk_acceptance_status", pd.Series(dtype=str)).eq("Unacceptable").sum()
        ),
        "corrective_action_required_count": int(
            hazards.get("corrective_action_required", pd.Series(False, index=hazards.index))
            .fillna(False)
            .astype(bool)
            .sum()
        ),
        "formal_approval_required_count": int(
            hazards.get("formal_approval_required", pd.Series(False, index=hazards.index))
            .fillna(False)
            .astype(bool)
            .sum()
        ),
        "missing_residual_assessment_count": int(
            hazards.get("residual_assessment_missing", pd.Series(True, index=hazards.index))
            .fillna(True)
            .astype(bool)
            .sum()
        ),
        "risk_acceptance_policy": policy.to_dict(),
        "risk_acceptance_limitations": RISK_ACCEPTANCE_LIMITATION,
    }


def risk_acceptance_summary_table(hazards: pd.DataFrame, policy: RiskAcceptancePolicy) -> pd.DataFrame:
    """Return a two-column summary suitable for an Excel worksheet."""
    summary = risk_acceptance_summary(hazards, policy)
    rows: list[dict[str, object]] = []
    source = summary["risk_source_summary"]
    rows.extend({"metric": key, "value": value} for key, value in source.items())
    rows.extend(
        {"metric": f"acceptance_status_{status}", "value": count}
        for status, count in summary["acceptance_status_counts"].items()
    )
    for key in (
        "unacceptable_hazard_count",
        "corrective_action_required_count",
        "formal_approval_required_count",
        "missing_residual_assessment_count",
    ):
        rows.append({"metric": key, "value": summary[key]})
    rows.extend({"metric": f"policy_{key}", "value": value} for key, value in summary["risk_acceptance_policy"].items())
    rows.append({"metric": "risk_acceptance_limitations", "value": RISK_ACCEPTANCE_LIMITATION})
    return pd.DataFrame(rows)
