"""Deployment policy, mandatory override, and ordering tests."""

import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st

from mobra.decisions import deployment_decision
from mobra.validation import validate_hazards, validate_requirements

from .cases_logic import (
    test_critical_control_override_cannot_be_bypassed_by_high_bri as test_critical_control_override_cannot_be_bypassed_by_high_bri,
)
from .cases_logic import test_decision_thresholds_without_overrides as test_decision_thresholds_without_overrides
from .cases_logic import (
    test_extreme_inherent_screening_is_not_called_residual_and_caps_ready as test_extreme_inherent_screening_is_not_called_residual_and_caps_ready,
)
from .cases_logic import test_extreme_residual_risk_override as test_extreme_residual_risk_override
from .cases_logic import (
    test_high_residual_risk_prevents_ready_and_requires_approval as test_high_residual_risk_prevents_ready_and_requires_approval,
)
from .cases_logic import (
    test_incomplete_critical_record_is_an_actual_override as test_incomplete_critical_record_is_an_actual_override,
)
from .cases_logic import (
    test_string_false_critical_flag_is_not_treated_as_true as test_string_false_critical_flag_is_not_treated_as_true,
)
from .cases_logic import test_validation_error_is_an_actual_override as test_validation_error_is_an_actual_override

pytestmark = pytest.mark.unit


def _ready_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    hazards = validate_hazards(
        pd.DataFrame({"hazard_id": ["H001"], "hazard": ["x"], "likelihood": [1], "consequence": [1]})
    ).data
    requirements = validate_requirements(
        pd.DataFrame(
            {
                "requirement_id": ["R001"],
                "requirement": ["x"],
                "observed_score": [5],
                "maximum_score": [5],
                "critical_control": [False],
                "objective_evidence": ["record"],
            }
        )
    ).data
    return hazards, requirements


@pytest.mark.property
@given(bri=st.floats(min_value=85, max_value=100, allow_nan=False, allow_infinity=False))
def test_validation_errors_always_prevent_ready(bri: float) -> None:
    hazards, requirements = _ready_inputs()
    decision, _ = deployment_decision(hazards, requirements, bri, validation_errors=["invalid input"])
    assert decision != "READY FOR DEPLOYMENT"


@pytest.mark.property
@given(bri=st.floats(min_value=85, max_value=100, allow_nan=False, allow_infinity=False))
def test_extreme_residual_risk_always_prevents_ready(bri: float) -> None:
    hazards = validate_hazards(
        pd.DataFrame(
            {
                "hazard_id": ["H001"],
                "hazard": ["x"],
                "likelihood": [1],
                "consequence": [1],
                "residual_likelihood": [5],
                "residual_consequence": [5],
            }
        )
    ).data
    _, requirements = _ready_inputs()
    decision, _ = deployment_decision(hazards, requirements, bri)
    assert decision != "READY FOR DEPLOYMENT"


@pytest.mark.property
@given(bri=st.floats(min_value=85, max_value=100, allow_nan=False, allow_infinity=False))
def test_deployment_blocking_control_always_prevents_ready(bri: float) -> None:
    hazards, _ = _ready_inputs()
    requirements = validate_requirements(
        pd.DataFrame(
            {
                "requirement_id": ["R001"],
                "requirement": ["blocking"],
                "observed_score": [0],
                "maximum_score": [5],
                "critical_control": [True],
                "objective_evidence": ["record"],
            }
        )
    ).data
    decision, _ = deployment_decision(hazards, requirements, bri)
    assert decision != "READY FOR DEPLOYMENT"
