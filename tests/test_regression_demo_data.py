"""Protected regression expectations for the repository demonstration data."""

import pandas as pd
import pytest

from mobra.acceptance import RiskAcceptancePolicy, risk_acceptance_summary
from mobra.decisions import deployment_decision
from mobra.mapping import mapping_coverage_summary, requirements_without_hazards
from mobra.readiness import calculate_bri
from mobra.risk import RISK_LEVELS, heatmap_counts, heatmap_total

pytestmark = pytest.mark.regression

EXPECTED_HEATMAP_CELLS = {
    (1, 5): 1,
    (2, 3): 1,
    (2, 4): 4,
    (2, 5): 4,
    (3, 2): 1,
    (3, 3): 7,
    (3, 4): 3,
    (3, 5): 1,
    (4, 2): 1,
    (4, 3): 1,
}


def test_demonstration_data_full_regression_contract(
    demo_data: dict[str, pd.DataFrame],
    demo_pipeline: dict[str, object],
) -> None:
    hazards = demo_pipeline["hazards"]
    requirements = demo_pipeline["requirements"]
    mapping_result = demo_pipeline["mapping_result"]
    critical_assessment = demo_pipeline["critical_assessment"]

    assert {name: len(data) for name, data in demo_data.items()} == {
        "hazards": 24,
        "requirements": 60,
        "mapping": 95,
        "profile": 60,
    }
    assert int(hazards["inherent_risk_eligible"].sum()) == 24
    assert int(requirements["bri_eligible"].sum()) == 60
    assert int(mapping_result.data["analysis_eligible"].sum()) == 95
    assert int(critical_assessment.validation.data["analysis_eligible"].sum()) == 60

    category_counts = hazards["risk_category"].value_counts().reindex(RISK_LEVELS, fill_value=0).astype(int).to_dict()
    assert category_counts == {"Low": 0, "Moderate": 15, "High": 9, "Extreme": 0}
    heatmap = heatmap_counts(hazards)
    nonzero = {
        (likelihood, consequence): int(heatmap.loc[consequence, likelihood])
        for consequence in heatmap.index
        for likelihood in heatmap.columns
        if heatmap.loc[consequence, likelihood]
    }
    assert nonzero == EXPECTED_HEATMAP_CELLS
    assert heatmap_total(hazards) == 24

    bri = calculate_bri(requirements)
    assert round(bri, 1) == 86.7

    mapping_summary = mapping_coverage_summary(mapping_result.data, requirements, hazards)
    assert mapping_summary == {
        "mapping_links": 95,
        "hazards_mapped": 24,
        "hazards_total": 24,
        "hazard_coverage_pct": 100.0,
        "requirements_mapped": 53,
        "requirements_total": 60,
        "requirement_coverage_pct": 88.33,
        "critical_links": 55,
    }
    unmapped = requirements_without_hazards(mapping_result.data, requirements)
    assert unmapped["requirement_id"].tolist() == ["R005", "R009", "R047", "R050", "R053", "R056", "R059"]

    acceptance = risk_acceptance_summary(hazards, RiskAcceptancePolicy())
    assert acceptance["acceptance_status_counts"] == {
        "Acceptable": 0,
        "Acceptable with monitoring": 15,
        "Conditional": 9,
        "Unacceptable": 0,
        "Not assessable": 0,
    }
    assert acceptance["missing_residual_assessment_count"] == 24
    assert acceptance["corrective_action_required_count"] == 9
    assert acceptance["formal_approval_required_count"] == 9

    critical = critical_assessment.summary
    assert critical["criticality_level_counts"] == {
        "Deployment-blocking": 21,
        "Conditional": 14,
        "Important": 24,
        "Non-critical": 1,
    }
    assert critical["critical_control_outcome_counts"] == {
        "Pass": 50,
        "Conditional gap": 2,
        "Fail": 6,
        "Manual review": 1,
        "Not applicable": 1,
    }
    assert critical["blocking_requirement_ids"] == ["R003", "R024", "R057", "R058"]
    assert critical["conditional_requirement_ids"] == ["R006", "R021"]
    assert critical["manual_review_requirement_ids"] == ["R032"]
    assert critical["evidence_deficient_requirement_ids"] == ["R003", "R006", "R021", "R032", "R058"]

    decision, reasons = deployment_decision(
        hazards,
        requirements,
        bri,
        risk_acceptance_policy=RiskAcceptancePolicy(),
        critical_control_assessment=critical_assessment,
    )
    assert decision == "DO NOT DEPLOY"
    joined = " ".join(reasons)
    assert "4 deployment-blocking" in joined
    assert all(requirement_id in joined for requirement_id in ("R003", "R024", "R057", "R058"))
    assert "inherent risk for screening" in joined
    assert "24 hazard(s)" in joined and "residual assessments were not provided" in joined
    assert "9 hazard(s) have High inherent screening risk" in joined
