# MOBRA Equation Audit

## Source and verification method

Primary source reviewed:

- `MOBRA_Manuscript.pdf`, author-supplied revision dated 27 July 2026.
- 27 PDF pages.
- SHA-256: `336453adcaf094e9234b7664e828713c12a28823784cbd2f4a96f50bc4108229`.
- Title: *MOBRA: A Requirements-Based Operational Biosecurity Readiness Framework for Mobile Biological Laboratories*.

Every page of the primary source was rendered to an image and visually reviewed.
Text extraction was used only as a searchable aid. The existing repository
manuscript (22 pages) and the BRI, risk-assessment, and Critical Control poster
PDFs were also inspected. The posters contain educational summaries but no
additional mathematical equations.

## Equation-to-code traceability

| Equation or rule | PDF source | Existing code location | New or verified code location | Verification status | Notes | Type |
|---|---|---|---|---|---|---|
| Domain Readiness: `DR_d = ΣS_id / ΣS_id^max × 100` | pp. 4-5, §2.4, Eqs. (1-2) | `mobra/readiness.py::domain_readiness` | `mobra/calculations.py::calculate_domain_readiness_from_totals`; `ui/equations.py` | Verified consistent | The fixed denominator of 30 in Eq. (2) applies only to the original six-item, five-point domain structure. | Original |
| Evidence Completeness: `EC = N_adequate / N_assessed × 100` | p. 5, §2.4, Eq. (3) | Missing-evidence flags existed, but no standalone percentage function | `mobra/calculations.py::calculate_evidence_completeness`; `ui/equations.py` | Implemented from source | Adequacy criteria still require expert validation as stated in the manuscript. | Original |
| Risk Score: `R_i = L_i × C_i` | p. 5, §2.5, Eq. (4) | `mobra/risk.py::calculate_risk_score` | Verified and reused by calculators | Verified consistent | Likelihood and consequence must be integers from 1 to 5. | Original |
| Risk classification bands | pp. 5-6, §2.5, Eq. (5) | `mobra/config.py::RISK_THRESHOLDS`; `mobra/risk.py::classify_risk` | Verified and reused by calculators | Verified consistent | Low 1-4; Moderate 5-9; High 10-16; Extreme 17-25. These are prototype design rules, not universal acceptance thresholds. | Original |
| Overall BRI: `BRI = ΣS_i / ΣS_i^max × 100` | pp. 6-7, §2.6, Eqs. (6-7) | `mobra/readiness.py::calculate_bri` | `mobra/calculations.py::calculate_bri_from_totals` and `calculate_bri_from_counts`; `ui/equations.py` | Verified consistent | User-facing terminology was corrected from "weighted BRI" to the manuscript's current unweighted score-ratio BRI. | Original |
| Balanced-domain equivalence: `BRI = (1/10)ΣDR_d` | p. 7, §2.6, Eq. (8) | Not used in operational calculation | `mobra/calculations.py::calculate_mean_domain_readiness`; calculator labelled with its limitation | Verified but not operational | Valid only for the balanced, equally weighted ten-domain prototype. | Original |
| Heat-map cell count: `H_lc = Σ1(L_i=l, C_i=c)` | p. 12, §3.3, Eq. (9) | `mobra/risk.py::heatmap_counts` | Reused in `ui/equations.py` | Verified consistent | The interactive calculator uses the active valid hazard population. | Original |
| Heat-map conservation: `Σ_lΣ_c H_lc = N` | p. 12, §3.3, Eq. (10) | `mobra/risk.py::heatmap_total` and `assert_heatmap_total` | Reused in `ui/equations.py` | Verified consistent | The manuscript shows 24 for its synthetic dataset; the general application uses the current valid count `N`. | Original |
| Critical-Control override indicator `O` | p. 15, §3.6, Eq. (11) | `mobra/decisions.py::deployment_decision`; `mobra/readiness.py::failed_critical_controls` | Reused by `evaluate_deployment_decision` and the simulator | Verified consistent | Extreme residual risk or mission-critical control failure cannot be bypassed by a high BRI. | Original |
| Decision rule with institutional function `g(...)` | p. 16, §3.6, Eq. (12) | `mobra/decisions.py::deployment_decision` | `mobra/decisions.py::evaluate_deployment_decision`; `ui/equations.py` | Consistent with documented software policy | The manuscript proposes no universal thresholds. The software's 70% and 85% bands are explicitly identified as current application policy, not manuscript equations. | Original rule plus application policy |
| Proposed weighted BRI | p. 20, §4.7, Eq. (13) | Not part of current operational BRI | `mobra/calculations.py::calculate_weighted_bri`; educational calculator only | Implemented with warning | Requires validated weights, expert review, and sensitivity analysis before operational use. | Original proposed metric |
| Estimated control effectiveness: `(R_inherent - R_residual) / R_inherent × 100` | p. 20, §4.7, Eq. (14) | Not previously exposed as a standalone function | `mobra/calculations.py::calculate_control_effectiveness`; `ui/equations.py` | Implemented with warning | Manuscript limits use to clearly documented and validated inherent/residual criteria. | Original proposed metric |
| Absolute BRI change: `ΔBRI = BRI_post - BRI_pre` | p. 20, §4.7, Eq. (15) | Not previously implemented | `mobra/calculations.py::calculate_bri_change`; `ui/equations.py` | Implemented with warning | Proposed longitudinal metric requiring validation. | Original proposed metric |
| Relative BRI improvement | p. 21, §4.7, Eq. (16) | Not previously implemented | `mobra/calculations.py::calculate_relative_bri_improvement`; `ui/equations.py` | Implemented with zero-baseline validation | Proposed longitudinal metric requiring validation. | Original proposed metric |
| CAPA closure percentage | p. 21, §4.7, Eq. (17) | CAPA records existed without this standalone percentage | `mobra/calculations.py::calculate_capa_closure`; `ui/equations.py` | Implemented with warning | Proposed performance indicator requiring validation. | Original proposed metric |
| Illustrative diagnostic accuracy | p. 24, Appendix A §A.4, unnumbered equation | Not part of the MOBRA readiness engine | `mobra/calculations.py::calculate_accuracy`; `ui/equations.py` | Implemented as an isolated illustrative calculator | The appendix explicitly states that this does not validate MOBRA or make MOBRA a diagnostic classifier. | Original appendix calculation |
| Residual Risk: `R_i^res = L_i^res × C_i^res` | Eq. (4) applied to residual inputs; residual risk discussed on pp. 6-7 and 15-16 | Residual score multiplication in `mobra/validation.py` | `mobra/risk.py::calculate_residual_risk`; `ui/equations.py` | Verified against application logic | The manuscript does not number a separate residual-product equation. The page labels it as a derived application of Eq. (4). | Derived calculation |
| Not-applicable denominator adjustment | The manuscript defines denominators over assessed requirements in Eqs. (1), (3), and (6); no separate N/A equation | Explicit applicability handling was absent | `mobra/validation.py`; `mobra/readiness.py`; BRI/domain calculators | Added and clearly labelled | Explicitly non-applicable requirements are excluded from numerator and denominator and do not create missing-evidence failures. | Derived calculation |
| Absolute risk-score reduction: `R_initial - R_residual` | Not stated as a numbered manuscript equation | Not previously exposed | `mobra/calculations.py::calculate_absolute_risk_reduction`; `ui/equations.py` | Added and clearly labelled | Negative values correctly indicate that residual risk increased. | Derived calculation |

## Differences and corrections

1. The manuscript describes the current prototype BRI as unweighted. Some
   interface text called the same observed-to-maximum score ratio "weighted."
   The calculation was already correct; the terminology was corrected.
2. The manuscript does not provide universal deployment thresholds. MOBRA's
   default 70% and 85% readiness bands remain software-policy settings and are
   now explicitly distinguished from original manuscript equations.
3. Explicit not-applicable handling was not represented by an import column.
   An optional `applicable` field and common aliases now allow these rows to be
   excluded consistently without being treated as invalid assessed evidence.
4. The manuscript provides Evidence Completeness, proposed longitudinal
   indicators, and an illustrative appendix accuracy equation that did not have
   dedicated calculation functions. Reusable validated functions were added.
5. A separate residual-risk product equation is not numbered in the manuscript.
   The application reuses the same likelihood-times-consequence rule and labels
   the residual formula as a derived application rather than an original
   manuscript equation.

## Formulas not supplied by the source

- Section 2.9, page 9, plans inter-assessor reliability assessment but supplies
  no agreement coefficient, threshold, or equation. No kappa, ICC, or other
  agreement formula was invented.
- The manuscript does not specify a validated universal function `g` for a final
  deployment decision. Application policy remains centralized in
  `mobra/decisions.py` and is labelled as software policy.
- No sensitivity, specificity, content-validity ratio, or scale-validity
  equation is supplied. These were not added.

## Calculator use boundary

The calculators are transparent educational and operational-assessment aids.
They do not establish institutional risk acceptance, validate the MOBRA
framework, or replace qualified biosafety, biosecurity, quality, governance, or
mission decision-makers.
