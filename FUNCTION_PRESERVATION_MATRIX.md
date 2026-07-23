# MOBRA Function-Preservation Matrix

## Purpose

This matrix documents the reconciliation of the visually refined MOBRA 1.0.0
interface with the advanced functions preserved on the historical development
branch. The application remains the existing MOBRA project; it was not replaced
or rebuilt as a different product.

## Preserved scientific contract

The restored functions are supplementary. They do not replace or weaken the
canonical calculation and decision path:

- 24 representative hazards in the synthetic demonstration dataset.
- BRI = 86.7% using weighted observed score divided by weighted maximum score.
- 11 failed Critical Controls.
- Final Deployment Decision = `DO NOT DEPLOY`.
- Risk Score = Likelihood × Consequence.
- Low = 1–4; Moderate = 5–9; High = 10–16; Extreme = 17–25.
- Risk heatmap X-axis = Consequence and Y-axis = Likelihood.
- Critical Control failures remain non-bypassable.

The supplementary governance profile contains its own classification and
approval metadata. Its internal profile findings are not substituted for the
canonical failed-Critical-Control count.

## Interface and navigation

| Requirement | Current implementation |
|---|---|
| Fourteen application views | The original twelve are preserved; Mission Map and Research & Manuscript are additive views. |
| Risk analysis discoverability | Sidebar label explicitly identifies `Risk Matrix & Heatmap`. |
| Current-page visibility | Selected navigation item receives a persistent highlighted state. |
| Responsive visual system | Existing MOBRA dark-teal identity, cards, spacing, and responsive CSS preserved. |
| Streamlit forward compatibility | Deprecated `use_container_width` calls replaced with `width="stretch"`. |

## Functional preservation

| Functional area | Location in the current fourteen-view structure |
|---|---|
| CSV, XLSX, XLS, and JSON import | Data Import |
| Nested JSON collection selection | Data Import |
| Column mapping and activation review | Data Import |
| Requirement–hazard mapping upload | Data Import → Advanced supporting data |
| Critical Control governance-profile upload | Data Import → Advanced supporting data |
| Schema and value validation | Data Validation |
| Structured cross-dataset findings | Data Validation |
| Duplicate, identifier, relationship, and coverage checks | Data Validation |
| Requirement register and detail | Requirements Assessment |
| Requirement–hazard coverage and rankings | Requirements Assessment |
| Critical Control governance detail | Requirements Assessment |
| Hazard register and drill-down | Hazard Register |
| Risk distribution charts | Risk Matrix & Heatmap |
| Initial versus residual comparison | Risk Matrix & Heatmap |
| Hazards by domain and top-risk ranking | Risk Matrix & Heatmap |
| Verified 5 × 5 heatmap | Risk Matrix & Heatmap |
| Provisional risk-acceptance analysis | Risk Matrix & Heatmap |
| BRI and domain readiness | Readiness Dashboard |
| Contextual radial BRI/control/risk indicators | Home |
| Synthetic interactive mission workflow | Mission Map |
| Non-bypassable decision evidence | Deployment Decision |
| Corrective-action register | Corrective Actions |
| HTML, XLSX, JSON, and CSV exports | Reports and Export |
| Mapping, governance, and acceptance exports | Reports and Export |
| Field workbooks, printable PDFs, and import templates | Reports and Export |
| Derived-output backup with checksums | Reports and Export |
| Normative resource catalogue | Reports and Export; About MOBRA |
| Scientific formulas and decision rules | Methodology |
| Contextual help topics | Methodology |
| Educational poster catalogue and ZIP package | About MOBRA |
| Research manuscript metadata and PDF download | Research & Manuscript; About MOBRA |
| Priority normative references and supporting literature | Research & Manuscript |
| Optional secrets-backed sign-in and logout | Application entry gate; sidebar |
| Scope, limitations, provenance, repository, and contact | About MOBRA |

## Verification

The automated suite currently contains 62 passing tests. It verifies the
scientific invariants, risk bands, heatmap axes and totals, import formats,
standalone HTML report, workbook structure, all fourteen Streamlit pages,
mapping and governance compatibility, non-bypassable Extreme-risk policy,
field packages, printable PDFs, authentication, the synthetic mission workflow,
executive gauges, manuscript access, and the normative resource catalogue.
