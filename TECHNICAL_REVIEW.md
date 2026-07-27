# MOBRA implementation and technical review

## Scope

This development round upgraded the existing MOBRA project in place. It preserved the scientific calculation modules and source data while redesigning the Streamlit interface, branding, import workflow, charts, reports, exports, documentation, and test coverage.

The final reconciliation also restored the advanced functions retained on the
historical development branch: requirement–hazard mapping, structured
cross-dataset findings, Critical Control governance metadata, provisional risk
acceptance, field assessment workbooks and printable forms, import templates,
and normative resource catalogues. These functions are integrated into the
existing twelve-view interface and remain supplementary to the canonical
scientific decision path.

The controlled enhancement round dated 2026-07-24 preserved those twelve views
and added only two new navigation targets: a synthetic Mission Map and a
Research & Manuscript view. It also added optional secrets-backed
authentication, contextual Home gauges, and a more balanced brand hero. None
of these additions writes to or replaces the canonical risk, readiness, or
deployment-decision modules.

## Files reviewed

- Application entry point and Streamlit configuration.
- All `mobra` calculation, validation, I/O, chart, decision, readiness, and reporting modules.
- Both synthetic sample datasets and both CSV templates.
- Existing tests, report generator, README, generated report, and Git state.

## Principal findings

- Scientific logic was already separated into modules, but the interface remained a single long page with default Streamlit styling.
- Heatmap data were counted correctly, but axis semantics were opposite the requested convention.
- Decision labels included legacy outcomes outside the approved three-label vocabulary.
- JSON was unsupported.
- Imports, validation issues, requirements, hazards, actions, reporting, and methodology did not have dedicated views.
- Styling was inline and repeated; no reusable component or institutional identity system existed.
- The HTML report lacked the new identity and requested print-oriented organization.

## Implemented changes

### Identity and visual system

- Added shield/readiness-grid SVG and PNG wordmarks, dark-background wordmark, compact icon, and favicon.
- Added centralized typography, color, spacing, cards, controls, table, tab, alert, empty-state, sidebar, and responsive CSS.
- Enlarged and rebalanced the sidebar wordmark, simplified visible navigation labels, and added wrapped dataset metadata.
- Replaced fixed KPI columns with a reusable CSS grid that resolves to 4, 2, and 1 columns at controlled breakpoints.
- Added consistent focus-visible and disabled-control states.
- Added a matching Streamlit theme.
- Preserved the approved risk colors across interface charts and reports.

### Application architecture

- Reduced `app.py` to configuration, context construction, sidebar rendering, and page dispatch.
- Added reusable UI components, layout, state, and page renderers.
- Preserved the twelve clearly ordered assessment views and added two
  supplementary views for mission workflow and research transparency.
- Preserved active dataset and page state across reruns.
- Added PBKDF2-based optional sign-in, session timeout, and logout with no
  repository credential or plaintext password.

### Data import and validation

- Added CSV, XLSX, XLS, and JSON support.
- Added Excel worksheet scoring, automatic selection, and manual override.
- Added nested JSON record-collection discovery, dotted-name flattening, multi-collection selection, and clear structure errors.
- Added mapping-confidence tables and required-field overrides.
- Added grouped, searchable, downloadable validation issues.

### Risk, readiness, and decisions

- Preserved `Risk Score = Likelihood × Consequence`.
- Preserved Low 1–4, Moderate 5–9, High 10–16, Extreme 17–25.
- Corrected every matrix to X = Consequence and Y = Likelihood.
- Added matrix tooltips with scores, category, count, and assigned hazard identifiers/names.
- Verified matrix cell totals before rendering.
- Preserved the weighted BRI formula and safe zero-denominator behavior.
- Standardized final labels to DO NOT DEPLOY, CONDITIONAL DEPLOYMENT, and READY / DEPLOY.
- Kept Critical Controls, Extreme residual risk, material validation errors, critical missing evidence, and core-readiness failures non-bypassable.

### Reporting and exports

- Added branded, self-contained, UTF-8, print-ready HTML reporting.
- Added responsive 4/2/1 report KPI layouts, solid high-contrast report branding, long-content wrapping, A4 page settings, and print page-break controls.
- Added a structured eight-worksheet Excel workbook.
- Added CSV and JSON helpers.
- Added report preview and downloads in the interface.
- Regenerated `MOBRA_Demo_Report.html`.

### Documentation

- Rewrote README with installation, workflow, pages, formats, formulas, decision rules, data limitations, exports, structure, identity, tests, and current screenshots.

## Verification record

Executed from the project root:

```powershell
.venv\Scripts\python.exe -m compileall -q app.py mobra ui generate_demo_report.py
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.venv\Scripts\python.exe generate_demo_report.py
.venv\Scripts\python.exe -m streamlit run app.py --server.headless=true --server.port=8513
```

Results:

- Python compilation: passed.
- Import validation: passed.
- Automated tests: 62 passed.
- Every navigation page: passed Streamlit application harness.
- Report generation: passed.
- Local Streamlit startup and HTTP render: passed.
- Live browser checks at 1440 × 900, 1280 × 720, 1024 × 768, 820 px, and 768 px: passed.
- KPI grids resolved to 4, 4, 2, 2, and 1 columns at those widths with no page or card overflow.
- All fourteen application pages were traversed in the live browser with no retired decision label or placeholder grammar.
- Standalone report checks at desktop, 820 px, and 560 px: passed with 4/2/1 KPI layouts and no document overflow.
- Browser console: zero application or report errors after the final render.
- Controlled-enhancement browser recheck: all fourteen navigation targets
  opened without a Streamlit exception; Home, Mission Map, Research &
  Manuscript, and Methodology received focused content checks.
- Controlled-enhancement responsive recheck: 1280×720, 768×900, 560×900, and
  390×844 with zero horizontal overflow and zero browser console warnings or
  errors.
- Heatmap: 24 valid hazards represented by 24 total matrix counts.
- Demonstration decision: 86.7% BRI with 11 failed Critical Controls correctly displayed as DO NOT DEPLOY.

## Remaining limitations

- External incident and index sources are not connected.
- Legacy XLS reading depends on `xlrd`; exported workbooks use XLSX.
- Custom scientific transformation of external incident variables into MOBRA scales is intentionally not implemented.
- Report printing was verified through print CSS and browser rendering; organization-specific PDF templates may still require local printer/profile tuning.
- Synthetic data remain demonstration records and are not scientific, field, clinical, or regulatory validation.
