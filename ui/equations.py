"""Interactive manuscript-traceable equations and practical calculators."""

from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd
import streamlit as st

from mobra.calculations import (
    calculate_absolute_risk_reduction,
    calculate_accuracy,
    calculate_bri_change,
    calculate_bri_from_counts,
    calculate_capa_closure,
    calculate_control_effectiveness,
    calculate_domain_readiness_from_totals,
    calculate_evidence_completeness,
    calculate_mean_domain_readiness,
    calculate_relative_bri_improvement,
    calculate_weighted_bri,
    maximum_possible_score,
)
from mobra.config import (
    DECISION_COLORS,
    RISK_COLORS,
    RISK_LEVELS,
    RISK_RANGES,
)
from mobra.decisions import DeploymentPolicy, evaluate_deployment_decision
from mobra.risk import (
    calculate_residual_risk,
    calculate_risk_score,
    classify_risk,
    heatmap_counts,
)
from ui.components import (
    render_decision_banner,
    render_metric_grid,
    render_page_header,
    render_section_header,
)


CORE_EQUATIONS = (
    {
        "anchor": "bri-equation",
        "name": "Biosecurity Readiness Index",
        "equation": (
            r"\mathrm{BRI}(\%)="
            r"\frac{\sum_{i=1}^{N}S_i}{\sum_{i=1}^{N}S_i^{\max}}\times100"
        ),
        "purpose": "Aggregate assessed operational readiness.",
        "variables": r"$S_i$, $S_i^{\max}$, $N$",
        "output": "Percentage (0–100%)",
        "source": "Manuscript pp. 6–7, §2.6, Eqs. (6–7)",
    },
    {
        "anchor": "domain-equation",
        "name": "Domain Readiness",
        "equation": (
            r"\mathrm{DR}_d(\%)="
            r"\frac{\sum_{i=1}^{n_d}S_{id}}"
            r"{\sum_{i=1}^{n_d}S_{id}^{\max}}\times100"
        ),
        "purpose": "Identify readiness within one assessment domain.",
        "variables": r"$S_{id}$, $S_{id}^{\max}$, $n_d$",
        "output": "Percentage (0–100%)",
        "source": "Manuscript pp. 4–5, §2.4, Eqs. (1–2)",
    },
    {
        "anchor": "risk-equation",
        "name": "Risk Score",
        "equation": r"R_i=L_i\times C_i",
        "purpose": "Combine likelihood and consequence in the 5 × 5 matrix.",
        "variables": r"$L_i$, $C_i$, $R_i$",
        "output": "Integer score (1–25)",
        "source": "Manuscript pp. 5–6, §2.5, Eqs. (4–5)",
    },
    {
        "anchor": "residual-equation",
        "name": "Residual Risk",
        "equation": r"R_i^{\mathrm{res}}=L_i^{\mathrm{res}}\times C_i^{\mathrm{res}}",
        "purpose": "Reapply the approved risk product after controls.",
        "variables": r"$L_i^{res}$, $C_i^{res}$, $R_i^{res}$",
        "output": "Integer score (1–25)",
        "source": "Derived application of manuscript Eq. (4); implemented in MOBRA",
    },
    {
        "anchor": "override-equation",
        "name": "Critical-Control Override",
        "equation": (
            r"O=\begin{cases}1,&\text{Extreme residual risk or critical-control "
            r"failure}\\0,&\text{otherwise}\end{cases}"
        ),
        "purpose": "Prevent aggregate readiness from bypassing safety blockers.",
        "variables": r"$O$ and validated decision inputs",
        "output": "Override state and decision",
        "source": "Manuscript pp. 15–16, §3.6, Eqs. (11–12)",
    },
)


def _anchor(name: str) -> None:
    st.markdown(f'<span id="{escape(name)}"></span>', unsafe_allow_html=True)


def _source(
    page: str,
    section: str,
    equation: str,
    *,
    status: str = "Original manuscript equation",
) -> None:
    st.caption(
        f"Source: MOBRA manuscript, {page}, {section}, {equation}. "
        f"Status: {status}."
    )


def _equation_card(equation: dict[str, str]) -> None:
    with st.container(border=True):
        st.markdown(f"#### {equation['name']}")
        st.latex(equation["equation"])
        st.write(equation["purpose"])
        st.caption(
            f"Variables: {equation['variables']} · Output: {equation['output']}"
        )
        st.caption(equation["source"])
        st.markdown(f"[Open detailed explanation](#{equation['anchor']})")


def _readiness_interpretation(value: float) -> str:
    policy = DeploymentPolicy()
    if value < policy.bri_not_recommended:
        return (
            "Below the current software core-readiness band; deployment is not "
            "recommended before overrides are even considered."
        )
    if value < policy.bri_ready:
        return (
            "Within the current software conditional band; documented readiness "
            "improvements are required."
        )
    return (
        "Within the current software ready band, subject to residual risk, Critical "
        "Controls, evidence, validation, and institutional authorization."
    )


def _risk_badge(score: int, category: str, label: str = "Risk") -> None:
    color = RISK_COLORS[category]
    st.markdown(
        (
            f'<div class="mobra-equation-result" style="border-left-color:{color}">'
            f'<span>{escape(label)}</span>'
            f"<strong>{score} · {escape(category)}</strong>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _parse_number_list(raw: str, label: str) -> list[float]:
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    if not parts:
        raise ValueError(f"{label} must contain at least one numeric value.")
    try:
        return [float(part) for part in parts]
    except ValueError as exc:
        raise ValueError(f"{label} must be a comma-separated numeric list.") from exc


def _render_overview() -> None:
    render_section_header(
        "Equation Overview",
        icon="∑",
        help_text=(
            "The first four cards describe quantitative calculations. The override "
            "is safety-critical decision logic rather than an average score."
        ),
    )
    columns = st.columns(2)
    for index, equation in enumerate(CORE_EQUATIONS):
        with columns[index % len(columns)]:
            _equation_card(equation)


def _render_bri_calculator() -> None:
    st.markdown("#### Interactive BRI calculator")
    input_columns = st.columns(3)
    applicable = input_columns[0].number_input(
        "Applicable requirements",
        min_value=0,
        value=60,
        step=1,
        key="eq_bri_applicable",
    )
    maximum_per_item = input_columns[1].number_input(
        "Maximum score per requirement",
        min_value=0.0,
        value=5.0,
        step=1.0,
        key="eq_bri_maximum",
    )
    observed = input_columns[2].number_input(
        "Observed total score",
        min_value=0.0,
        value=246.0,
        step=1.0,
        key="eq_bri_observed",
    )
    try:
        maximum, bri = calculate_bri_from_counts(
            int(applicable),
            maximum_per_item,
            observed,
        )
    except ValueError as exc:
        st.error(str(exc))
        return
    render_metric_grid(
        [
            ("Maximum Possible Score", f"{maximum:g}", "Applicable count × maximum"),
            ("Calculated BRI", f"{bri:.2f}%", "Observed ÷ maximum × 100"),
        ],
        max_columns=2,
    )
    st.progress(bri / 100)
    st.info(_readiness_interpretation(bri))
    st.warning(
        "A BRI percentage never overrides an Extreme residual risk, a failed "
        "Critical Control, missing critical evidence, or institutional governance."
    )


def _render_domain_calculator() -> None:
    st.markdown("#### Interactive domain-readiness calculator")
    input_columns = st.columns(3)
    count = input_columns[0].number_input(
        "Applicable domain requirements",
        min_value=0,
        value=8,
        step=1,
        key="eq_domain_count",
    )
    maximum_per_item = input_columns[1].number_input(
        "Maximum score per domain requirement",
        min_value=0.0,
        value=5.0,
        step=1.0,
        key="eq_domain_maximum",
    )
    observed = input_columns[2].number_input(
        "Observed domain score",
        min_value=0.0,
        value=31.0,
        step=1.0,
        key="eq_domain_observed",
    )
    try:
        maximum = maximum_possible_score(int(count), maximum_per_item)
        readiness = calculate_domain_readiness_from_totals(observed, maximum)
    except ValueError as exc:
        st.error(str(exc))
        return
    render_metric_grid(
        [
            ("Domain Maximum", f"{maximum:g}", "Applicable domain denominator"),
            ("Domain Readiness", f"{readiness:.2f}%", "Observed ÷ maximum × 100"),
        ],
        max_columns=2,
    )
    st.progress(readiness / 100)
    st.info(
        "Domain readiness identifies localized weaknesses that an aggregate BRI may conceal."
    )


def _render_evidence_calculator() -> None:
    st.markdown("#### Evidence Completeness")
    st.latex(
        r"\mathrm{EC}(\%)="
        r"\frac{N_{\mathrm{requirements\ with\ adequate\ evidence}}}"
        r"{N_{\mathrm{assessed\ requirements}}}\times100"
    )
    _source("page 5", "§2.4 Evidence-based scoring", "Eq. (3)")
    columns = st.columns(2)
    adequate = columns[0].number_input(
        "Requirements with adequate evidence",
        min_value=0,
        value=48,
        step=1,
        key="eq_evidence_adequate",
    )
    assessed = columns[1].number_input(
        "Assessed requirements",
        min_value=0,
        value=60,
        step=1,
        key="eq_evidence_assessed",
    )
    try:
        completeness = calculate_evidence_completeness(int(adequate), int(assessed))
    except ValueError as exc:
        st.error(str(exc))
        return
    st.metric("Evidence Completeness", f"{completeness:.2f}%")
    st.caption(
        "Limitation: the manuscript requires adequate objective evidence but states "
        "that final scoring criteria and assessor guidance still require expert validation."
    )


def _render_readiness_tab() -> None:
    _anchor("bri-equation")
    render_section_header("Biosecurity Readiness Index", icon="◔")
    st.latex(CORE_EQUATIONS[0]["equation"])
    _source("pages 6–7", "§2.6 Biosecurity Readiness Index", "Eqs. (6–7)")
    st.markdown(
        """
The numerator is the sum of observed scores for assessed, applicable requirements.
The denominator is the sum of their maximum possible scores. Each score is on the
manuscript's six-level maturity scale from 0 to 5. The output is a percentage, not
an authorization.

**Worked example 1.** For 60 requirements scored out of 5, the maximum is
`60 × 5 = 300`; therefore `BRI = (246 ÷ 300) × 100 = 82.0%`.

**Worked example 2 - not-applicable adjustment.** If 4 of 60 requirements are
not applicable, 56 remain in scope. The adjusted maximum is `56 × 5 = 280`;
therefore `Adjusted BRI = (230 ÷ 280) × 100 ≈ 82.14%`.
"""
    )
    st.info(
        "**Derived calculation:** the explicit not-applicable adjustment is not a "
        "numbered manuscript equation. It follows the manuscript denominator of "
        "assessed requirements. MOBRA excludes an explicitly non-applicable row "
        "from both numerator and denominator."
    )
    with st.expander("Definitions, assumptions, and limitations"):
        st.markdown(
            r"""
- **Symbols:** \(S_i\) is the observed score; \(S_i^{max}\) is the maximum
  possible score; \(N\) is the number of assessed applicable requirements.
- **Valid inputs:** observed 0–maximum; maximum > 0; at least one applicable item.
- **Assumption:** the current prototype is unweighted and uses equal item treatment.
- **Limitation:** a high BRI cannot compensate for an Extreme residual risk,
  Critical Control failure, incomplete critical data, or missing critical evidence.
"""
        )
    _render_bri_calculator()

    _anchor("domain-equation")
    render_section_header("Domain Readiness", icon="▤")
    st.latex(CORE_EQUATIONS[1]["equation"])
    _source("pages 4–5", "§2.4 Evidence-based scoring", "Eqs. (1–2)")
    st.markdown(
        """
The same observed-to-maximum score ratio is calculated within one operational
domain. In the manuscript's original balanced prototype, each domain contained
six requirements with a maximum total of 30.

**Worked example 3.** Eight applicable requirements scored out of 5 have a
maximum of `8 × 5 = 40`; `Domain Readiness = (31 ÷ 40) × 100 = 77.5%`.
"""
    )
    with st.expander("Definitions, assumptions, and limitations"):
        st.markdown(
            r"""
- **Symbols:** \(d\) is the domain; \(n_d\) is its assessed requirement count.
- **Valid inputs:** observed total 0–domain maximum; domain maximum > 0.
- **Interpretation:** lower domains identify focused improvement priorities.
- **Limitation:** averaging domain percentages equals overall BRI only when domain
  structure and weighting are balanced as described in manuscript Eq. (8).
"""
        )
    _render_domain_calculator()
    _render_evidence_calculator()


def _render_risk_calculator() -> None:
    st.markdown("#### Interactive 5 × 5 risk calculator")
    columns = st.columns(2)
    likelihood = columns[0].slider(
        "Likelihood (L)",
        min_value=1,
        max_value=5,
        value=4,
        key="eq_risk_likelihood",
    )
    consequence = columns[1].slider(
        "Consequence (C)",
        min_value=1,
        max_value=5,
        value=5,
        key="eq_risk_consequence",
    )
    score = int(calculate_risk_score(likelihood, consequence))
    category = classify_risk(score)
    _risk_badge(score, category)
    st.write(
        f"Matrix position: row **Likelihood {likelihood}**, column "
        f"**Consequence {consequence}**."
    )
    definitions = {
        "Low": "Monitor through routine controls and review.",
        "Moderate": "Review controls and determine proportionate action.",
        "High": "Prioritize mitigation and document corrective action.",
        "Extreme": "Escalate immediately; deployment cannot proceed while it persists.",
    }
    st.info(definitions[category])


def _render_residual_calculator() -> None:
    st.markdown("#### Initial-versus-residual risk calculator")
    first = st.columns(2)
    initial_likelihood = first[0].slider(
        "Initial likelihood",
        1,
        5,
        4,
        key="eq_initial_likelihood",
    )
    initial_consequence = first[1].slider(
        "Initial consequence",
        1,
        5,
        5,
        key="eq_initial_consequence",
    )
    second = st.columns(2)
    residual_likelihood = second[0].slider(
        "Residual likelihood",
        1,
        5,
        2,
        key="eq_residual_likelihood",
    )
    residual_consequence = second[1].slider(
        "Residual consequence",
        1,
        5,
        4,
        key="eq_residual_consequence",
    )
    initial = int(calculate_risk_score(initial_likelihood, initial_consequence))
    residual = calculate_residual_risk(
        residual_likelihood,
        residual_consequence,
    )
    initial_category = classify_risk(initial)
    residual_category = classify_risk(residual)
    reduction = calculate_absolute_risk_reduction(initial, residual)
    effectiveness = calculate_control_effectiveness(initial, residual)
    result_columns = st.columns(2)
    with result_columns[0]:
        _risk_badge(initial, initial_category, "Initial risk")
    with result_columns[1]:
        _risk_badge(residual, residual_category, "Residual risk")
    render_metric_grid(
        [
            (
                "Absolute Score Reduction",
                f"{reduction:g}",
                "Derived calculation: initial − residual",
            ),
            (
                "Estimated Control Effectiveness",
                f"{effectiveness:.1f}%",
                "Proposed manuscript metric, Eq. (14)",
            ),
        ],
        max_columns=2,
    )
    if residual_category in {"High", "Extreme"}:
        st.error(
            f"Residual risk remains {residual_category}. Escalation and additional "
            "control review are required."
        )
    else:
        st.info(
            "Residual risk is lower, but acceptability still requires documented, "
            "mission-specific institutional review."
        )
    st.caption(
        "Example controls: an appropriate biological safety cabinet or Class III "
        "glovebox, negative pressure, validated SOPs, competency verification, PPE, "
        "decontamination, and emergency-response readiness."
    )


def _render_heatmap_equations(context: Any) -> None:
    st.markdown("#### Heat-map cell counts and conservation check")
    st.latex(
        r"H_{lc}=\sum_{i=1}^{N}\mathbf{1}(L_i=l,\ C_i=c)"
    )
    st.latex(
        r"\sum_{l=1}^{5}\sum_{c=1}^{5}H_{lc}=N"
    )
    _source("page 12", "§3.3 Heat Mapping and Prototype Analytics", "Eqs. (9–10)")
    columns = st.columns(2)
    likelihood = columns[0].slider(
        "Inspect heat-map likelihood",
        1,
        5,
        4,
        key="eq_heatmap_likelihood",
    )
    consequence = columns[1].slider(
        "Inspect heat-map consequence",
        1,
        5,
        5,
        key="eq_heatmap_consequence",
    )
    hazards = getattr(context, "hazards", pd.DataFrame())
    counts = heatmap_counts(hazards)
    cell_count = int(counts.loc[likelihood, consequence])
    total = int(counts.to_numpy().sum())
    render_metric_grid(
        [
            (
                f"Cell H({likelihood},{consequence})",
                str(cell_count),
                "Hazards at the selected matrix position",
            ),
            (
                "All Matrix Cells",
                str(total),
                "Valid hazards counted once across 25 cells",
            ),
        ],
        max_columns=2,
    )
    st.caption(
        "The manuscript's Eq. (10) uses 24 because its synthetic register contains "
        "24 hazards. In the application, the right-hand side is the current valid "
        "hazard count N."
    )


def _render_risk_tab(context: Any) -> None:
    _anchor("risk-equation")
    render_section_header("Initial Risk and Classification", icon="▦")
    st.latex(CORE_EQUATIONS[2]["equation"])
    st.latex(
        r"\operatorname{RiskLevel}(R_i)=\begin{cases}"
        r"\mathrm{Low},&1\le R_i\le4\\"
        r"\mathrm{Moderate},&5\le R_i\le9\\"
        r"\mathrm{High},&10\le R_i\le16\\"
        r"\mathrm{Extreme},&17\le R_i\le25"
        r"\end{cases}"
    )
    _source("pages 5–6", "§2.5 Hazard and Risk Assessment", "Eqs. (4–5)")
    st.markdown(
        """
Likelihood and consequence are integers from 1 to 5. Their product is classified
using the approved prototype bands shown below. The manuscript explicitly notes
that these are framework design rules rather than internationally standardized
risk-acceptance thresholds.

**Worked example 4.** Aerosol generation during high-risk sample processing with
inadequate containment: `Likelihood = 4`, `Consequence = 5`, therefore
`Risk Score = 20`, classified **Extreme**.
"""
    )
    render_metric_grid(
        [
            (
                category,
                RISK_RANGES[category],
                f"{category} risk",
                RISK_COLORS[category],
            )
            for category in RISK_LEVELS
        ]
    )
    _render_risk_calculator()

    _anchor("residual-equation")
    render_section_header("Residual Risk After Controls", icon="↘")
    st.latex(CORE_EQUATIONS[3]["equation"])
    st.caption(
        "Source status: Derived application of manuscript Eq. (4) to residual "
        "likelihood and residual consequence; the current Python implementation "
        "uses the same 5 × 5 multiplication and category thresholds."
    )
    st.markdown(
        """
**Worked example 5.** Initial risk: `4 × 5 = 20`, Extreme. After mitigation:
`2 × 4 = 8`, Moderate. The residual result describes risk remaining after the
documented controls; it does not by itself establish institutional acceptability.
"""
    )
    _render_residual_calculator()
    _render_heatmap_equations(context)


def _render_decision_simulator() -> None:
    st.markdown("#### Deployment-decision simulator")
    columns = st.columns(3)
    bri = columns[0].number_input(
        "BRI percentage",
        min_value=0.0,
        max_value=100.0,
        value=91.0,
        step=0.5,
        key="eq_decision_bri",
    )
    residual_score = columns[1].slider(
        "Residual risk score",
        min_value=1,
        max_value=25,
        value=20,
        key="eq_decision_residual",
    )
    critical_passed = columns[2].checkbox(
        "Mission-critical control passed",
        value=False,
        key="eq_decision_control",
    )
    residual_category = classify_risk(residual_score)
    action_documented = st.checkbox(
        "Documented corrective action exists for a High residual risk",
        value=True,
        key="eq_decision_action",
        disabled=residual_category != "High",
    )
    try:
        decision, reasons = evaluate_deployment_decision(
            bri,
            residual_score,
            bool(critical_passed),
            high_risk_action_documented=bool(action_documented),
        )
    except ValueError as exc:
        st.error(str(exc))
        return
    render_decision_banner(decision, reasons)
    st.caption(
        f"Decision color: {DECISION_COLORS[decision]}. The simulator calls the "
        "application's central deployment_decision() function; it does not duplicate "
        "the business rules in the page."
    )
    policy = DeploymentPolicy()
    st.info(
        f"Current software policy bands: below {policy.bri_not_recommended:.0f}% "
        f"= DO NOT DEPLOY; {policy.bri_not_recommended:.0f}% to below "
        f"{policy.bri_ready:.0f}% = CONDITIONAL; at least "
        f"{policy.bri_ready:.0f}% may be READY only when all overrides pass. "
        "These are configurable software-policy thresholds, not universal "
        "thresholds claimed by the manuscript."
    )


def _render_decision_tab() -> None:
    _anchor("override-equation")
    render_section_header("Critical-Control Override and Decision Logic", icon="◆")
    st.latex(CORE_EQUATIONS[4]["equation"])
    st.latex(
        r"\mathrm{Decision}=\begin{cases}"
        r"\mathrm{DO\ NOT\ DEPLOY},&O=1\\"
        r"g(\mathrm{BRI},\mathrm{DR},R,\mathrm{EC},"
        r"\mathrm{institutional\ criteria}),&O=0"
        r"\end{cases}"
    )
    _source("pages 15–16", "§3.6 Decision-Support Logic", "Eqs. (11–12)")
    st.markdown(
        r"""
The override is intentionally evaluated before aggregate readiness. The
manuscript leaves function \(g\) to institutionally defined and formally
validated criteria; it does not claim universal deployment thresholds.

**Worked example 6.** BRI is 91%, most domains are strong, but a
mission-critical containment control failed and residual risk remains Extreme.
The result is **DO NOT DEPLOY**. A high average cannot compensate for a
deployment-blocking control failure.
"""
    )
    process = [
        ("1", "Calculate BRI", "Summarize applicable requirement scores."),
        ("2", "Review domains", "Identify localized readiness weaknesses."),
        ("3", "Assess risk", "Calculate initial and residual risk."),
        ("4", "Check controls", "Identify failed mission-critical controls."),
        ("5", "Apply override", "Block deployment for non-bypassable findings."),
        ("6", "Recommend", "Return the standardized MOBRA decision."),
    ]
    process_columns = st.columns(3)
    for index, (number, title, description) in enumerate(process):
        with process_columns[index % len(process_columns)]:
            with st.container(border=True):
                st.markdown(f"**{number}. {title}**")
                st.caption(description)
    _render_decision_simulator()


def _render_balanced_and_weighted() -> None:
    st.markdown("#### Balanced-domain equivalence")
    st.latex(r"\mathrm{BRI}=\frac{1}{10}\sum_{d=1}^{10}\mathrm{DR}_d")
    _source("page 7", "§2.6 Biosecurity Readiness Index", "Eq. (8)")
    st.warning(
        "This equivalence applies only to the manuscript's balanced, equally "
        "weighted ten-domain prototype."
    )
    domain_values_raw = st.text_input(
        "Domain readiness values, comma separated",
        value="66.7, 83.3, 83.3, 76.7, 83.3, 86.7, 93.3, 93.3, 76.7, 76.7",
        key="eq_domain_mean_values",
    )
    try:
        domain_values = _parse_number_list(
            domain_values_raw,
            "Domain readiness values",
        )
        domain_mean = calculate_mean_domain_readiness(domain_values)
        st.metric("Arithmetic Mean of Domains", f"{domain_mean:.2f}%")
    except ValueError as exc:
        st.error(str(exc))

    st.markdown("#### Proposed weighted BRI")
    st.latex(
        r"\mathrm{BRI}_w(\%)="
        r"\frac{\sum_{i=1}^{N}w_iS_i}{\sum_{i=1}^{N}w_iS_i^{\max}}\times100"
    )
    _source(
        "page 20",
        "§4.7 Future Development and Research Directions",
        "Eq. (13)",
        status="Proposed future-development equation; not current prototype logic",
    )
    input_columns = st.columns(3)
    observed_raw = input_columns[0].text_input(
        "Observed scores",
        value="4,3,5",
        key="eq_weighted_observed",
    )
    maximum_raw = input_columns[1].text_input(
        "Maximum scores",
        value="5,5,5",
        key="eq_weighted_maximum",
    )
    weights_raw = input_columns[2].text_input(
        "Validated weights",
        value="1,2,1",
        key="eq_weighted_weights",
    )
    try:
        weighted = calculate_weighted_bri(
            _parse_number_list(observed_raw, "Observed scores"),
            _parse_number_list(maximum_raw, "Maximum scores"),
            _parse_number_list(weights_raw, "Weights"),
        )
        st.metric("Proposed Weighted BRI", f"{weighted:.2f}%")
    except ValueError as exc:
        st.error(str(exc))
    st.caption(
        "Limitation: weights must be validated through expert review and sensitivity "
        "analysis before institutional use."
    )


def _render_longitudinal_calculators() -> None:
    st.markdown("#### Longitudinal readiness and CAPA")
    st.latex(r"\Delta\mathrm{BRI}=\mathrm{BRI}_{post}-\mathrm{BRI}_{pre}")
    st.latex(
        r"\mathrm{RI}(\%)="
        r"\frac{\mathrm{BRI}_{post}-\mathrm{BRI}_{pre}}{\mathrm{BRI}_{pre}}\times100"
    )
    _source(
        "pages 20–21",
        "§4.7 Future Development and Research Directions",
        "Eqs. (15–16)",
        status="Proposed longitudinal metrics requiring validation",
    )
    columns = st.columns(2)
    before = columns[0].number_input(
        "BRI before",
        min_value=0.0,
        max_value=100.0,
        value=70.0,
        step=0.5,
        key="eq_bri_before",
    )
    after = columns[1].number_input(
        "BRI after",
        min_value=0.0,
        max_value=100.0,
        value=82.0,
        step=0.5,
        key="eq_bri_after",
    )
    try:
        change = calculate_bri_change(before, after)
        relative = calculate_relative_bri_improvement(before, after)
        render_metric_grid(
            [
                ("Absolute BRI Change", f"{change:+.2f} points", "Eq. (15)"),
                ("Relative Improvement", f"{relative:+.2f}%", "Eq. (16)"),
            ],
            max_columns=2,
        )
    except ValueError as exc:
        st.error(str(exc))

    st.latex(
        r"\mathrm{CAPA}_{closure}(\%)="
        r"\frac{N_{\mathrm{closed\ CAPA}}}{N_{\mathrm{total\ CAPA}}}\times100"
    )
    _source(
        "page 21",
        "§4.7 Future Development and Research Directions",
        "Eq. (17)",
        status="Proposed performance indicator requiring validation",
    )
    columns = st.columns(2)
    closed = columns[0].number_input(
        "Closed CAPA items",
        min_value=0,
        value=18,
        step=1,
        key="eq_capa_closed",
    )
    total = columns[1].number_input(
        "Total CAPA items",
        min_value=0,
        value=24,
        step=1,
        key="eq_capa_total",
    )
    try:
        closure = calculate_capa_closure(int(closed), int(total))
        st.metric("CAPA Closure", f"{closure:.2f}%")
    except ValueError as exc:
        st.error(str(exc))


def _render_accuracy() -> None:
    st.markdown("#### Illustrative Appendix A diagnostic accuracy")
    st.latex(
        r"\mathrm{Accuracy}(\%)="
        r"\frac{N_{\mathrm{correctly\ classified}}}{N_{\mathrm{evaluated}}}\times100"
    )
    _source(
        "page 24",
        "Appendix A, §A.4 Results and Interpretation",
        "unnumbered accuracy equation",
        status="Illustrative appendix calculation; not validation of MOBRA itself",
    )
    columns = st.columns(2)
    correct = columns[0].number_input(
        "Correctly classified results",
        min_value=0,
        value=285,
        step=1,
        key="eq_accuracy_correct",
    )
    evaluated = columns[1].number_input(
        "Evaluated results",
        min_value=0,
        value=320,
        step=1,
        key="eq_accuracy_total",
    )
    try:
        accuracy = calculate_accuracy(int(correct), int(evaluated))
        st.metric("Illustrative Accuracy", f"{accuracy:.2f}%")
    except ValueError as exc:
        st.error(str(exc))
    st.warning(
        "The manuscript explicitly states that this appendix example does not "
        "validate MOBRA or show that MOBRA performs diagnostic classification."
    )


def _render_additional_tab() -> None:
    render_section_header(
        "Additional Manuscript Equations",
        icon="∑",
        help_text=(
            "These calculations are traceable to the manuscript but several are "
            "future-development proposals rather than current decision logic."
        ),
    )
    _render_balanced_and_weighted()
    _render_longitudinal_calculators()
    _render_accuracy()
    st.info(
        "Inter-assessor agreement is planned in manuscript §2.9 (page 9), but no "
        "agreement coefficient or equation is specified. MOBRA therefore does not "
        "invent or display one."
    )


def _render_glossary() -> None:
    render_section_header("Variable Glossary", icon="□")
    glossary = pd.DataFrame(
        [
            ("BRI", "Biosecurity Readiness Index", "Aggregate assessed readiness", "0–100", "%", "BRI"),
            ("DR_d", "Domain readiness", "Readiness in domain d", "0–100", "%", "Domain"),
            ("S_i", "Observed score", "Requirement maturity/evidence score", "0–S_i max", "points", "BRI"),
            ("S_i max", "Maximum score", "Maximum achievable requirement score", ">0; normally 5", "points", "BRI"),
            ("N", "Assessment population", "Assessed applicable requirements or hazards", "positive integer", "count", "BRI / heat map"),
            ("n_d", "Domain population", "Assessed applicable requirements in domain d", "positive integer", "count", "Domain"),
            ("L_i", "Likelihood", "Likelihood score for hazard i", "1–5", "ordinal score", "Risk"),
            ("C_i", "Consequence", "Consequence score for hazard i", "1–5", "ordinal score", "Risk"),
            ("R_i", "Risk score", "Likelihood × consequence", "1–25", "score", "Risk"),
            ("R_i res", "Residual risk", "Risk remaining after controls", "1–25", "score", "Residual risk"),
            ("EC", "Evidence Completeness", "Requirements with adequate evidence", "0–100", "%", "Evidence"),
            ("H_lc", "Heat-map cell count", "Hazards at likelihood l and consequence c", "0–N", "count", "Heat map"),
            ("O", "Override indicator", "Critical-control or Extreme-risk override", "0 or 1", "binary", "Decision"),
            ("w_i", "Proposed weight", "Validated criticality/importance weight", "non-negative", "weight", "Weighted BRI"),
            ("ΔBRI", "Absolute BRI change", "Post-assessment BRI minus pre-assessment BRI", "-100–100", "percentage points", "Longitudinal"),
            ("RI", "Relative improvement", "BRI change relative to pre-assessment BRI", "context dependent", "%", "Longitudinal"),
        ],
        columns=[
            "Symbol",
            "Variable name",
            "Description",
            "Allowed range",
            "Unit",
            "Related equation",
        ],
    )
    st.dataframe(glossary, width="stretch", hide_index=True)


def render_equations_calculations(context: Any) -> None:
    """Render all verified MOBRA equations and calculator interfaces."""
    render_page_header(
        "Equations & Practical Calculations",
        (
            "Mathematical foundations, manuscript traceability, worked examples, "
            "and interactive decision-support calculators used by MOBRA."
        ),
        icon="∑",
        status="Manuscript-traceable · 27-page source reviewed",
    )
    st.warning(
        "Scientific use boundary: these calculators support transparent operational "
        "assessment. They do not replace qualified biosafety or biosecurity judgment, "
        "institutional risk acceptance, governance approval, or mission-specific review."
    )
    _render_overview()
    readiness_tab, risk_tab, decision_tab, additional_tab = st.tabs(
        [
            "BRI & Domain Readiness",
            "Risk & Residual Risk",
            "Decision Logic",
            "Additional Equations",
        ]
    )
    with readiness_tab:
        _render_readiness_tab()
    with risk_tab:
        _render_risk_tab(context)
    with decision_tab:
        _render_decision_tab()
    with additional_tab:
        _render_additional_tab()
    _render_glossary()
    st.caption(
        "Primary source: MOBRA: A Requirements-Based Operational Biosecurity "
        "Readiness Framework for Mobile Biological Laboratories, 27-page manuscript, "
        "27 July 2026. See docs/EQUATION_AUDIT.md for equation-by-equation code mapping."
    )


__all__ = ["CORE_EQUATIONS", "render_equations_calculations"]
