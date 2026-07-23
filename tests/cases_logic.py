"""Independent unit and smoke tests for the MOBRA calculation engine."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest

from mobra.acceptance import (
    RISK_ACCEPTANCE_LIMITATION,
    RiskAcceptancePolicy,
    apply_risk_acceptance,
    risk_acceptance_summary,
    risk_source_summary,
)
from mobra.charts import heatmap_figure, risk_counts_figure
from mobra.critical_controls import (
    CRITICAL_CONTROL_LIMITATION,
    CRITICALITY_LEVELS,
    assess_critical_controls,
    critical_control_summary_table,
    validate_critical_control_profile,
)
from mobra.decisions import deployment_decision
from mobra.io import list_excel_sheets, read_data_file
from mobra.mapping import (
    ALLOWED_CONTROL_ROLES,
    ALLOWED_RELATIONSHIP_TYPES,
    REPRESENTATIVE_SOURCE_STATUS,
    mapping_coverage_summary,
    requirements_without_hazards,
    validate_mapping,
)
from mobra.readiness import calculate_bri, domain_readiness, failed_critical_controls
from mobra.reporting import make_html_report
from mobra.risk import RISK_COLORS, RISK_LEVELS, assert_heatmap_total, classify_risk, heatmap_counts, heatmap_total
from mobra.validation import validate_hazards, validate_requirements

ROOT = Path(__file__).parents[1]
MAPPING_PATH = ROOT / "sample_data" / "requirement_hazard_mapping.csv"
CRITICAL_PROFILE_PATH = ROOT / "sample_data" / "critical_control_profile.csv"
EXPECTED_SAMPLE_HEATMAP_CELLS = {
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
EXPECTED_SAMPLE_CATEGORY_TOTALS = {"Low": 0, "Moderate": 15, "High": 9, "Extreme": 0}


def _validated_sample_hazards() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.read_csv(ROOT / "sample_data" / "hazards_sample.csv")
    result = validate_hazards(raw)
    assert result.ok
    return raw, result.data


def _validated_mapping_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    hazards = validate_hazards(pd.read_csv(ROOT / "sample_data" / "hazards_sample.csv")).data
    requirements = validate_requirements(pd.read_csv(ROOT / "sample_data" / "requirements_sample.csv")).data
    mapping = pd.read_csv(MAPPING_PATH)
    return mapping, requirements, hazards


def _single_critical_profile(
    requirement_id: str,
    *,
    criticality_level: str = "Deployment-blocking",
    failure_disposition: str = "DO NOT DEPLOY",
    minimum_acceptable_score: int = 5,
    evidence_required: bool = True,
    incomplete_record_disposition: str = "DO NOT DEPLOY",
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "requirement_id": [requirement_id],
            "criticality_level": [criticality_level],
            "failure_disposition": [failure_disposition],
            "minimum_acceptable_score": [minimum_acceptable_score],
            "evidence_required": [evidence_required],
            "incomplete_record_disposition": [incomplete_record_disposition],
            "rationale": ["Focused test profile rationale"],
            "approval_status": ["Provisional — Expert and institutional approval required"],
            "source_status": ["Representative Demonstration Critical-Control Profile"],
        }
    )


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (1, "Low"),
        (4, "Low"),
        (5, "Moderate"),
        (9, "Moderate"),
        (10, "High"),
        (16, "High"),
        (17, "Extreme"),
        (25, "Extreme"),
    ],
)
def test_risk_boundaries(score: int, expected: str) -> None:
    assert classify_risk(score) == expected


@pytest.mark.parametrize("value", [0, 26, -1, None, "bad"])
def test_invalid_risk_score_is_not_a_category(value: object) -> None:
    assert classify_risk(value) in {"Invalid", "Unknown"}


def test_risk_score_is_likelihood_times_consequence() -> None:
    result = validate_hazards(pd.DataFrame({"hazard": ["x"], "likelihood": [3], "consequence": [5]}))
    assert result.ok
    assert result.data.loc[0, "risk_score"] == 15
    assert result.data.loc[0, "risk_category"] == "High"


@pytest.mark.parametrize(
    ("score", "category", "status"),
    [
        (4, "Low", "Acceptable"),
        (5, "Moderate", "Acceptable with monitoring"),
        (9, "Moderate", "Acceptable with monitoring"),
        (10, "High", "Conditional"),
        (16, "High", "Conditional"),
        (17, "Extreme", "Unacceptable"),
    ],
)
def test_provisional_acceptance_boundaries(score: int, category: str, status: str) -> None:
    hazards = pd.DataFrame(
        {
            "hazard_id": ["H001"],
            "risk_score": [score],
            "risk_category": [category],
            "recommended_action": ["Preserve this source action"],
        }
    )
    analyzed = apply_risk_acceptance(hazards)
    assert analyzed.loc[0, "decision_risk_score"] == score
    assert analyzed.loc[0, "decision_risk_category"] == category
    assert analyzed.loc[0, "decision_risk_source"] == "Inherent"
    assert analyzed.loc[0, "risk_acceptance_status"] == status
    assert analyzed.loc[0, "recommended_action"] == "Preserve this source action"


def test_valid_residual_risk_is_preferred_per_hazard() -> None:
    hazards = validate_hazards(
        pd.DataFrame(
            {
                "hazard": ["x"],
                "likelihood": [5],
                "consequence": [5],
                "residual_likelihood": [1],
                "residual_consequence": [2],
            }
        )
    ).data
    analyzed = apply_risk_acceptance(hazards)
    assert analyzed.loc[0, "risk_category"] == "Extreme"
    assert analyzed.loc[0, "decision_risk_score"] == 2
    assert analyzed.loc[0, "decision_risk_category"] == "Low"
    assert analyzed.loc[0, "decision_risk_source"] == "Residual"


def test_valid_calculated_residual_category_is_accepted_without_raw_pair() -> None:
    hazards = pd.DataFrame(
        {
            "hazard": ["x"],
            "risk_score": [20],
            "risk_category": ["Extreme"],
            "residual_risk_score": [8],
            "residual_risk_category": ["Moderate"],
        }
    )
    analyzed = apply_risk_acceptance(hazards)
    assert analyzed.loc[0, "decision_risk_score"] == 8
    assert analyzed.loc[0, "decision_risk_category"] == "Moderate"
    assert analyzed.loc[0, "decision_risk_source"] == "Residual"


def test_missing_residual_uses_explicit_inherent_screening_language() -> None:
    hazards = validate_hazards(pd.DataFrame({"hazard": ["x"], "likelihood": [2], "consequence": [5]})).data
    analyzed = apply_risk_acceptance(hazards)
    reason = analyzed.loc[0, "acceptance_reason"]
    assert analyzed.loc[0, "decision_risk_source"] == "Inherent"
    assert analyzed.loc[0, "risk_acceptance_status"] == "Conditional"
    assert "Inherent risk" in reason
    assert "screening" in reason
    assert "Valid residual-risk data" not in reason
    assert "residual risk remains" not in reason.lower()


def test_mixed_risk_sources_are_counted_without_silent_fallback() -> None:
    hazards = validate_hazards(
        pd.DataFrame(
            {
                "hazard": ["residual", "screening"],
                "likelihood": [5, 3],
                "consequence": [5, 4],
                "residual_likelihood": [1, pd.NA],
                "residual_consequence": [2, pd.NA],
            }
        )
    ).data
    analyzed = apply_risk_acceptance(hazards)
    summary = risk_source_summary(analyzed)
    assert analyzed["decision_risk_source"].tolist() == ["Residual", "Inherent"]
    assert summary["risk_source_used"] == "Mixed"
    assert summary["residual_hazard_count"] == 1
    assert summary["inherent_screening_hazard_count"] == 1

    req = validate_requirements(
        pd.DataFrame({"requirement": ["ok"], "observed_score": [5], "maximum_score": [5], "evidence": ["present"]})
    ).data
    _, reasons = deployment_decision(analyzed, req, 100.0)
    mixed_reasons = [reason for reason in reasons if reason.startswith("Mixed decision-risk sources were used")]
    assert mixed_reasons == [
        "Mixed decision-risk sources were used: 1 hazard(s) used residual data, 1 used inherent screening, and 0 were unavailable."
    ]


@pytest.mark.parametrize("column", ["likelihood", "consequence"])
def test_invalid_likelihood_or_consequence_is_reported(column: str) -> None:
    row = {"hazard": ["x"], "likelihood": [3], "consequence": [4]}
    row[column] = [6]
    result = validate_hazards(pd.DataFrame(row))
    assert not result.ok
    assert result.invalid_rows == [0]


def test_bri_formula_is_weighted() -> None:
    req = pd.DataFrame({"observed_score": [4, 3, 5], "maximum_score": [5, 5, 5]})
    assert calculate_bri(req) == 80.0


def test_bri_zero_maximum_is_nan_and_invalid_row_is_reported() -> None:
    result = validate_requirements(pd.DataFrame({"requirement": ["x"], "observed_score": [0], "maximum_score": [0]}))
    assert not result.ok
    assert pd.isna(calculate_bri(result.data))


def test_observed_score_above_maximum_is_reported() -> None:
    result = validate_requirements(pd.DataFrame({"requirement": ["x"], "observed_score": [6], "maximum_score": [5]}))
    assert not result.ok
    assert "invalid requirement" in result.errors[0].lower()


def test_missing_required_columns_are_reported() -> None:
    result = validate_hazards(pd.DataFrame({"hazard": ["x"], "likelihood": [2]}))
    assert not result.ok
    assert "consequence" in result.missing_columns


def test_duplicate_ids_are_reported() -> None:
    result = validate_hazards(
        pd.DataFrame({"hazard_id": ["H1", "H1"], "hazard": ["a", "b"], "likelihood": [1, 2], "consequence": [1, 2]})
    )
    assert not result.ok
    assert result.duplicate_ids == ["H1"]


def test_blank_ids_are_reported() -> None:
    result = validate_hazards(pd.DataFrame({"hazard_id": [""], "hazard": ["a"], "likelihood": [1], "consequence": [1]}))
    assert not result.ok
    assert "blank" in result.errors[0].lower()


def test_sample_has_all_24_hazards_with_calculated_scores_and_categories() -> None:
    raw, hazards = _validated_sample_hazards()
    assert len(raw) == len(hazards) == 24
    assert hazards["hazard_id"].tolist() == [f"H{number:03d}" for number in range(1, 25)]
    expected_scores = raw["likelihood"] * raw["consequence"]
    assert hazards["risk_score"].tolist() == expected_scores.tolist()
    assert hazards["risk_category"].tolist() == expected_scores.map(classify_risk).tolist()


def test_sample_heatmap_has_expected_complete_5_by_5_counts() -> None:
    _, hazards = _validated_sample_hazards()
    counts = heatmap_counts(hazards)
    non_zero_cells = {
        (likelihood, consequence): int(counts.loc[consequence, likelihood])
        for consequence in counts.index
        for likelihood in counts.columns
        if counts.loc[consequence, likelihood]
    }
    assert counts.shape == (5, 5)
    assert counts.index.tolist() == [5, 4, 3, 2, 1]
    assert counts.columns.tolist() == [1, 2, 3, 4, 5]
    assert non_zero_cells == EXPECTED_SAMPLE_HEATMAP_CELLS
    assert heatmap_total(hazards) == int(counts.to_numpy().sum()) == 24
    assert_heatmap_total(hazards)


def test_sample_category_totals_match_approved_boundaries() -> None:
    _, hazards = _validated_sample_hazards()
    totals = hazards["risk_category"].value_counts().reindex(RISK_LEVELS, fill_value=0).astype(int).to_dict()
    assert totals == EXPECTED_SAMPLE_CATEGORY_TOTALS
    chart_totals = {trace.name: int(trace.y[0]) for trace in risk_counts_figure(hazards).data}
    assert chart_totals == EXPECTED_SAMPLE_CATEGORY_TOTALS


@pytest.mark.parametrize(("category", "expected_count"), [("High", 9), ("Extreme", 0)])
def test_sample_category_filter_recalculates_heatmap(category: str, expected_count: int) -> None:
    _, hazards = _validated_sample_hazards()
    filtered = hazards[hazards["risk_category"].eq(category)]
    assert len(filtered) == expected_count
    assert heatmap_total(filtered) == expected_count
    assert_heatmap_total(filtered)
    assert heatmap_counts(filtered).shape == (5, 5)


def test_heatmap_figure_uses_frequency_text_and_risk_score_backgrounds() -> None:
    _, hazards = _validated_sample_hazards()
    counts = heatmap_counts(hazards)
    figure = heatmap_figure(hazards)
    trace = figure.data[0]
    expected_scores = [[likelihood * consequence for likelihood in range(1, 6)] for consequence in [5, 4, 3, 2, 1]]
    assert list(trace.x) == [1, 2, 3, 4, 5]
    assert list(trace.y) == [5, 4, 3, 2, 1]
    assert trace.text.tolist() == counts.to_numpy().tolist()
    assert trace.z.tolist() == expected_scores
    assert {color for _, color in trace.colorscale} == set(RISK_COLORS.values())
    assert "Hazard count=%{text}" in trace.hovertemplate
    assert figure.layout.xaxis.title.text.startswith("Likelihood (L)")
    assert figure.layout.yaxis.title.text.startswith("Consequence (C)")


def test_demonstration_mapping_is_valid_unique_and_complete_for_hazards() -> None:
    mapping, requirements, hazards = _validated_mapping_inputs()
    result = validate_mapping(mapping, requirements, hazards)
    assert result.ok
    assert len(result.data) == result.data["mapping_id"].nunique() == 95
    assert not result.data.duplicated(["requirement_id", "hazard_id"]).any()
    assert result.data["mapping_rationale"].str.strip().ne("").all()
    assert set(result.data["relationship_type"]).issubset(ALLOWED_RELATIONSHIP_TYPES)
    assert set(result.data["control_role"]).issubset(ALLOWED_CONTROL_ROLES)
    assert result.data["source_status"].eq(REPRESENTATIVE_SOURCE_STATUS).all()
    assert set(result.data["hazard_id"]) == {f"H{number:03d}" for number in range(1, 25)}
    assert set(result.data["requirement_id"]).issubset(set(requirements["requirement_id"]))
    summary = mapping_coverage_summary(result.data, requirements, hazards)
    assert summary == {
        "mapping_links": 95,
        "hazards_mapped": 24,
        "hazards_total": 24,
        "hazard_coverage_pct": 100.0,
        "requirements_mapped": 53,
        "requirements_total": 60,
        "requirement_coverage_pct": 88.33,
        "critical_links": 55,
    }


@pytest.mark.parametrize(
    ("column", "unknown_id", "expected_message"),
    [("hazard_id", "H999", "Unknown hazard ID"), ("requirement_id", "R999", "Unknown requirement ID")],
)
def test_mapping_unknown_foreign_id_fails_validation(column: str, unknown_id: str, expected_message: str) -> None:
    mapping, requirements, hazards = _validated_mapping_inputs()
    mapping.loc[0, column] = unknown_id
    result = validate_mapping(mapping, requirements, hazards)
    assert not result.ok
    assert any(expected_message in message for message in result.errors)


def test_mapping_duplicate_id_and_duplicate_pair_fail_validation() -> None:
    mapping, requirements, hazards = _validated_mapping_inputs()
    duplicate_id = mapping.copy()
    duplicate_id.loc[1, "mapping_id"] = duplicate_id.loc[0, "mapping_id"]
    id_result = validate_mapping(duplicate_id, requirements, hazards)
    assert any("Duplicate mapping_id" in message for message in id_result.errors)

    duplicate_pair = pd.concat([mapping, mapping.iloc[[0]].assign(mapping_id="M999")], ignore_index=True)
    pair_result = validate_mapping(duplicate_pair, requirements, hazards)
    assert any("Duplicate requirement-hazard pair" in message for message in pair_result.errors)


@pytest.mark.parametrize(
    ("column", "invalid_value", "expected_message"),
    [
        ("mapping_rationale", "", "missing rationale"),
        ("relationship_type", "Unsupported", "Invalid relationship type"),
        ("control_role", "Unsupported", "Invalid control role"),
        ("critical_link", "", "blank critical_link"),
    ],
)
def test_mapping_required_content_and_enumerations_are_validated(
    column: str,
    invalid_value: str,
    expected_message: str,
) -> None:
    mapping, requirements, hazards = _validated_mapping_inputs()
    mapping[column] = mapping[column].astype(object)
    mapping.loc[0, column] = invalid_value
    result = validate_mapping(mapping, requirements, hazards)
    assert not result.ok
    assert any(expected_message in message for message in result.errors)


def test_unmapped_requirements_are_a_warning_and_coverage_finding() -> None:
    mapping, requirements, hazards = _validated_mapping_inputs()
    result = validate_mapping(mapping, requirements, hazards)
    assert result.ok
    assert any("Requirements without linked hazards" in warning for warning in result.warnings)
    assert requirements_without_hazards(result.data, requirements)["requirement_id"].tolist() == [
        "R005",
        "R009",
        "R047",
        "R050",
        "R053",
        "R056",
        "R059",
    ]


def test_mapping_csv_and_xlsx_input_round_trip() -> None:
    csv_mapping = read_data_file(MAPPING_PATH)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        csv_mapping.to_excel(writer, sheet_name="Mapping", index=False)
    xlsx_mapping = read_data_file(buffer.getvalue(), name="mapping.xlsx", sheet_name="Mapping")
    assert len(csv_mapping) == len(xlsx_mapping) == 95
    assert xlsx_mapping["mapping_id"].tolist() == csv_mapping["mapping_id"].tolist()


def test_critical_control_profile_has_exact_complete_coverage_and_valid_thresholds() -> None:
    requirements = validate_requirements(pd.read_csv(ROOT / "sample_data" / "requirements_sample.csv")).data
    profile = pd.read_csv(CRITICAL_PROFILE_PATH)
    result = validate_critical_control_profile(profile, requirements)
    assert result.ok
    assert len(profile) == profile["requirement_id"].nunique() == 60
    assert profile["requirement_id"].tolist() == [f"R{i:03d}" for i in range(1, 61)]
    assert not result.unknown_requirement_ids
    assert not result.missing_requirement_ids
    assert set(profile["source_status"]) == {"Representative Demonstration Critical-Control Profile"}
    assert set(profile["approval_status"]) == {"Provisional — Expert and institutional approval required"}
    assert profile["minimum_acceptable_score"].between(0, 5).all()
    maxima = requirements.set_index("requirement_id")["maximum_score"]
    assert all(row.minimum_acceptable_score <= maxima[row.requirement_id] for row in profile.itertuples(index=False))
    assert not (
        profile["criticality_level"].eq("Non-critical") & profile["failure_disposition"].eq("DO NOT DEPLOY")
    ).any()
    assert profile["criticality_level"].value_counts().reindex(CRITICALITY_LEVELS).to_dict() == {
        "Deployment-blocking": 21,
        "Conditional": 14,
        "Important": 24,
        "Non-critical": 1,
    }


def test_critical_profile_validation_detects_missing_unknown_and_duplicate_ids() -> None:
    requirements = validate_requirements(pd.read_csv(ROOT / "sample_data" / "requirements_sample.csv")).data
    profile = pd.read_csv(CRITICAL_PROFILE_PATH)
    missing = validate_critical_control_profile(profile.iloc[:-1], requirements)
    assert missing.missing_requirement_ids == ["R060"]
    unknown_profile = profile.copy()
    unknown_profile.loc[unknown_profile["requirement_id"].eq("R060"), "requirement_id"] = "R999"
    unknown = validate_critical_control_profile(unknown_profile, requirements)
    assert unknown.missing_requirement_ids == ["R060"]
    assert unknown.unknown_requirement_ids == ["R999"]
    duplicate = validate_critical_control_profile(
        pd.concat([profile, profile.iloc[[0]]], ignore_index=True), requirements
    )
    assert duplicate.duplicate_ids == ["R001"]


def test_critical_profile_validation_detects_missing_rationale_and_invalid_governance() -> None:
    requirements = validate_requirements(pd.read_csv(ROOT / "sample_data" / "requirements_sample.csv")).data
    profile = pd.read_csv(CRITICAL_PROFILE_PATH)
    invalid = profile.copy()
    invalid.loc[0, "rationale"] = ""
    invalid.loc[invalid["requirement_id"].eq("R060"), "failure_disposition"] = "DO NOT DEPLOY"
    invalid.loc[invalid["requirement_id"].eq("R001"), "minimum_acceptable_score"] = 6
    result = validate_critical_control_profile(invalid, requirements)
    assert not result.ok
    assert any("blank rationale" in error for error in result.errors)
    assert any("Non-critical requirement(s) cannot use DO NOT DEPLOY" in error for error in result.errors)
    assert any("invalid minimum_acceptable_score" in error for error in result.errors)
    assert any("exceeds maximum score" in error for error in result.errors)


def test_analyzed_workbook_includes_mapping_sheet() -> None:
    from app import excel_bytes

    mapping, requirements, hazards = _validated_mapping_inputs()
    validated_mapping = validate_mapping(mapping, requirements, hazards).data
    critical_profile = pd.read_csv(CRITICAL_PROFILE_PATH)
    critical_assessment = assess_critical_controls(requirements, critical_profile)
    payload = excel_bytes(
        hazards,
        requirements,
        {"mapping_links": len(validated_mapping)},
        validated_mapping,
        critical_profile=critical_profile,
        critical_control_assessment=critical_assessment,
    )
    workbook = pd.ExcelFile(BytesIO(payload), engine="openpyxl")
    assert "Requirement_Hazard_Map" in workbook.sheet_names
    assert "Risk_Acceptance_Summary" in workbook.sheet_names
    assert {
        "Critical_Control_Profile",
        "Critical_Control_Assessment",
        "Critical_Control_Summary",
    }.issubset(workbook.sheet_names)
    exported_mapping = pd.read_excel(BytesIO(payload), sheet_name="Requirement_Hazard_Map", engine="openpyxl")
    exported_hazards = pd.read_excel(BytesIO(payload), sheet_name="Analyzed_Hazards", engine="openpyxl")
    assert len(exported_mapping) == 95
    assert exported_mapping["mapping_id"].tolist() == validated_mapping["mapping_id"].tolist()
    assert {
        "decision_risk_score",
        "decision_risk_category",
        "decision_risk_source",
        "risk_acceptance_status",
        "acceptance_action_required",
        "acceptance_reason",
    }.issubset(exported_hazards.columns)
    exported_critical = pd.read_excel(
        BytesIO(payload),
        sheet_name="Critical_Control_Assessment",
        engine="openpyxl",
    )
    assert {
        "score_status",
        "evidence_status",
        "completion_status",
        "critical_control_outcome",
        "critical_control_disposition",
        "critical_control_reason",
    }.issubset(exported_critical.columns)


def test_demo_acceptance_counts_and_json_csv_exports() -> None:
    from app import csv_bytes

    hazards = apply_risk_acceptance(validate_hazards(pd.read_csv(ROOT / "sample_data" / "hazards_sample.csv")).data)
    policy = RiskAcceptancePolicy()
    summary = risk_acceptance_summary(hazards, policy)
    assert summary["risk_source_summary"] == {
        "risk_source_used": "Inherent",
        "risk_source_display": "Inherent screening",
        "residual_hazard_count": 0,
        "inherent_screening_hazard_count": 24,
        "unavailable_hazard_count": 0,
    }
    assert summary["acceptance_status_counts"] == {
        "Acceptable": 0,
        "Acceptable with monitoring": 15,
        "Conditional": 9,
        "Unacceptable": 0,
        "Not assessable": 0,
    }
    assert summary["corrective_action_required_count"] == 9
    assert summary["formal_approval_required_count"] == 9
    assert summary["missing_residual_assessment_count"] == 24
    assert summary["unacceptable_hazard_count"] == 0
    assert summary["risk_acceptance_limitations"] == RISK_ACCEPTANCE_LIMITATION
    json_payload = json.loads(json.dumps(summary))
    required_json_fields = {
        "risk_source_summary",
        "acceptance_status_counts",
        "unacceptable_hazard_count",
        "corrective_action_required_count",
        "formal_approval_required_count",
        "missing_residual_assessment_count",
        "risk_acceptance_policy",
        "risk_acceptance_limitations",
    }
    assert required_json_fields.issubset(json_payload)
    csv_export = pd.read_csv(BytesIO(csv_bytes(hazards)))
    assert required_json_fields.isdisjoint(csv_export.columns)
    assert {
        "decision_risk_score",
        "decision_risk_category",
        "decision_risk_source",
        "risk_acceptance_status",
        "acceptance_action_required",
        "acceptance_reason",
    }.issubset(csv_export.columns)


def test_domain_bri_is_weighted_by_maximum_points() -> None:
    req = pd.DataFrame({"domain": ["A", "A", "B"], "observed_score": [5, 0, 5], "maximum_score": [5, 5, 10]})
    domains = domain_readiness(req).set_index("domain")
    assert domains.loc["A", "readiness_pct"] == 50
    assert domains.loc["B", "readiness_pct"] == 50


def test_deployment_blocking_score_failure_overrides_high_bri() -> None:
    hazards = validate_hazards(pd.DataFrame({"hazard": ["x"], "likelihood": [1], "consequence": [1]})).data
    requirements = validate_requirements(
        pd.DataFrame(
            {
                "requirement_id": ["R001"],
                "requirement": ["Blocking control"],
                "observed_score": [4],
                "maximum_score": [5],
                "evidence": ["Complete evidence"],
            }
        )
    ).data
    assessment = assess_critical_controls(requirements, _single_critical_profile("R001"))
    assert assessment.data.loc[0, "score_status"] == "Below threshold"
    assert assessment.data.loc[0, "evidence_status"] == "Complete"
    assert assessment.data.loc[0, "completion_status"] == "Complete"
    decision, reasons = deployment_decision(
        hazards,
        requirements,
        100.0,
        critical_control_assessment=assessment,
    )
    assert decision == "DO NOT DEPLOY"
    assert any("R001 (Blocking control)" in reason for reason in reasons)
    assert any("A high BRI cannot override" in reason for reason in reasons)


def test_deployment_blocking_missing_evidence_is_separate_from_score_and_blocks() -> None:
    requirements = validate_requirements(
        pd.DataFrame(
            {
                "requirement_id": ["R001"],
                "requirement": ["Blocking control"],
                "observed_score": [5],
                "maximum_score": [5],
                "evidence": [pd.NA],
            }
        )
    ).data
    assessment = assess_critical_controls(requirements, _single_critical_profile("R001"))
    row = assessment.data.iloc[0]
    assert row["score_status"] == "Meets threshold"
    assert row["evidence_status"] == "Missing"
    assert row["completion_status"] == "Complete"
    assert row["critical_control_disposition"] == "DO NOT DEPLOY"
    assert assessment.summary["evidence_deficiency_count"] == 1
    assert assessment.summary["incomplete_critical_record_count"] == 0


def test_incomplete_record_is_separate_from_score_and_evidence() -> None:
    requirements = pd.DataFrame(
        {
            "requirement_id": ["R001"],
            "requirement": ["Blocking control"],
            "observed_score": [pd.NA],
            "maximum_score": [5],
            "objective_evidence": ["Complete evidence"],
        }
    )
    assessment = assess_critical_controls(requirements, _single_critical_profile("R001"))
    row = assessment.data.iloc[0]
    assert row["score_status"] == "Not scorable"
    assert row["evidence_status"] == "Complete"
    assert row["completion_status"] == "Incomplete"
    assert assessment.summary["incomplete_critical_record_count"] == 1
    assert assessment.summary["evidence_deficiency_count"] == 0


def test_conditional_gap_caps_ready_without_automatic_block() -> None:
    hazards = validate_hazards(pd.DataFrame({"hazard": ["x"], "likelihood": [1], "consequence": [1]})).data
    requirements = validate_requirements(
        pd.DataFrame(
            {
                "requirement_id": ["R001"],
                "requirement": ["Conditional control"],
                "observed_score": [3],
                "maximum_score": [5],
                "evidence": ["Complete evidence"],
            }
        )
    ).data
    profile = _single_critical_profile(
        "R001",
        criticality_level="Conditional",
        failure_disposition="CONDITIONAL DEPLOYMENT",
        minimum_acceptable_score=4,
        incomplete_record_disposition="CONDITIONAL DEPLOYMENT",
    )
    assessment = assess_critical_controls(requirements, profile)
    decision, _ = deployment_decision(
        hazards,
        requirements,
        100.0,
        critical_control_assessment=assessment,
    )
    assert assessment.data.loc[0, "critical_control_outcome"] == "Conditional gap"
    assert assessment.data.loc[0, "compensating_control_required"]
    assert assessment.data.loc[0, "formal_approval_required"]
    assert decision == "CONDITIONAL DEPLOYMENT"


def test_important_gap_requires_correction_without_automatic_block() -> None:
    hazards = validate_hazards(pd.DataFrame({"hazard": ["x"], "likelihood": [1], "consequence": [1]})).data
    requirements = validate_requirements(
        pd.DataFrame(
            {
                "requirement_id": ["R001"],
                "requirement": ["Important control"],
                "observed_score": [3],
                "maximum_score": [5],
                "evidence": ["Complete evidence"],
            }
        )
    ).data
    profile = _single_critical_profile(
        "R001",
        criticality_level="Important",
        failure_disposition="CORRECTIVE ACTION REQUIRED",
        minimum_acceptable_score=4,
        incomplete_record_disposition="MANUAL REVIEW REQUIRED",
    )
    assessment = assess_critical_controls(requirements, profile)
    decision, reasons = deployment_decision(
        hazards,
        requirements,
        100.0,
        critical_control_assessment=assessment,
    )
    assert assessment.data.loc[0, "critical_control_disposition"] == "CORRECTIVE ACTION REQUIRED"
    assert len(assessment.important_gaps) == 1
    assert decision == "READY FOR DEPLOYMENT"
    assert any("without an automatic deployment block" in reason for reason in reasons)


@pytest.mark.parametrize(
    ("criticality", "failure_disposition", "threshold", "expected_outcome"),
    [
        ("Conditional", "CONDITIONAL DEPLOYMENT", 4, "Pass"),
        ("Deployment-blocking", "DO NOT DEPLOY", 5, "Fail"),
    ],
)
def test_explicit_four_of_five_threshold_behavior(
    criticality: str,
    failure_disposition: str,
    threshold: int,
    expected_outcome: str,
) -> None:
    requirements = validate_requirements(
        pd.DataFrame(
            {
                "requirement_id": ["R001"],
                "requirement": ["Threshold control"],
                "observed_score": [4],
                "maximum_score": [5],
                "evidence": ["Complete evidence"],
            }
        )
    ).data
    incomplete_disposition = "CONDITIONAL DEPLOYMENT" if criticality == "Conditional" else "DO NOT DEPLOY"
    profile = _single_critical_profile(
        "R001",
        criticality_level=criticality,
        failure_disposition=failure_disposition,
        minimum_acceptable_score=threshold,
        incomplete_record_disposition=incomplete_disposition,
    )
    assessment = assess_critical_controls(requirements, profile)
    assert assessment.data.loc[0, "critical_control_outcome"] == expected_outcome


def test_demo_critical_control_governance_counts_and_ids() -> None:
    from app import csv_bytes

    requirements = validate_requirements(pd.read_csv(ROOT / "sample_data" / "requirements_sample.csv")).data
    assessment = assess_critical_controls(requirements, pd.read_csv(CRITICAL_PROFILE_PATH))
    assert assessment.ok
    assert assessment.summary["critical_control_outcome_counts"] == {
        "Pass": 50,
        "Conditional gap": 2,
        "Fail": 6,
        "Manual review": 1,
        "Not applicable": 1,
    }
    assert assessment.summary["blocking_requirement_ids"] == ["R003", "R024", "R057", "R058"]
    assert assessment.summary["conditional_requirement_ids"] == ["R006", "R021"]
    assert assessment.summary["important_gap_requirement_ids"] == ["R032", "R041", "R052"]
    assert assessment.summary["evidence_deficient_requirement_ids"] == ["R003", "R006", "R021", "R032", "R058"]
    assert assessment.summary["manual_review_requirement_ids"] == ["R032"]
    assert assessment.summary["formal_approval_required_count"] == 3
    assert assessment.summary["compensating_control_required_count"] == 2
    assert CRITICAL_CONTROL_LIMITATION in critical_control_summary_table(assessment)["value"].astype(str).tolist()
    required_json_fields = {
        "critical_control_profile_status",
        "criticality_level_counts",
        "critical_control_outcome_counts",
        "deployment_blocking_failure_count",
        "conditional_gap_count",
        "evidence_deficiency_count",
        "incomplete_critical_record_count",
        "manual_review_count",
        "formal_approval_required_count",
        "compensating_control_required_count",
        "blocking_requirement_ids",
        "conditional_requirement_ids",
        "critical_control_limitations",
    }
    assert required_json_fields.issubset(json.loads(json.dumps(assessment.summary)))
    assessment_csv = pd.read_csv(BytesIO(csv_bytes(assessment.data)))
    assert {
        "criticality_level",
        "minimum_acceptable_score",
        "score_status",
        "evidence_status",
        "completion_status",
        "critical_control_outcome",
        "critical_control_disposition",
        "critical_control_reason",
        "requires_manual_review",
        "compensating_control_required",
        "formal_approval_required",
    }.issubset(assessment_csv.columns)


def test_critical_control_override_cannot_be_bypassed_by_high_bri() -> None:
    hazards = validate_hazards(pd.DataFrame({"hazard": ["x"], "likelihood": [1], "consequence": [1]})).data
    req = validate_requirements(
        pd.DataFrame(
            {
                "requirement": ["critical"],
                "observed_score": [4],
                "maximum_score": [5],
                "critical_control": [True],
                "evidence": ["present"],
            }
        )
    ).data
    decision, reasons = deployment_decision(hazards, req, 99.0)
    assert decision == "DO NOT DEPLOY"
    assert reasons
    assert len(failed_critical_controls(req)) == 1


def test_string_false_critical_flag_is_not_treated_as_true() -> None:
    req = pd.DataFrame({"observed_score": [0], "maximum_score": [5], "critical_control": ["FALSE"]})
    assert failed_critical_controls(req).empty


def test_extreme_residual_risk_override() -> None:
    hazards = validate_hazards(
        pd.DataFrame(
            {
                "hazard": ["x"],
                "likelihood": [1],
                "consequence": [1],
                "residual_likelihood": [5],
                "residual_consequence": [5],
            }
        )
    ).data
    req = validate_requirements(pd.DataFrame({"requirement": ["ok"], "observed_score": [5], "maximum_score": [5]})).data
    decision, _ = deployment_decision(hazards, req, 100.0)
    assert decision == "DO NOT DEPLOY"


def test_high_residual_risk_prevents_ready_and_requires_approval() -> None:
    hazards = validate_hazards(
        pd.DataFrame(
            {
                "hazard": ["x"],
                "likelihood": [5],
                "consequence": [5],
                "residual_likelihood": [2],
                "residual_consequence": [5],
            }
        )
    ).data
    req = validate_requirements(
        pd.DataFrame({"requirement": ["ok"], "observed_score": [5], "maximum_score": [5], "evidence": ["present"]})
    ).data
    analyzed = apply_risk_acceptance(hazards)
    decision, reasons = deployment_decision(analyzed, req, 100.0)
    assert decision == "CONDITIONAL DEPLOYMENT"
    assert analyzed.loc[0, "corrective_action_required"]
    assert analyzed.loc[0, "formal_approval_required"]
    assert any("High residual risk" in reason for reason in reasons)


@pytest.mark.parametrize("missing_policy", ["require_residual_assessment", "not_assessable"])
def test_configured_missing_residual_policy_blocks_unassessable_deployment(missing_policy: str) -> None:
    policy = RiskAcceptancePolicy(missing_residual_policy=missing_policy)
    hazards = validate_hazards(pd.DataFrame({"hazard": ["x"], "likelihood": [1], "consequence": [1]})).data
    req = validate_requirements(
        pd.DataFrame({"requirement": ["ok"], "observed_score": [5], "maximum_score": [5], "evidence": ["present"]})
    ).data
    analyzed = apply_risk_acceptance(hazards, policy)
    decision, reasons = deployment_decision(analyzed, req, 100.0, risk_acceptance_policy=policy)
    assert analyzed.loc[0, "risk_acceptance_status"] == "Not assessable"
    assert decision == "DO NOT DEPLOY"
    assert any("Policy" in reason for reason in reasons)


def test_require_residual_for_ready_caps_missing_residual_at_conditional() -> None:
    policy = RiskAcceptancePolicy(require_residual_for_ready_decision=True)
    hazards = validate_hazards(pd.DataFrame({"hazard": ["x"], "likelihood": [1], "consequence": [1]})).data
    req = validate_requirements(
        pd.DataFrame({"requirement": ["ok"], "observed_score": [5], "maximum_score": [5], "evidence": ["present"]})
    ).data
    decision, reasons = deployment_decision(hazards, req, 100.0, risk_acceptance_policy=policy)
    assert decision == "CONDITIONAL DEPLOYMENT"
    assert any("requires residual assessment for READY" in reason for reason in reasons)


def test_extreme_inherent_screening_is_not_called_residual_and_caps_ready() -> None:
    hazards = validate_hazards(pd.DataFrame({"hazard": ["x"], "likelihood": [5], "consequence": [5]})).data
    req = validate_requirements(
        pd.DataFrame({"requirement": ["ok"], "observed_score": [5], "maximum_score": [5], "evidence": ["present"]})
    ).data
    decision, reasons = deployment_decision(hazards, req, 100.0)
    assert decision == "CONDITIONAL DEPLOYMENT"
    assert any("Extreme inherent screening risk" in reason for reason in reasons)
    assert not any("Extreme residual risk" in reason for reason in reasons)


def test_incomplete_critical_record_is_an_actual_override() -> None:
    hazards = validate_hazards(pd.DataFrame({"hazard": ["x"], "likelihood": [1], "consequence": [1]})).data
    req = validate_requirements(
        pd.DataFrame(
            {
                "requirement": ["critical"],
                "observed_score": [5],
                "maximum_score": [5],
                "critical_control": [True],
                "evidence": [pd.NA],
            }
        )
    ).data
    decision, reasons = deployment_decision(hazards, req, 100.0)
    assert decision == "DO NOT DEPLOY"
    assert any("critical record(s) are incomplete" in reason for reason in reasons)


def test_validation_error_is_an_actual_override() -> None:
    hazards = validate_hazards(pd.DataFrame({"hazard": ["x"], "likelihood": [1], "consequence": [1]})).data
    req = validate_requirements(
        pd.DataFrame({"requirement": ["ok"], "observed_score": [5], "maximum_score": [5], "evidence": ["present"]})
    ).data
    decision, reasons = deployment_decision(hazards, req, 100.0, validation_errors=["bad input"])
    assert decision == "DO NOT DEPLOY"
    assert any("Data validation" in reason for reason in reasons)


def test_decision_thresholds_without_overrides() -> None:
    hazards = validate_hazards(pd.DataFrame({"hazard": ["x"], "likelihood": [1], "consequence": [1]})).data
    req = validate_requirements(pd.DataFrame({"requirement": ["ok"], "observed_score": [5], "maximum_score": [5]})).data
    assert deployment_decision(hazards, req, 60)[0] == "DEPLOYMENT NOT RECOMMENDED"
    assert deployment_decision(hazards, req, 75)[0] == "CONDITIONAL DEPLOYMENT"
    assert deployment_decision(hazards, req, 90)[0] == "READY FOR DEPLOYMENT"


def test_csv_and_xlsx_readers_and_sheet_selection() -> None:
    csv = b"hazard,likelihood,consequence\nx,1,2\n"
    assert len(read_data_file(csv, name="x.csv")) == 1
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame({"a": [1]}).to_excel(writer, sheet_name="First", index=False)
        pd.DataFrame({"a": [2]}).to_excel(writer, sheet_name="Second", index=False)
    payload = buffer.getvalue()
    assert list_excel_sheets(type("Upload", (), {"name": "x.xlsx", "getvalue": lambda self: payload})()) == [
        "First",
        "Second",
    ]
    assert read_data_file(payload, name="x.xlsx", sheet_name="Second").iloc[0, 0] == 2


def test_html_report_is_standalone_and_contains_required_sections() -> None:
    hazards = validate_hazards(pd.read_csv(ROOT / "sample_data" / "hazards_sample.csv")).data
    req = validate_requirements(pd.read_csv(ROOT / "sample_data" / "requirements_sample.csv")).data
    mapping_result = validate_mapping(pd.read_csv(MAPPING_PATH), req, hazards)
    critical_profile = pd.read_csv(CRITICAL_PROFILE_PATH)
    critical_assessment = assess_critical_controls(req, critical_profile)
    bri = calculate_bri(req)
    decision, reasons = deployment_decision(
        hazards,
        req,
        bri,
        critical_control_assessment=critical_assessment,
    )
    html = make_html_report(
        hazards,
        req,
        bri,
        decision,
        reasons,
        mapping=mapping_result.data,
        mapping_validation_messages=mapping_result.warnings,
        critical_profile=critical_profile,
        critical_control_assessment=critical_assessment,
    )
    assert html.startswith("<!doctype html>")
    assert "<title>MOBRA — Mobile Operational Biosecurity Readiness Assessment Report</title>" in html
    assert "not clinical, operational, regulatory, or field validation" in html
    assert "Critical-control failures" in html
    assert "Critical-Control Governance" in html
    assert "Deployment-blocking controls" in html
    assert "Conditional gaps" in html
    assert "How to use this application" in html
    assert "What MOBRA does not do" in html
    assert "Disclaimer and Limitation of Liability" in html
    assert "Evidence deficiencies" in html
    assert "Manual-review items" in html
    assert "Appendix: Critical-Control Profile" in html
    assert "Appendix: Full Critical-Control Assessment" in html
    assert CRITICAL_CONTROL_LIMITATION in html
    assert "R003" in html and "R058" in html
    assert "Risk Acceptance" in html
    assert "Inherent screening" in html
    assert "Missing residual assessment" in html
    assert "Per-hazard Risk Acceptance" in html
    assert RISK_ACCEPTANCE_LIMITATION in html
    assert "decision_risk_source" in html
    assert "risk_acceptance_status" in html
    assert '<div class="label">Hazards analyzed</div><div class="metric">24</div>' in html
    assert "Heat-map cells: 24 records" in html
    assert all(f"H{number:03d}" in html for number in range(1, 25))
    assert "Requirement-to-Hazard Mapping" in html
    assert "Representative Requirement-to-Hazard Mapping" in html
    assert '<div class="label">Mapping links</div><div class="metric">95</div>' in html
    assert "R005" in html and "R059" in html
    assert "M095" in html
    assert "plotly" in html.lower()


def test_streamlit_app_smoke() -> None:
    """Execute the default demonstration path without a browser or network."""
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(ROOT / "app.py"))
    app.run(timeout=30)
    assert not app.exception
    assert app.title[0].value == "MOBRA — Mobile Operational Biosecurity Readiness Assessment"
