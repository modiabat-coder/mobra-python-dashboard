# MOBRA deployment guide

## Release

MOBRA version 1.0.0 is a self-contained Streamlit application. Application
code, local branding assets, synthetic demonstration data, tests, technical
documentation, and the standalone demonstration report are included in the
release package.

MOBRA does not require files outside the release directory. Runtime paths are
resolved relative to the project root by `mobra.config.PROJECT_ROOT`.

## Supported runtime

- Python 3.12 is the verified runtime.
- A currently supported Python 3.11 or 3.12 environment is recommended.
- Windows, Linux, and macOS are supported by the Python dependencies.
- Network access is not required for the packaged synthetic demonstration
  workflow or the standalone HTML report.

## Installation

From the extracted release directory:

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Linux or macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run

```powershell
python -m streamlit run app.py
```

The default local address is `http://localhost:8501`.

For a headless server:

```powershell
python -m streamlit run app.py --server.headless true --server.address 0.0.0.0
```

Place TLS termination, authentication, and access controls in the hosting
platform or reverse proxy appropriate to the deployment environment.

## Test

```powershell
python -m pytest -q -p no:cacheprovider
python generate_demo_report.py
```

Expected automated result for this release: 52 tests passed.

The regenerated demonstration report is written to
`MOBRA_Demo_Report.html`.

## Data and persistence

- The packaged CSV files are synthetic demonstration records and templates.
- Uploaded assessment data are held in the active Streamlit session and are not
  written back to source files by the application.
- No database, remote API, external incident feed, or external index service is
  configured.
- JSON uploads are limited to 50 MB by the application.
- Legacy XLS reading uses `xlrd`; exported workbooks use XLSX.

## Configuration and secrets

- Streamlit presentation settings are stored in `.streamlit/config.toml`.
- No secrets are required for the packaged application.
- Do not add `.env`, `secrets.toml`, credentials, or private operational data to
  a distributable release.

## Scientific release checks

The following invariants must remain true:

- Representative hazards: 24.
- Demonstration BRI: 86.7%.
- Failed critical controls: 11.
- Demonstration decision: DO NOT DEPLOY.
- Risk score: Likelihood × Consequence.
- Low: 1–4.
- Moderate: 5–9.
- High: 10–16.
- Extreme: 17–25.

A high BRI never overrides a failed critical control.

## Production considerations

- Use organization-approved identity, authentication, TLS, backup, monitoring,
  audit logging, and vulnerability-management controls.
- Treat MOBRA output as structured decision support, not clinical, regulatory,
  field, or scientific validation.
- Validate uploaded schemas and review all warnings before using an assessment
  result.
- Keep synthetic data clearly separated from operational evidence.

