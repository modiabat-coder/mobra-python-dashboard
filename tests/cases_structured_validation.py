"""Granular tests for structured, auditable Task 6 validation behavior."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest

from app import excel_bytes
from mobra.critical_controls import validate_critical_control_profile
from mobra.io import FileValidationError, read_data_file, read_data_file_with_validation
from mobra.mapping import validate_mapping
from mobra.readiness import calculate_bri
from mobra.reporting import make_html_report
from mobra.risk import heatmap_total
from mobra.validation import validate_hazards, validate_requirements
from mobra.validation_exports import invalid_records_workbook_bytes, validation_json_fields
from mobra.validation_findings import (
    VALIDATION_LIMITATION,
    findings_frame,
    validate_cross_dataset_consistency,
    validation_summary,
)

ROOT = Path(__file__).parents[1]


def _codes(result: object) -> list[str]:
    return [finding.code for finding in result.findings]


def _hazards(**changes: object) -> pd.DataFrame:
    data: dict[str, list[object]] = {
        "hazard_id": ["H001"],
        "hazard": ["Exposure event"],
        "likelihood": [2],
        "consequence": [4],
    }
    for key, value in changes.items():
        data[key] = value if isinstance(value, list) else [value]
    return pd.DataFrame(data)


def _requirements(**changes: object) -> pd.DataFrame:
    data: dict[str, list[object]] = {
        "requirement_id": ["R001"],
        "requirement": ["Verified control"],
        "domain": ["Governance"],
        "observed_score": [4],
        "maximum_score": [5],
        "critical_control": [False],
        "objective_evidence": ["Approved record"],
    }
    for key, value in changes.items():
        data[key] = value if isinstance(value, list) else [value]
    return pd.DataFrame(data)


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"hazard": ""}, "EMPTY_REQUIRED_TEXT"),
        ({"hazard_id": ""}, "BLANK_ID"),
        ({"likelihood": 2.5}, "NON_INTEGER_VALUE"),
        ({"likelihood": "High"}, "INVALID_NUMERIC_VALUE"),
        ({"likelihood": 0}, "VALUE_OUT_OF_RANGE"),
        ({"likelihood": 6}, "VALUE_OUT_OF_RANGE"),
        ({"likelihood": float("inf")}, "NON_FINITE_VALUE"),
        ({"consequence": pd.NA}, "MISSING_NUMERIC_VALUE"),
    ],
)
def test_hazard_granular_validation_codes(changes: dict[str, object], code: str) -> None:
    result = validate_hazards(_hazards(**changes))
    assert code in _codes(result)
    assert len(result.data) == 1
    assert not bool(result.data.loc[0, "analysis_eligible"])
    assert result.data.loc[0, "validation_status"] == "Invalid"


def test_hazard_duplicate_id_is_structured_and_both_rows_remain_visible() -> None:
    data = pd.concat([_hazards(), _hazards(hazard="Second event")], ignore_index=True)
    result = validate_hazards(data)
    assert "DUPLICATE_ID" in _codes(result)
    assert len(result.data) == 2
    assert result.data["analysis_eligible"].sum() == 0


def test_uploaded_hazard_risk_mismatches_are_preserved_separately() -> None:
    result = validate_hazards(_hazards(risk_score=10, risk_category="Extreme"))
    mismatches = [finding for finding in result.findings if finding.code == "INCONSISTENT_CALCULATED_RISK"]
    assert {finding.column for finding in mismatches} == {"risk_score", "risk_category"}
    assert result.data.loc[0, "uploaded_risk_score"] == 10
    assert result.data.loc[0, "uploaded_risk_category"] == "Extreme"
    assert result.data.loc[0, "risk_score"] == 8
    assert result.data.loc[0, "risk_category"] == "Moderate"


def test_partial_and_invalid_residual_pairs_have_specific_codes() -> None:
    partial = validate_hazards(_hazards(residual_likelihood=2))
    invalid = validate_hazards(_hazards(residual_likelihood=2, residual_consequence=7))
    assert "INCOMPLETE_RESIDUAL_PAIR" in _codes(partial)
    assert "VALUE_OUT_OF_RANGE" in _codes(invalid)
    assert not partial.data.loc[0, "residual_risk_eligible"]
    assert not invalid.data.loc[0, "residual_risk_eligible"]


def test_empty_hazard_dataset_is_a_blocking_structured_error() -> None:
    result = validate_hazards(pd.DataFrame(columns=["hazard", "likelihood", "consequence"]))
    assert "EMPTY_DATASET" in _codes(result)
    assert result.dataset_blocked


def test_generated_hazard_ids_are_raw_traceable_and_warned() -> None:
    result = validate_hazards(pd.DataFrame({"hazard": ["x"], "likelihood": [1], "consequence": [2]}))
    assert "GENERATED_ROW_ORDER_ID" in _codes(result)
    assert result.data.loc[0, "hazard_id"] == "H001"
    assert pd.isna(result.data.loc[0, "hazard_id_raw"])
    assert result.data.loc[0, "hazard_id_generated"]


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"requirement": ""}, "EMPTY_REQUIRED_TEXT"),
        ({"observed_score": pd.NA}, "MISSING_NUMERIC_VALUE"),
        ({"observed_score": "four"}, "INVALID_NUMERIC_VALUE"),
        ({"observed_score": 6}, "VALUE_OUT_OF_RANGE"),
        ({"maximum_score": 0}, "ZERO_OR_NEGATIVE_MAXIMUM"),
        ({"observed_score": -1}, "VALUE_OUT_OF_RANGE"),
        ({"critical_control": "maybe"}, "INVALID_BOOLEAN"),
        ({"objective_evidence": ""}, "MISSING_EVIDENCE"),
        ({"objective_evidence": "Not provided"}, "MISSING_EVIDENCE"),
    ],
)
def test_requirement_granular_validation_codes(changes: dict[str, object], code: str) -> None:
    result = validate_requirements(_requirements(**changes))
    assert code in _codes(result)
    assert len(result.data) == 1


def test_observed_above_maximum_has_specific_code() -> None:
    result = validate_requirements(_requirements(observed_score=5, maximum_score=4))
    assert "OBSERVED_EXCEEDS_MAXIMUM" in _codes(result)
    assert not result.data.loc[0, "bri_eligible"]


def test_duplicate_requirement_ids_are_excluded_but_visible() -> None:
    data = pd.concat([_requirements(), _requirements(requirement="Duplicate")], ignore_index=True)
    result = validate_requirements(data)
    assert "DUPLICATE_ID" in _codes(result)
    assert len(result.data) == 2
    assert result.data["bri_eligible"].sum() == 0


@pytest.mark.parametrize(
    ("due_date", "expected_code"),
    [
        ("not-a-date", "INVALID_DATE"),
        ("03/04/2026", "AMBIGUOUS_DATE"),
        ("2025-01-01", "OVERDUE_OPEN_ACTION"),
    ],
)
def test_requirement_date_findings_use_explicit_reference_date(due_date: str, expected_code: str) -> None:
    result = validate_requirements(
        _requirements(due_date=due_date, status="Open"),
        validation_reference_date="2026-07-22",
    )
    assert expected_code in _codes(result)
    assert result.data.loc[0, "due_date_raw"] == due_date
    assert result.data.loc[0, "validation_reference_date"] == "2026-07-22"


def test_invalid_requirement_is_excluded_from_bri_without_disappearing() -> None:
    data = pd.DataFrame(
        {
            "requirement_id": ["R001", "R002"],
            "requirement": ["Valid", "Invalid"],
            "observed_score": [4, "bad"],
            "maximum_score": [5, 5],
            "critical_control": [False, False],
            "objective_evidence": ["record", "record"],
        }
    )
    result = validate_requirements(data)
    assert len(result.data) == 2
    assert result.data["bri_eligible"].tolist() == [True, False]
    assert calculate_bri(result.data) == 80.0


def test_invalid_hazard_is_excluded_from_heatmap_without_disappearing() -> None:
    data = pd.DataFrame(
        {
            "hazard_id": ["H001", "H002"],
            "hazard": ["Valid", "Invalid"],
            "likelihood": [2, "bad"],
            "consequence": [3, 4],
        }
    )
    result = validate_hazards(data)
    assert len(result.data) == 2
    assert result.data["inherent_risk_eligible"].tolist() == [True, False]
    assert heatmap_total(result.data) == 1


def test_mapping_and_profile_use_structured_blocking_codes() -> None:
    hazards = validate_hazards(_hazards()).data
    requirements = validate_requirements(_requirements()).data
    mapping = pd.read_csv(ROOT / "sample_data" / "requirement_hazard_mapping.csv").head(1)
    mapping.loc[0, "hazard_id"] = "H999"
    mapping_result = validate_mapping(mapping, requirements, hazards, require_full_hazard_coverage=False)
    unknown = next(finding for finding in mapping_result.findings if finding.code == "UNKNOWN_HAZARD_ID")
    assert unknown.severity == "Error" and unknown.blocks_analysis

    full_requirements = validate_requirements(pd.read_csv(ROOT / "sample_data" / "requirements_sample.csv")).data
    profile = pd.read_csv(ROOT / "sample_data" / "critical_control_profile.csv").iloc[1:].copy()
    profile_result = validate_critical_control_profile(profile, full_requirements)
    missing = [finding for finding in profile_result.findings if finding.code == "MISSING_PROFILE_ROW"]
    assert missing and all(finding.severity == "Error" and finding.blocks_analysis for finding in missing)


def test_unmapped_requirement_is_a_structured_warning() -> None:
    hazards = validate_hazards(_hazards()).data
    requirements = validate_requirements(
        pd.concat([_requirements(), _requirements(requirement_id="R002", requirement="Second")], ignore_index=True)
    ).data
    mapping = pd.DataFrame(
        {
            "mapping_id": ["M001"],
            "requirement_id": ["R001"],
            "hazard_id": ["H001"],
            "relationship_type": ["Preventive"],
            "mapping_rationale": ["Direct control"],
            "control_role": ["Primary"],
            "critical_link": [True],
            "source_status": ["Representative Demonstration Mapping"],
        }
    )
    result = validate_mapping(mapping, requirements, hazards)
    finding = next(finding for finding in result.findings if finding.code == "UNMAPPED_REQUIREMENT")
    assert finding.severity == "Warning" and not finding.blocks_analysis


def test_cross_dataset_case_whitespace_and_duplicate_wording_findings() -> None:
    hazards = pd.DataFrame(
        {
            "hazard_id": ["H001", "H002"],
            "hazard": ["Same hazard", " same HAZARD "],
            "likelihood": [1, 1],
            "consequence": [2, 2],
        }
    )
    requirements = pd.DataFrame(
        {
            "requirement_id": ["R001", "R002"],
            "requirement": ["Same wording", " same WORDING "],
            "observed_score": [5, 5],
            "maximum_score": [5, 5],
        }
    )
    mapping = pd.DataFrame(
        {
            "mapping_id": ["M001", "M002"],
            "hazard_id": ["h001", " H002 "],
            "requirement_id": ["R001", "R002"],
            "critical_link": [True, False],
        }
    )
    result = validate_cross_dataset_consistency(hazards, requirements, mapping, require_full_hazard_coverage=False)
    codes = _codes(result)
    assert "CASE_ONLY_ID_MISMATCH" in codes
    assert "TRAILING_OR_LEADING_WHITESPACE" in codes
    assert "SUSPICIOUS_DUPLICATE_HAZARD" in codes
    assert "SUSPICIOUS_DUPLICATE_REQUIREMENT" in codes
    assert "SUSPICIOUS_DUPLICATE_RECORD" in codes


def test_file_validation_handles_unsupported_empty_corrupt_and_bad_csv() -> None:
    unsupported = read_data_file_with_validation(b"x", name="data.xlsm")
    empty = read_data_file_with_validation(b"", name="data.csv")
    corrupt = read_data_file_with_validation(b"not an xlsx", name="data.xlsx")
    bad_csv = read_data_file_with_validation(b"a,b\n1,2\n3,4,5\n", name="data.csv")
    assert "UNSUPPORTED_FILE_TYPE" in _codes(unsupported)
    assert "EMPTY_FILE" in _codes(empty)
    assert "CORRUPTED_WORKBOOK" in _codes(corrupt)
    assert "INCONSISTENT_ROW_WIDTH" in _codes(bad_csv)
    with pytest.raises(FileValidationError) as exc_info:
        read_data_file(b"x", name="data.exe")
    assert exc_info.value.code == "UNSUPPORTED_FILE_TYPE"


def test_file_validation_reports_header_position_delimiter_and_formula_cache() -> None:
    csv_result = read_data_file_with_validation(
        b"\nrequirement_id;requirement;observed_score;maximum_score\nR001;x;5;5\n",
        name="requirements.csv",
    )
    assert "HEADER_NOT_FIRST_ROW" in _codes(csv_result)
    assert csv_result.delimiter == ";"
    assert len(csv_result.data) == 1

    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Data"
    sheet.append(["value", "calculated"])
    sheet.append([1, "=A2+1"])
    buffer = BytesIO()
    workbook.save(buffer)
    formula_result = read_data_file_with_validation(buffer.getvalue(), name="formula.xlsx", sheet_name="Data")
    assert "FORMULA_CELL_NOT_EVALUATED" in _codes(formula_result)


def test_validation_json_csv_excel_and_html_outputs_are_auditable() -> None:
    hazard_result = validate_hazards(_hazards())
    requirement_result = validate_requirements(_requirements())
    summaries = [
        validation_summary(
            dataset_type="Hazards",
            filename="hazards.csv",
            data=hazard_result.data,
            findings=hazard_result.findings,
            required_columns=("hazard", "likelihood", "consequence"),
            validation_reference_date="2026-07-22",
        ),
        validation_summary(
            dataset_type="Requirements",
            filename="requirements.csv",
            data=requirement_result.data,
            findings=requirement_result.findings,
            required_columns=("requirement", "observed_score", "maximum_score"),
            validation_reference_date="2026-07-22",
        ),
    ]
    findings = [*hazard_result.findings, *requirement_result.findings]
    datasets = {
        "Hazards": hazard_result.data,
        "Requirements": requirement_result.data,
        "Mapping": None,
        "Critical-Control Profile": None,
    }
    json_fields = validation_json_fields(summaries, findings, validation_reference_date="2026-07-22")
    assert json_fields["validation_reference_date"] == "2026-07-22"
    assert "finding_counts_by_code" in json_fields
    assert json_fields["validation_limitations"] == VALIDATION_LIMITATION
    assert "code" in findings_frame(findings).to_csv(index=False)

    workbook = excel_bytes(
        hazard_result.data,
        requirement_result.data,
        {"bri_pct": calculate_bri(requirement_result.data), **json_fields},
        validation_summaries=summaries,
        validation_findings=findings,
        validation_datasets=datasets,
    )
    required_sheets = {
        "Validation_Summary",
        "Validation_Findings",
        "Invalid_Hazard_Records",
        "Invalid_Requirement_Records",
        "Invalid_Mapping_Records",
        "Invalid_Profile_Records",
    }
    assert required_sheets.issubset(pd.ExcelFile(BytesIO(workbook), engine="openpyxl").sheet_names)
    invalid_workbook = invalid_records_workbook_bytes(summaries, findings, datasets)
    assert required_sheets.issubset(pd.ExcelFile(BytesIO(invalid_workbook), engine="openpyxl").sheet_names)

    bri = calculate_bri(requirement_result.data)
    html = make_html_report(
        hazard_result.data,
        requirement_result.data,
        bri,
        "CONDITIONAL DEPLOYMENT",
        ["Test decision"],
        validation_findings=findings,
        validation_summaries=summaries,
        validation_reference_date="2026-07-22",
    )
    assert "<h2>Data Validation</h2>" in html
    assert "Validation reference date:</strong> 2026-07-22" in html
    assert "Invalid rows were retained for review and excluded from relevant calculations" in html
    assert "Appendix: Validation Findings" in html
    assert VALIDATION_LIMITATION in html
