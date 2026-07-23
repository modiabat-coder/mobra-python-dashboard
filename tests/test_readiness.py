"""BRI and domain-readiness tests."""

import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st

from mobra.readiness import calculate_bri

from .cases_logic import test_bri_formula_is_weighted as test_bri_formula_is_weighted
from .cases_logic import (
    test_bri_zero_maximum_is_nan_and_invalid_row_is_reported as test_bri_zero_maximum_is_nan_and_invalid_row_is_reported,
)
from .cases_logic import test_domain_bri_is_weighted_by_maximum_points as test_domain_bri_is_weighted_by_maximum_points

pytestmark = pytest.mark.unit


@st.composite
def valid_score_rows(draw: st.DrawFn) -> list[tuple[int, int]]:
    maxima = draw(st.lists(st.integers(min_value=1, max_value=5), min_size=1, max_size=20))
    return [(draw(st.integers(min_value=0, max_value=maximum)), maximum) for maximum in maxima]


@pytest.mark.property
@given(rows=valid_score_rows())
def test_bri_range_extremes_and_reordering_properties(rows: list[tuple[int, int]]) -> None:
    data = pd.DataFrame(rows, columns=["observed_score", "maximum_score"])
    bri = calculate_bri(data)
    assert 0 <= bri <= 100
    assert calculate_bri(data.sample(frac=1, random_state=17).reset_index(drop=True)) == pytest.approx(bri)
    full = data.assign(observed_score=data["maximum_score"])
    zero = data.assign(observed_score=0)
    assert calculate_bri(full) == 100
    assert calculate_bri(zero) == 0


@pytest.mark.property
@given(maximum=st.integers(1, 5), observed=st.integers(0, 4))
def test_increasing_observed_score_cannot_decrease_bri(maximum: int, observed: int) -> None:
    lower = min(observed, maximum)
    higher = min(lower + 1, maximum)
    lower_bri = calculate_bri(pd.DataFrame({"observed_score": [lower], "maximum_score": [maximum]}))
    higher_bri = calculate_bri(pd.DataFrame({"observed_score": [higher], "maximum_score": [maximum]}))
    assert higher_bri >= lower_bri
