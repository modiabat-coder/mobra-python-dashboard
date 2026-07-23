"""Shared, copy-safe pytest fixtures for MOBRA quality assurance."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from hypothesis import HealthCheck, settings

from mobra.acceptance import RiskAcceptancePolicy, apply_risk_acceptance
from mobra.critical_controls import assess_critical_controls
from mobra.mapping import validate_mapping
from mobra.validation import validate_hazards, validate_requirements

settings.register_profile(
    "mobra_ci",
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
settings.load_profile("mobra_ci")


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).parents[1]


@pytest.fixture
def valid_hazards() -> pd.DataFrame:
    return validate_hazards(
        pd.DataFrame(
            {
                "hazard_id": ["H001", "H002"],
                "hazard": ["Controlled exposure", "Transport spill"],
                "domain": ["Operations", "Transport"],
                "likelihood": [2, 3],
                "consequence": [4, 3],
                "residual_likelihood": [1, 2],
                "residual_consequence": [3, 2],
            }
        )
    ).data


@pytest.fixture
def valid_requirements() -> pd.DataFrame:
    return validate_requirements(
        pd.DataFrame(
            {
                "requirement_id": ["R001", "R002"],
                "requirement": ["Authority is documented", "Training is verified"],
                "domain": ["Governance", "Training"],
                "objective_evidence": ["Approved policy", "Training record"],
                "observed_score": [5, 4],
                "maximum_score": [5, 5],
                "critical_control": [True, False],
                "corrective_action": ["None", "Complete refresher"],
                "responsible_person": ["Director", "Training lead"],
            }
        )
    ).data


@pytest.fixture
def valid_mapping() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "mapping_id": ["M001", "M002"],
            "requirement_id": ["R001", "R002"],
            "hazard_id": ["H001", "H002"],
            "relationship_type": ["Preventive", "Detective"],
            "mapping_rationale": ["Policy prevents exposure", "Training detects unsafe handling"],
            "control_role": ["Primary", "Supporting"],
            "critical_link": [True, False],
            "source_status": ["Representative Demonstration Mapping"] * 2,
        }
    )


@pytest.fixture
def valid_critical_control_profile() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "requirement_id": ["R001", "R002"],
            "criticality_level": ["Deployment-blocking", "Important"],
            "failure_disposition": ["DO NOT DEPLOY", "CORRECTIVE ACTION REQUIRED"],
            "minimum_acceptable_score": [5, 4],
            "evidence_required": [True, True],
            "incomplete_record_disposition": ["DO NOT DEPLOY", "MANUAL REVIEW REQUIRED"],
            "rationale": ["Authority is mandatory", "Training supports readiness"],
            "approval_status": ["Provisional"] * 2,
            "source_status": ["Representative Demonstration Critical-Control Profile"] * 2,
        }
    )


@pytest.fixture
def empty_dataset() -> pd.DataFrame:
    return pd.DataFrame()


@pytest.fixture
def invalid_hazard_records() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "hazard_id": ["H001", "H002"],
            "hazard": ["Valid hazard", "Invalid hazard"],
            "likelihood": [2, "invalid"],
            "consequence": [3, 4],
        }
    )


@pytest.fixture
def invalid_requirement_records() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "requirement_id": ["R001", "R002"],
            "requirement": ["Valid requirement", "Invalid requirement"],
            "observed_score": [4, "invalid"],
            "maximum_score": [5, 5],
            "critical_control": [False, False],
            "objective_evidence": ["Record", "Record"],
        }
    )


@pytest.fixture
def mixed_inherent_residual_hazards() -> pd.DataFrame:
    return apply_risk_acceptance(
        validate_hazards(
            pd.DataFrame(
                {
                    "hazard_id": ["H001", "H002"],
                    "hazard": ["Residual assessed", "Inherent screening"],
                    "likelihood": [5, 3],
                    "consequence": [5, 4],
                    "residual_likelihood": [1, pd.NA],
                    "residual_consequence": [2, pd.NA],
                }
            )
        ).data,
        RiskAcceptancePolicy(),
    )


@pytest.fixture
def temporary_csv_file(tmp_path: Path) -> Path:
    path = tmp_path / "hazards.csv"
    pd.DataFrame({"hazard": ["x"], "likelihood": [1], "consequence": [2]}).to_csv(path, index=False)
    return path


@pytest.fixture
def temporary_xlsx_file(tmp_path: Path) -> Path:
    path = tmp_path / "requirements.xlsx"
    pd.DataFrame({"requirement": ["x"], "observed_score": [5], "maximum_score": [5]}).to_excel(
        path, index=False, sheet_name="Data"
    )
    return path


@pytest.fixture(scope="session")
def demo_raw_data(repo_root: Path) -> dict[str, pd.DataFrame]:
    sample = repo_root / "sample_data"
    return {
        "hazards": pd.read_csv(sample / "hazards_sample.csv"),
        "requirements": pd.read_csv(sample / "requirements_sample.csv"),
        "mapping": pd.read_csv(sample / "requirement_hazard_mapping.csv"),
        "profile": pd.read_csv(sample / "critical_control_profile.csv"),
    }


@pytest.fixture
def demo_data(demo_raw_data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    return {name: data.copy(deep=True) for name, data in demo_raw_data.items()}


@pytest.fixture
def demo_pipeline(demo_data: dict[str, pd.DataFrame]) -> dict[str, object]:
    hazard_result = validate_hazards(demo_data["hazards"])
    requirement_result = validate_requirements(demo_data["requirements"])
    hazards = apply_risk_acceptance(hazard_result.data, RiskAcceptancePolicy())
    requirements = requirement_result.data
    mapping_result = validate_mapping(demo_data["mapping"], requirements, hazards)
    critical_assessment = assess_critical_controls(requirements, demo_data["profile"])
    return {
        "hazard_result": hazard_result,
        "requirement_result": requirement_result,
        "hazards": hazards,
        "requirements": requirements,
        "mapping_result": mapping_result,
        "critical_assessment": critical_assessment,
    }
