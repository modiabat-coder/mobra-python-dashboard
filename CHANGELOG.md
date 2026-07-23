# Changelog

All notable changes to MOBRA are documented in this file.

## [1.0.0] - 2026-07-23

### Added

- Twelve-page Streamlit assessment workflow.
- Institutional MOBRA identity, local SVG/PNG assets, favicon, and responsive
  application shell.
- CSV, XLSX, legacy XLS, nested JSON, and unified-file import workflows.
- Column-mapping confidence, validation issue register, and corrective-action
  tracking.
- Responsive 4/2/1 KPI grids and compact page headers.
- Branded standalone HTML report and eight-worksheet Excel export.
- Release deployment guide, technical review, QA summary, and automated
  scientific regression coverage.
- Preserved requirement–hazard mapping, structured cross-dataset validation,
  Critical Control governance, provisional risk acceptance, field forms,
  import templates, and normative resource catalogues from the prior
  development line.
- Added a function-preservation matrix documenting where every restored
  capability appears in the twelve-view application structure.

### Changed

- Standardized deployment outcomes to DO NOT DEPLOY, CONDITIONAL DEPLOYMENT,
  and READY TO DEPLOY.
- Standardized user-facing singular/plural grammar.
- Improved sidebar branding, concise navigation, long-filename wrapping,
  keyboard focus visibility, table readability, and report print behavior.
- Replaced the collapsed page selector with a fully visible twelve-item
  navigation list and identified the Risk Matrix & Heatmap explicitly.
- Replaced deprecated Streamlit `use_container_width` arguments with
  `width="stretch"` for Streamlit 1.60 compatibility.

### Verified

- 24 representative hazards.
- 86.7% demonstration BRI.
- 11 failed critical controls.
- DO NOT DEPLOY demonstration decision.
- Risk score remains Likelihood × Consequence.
- Risk thresholds remain Low 1–4, Moderate 5–9, High 10–16, and Extreme 17–25.
- Failed critical controls remain non-bypassable.
- 56 automated tests pass.
