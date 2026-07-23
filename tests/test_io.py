"""CSV/XLSX/XLS and hostile-file validation tests."""

from pathlib import Path

import pytest

from mobra.io import read_data_file

from .cases_logic import test_csv_and_xlsx_readers_and_sheet_selection as test_csv_and_xlsx_readers_and_sheet_selection
from .cases_structured_validation import (
    test_file_validation_handles_unsupported_empty_corrupt_and_bad_csv as test_file_validation_handles_unsupported_empty_corrupt_and_bad_csv,
)
from .cases_structured_validation import (
    test_file_validation_reports_header_position_delimiter_and_formula_cache as test_file_validation_reports_header_position_delimiter_and_formula_cache,
)

pytestmark = [pytest.mark.unit, pytest.mark.io]


def test_temporary_file_fixtures_round_trip(temporary_csv_file: Path, temporary_xlsx_file: Path) -> None:
    assert len(read_data_file(temporary_csv_file)) == 1
    assert len(read_data_file(temporary_xlsx_file, sheet_name="Data")) == 1
