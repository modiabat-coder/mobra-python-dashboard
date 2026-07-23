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
- Automated tests: 52 passed.
- All twelve application pages: passed Streamlit test harness.
- CSV, XLSX, legacy XLS, and JSON import tests: passed.
- BRI, risk boundaries, heatmap totals, axes, and decision overrides: passed.
- HTML and Excel export structure: passed.
- Exact decision-label and grammar checks: passed.
- Standalone report generation: passed.
- Git whitespace validation: passed.

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

## Scope boundary

MOBRA is scientific and operational decision support. The included synthetic
demonstration data are representative test records and are not operational
evidence, clinical approval, regulatory authorization, field validation, or
final scientific validation.
