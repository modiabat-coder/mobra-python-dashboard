"""Risk scoring and 5 × 5 matrix calculations."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import RISK_COLORS, RISK_LEVELS


RISK_CATEGORIES = {
    "Low": (1, 4),
    "Moderate": (5, 9),
    "High": (10, 16),
    "Extreme": (17, 25),
}


def classify_risk(score: float | int | None) -> str:
    """Classify a score using the fixed MOBRA thresholds."""
    if score is None or pd.isna(score):
        return "Unknown"
    try:
        score = float(score)
    except (TypeError, ValueError):
        return "Invalid"
    if not np.isfinite(score):
        return "Unknown"
    if score < 1 or score > 25:
        return "Invalid"
    if score <= 4:
        return "Low"
    if score <= 9:
        return "Moderate"
    if score <= 16:
        return "High"
    return "Extreme"


def valid_scale(value: object) -> bool:
    """Return whether a value is an integer on the 1–5 MOBRA scale."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return np.isfinite(number) and number.is_integer() and 1 <= number <= 5


def calculate_risk_score(likelihood: pd.Series, consequence: pd.Series) -> pd.Series:
    """Calculate ``Likelihood × Consequence`` without coercing invalid data."""
    return likelihood * consequence


def heatmap_counts(hazards: pd.DataFrame) -> pd.DataFrame:
    """Return counts indexed by Likelihood (5→1) and Consequence (1→5)."""
    if not {"likelihood", "consequence"}.issubset(hazards.columns):
        return pd.DataFrame(0, index=[5, 4, 3, 2, 1], columns=[1, 2, 3, 4, 5], dtype=int)
    valid = hazards[
        hazards["likelihood"].map(valid_scale) & hazards["consequence"].map(valid_scale)
    ].copy()
    matrix = pd.crosstab(valid["likelihood"].astype(int), valid["consequence"].astype(int))
    return matrix.reindex(
        index=[5, 4, 3, 2, 1],
        columns=[1, 2, 3, 4, 5],
        fill_value=0,
    ).astype(int)


def heatmap_total(hazards: pd.DataFrame) -> int:
    """Return the number of valid rows represented by the matrix cells."""
    return int(heatmap_counts(hazards).to_numpy().sum())


def valid_hazard_count(hazards: pd.DataFrame) -> int:
    """Return the number of records with valid Likelihood and Consequence."""
    if not {"likelihood", "consequence"}.issubset(hazards.columns):
        return 0
    return int(
        (
            hazards["likelihood"].map(valid_scale)
            & hazards["consequence"].map(valid_scale)
        ).sum()
    )


def assert_heatmap_total(hazards: pd.DataFrame) -> None:
    """Raise if matrix counts do not equal the valid hazard count."""
    actual = heatmap_total(hazards)
    expected = valid_hazard_count(hazards)
    if actual != expected:
        raise AssertionError(
            f"Risk heatmap count mismatch: cells contain {actual} hazards, "
            f"but {expected} valid hazards were supplied."
        )
