"""Stable public filenames and workbook-sheet contracts."""

EXPORT_FILENAMES = {
    "report": "MOBRA_Report.html",
    "hazards_csv": "MOBRA_Analyzed_Hazards.csv",
    "requirements_csv": "MOBRA_Analyzed_Requirements.csv",
    "summary_json": "MOBRA_Summary.json",
    "workbook": "MOBRA_Analyzed_Data.xlsx",
    "mapping_csv": "MOBRA_Requirement_Hazard_Mapping.csv",
    "mapping_coverage_csv": "MOBRA_Mapping_Coverage.csv",
    "critical_profile_csv": "MOBRA_Critical_Control_Profile.csv",
    "critical_assessment_csv": "MOBRA_Critical_Control_Assessment.csv",
    "critical_summary_csv": "MOBRA_Critical_Control_Summary.csv",
    "validation_findings_csv": "MOBRA_Validation_Findings.csv",
    "validation_summary_csv": "MOBRA_Validation_Summary.csv",
    "invalid_records_workbook": "MOBRA_Invalid_Records.xlsx",
}

EXCEL_SHEETS = {
    "hazards": "Analyzed_Hazards",
    "requirements": "Analyzed_Requirements",
    "summary": "Summary",
    "mapping": "Requirement_Hazard_Map",
    "risk_acceptance": "Risk_Acceptance_Summary",
    "critical_profile": "Critical_Control_Profile",
    "critical_assessment": "Critical_Control_Assessment",
    "critical_summary": "Critical_Control_Summary",
    "validation_summary": "Validation_Summary",
    "validation_findings": "Validation_Findings",
    "invalid_hazards": "Invalid_Hazard_Records",
    "invalid_requirements": "Invalid_Requirement_Records",
    "invalid_mapping": "Invalid_Mapping_Records",
    "invalid_profile": "Invalid_Profile_Records",
}

REQUIRED_EXPORT_FILENAMES = tuple(EXPORT_FILENAMES.values())
REQUIRED_EXCEL_SHEET_NAMES = tuple(EXCEL_SHEETS.values())
