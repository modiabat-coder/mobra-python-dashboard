"""CSV, JSON, and Excel export contracts."""

from io import BytesIO

import pandas as pd
import pytest

from app import excel_bytes
from mobra.export_contracts import REQUIRED_EXCEL_SHEET_NAMES, REQUIRED_EXPORT_FILENAMES

from .cases_logic import test_analyzed_workbook_includes_mapping_sheet as test_analyzed_workbook_includes_mapping_sheet
from .cases_structured_validation import (
    test_validation_json_csv_excel_and_html_outputs_are_auditable as test_validation_json_csv_excel_and_html_outputs_are_auditable,
)

pytestmark = [pytest.mark.integration, pytest.mark.io]


EXPECTED_FILENAMES = (
    "MOBRA_Report.html",
    "MOBRA_Analyzed_Hazards.csv",
    "MOBRA_Analyzed_Requirements.csv",
    "MOBRA_Summary.json",
    "MOBRA_Analyzed_Data.xlsx",
    "MOBRA_Requirement_Hazard_Mapping.csv",
    "MOBRA_Mapping_Coverage.csv",
    "MOBRA_Critical_Control_Profile.csv",
    "MOBRA_Critical_Control_Assessment.csv",
    "MOBRA_Critical_Control_Summary.csv",
    "MOBRA_Validation_Findings.csv",
    "MOBRA_Validation_Summary.csv",
    "MOBRA_Invalid_Records.xlsx",
)

EXPECTED_SHEETS = (
    "Analyzed_Hazards",
    "Analyzed_Requirements",
    "Summary",
    "Requirement_Hazard_Map",
    "Risk_Acceptance_Summary",
    "Critical_Control_Profile",
    "Critical_Control_Assessment",
    "Critical_Control_Summary",
    "Validation_Summary",
    "Validation_Findings",
    "Invalid_Hazard_Records",
    "Invalid_Requirement_Records",
    "Invalid_Mapping_Records",
    "Invalid_Profile_Records",
)


def test_public_download_filename_contract_is_stable() -> None:
    assert REQUIRED_EXPORT_FILENAMES == EXPECTED_FILENAMES
    assert all("/" not in filename and "\\" not in filename for filename in REQUIRED_EXPORT_FILENAMES)


def test_analyzed_workbook_exact_sheet_contract(demo_pipeline: dict[str, object]) -> None:
    workbook = excel_bytes(
        demo_pipeline["hazards"],
        demo_pipeline["requirements"],
        {"contract": "test"},
        demo_pipeline["mapping_result"].data,
        critical_profile=demo_pipeline["critical_assessment"].validation.data,
        critical_control_assessment=demo_pipeline["critical_assessment"],
    )
    sheets = tuple(pd.ExcelFile(BytesIO(workbook), engine="openpyxl").sheet_names)
    assert REQUIRED_EXCEL_SHEET_NAMES == EXPECTED_SHEETS
    assert sheets == EXPECTED_SHEETS
