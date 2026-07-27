"""Portable JSON and Excel representations of MOBRA validation results."""

from __future__ import annotations

import io
import json
from collections.abc import Iterable, Mapping

import pandas as pd

from .export_contracts import EXCEL_SHEETS
from .security import spreadsheet_safe_frame
from .validation_findings import (
    VALIDATION_LIMITATION,
    ValidationFinding,
    finding_counts,
    findings_frame,
    invalid_records,
    summaries_frame,
    validation_overview,
)

INVALID_SHEET_NAMES = {
    "Hazards": EXCEL_SHEETS["invalid_hazards"],
    "Requirements": EXCEL_SHEETS["invalid_requirements"],
    "Mapping": EXCEL_SHEETS["invalid_mapping"],
    "Critical-Control Profile": EXCEL_SHEETS["invalid_profile"],
}


def excel_safe_frame(data: pd.DataFrame) -> pd.DataFrame:
    """Convert container values to readable JSON so openpyxl can serialize them."""
    out = data.copy()
    for column in out.columns:
        if out[column].dtype != object:
            continue
        out[column] = out[column].map(
            lambda value: (
                json.dumps(value, ensure_ascii=False, default=str)
                if isinstance(value, (dict, list, tuple, set))
                else value
            )
        )
    return spreadsheet_safe_frame(out)


def validation_json_fields(
    summaries: Iterable[dict[str, object]],
    findings: Iterable[ValidationFinding],
    *,
    validation_reference_date: str,
) -> dict[str, object]:
    """Build the mandated auditable validation block for JSON outputs."""
    summary_list = list(summaries)
    finding_list = list(findings)
    counts = finding_counts(finding_list)
    overview = validation_overview(summary_list, finding_list)
    if counts["blocking_finding_count"]:
        status = "Blocked"
    elif counts["finding_counts_by_severity"]["Error"]:
        status = "Errors found"
    elif counts["finding_counts_by_severity"]["Warning"]:
        status = "Warnings found"
    else:
        status = "Passed"
    return {
        "validation_reference_date": validation_reference_date,
        "validation_status": status,
        "dataset_validation_summaries": summary_list,
        "finding_counts_by_severity": counts["finding_counts_by_severity"],
        "finding_counts_by_code": counts["finding_counts_by_code"],
        "analysis_eligible_counts": {
            str(summary.get("dataset_type", "Dataset")): int(summary.get("analysis_eligible_records", 0))
            for summary in summary_list
        },
        "excluded_record_counts": {
            str(summary.get("dataset_type", "Dataset")): int(summary.get("excluded_records", 0))
            for summary in summary_list
        },
        "blocking_finding_count": counts["blocking_finding_count"],
        "validation_limitations": VALIDATION_LIMITATION,
        "validation_overview": overview,
    }


def write_validation_sheets(
    writer: pd.ExcelWriter,
    summaries: Iterable[dict[str, object]],
    findings: Iterable[ValidationFinding],
    datasets: Mapping[str, pd.DataFrame | None],
) -> None:
    """Write every required validation sheet, including empty invalid tables."""
    summary_data = summaries_frame(summaries)
    finding_data = findings_frame(findings)
    excel_safe_frame(summary_data).to_excel(writer, sheet_name=EXCEL_SHEETS["validation_summary"], index=False)
    excel_safe_frame(finding_data).to_excel(writer, sheet_name=EXCEL_SHEETS["validation_findings"], index=False)
    for dataset_type, sheet_name in INVALID_SHEET_NAMES.items():
        data = datasets.get(dataset_type)
        invalid = invalid_records(data) if data is not None else pd.DataFrame()
        excel_safe_frame(invalid).to_excel(writer, sheet_name=sheet_name, index=False)


def invalid_records_workbook_bytes(
    summaries: Iterable[dict[str, object]],
    findings: Iterable[ValidationFinding],
    datasets: Mapping[str, pd.DataFrame | None],
) -> bytes:
    """Create the dedicated MOBRA_Invalid_Records.xlsx download."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        write_validation_sheets(writer, summaries, findings, datasets)
    return buffer.getvalue()
