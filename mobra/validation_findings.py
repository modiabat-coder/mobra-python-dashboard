"""Shared structured findings, summaries, and cross-dataset validation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

import pandas as pd

VALIDATION_SEVERITIES = ("Error", "Warning", "Information")
VALIDATION_FINDING_CODES = frozenset(
    {
        "AMBIGUOUS_DATE",
        "AMBIGUOUS_DELIMITER",
        "BLANK_CRITICAL_LINK",
        "BLANK_ID",
        "CASE_ONLY_ID_DIFFERENCE",
        "CASE_ONLY_ID_MISMATCH",
        "COMPLETED_WITH_FUTURE_DUE_DATE",
        "COMPLETELY_BLANK_COLUMN",
        "COMPLETELY_BLANK_ROW",
        "CORRUPTED_WORKBOOK",
        "CSV_PARSE_FAILURE",
        "DUPLICATE_ID",
        "DUPLICATE_MAPPING_PAIR",
        "DUPLICATE_NORMALIZED_COLUMN",
        "DUPLICATE_PROFILE_ROW",
        "DUPLICATE_SHEET_NAME",
        "EMPTY_DATASET",
        "EMPTY_FILE",
        "EMPTY_REQUIRED_TEXT",
        "ENCODING_FAILURE",
        "FILE_READ_FAILURE",
        "FILE_TOO_LARGE",
        "FORMULA_CELL_NOT_EVALUATED",
        "GENERATED_ROW_ORDER_ID",
        "HAZARD_LINK_COUNT",
        "HEADER_NOT_FIRST_ROW",
        "IMPLAUSIBLE_FUTURE_DATE",
        "IMPLAUSIBLE_PAST_DATE",
        "INCOMPLETE_EVIDENCE",
        "INCOMPLETE_RESIDUAL_PAIR",
        "INCONSISTENT_CALCULATED_RISK",
        "INCONSISTENT_ROW_WIDTH",
        "INVALID_BOOLEAN",
        "INVALID_CONTROL_ROLE",
        "INVALID_CRITICALITY_LEVEL",
        "INVALID_DATE",
        "INVALID_FAILURE_DISPOSITION",
        "INVALID_ID_FORMAT",
        "INVALID_INCOMPLETE_DISPOSITION",
        "INVALID_NUMERIC_VALUE",
        "INVALID_RELATIONSHIP_TYPE",
        "INVALID_THRESHOLD",
        "MISSING_APPROVAL_STATUS",
        "MISSING_CRITICAL_CONTROL_COLUMN",
        "MISSING_EVIDENCE",
        "MISSING_EVIDENCE_COLUMN",
        "MISSING_NUMERIC_VALUE",
        "MISSING_OPERATIONAL_TEXT",
        "MISSING_PROFILE_ROW",
        "MISSING_RATIONALE",
        "MISSING_REQUIRED_COLUMN",
        "MISSING_SOURCE_STATUS",
        "NO_READABLE_SHEETS",
        "NONCRITICAL_BLOCKING_DISPOSITION",
        "NON_FINITE_VALUE",
        "NON_INTEGER_VALUE",
        "NON_UTF8_ENCODING",
        "OBSERVED_EXCEEDS_MAXIMUM",
        "OUTSIDE_DEMONSTRATION_SCALE",
        "OVERDUE_OPEN_ACTION",
        "PASSWORD_PROTECTED_WORKBOOK",
        "POSSIBLE_INSTRUCTION_SHEET",
        "REQUIREMENT_LINK_COUNT",
        "RESIDUAL_ASSESSMENT_NOT_PROVIDED",
        "RESIDUAL_RISK_HIGHER_THAN_INHERENT",
        "SUSPICIOUS_DUPLICATE_HAZARD",
        "SUSPICIOUS_DUPLICATE_RECORD",
        "SUSPICIOUS_DUPLICATE_REQUIREMENT",
        "TARGET_BEFORE_ASSESSMENT_DATE",
        "THRESHOLD_EXCEEDS_MAXIMUM",
        "TRAILING_OR_LEADING_WHITESPACE",
        "UNEXPECTEDLY_LOW_BLOCKING_THRESHOLD",
        "UNKNOWN_CATEGORY",
        "UNKNOWN_HAZARD_ID",
        "UNKNOWN_REQUIREMENT_ID",
        "UNKNOWN_SHEET",
        "UNKNOWN_SOURCE_STATUS",
        "UNMAPPED_HAZARD",
        "UNMAPPED_REQUIREMENT",
        "UNRECOGNIZED_DATASET_TYPE",
        "UNSUPPORTED_FILE_TYPE",
        "VALUE_OUT_OF_RANGE",
        "ZERO_OR_NEGATIVE_MAXIMUM",
    }
)
VALIDATION_LIMITATION = (
    "Successful software input validation confirms conformance to implemented data rules only. "
    "It is not scientific, clinical, regulatory, operational, or field validation."
)


@dataclass(frozen=True)
class ValidationFinding:
    """One stable machine-readable validation observation."""

    finding_id: str
    dataset_type: str
    severity: str
    code: str
    message: str
    row_index: int | None = None
    record_id: str | None = None
    column: str | None = None
    original_value: Any = None
    normalized_value: Any = None
    suggested_action: str = "Review and correct the source record."
    blocks_analysis: bool = False

    def __post_init__(self) -> None:
        if self.severity not in VALIDATION_SEVERITIES:
            raise ValueError(f"Unsupported validation severity: {self.severity}.")
        if self.code not in VALIDATION_FINDING_CODES:
            raise ValueError(f"Unregistered validation finding code: {self.code}.")


@dataclass
class FindingCollector:
    """Create deterministic finding IDs in validation order."""

    dataset_type: str
    findings: list[ValidationFinding] = field(default_factory=list)

    def add(
        self,
        severity: str,
        code: str,
        message: str,
        *,
        row_index: int | None = None,
        record_id: object = None,
        column: str | None = None,
        original_value: Any = None,
        normalized_value: Any = None,
        suggested_action: str = "Review and correct the source record.",
        blocks_analysis: bool = False,
    ) -> ValidationFinding:
        finding = ValidationFinding(
            finding_id=f"{self.dataset_type.upper()}-{len(self.findings) + 1:04d}",
            dataset_type=self.dataset_type,
            severity=severity,
            code=code,
            message=message,
            row_index=int(row_index) if row_index is not None else None,
            record_id=None if record_id is None or pd.isna(record_id) else str(record_id),
            column=column,
            original_value=_portable(original_value),
            normalized_value=_portable(normalized_value),
            suggested_action=suggested_action,
            blocks_analysis=bool(blocks_analysis),
        )
        self.findings.append(finding)
        return finding


@dataclass
class CrossDatasetValidationResult:
    """Structured relationship and possible-duplicate findings."""

    findings: list[ValidationFinding] = field(default_factory=list)
    dataset_type: str = "Cross-dataset"

    @property
    def errors(self) -> list[str]:
        return [finding.message for finding in self.findings if finding.severity == "Error"]

    @property
    def warnings(self) -> list[str]:
        return [finding.message for finding in self.findings if finding.severity == "Warning"]

    @property
    def information(self) -> list[str]:
        return [finding.message for finding in self.findings if finding.severity == "Information"]

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def quality(self) -> dict[str, Any]:
        return finding_counts(self.findings)


def _portable(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, pd.Timestamp)):
        return value.isoformat()
    return str(value)


def findings_frame(findings: Iterable[ValidationFinding]) -> pd.DataFrame:
    """Return findings in a stable downloadable column order."""
    columns = [field.name for field in ValidationFinding.__dataclass_fields__.values()]
    rows = [asdict(finding) for finding in findings]
    return pd.DataFrame(rows, columns=columns)


def finding_counts(findings: Iterable[ValidationFinding]) -> dict[str, Any]:
    finding_list = list(findings)
    severity = {level: 0 for level in VALIDATION_SEVERITIES}
    code: dict[str, int] = {}
    for finding in finding_list:
        severity[finding.severity] += 1
        code[finding.code] = code.get(finding.code, 0) + 1
    return {
        "finding_count": len(finding_list),
        "finding_counts_by_severity": severity,
        "finding_counts_by_code": dict(sorted(code.items())),
        "blocking_finding_count": sum(finding.blocks_analysis for finding in finding_list),
    }


def apply_validation_fields(
    data: pd.DataFrame,
    findings: Iterable[ValidationFinding],
    *,
    analysis_eligible: pd.Series,
    record_id_column: str,
    exclusion_reasons: dict[int, list[str]] | None = None,
) -> pd.DataFrame:
    """Attach row counts and eligibility without removing invalid records."""
    out = data.copy()
    finding_list = list(findings)
    errors = pd.Series(0, index=out.index, dtype=int)
    warnings = pd.Series(0, index=out.index, dtype=int)
    information = pd.Series(0, index=out.index, dtype=int)
    for finding in finding_list:
        if finding.row_index is None or finding.row_index not in out.index:
            continue
        if finding.severity == "Error":
            errors.loc[finding.row_index] += 1
        elif finding.severity == "Warning":
            warnings.loc[finding.row_index] += 1
        else:
            information.loc[finding.row_index] += 1
    out["validation_error_count"] = errors
    out["validation_warning_count"] = warnings
    out["validation_information_count"] = information
    out["validation_status"] = "Valid"
    out.loc[information.gt(0), "validation_status"] = "Valid with information"
    out.loc[warnings.gt(0), "validation_status"] = "Valid with warnings"
    out.loc[errors.gt(0), "validation_status"] = "Invalid"
    eligible = analysis_eligible.reindex(out.index, fill_value=False).fillna(False).astype(bool)
    out["analysis_eligible"] = eligible
    reasons = exclusion_reasons or {}
    out["exclusion_reason"] = [
        "; ".join(dict.fromkeys(reasons.get(int(index), []))) if not eligible.loc[index] else "" for index in out.index
    ]
    return out


def validation_summary(
    *,
    dataset_type: str,
    filename: str,
    data: pd.DataFrame,
    findings: Iterable[ValidationFinding],
    required_columns: Iterable[str] = (),
    missing_columns: Iterable[str] = (),
    duplicate_ids: Iterable[str] = (),
    sheet_name: str = "",
    validation_reference_date: str | None = None,
) -> dict[str, Any]:
    """Build one portable dataset-level summary."""
    finding_list = list(findings)
    counts = finding_counts(finding_list)
    eligible = int(data.get("analysis_eligible", pd.Series(True, index=data.index)).fillna(False).astype(bool).sum())
    status = (
        "Blocked"
        if any(f.severity == "Error" and f.blocks_analysis and f.row_index is None for f in finding_list)
        else (
            "Errors found"
            if counts["finding_counts_by_severity"]["Error"]
            else ("Warnings found" if counts["finding_counts_by_severity"]["Warning"] else "Passed")
        )
    )
    return {
        "dataset_type": dataset_type,
        "filename": filename,
        "sheet_name": sheet_name,
        "rows": len(data),
        "columns": len(data.columns),
        "required_columns_found": sorted(set(required_columns) - set(missing_columns)),
        "missing_columns": list(missing_columns),
        "duplicate_ids": list(duplicate_ids),
        "invalid_rows": int(data.get("validation_status", pd.Series(dtype=str)).eq("Invalid").sum()),
        "missing_values": int(data.isna().sum().sum()),
        "analysis_eligible_records": eligible,
        "excluded_records": len(data) - eligible,
        "validation_status": status,
        "validation_reference_date": validation_reference_date,
        **counts,
    }


def summaries_frame(summaries: Iterable[dict[str, Any]]) -> pd.DataFrame:
    """Flatten list-like and dictionary summary values for CSV/Excel."""
    rows = []
    for summary in summaries:
        row = {}
        for key, value in summary.items():
            if isinstance(value, dict):
                row[key] = "; ".join(f"{item_key}={item_value}" for item_key, item_value in value.items())
            elif isinstance(value, (list, tuple, set)):
                row[key] = ", ".join(str(item) for item in value)
            else:
                row[key] = value
        rows.append(row)
    return pd.DataFrame(rows)


def validation_overview(
    summaries: Iterable[dict[str, Any]],
    findings: Iterable[ValidationFinding],
) -> dict[str, Any]:
    """Return portable overall metrics for UI, JSON, and reports."""
    summary_list = list(summaries)
    finding_list = list(findings)
    counts = finding_counts(finding_list)
    return {
        "total_datasets_loaded": len(summary_list),
        "total_records": sum(int(summary.get("rows", 0)) for summary in summary_list),
        "analysis_eligible_records": sum(int(summary.get("analysis_eligible_records", 0)) for summary in summary_list),
        "excluded_records": sum(int(summary.get("excluded_records", 0)) for summary in summary_list),
        "datasets_passing_validation": sum(
            summary.get("validation_status") in {"Passed", "Warnings found"} for summary in summary_list
        ),
        "datasets_blocked": sum(summary.get("validation_status") == "Blocked" for summary in summary_list),
        **counts,
    }


def invalid_records(data: pd.DataFrame) -> pd.DataFrame:
    """Return invalid or excluded rows without discarding their raw trace fields."""
    if data is None or data.empty:
        return pd.DataFrame(columns=list(data.columns) if data is not None else [])
    invalid = data.get("validation_status", pd.Series("Valid", index=data.index)).eq("Invalid")
    excluded = ~data.get("analysis_eligible", pd.Series(True, index=data.index)).fillna(False).astype(bool)
    return data.loc[invalid | excluded].copy()


def _id_series(data: pd.DataFrame, column: str) -> pd.Series:
    return data.get(column, pd.Series(dtype="string")).astype("string")


def _add_id_trace_findings(
    collector: FindingCollector,
    data: pd.DataFrame,
    column: str,
    raw_column: str | None = None,
) -> None:
    raw = _id_series(data, raw_column or column)
    for index, value in raw.items():
        if pd.isna(value):
            continue
        text = str(value)
        if text != text.strip():
            collector.add(
                "Warning",
                "TRAILING_OR_LEADING_WHITESPACE",
                f"{collector.dataset_type}: {column} contains leading or trailing whitespace at row {index + 2}.",
                row_index=index,
                record_id=text.strip(),
                column=column,
                original_value=text,
                normalized_value=text.strip(),
                suggested_action="Remove accidental whitespace from the source identifier.",
            )


def _possible_duplicate_descriptions(
    collector: FindingCollector,
    data: pd.DataFrame,
    id_column: str,
    text_column: str,
    code: str,
) -> None:
    if not {id_column, text_column}.issubset(data.columns):
        return
    normalized = data[text_column].astype("string").str.strip().str.casefold()
    duplicated = normalized.notna() & normalized.ne("") & normalized.duplicated(keep=False)
    for value, group in data.loc[duplicated].assign(_normalized=normalized[duplicated]).groupby("_normalized"):
        ids = sorted(group[id_column].dropna().astype(str).unique())
        if len(ids) > 1:
            collector.add(
                "Warning",
                code,
                f"{collector.dataset_type}: possible duplicate wording is used by different IDs: {', '.join(ids)}.",
                column=text_column,
                original_value=value,
                suggested_action="Review whether these records are intentional variants or duplicates.",
            )


def _repeated_core_records(
    collector: FindingCollector,
    data: pd.DataFrame,
    id_column: str,
    core_columns: list[str],
) -> None:
    available = [column for column in core_columns if column in data.columns]
    if not available or id_column not in data.columns:
        return
    normalized = data[available].copy()
    for column in available:
        normalized[column] = normalized[column].astype("string").str.strip().str.casefold()
    repeated = normalized.notna().any(axis=1) & normalized.duplicated(keep=False)
    for _, indexes in normalized.loc[repeated].groupby(available, dropna=False).groups.items():
        index_list = list(indexes)
        ids = sorted(data.loc[index_list, id_column].dropna().astype(str).unique())
        if len(ids) > 1:
            collector.add(
                "Warning",
                "SUSPICIOUS_DUPLICATE_RECORD",
                f"{collector.dataset_type}: records {', '.join(ids)} repeat identical core fields ({', '.join(available)}).",
                column=", ".join(available),
                original_value=ids,
                suggested_action="Review whether the repeated records are intentional or should be consolidated.",
            )


def validate_cross_dataset_consistency(
    hazards: pd.DataFrame,
    requirements: pd.DataFrame,
    mapping: pd.DataFrame | None = None,
    critical_profile: pd.DataFrame | None = None,
    *,
    require_full_hazard_coverage: bool = True,
) -> CrossDatasetValidationResult:
    """Validate ID relationships, normalization hazards, coverage, and possible duplicates."""
    collector = FindingCollector("Cross-dataset")
    hazard_ids_raw = _id_series(hazards, "hazard_id")
    requirement_ids_raw = _id_series(requirements, "requirement_id")
    hazard_ids = set(hazard_ids_raw.dropna().astype(str).str.strip())
    requirement_ids = set(requirement_ids_raw.dropna().astype(str).str.strip())
    _add_id_trace_findings(collector, hazards, "hazard_id", "hazard_id_raw" if "hazard_id_raw" in hazards else None)
    _add_id_trace_findings(
        collector,
        requirements,
        "requirement_id",
        "requirement_id_raw" if "requirement_id_raw" in requirements else None,
    )

    def case_map(values: set[str]) -> dict[str, list[str]]:
        mapped: dict[str, list[str]] = {}
        for value in values:
            mapped.setdefault(value.casefold(), []).append(value)
        return mapped

    for label, values in (("hazard", hazard_ids), ("requirement", requirement_ids)):
        for variants in case_map(values).values():
            if len(variants) > 1:
                collector.add(
                    "Error",
                    "CASE_ONLY_ID_DIFFERENCE",
                    f"Cross-dataset: {label} IDs differ only by capitalization: {', '.join(sorted(variants))}.",
                    column=f"{label}_id",
                    original_value=variants,
                    suggested_action="Use one exact capitalization for each identifier.",
                    blocks_analysis=True,
                )

    if mapping is not None and not mapping.empty:
        mapped_hazards_raw = _id_series(mapping, "hazard_id_raw" if "hazard_id_raw" in mapping else "hazard_id")
        mapped_requirements_raw = _id_series(
            mapping, "requirement_id_raw" if "requirement_id_raw" in mapping else "requirement_id"
        )
        _add_id_trace_findings(collector, mapping, "hazard_id", "hazard_id_raw" if "hazard_id_raw" in mapping else None)
        _add_id_trace_findings(
            collector,
            mapping,
            "requirement_id",
            "requirement_id_raw" if "requirement_id_raw" in mapping else None,
        )
        for index, raw in mapped_hazards_raw.items():
            if pd.isna(raw):
                continue
            text, stripped = str(raw), str(raw).strip()
            if stripped not in hazard_ids:
                case_match = next((value for value in hazard_ids if value.casefold() == stripped.casefold()), None)
                code = "CASE_ONLY_ID_MISMATCH" if case_match else "UNKNOWN_HAZARD_ID"
                collector.add(
                    "Error",
                    code,
                    f"Cross-dataset: mapping row {index + 2} references hazard ID {text!r} that does not exactly match a hazard record.",
                    row_index=index,
                    record_id=mapping.get("mapping_id", pd.Series(index=mapping.index)).get(index),
                    column="hazard_id",
                    original_value=text,
                    normalized_value=case_match or stripped,
                    suggested_action="Use an existing hazard_id with exact case and no surrounding whitespace.",
                    blocks_analysis=True,
                )
        for index, raw in mapped_requirements_raw.items():
            if pd.isna(raw):
                continue
            text, stripped = str(raw), str(raw).strip()
            if stripped not in requirement_ids:
                case_match = next((value for value in requirement_ids if value.casefold() == stripped.casefold()), None)
                code = "CASE_ONLY_ID_MISMATCH" if case_match else "UNKNOWN_REQUIREMENT_ID"
                collector.add(
                    "Error",
                    code,
                    f"Cross-dataset: mapping row {index + 2} references requirement ID {text!r} that does not exactly match a requirement record.",
                    row_index=index,
                    record_id=mapping.get("mapping_id", pd.Series(index=mapping.index)).get(index),
                    column="requirement_id",
                    original_value=text,
                    normalized_value=case_match or stripped,
                    suggested_action="Use an existing requirement_id with exact case and no surrounding whitespace.",
                    blocks_analysis=True,
                )
        mapped_hazards = set(mapped_hazards_raw.dropna().astype(str).str.strip()) & hazard_ids
        mapped_requirements = set(mapped_requirements_raw.dropna().astype(str).str.strip()) & requirement_ids
        for hazard_id in sorted(hazard_ids - mapped_hazards):
            collector.add(
                "Error" if require_full_hazard_coverage else "Warning",
                "UNMAPPED_HAZARD",
                f"Cross-dataset: hazard {hazard_id} has no linked requirement.",
                record_id=hazard_id,
                column="hazard_id",
                suggested_action="Add at least one valid requirement-to-hazard mapping link.",
                blocks_analysis=require_full_hazard_coverage,
            )
        for requirement_id in sorted(requirement_ids - mapped_requirements):
            collector.add(
                "Warning",
                "UNMAPPED_REQUIREMENT",
                f"Cross-dataset: requirement {requirement_id} has no linked hazard.",
                record_id=requirement_id,
                column="requirement_id",
                suggested_action="Review whether a representative hazard link should be added.",
            )

    if critical_profile is not None and not critical_profile.empty:
        profile_ids_raw = _id_series(
            critical_profile,
            "requirement_id_raw" if "requirement_id_raw" in critical_profile else "requirement_id",
        )
        _add_id_trace_findings(
            collector,
            critical_profile,
            "requirement_id",
            "requirement_id_raw" if "requirement_id_raw" in critical_profile else None,
        )
        profile_ids = set(profile_ids_raw.dropna().astype(str).str.strip())
        duplicates = profile_ids_raw.astype(str).str.strip().duplicated(keep=False)
        for index, value in profile_ids_raw[duplicates].items():
            collector.add(
                "Error",
                "DUPLICATE_PROFILE_ROW",
                f"Cross-dataset: profile requirement {str(value).strip()} appears more than once.",
                row_index=index,
                record_id=str(value).strip(),
                column="requirement_id",
                original_value=value,
                blocks_analysis=True,
            )
        for profile_id in sorted(profile_ids - requirement_ids):
            case_match = next((value for value in requirement_ids if value.casefold() == profile_id.casefold()), None)
            collector.add(
                "Error",
                "CASE_ONLY_ID_MISMATCH" if case_match else "UNKNOWN_REQUIREMENT_ID",
                f"Cross-dataset: critical-control profile ID {profile_id} does not exactly match a requirement.",
                record_id=profile_id,
                column="requirement_id",
                normalized_value=case_match,
                blocks_analysis=True,
            )
        for missing_id in sorted(requirement_ids - profile_ids):
            collector.add(
                "Error",
                "MISSING_PROFILE_ROW",
                f"Cross-dataset: requirement {missing_id} has no critical-control profile row.",
                record_id=missing_id,
                column="requirement_id",
                blocks_analysis=True,
            )

    _possible_duplicate_descriptions(collector, hazards, "hazard_id", "hazard", "SUSPICIOUS_DUPLICATE_HAZARD")
    _possible_duplicate_descriptions(
        collector,
        requirements,
        "requirement_id",
        "requirement",
        "SUSPICIOUS_DUPLICATE_REQUIREMENT",
    )
    _repeated_core_records(
        collector,
        hazards,
        "hazard_id",
        ["hazard", "likelihood", "consequence", "domain"],
    )
    _repeated_core_records(
        collector,
        requirements,
        "requirement_id",
        ["requirement", "observed_score", "maximum_score", "domain"],
    )
    return CrossDatasetValidationResult(collector.findings)
