"""Transparent deployment decision logic with non-bypassable safety overrides."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .config import (
    DECISION_CONDITIONAL,
    DECISION_DO_NOT_DEPLOY,
    DECISION_READY,
    RISK_LEVELS,
    count_phrase,
)
from .readiness import failed_critical_controls
from .risk import classify_risk


@dataclass(frozen=True)
class DeploymentPolicy:
    """Operational readiness bands supporting the approved decision rules."""

    bri_not_recommended: float = 70.0
    bri_ready: float = 85.0
    critical_default_threshold_ratio: float = 1.0


def decision_risk_column(hazards: pd.DataFrame) -> str:
    """Return the legacy dataset-level risk column name for external callers."""
    if "decision_risk_category" in hazards.columns:
        return "decision_risk_category"
    residual = hazards.get("residual_risk_category", pd.Series(dtype="string"))
    if not residual.empty and residual.notna().any() and residual.ne("Not provided").any():
        return "residual_risk_category"
    if "risk_category" in hazards.columns:
        return "risk_category"
    return "risk_level"


def decision_risk_values(hazards: pd.DataFrame) -> pd.Series:
    """Return the safest available decision category for each hazard record."""
    if "decision_risk_category" in hazards.columns:
        return hazards["decision_risk_category"].astype("string")
    initial = hazards.get(
        "risk_category",
        hazards.get(
            "risk_level",
            pd.Series(pd.NA, index=hazards.index, dtype="string"),
        ),
    ).astype("string")
    residual = hazards.get(
        "residual_risk_category",
        pd.Series(pd.NA, index=hazards.index, dtype="string"),
    ).astype("string")
    valid_residual = residual.isin(RISK_LEVELS)
    return residual.where(valid_residual, initial)


def decision_risk_basis(hazards: pd.DataFrame) -> str:
    """Describe whether decision risk is residual, initial, or a safe mixture."""
    if "decision_risk_source" in hazards.columns:
        sources = set(
            hazards["decision_risk_source"]
            .dropna()
            .astype("string")
            .tolist()
        )
        if sources == {"Residual risk"}:
            return "Residual risk"
        if "Residual risk" in sources:
            return "Residual risk with initial-risk fallback"
        return "Initial calculated risk"
    residual = hazards.get(
        "residual_risk_category",
        pd.Series(pd.NA, index=hazards.index, dtype="string"),
    ).astype("string")
    valid_residual = residual.isin(RISK_LEVELS)
    if not valid_residual.any():
        return "Initial calculated risk"
    initial = hazards.get(
        "risk_category",
        hazards.get(
            "risk_level",
            pd.Series(pd.NA, index=hazards.index, dtype="string"),
        ),
    ).astype("string")
    eligible = initial.isin(RISK_LEVELS) | valid_residual
    if eligible.any() and valid_residual[eligible].all():
        return "Residual risk"
    return "Residual risk with initial-risk fallback"


def _meaningful_text(series: pd.Series) -> pd.Series:
    normalized = series.astype("string").str.strip().str.lower()
    return series.notna() & ~normalized.isin(
        {"", "nan", "none", "not provided", "n/a", "na", "unknown"}
    )


def deployment_decision(
    hazards: pd.DataFrame,
    requirements: pd.DataFrame,
    bri: float,
    *,
    validation_errors: list[str] | None = None,
    policy: DeploymentPolicy | None = None,
) -> tuple[str, list[str]]:
    """Apply the approved MOBRA deployment rules in deterministic order.

    A high BRI never overrides failed critical controls, extreme residual risk,
    critical missing evidence, material validation errors, or an uncomputable
    readiness index.
    """
    policy = policy or DeploymentPolicy()
    reasons: list[str] = []
    validation_errors = [message for message in (validation_errors or []) if message]

    risk_values = decision_risk_values(hazards)
    risk_basis = decision_risk_basis(hazards)
    extreme_count = int(risk_values.eq("Extreme").sum())
    high_count = int(risk_values.eq("High").sum())
    failed = failed_critical_controls(requirements)

    if validation_errors:
        reasons.append(
            f"Critical data validation identified "
            f"{count_phrase(len(validation_errors), 'blocking error')}."
        )
    if pd.isna(bri):
        reasons.append(
            "Overall BRI cannot be calculated because valid observed and maximum scores are unavailable."
        )
    if extreme_count:
        qualifier = (
            "residual "
            if risk_basis == "Residual risk"
            else "decision-basis "
            if "fallback" in risk_basis
            else ""
        )
        reasons.append(
            f"{count_phrase(extreme_count, f'Extreme {qualifier}risk')} "
            f"{'remains' if extreme_count == 1 else 'remain'}."
        )
    if not failed.empty:
        reasons.append(
            f"{count_phrase(len(failed), 'critical control')} "
            f"{'is' if len(failed) == 1 else 'are'} not satisfied or "
            "lack required evidence."
        )

    if validation_errors or pd.isna(bri) or extreme_count or not failed.empty:
        return DECISION_DO_NOT_DEPLOY, reasons

    if bri < policy.bri_not_recommended:
        reasons.append(
            f"Overall BRI is {bri:.1f}%, below the {policy.bri_not_recommended:.0f}% "
            "minimum core-readiness band."
        )
        return DECISION_DO_NOT_DEPLOY, reasons

    if high_count:
        actions = hazards.get("corrective_action", pd.Series(pd.NA, index=hazards.index))
        high_mask = risk_values.eq("High")
        missing_action_count = int((high_mask & ~_meaningful_text(actions)).sum())
        if missing_action_count:
            reasons.append(
                f"{count_phrase(missing_action_count, 'High risk')} "
                f"{'does' if missing_action_count == 1 else 'do'} not have a "
                "defined corrective action."
            )
            return DECISION_DO_NOT_DEPLOY, reasons
        reasons.append(
            f"{count_phrase(high_count, 'manageable High risk')} "
            f"{'remains' if high_count == 1 else 'remain'} with documented "
            "corrective actions."
        )
        return DECISION_CONDITIONAL, reasons

    if bri < policy.bri_ready:
        reasons.append(
            f"Overall BRI is {bri:.1f}%; readiness improvements are required before full deployment."
        )
        return DECISION_CONDITIONAL, reasons

    return DECISION_READY, [
        "All critical controls are satisfied, no Extreme residual risk exists, "
        "required evidence is available, and core readiness requirements are met."
    ]


def evaluate_deployment_decision(
    bri: float,
    residual_risk_score: int,
    critical_control_passed: bool,
    *,
    high_risk_action_documented: bool = True,
    policy: DeploymentPolicy | None = None,
) -> tuple[str, list[str]]:
    """Evaluate one calculator scenario through the central deployment function.

    This adapter intentionally builds the smallest valid assessment context and
    delegates all decision rules to :func:`deployment_decision`; the UI does not
    maintain a second copy of safety-critical thresholds or override logic.
    """
    try:
        bri_value = float(bri)
        risk_value = float(residual_risk_score)
    except (TypeError, ValueError) as exc:
        raise ValueError("BRI and residual risk score must be numeric.") from exc
    if pd.isna(bri_value) or not 0 <= bri_value <= 100:
        raise ValueError("BRI must be between 0 and 100.")
    if (
        pd.isna(risk_value)
        or not risk_value.is_integer()
        or not 1 <= risk_value <= 25
    ):
        raise ValueError("Residual risk score must be an integer from 1 to 25.")
    if not isinstance(critical_control_passed, bool):
        raise ValueError("Critical-control status must be True or False.")

    risk_category = classify_risk(int(risk_value))
    hazards = pd.DataFrame(
        {
            "risk_category": [risk_category],
            "residual_risk_category": [risk_category],
            "decision_risk_category": [risk_category],
            "decision_risk_source": ["Residual risk"],
            "corrective_action": [
                "Documented mitigation action"
                if high_risk_action_documented
                else "Not provided"
            ],
        }
    )
    requirements = pd.DataFrame(
        {
            "requirement": ["Mission-critical containment control"],
            "observed_score": [5 if critical_control_passed else 4],
            "maximum_score": [5],
            "critical_control": [True],
            "objective_evidence": ["Verified"],
            "applicable": [True],
        }
    )
    return deployment_decision(
        hazards,
        requirements,
        bri_value,
        policy=policy,
    )
