"""Independent unit and smoke tests for the MOBRA calculation engine."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest

from mobra.decisions import deployment_decision
from mobra.io import list_excel_sheets, read_data_file
from mobra.readiness import calculate_bri, domain_readiness, failed_critical_controls
from mobra.reporting import make_html_report
from mobra.risk import assert_heatmap_total, classify_risk, heatmap_counts, heatmap_total
from mobra.validation import validate_hazards, validate_requirements


ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize(
    ("score", "expected"),
    [(1, "Low"), (4, "Low"), (5, "Moderate"), (9, "Moderate"), (10, "High"), (16, "High"), (17, "Extreme"), (25, "Extreme")],
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
    result = validate_hazards(pd.DataFrame({"hazard_id": ["H1", "H1"], "hazard": ["a", "b"], "likelihood": [1, 2], "consequence": [1, 2]}))
    assert not result.ok
    assert result.duplicate_ids == ["H1"]


def test_blank_ids_are_reported() -> None:
    result = validate_hazards(pd.DataFrame({"hazard_id": [""], "hazard": ["a"], "likelihood": [1], "consequence": [1]}))
    assert not result.ok
    assert "blank" in result.errors[0].lower()


def test_heatmap_total_matches_valid_hazards_and_filtered_subset() -> None:
    raw = pd.read_csv(ROOT / "sample_data" / "hazards_sample.csv")
    result = validate_hazards(raw)
    assert result.ok
    assert heatmap_total(result.data) == len(raw) == 24
    filtered = result.data[result.data["risk_category"].isin(["Low", "Moderate"])]
    assert_heatmap_total(filtered)
    assert heatmap_counts(filtered).to_numpy().sum() == len(filtered)


def test_domain_bri_is_weighted_by_maximum_points() -> None:
    req = pd.DataFrame({"domain": ["A", "A", "B"], "observed_score": [5, 0, 5], "maximum_score": [5, 5, 10]})
    domains = domain_readiness(req).set_index("domain")
    assert domains.loc["A", "readiness_pct"] == 50
    assert domains.loc["B", "readiness_pct"] == 50


def test_critical_control_override_cannot_be_bypassed_by_high_bri() -> None:
    hazards = validate_hazards(pd.DataFrame({"hazard": ["x"], "likelihood": [1], "consequence": [1]})).data
    req = validate_requirements(pd.DataFrame({"requirement": ["critical"], "observed_score": [4], "maximum_score": [5], "critical_control": [True], "evidence": ["present"]})).data
    decision, reasons = deployment_decision(hazards, req, 99.0)
    assert decision == "DO NOT DEPLOY"
    assert reasons
    assert len(failed_critical_controls(req)) == 1


def test_string_false_critical_flag_is_not_treated_as_true() -> None:
    req = pd.DataFrame({"observed_score": [0], "maximum_score": [5], "critical_control": ["FALSE"]})
    assert failed_critical_controls(req).empty


def test_extreme_residual_risk_override() -> None:
    hazards = validate_hazards(pd.DataFrame({"hazard": ["x"], "likelihood": [1], "consequence": [1], "residual_likelihood": [5], "residual_consequence": [5]})).data
    req = validate_requirements(pd.DataFrame({"requirement": ["ok"], "observed_score": [5], "maximum_score": [5]})).data
    decision, _ = deployment_decision(hazards, req, 100.0)
    assert decision == "DO NOT DEPLOY"


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
    assert list_excel_sheets(type("Upload", (), {"name": "x.xlsx", "getvalue": lambda self: payload})()) == ["First", "Second"]
    assert read_data_file(payload, name="x.xlsx", sheet_name="Second").iloc[0, 0] == 2


def test_html_report_is_standalone_and_contains_required_sections() -> None:
    hazards = validate_hazards(pd.read_csv(ROOT / "sample_data" / "hazards_sample.csv")).data
    req = validate_requirements(pd.read_csv(ROOT / "sample_data" / "requirements_sample.csv")).data
    bri = calculate_bri(req)
    decision, reasons = deployment_decision(hazards, req, bri)
    html = make_html_report(hazards, req, bri, decision, reasons)
    assert html.startswith("<!doctype html>")
    assert "MOBRA Assessment Report" in html
    assert "Critical-control failures" in html
    assert "plotly" in html.lower()


def test_streamlit_app_smoke() -> None:
    """Execute the default demonstration path without a browser or network."""
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(ROOT / "app.py"))
    app.run(timeout=30)
    assert not app.exception
    assert app.title[0].value.endswith("MOBRA Dashboard")
