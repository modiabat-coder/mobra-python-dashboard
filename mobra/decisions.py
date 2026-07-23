"""Transparent deployment decision logic with non-bypassable safety overrides."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .config import (
    DECISION_CONDITIONAL,
    DECISION_DO_NOT_DEPLOY,
    DECISION_READY,
    count_phrase,
)
from .readiness import failed_critical_controls


@dataclass(frozen=True)
class DeploymentPolicy:
    """Operational readiness bands supporting the approved decision rules."""

    bri_not_recommended: float = 70.0
    bri_ready: float = 85.0
    critical_default_threshold_ratio: float = 1.0


def decision_risk_column(hazards: pd.DataFrame) -> str:
    """Choose residual risk when supplied; otherwise use current calculated risk."""
    residual = hazards.get("residual_risk_category", pd.Series(dtype="string"))
    if not residual.empty and residual.notna().any() and residual.ne("Not provided").any():
        return "residual_risk_category"
    if "risk_category" in hazards.columns:
        return "risk_category"
    return "risk_level"


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

    risk_column = decision_risk_column(hazards)
    risk_values = hazards.get(risk_column, pd.Series(dtype="string"))
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
        qualifier = "residual " if risk_column == "residual_risk_category" else ""
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
