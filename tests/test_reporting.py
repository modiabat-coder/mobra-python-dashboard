"""HTML report and Streamlit smoke contracts."""

import pytest

from .cases_logic import (
    test_html_report_is_standalone_and_contains_required_sections as test_html_report_is_standalone_and_contains_required_sections,
)
from .cases_logic import test_streamlit_app_smoke as test_streamlit_app_smoke

pytestmark = [pytest.mark.report, pytest.mark.slow]
