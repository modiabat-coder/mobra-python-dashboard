# MOBRA — Mobile Operational Biosecurity Readiness Assessment

[![MOBRA tests](https://github.com/modiabat-coder/mobra-python-dashboard/actions/workflows/tests.yml/badge.svg)](https://github.com/modiabat-coder/mobra-python-dashboard/actions/workflows/tests.yml)

MOBRA — Mobile Operational Biosecurity Readiness Assessment — is a Streamlit decision-support prototype for external-dataset-based computational verification. It calculates laboratory hazard risk, the Biosecurity Readiness Index (BRI), domain BRI, critical-control status, and a transparent deployment recommendation.

The prototype also includes a separate many-to-many **Operational Requirement ↔ Objective Evidence ↔ Representative Hazard** mapping module for coverage analysis and methodology illustration.

This software is not clinical, operational, regulatory, or field validation of MOBRA.

## Core rules (unchanged)

```text
Risk Score = Likelihood × Consequence
Low      = 1–4
Moderate = 5–9
High     = 10–16
Extreme  = 17–25

BRI (%) = sum(observed requirement scores)
          / sum(maximum requirement scores) × 100
```

An Extreme residual risk, a deployment-blocking critical-control failure, a validation error, or an uncomputable BRI produces **DO NOT DEPLOY** regardless of how high the BRI is. With no override, BRI <70% is **DEPLOYMENT NOT RECOMMENDED**, 70–84.9% is **CONDITIONAL DEPLOYMENT**, and BRI ≥85% may qualify for **READY FOR DEPLOYMENT**. A High residual risk caps the result at **CONDITIONAL DEPLOYMENT** and requires corrective action and formal approval.

## Inherent, residual, and decision-support risk

Inherent risk is calculated from the original Likelihood and Consequence fields. Residual risk is used for a hazard only when that hazard has a valid residual Likelihood and Consequence pair, or a valid calculated residual category. The analyzed hazard output preserves the inherent fields and adds `decision_risk_score`, `decision_risk_category`, and `decision_risk_source` so Residual, Inherent, Mixed, and Unavailable sources are never silently conflated.

The provisional `RiskAcceptancePolicy` defaults are:

- Low: **Acceptable** — routine controls and periodic review.
- Moderate: **Acceptable with monitoring** — maintain controls, monitor indicators, and review changes.
- High: **Conditional** — corrective action, a responsible person, target date, and formal approval before acceptance.
- Extreme: **Unacceptable** — stop or prohibit deployment/activity until risk is reduced and formally reassessed.

These are provisional MOBRA software rules for computational verification and methodology illustration. They are not universal biosafety standards or institutionally approved acceptance criteria.

When residual data are absent, `missing_residual_policy="use_inherent_for_screening"` uses inherent risk as an explicitly labeled screening substitute. It never labels the result as residual risk, and READY does not imply that residual assessment occurred. Other supported policies are `require_residual_assessment` and `not_assessable`. Setting `require_residual_for_ready_decision=True` caps a result with missing residual assessments at **CONDITIONAL DEPLOYMENT**. Policy fields also configure the four dispositions and High-risk corrective-action/formal-approval flags.

## Critical-Control Governance

The Biosecurity Readiness Index and critical-control governance answer different questions. BRI remains the weighted total of all observed scores divided by all maximum scores; no low-scoring critical requirement is removed from that calculation. The separate governance layer determines whether a specific control creates a deployment override. **A high BRI cannot override a deployment-blocking critical-control failure.**

`sample_data/critical_control_profile.csv` contains one transparent provisional profile row for each requirement R001–R060. It preserves the source `critical_control` flags while assigning an explicit level and threshold:

- **Deployment-blocking:** a failed score or required-evidence deficiency produces **DO NOT DEPLOY**. These controls normally require 5/5.
- **Conditional:** a gap caps the result at **CONDITIONAL DEPLOYMENT** and requires corrective action, a named owner, target date, formal approval, and a compensating control. Most use 4/5; a control may explicitly require 5/5.
- **Important:** a gap produces **CORRECTIVE ACTION REQUIRED** or manual review without independently blocking deployment.
- **Non-critical:** no automatic deployment override. The demonstration profile uses a zero override threshold only for the one Non-critical requirement.

The assessment reports score, evidence, and record completeness independently. `score_status` can be Meets threshold, Below threshold, or Not scorable. `evidence_status` can be Complete, Missing, Incomplete, or Not assessed. `completion_status` identifies whether the requirement record itself is scorable and complete; missing or incomplete evidence is not silently treated as the same condition.

Profile validation requires complete one-to-one ID coverage, controlled dispositions, thresholds from 0 to 5 that do not exceed the requirement maximum, rationale, approval status, and source status. Invalid profile data pause governance analysis without changing raw BRI or hazard calculations.

## Project structure

```text
mobra_app_project/
├── app.py                         # Streamlit UI
├── mobra/
│   ├── io.py                       # CSV/XLSX/XLS readers and unified-file split
│   ├── validation.py               # aliases, schema validation, dates, quality flags
│   ├── risk.py                     # scoring, categories, heat-map counts
│   ├── readiness.py                # BRI, domain BRI, critical controls
│   ├── acceptance.py               # risk sources and provisional acceptance policy
│   ├── critical_controls.py        # profile validation and structured governance assessment
│   ├── mapping.py                  # many-to-many mapping validation and coverage
│   ├── decisions.py                # deployment policy and overrides
│   ├── charts.py                   # Plotly figures
│   └── reporting.py                # standalone UTF-8 HTML report
├── sample_data/                    # 24 hazards, 60 ORL requirements, mapping, templates
│   └── critical_control_profile.csv # separate provisional R001–R060 governance profile
├── tests/                          # subsystem, regression, integration, property, and safety tests
│   ├── conftest.py                 # reusable valid, invalid, empty, file, and demo fixtures
│   ├── test_risk.py
│   ├── test_readiness.py
│   ├── test_decisions.py
│   ├── test_acceptance.py
│   ├── test_mapping.py
│   ├── test_critical_controls.py
│   ├── test_validation_*.py
│   ├── test_io.py
│   ├── test_reporting.py
│   ├── test_exports.py
│   ├── test_regression_demo_data.py
│   └── test_integration_pipeline.py
├── scripts/verify_project.py       # cross-platform complete quality gate
├── verify.ps1                      # Windows wrapper for the complete quality gate
├── .github/workflows/tests.yml     # Linux 3.11/3.12 and Windows 3.12 CI
├── generate_demo_report.py         # regenerate MOBRA_Demo_Report.html
└── TECHNICAL_REVIEW.md             # review findings and verification record
```

## Windows PowerShell setup

From the extracted project folder:

```powershell
py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pytest -q
python generate_demo_report.py
streamlit run app.py
```

If `py` is not available, use `python -m venv .venv`. The app opens at <http://localhost:8501>. Stop Streamlit with `Ctrl+C`.

## Input files

The UI supports:

- Two separate files: a hazard register plus an ORL/requirements file.
- One unified CSV/XLSX/XLS file with a `record_type` column containing hazard/risk and requirement/ORL/control values, or with both field sets present on separate rows.
- An optional separate requirement-to-hazard mapping in CSV/XLSX/XLS format. The included demonstration mode loads `requirement_hazard_mapping.csv` automatically.
- An optional separate critical-control profile in CSV/XLSX/XLS format. The included demonstration mode loads `critical_control_profile.csv` automatically.
- CSV encoded as UTF-8, UTF-8 with BOM, CP1256, or Latin-1.
- XLSX and legacy XLS, with explicit sheet selection.

Hazard required fields are equivalent to `hazard`, `likelihood`, and `consequence`. Requirement required fields are equivalent to `requirement`, `observed_score`, and `maximum_score`. Automatic aliases cover the full MOBRA field list; the sidebar also provides manual overrides for required columns. Missing optional fields are reported rather than causing a crash.

Invalid rows remain visible in the validation preview but are excluded from calculations. Duplicate IDs, out-of-range risk scales, impossible observed/max scores, malformed dates, missing evidence, and blank critical-control flags are reported explicitly.

## Structured data validation

Every finding uses the shared `ValidationFinding` model: stable finding ID, dataset type, severity, machine-readable code, message, row/record/column location, original and normalized values, suggested action, and whether the finding blocks analysis. The three severity levels are:

- **Error:** invalid or inconsistent input that blocks the affected row, calculation, dataset, or dependent module.
- **Warning:** a material quality or completeness issue that requires review but may not prevent the relevant calculation.
- **Information:** traceability, normalization, coverage, or noteworthy context that does not itself invalidate a record.

Common codes include `MISSING_REQUIRED_COLUMN`, `DUPLICATE_ID`, `BLANK_ID`, `INVALID_NUMERIC_VALUE`, `NON_INTEGER_VALUE`, `VALUE_OUT_OF_RANGE`, `INVALID_BOOLEAN`, `INVALID_DATE`, `INCOMPLETE_RESIDUAL_PAIR`, `INCONSISTENT_CALCULATED_RISK`, `UNKNOWN_REQUIREMENT_ID`, `UNKNOWN_HAZARD_ID`, `MISSING_PROFILE_ROW`, and `SUSPICIOUS_DUPLICATE_RECORD`. File checks add codes for unsupported types, empty/oversized files, malformed CSV rows, ambiguous delimiters, encoding problems, corrupt/password-protected workbooks, missing worksheets, displaced headers, and formulas without cached results.

Parsed fields retain companion raw columns such as `likelihood_raw`, `consequence_raw`, `observed_score_raw`, `maximum_score_raw`, `critical_control_raw`, and `due_date_raw`. Uploaded calculated risk values are retained separately before MOBRA recalculates the authoritative score and category. Each analyzed row includes `validation_status`, finding counts, `analysis_eligible`, and `exclusion_reason`; hazards also expose inherent/residual eligibility and requirements expose BRI/critical-control eligibility.

Cross-dataset checks require exact ID matches, detect case-only and whitespace differences, validate mapping/profile references and coverage, and flag repeated wording or identical core records as possible duplicates. Invalid records are never removed from review exports. Calculations consume only the rows eligible for the fields they require, and the UI/report state the included and excluded counts.

Date findings use the explicit `validation_reference_date` captured at validation runtime. Ambiguous dates are not guessed; ISO `YYYY-MM-DD` is recommended. Overdue status therefore reflects the documented runtime reference date, not an undisclosed fixed date.

The **Data Validation Center** provides overall metrics, dataset summaries, filters, finding details, affected-record inspection, and the three dedicated downloads `MOBRA_Validation_Findings.csv`, `MOBRA_Validation_Summary.csv`, and `MOBRA_Invalid_Records.xlsx`.

Successful input validation means only that the data conform to the implemented software rules. It does not establish scientific, clinical, regulatory, operational, or field validity.

## Requirement-to-hazard mapping

The mapping is stored in `sample_data/requirement_hazard_mapping.csv` as a separate many-to-many dataset. A hazard may link to multiple requirements and a requirement may link to multiple hazards; the hazard and requirement source tables are not flattened with a single related-ID column.

The included links are **representative demonstration mappings** intended for software verification and methodology illustration. They have not undergone expert content-validity assessment and must not be treated as scientifically or institutionally validated relationships. Future subject-matter-expert review may add, remove, or modify relationships.

The mapping tab reports hazard and requirement coverage, unmapped records, critical links, link rankings, domain coverage, filters, selected-hazard evidence, and a readable selected-hazard Sankey diagram. Invalid mapping data pauses only the mapping module; risk scoring, BRI, and deployment analysis remain available.

## Outputs

The **Data & exports** tab provides:

- Calculated hazards and requirements as UTF-8 CSV.
- A summary JSON file.
- An analyzed XLSX workbook with a `Risk_Acceptance_Summary` sheet.
- Critical-control profile, assessment, and summary CSV downloads.
- An analyzed XLSX workbook with `Critical_Control_Profile`, `Critical_Control_Assessment`, and `Critical_Control_Summary` sheets when the profile is valid.
- A self-contained HTML report that opens directly in a browser.
- The validated requirement-to-hazard mapping and mapping-coverage tables as UTF-8 CSV.
- An analyzed XLSX workbook with a `Requirement_Hazard_Map` sheet when valid mapping data are available.
- Hazard and ORL template CSV files.
- Validation findings and dataset summaries as UTF-8 CSV.
- A dedicated invalid-record workbook and validation fields in summary JSON.
- `Validation_Summary`, `Validation_Findings`, `Invalid_Hazard_Records`, `Invalid_Requirement_Records`, `Invalid_Mapping_Records`, and `Invalid_Profile_Records` sheets in the analyzed workbook.
- A Data Validation section and full findings appendix in the standalone HTML report.

The heat map always rebuilds from the currently selected risk-category filter. A programmatic assertion verifies that cell counts equal the number of valid filtered hazards.

## Tests and report generation

```powershell
python -m pytest -q
python -m pytest -m unit
python -m pytest -m regression
python -m pytest -m "not slow"
python -m pytest --cov=mobra --cov=app --cov-report=term-missing --cov-report=xml
python generate_demo_report.py
./verify.ps1
```

On Linux, macOS, or Windows, the equivalent complete check is `python scripts/verify_project.py`. Install `requirements-dev.txt` first. The supported interpreter versions are Python 3.11 and 3.12.

The suite is organized by subsystem and includes bounded Hypothesis properties, full-pipeline integration tests, mutation-safety and deterministic-output checks, export-contract tests, and a dedicated regression test against the actual demonstration files. The regression contract protects 24 hazards, 60 requirements, 95 links, 60 profile rows, BRI 86.7%, the exact risk/heat-map and governance totals, the **DO NOT DEPLOY** decision, and blocking IDs R003, R024, R057, and R058.

Coverage includes branches and is enforced at 82% overall; the current suite is above that threshold. The principal uncovered areas are defensive Streamlit presentation branches and uncommon malformed/legacy file-reader paths. These are documented rather than covered with artificial tests.

GitHub Actions runs Ruff and Black, executes coverage on Ubuntu with Python 3.11 and 3.12, generates and uploads the coverage XML and demonstration report, and runs the non-slow core suite on Windows with Python 3.12. The workflow uses only repository contents and does not expose or require secrets.

`MOBRA_Demo_Report.html` contains a generation timestamp and Plotly-generated identifiers. CI regenerates it and verifies that it is nonempty, while report tests protect stable headings and content; CI intentionally does not require a clean Git diff after report generation.

Passing these tests and CI checks confirms conformance to the implemented MOBRA software rules and protected demonstration outputs. It does **not** constitute scientific, clinical, operational, regulatory, or field validation.

## GitHub and Streamlit Community Cloud

Create a repository containing this folder, commit the source and sample data, and push it to GitHub. In Streamlit Community Cloud select the repository, branch, and `app.py` as the main file. Keep `requirements.txt` at the project root. Do not commit `.venv`, secrets, or real laboratory records.

## Scientific and data limitations

The included 24-hazard and 60-requirement files are representative demonstration data. External incident datasets may not contain 1–5 Likelihood/Consequence scores; any future transformation must be explicit, reproducible, documented, and kept separate from raw columns. A high BRI is not evidence that a mission is safe when a critical-control or extreme-risk override is present.

The included mapping is likewise representative rather than expert-validated. Its relationships support computational verification and transparent discussion; they are not a substitute for formal content-validity assessment by qualified biosafety, biosecurity, laboratory, operational, and institutional reviewers.

Risk-acceptance dispositions require institutional approval and expert validation before operational use. MOBRA does not replace authorized risk acceptance by accountable institutional personnel.

Critical-control classifications and thresholds are also provisional demonstration rules. They have not undergone institutional authorization, expert content-validity assessment, or operational field validation and must not be treated as universal or regulatory criteria.

## Interface, operational tools, and resources

The application now presents a Home/Assessment Setup workflow with Data Validation, Readiness and BRI, Hazard Analysis, Requirement–Hazard Mapping, Critical-Control Governance, Reports and Exports, and Resources and Contact areas. The introduction, “How to use this application”, “What MOBRA does not do”, contextual result explanations, refresh control, and confirmed Reset Assessment control are available in the UI.

Resources can generate the current-schema printable ORL and hazard forms, blank import workbooks, a combined `MOBRA_Field_Assessment_Package.xlsx`, and paper PDFs. Handwritten PDFs require manual entry later; MOBRA does not claim OCR recognition. These forms use the existing 60 requirements and 24-hazard demonstration schemas and do not change calculations.

The public author contact is **Mohammad Ahmad Yousef E'Diabat** at [modiabat@gmail.com](mailto:modiabat@gmail.com). This is not an SMTP credential and assessment results are never sent to the author automatically. Optional email backup is disabled unless SMTP secrets are explicitly configured; it requires recipient validation, consent, authorization, data-classification confirmation, and a size limit. A derived-output ZIP fallback remains available and excludes uploaded source files by default.

The final approved manuscript is expected at `docs/MOBRA_Manuscript.pdf` and is not fabricated when missing. Before final production release, obtain the author-approved final manuscript PDF and place it at that path.

The normative evidence base is loaded from `config/normative_resources.json`; it includes WHO LBM4, WHO laboratory biosecurity guidance, WHO rapid-response mobile-laboratory standards, the current WHO 2025–2026 transport edition, ISO 35001:2019 with Amendment 1:2024, ISO 31000:2018, ISO/TS 7446:2026, and BMBL sixth edition. Licensed ISO resources are link-only and labelled **Do not redistribute**. Supporting scientific literature is kept separately in `config/supporting_literature.json`; no publisher PDFs are bundled and no issuing-organization endorsement is claimed. See [docs/NORMATIVE_EVIDENCE_BASE.md](docs/NORMATIVE_EVIDENCE_BASE.md) for review and attribution rules.

The full disclaimer appears in the Home page, Resources and Contact, generated HTML reports, PDF/Excel templates, backup packages, this README, and `TECHNICAL_REVIEW.md`. Final legal wording should be reviewed by qualified legal counsel.
