"""BRI and ORL readiness calculations."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .calculations import (
    calculate_bri_from_totals,
    calculate_domain_readiness_from_totals,
)


def _applicable_mask(requirements: pd.DataFrame) -> pd.Series:
    """Return the rows that belong in readiness numerators and denominators."""
    if "applicable" not in requirements.columns:
        return pd.Series(True, index=requirements.index, dtype=bool)
    flags = requirements["applicable"]
    if flags.dtype == bool:
        return flags.fillna(True)
    normalized = flags.astype("string").str.strip().str.lower()
    false_values = {"false", "0", "no", "n", "not applicable", "n/a", "na"}
    return ~normalized.isin(false_values)


def _valid_requirements(requirements: pd.DataFrame) -> pd.DataFrame:
    if not {"observed_score", "maximum_score"}.issubset(requirements.columns):
        return requirements.iloc[0:0]
    valid = _applicable_mask(requirements)
    valid &= requirements["observed_score"].notna() & requirements["maximum_score"].notna()
    valid &= requirements["maximum_score"] > 0
    valid &= requirements["observed_score"] >= 0
    valid &= requirements["observed_score"] <= requirements["maximum_score"]
    return requirements.loc[valid]


def calculate_bri(requirements: pd.DataFrame) -> float:
    """Calculate the current unweighted BRI as observed points over maximum points."""
    valid = _valid_requirements(requirements)
    maximum = float(valid["maximum_score"].sum()) if not valid.empty else 0.0
    if maximum <= 0:
        return float("nan")
    observed = float(valid["observed_score"].sum())
    return float(np.clip(calculate_bri_from_totals(observed, maximum), 0, 100))


def domain_readiness(requirements: pd.DataFrame) -> pd.DataFrame:
    """Calculate score-ratio readiness for each operational domain."""
    valid = _valid_requirements(requirements).copy()
    if "domain" not in valid.columns:
        valid["domain"] = "General"
    result = (
        valid.groupby("domain", dropna=False)
        .agg(observed_score=("observed_score", "sum"), maximum_score=("maximum_score", "sum"), requirement_count=("domain", "size"))
        .reset_index()
    )
    if result.empty:
        result["readiness_pct"] = pd.Series(dtype=float)
        return result
    result["readiness_pct"] = result.apply(
        lambda row: calculate_domain_readiness_from_totals(
            row["observed_score"],
            row["maximum_score"],
        ),
        axis=1,
    )
    return result.sort_values("readiness_pct", ascending=True).reset_index(drop=True)


def failed_critical_controls(requirements: pd.DataFrame) -> pd.DataFrame:
    """Return critical controls below their accepted threshold or incomplete."""
    if "critical_control" not in requirements.columns:
        return requirements.iloc[0:0].copy()
    flags = requirements["critical_control"]
    if flags.dtype == bool:
        parsed_flags = flags.fillna(False)
    else:
        parsed_flags = flags.astype("string").str.strip().str.lower().isin(["true", "1", "yes", "y", "critical"])
    critical = requirements[parsed_flags & _applicable_mask(requirements)].copy()
    if critical.empty:
        return critical
    maximum = pd.to_numeric(critical["maximum_score"], errors="coerce")
    if "critical_threshold" in critical.columns:
        raw_threshold = critical["critical_threshold"]
        threshold = pd.to_numeric(raw_threshold, errors="coerce")
        supplied = (
            raw_threshold.notna()
            & raw_threshold.astype("string").str.strip().ne("")
        )
        invalid_threshold = supplied & (
            threshold.isna()
            | maximum.isna()
            | (threshold <= 0)
            | (threshold > maximum)
        )
        effective_threshold = threshold.where(
            threshold.notna() & (threshold > 0) & (threshold <= maximum),
            maximum,
        )
    else:
        invalid_threshold = pd.Series(False, index=critical.index)
        effective_threshold = maximum
    failed = critical["observed_score"].isna() | critical["maximum_score"].isna()
    failed |= invalid_threshold
    failed |= critical["observed_score"] < effective_threshold
    if "incomplete" in critical.columns:
        failed |= critical["incomplete"].fillna(False).astype(bool)
    return critical.loc[failed]


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
