"""Requirement-to-hazard mapping validation and coverage tests."""

import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st

from mobra.mapping import mapping_coverage_summary

from .cases_logic import test_mapping_csv_and_xlsx_input_round_trip as test_mapping_csv_and_xlsx_input_round_trip
from .cases_logic import (
    test_mapping_duplicate_id_and_duplicate_pair_fail_validation as test_mapping_duplicate_id_and_duplicate_pair_fail_validation,
)
from .cases_logic import (
    test_mapping_required_content_and_enumerations_are_validated as test_mapping_required_content_and_enumerations_are_validated,
)
from .cases_logic import (
    test_mapping_unknown_foreign_id_fails_validation as test_mapping_unknown_foreign_id_fails_validation,
)
from .cases_logic import (
    test_unmapped_requirements_are_a_warning_and_coverage_finding as test_unmapped_requirements_are_a_warning_and_coverage_finding,
)
from .cases_structured_validation import (
    test_mapping_and_profile_use_structured_blocking_codes as test_mapping_and_profile_use_structured_blocking_codes,
)
from .cases_structured_validation import (
    test_unmapped_requirement_is_a_structured_warning as test_unmapped_requirement_is_a_structured_warning,
)

pytestmark = pytest.mark.unit


@pytest.mark.property
@given(total=st.integers(1, 15), linked=st.integers(0, 15))
def test_mapping_coverage_bounds_and_monotonicity(total: int, linked: int) -> None:
    linked = min(linked, total)
    hazards = pd.DataFrame({"hazard_id": [f"H{index:03d}" for index in range(1, total + 1)]})
    requirements = pd.DataFrame({"requirement_id": [f"R{index:03d}" for index in range(1, total + 1)]})
    mapping = pd.DataFrame(
        {
            "hazard_id": [f"H{index:03d}" for index in range(1, linked + 1)],
            "requirement_id": [f"R{index:03d}" for index in range(1, linked + 1)],
            "critical_link": [False] * linked,
        }
    )
    before = mapping_coverage_summary(mapping, requirements, hazards)
    assert 0 <= before["hazard_coverage_pct"] <= 100
    assert 0 <= before["requirement_coverage_pct"] <= 100
    if linked < total:
        new_link = pd.DataFrame(
            {
                "hazard_id": [f"H{linked + 1:03d}"],
                "requirement_id": [f"R{linked + 1:03d}"],
                "critical_link": [False],
            }
        )
        after = mapping_coverage_summary(pd.concat([mapping, new_link], ignore_index=True), requirements, hazards)
        assert after["hazard_coverage_pct"] >= before["hazard_coverage_pct"]
