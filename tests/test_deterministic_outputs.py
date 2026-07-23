"""Stable ordering and repeatability contracts for fixed inputs."""

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from mobra.critical_controls import assess_critical_controls, critical_control_summary_table
from mobra.decisions import deployment_decision
from mobra.mapping import hazard_mapping_ranking, mapping_coverage_table, requirement_mapping_ranking
from mobra.readiness import calculate_bri
from mobra.risk import heatmap_counts

pytestmark = pytest.mark.regression


def test_fixed_analyses_have_deterministic_ordering(
    demo_data: dict[str, pd.DataFrame],
    demo_pipeline: dict[str, object],
) -> None:
    hazards = demo_pipeline["hazards"]
    requirements = demo_pipeline["requirements"]
    mapping = demo_pipeline["mapping_result"].data
    critical_first = demo_pipeline["critical_assessment"]
    critical_second = assess_critical_controls(requirements, demo_data["profile"])

    assert_frame_equal(heatmap_counts(hazards), heatmap_counts(hazards.copy(deep=True)))
    assert_frame_equal(
        mapping_coverage_table(mapping, requirements, hazards),
        mapping_coverage_table(mapping.copy(deep=True), requirements.copy(deep=True), hazards.copy(deep=True)),
    )
    assert_frame_equal(
        hazard_mapping_ranking(mapping, hazards).reset_index(drop=True),
        hazard_mapping_ranking(mapping.copy(deep=True), hazards.copy(deep=True)).reset_index(drop=True),
    )
    assert_frame_equal(
        requirement_mapping_ranking(mapping, requirements).reset_index(drop=True),
        requirement_mapping_ranking(mapping.copy(deep=True), requirements.copy(deep=True)).reset_index(drop=True),
    )
    assert critical_first.summary == critical_second.summary
    assert_frame_equal(
        critical_control_summary_table(critical_first),
        critical_control_summary_table(critical_second),
    )
    bri = calculate_bri(requirements)
    first_decision = deployment_decision(
        hazards,
        requirements,
        bri,
        critical_control_assessment=critical_first,
    )
    second_decision = deployment_decision(
        hazards.copy(deep=True),
        requirements.copy(deep=True),
        bri,
        critical_control_assessment=critical_second,
    )
    assert first_decision == second_decision
