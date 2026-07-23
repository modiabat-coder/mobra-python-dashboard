"""BRI and ORL readiness calculations."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _valid_requirements(requirements: pd.DataFrame) -> pd.DataFrame:
    if not {"observed_score", "maximum_score"}.issubset(requirements.columns):
        return requirements.iloc[0:0]
    valid = requirements["observed_score"].notna() & requirements["maximum_score"].notna()
    valid &= requirements["maximum_score"] > 0
    valid &= requirements["observed_score"] >= 0
    valid &= requirements["observed_score"] <= requirements["maximum_score"]
    if "bri_eligible" in requirements.columns:
        valid &= requirements["bri_eligible"].fillna(False).astype(bool)
    return requirements.loc[valid]


def calculate_bri(requirements: pd.DataFrame) -> float:
    """Calculate weighted BRI as observed points divided by maximum points."""
    valid = _valid_requirements(requirements)
    maximum = float(valid["maximum_score"].sum()) if not valid.empty else 0.0
    if maximum <= 0:
        return float("nan")
    observed = float(valid["observed_score"].sum())
    return float(np.clip(100 * observed / maximum, 0, 100))


def domain_readiness(requirements: pd.DataFrame) -> pd.DataFrame:
    """Calculate weighted readiness for each operational domain."""
    valid = _valid_requirements(requirements).copy()
    if "domain" not in valid.columns:
        valid["domain"] = "General"
    result = (
        valid.groupby("domain", dropna=False)
        .agg(
            observed_score=("observed_score", "sum"),
            maximum_score=("maximum_score", "sum"),
            requirement_count=("domain", "size"),
        )
        .reset_index()
    )
    if result.empty:
        result["readiness_pct"] = pd.Series(dtype=float)
        return result
    result["readiness_pct"] = 100 * result["observed_score"] / result["maximum_score"]
    return result.sort_values("readiness_pct", ascending=True).reset_index(drop=True)


def failed_critical_controls(
    requirements: pd.DataFrame,
    critical_profile: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Backward-compatible wrapper around structured critical-control assessment."""
    from .critical_controls import assess_critical_controls, legacy_critical_control_profile

    assessment_requirements = requirements.copy()
    if "requirement_id" not in assessment_requirements.columns:
        assessment_requirements.insert(
            0,
            "requirement_id",
            [f"R{i:03d}" for i in range(1, len(assessment_requirements) + 1)],
        )
    profile = (
        critical_profile if critical_profile is not None else legacy_critical_control_profile(assessment_requirements)
    )
    assessment = assess_critical_controls(assessment_requirements, profile)
    return assessment.deployment_blocking_failures


def data_quality_summary(hazards: pd.DataFrame, requirements: pd.DataFrame) -> dict[str, int | float]:
    """Summarize missing and incomplete values for the report."""
    total_cells = len(hazards) * max(len(hazards.columns), 1) + len(requirements) * max(len(requirements.columns), 1)
    missing = int(hazards.isna().sum().sum() + requirements.isna().sum().sum())
    return {
        "hazard_rows": len(hazards),
        "requirement_rows": len(requirements),
        "missing_values": missing,
        "missing_value_pct": round(100 * missing / max(total_cells, 1), 2),
        "incomplete_requirements": int(requirements.get("incomplete", pd.Series(dtype=bool)).fillna(False).sum()),
        "missing_evidence": int(requirements.get("evidence_missing", pd.Series(dtype=bool)).fillna(False).sum()),
    }
