"""Transparent deployment decision logic with non-bypassable overrides."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .acceptance import RiskAcceptancePolicy, apply_risk_acceptance, risk_source_summary
from .critical_controls import CriticalControlAssessment
from .readiness import failed_critical_controls


@dataclass(frozen=True)
class DeploymentPolicy:
    """Configurable thresholds; defaults preserve the supplied MOBRA rules."""

    bri_not_recommended: float = 70.0
    bri_ready: float = 85.0
    critical_default_threshold_ratio: float = 1.0


def _critical_flags(requirements: pd.DataFrame) -> pd.Series:
    flags = requirements.get("critical_control", pd.Series(False, index=requirements.index))
    if flags.dtype == bool:
        return flags.fillna(False)
    return flags.astype("string").str.strip().str.lower().isin(["true", "1", "yes", "y", "critical"])


def _append_reason(reasons: list[str], reason: str) -> None:
    if reason not in reasons:
        reasons.append(reason)


def _finding_items(findings: pd.DataFrame, limit: int = 5) -> str:
    items = [
        f"{row['requirement_id']} ({row.get('requirement', 'description unavailable')})"
        for _, row in findings.head(limit).iterrows()
    ]
    if len(findings) > limit:
        items.append(f"and {len(findings) - limit} more")
    return "; ".join(items)


def deployment_decision(
    hazards: pd.DataFrame,
    requirements: pd.DataFrame,
    bri: float,
    *,
    validation_errors: list[str] | None = None,
    policy: DeploymentPolicy | None = None,
    risk_acceptance_policy: RiskAcceptancePolicy | None = None,
    critical_control_assessment: CriticalControlAssessment | None = None,
) -> tuple[str, list[str]]:
    """Apply BRI thresholds, explicit risk sources, and mandatory overrides."""
    policy = policy or DeploymentPolicy()
    acceptance_policy = risk_acceptance_policy or RiskAcceptancePolicy()
    analyzed = apply_risk_acceptance(hazards, acceptance_policy)
    reasons: list[str] = []
    hard_block = False
    conditional_cap = False

    if validation_errors:
        _append_reason(reasons, f"Data validation has {len(validation_errors)} error(s); deployment cannot proceed.")
        hard_block = True
    if pd.isna(bri):
        _append_reason(reasons, "BRI cannot be calculated because no valid maximum score is available.")
        hard_block = True

    if critical_control_assessment is not None:
        if not critical_control_assessment.ok:
            _append_reason(
                reasons,
                "Critical-control profile validation failed; automatic READY is unavailable pending manual review.",
            )
            conditional_cap = True
        else:
            blocking = critical_control_assessment.deployment_blocking_failures
            conditional = critical_control_assessment.conditional_gaps
            important = critical_control_assessment.important_gaps
            manual = critical_control_assessment.manual_review_items
            if not blocking.empty:
                _append_reason(
                    reasons,
                    f"{len(blocking)} deployment-blocking critical-control failure(s): {_finding_items(blocking)}. "
                    "A high BRI cannot override a deployment-blocking critical-control failure.",
                )
                hard_block = True
            if not conditional.empty:
                _append_reason(
                    reasons,
                    f"{len(conditional)} conditional critical-control gap(s) cap the decision at CONDITIONAL DEPLOYMENT: "
                    f"{_finding_items(conditional)}. Corrective action, a named owner, target date, formal approval, "
                    "and a compensating control are required.",
                )
                conditional_cap = True
            if not manual.empty:
                _append_reason(
                    reasons,
                    f"{len(manual)} critical-control item(s) require manual review and prevent automatic READY: "
                    f"{_finding_items(manual)}.",
                )
                conditional_cap = True
            if not important.empty:
                _append_reason(
                    reasons,
                    f"{len(important)} Important control finding(s) require corrective action without an automatic "
                    f"deployment block: {_finding_items(important)}.",
                )
    else:
        incomplete_flags = (
            requirements.get("incomplete", pd.Series(False, index=requirements.index)).fillna(False).astype(bool)
        )
        incomplete_critical = _critical_flags(requirements) & incomplete_flags
        failed = failed_critical_controls(requirements)
        threshold_failed = failed.loc[~failed.index.isin(requirements.index[incomplete_critical])]
        if not threshold_failed.empty:
            _append_reason(reasons, f"{len(threshold_failed)} critical control(s) are below their accepted threshold.")
            hard_block = True
        incomplete_count = int(incomplete_critical.sum())
        if incomplete_count:
            _append_reason(reasons, f"{incomplete_count} critical record(s) are incomplete and require review.")
            hard_block = True

    source = analyzed["decision_risk_source"]
    category = analyzed["decision_risk_category"]
    residual_extreme_count = int(((source == "Residual") & (category == "Extreme")).sum())
    residual_high_count = int(((source == "Residual") & (category == "High")).sum())
    inherent_extreme_count = int(((source == "Inherent") & (category == "Extreme")).sum())
    inherent_high_count = int(((source == "Inherent") & (category == "High")).sum())
    missing_residual_count = int(source.ne("Residual").sum())

    if residual_extreme_count:
        _append_reason(
            reasons,
            f"{residual_extreme_count} hazard(s) have Extreme residual risk; deployment is blocked until risk is reduced and reassessed.",
        )
        hard_block = True

    source_summary = risk_source_summary(analyzed)
    if source_summary["risk_source_used"] == "Mixed":
        _append_reason(
            reasons,
            "Mixed decision-risk sources were used: "
            f"{source_summary['residual_hazard_count']} hazard(s) used residual data, "
            f"{source_summary['inherent_screening_hazard_count']} used inherent screening, and "
            f"{source_summary['unavailable_hazard_count']} were unavailable.",
        )
    elif source_summary["risk_source_used"] == "Inherent":
        _append_reason(
            reasons,
            f"{source_summary['inherent_screening_hazard_count']} hazard(s) use inherent risk for screening because residual assessments were not provided.",
        )
    elif source_summary["risk_source_used"] == "Unavailable":
        _append_reason(reasons, "No valid inherent or residual decision-risk category is available.")

    if missing_residual_count and acceptance_policy.missing_residual_policy == "require_residual_assessment":
        _append_reason(
            reasons,
            f"Policy requires residual assessment, but {missing_residual_count} hazard(s) do not have one.",
        )
        hard_block = True
    elif missing_residual_count and acceptance_policy.missing_residual_policy == "not_assessable":
        _append_reason(
            reasons,
            f"Policy marks {missing_residual_count} hazard(s) without residual assessment as Not assessable.",
        )
        hard_block = True

    if residual_high_count:
        _append_reason(
            reasons,
            f"{residual_high_count} hazard(s) have High residual risk; corrective action and formal approval are required.",
        )
        conditional_cap = True
    if inherent_extreme_count:
        _append_reason(
            reasons,
            f"{inherent_extreme_count} hazard(s) have Extreme inherent screening risk and are missing residual assessment.",
        )
        conditional_cap = True
    if inherent_high_count:
        _append_reason(
            reasons,
            f"{inherent_high_count} hazard(s) have High inherent screening risk that remains to be reassessed after controls.",
        )
        if acceptance_policy.require_residual_for_ready_decision:
            conditional_cap = True
    if missing_residual_count and acceptance_policy.require_residual_for_ready_decision:
        _append_reason(
            reasons,
            f"Policy requires residual assessment for READY; {missing_residual_count} hazard(s) are missing residual assessment.",
        )
        conditional_cap = True

    if hard_block:
        return "DO NOT DEPLOY", reasons
    if bri < policy.bri_not_recommended:
        _append_reason(
            reasons,
            f"Overall BRI is below the {policy.bri_not_recommended:.0f}% operational threshold ({bri:.1f}%).",
        )
        return "DEPLOYMENT NOT RECOMMENDED", reasons
    if bri < policy.bri_ready:
        _append_reason(reasons, f"BRI is in the conditional band ({bri:.1f}%).")
        return "CONDITIONAL DEPLOYMENT", reasons
    if conditional_cap:
        return "CONDITIONAL DEPLOYMENT", reasons
    _append_reason(reasons, f"BRI is {bri:.1f}% and no mandatory deployment override was detected.")
    return "READY FOR DEPLOYMENT", reasons
