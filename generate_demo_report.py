"""Regenerate the included standalone demonstration report."""

from pathlib import Path

import pandas as pd

from mobra.acceptance import RiskAcceptancePolicy, apply_risk_acceptance
from mobra.critical_controls import assess_critical_controls
from mobra.decisions import deployment_decision
from mobra.mapping import validate_mapping
from mobra.readiness import calculate_bri
from mobra.reporting import make_html_report
from mobra.validation import validate_hazards, validate_requirements
from mobra.validation_findings import validate_cross_dataset_consistency, validation_summary

BASE = Path(__file__).resolve().parent
OUT = BASE / "MOBRA_Demo_Report.html"


def main() -> None:
    hazard_result = validate_hazards(pd.read_csv(BASE / "sample_data" / "hazards_sample.csv"))
    requirement_result = validate_requirements(pd.read_csv(BASE / "sample_data" / "requirements_sample.csv"))
    if hazard_result.errors or requirement_result.errors:
        raise SystemExit("Demo data failed validation: " + "; ".join(hazard_result.errors + requirement_result.errors))
    acceptance_policy = RiskAcceptancePolicy()
    hazards = apply_risk_acceptance(hazard_result.data, acceptance_policy)
    requirements = requirement_result.data
    critical_profile = pd.read_csv(BASE / "sample_data" / "critical_control_profile.csv")
    critical_assessment = assess_critical_controls(requirements, critical_profile)
    if not critical_assessment.ok:
        raise SystemExit(
            "Demo critical-control profile failed validation: " + "; ".join(critical_assessment.validation.errors)
        )
    mapping_result = validate_mapping(
        pd.read_csv(BASE / "sample_data" / "requirement_hazard_mapping.csv"),
        requirements,
        hazards,
    )
    if mapping_result.errors:
        raise SystemExit("Demo mapping failed validation: " + "; ".join(mapping_result.errors))
    cross_result = validate_cross_dataset_consistency(
        hazards,
        requirements,
        mapping_result.data,
        critical_assessment.validation.data,
    )
    all_findings = [
        *hazard_result.findings,
        *requirement_result.findings,
        *mapping_result.findings,
        *critical_assessment.validation.findings,
        *cross_result.findings,
    ]
    reference_date = hazard_result.validation_reference_date
    validation_summaries = [
        validation_summary(
            dataset_type="Hazards",
            filename="hazards_sample.csv",
            data=hazards,
            findings=hazard_result.findings,
            required_columns=("hazard", "likelihood", "consequence"),
            missing_columns=hazard_result.missing_columns,
            duplicate_ids=hazard_result.duplicate_ids,
            validation_reference_date=reference_date,
        ),
        validation_summary(
            dataset_type="Requirements",
            filename="requirements_sample.csv",
            data=requirements,
            findings=requirement_result.findings,
            required_columns=("requirement", "observed_score", "maximum_score"),
            missing_columns=requirement_result.missing_columns,
            duplicate_ids=requirement_result.duplicate_ids,
            validation_reference_date=reference_date,
        ),
        validation_summary(
            dataset_type="Mapping",
            filename="requirement_hazard_mapping.csv",
            data=mapping_result.data,
            findings=mapping_result.findings,
            required_columns=tuple(mapping_result.data.columns),
            missing_columns=mapping_result.missing_columns,
            duplicate_ids=mapping_result.duplicate_ids,
            validation_reference_date=reference_date,
        ),
        validation_summary(
            dataset_type="Critical-Control Profile",
            filename="critical_control_profile.csv",
            data=critical_assessment.validation.data,
            findings=critical_assessment.validation.findings,
            required_columns=tuple(critical_assessment.validation.data.columns),
            missing_columns=critical_assessment.validation.missing_columns,
            duplicate_ids=critical_assessment.validation.duplicate_ids,
            validation_reference_date=reference_date,
        ),
    ]
    bri = calculate_bri(requirements)
    decision, reasons = deployment_decision(
        hazards,
        requirements,
        bri,
        risk_acceptance_policy=acceptance_policy,
        critical_control_assessment=critical_assessment,
    )
    html = make_html_report(
        hazards,
        requirements,
        bri,
        decision,
        reasons,
        hazard_filename="hazards_sample.csv",
        requirements_filename="requirements_sample.csv",
        validation_messages=[finding.message for finding in all_findings if finding.severity in {"Error", "Warning"}],
        mapping=mapping_result.data,
        mapping_validation_messages=mapping_result.warnings,
        risk_acceptance_policy=acceptance_policy,
        critical_profile=critical_assessment.validation.data,
        critical_control_assessment=critical_assessment,
        critical_profile_validation_messages=critical_assessment.validation.warnings,
        validation_findings=all_findings,
        validation_summaries=validation_summaries,
        validation_reference_date=reference_date,
    )
    OUT.write_text(html, encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
