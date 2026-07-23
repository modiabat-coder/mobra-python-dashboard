"""Risk scoring, category, chart, and heat-map tests."""

import numpy as np
import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st

from mobra.risk import calculate_risk_score, classify_risk, heatmap_counts

from .cases_logic import (
    test_heatmap_figure_uses_frequency_text_and_risk_score_backgrounds as test_heatmap_figure_uses_frequency_text_and_risk_score_backgrounds,
)
from .cases_logic import (
    test_invalid_likelihood_or_consequence_is_reported as test_invalid_likelihood_or_consequence_is_reported,
)
from .cases_logic import test_invalid_risk_score_is_not_a_category as test_invalid_risk_score_is_not_a_category
from .cases_logic import test_risk_boundaries as test_risk_boundaries
from .cases_logic import (
    test_risk_score_is_likelihood_times_consequence as test_risk_score_is_likelihood_times_consequence,
)

pytestmark = pytest.mark.unit


@pytest.mark.property
@given(likelihood=st.integers(min_value=1, max_value=5), consequence=st.integers(min_value=1, max_value=5))
def test_risk_score_and_category_properties(likelihood: int, consequence: int) -> None:
    score = calculate_risk_score(pd.Series([likelihood]), pd.Series([consequence])).iloc[0]
    expected = "Low" if score <= 4 else "Moderate" if score <= 9 else "High" if score <= 16 else "Extreme"
    assert score == likelihood * consequence
    assert 1 <= score <= 25
    assert classify_risk(score) == expected


@pytest.mark.property
@given(rows=st.lists(st.tuples(st.integers(1, 5), st.integers(1, 5)), max_size=40))
def test_heatmap_matrix_properties(rows: list[tuple[int, int]]) -> None:
    hazards = pd.DataFrame(rows, columns=["likelihood", "consequence"])
    matrix = heatmap_counts(hazards)
    assert matrix.shape == (5, 5)
    assert int(matrix.to_numpy().sum()) == len(rows)
    assert (matrix.to_numpy() >= 0).all()
    assert np.issubdtype(matrix.to_numpy().dtype, np.integer)


def test_empty_heatmap_is_complete_zero_matrix() -> None:
    matrix = heatmap_counts(pd.DataFrame(columns=["likelihood", "consequence"]))
    assert matrix.shape == (5, 5)
    assert int(matrix.to_numpy().sum()) == 0
