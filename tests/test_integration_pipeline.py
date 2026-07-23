"""End-to-end MOBRA pipeline and deterministic-output tests."""

from io import BytesIO

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from app import excel_bytes
from mobra.acceptance import RiskAcceptancePolicy, apply_risk_acceptance, risk_acceptance_summary
from mobra.critical_controls import assess_critical_controls
from mobra.decisions import deployment_decision
from mobra.mapping import MAPPING_REQUIRED_COLUMNS, mapping_coverage_summary, validate_mapping
from mobra.readiness import calculate_bri
from mobra.reporting import make_html_report
from mobra.risk import heatmap_total
from mobra.validation import validate_hazards, validate_requirements
from mobra.validation_exports import validation_json_fields
from mobra.validation_findings import validate_cross_dataset_consistency, validation_summary

pytestmark = pytest.mark.integration

REQUIRED_EXCEL_SHEETS = {
    "Analyzed_Hazards",
    "Analyzed_Requirements",
    "Summary",
    "Requirement_Hazard_Map",
    "Risk_Acceptance_Summary",
    "Critical_Control_Profile",
    "Critical_Control_Assessment",
    "Critical_Control_Summary",
    "Validation_Summary",
    "Validation_Findings",
    "Invalid_Hazard_Records",
    "Invalid_Requirement_Records",
    "Invalid_Mapping_Records",
    "Invalid_Profile_Records",
}


def _validation_outputs(
    hazard_result: object,
    requirement_result: object,
    mapping_result: object,
    critical_assessment: object,
) -> tuple[list[object], list[dict[str, object]]]:
    cross = validate_cross_dataset_consistency(
        hazard_result.data,
        requirement_result.data,
        mapping_result.data,
        critical_assessment.validation.data,
    )
    findings = [
        *hazard_result.findings,
        *requirement_result.findings,
        *mapping_result.findings,
        *critical_assessment.validation.findings,
        *cross.findings,
    ]
    reference = "2026-07-22"
    summaries = [
        validation_summary(
            dataset_type="Hazards",
            filename="hazards_sample.csv",
            data=hazard_result.data,
            findings=hazard_result.findings,
            required_columns=("hazard", "likelihood", "consequence"),
            validation_reference_date=reference,
        ),
        validation_summary(
            dataset_type="Requirements",
            filename="requirements_sample.csv",
            data=requirement_result.data,
            findings=requirement_result.findings,
            required_columns=("requirement", "observed_score", "maximum_score"),
            validation_reference_date=reference,
        ),
        validation_summary(
            dataset_type="Mapping",
            filename="requirement_hazard_mapping.csv",
            data=mapping_result.data,
            findings=mapping_result.findings,
            required_columns=MAPPING_REQUIRED_COLUMNS,
            validation_reference_date=reference,
        ),
        validation_summary(
            dataset_type="Critical-Control Profile",
            filename="critical_control_profile.csv",
            data=critical_assessment.validation.data,
            findings=critical_assessment.validation.findings,
            validation_reference_date=reference,
        ),
    ]
    return findings, summaries


@pytest.mark.slow
@pytest.mark.report
def test_complete_demo_pipeline_generates_all_output_contracts(
    demo_data: dict[str, pd.DataFrame],
) -> None:
    original = {name: data.copy(deep=True) for name, data in demo_data.items()}
    hazard_result = validate_hazards(demo_data["hazards"], validation_reference_date="2026-07-22")
    requirement_result = validate_requirements(demo_data["requirements"], validation_reference_date="2026-07-22")
    hazards = apply_risk_acceptance(hazard_result.data, RiskAcceptancePolicy())
    requirements = requirement_result.data
    mapping_result = validate_mapping(demo_data["mapping"], requirements, hazards)
    critical_assessment = assess_critical_controls(requirements, demo_data["profile"])
    bri = calculate_bri(requirements)
    decision, reasons = deployment_decision(
        hazards,
        requirements,
        bri,
        critical_control_assessment=critical_assessment,
    )
    findings, summaries = _validation_outputs(hazard_result, requirement_result, mapping_result, critical_assessment)
    validation_block = validation_json_fields(
        summaries,
        findings,
        validation_reference_date="2026-07-22",
    )
    summary = {
        "bri_pct": round(bri, 2),
        "decision": decision,
        "decision_reasons": reasons,
        **validation_block,
    }
    datasets = {
        "Hazards": hazards,
        "Requirements": requirements,
        "Mapping": mapping_result.data,
        "Critical-Control Profile": critical_assessment.validation.data,
    }
    workbook = excel_bytes(
        hazards,
        requirements,
        summary,
        mapping_result.data,
        critical_profile=critical_assessment.validation.data,
        critical_control_assessment=critical_assessment,
        validation_summaries=summaries,
        validation_findings=findings,
        validation_datasets=datasets,
    )
    html = make_html_report(
        hazards,
        requirements,
        bri,
        decision,
        reasons,
        mapping=mapping_result.data,
        critical_profile=critical_assessment.validation.data,
        critical_control_assessment=critical_assessment,
        validation_findings=findings,
        validation_summaries=summaries,
        validation_reference_date="2026-07-22",
    )

    assert summary["validation_status"] == "Warnings found"
    assert REQUIRED_EXCEL_SHEETS.issubset(pd.ExcelFile(BytesIO(workbook), engine="openpyxl").sheet_names)
    for heading in (
        "Data Validation",
        "Risk Acceptance",
        "Critical-Control Governance",
        "Requirement-to-Hazard Mapping",
        "Appendix: Validation Findings",
    ):
        assert heading in html
    assert len(html.encode("utf-8")) > 100_000
    for name, source in original.items():
        assert_frame_equal(demo_data[name], source)


def test_invalid_rows_do_not_contaminate_valid_calculations(
    invalid_hazard_records: pd.DataFrame,
    invalid_requirement_records: pd.DataFrame,
) -> None:
    hazards = validate_hazards(invalid_hazard_records).data
    requirements = validate_requirements(invalid_requirement_records).data
    assert len(hazards) == 2 and heatmap_total(hazards) == 1
    assert len(requirements) == 2 and calculate_bri(requirements) == 80.0


def test_pipeline_is_deterministic_for_identical_inputs(demo_data: dict[str, pd.DataFrame]) -> None:
    first_hazards = validate_hazards(demo_data["hazards"], validation_reference_date="2026-07-22")
    second_hazards = validate_hazards(demo_data["hazards"], validation_reference_date="2026-07-22")
    first_requirements = validate_requirements(demo_data["requirements"], validation_reference_date="2026-07-22")
    second_requirements = validate_requirements(demo_data["requirements"], validation_reference_date="2026-07-22")
    assert_frame_equal(first_hazards.data, second_hazards.data)
    assert_frame_equal(first_requirements.data, second_requirements.data)
    assert first_hazards.findings == second_hazards.findings
    assert first_requirements.findings == second_requirements.findings
    bri = calculate_bri(first_requirements.data)
    first_decision = deployment_decision(first_hazards.data, first_requirements.data, bri)
    second_decision = deployment_decision(second_hazards.data, second_requirements.data, bri)
    assert first_decision == second_decision


def test_reordering_inputs_preserves_aggregate_results(demo_data: dict[str, pd.DataFrame]) -> None:
    hazards_a = validate_hazards(demo_data["hazards"]).data
    requirements_a = validate_requirements(demo_data["requirements"]).data
    mapping_a = validate_mapping(demo_data["mapping"], requirements_a, hazards_a).data

    hazards_b = validate_hazards(demo_data["hazards"].iloc[::-1].reset_index(drop=True)).data
    requirements_b = validate_requirements(demo_data["requirements"].iloc[::-1].reset_index(drop=True)).data
    mapping_b = validate_mapping(demo_data["mapping"].iloc[::-1].reset_index(drop=True), requirements_b, hazards_b).data

    assert calculate_bri(requirements_a) == pytest.approx(calculate_bri(requirements_b))
    assert hazards_a["risk_category"].value_counts().to_dict() == hazards_b["risk_category"].value_counts().to_dict()
    assert mapping_coverage_summary(mapping_a, requirements_a, hazards_a) == mapping_coverage_summary(
        mapping_b, requirements_b, hazards_b
    )


def test_chart_filtering_does_not_change_full_dataset_calculations(demo_pipeline: dict[str, object]) -> None:
    hazards = demo_pipeline["hazards"]
    requirements = demo_pipeline["requirements"]
    full_bri = calculate_bri(requirements)
    full_acceptance = risk_acceptance_summary(hazards, RiskAcceptancePolicy())
    filtered = hazards.loc[hazards["risk_category"].eq("High")]
    assert heatmap_total(filtered) == 9
    assert calculate_bri(requirements) == full_bri
    assert risk_acceptance_summary(hazards, RiskAcceptancePolicy()) == full_acceptance
