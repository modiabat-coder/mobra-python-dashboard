# MOBRA technical review

## Problems found in the supplied package

- The application was a single `app.py`; validation, scoring, readiness, decisions, charts, I/O, and reporting were tightly coupled.
- The original validator calculated a risk score even when Likelihood/Consequence were missing or non-integer, did not validate duplicate IDs, and did not parse dates or residual-risk fields.
- Critical-control flags and evidence completeness were only partially checked. The original report generator did not apply the BRI threshold or document critical-control overrides.
- The UI heat map was created before the risk filter and asserted against the unfiltered row count, so filtered cell totals could be misleading.
- The original report omitted input metadata, validation/data-quality results, critical-control failures, methodology, and limitations.
- The original standalone generator could label the demonstration data READY solely because no extreme or failed critical control existed, even though high risks remained; the corrected generator applies the documented conditional-deployment rule for remaining high risk.
- Excel sheet selection, unified-file splitting, templates, workbook export, and editable preview were absent.
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

## Verification record

Commands run from the project folder:

```powershell
python -m venv .venv
python -m pip install -r requirements.txt
python -m pytest -q
python generate_demo_report.py
streamlit run app.py --server.headless=true --server.port=8511
```

The clean environment installed successfully. The final test suite covers risk boundaries, invalid inputs, BRI/domain BRI, critical-control and residual-risk overrides, filtered heat-map totals, CSV/XLSX reading, and HTML generation. Streamlit was smoke-tested by requesting `http://127.0.0.1:8511` and receiving HTTP 200.

## Remaining limitations and assumptions

- `.xls` reading depends on the `xlrd` package and an actual legacy XLS file; the test fixture uses XLSX because it is reproducible without binary test assets.
- A critical control with no explicit accepted threshold uses its `maximum_score` as the threshold, matching the supplied prototype behavior. A `critical_threshold` column can override it.
- When residual fields are absent, the current calculated risk is used as the decision risk and is labeled as such in the report; it is not silently called a residual measurement.
- Unified files need a `record_type` column or both field sets on separate rows. Arbitrary external schemas still require manual mapping.
- Demonstration data are synthetic/representative and must not be treated as real incident or clinical records.
