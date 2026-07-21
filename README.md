# MOBRA Python Dashboard

MOBRA (Mobile Operational Biosecurity Readiness Assessment) is a Streamlit decision-support prototype for external-dataset-based computational verification. It calculates laboratory hazard risk, the Biosecurity Readiness Index (BRI), domain BRI, critical-control status, and a transparent deployment recommendation.

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

An extreme residual risk, a failed or incomplete critical control, an invalid critical record, a validation error, or an uncomputable BRI produces **DO NOT DEPLOY** regardless of how high the BRI is. With no override, BRI <70% is **DEPLOYMENT NOT RECOMMENDED**, 70–84.9% is **CONDITIONAL DEPLOYMENT**, and BRI ≥85% is ready only when no high residual risk remains.

## Project structure

```text
mobra_app_project/
├── app.py                         # Streamlit UI
├── mobra/
│   ├── io.py                       # CSV/XLSX/XLS readers and unified-file split
│   ├── validation.py               # aliases, schema validation, dates, quality flags
│   ├── risk.py                     # scoring, categories, heat-map counts
│   ├── readiness.py                # BRI, domain BRI, critical controls
│   ├── decisions.py                # deployment policy and overrides
│   ├── charts.py                   # Plotly figures
│   └── reporting.py                # standalone UTF-8 HTML report
├── sample_data/                    # 24 hazards, 60 ORL requirements, templates
├── tests/test_logic.py             # unit, boundary, I/O, report, and override tests
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
python -m pip install -r requirements.txt
python -m pytest -q
python generate_demo_report.py
streamlit run app.py
```

If `py` is not available, use `python -m venv .venv`. The app opens at <http://localhost:8501>. Stop Streamlit with `Ctrl+C`.

## Input files

The UI supports:

- Two separate files: a hazard register plus an ORL/requirements file.
- One unified CSV/XLSX/XLS file with a `record_type` column containing hazard/risk and requirement/ORL/control values, or with both field sets present on separate rows.
- CSV encoded as UTF-8, UTF-8 with BOM, CP1256, or Latin-1.
- XLSX and legacy XLS, with explicit sheet selection.

Hazard required fields are equivalent to `hazard`, `likelihood`, and `consequence`. Requirement required fields are equivalent to `requirement`, `observed_score`, and `maximum_score`. Automatic aliases cover the full MOBRA field list; the sidebar also provides manual overrides for required columns. Missing optional fields are reported rather than causing a crash.

Invalid rows remain visible in the validation preview but are excluded from calculations. Duplicate IDs, out-of-range risk scales, impossible observed/max scores, malformed dates, missing evidence, and blank critical-control flags are reported explicitly.

## Outputs

The **Data & exports** tab provides:

- Calculated hazards and requirements as UTF-8 CSV.
- A summary JSON file.
- An analyzed XLSX workbook.
- A self-contained HTML report that opens directly in a browser.
- Hazard and ORL template CSV files.

The heat map always rebuilds from the currently selected risk-category filter. A programmatic assertion verifies that cell counts equal the number of valid filtered hazards.

## Tests and report generation

```powershell
python -m pytest -q
python generate_demo_report.py
```

The test suite covers every category boundary, invalid scales, missing columns, duplicate IDs, observed scores above maximum, zero maximum scores, weighted BRI/domain BRI, residual-risk and critical-control overrides, filtered heat-map totals, CSV/XLSX readers, and HTML report generation.

## GitHub and Streamlit Community Cloud

Create a repository containing this folder, commit the source and sample data, and push it to GitHub. In Streamlit Community Cloud select the repository, branch, and `app.py` as the main file. Keep `requirements.txt` at the project root. Do not commit `.venv`, secrets, or real laboratory records.

## Scientific and data limitations

The included 24-hazard and 60-requirement files are representative demonstration data. External incident datasets may not contain 1–5 Likelihood/Consequence scores; any future transformation must be explicit, reproducible, documented, and kept separate from raw columns. A high BRI is not evidence that a mission is safe when a critical-control or extreme-risk override is present.
