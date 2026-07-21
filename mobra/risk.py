"""Risk scoring and 5 x 5 matrix calculations."""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


RISK_LEVELS = ["Low", "Moderate", "High", "Extreme"]
RISK_CATEGORIES = {
    "Low": (1, 4),
    "Moderate": (5, 9),
    "High": (10, 16),
    "Extreme": (17, 25),
}
RISK_COLORS = {
    "Low": "#2e7d32",
    "Moderate": "#f9a825",
    "High": "#ef6c00",
    "Extreme": "#c62828",
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
    """Return whether a value is an integer on the 1-5 MOBRA scale."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return np.isfinite(number) and number.is_integer() and 1 <= number <= 5


def calculate_risk_score(likelihood: pd.Series, consequence: pd.Series) -> pd.Series:
    """Calculate ``Likelihood × Consequence`` without coercing invalid data."""
    return likelihood * consequence


def heatmap_counts(hazards: pd.DataFrame) -> pd.DataFrame:
    """Return a complete 5x5 count matrix for valid hazard records."""
    if not {"likelihood", "consequence"}.issubset(hazards.columns):
        return pd.DataFrame(0, index=[5, 4, 3, 2, 1], columns=[1, 2, 3, 4, 5], dtype=int)
    valid = hazards[
        hazards["likelihood"].map(valid_scale) & hazards["consequence"].map(valid_scale)
    ].copy()
    matrix = pd.crosstab(valid["consequence"].astype(int), valid["likelihood"].astype(int))
    return matrix.reindex(index=[5, 4, 3, 2, 1], columns=[1, 2, 3, 4, 5], fill_value=0).astype(int)


def heatmap_total(hazards: pd.DataFrame) -> int:
    """Return the number of rows represented by the heat-map cells."""
    return int(heatmap_counts(hazards).to_numpy().sum())


def assert_heatmap_total(hazards: pd.DataFrame) -> None:
    """Raise an assertion error if matrix counts do not match valid rows."""
    valid_count = 0
    if {"likelihood", "consequence"}.issubset(hazards.columns):
        valid_count = int(
            (hazards["likelihood"].map(valid_scale) & hazards["consequence"].map(valid_scale)).sum()
        )
    assert heatmap_total(hazards) == valid_count
