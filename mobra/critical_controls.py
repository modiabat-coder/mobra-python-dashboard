"""Transparent critical-control profile validation and structured assessment."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .validation_findings import FindingCollector, ValidationFinding, apply_validation_fields, finding_counts

CRITICALITY_LEVELS = ("Deployment-blocking", "Conditional", "Important", "Non-critical")
FAILURE_DISPOSITIONS = (
    "DO NOT DEPLOY",
    "CONDITIONAL DEPLOYMENT",
    "CORRECTIVE ACTION REQUIRED",
    "NO AUTOMATIC OVERRIDE",
)
INCOMPLETE_RECORD_DISPOSITIONS = (
    "DO NOT DEPLOY",
    "CONDITIONAL DEPLOYMENT",
    "MANUAL REVIEW REQUIRED",
    "NO AUTOMATIC OVERRIDE",
)
CONTROL_OUTCOMES = ("Pass", "Conditional gap", "Fail", "Manual review", "Not applicable")
PROFILE_REQUIRED_COLUMNS = (
    "requirement_id",
    "criticality_level",
    "failure_disposition",
    "minimum_acceptable_score",
    "evidence_required",
    "incomplete_record_disposition",
    "rationale",
    "approval_status",
    "source_status",
)
CRITICAL_CONTROL_LIMITATION = (
    "Critical-control classifications and thresholds are provisional demonstration rules and require "
    "expert and institutional approval before operational use."
)


@dataclass
class CriticalControlProfileValidationResult:
    """Validated profile plus deterministic coverage diagnostics."""

    data: pd.DataFrame
    findings: list[ValidationFinding] = field(default_factory=list)
    missing_columns: list[str] = field(default_factory=list)
    duplicate_ids: list[str] = field(default_factory=list)
    missing_requirement_ids: list[str] = field(default_factory=list)
    unknown_requirement_ids: list[str] = field(default_factory=list)
    invalid_rows: list[int] = field(default_factory=list)
    dataset_type: str = "Critical-Control Profile"

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
    def quality(self) -> dict[str, int | float]:
        return {
            "profile_rows": len(self.data),
            "unique_requirement_ids": int(self.data.get("requirement_id", pd.Series(dtype=str)).nunique()),
            "duplicate_ids": len(self.duplicate_ids),
            "missing_requirement_ids": len(self.missing_requirement_ids),
            "unknown_requirement_ids": len(self.unknown_requirement_ids),
            "validation_errors": len(self.errors),
            "analysis_eligible_records": int(
                self.data.get("analysis_eligible", pd.Series(True, index=self.data.index)).fillna(False).sum()
            ),
            **finding_counts(self.findings),
        }


@dataclass
class CriticalControlAssessment:
    """Structured governance result with summary and focused finding tables."""

    data: pd.DataFrame
    summary: dict[str, Any]
    deployment_blocking_failures: pd.DataFrame
    conditional_gaps: pd.DataFrame
    important_gaps: pd.DataFrame
    evidence_deficiencies: pd.DataFrame
    incomplete_records: pd.DataFrame
    manual_review_items: pd.DataFrame
    validation: CriticalControlProfileValidationResult

    @property
    def ok(self) -> bool:
        return self.validation.ok


def _evidence_status(row: pd.Series) -> str:
    required = bool(row["evidence_required"])
    evidence = row.get("objective_evidence", row.get("evidence", pd.NA))
    if pd.isna(evidence) or str(evidence).strip().lower() in {"", "nan", "none", "not provided"}:
        return "Missing" if required else "Not assessed"
    normalized = str(evidence).strip().lower()
    incomplete_markers = ("incomplete", "pending", "overdue", "unavailable", "missing", "expired", "draft")
    if any(marker in normalized for marker in incomplete_markers):
        return "Incomplete"
    return "Complete"


def _record_complete(row: pd.Series) -> bool:
    requirement_id = row.get("requirement_id")
    requirement = row.get("requirement")
    if pd.isna(requirement_id) or not str(requirement_id).strip():
        return False
    if pd.isna(requirement) or not str(requirement).strip():
        return False
    observed = pd.to_numeric(pd.Series([row.get("observed_score")]), errors="coerce").iloc[0]
    maximum = pd.to_numeric(pd.Series([row.get("maximum_score")]), errors="coerce").iloc[0]
    return bool(pd.notna(observed) and pd.notna(maximum) and maximum > 0 and 0 <= observed <= maximum)


def _evidence_disposition(criticality_level: str, failure_disposition: str) -> str:
    if criticality_level == "Deployment-blocking":
        return "DO NOT DEPLOY"
    if criticality_level == "Conditional":
        return "CONDITIONAL DEPLOYMENT"
    if criticality_level == "Important":
        return "MANUAL REVIEW REQUIRED"
    return "NO AUTOMATIC OVERRIDE"


def _select_disposition(dispositions: list[str]) -> str:
    priority = {
        "DO NOT DEPLOY": 5,
        "CONDITIONAL DEPLOYMENT": 4,
        "MANUAL REVIEW REQUIRED": 3,
        "CORRECTIVE ACTION REQUIRED": 2,
        "NO AUTOMATIC OVERRIDE": 1,
    }
    return max(dispositions, key=lambda value: priority[value])


def _empty_assessment(validation: CriticalControlProfileValidationResult) -> CriticalControlAssessment:
    empty = pd.DataFrame()
    summary = {
        "critical_control_profile_status": "Invalid",
        "criticality_level_counts": {level: 0 for level in CRITICALITY_LEVELS},
        "critical_control_outcome_counts": {outcome: 0 for outcome in CONTROL_OUTCOMES},
        "deployment_blocking_failure_count": 0,
        "conditional_gap_count": 0,
        "important_gap_count": 0,
        "evidence_deficiency_count": 0,
        "incomplete_critical_record_count": 0,
        "manual_review_count": 0,
        "formal_approval_required_count": 0,
        "compensating_control_required_count": 0,
        "blocking_requirement_ids": [],
        "conditional_requirement_ids": [],
        "important_gap_requirement_ids": [],
        "evidence_deficient_requirement_ids": [],
        "manual_review_requirement_ids": [],
        "critical_control_limitations": CRITICAL_CONTROL_LIMITATION,
    }
    return CriticalControlAssessment(empty, summary, empty, empty, empty, empty, empty, empty, validation)


def assess_critical_controls(
    requirements_df: pd.DataFrame,
    critical_profile_df: pd.DataFrame,
) -> CriticalControlAssessment:
    """Assess score, evidence, and record completeness as separate governance dimensions."""
    validation = validate_critical_control_profile(critical_profile_df, requirements_df)
    if not validation.ok:
        return _empty_assessment(validation)

    profile = validation.data[list(PROFILE_REQUIRED_COLUMNS)].copy()
    profile_columns = [column for column in PROFILE_REQUIRED_COLUMNS if column != "requirement_id"]
    requirements = requirements_df.drop(
        columns=[column for column in profile_columns if column in requirements_df], errors="ignore"
    )
    data = requirements.merge(profile, on="requirement_id", how="left", validate="one_to_one")
    observed = pd.to_numeric(data["observed_score"], errors="coerce")
    maximum = pd.to_numeric(data["maximum_score"], errors="coerce")
    threshold = pd.to_numeric(data["minimum_acceptable_score"], errors="coerce")
    scorable = observed.notna() & maximum.notna() & (maximum > 0) & (observed >= 0) & (observed <= maximum)
    data["score_status"] = np.select(
        [~scorable, observed >= threshold],
        ["Not scorable", "Meets threshold"],
        default="Below threshold",
    )
    data["evidence_status"] = data.apply(_evidence_status, axis=1)
    data["completion_status"] = data.apply(
        lambda row: "Complete" if _record_complete(row) else "Incomplete",
        axis=1,
    )
    data["score_failure"] = data["score_status"].eq("Below threshold")
    data["evidence_deficiency"] = data["evidence_required"] & data["evidence_status"].isin(
        ["Missing", "Incomplete", "Not assessed"]
    )
    data["incomplete_critical_record"] = data["completion_status"].ne("Complete")

    outcomes: list[str] = []
    dispositions: list[str] = []
    reasons: list[str] = []
    manual_review: list[bool] = []
    compensating: list[bool] = []
    approvals: list[bool] = []
    for _, row in data.iterrows():
        issue_dispositions: list[str] = []
        reason_parts: list[str] = []
        if row["incomplete_critical_record"]:
            issue_dispositions.append(str(row["incomplete_record_disposition"]))
            reason_parts.append("the requirement record is incomplete or not scorable")
        if row["score_failure"]:
            issue_dispositions.append(str(row["failure_disposition"]))
            reason_parts.append(
                f"score {float(row['observed_score']):g}/{float(row['maximum_score']):g} is below threshold "
                f"{float(row['minimum_acceptable_score']):g}"
            )
        if row["evidence_deficiency"]:
            issue_dispositions.append(
                _evidence_disposition(str(row["criticality_level"]), str(row["failure_disposition"]))
            )
            reason_parts.append(f"required evidence is {str(row['evidence_status']).lower()}")

        if not issue_dispositions:
            disposition = "NO AUTOMATIC OVERRIDE"
            if row["criticality_level"] == "Non-critical":
                outcome = "Not applicable"
                reason = f"{row['requirement_id']} is Non-critical and creates no automatic deployment override."
            else:
                outcome = "Pass"
                reason = (
                    f"{row['requirement_id']} meets threshold {float(row['minimum_acceptable_score']):g} "
                    "and its required evidence is complete."
                )
        else:
            disposition = _select_disposition(issue_dispositions)
            outcome = {
                "DO NOT DEPLOY": "Fail",
                "CONDITIONAL DEPLOYMENT": "Conditional gap",
                "MANUAL REVIEW REQUIRED": "Manual review",
                "CORRECTIVE ACTION REQUIRED": "Fail",
                "NO AUTOMATIC OVERRIDE": "Not applicable",
            }[disposition]
            reason = f"{row['requirement_id']}: " + "; ".join(reason_parts) + "."
            if disposition == "CONDITIONAL DEPLOYMENT":
                reason += (
                    " Documented corrective action, a named owner, target date, formal approval, and a "
                    "compensating control are required."
                )
            elif disposition == "MANUAL REVIEW REQUIRED":
                reason += " Documented manual review and formal approval are required before automatic READY."
            elif disposition == "CORRECTIVE ACTION REQUIRED":
                reason += " Corrective action and monitoring are required without an automatic deployment override."
        outcomes.append(outcome)
        dispositions.append(disposition)
        reasons.append(reason)
        manual_review.append(disposition == "MANUAL REVIEW REQUIRED")
        compensating.append(disposition == "CONDITIONAL DEPLOYMENT")
        approvals.append(disposition in {"CONDITIONAL DEPLOYMENT", "MANUAL REVIEW REQUIRED"})

    data["critical_control_outcome"] = outcomes
    data["critical_control_disposition"] = dispositions
    data["critical_control_reason"] = reasons
    data["requires_manual_review"] = manual_review
    data["compensating_control_required"] = compensating
    data["formal_approval_required"] = approvals

    blocking = data.loc[data["critical_control_disposition"].eq("DO NOT DEPLOY")].copy()
    conditional = data.loc[data["critical_control_disposition"].eq("CONDITIONAL DEPLOYMENT")].copy()
    important = data.loc[
        data["criticality_level"].eq("Important")
        & (data["score_failure"] | data["evidence_deficiency"] | data["incomplete_critical_record"])
    ].copy()
    evidence = data.loc[data["evidence_deficiency"]].copy()
    incomplete = data.loc[data["incomplete_critical_record"]].copy()
    manual = data.loc[data["requires_manual_review"]].copy()

    criticality_counts = (
        data["criticality_level"].value_counts().reindex(CRITICALITY_LEVELS, fill_value=0).astype(int).to_dict()
    )
    outcome_counts = (
        data["critical_control_outcome"].value_counts().reindex(CONTROL_OUTCOMES, fill_value=0).astype(int).to_dict()
    )
    summary = {
        "critical_control_profile_status": "Valid",
        "criticality_level_counts": criticality_counts,
        "critical_control_outcome_counts": outcome_counts,
        "deployment_blocking_failure_count": len(blocking),
        "conditional_gap_count": len(conditional),
        "important_gap_count": len(important),
        "evidence_deficiency_count": len(evidence),
        "incomplete_critical_record_count": len(incomplete),
        "manual_review_count": len(manual),
        "formal_approval_required_count": int(data["formal_approval_required"].sum()),
        "compensating_control_required_count": int(data["compensating_control_required"].sum()),
        "blocking_requirement_ids": blocking["requirement_id"].astype(str).tolist(),
        "conditional_requirement_ids": conditional["requirement_id"].astype(str).tolist(),
        "important_gap_requirement_ids": important["requirement_id"].astype(str).tolist(),
        "evidence_deficient_requirement_ids": evidence["requirement_id"].astype(str).tolist(),
        "manual_review_requirement_ids": manual["requirement_id"].astype(str).tolist(),
        "critical_control_limitations": CRITICAL_CONTROL_LIMITATION,
    }
    return CriticalControlAssessment(
        data=data,
        summary=summary,
        deployment_blocking_failures=blocking,
        conditional_gaps=conditional,
        important_gaps=important,
        evidence_deficiencies=evidence,
        incomplete_records=incomplete,
        manual_review_items=manual,
        validation=validation,
    )


def legacy_critical_control_profile(requirements: pd.DataFrame) -> pd.DataFrame:
    """Build a compatibility profile that reproduces the former boolean behavior."""
    flags = requirements.get("critical_control", pd.Series(False, index=requirements.index))
    if flags.dtype == bool:
        critical = flags.fillna(False)
    else:
        critical = flags.astype("string").str.strip().str.lower().isin(["true", "1", "yes", "y", "critical"])
    maximum = pd.to_numeric(
        requirements.get("maximum_score", pd.Series(np.nan, index=requirements.index)), errors="coerce"
    )
    explicit_threshold = pd.to_numeric(requirements.get("critical_threshold", maximum), errors="coerce")
    return pd.DataFrame(
        {
            "requirement_id": requirements.get(
                "requirement_id",
                pd.Series([f"R{i:03d}" for i in range(1, len(requirements) + 1)], index=requirements.index),
            ),
            "criticality_level": np.where(critical, "Deployment-blocking", "Non-critical"),
            "failure_disposition": np.where(critical, "DO NOT DEPLOY", "NO AUTOMATIC OVERRIDE"),
            "minimum_acceptable_score": np.where(critical, explicit_threshold, 0),
            "evidence_required": critical,
            "incomplete_record_disposition": np.where(critical, "DO NOT DEPLOY", "NO AUTOMATIC OVERRIDE"),
            "rationale": np.where(
                critical,
                "Backward-compatible profile derived from the existing critical_control flag.",
                "Backward-compatible non-critical profile row.",
            ),
            "approval_status": "Backward-compatible software behavior",
            "source_status": "Generated legacy critical-control profile",
        }
    )


def critical_control_summary_table(assessment: CriticalControlAssessment) -> pd.DataFrame:
    """Return a stable two-column summary for CSV and Excel exports."""
    summary = assessment.summary
    rows: list[dict[str, object]] = [
        {"metric": "critical_control_profile_status", "value": summary["critical_control_profile_status"]}
    ]
    rows.extend(
        {"metric": f"criticality_level_{level}", "value": count}
        for level, count in summary["criticality_level_counts"].items()
    )
    rows.extend(
        {"metric": f"critical_control_outcome_{outcome}", "value": count}
        for outcome, count in summary["critical_control_outcome_counts"].items()
    )
    for key in (
        "deployment_blocking_failure_count",
        "conditional_gap_count",
        "important_gap_count",
        "evidence_deficiency_count",
        "incomplete_critical_record_count",
        "manual_review_count",
        "formal_approval_required_count",
        "compensating_control_required_count",
    ):
        rows.append({"metric": key, "value": summary[key]})
    for key in (
        "blocking_requirement_ids",
        "conditional_requirement_ids",
        "important_gap_requirement_ids",
        "evidence_deficient_requirement_ids",
        "manual_review_requirement_ids",
    ):
        rows.append({"metric": key, "value": ", ".join(summary[key])})
    rows.append({"metric": "critical_control_limitations", "value": CRITICAL_CONTROL_LIMITATION})
    return pd.DataFrame(rows)


def validate_critical_control_profile(
    profile: pd.DataFrame,
    requirements: pd.DataFrame,
) -> CriticalControlProfileValidationResult:
    """Validate profiles using the common structured-finding model."""
    collector = FindingCollector("Critical-Control Profile")
    data = profile.copy()
    original_columns = [str(column) for column in data.columns]
    normalized_bases = [column.strip().lower().replace(" ", "_").replace("-", "_") for column in original_columns]
    used: dict[str, int] = {}
    normalized_columns: list[str] = []
    for name in normalized_bases:
        used[name] = used.get(name, 0) + 1
        normalized_columns.append(name if used[name] == 1 else f"{name}_{used[name]}")
    data.columns = normalized_columns
    duplicate_headers = sorted({name for name in normalized_bases if normalized_bases.count(name) > 1})
    if duplicate_headers:
        collector.add(
            "Warning",
            "DUPLICATE_NORMALIZED_COLUMN",
            f"Critical-Control Profile: headers become duplicates after normalization: {', '.join(duplicate_headers)}.",
            original_value=original_columns,
            normalized_value=normalized_columns,
            suggested_action="Rename ambiguous source columns.",
        )
    if data.empty:
        collector.add(
            "Error",
            "EMPTY_DATASET",
            "Critical-Control Profile: the dataset contains no rows.",
            suggested_action="Provide one profile row for every requirement.",
            blocks_analysis=True,
        )
    if len(data.columns) and not set(PROFILE_REQUIRED_COLUMNS).intersection(data.columns):
        collector.add(
            "Error",
            "UNRECOGNIZED_DATASET_TYPE",
            "Critical-Control Profile: no recognizable profile columns were found; this may be an instruction or cover sheet.",
            original_value=list(data.columns),
            suggested_action="Select the worksheet containing the profile table.",
            blocks_analysis=True,
        )
    blank_rows = (
        data.apply(lambda row: all(pd.isna(value) or str(value).strip() == "" for value in row), axis=1)
        if len(data.columns)
        else pd.Series(True, index=data.index)
    )
    for index in data.index[blank_rows]:
        collector.add(
            "Error",
            "COMPLETELY_BLANK_ROW",
            f"Critical-Control Profile: row {index + 2} is completely blank.",
            row_index=index,
            suggested_action="Remove the blank row or populate the complete profile record.",
            blocks_analysis=True,
        )
    for column in data.columns:
        if data[column].map(lambda value: pd.isna(value) or str(value).strip() == "").all():
            collector.add(
                "Warning",
                "COMPLETELY_BLANK_COLUMN",
                f"Critical-Control Profile: column {column!r} is completely blank.",
                column=column,
                suggested_action="Remove the unused column or populate it if required.",
            )
    missing_columns = [column for column in PROFILE_REQUIRED_COLUMNS if column not in data.columns]
    for column in missing_columns:
        collector.add(
            "Error",
            "MISSING_REQUIRED_COLUMN",
            f"Critical-Control Profile: required column {column!r} is missing.",
            column=column,
            suggested_action=f"Add the required {column} column.",
            blocks_analysis=True,
        )
    if missing_columns:
        eligible = pd.Series(False, index=data.index)
        data = apply_validation_fields(
            data,
            collector.findings,
            analysis_eligible=eligible,
            record_id_column="requirement_id",
            exclusion_reasons={int(index): ["Missing required profile columns."] for index in data.index},
        )
        return CriticalControlProfileValidationResult(
            data=data,
            findings=collector.findings,
            missing_columns=missing_columns,
            invalid_rows=data.index.tolist(),
        )

    for column in PROFILE_REQUIRED_COLUMNS:
        data[f"{column}_raw"] = data[column]
    data["requirement_id"] = data["requirement_id"].astype("string").str.strip()
    row_eligible = pd.Series(True, index=data.index, dtype=bool) & ~blank_rows
    for index, raw in data["requirement_id_raw"].items():
        normalized = data.at[index, "requirement_id"]
        if not pd.isna(raw) and str(raw) != str(raw).strip():
            collector.add(
                "Warning",
                "TRAILING_OR_LEADING_WHITESPACE",
                f"Critical-Control Profile: requirement_id={raw!r} contains surrounding whitespace.",
                row_index=index,
                record_id=normalized,
                column="requirement_id",
                original_value=raw,
                normalized_value=normalized,
                suggested_action="Remove surrounding whitespace from the profile identifier.",
            )
        if pd.isna(normalized) or str(normalized) == "":
            row_eligible.loc[index] = False
            collector.add(
                "Error",
                "BLANK_ID",
                f"Critical-Control Profile: row {index + 2} has a blank requirement_id.",
                row_index=index,
                column="requirement_id",
                original_value=raw,
                suggested_action="Provide an existing requirement_id.",
                blocks_analysis=True,
            )
    duplicate_mask = (
        data["requirement_id"].notna() & data["requirement_id"].ne("") & data["requirement_id"].duplicated(keep=False)
    )
    duplicate_ids = sorted(data.loc[duplicate_mask, "requirement_id"].astype(str).unique())
    for index in data.index[duplicate_mask]:
        row_eligible.loc[index] = False
        collector.add(
            "Error",
            "DUPLICATE_PROFILE_ROW",
            f"Critical-Control Profile: requirement {data.at[index, 'requirement_id']} appears more than once.",
            row_index=index,
            record_id=data.at[index, "requirement_id"],
            column="requirement_id",
            original_value=data.at[index, "requirement_id_raw"],
            suggested_action="Keep exactly one profile row per requirement.",
            blocks_analysis=True,
        )

    requirement_ids = set(requirements.get("requirement_id", pd.Series(dtype=str)).dropna().astype(str).str.strip())
    profile_ids = set(data["requirement_id"].dropna().astype(str)) - {""}
    missing_requirement_ids = sorted(requirement_ids - profile_ids)
    unknown_requirement_ids = sorted(profile_ids - requirement_ids)
    for requirement_id in missing_requirement_ids:
        collector.add(
            "Error",
            "MISSING_PROFILE_ROW",
            f"Critical-Control Profile: requirement {requirement_id} has no profile row.",
            record_id=requirement_id,
            column="requirement_id",
            suggested_action="Add exactly one profile row for this requirement.",
            blocks_analysis=True,
        )
    for requirement_id in unknown_requirement_ids:
        indexes = data.index[data["requirement_id"].eq(requirement_id)]
        for index in indexes:
            row_eligible.loc[index] = False
            collector.add(
                "Error",
                "UNKNOWN_REQUIREMENT_ID",
                f"Critical-Control Profile: requirement_id {requirement_id} does not exist in the requirements dataset.",
                row_index=index,
                record_id=requirement_id,
                column="requirement_id",
                original_value=data.at[index, "requirement_id_raw"],
                suggested_action="Use an existing exact requirement_id.",
                blocks_analysis=True,
            )

    for column, allowed, code in (
        ("criticality_level", set(CRITICALITY_LEVELS), "INVALID_CRITICALITY_LEVEL"),
        ("failure_disposition", set(FAILURE_DISPOSITIONS), "INVALID_FAILURE_DISPOSITION"),
        ("incomplete_record_disposition", set(INCOMPLETE_RECORD_DISPOSITIONS), "INVALID_INCOMPLETE_DISPOSITION"),
    ):
        data[column] = data[column].astype("string").str.strip()
        invalid = ~data[column].isin(allowed)
        for index in data.index[invalid]:
            row_eligible.loc[index] = False
            collector.add(
                "Error",
                code,
                f"Critical-Control Profile: {column}={data.at[index, column]!r} is invalid for {data.at[index, 'requirement_id']}.",
                row_index=index,
                record_id=data.at[index, "requirement_id"],
                column=column,
                original_value=data.at[index, f"{column}_raw"],
                normalized_value=data.at[index, column],
                suggested_action=f"Use one of: {', '.join(sorted(allowed))}.",
                blocks_analysis=True,
            )

    threshold = pd.to_numeric(data["minimum_acceptable_score_raw"], errors="coerce")
    data["minimum_acceptable_score"] = threshold
    invalid_threshold = (
        threshold.isna() | ~np.isfinite(threshold) | (threshold < 0) | (threshold > 5) | (threshold % 1 != 0)
    )
    for index in data.index[invalid_threshold]:
        row_eligible.loc[index] = False
        collector.add(
            "Error",
            "INVALID_THRESHOLD",
            f"Critical-Control Profile: invalid minimum_acceptable_score={data.at[index, 'minimum_acceptable_score_raw']!r} for {data.at[index, 'requirement_id']}.",
            row_index=index,
            record_id=data.at[index, "requirement_id"],
            column="minimum_acceptable_score",
            original_value=data.at[index, "minimum_acceptable_score_raw"],
            normalized_value=threshold.loc[index],
            suggested_action="Use an integer threshold from 0 to 5.",
            blocks_analysis=True,
        )
    maxima = (
        requirements[["requirement_id", "maximum_score"]].copy()
        if {"requirement_id", "maximum_score"}.issubset(requirements.columns)
        else pd.DataFrame(columns=["requirement_id", "maximum_score"])
    )
    maximum_map = maxima.set_index("requirement_id")["maximum_score"] if not maxima.empty else pd.Series(dtype=float)
    for index, row in data.iterrows():
        requirement_id = row["requirement_id"]
        maximum = pd.to_numeric(pd.Series([maximum_map.get(requirement_id)]), errors="coerce").iloc[0]
        if (
            pd.notna(row["minimum_acceptable_score"])
            and pd.notna(maximum)
            and row["minimum_acceptable_score"] > maximum
        ):
            row_eligible.loc[index] = False
            collector.add(
                "Error",
                "THRESHOLD_EXCEEDS_MAXIMUM",
                f"Critical-Control Profile: threshold {row['minimum_acceptable_score']:g} exceeds maximum score {maximum:g} for {requirement_id}.",
                row_index=index,
                record_id=requirement_id,
                column="minimum_acceptable_score",
                original_value=row["minimum_acceptable_score_raw"],
                normalized_value=row["minimum_acceptable_score"],
                suggested_action="Set the threshold at or below the requirement maximum.",
                blocks_analysis=True,
            )
        if (
            row["criticality_level"] == "Deployment-blocking"
            and pd.notna(row["minimum_acceptable_score"])
            and row["minimum_acceptable_score"] < 5
        ):
            collector.add(
                "Warning",
                "UNEXPECTEDLY_LOW_BLOCKING_THRESHOLD",
                f"Critical-Control Profile: Deployment-blocking requirement {requirement_id} uses threshold {row['minimum_acceptable_score']:g}/5.",
                row_index=index,
                record_id=requirement_id,
                column="minimum_acceptable_score",
                original_value=row["minimum_acceptable_score_raw"],
                normalized_value=row["minimum_acceptable_score"],
                suggested_action="Document why a Deployment-blocking control may pass below full implementation.",
            )

    evidence_text = data["evidence_required_raw"].astype("string").str.strip().str.lower()
    true_values, false_values = {"true", "1", "yes", "y", "t"}, {"false", "0", "no", "n", "f"}
    valid_evidence_boolean = evidence_text.isin(true_values | false_values)
    parsed_evidence = evidence_text.isin(true_values)
    for index in data.index[~valid_evidence_boolean]:
        row_eligible.loc[index] = False
        collector.add(
            "Error",
            "INVALID_BOOLEAN",
            f"Critical-Control Profile: evidence_required={data.at[index, 'evidence_required_raw']!r} is invalid for {data.at[index, 'requirement_id']}.",
            row_index=index,
            record_id=data.at[index, "requirement_id"],
            column="evidence_required",
            original_value=data.at[index, "evidence_required_raw"],
            suggested_action="Use TRUE/FALSE, yes/no, y/n, or 1/0.",
            blocks_analysis=True,
        )
    data["evidence_required"] = parsed_evidence

    for column, code in (
        ("rationale", "MISSING_RATIONALE"),
        ("approval_status", "MISSING_APPROVAL_STATUS"),
        ("source_status", "MISSING_SOURCE_STATUS"),
    ):
        data[column] = data[column].astype("string").str.strip()
        blank = (
            data[column].isna() | data[column].eq("") | data[column].str.lower().isin(["nan", "none", "not provided"])
        )
        for index in data.index[blank]:
            row_eligible.loc[index] = False
            collector.add(
                "Error",
                code,
                f"Critical-Control Profile: blank {column} for {data.at[index, 'requirement_id']}.",
                row_index=index,
                record_id=data.at[index, "requirement_id"],
                column=column,
                original_value=data.at[index, f"{column}_raw"],
                suggested_action=f"Provide a transparent {column.replace('_', ' ')}.",
                blocks_analysis=True,
            )
    noncritical_block = data["criticality_level"].eq("Non-critical") & data["failure_disposition"].eq("DO NOT DEPLOY")
    for index in data.index[noncritical_block]:
        row_eligible.loc[index] = False
        collector.add(
            "Error",
            "NONCRITICAL_BLOCKING_DISPOSITION",
            f"Critical-Control Profile: Non-critical requirement(s) cannot use DO NOT DEPLOY; affected ID: {data.at[index, 'requirement_id']}.",
            row_index=index,
            record_id=data.at[index, "requirement_id"],
            column="failure_disposition",
            original_value=data.at[index, "failure_disposition_raw"],
            suggested_action="Use NO AUTOMATIC OVERRIDE for a Non-critical requirement or change the documented criticality.",
            blocks_analysis=True,
        )
    exclusion = {
        int(index): ["Critical-control profile row has one or more blocking validation findings."]
        for index in data.index[~row_eligible]
    }
    data = apply_validation_fields(
        data,
        collector.findings,
        analysis_eligible=row_eligible,
        record_id_column="requirement_id",
        exclusion_reasons=exclusion,
    )
    return CriticalControlProfileValidationResult(
        data=data,
        findings=collector.findings,
        missing_columns=missing_columns,
        duplicate_ids=duplicate_ids,
        missing_requirement_ids=missing_requirement_ids,
        unknown_requirement_ids=unknown_requirement_ids,
        invalid_rows=sorted(int(index) for index in data.index[~row_eligible]),
    )
