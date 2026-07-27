"""Reusable quantitative calculations documented by the MOBRA manuscript."""

from __future__ import annotations

from collections.abc import Sequence
from math import isfinite


def _finite_number(value: float | int, name: str) -> float:
    """Return ``value`` as a finite float or raise a clear validation error."""
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric.") from exc
    if not isfinite(number):
        raise ValueError(f"{name} must be finite.")
    return number


def _nonnegative_integer(value: int, name: str) -> int:
    """Validate a count used in a percentage denominator."""
    number = _finite_number(value, name)
    if not number.is_integer() or number < 0:
        raise ValueError(f"{name} must be a non-negative integer.")
    return int(number)


def calculate_percentage(
    numerator: float | int,
    denominator: float | int,
    *,
    numerator_name: str = "Numerator",
    denominator_name: str = "Denominator",
) -> float:
    """Calculate a bounded percentage after validating both terms."""
    numerator_value = _finite_number(numerator, numerator_name)
    denominator_value = _finite_number(denominator, denominator_name)
    if numerator_value < 0:
        raise ValueError(f"{numerator_name} must not be negative.")
    if denominator_value <= 0:
        raise ValueError(f"{denominator_name} must be greater than zero.")
    if numerator_value > denominator_value:
        raise ValueError(
            f"{numerator_name} must not exceed {denominator_name.lower()}."
        )
    return 100.0 * numerator_value / denominator_value


def maximum_possible_score(
    applicable_requirements: int,
    maximum_score_per_requirement: float | int,
) -> float:
    """Return the maximum score for the applicable assessment population."""
    count = _nonnegative_integer(
        applicable_requirements,
        "Applicable requirements",
    )
    maximum_per_item = _finite_number(
        maximum_score_per_requirement,
        "Maximum score per requirement",
    )
    if count <= 0:
        raise ValueError("Applicable requirements must be greater than zero.")
    if maximum_per_item <= 0:
        raise ValueError("Maximum score per requirement must be greater than zero.")
    return count * maximum_per_item


def calculate_bri_from_totals(
    observed_score: float | int,
    maximum_score: float | int,
) -> float:
    """Calculate the unweighted Biosecurity Readiness Index from score totals."""
    return calculate_percentage(
        observed_score,
        maximum_score,
        numerator_name="Observed score",
        denominator_name="Maximum score",
    )


def calculate_bri_from_counts(
    applicable_requirements: int,
    maximum_score_per_requirement: float | int,
    observed_score: float | int,
) -> tuple[float, float]:
    """Return maximum possible score and BRI for calculator-style inputs."""
    maximum = maximum_possible_score(
        applicable_requirements,
        maximum_score_per_requirement,
    )
    return maximum, calculate_bri_from_totals(observed_score, maximum)


def calculate_domain_readiness_from_totals(
    observed_score: float | int,
    maximum_score: float | int,
) -> float:
    """Calculate one domain's readiness percentage from observed and maximum totals."""
    return calculate_percentage(
        observed_score,
        maximum_score,
        numerator_name="Observed domain score",
        denominator_name="Maximum domain score",
    )


def calculate_evidence_completeness(
    requirements_with_adequate_evidence: int,
    assessed_requirements: int,
) -> float:
    """Calculate the manuscript's Evidence Completeness indicator."""
    adequate = _nonnegative_integer(
        requirements_with_adequate_evidence,
        "Requirements with adequate evidence",
    )
    assessed = _nonnegative_integer(
        assessed_requirements,
        "Assessed requirements",
    )
    return calculate_percentage(
        adequate,
        assessed,
        numerator_name="Requirements with adequate evidence",
        denominator_name="Assessed requirements",
    )


def calculate_mean_domain_readiness(
    domain_readiness_percentages: Sequence[float | int],
) -> float:
    """Calculate the equal-domain mean used only by the balanced prototype."""
    if not domain_readiness_percentages:
        raise ValueError("At least one domain-readiness percentage is required.")
    values = [
        _finite_number(value, "Domain readiness")
        for value in domain_readiness_percentages
    ]
    if any(value < 0 or value > 100 for value in values):
        raise ValueError("Domain-readiness percentages must be between 0 and 100.")
    return sum(values) / len(values)


def calculate_weighted_bri(
    observed_scores: Sequence[float | int],
    maximum_scores: Sequence[float | int],
    weights: Sequence[float | int],
) -> float:
    """Calculate the manuscript's proposed, not-yet-validated weighted BRI."""
    if not observed_scores:
        raise ValueError("At least one scored requirement is required.")
    if not (len(observed_scores) == len(maximum_scores) == len(weights)):
        raise ValueError("Observed scores, maximum scores, and weights must align.")

    observed_values = [
        _finite_number(value, "Observed score") for value in observed_scores
    ]
    maximum_values = [
        _finite_number(value, "Maximum score") for value in maximum_scores
    ]
    weight_values = [_finite_number(value, "Weight") for value in weights]

    if any(maximum <= 0 for maximum in maximum_values):
        raise ValueError("Every maximum score must be greater than zero.")
    if any(weight < 0 for weight in weight_values) or not any(
        weight > 0 for weight in weight_values
    ):
        raise ValueError("Weights must be non-negative with at least one positive value.")
    if any(
        observed < 0 or observed > maximum
        for observed, maximum in zip(observed_values, maximum_values, strict=True)
    ):
        raise ValueError("Every observed score must be between zero and its maximum.")

    weighted_observed = sum(
        weight * observed
        for weight, observed in zip(weight_values, observed_values, strict=True)
    )
    weighted_maximum = sum(
        weight * maximum
        for weight, maximum in zip(weight_values, maximum_values, strict=True)
    )
    return calculate_bri_from_totals(weighted_observed, weighted_maximum)


def calculate_control_effectiveness(
    inherent_risk_score: float | int,
    residual_risk_score: float | int,
) -> float:
    """Calculate proposed control effectiveness from inherent and residual risk."""
    inherent = _finite_number(inherent_risk_score, "Inherent risk score")
    residual = _finite_number(residual_risk_score, "Residual risk score")
    if not 1 <= inherent <= 25 or not 1 <= residual <= 25:
        raise ValueError("Risk scores must be between 1 and 25.")
    return 100.0 * (inherent - residual) / inherent


def calculate_absolute_risk_reduction(
    initial_risk_score: float | int,
    residual_risk_score: float | int,
) -> float:
    """Return the derived absolute change between initial and residual risk."""
    initial = _finite_number(initial_risk_score, "Initial risk score")
    residual = _finite_number(residual_risk_score, "Residual risk score")
    if not 1 <= initial <= 25 or not 1 <= residual <= 25:
        raise ValueError("Risk scores must be between 1 and 25.")
    return initial - residual


def calculate_bri_change(
    bri_before: float | int,
    bri_after: float | int,
) -> float:
    """Calculate the absolute change in BRI between two assessment periods."""
    before = _finite_number(bri_before, "BRI before")
    after = _finite_number(bri_after, "BRI after")
    if not 0 <= before <= 100 or not 0 <= after <= 100:
        raise ValueError("BRI percentages must be between 0 and 100.")
    return after - before


def calculate_relative_bri_improvement(
    bri_before: float | int,
    bri_after: float | int,
) -> float:
    """Calculate the manuscript's proposed relative BRI improvement."""
    before = _finite_number(bri_before, "BRI before")
    after = _finite_number(bri_after, "BRI after")
    if not 0 < before <= 100 or not 0 <= after <= 100:
        raise ValueError(
            "BRI before must be greater than zero and both values must be at most 100."
        )
    return 100.0 * (after - before) / before


def calculate_capa_closure(closed_items: int, total_items: int) -> float:
    """Calculate the manuscript's proposed CAPA closure percentage."""
    closed = _nonnegative_integer(closed_items, "Closed CAPA items")
    total = _nonnegative_integer(total_items, "Total CAPA items")
    return calculate_percentage(
        closed,
        total,
        numerator_name="Closed CAPA items",
        denominator_name="Total CAPA items",
    )


def calculate_accuracy(correctly_classified: int, evaluated: int) -> float:
    """Calculate the Appendix A illustrative diagnostic accuracy percentage."""
    correct = _nonnegative_integer(
        correctly_classified,
        "Correctly classified results",
    )
    total = _nonnegative_integer(evaluated, "Evaluated results")
    return calculate_percentage(
        correct,
        total,
        numerator_name="Correctly classified results",
        denominator_name="Evaluated results",
    )


__all__ = [
    "calculate_absolute_risk_reduction",
    "calculate_accuracy",
    "calculate_bri_change",
    "calculate_bri_from_counts",
    "calculate_bri_from_totals",
    "calculate_capa_closure",
    "calculate_control_effectiveness",
    "calculate_domain_readiness_from_totals",
    "calculate_evidence_completeness",
    "calculate_mean_domain_readiness",
    "calculate_percentage",
    "calculate_relative_bri_improvement",
    "calculate_weighted_bri",
    "maximum_possible_score",
]
