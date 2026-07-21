"""Regenerate the included standalone demonstration report."""

from pathlib import Path

import pandas as pd

from mobra.decisions import deployment_decision
from mobra.readiness import calculate_bri
from mobra.reporting import make_html_report
from mobra.validation import validate_hazards, validate_requirements


BASE = Path(__file__).resolve().parent
OUT = BASE / "MOBRA_Demo_Report.html"


def main() -> None:
    hazard_result = validate_hazards(pd.read_csv(BASE / "sample_data" / "hazards_sample.csv"))
    requirement_result = validate_requirements(pd.read_csv(BASE / "sample_data" / "requirements_sample.csv"))
    if hazard_result.errors or requirement_result.errors:
        raise SystemExit("Demo data failed validation: " + "; ".join(hazard_result.errors + requirement_result.errors))
    hazards, requirements = hazard_result.data, requirement_result.data
    bri = calculate_bri(requirements)
    decision, reasons = deployment_decision(hazards, requirements, bri)
    html = make_html_report(
        hazards,
        requirements,
        bri,
        decision,
        reasons,
        hazard_filename="hazards_sample.csv",
        requirements_filename="requirements_sample.csv",
        validation_messages=hazard_result.warnings + requirement_result.warnings,
    )
    OUT.write_text(html, encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
