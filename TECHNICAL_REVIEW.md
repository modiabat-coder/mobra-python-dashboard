# MOBRA — Mobile Operational Biosecurity Readiness Assessment: Technical Review

## Problems found in the supplied package

- The application was a single `app.py`; validation, scoring, readiness, decisions, charts, I/O, and reporting were tightly coupled.
- The original validator calculated a risk score even when Likelihood/Consequence were missing or non-integer, did not validate duplicate IDs, and did not parse dates or residual-risk fields.
- Critical-control flags and evidence completeness were only partially checked. The original report generator did not apply the BRI threshold or document critical-control overrides.
- The UI heat map was created before the risk filter and asserted against the unfiltered row count, so filtered cell totals could be misleading.
- The original report omitted input metadata, validation/data-quality results, critical-control failures, methodology, and limitations.
- The original standalone generator did not distinguish High inherent screening risk from High residual risk; the corrected decision layer now applies source-specific wording and overrides.
- Excel sheet selection, unified-file splitting, templates, workbook export, and editable preview were absent.
- No separate many-to-many requirement-to-hazard dataset or mapping validation and coverage workflow was present.
- The deployment code selected one risk-category column for the entire dataset. If any residual category existed, hazards without valid residual data could be evaluated inconsistently while decision messages still called the result residual risk.
- `invalid_critical` generated a decision reason for an incomplete critical record, but that variable was not itself included in the final non-bypassable decision condition.
- The earlier critical-control function treated every flagged control as deployment-blocking, defaulted its minimum threshold to the maximum score, and conflated a score gap, missing evidence, and an incomplete record into one failure result.
- During the clean Streamlit smoke test, the refactored UI initially exposed duplicate Plotly element IDs when the same domain chart appeared in two tabs; unique chart keys were added and the smoke test was rerun successfully.

## Changes made

- Added the `mobra` package with independent `io`, `validation`, `risk`, `readiness`, `decisions`, `charts`, and `reporting` modules.
- Added alias mapping and manual required-column overrides, CSV encoding fallbacks, XLSX/XLS sheet selection, unified-file support, duplicate-ID checks, numeric/date validation, residual-risk calculations, evidence and incomplete-record flags, and safe exports.
- Preserved the fixed Risk Score, category boundaries, and weighted BRI formula. Added a configurable policy object without changing default thresholds.
- Made extreme residual risk, failed/incomplete critical controls, validation errors, and an uncomputable BRI non-bypassable deployment overrides.
- Rebuilt the filtered heat map and assert that cell totals equal valid filtered hazards.
- Added unique Streamlit keys for repeated Plotly charts so the app runs cleanly in Streamlit's element registry.
- Added an editable preview, validation panel, KPI cards, top-risk and corrective-control tables, CSV/XLSX/JSON/template downloads, and a standalone UTF-8 report.
- Regenerated `MOBRA_Demo_Report.html` after the changes and expanded automated tests.
- Added a separate representative requirement-to-hazard mapping dataset with foreign-key, uniqueness, enumeration, rationale, critical-link, and hazard-coverage validation.
- Added optional CSV/XLSX/XLS mapping input, mapping filters and evidence details, coverage and ranking analyses, selected-hazard Sankey visualization, mapping CSV exports, workbook mapping sheet, summary JSON statistics, and HTML report appendices.
- Added per-hazard risk-source selection. Valid residual data are preferred for that hazard only; otherwise inherent risk is explicitly labeled as screening, and mixed datasets report Residual, Inherent, and Unavailable counts.
- Added a configurable `RiskAcceptancePolicy` with controlled Low, Moderate, High, Extreme, and Not assessable dispositions; explicit missing-residual policies; corrective-action and approval flags; and a READY residual-assessment option.
- Added calculated decision-risk, acceptance-status, action, reason, and approval fields without overwriting raw inherent fields or source actions.
- Added a Streamlit Risk Acceptance section, filters, source and action metrics, HTML acceptance appendices, JSON acceptance summaries, CSV calculated fields, and the Excel `Risk_Acceptance_Summary` sheet.
- Made incomplete critical records an explicit hard-block condition and added regression tests proving that each mandatory reason changes the decision outcome.
- Added a separate 60-row provisional critical-control profile with one row for every R001–R060 requirement, controlled criticality/disposition values, explicit 0–5 thresholds, evidence requirements, record-completeness dispositions, row-level rationales, and approval/source status.
- Added profile validation for schema, duplicates, unknown and missing IDs, full coverage, enumerations, thresholds, maximum-score consistency, rationale, approval/source fields, and invalid Non-critical blocking dispositions.
- Replaced the single boolean failure calculation with structured score, evidence, and completion assessments. Deployment-blocking failures, Conditional gaps, Important corrective findings, evidence deficiencies, incomplete records, and manual-review items are returned separately; the legacy wrapper now delegates to the structured engine.
- Integrated profile-specific overrides into deployment decisions. Blocking reasons identify requirement IDs and descriptions; Conditional and manual-review findings cap READY; Important findings remain corrective without independently blocking deployment.
- Added a Critical-Control Governance Streamlit tab, filters, metrics, full assessment, focused findings, three CSV downloads, three Excel sheets, JSON governance summaries, and HTML report appendices.
- Replaced parallel message lists with the common `ValidationFinding` model while retaining backward-compatible `errors`, `warnings`, `ok`, `data`, and `invalid_rows` views.
- Added granular hazard and requirement checks for raw numeric types, missing/decimal/non-finite/out-of-range values, uploaded-versus-calculated risk mismatches, residual pairs, evidence states, Boolean parsing, configurable ORL scale strictness, and runtime-referenced dates.
- Added row-level `validation_status`, error/warning/information counts, `analysis_eligible`, and `exclusion_reason`, plus module-specific inherent, residual, BRI, and critical-control eligibility. Invalid rows remain visible and downloadable while eligible calculations exclude them.
- Unified mapping and critical-profile diagnostics under structured finding codes, including coverage and per-link information findings, full profile coverage, threshold consistency, and governance configuration checks.
- Added cross-dataset validation for exact foreign keys, case-only/whitespace differences, mapping/profile coverage, repeated descriptions/wording, and identical core records.
- Added safe file validation for approved CSV/XLSX/XLS inputs: size limits, empty/unsupported files, encoding and delimiter handling, row-width checks, worksheet selection, corrupted/password-protected workbooks, displaced headers, and formulas without cached values. MOBRA does not execute formulas or macros and does not accept XLSM.
- Added the Streamlit Data Validation Center with metrics, filters, dataset summaries, record inspection, and dedicated findings/summary/invalid-record downloads.
- Added validation blocks to JSON, six required validation sheets to Excel, validation fields to CSV, and a Data Validation section plus full findings appendix to HTML.
- Reorganized automated tests by risk, readiness, decisions, acceptance, mapping, governance, validation, I/O, reporting, exports, regression, and integration subsystem, backed by reusable fixtures.
- Added bounded Hypothesis tests for risk, heat-map, BRI, mapping, and mandatory decision properties; mutation-safety, deterministic-output, export-contract, and repository safety tests; and an exact demonstration-data regression contract.
- Removed superseded private validator implementations that were unreachable after structured validation was introduced. Public behavior, schemas, calculations, and scientific rules were unchanged.
- Added Ruff and Black configuration, branch-aware pytest-cov enforcement at 82%, a cross-platform verifier, a Windows PowerShell wrapper, and GitHub Actions for Ubuntu/Python 3.11–3.12 plus Windows/Python 3.12.

## Automated quality architecture

Focused unit modules cover mathematical and validation behavior; `test_regression_demo_data.py` protects all fixed demonstration aggregates; `test_integration_pipeline.py` traverses ingestion through JSON, Excel, and HTML output; and property tests exercise bounded invariants rather than repeated examples. Separate mutation, determinism, export-contract, and security modules protect input ownership, stable ordering and headings, filenames/sheets, local secret hygiene, sample-data boundaries, macro rejection, and temporary export containment.

The demonstration regression contract fixes 24 hazards, 60 BRI-eligible requirements, 95 mapping links, 60 profile rows, BRI 86.7%, all heat-map/risk-acceptance/governance counts, **DO NOT DEPLOY**, and blocking IDs R003, R024, R057, and R058. Assertions target stable fields and identifiers rather than full timestamped paragraphs or report bytes.

Coverage is measured across `mobra` and `app` with branch coverage enabled. The enforced threshold is 82%; the completed local run achieved 83.0%. Remaining gaps are concentrated in defensive Streamlit-only branches and uncommon malformed, password-protected, legacy-XLS, encoding-fallback, and worksheet-selection paths. The threshold deliberately avoids superficial tests and should increase when those paths receive meaningful fixtures.

CI runs lint and formatting checks on Ubuntu, the full coverage suite and report generation on Python 3.11 and 3.12, and the non-slow suite on Windows/Python 3.12. Coverage XML and generated reports are uploaded per Python version. The generated report is checked for existence and stable content, but CI does not require a clean diff because timestamps and Plotly identifiers may vary.

Local verification is available as `./verify.ps1` on Windows or `python scripts/verify_project.py` cross-platform. Both fail on dependency, Ruff, Black, coverage, report-output, or Git whitespace errors.

## Verification record

Commands run from the project folder:

```powershell
python -m venv .venv
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m black --check .
python -m pytest --cov=mobra --cov=app --cov-report=term-missing --cov-report=xml
python generate_demo_report.py
./verify.ps1
streamlit run app.py --server.headless=true --server.port=8511
```

The clean environment installed successfully. The final suite includes unit, property, regression, integration, mutation-safety, determinism, export, security, report, and platform-compatible tests. Passing the suite establishes software-rule consistency only; it is not scientific, clinical, operational, regulatory, or field validation.

## Remaining limitations and assumptions

- `.xls` reading depends on the `xlrd` package and an actual legacy XLS file; the test fixture uses XLSX because it is reproducible without binary test assets.
- The separate demonstration profile provides every explicit governance threshold. Only the backward-compatible wrapper for datasets without a profile derives the former threshold behavior from `critical_threshold` or `maximum_score`.
- When residual fields are absent, the default policy uses inherent risk as an explicitly labeled screening substitute. `require_residual_assessment` and `not_assessable` are supported alternatives, while `require_residual_for_ready_decision=True` prevents a fully READY result when residual assessments are missing.
- Unified files need a `record_type` column or both field sets on separate rows. Arbitrary external schemas still require manual mapping.
- Demonstration data are synthetic/representative and must not be treated as real incident or clinical records.
- Requirement-to-hazard relationships are representative demonstration mappings for software verification and methodology illustration. They have not undergone expert content-validity assessment; future expert review may add, remove, or modify links.
- Risk-acceptance dispositions are provisional software rules. They require institutional approval and expert validation, are not regulatory or field-validated criteria, and do not replace acceptance by accountable institutional personnel.
- Critical-control classifications and thresholds are likewise provisional. The software distinction among Deployment-blocking, Conditional, Important, and Non-critical controls is transparent and testable but still requires expert content-validity review and institutional authorization before operational use.
- Validation reference dates are captured at runtime. Overdue and implausible-date findings must therefore be interpreted against the exported `validation_reference_date`.
- A record that passes implemented schema and consistency checks is only software-valid. It is not thereby scientifically, clinically, regulatorily, operationally, or field validated.
