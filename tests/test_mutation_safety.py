"""Verify that public analysis APIs do not mutate caller-owned DataFrames."""

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from mobra.acceptance import apply_risk_acceptance
from mobra.critical_controls import assess_critical_controls
from mobra.decisions import deployment_decision
from mobra.mapping import validate_mapping
from mobra.readiness import calculate_bri
from mobra.reporting import make_html_report
from mobra.risk import heatmap_counts
from mobra.validation import validate_hazards, validate_requirements

pytestmark = pytest.mark.unit


def _assert_unchanged(current: pd.DataFrame, original: pd.DataFrame) -> None:
    assert_frame_equal(current, original)


@pytest.mark.slow
@pytest.mark.report
def test_analysis_api_mutation_safety(
    valid_hazards: pd.DataFrame,
    valid_requirements: pd.DataFrame,
    valid_mapping: pd.DataFrame,
    valid_critical_control_profile: pd.DataFrame,
) -> None:
    raw_hazards = valid_hazards[["hazard_id", "hazard", "likelihood", "consequence"]].copy()
    raw_requirements = valid_requirements[
        [
            "requirement_id",
            "requirement",
            "domain",
            "objective_evidence",
            "observed_score",
            "maximum_score",
            "critical_control",
        ]
    ].copy()
    originals = {
        "raw_hazards": raw_hazards.copy(deep=True),
        "raw_requirements": raw_requirements.copy(deep=True),
        "hazards": valid_hazards.copy(deep=True),
        "requirements": valid_requirements.copy(deep=True),
        "mapping": valid_mapping.copy(deep=True),
        "profile": valid_critical_control_profile.copy(deep=True),
    }

    validate_hazards(raw_hazards)
    validate_requirements(raw_requirements)
    calculate_bri(valid_requirements)
    heatmap_counts(valid_hazards)
    analyzed_hazards = apply_risk_acceptance(valid_hazards)
    mapping_result = validate_mapping(valid_mapping, valid_requirements, valid_hazards)
    critical_assessment = assess_critical_controls(valid_requirements, valid_critical_control_profile)
    bri = calculate_bri(valid_requirements)
    decision, reasons = deployment_decision(
        analyzed_hazards,
        valid_requirements,
        bri,
        critical_control_assessment=critical_assessment,
    )
    make_html_report(
        analyzed_hazards,
        valid_requirements,
        bri,
        decision,
        reasons,
        mapping=mapping_result.data,
        critical_profile=critical_assessment.validation.data,
        critical_control_assessment=critical_assessment,
    )

    _assert_unchanged(raw_hazards, originals["raw_hazards"])
    _assert_unchanged(raw_requirements, originals["raw_requirements"])
    _assert_unchanged(valid_hazards, originals["hazards"])
    _assert_unchanged(valid_requirements, originals["requirements"])
    _assert_unchanged(valid_mapping, originals["mapping"])
    _assert_unchanged(valid_critical_control_profile, originals["profile"])
