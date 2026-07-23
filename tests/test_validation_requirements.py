"""Granular ORL requirement-validation tests."""

import pytest

from .cases_logic import test_observed_score_above_maximum_is_reported as test_observed_score_above_maximum_is_reported
from .cases_structured_validation import (
    test_duplicate_requirement_ids_are_excluded_but_visible as test_duplicate_requirement_ids_are_excluded_but_visible,
)
from .cases_structured_validation import (
    test_invalid_requirement_is_excluded_from_bri_without_disappearing as test_invalid_requirement_is_excluded_from_bri_without_disappearing,
)
from .cases_structured_validation import (
    test_observed_above_maximum_has_specific_code as test_observed_above_maximum_has_specific_code,
)
from .cases_structured_validation import (
    test_requirement_date_findings_use_explicit_reference_date as test_requirement_date_findings_use_explicit_reference_date,
)
from .cases_structured_validation import (
    test_requirement_granular_validation_codes as test_requirement_granular_validation_codes,
)

pytestmark = pytest.mark.unit
