"""Independent unit and smoke tests for the MOBRA calculation engine."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import pytest

from mobra.acceptance import RiskAcceptancePolicy, apply_risk_acceptance
from mobra.auth import hash_password, load_auth_config, verify_password
from mobra.config import (
    DECISION_CONDITIONAL,
    DECISION_DO_NOT_DEPLOY,
    DECISION_LABELS,
    DECISION_READY,
    count_phrase,
)
from mobra.critical_controls import (
    assess_critical_controls,
    validate_critical_control_profile,
)
from mobra.decisions import deployment_decision
from mobra.educational_media import (
    educational_media_package,
    load_educational_media,
)
from mobra.charts import executive_radial_gauge, heatmap_figure
from mobra.io import list_excel_sheets, read_data_file, read_json_collections
from mobra.mapping import mapping_coverage_summary, validate_mapping
from mobra.manuscript import manuscript_is_current, manuscript_metadata
from mobra.mission_map import mission_map_deck, synthetic_mission_stages
from mobra.operational_tools import (
    build_field_assessment_package,
    build_hazard_pdf,
    build_orl_pdf,
)
from mobra.readiness import calculate_bri, domain_readiness, failed_critical_controls
from mobra.reporting import make_excel_workbook, make_html_report
from mobra.resources import (
    load_normative_resources,
    load_supporting_literature,
    validate_resource_manifest,
)
from mobra.risk import assert_heatmap_total, classify_risk, heatmap_counts, heatmap_total
from mobra.validation import (
    suggest_column_mapping,
    validate_hazards,
    validate_requirements,
)
from ui.components import metric_grid_html
from ui.layout import PAGE_ORDER


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
    assert deployment_decision(hazards, req, 60)[0] == DECISION_DO_NOT_DEPLOY
    assert deployment_decision(hazards, req, 75)[0] == DECISION_CONDITIONAL
    assert deployment_decision(hazards, req, 90)[0] == DECISION_READY


def test_decision_labels_are_exact_and_centralized() -> None:
    assert DECISION_LABELS == (
        "DO NOT DEPLOY",
        "CONDITIONAL DEPLOYMENT",
        "READY TO DEPLOY",
    )


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (0, "0 hazards"),
        (1, "1 hazard"),
        (2, "2 hazards"),
        (1, "1 critical control"),
        (11, "11 critical controls"),
    ],
)
def test_count_phrase_uses_real_grammar(count: int, expected: str) -> None:
    noun = "critical control" if "control" in expected else "hazard"
    assert count_phrase(count, noun) == expected


def test_demonstration_safety_invariants() -> None:
    hazards = validate_hazards(
        pd.read_csv(ROOT / "sample_data" / "hazards_sample.csv")
    ).data
    requirements = validate_requirements(
        pd.read_csv(ROOT / "sample_data" / "requirements_sample.csv")
    ).data
    bri = calculate_bri(requirements)
    decision, reasons = deployment_decision(hazards, requirements, bri)
    assert len(hazards) == 24
    assert bri == pytest.approx(86.7, abs=0.05)
    assert len(failed_critical_controls(requirements)) == 11
    assert decision == DECISION_DO_NOT_DEPLOY
    assert any("11 critical controls" in reason for reason in reasons)


def test_high_risk_requires_defined_action_for_conditional_deployment() -> None:
    hazards = validate_hazards(
        pd.DataFrame(
            {
                "hazard": ["x"],
                "likelihood": [3],
                "consequence": [4],
                "corrective_action": ["Complete containment review"],
            }
        )
    ).data
    req = validate_requirements(
        pd.DataFrame(
            {
                "requirement": ["ok"],
                "observed_score": [5],
                "maximum_score": [5],
            }
        )
    ).data
    assert deployment_decision(hazards, req, 90)[0] == "CONDITIONAL DEPLOYMENT"
    hazards["corrective_action"] = "Not provided"
    assert deployment_decision(hazards, req, 90)[0] == "DO NOT DEPLOY"


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


def test_json_import_supports_nested_and_flattened_records() -> None:
    payload = b'{"metadata":{"source":"test"},"records":[{"hazard":"x","likelihood":1,"consequence":2,"owner":{"name":"A"}}]}'
    collections = read_json_collections(payload)
    assert "records" in collections
    assert collections["records"].loc[0, "owner.name"] == "A"
    frame = read_data_file(payload, name="x.json")
    assert frame.loc[0, "hazard"] == "x"


def test_empty_and_duplicate_header_files_are_rejected() -> None:
    with pytest.raises(ValueError, match="empty"):
        read_data_file(b"", name="empty.csv")
    with pytest.raises(ValueError, match="duplicate column"):
        read_data_file(
            b"hazard,likelihood,Likelihood,consequence\nx,1,1,2\n",
            name="duplicate.csv",
        )


@pytest.mark.parametrize(
    "payload",
    [b"", b"{bad json", b'{"values":[1,2,3]}'],
)
def test_invalid_json_structures_have_clear_errors(payload: bytes) -> None:
    with pytest.raises(ValueError):
        read_data_file(payload, name="x.json")


def test_xls_reader_selects_legacy_xlrd_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_read_excel(*args: object, **kwargs: object) -> pd.DataFrame:
        captured.update(kwargs)
        return pd.DataFrame({"a": [1]})

    monkeypatch.setattr(pd, "read_excel", fake_read_excel)
    result = read_data_file(b"legacy-xls-placeholder", name="x.xls")
    assert len(result) == 1
    assert captured["engine"] == "xlrd"


def test_column_mapping_reports_confidence_and_missing_required_fields() -> None:
    frame = pd.DataFrame(
        {"Hazard Name": ["x"], "Probability": [2], "Severity": [3]}
    )
    mapping = suggest_column_mapping(frame, "hazards").set_index("standard_field")
    assert mapping.loc["hazard", "mapping_status"] == "Matched"
    assert mapping.loc["likelihood", "confidence_pct"] == 90
    missing = suggest_column_mapping(
        pd.DataFrame({"Hazard": ["x"]}),
        "hazards",
    ).set_index("standard_field")
    assert missing.loc["consequence", "mapping_status"] == "Missing"


def test_heatmap_axes_tooltips_and_record_names_are_consistent() -> None:
    hazards = validate_hazards(
        pd.DataFrame(
            {
                "hazard_id": ["H1"],
                "hazard": ["Named hazard"],
                "likelihood": [4],
                "consequence": [5],
            }
        )
    ).data
    figure = heatmap_figure(hazards)
    heatmap = figure.data[0]
    assert list(heatmap.x) == [1, 2, 3, 4, 5]
    assert list(heatmap.y) == [5, 4, 3, 2, 1]
    assert figure.layout.xaxis.title.text == "Consequence"
    assert figure.layout.yaxis.title.text == "Likelihood"
    assert "Risk Score" in heatmap.hovertemplate
    assert "Hazard Count" in heatmap.hovertemplate
    assert "Named hazard" in str(heatmap.customdata)
    assert "No hazards assigned" in str(heatmap.customdata)


def test_html_report_is_standalone_and_contains_required_sections() -> None:
    hazards = validate_hazards(pd.read_csv(ROOT / "sample_data" / "hazards_sample.csv")).data
    req = validate_requirements(pd.read_csv(ROOT / "sample_data" / "requirements_sample.csv")).data
    bri = calculate_bri(req)
    decision, reasons = deployment_decision(hazards, req, bri)
    html = make_html_report(hazards, req, bri, decision, reasons)
    assert html.startswith("<!doctype html>")
    assert "MOBRA Assessment Report" in html
    assert "Critical-control Findings" in html
    assert "plotly" in html.lower()
    assert "Synthetic Demonstration Data" in html
    assert '<header class="report-header">' in html
    assert '<div class="report-kpi-grid">' in html
    assert "@page{size:A4" in html
    assert "@media(max-width:900px)" in html
    assert "@media(max-width:560px)" in html
    assert '<div class="table-wrap">' in html
    assert (
        "Cell color represents the MOBRA risk category based on Likelihood × Consequence."
        in html
    )
    assert "X-axis = Consequence" not in html  # Semantics are expressed in the chart itself.
    assert "Likelihood" in html and "Consequence" in html


def test_metric_grid_has_responsive_structure() -> None:
    html = metric_grid_html(
        [
            ("Overall BRI", "86.7%", "Weighted readiness"),
            ("Hazards", 24, "Structurally valid imported records"),
            ("Failed Critical Controls", 11, "Non-bypassable override"),
            ("Decision", DECISION_DO_NOT_DEPLOY, "Final rule output"),
        ]
    )
    assert html.startswith('<div class="mobra-metric-grid"')
    assert html.count('class="mobra-metric-card"') == 4
    assert "--metric-columns:4" in html


def test_navigation_preserves_twelve_pages_and_adds_two_controlled_views() -> None:
    original_pages = {
        "Home",
        "Data Import",
        "Data Validation",
        "Requirements Assessment",
        "Hazard Register",
        "Risk Analysis",
        "Readiness Dashboard",
        "Deployment Decision",
        "Corrective Actions",
        "Reports and Export",
        "Methodology",
        "About MOBRA",
    }
    assert len(PAGE_ORDER) == 14
    assert len(set(PAGE_ORDER)) == 14
    assert original_pages.issubset(PAGE_ORDER)
    assert {"Mission Map", "Research and References"}.issubset(PAGE_ORDER)


def test_password_hash_round_trip_and_rejects_wrong_password() -> None:
    encoded = hash_password(
        "correct horse battery staple",
        salt=b"0123456789abcdef",
    )
    assert encoded.startswith("pbkdf2_sha256$600000$")
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("incorrect", encoded)
    assert not verify_password("correct horse battery staple", "invalid")


def test_authentication_enables_only_from_external_configuration() -> None:
    disabled = load_auth_config(environ={}, secret_auth={})
    assert not disabled.enabled
    configured = load_auth_config(
        environ={},
        secret_auth={
            "username": "reviewer",
            "password_hash": "pbkdf2_sha256$600000$00$00",
            "session_timeout_minutes": 45,
        },
    )
    assert configured.enabled and configured.ready
    assert configured.username == "reviewer"
    assert configured.session_timeout_minutes == 45


def test_login_gate_and_logout_streamlit_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("MOBRA_AUTH_ENABLED", "true")
    monkeypatch.setenv("MOBRA_AUTH_USERNAME", "reviewer")
    monkeypatch.setenv(
        "MOBRA_AUTH_PASSWORD_HASH",
        hash_password("test-password", salt=b"0123456789abcdef"),
    )
    app = AppTest.from_file(str(ROOT / "app.py")).run(timeout=30)
    assert not app.exception
    assert [item.label for item in app.text_input] == ["Username", "Password"]
    assert not app.radio
    app.text_input[0].set_value("reviewer")
    app.text_input[1].set_value("test-password")
    app.button[0].click()
    app.run(timeout=30)
    assert not app.exception
    assert app.radio[0].label == "Navigation"
    assert any(button.label == "Log out" for button in app.button)


def test_executive_radial_gauges_are_context_only_and_bounded() -> None:
    readiness = executive_radial_gauge(86.7, "Overall BRI")
    risk_load = executive_radial_gauge(37.5, "High / Extreme Risk Load", higher_is_better=False)
    assert readiness.data[0].value == pytest.approx(86.7)
    assert risk_load.data[0].value == pytest.approx(37.5)
    assert readiness.data[0].gauge.axis.range == (0, 100)
    assert readiness.data[0].gauge.steps[0].range == (0, 50)
    assert risk_load.data[0].gauge.steps[0].range == (0, 25)


def test_synthetic_mission_map_reflects_non_bypassable_decision() -> None:
    stages = synthetic_mission_stages(
        DECISION_DO_NOT_DEPLOY,
        86.7,
        11,
        24,
    )
    assert len(stages) == 4
    assert stages["hazard_count"].eq(24).all()
    assert stages["failed_controls"].eq(11).all()
    assert stages.loc[stages["stage"].eq("Site setup gate"), "status"].item() == "Blocked"
    assert len(mission_map_deck(stages).layers) == 3


def test_priority_references_and_supporting_literature_are_available() -> None:
    resources = load_normative_resources()
    resource_ids = {resource["resource_id"] for resource in resources}
    assert {
        "WHO-01",
        "WHO-03",
        "WHO-04",
        "BMBL-01",
        "ISO-01",
        "ISO-02",
    }.issubset(resource_ids)
    literature = load_supporting_literature()
    assert literature
    assert all(item.get("title") for item in literature)


def test_preserved_mapping_and_governance_features_do_not_change_invariants() -> None:
    hazards = validate_hazards(
        pd.read_csv(ROOT / "sample_data" / "hazards_sample.csv")
    ).data
    requirements = validate_requirements(
        pd.read_csv(ROOT / "sample_data" / "requirements_sample.csv")
    ).data
    mapping = validate_mapping(
        pd.read_csv(ROOT / "sample_data" / "requirement_hazard_mapping.csv"),
        requirements,
        hazards,
    )
    profile = validate_critical_control_profile(
        pd.read_csv(ROOT / "sample_data" / "critical_control_profile.csv"),
        requirements,
    )
    governance = assess_critical_controls(requirements, profile.data)
    coverage = mapping_coverage_summary(mapping.data, requirements, hazards)

    assert mapping.ok and profile.ok and governance.ok
    assert coverage["hazards_mapped"] == 24
    assert coverage["hazard_coverage_pct"] == 100
    assert calculate_bri(requirements) == pytest.approx(86.7, abs=0.05)
    assert len(failed_critical_controls(requirements)) == 11
    decision, _ = deployment_decision(
        hazards,
        requirements,
        calculate_bri(requirements),
    )
    assert decision == DECISION_DO_NOT_DEPLOY


def test_preserved_risk_acceptance_cannot_disable_extreme_risk_block() -> None:
    with pytest.raises(ValueError, match="non-bypassable"):
        RiskAcceptancePolicy(extreme_blocks_deployment=False)
    hazards = validate_hazards(
        pd.DataFrame(
            {
                "hazard_id": ["HX"],
                "hazard": ["Extreme representative hazard"],
                "likelihood": [5],
                "consequence": [5],
            }
        )
    ).data
    assessed = apply_risk_acceptance(hazards, RiskAcceptancePolicy())
    assert assessed.loc[0, "risk_acceptance_status"] == "Unacceptable"
    assert bool(assessed.loc[0, "formal_approval_required"])


def test_preserved_field_tools_and_resource_catalogue_are_portable() -> None:
    hazards = validate_hazards(
        pd.read_csv(ROOT / "sample_data" / "hazards_sample.csv")
    ).data
    requirements = validate_requirements(
        pd.read_csv(ROOT / "sample_data" / "requirements_sample.csv")
    ).data
    package = build_field_assessment_package(requirements, hazards)
    sheets = pd.ExcelFile(BytesIO(package), engine="openpyxl").sheet_names
    assert "ORL_Assessment" in sheets
    assert "Hazard_Register" in sheets
    assert build_orl_pdf(requirements).startswith(b"%PDF")
    assert build_hazard_pdf(hazards).startswith(b"%PDF")
    resources = load_normative_resources()
    assert resources
    assert validate_resource_manifest(resources) == []


def test_preserved_media_and_manuscript_assets_are_complete_and_relative() -> None:
    media = load_educational_media()
    assert len(media) == 10
    with ZipFile(BytesIO(educational_media_package(media))) as archive:
        names = archive.namelist()
    assert names
    assert all(":" not in name and not name.startswith("/") for name in names)
    manuscript = manuscript_metadata()
    assert manuscript["manuscript_available"]
    assert manuscript["manuscript_page_count"]
    assert manuscript_is_current()


def test_user_facing_sources_have_no_retired_labels_or_placeholder_grammar() -> None:
    paths = [
        *sorted((ROOT / "mobra").glob("*.py")),
        *sorted((ROOT / "ui").glob("*.py")),
        ROOT / "README.md",
        ROOT / "TECHNICAL_REVIEW.md",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    retired = "READY " + "/" + " DEPLOY"
    placeholder = "Control" + "(s)"
    assert retired not in text
    assert placeholder not in text


def test_excel_report_contains_required_worksheets() -> None:
    hazards = validate_hazards(
        pd.read_csv(ROOT / "sample_data" / "hazards_sample.csv")
    ).data
    req = validate_requirements(
        pd.read_csv(ROOT / "sample_data" / "requirements_sample.csv")
    ).data
    bri = calculate_bri(req)
    decision, reasons = deployment_decision(hazards, req, bri)
    workbook = make_excel_workbook(hazards, req, bri, decision, reasons)
    sheets = pd.ExcelFile(BytesIO(workbook), engine="openpyxl").sheet_names
    assert sheets == [
        "Executive Summary",
        "Domain Summary",
        "Requirements",
        "Hazard Register",
        "Risk Matrix",
        "Critical Controls",
        "Corrective Actions",
        "Validation Issues",
    ]


def test_streamlit_app_smoke() -> None:
    """Execute the default demonstration path without a browser or network."""
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(ROOT / "app.py"))
    app.run(timeout=30)
    assert not app.exception
    assert app.radio[0].label == "Navigation"
    assert app.radio[0].value == "Home"
    assert any("Risk Matrix & Heatmap" in option for option in app.radio[0].options)


def test_every_application_page_smoke() -> None:
    """Run every navigation target with the synthetic dataset."""
    from streamlit.testing.v1 import AppTest

    pages = [
        "Home",
        "Data Import",
        "Data Validation",
        "Requirements Assessment",
        "Hazard Register",
        "Risk Analysis",
        "Readiness Dashboard",
        "Mission Map",
        "Deployment Decision",
        "Corrective Actions",
        "Reports and Export",
        "Methodology",
        "Research and References",
        "About MOBRA",
    ]
    for page in pages:
        app = AppTest.from_file(str(ROOT / "app.py"))
        app.session_state["active_page"] = page
        app.run(timeout=60)
        assert not app.exception, page
