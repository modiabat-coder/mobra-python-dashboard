# MOBRA 1.0.0 final QA summary

Release date: 2026-07-24

## Scientific regression result

- Representative hazards: 24.
- Demonstration BRI: 86.7%.
- Failed critical controls: 11.
- Final demonstration decision: DO NOT DEPLOY.
- Risk score: Likelihood × Consequence.
- Low: 1–4.
- Moderate: 5–9.
- High: 10–16.
- Extreme: 17–25.
- Critical-control override: preserved and non-bypassable.
- Synthetic-data disclaimer: present in the application and report.

## Automated verification

- Python compilation: passed.
- Automated tests: 56 passed.
- All twelve application pages: passed Streamlit test harness.
- CSV, XLSX, legacy XLS, and JSON import tests: passed.
- BRI, risk boundaries, heatmap totals, axes, and decision overrides: passed.
- HTML and Excel export structure: passed.
- Exact decision-label and grammar checks: passed.
- Standalone report generation: passed.
- Git whitespace validation: passed.
- Requirement–hazard mapping: 95 validated links and 24/24 hazard coverage.
- Restored field workbooks, printable PDFs, and resource catalogue: passed.
- Supplementary governance and risk-acceptance logic: verified not to alter
  the canonical 11-control failure count or Deployment Decision.

## Live interface verification

- Application viewports checked: 1440×900, 1280×720, 1024×768, 820 px,
  and 768 px.
- KPI columns at those widths: 4, 4, 2, 2, and 1.
- Application horizontal overflow: none.
- Standalone report viewports checked: desktop, 820 px, and 560 px.
- Report KPI columns: 4, 2, and 1.
- Report document overflow: none.
- Final application browser-console errors: 0.
- Final report browser-console errors: 0.
- Restored navigation and analysis checks: all twelve sidebar items visible;
  Risk Matrix & Heatmap verified with 24 hazards; requirement mapping and
  governance sections verified in the local browser.
- Current responsive recheck: desktop, 768 px, and 560 px; no horizontal page
  overflow and the narrow sidebar remained collapsible.

## Scope boundary

MOBRA is scientific and operational decision support. The included synthetic
demonstration data are representative test records and are not operational
evidence, clinical approval, regulatory authorization, field validation, or
final scientific validation.
