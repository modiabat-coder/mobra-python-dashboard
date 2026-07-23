"""Per-hazard risk acceptance and residual-source tests."""

import pytest

from .cases_logic import (
    test_configured_missing_residual_policy_blocks_unassessable_deployment as test_configured_missing_residual_policy_blocks_unassessable_deployment,
)
from .cases_logic import (
    test_missing_residual_uses_explicit_inherent_screening_language as test_missing_residual_uses_explicit_inherent_screening_language,
)
from .cases_logic import (
    test_mixed_risk_sources_are_counted_without_silent_fallback as test_mixed_risk_sources_are_counted_without_silent_fallback,
)
from .cases_logic import test_provisional_acceptance_boundaries as test_provisional_acceptance_boundaries
from .cases_logic import (
    test_require_residual_for_ready_caps_missing_residual_at_conditional as test_require_residual_for_ready_caps_missing_residual_at_conditional,
)
from .cases_logic import (
    test_valid_calculated_residual_category_is_accepted_without_raw_pair as test_valid_calculated_residual_category_is_accepted_without_raw_pair,
)
from .cases_logic import (
    test_valid_residual_risk_is_preferred_per_hazard as test_valid_residual_risk_is_preferred_per_hazard,
)

pytestmark = pytest.mark.unit
