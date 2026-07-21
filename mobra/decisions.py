"""Transparent deployment decision logic with non-bypassable overrides."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .readiness import failed_critical_controls


@dataclass(frozen=True)
class DeploymentPolicy:
    """Configurable thresholds; defaults preserve the supplied MOBRA rules."""

    bri_not_recommended: float = 70.0
    bri_ready: float = 85.0
    critical_default_threshold_ratio: float = 1.0


def _decision_risk_column(hazards: pd.DataFrame) -> str:
    if "residual_risk_category" in hazards.columns and hazards["residual_risk_category"].ne("Not provided").any():
        return "residual_risk_category"
    if "risk_category" in hazards.columns:
        return "risk_category"
    return "risk_level"


def deployment_decision(
    hazards: pd.DataFrame,
    requirements: pd.DataFrame,
    bri: float,
    *,
    validation_errors: list[str] | None = None,
    policy: DeploymentPolicy | None = None,
) -> tuple[str, list[str]]:
    """Apply BRI thresholds and mandatory safety overrides in deterministic order."""
    policy = policy or DeploymentPolicy()
    reasons: list[str] = []
    if validation_errors:
        reasons.append(f"Data validation has {len(validation_errors)} error(s).")
    if pd.isna(bri):
        reasons.append("BRI cannot be calculated because no valid maximum score is available.")

    risk_column = _decision_risk_column(hazards)
    extreme_count = int(hazards.get(risk_column, pd.Series(dtype=str)).eq("Extreme").sum())
    high_count = int(hazards.get(risk_column, pd.Series(dtype=str)).eq("High").sum())
    failed = failed_critical_controls(requirements)
    if extreme_count:
        reasons.append(f"{extreme_count} extreme residual risk(s) remain uncontrolled.")
    if not failed.empty:
        reasons.append(f"{len(failed)} critical control(s) are below their accepted threshold or incomplete.")
    critical_flags = requirements.get("critical_control", pd.Series(False, index=requirements.index))
    if critical_flags.dtype == bool:
        critical_flags = critical_flags.fillna(False)
    else:
        critical_flags = critical_flags.astype("string").str.strip().str.lower().isin(["true", "1", "yes", "y", "critical"])
    invalid_critical = critical_flags & requirements.get("incomplete", pd.Series(False, index=requirements.index)).fillna(False).astype(bool)
    if int(invalid_critical.sum()):
        reasons.append(f"{int(invalid_critical.sum())} critical record(s) are incomplete and require review.")
    if validation_errors:
        return "DO NOT DEPLOY", reasons
    if extreme_count or not failed.empty or pd.isna(bri):
        return "DO NOT DEPLOY", reasons
    if bri < policy.bri_not_recommended:
        reasons.append(f"Overall BRI is below the {policy.bri_not_recommended:.0f}% operational threshold ({bri:.1f}%).")
        return "DEPLOYMENT NOT RECOMMENDED", reasons
    if bri < policy.bri_ready or high_count:
        if high_count:
            reasons.append(f"{high_count} high residual risk(s) remain; corrective action and approval are required.")
        else:
            reasons.append(f"BRI is in the conditional band ({bri:.1f}%).")
        return "CONDITIONAL DEPLOYMENT", reasons
    return "READY FOR DEPLOYMENT", ["No extreme residual risks or failed critical controls were detected."]
