# Changelog

All notable changes to MOBRA are documented in this file.

## [Unreleased] - 2026-07-27

### Added

- Optional Streamlit-Secrets authentication with PBKDF2 password hashes,
  session timeout, branded sign-in, and explicit logout.
- Three contextual radial executive indicators on Home for BRI, satisfied
  Critical Controls, and High/Extreme risk load.
- Synthetic, interactive Mission Map workflow with tooltips, progress,
  decision-linked gate status, and a visible legend.
- Dedicated Research and References page for the approved manuscript, WHO
  Laboratory Biosafety Manual, WHO biosecurity and mobile-laboratory guidance,
  BMBL sixth edition, ISO 35001, ISO 31000, and supporting literature.
- Streamlit Secrets example and deployment instructions.
- Per-record decision-risk selection with conservative initial-risk fallback
  when residual values are unavailable.
- Spreadsheet formula-injection protection, project-local archive path checks,
  and uniform 50 MB upload enforcement.
- Repository-level pytest discovery configuration and separate development
  dependencies.

### Changed

- Refined the Home hero composition, typography, wordmark placement, and
  contextual metadata.
- Increased and rebalanced the sidebar wordmark while preserving the existing
  visual identity and responsive navigation.
- Extended navigation from twelve preserved views to fourteen by adding only
  Mission Map and Research & Manuscript.
- Derived compliance labels now remain consistent with validated scores while
  preserving any reported source label for traceability.
- High-risk badge text now meets WCAG AA contrast against the approved orange.

### Verified

- All twelve original views remain present.
- Scientific invariants and non-bypassable decision logic remain unchanged.
- 71 automated tests pass, including authentication, all fourteen pages,
  partial residual-risk fallback, fail-closed Critical Control validation,
  upload limits, export safety, gauges, map workflow, manuscript, and priority
  references.

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
  and READY / DEPLOY.
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
