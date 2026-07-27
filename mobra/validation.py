"""Schema mapping and validation for hazard and ORL requirement data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

import numpy as np
import pandas as pd

from .config import RISK_LEVELS, count_phrase
from .risk import calculate_risk_score, classify_risk, valid_scale


HAZARD_REQUIRED_FIELDS = ["hazard", "likelihood", "consequence"]
REQUIREMENT_REQUIRED_FIELDS = ["requirement", "observed_score", "maximum_score"]


@dataclass
class ValidationResult:
    """Validated data plus user-facing diagnostics."""

    data: pd.DataFrame
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    missing_columns: list[str] = field(default_factory=list)
    duplicate_ids: list[str] = field(default_factory=list)
    invalid_rows: list[int] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def all_messages(self) -> list[str]:
        return [*self.errors, *self.warnings]

    def __iter__(self):
        """Allow legacy ``validated, errors = validate_*`` unpacking."""
        yield self.data
        yield self.errors

    @property
    def quality(self) -> dict[str, int | float]:
        rows = len(self.data)
        missing = int(self.data.isna().sum().sum()) if rows else 0
        return {
            "rows": rows,
            "columns": len(self.data.columns),
            "missing_values": missing,
            "duplicate_ids": len(self.duplicate_ids),
            "invalid_rows": len(self.invalid_rows),
            "missing_value_pct": round(100 * missing / max(rows * max(len(self.data.columns), 1), 1), 2),
        }


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize headers to portable snake_case names."""
    out = df.copy()
    names: list[str] = []
    used: dict[str, int] = {}
    for raw in out.columns:
        name = str(raw).strip().lower()
        name = "".join(char if (char.isascii() and char.isalnum()) else "_" for char in name)
        name = name.strip("_") or "unnamed"
        used[name] = used.get(name, 0) + 1
        names.append(name if used[name] == 1 else f"{name}_{used[name]}")
    out.columns = names
    return out


HAZARD_ALIASES = {
    "hazard_id": ["hazard_id", "id", "risk_id", "incident_id", "event_id"],
    "hazard": ["hazard", "hazard_name", "risk", "description", "hazard_description"],
    "hazard_category": ["hazard_category", "category", "incident_type", "event_type"],
    "domain": ["domain", "operational_domain"],
    "activity": ["activity", "operational_activity", "laboratory_activity"],
    "biological_agent": ["biological_agent", "agent", "pathogen", "organism"],
    "cause": ["cause", "root_cause", "mechanism", "exposure_mechanism"],
    "existing_controls": ["existing_controls", "controls", "control_measures"],
    "likelihood": ["likelihood", "l", "probability"],
    "consequence": ["consequence", "c", "severity", "impact"],
    "risk_score": ["risk_score", "initial_risk_score"],
    "risk_category": ["risk_category", "risk_level", "initial_risk_category"],
    "residual_likelihood": ["residual_likelihood", "post_control_likelihood"],
    "residual_consequence": ["residual_consequence", "post_control_consequence"],
    "objective_evidence": ["objective_evidence", "evidence", "evidence_description"],
    "related_requirement": ["related_requirement", "requirement_id", "related_control"],
    "corrective_action": ["corrective_action", "recommended_action", "action"],
    "responsible_person": ["responsible_person", "responsible", "owner", "assignee"],
    "status": ["status", "action_status", "outcome"],
    "due_date": ["due_date", "target_date", "action_due_date"],
}

REQUIREMENT_ALIASES = {
    "requirement_id": ["requirement_id", "id", "orl_id", "control_id"],
    "requirement": ["requirement", "requirement_text", "item", "control", "description"],
    "domain": ["domain", "operational_domain"],
    "lifecycle_stage": ["lifecycle_stage", "stage", "mission_stage"],
    "objective_evidence": ["objective_evidence", "evidence", "evidence_description"],
    "observed_score": ["observed_score", "observed", "score", "actual_score"],
    "maximum_score": ["maximum_score", "maximum", "max_score", "possible_score"],
    "critical_control": ["critical_control", "mission_critical", "critical", "is_critical"],
    "compliance_status": ["compliance_status", "status", "compliance"],
    "corrective_action": ["corrective_action", "recommended_action", "action"],
    "responsible_person": ["responsible_person", "responsible", "owner", "assignee"],
    "due_date": ["due_date", "target_date", "action_due_date"],
    "critical_threshold": ["critical_threshold", "accepted_threshold", "minimum_score"],
    "notes": ["notes", "comments", "assessment_notes"],
}


def suggest_column_mapping(
    df: pd.DataFrame,
    kind: str,
) -> pd.DataFrame:
    """Return deterministic alias matches with confidence and required status."""
    if kind not in {"hazards", "requirements"}:
        raise ValueError("kind must be 'hazards' or 'requirements'.")
    aliases = HAZARD_ALIASES if kind == "hazards" else REQUIREMENT_ALIASES
    required = HAZARD_REQUIRED_FIELDS if kind == "hazards" else REQUIREMENT_REQUIRED_FIELDS
    normalized = normalise_columns(df)
    rows: list[dict[str, object]] = []
    for target, candidates in aliases.items():
        match = target if target in normalized.columns else next(
            (candidate for candidate in candidates if candidate in normalized.columns),
            None,
        )
        if match == target:
            confidence, status = 100, "Matched"
        elif match:
            confidence, status = 90, "Matched"
        elif target in required:
            confidence, status = 0, "Missing"
        else:
            confidence, status = 0, "Optional"
        rows.append(
            {
                "standard_field": target,
                "detected_source_column": match or "",
                "confidence_pct": confidence,
                "mapping_status": status,
                "required": target in required,
            }
        )
    return pd.DataFrame(rows)


def _apply_aliases(df: pd.DataFrame, aliases: Mapping[str, list[str]], overrides: Mapping[str, str] | None) -> pd.DataFrame:
    out = normalise_columns(df)
    overrides = overrides or {}
    rename: dict[str, str] = {}
    for target, options in aliases.items():
        requested = overrides.get(target)
        if requested and requested in out.columns:
            rename[requested] = target
            continue
        if target in out.columns:
            continue
        found = next((candidate for candidate in options if candidate in out.columns), None)
        if found:
            rename[found] = target
    return out.rename(columns=rename)


def _duplicate_ids(df: pd.DataFrame, column: str) -> list[str]:
    if column not in df.columns:
        return []
    values = df[column].astype("string").str.strip()
    return sorted(values[values.notna() & values.duplicated(keep=False)].dropna().unique().tolist())


def _blank_ids(df: pd.DataFrame, column: str) -> int:
    if column not in df.columns:
        return 0
    values = df[column].astype("string").str.strip()
    return int(values.isna().sum() + values.eq("").sum())


def _parse_dates(df: pd.DataFrame, result: ValidationResult) -> None:
    if "due_date" not in df.columns:
        return
    raw = df["due_date"]
    parsed = pd.to_datetime(raw, errors="coerce")
    invalid = raw.notna() & parsed.isna() & raw.astype(str).str.strip().ne("")
    if invalid.any():
        count = int(invalid.sum())
        result.warnings.append(
            f"{count_phrase(count, 'due-date value')} could not be parsed and "
            f"{'was' if count == 1 else 'were'} left blank."
        )
    df["due_date"] = parsed.dt.strftime("%Y-%m-%d")
    df.loc[parsed.isna(), "due_date"] = pd.NA
    df["overdue"] = parsed.notna() & (parsed.dt.normalize() < pd.Timestamp.now().normalize())


def validate_hazards(df: pd.DataFrame, overrides: Mapping[str, str] | None = None) -> ValidationResult:
    """Map and validate hazard records; invalid rows remain visible but are not analyzable."""
    out = _apply_aliases(df, HAZARD_ALIASES, overrides)
    result = ValidationResult(out)
    required = HAZARD_REQUIRED_FIELDS
    result.missing_columns = [column for column in required if column not in out.columns]
    if result.missing_columns:
        result.errors.append(f"Missing required hazard columns: {', '.join(result.missing_columns)}.")
        return result
    if "hazard_id" not in out.columns:
        out.insert(0, "hazard_id", [f"H{i:03d}" for i in range(1, len(out) + 1)])
        result.warnings.append("hazard_id was not supplied; stable row-based IDs were generated.")
    result.duplicate_ids = _duplicate_ids(out, "hazard_id")
    if result.duplicate_ids:
        result.errors.append(f"Duplicate hazard_id values: {', '.join(result.duplicate_ids)}.")
    blank_ids = _blank_ids(out, "hazard_id")
    if blank_ids:
        result.errors.append(
            f"{count_phrase(blank_ids, 'hazard_id value')} "
            f"{'is' if blank_ids == 1 else 'are'} blank."
        )

    for column in ("likelihood", "consequence"):
        numeric = pd.to_numeric(out[column], errors="coerce")
        out[column] = numeric
        invalid = ~numeric.map(valid_scale)
        if invalid.any():
            result.invalid_rows.extend(out.index[invalid].tolist())
            count = int(invalid.sum())
            result.errors.append(
                f"{count_phrase(count, f'invalid {column!r} value')}; "
                "use integer values from 1 to 5."
            )
    out["risk_score"] = calculate_risk_score(out["likelihood"], out["consequence"])
    valid_risk = out["likelihood"].map(valid_scale) & out["consequence"].map(valid_scale)
    out.loc[~valid_risk, "risk_score"] = np.nan
    out["risk_category"] = out["risk_score"].map(classify_risk)
    out["risk_level"] = out["risk_category"]
    out["risk_value_source"] = "Calculated from likelihood × consequence"

    for optional in (
        "hazard_category",
        "domain",
        "activity",
        "biological_agent",
        "cause",
        "existing_controls",
        "corrective_action",
        "responsible_person",
        "status",
        "objective_evidence",
        "related_requirement",
    ):
        if optional not in out.columns:
            out[optional] = "Not provided"
    residual_present = {"residual_likelihood", "residual_consequence"}.intersection(out.columns)
    residual_valid = pd.Series(False, index=out.index)
    if residual_present and residual_present != {"residual_likelihood", "residual_consequence"}:
        result.warnings.append("Only one residual-risk field was supplied; residual risk was not calculated.")
    if residual_present == {"residual_likelihood", "residual_consequence"}:
        for column in ("residual_likelihood", "residual_consequence"):
            numeric = pd.to_numeric(out[column], errors="coerce")
            out[column] = numeric
            invalid = numeric.notna() & ~numeric.map(valid_scale)
            if invalid.any():
                count = int(invalid.sum())
                result.errors.append(
                    f"{count_phrase(count, f'invalid {column!r} value')}; "
                    "use integers from 1 to 5."
                )
                result.invalid_rows.extend(out.index[invalid].tolist())
        incomplete_pair = (
            out["residual_likelihood"].notna()
            ^ out["residual_consequence"].notna()
        )
        if incomplete_pair.any():
            count = int(incomplete_pair.sum())
            result.warnings.append(
                f"{count_phrase(count, 'residual-risk pair')} "
                f"{'is' if count == 1 else 'are'} incomplete; "
                "the initial calculated risk is used for those records."
            )
        residual_valid = out["residual_likelihood"].map(valid_scale) & out["residual_consequence"].map(valid_scale)
        out["residual_risk_score"] = calculate_risk_score(out["residual_likelihood"], out["residual_consequence"])
        out.loc[~residual_valid, "residual_risk_score"] = np.nan
        out["residual_risk_category"] = out["residual_risk_score"].map(classify_risk)
    else:
        out["residual_risk_score"] = np.nan
        out["residual_risk_category"] = "Not provided"
    out["decision_risk_score"] = out["residual_risk_score"].where(
        residual_valid,
        out["risk_score"],
    )
    out["decision_risk_category"] = out["residual_risk_category"].where(
        out["residual_risk_category"].isin(RISK_LEVELS),
        out["risk_category"],
    )
    out["decision_risk_source"] = np.where(
        residual_valid,
        "Residual risk",
        "Initial calculated risk",
    )
    _parse_dates(out, result)
    result.data = out
    result.invalid_rows = sorted(set(result.invalid_rows))
    return result


def _parse_boolean(series: pd.Series, result: ValidationResult) -> pd.Series:
    normalized = series.astype("string").str.strip().str.lower()
    true_values = {"true", "1", "yes", "y", "t", "critical"}
    false_values = {"false", "0", "no", "n", "f", "not critical", ""}
    unknown = series.notna() & ~normalized.isin(true_values | false_values)
    if unknown.any():
        count = int(unknown.sum())
        result.invalid_rows.extend(series.index[unknown].tolist())
        result.errors.append(
            f"{count_phrase(count, 'critical-control flag')} "
            f"{'was' if count == 1 else 'were'} not recognized; "
            "use true/false, yes/no, or 1/0."
        )
    return normalized.isin(true_values)


def validate_requirements(df: pd.DataFrame, overrides: Mapping[str, str] | None = None) -> ValidationResult:
    """Map and validate ORL requirement records and derive readiness fields."""
    out = _apply_aliases(df, REQUIREMENT_ALIASES, overrides)
    result = ValidationResult(out)
    required = REQUIREMENT_REQUIRED_FIELDS
    result.missing_columns = [column for column in required if column not in out.columns]
    if result.missing_columns:
        result.errors.append(f"Missing required requirement columns: {', '.join(result.missing_columns)}.")
        return result
    if "requirement_id" not in out.columns:
        out.insert(0, "requirement_id", [f"R{i:03d}" for i in range(1, len(out) + 1)])
        result.warnings.append("requirement_id was not supplied; stable row-based IDs were generated.")
    result.duplicate_ids = _duplicate_ids(out, "requirement_id")
    if result.duplicate_ids:
        result.errors.append(f"Duplicate requirement_id values: {', '.join(result.duplicate_ids)}.")
    blank_ids = _blank_ids(out, "requirement_id")
    if blank_ids:
        result.errors.append(
            f"{count_phrase(blank_ids, 'requirement_id value')} "
            f"{'is' if blank_ids == 1 else 'are'} blank."
        )

    observed = pd.to_numeric(out["observed_score"], errors="coerce")
    maximum = pd.to_numeric(out["maximum_score"], errors="coerce")
    out["observed_score"], out["maximum_score"] = observed, maximum
    invalid = observed.isna() | maximum.isna() | (maximum <= 0) | (observed < 0) | (observed > maximum)
    if invalid.any():
        result.invalid_rows.extend(out.index[invalid].tolist())
        count = int(invalid.sum())
        result.errors.append(
            f"{count_phrase(count, 'invalid requirement row')}: observed must be "
            "≥0, observed ≤ maximum, and maximum >0."
        )
    out["item_readiness_pct"] = 100 * observed / maximum
    out.loc[invalid, "item_readiness_pct"] = np.nan
    if "domain" not in out.columns:
        out["domain"] = "General"
    if "objective_evidence" not in out.columns:
        out["objective_evidence"] = pd.NA
        result.warnings.append("objective_evidence/evidence was not supplied; missing evidence is reported.")
    if "critical_control" not in out.columns:
        out["critical_control"] = False
        result.warnings.append("critical_control was not supplied; all controls were treated as non-critical.")
    else:
        blank = out["critical_control"].isna() | out["critical_control"].astype(str).str.strip().eq("")
        if blank.any():
            count = int(blank.sum())
            result.warnings.append(
                f"{count_phrase(count, 'critical-control flag')} "
                f"{'is' if count == 1 else 'are'} blank and treated as false."
            )
        out["critical_control"] = _parse_boolean(out["critical_control"], result)
    out["evidence_missing"] = out["objective_evidence"].isna() | out["objective_evidence"].astype(str).str.strip().isin(["", "nan", "none", "not provided"])
    out["incomplete"] = invalid | out["evidence_missing"]
    calculated_status = pd.Series(
        np.where(
            out["incomplete"],
            "Incomplete",
            np.where(
                out["observed_score"] < out["maximum_score"],
                "Below threshold",
                "Compliant",
            ),
        ),
        index=out.index,
        dtype="string",
    )
    if "compliance_status" in out.columns:
        reported_status = out["compliance_status"].copy()
        out["reported_compliance_status"] = reported_status
        meaningful = (
            reported_status.notna()
            & reported_status.astype("string").str.strip().ne("")
        )
        conflicts = meaningful & (
            reported_status.astype("string").str.strip().str.casefold()
            != calculated_status.str.casefold()
        )
        if conflicts.any():
            count = int(conflicts.sum())
            result.warnings.append(
                f"{count_phrase(count, 'reported compliance status')} "
                f"{'differs' if count == 1 else 'differ'} from the validated "
                "score/evidence result; the calculated status is used for analysis."
            )
    out["compliance_status"] = calculated_status
    for optional in ("corrective_action", "responsible_person", "lifecycle_stage", "notes"):
        if optional not in out.columns:
            out[optional] = "Not provided"
    if "critical_threshold" in out.columns:
        raw_threshold = out["critical_threshold"].copy()
        threshold = pd.to_numeric(raw_threshold, errors="coerce")
        supplied = (
            raw_threshold.notna()
            & raw_threshold.astype("string").str.strip().ne("")
        )
        invalid_threshold = supplied & (
            threshold.isna()
            | maximum.isna()
            | (threshold <= 0)
            | (threshold > maximum)
        )
        if invalid_threshold.any():
            count = int(invalid_threshold.sum())
            result.invalid_rows.extend(out.index[invalid_threshold].tolist())
            result.errors.append(
                f"{count_phrase(count, 'invalid critical threshold')}; "
                "use a numeric value greater than 0 and no greater than maximum_score."
            )
        out["critical_threshold"] = threshold
    else:
        out["critical_threshold"] = out["maximum_score"]
    _parse_dates(out, result)
    result.data = out
    result.invalid_rows = sorted(set(result.invalid_rows))
    return result


def validation_issue_table(
    hazard_result: ValidationResult,
    requirement_result: ValidationResult,
) -> pd.DataFrame:
    """Convert validation diagnostics into a grouped, exportable issue register."""
    records: list[dict[str, str]] = []
    for dataset, result in (
        ("Hazard Register", hazard_result),
        ("Requirements", requirement_result),
    ):
        for severity, messages in (
            ("Error", result.errors),
            ("Warning", result.warnings),
        ):
            for message in messages:
                recommended_fix = (
                    "Open Column Mapping and select the corresponding source column."
                    if "missing required" in message.lower()
                    else "Review the identified source records, correct the values, and validate again."
                )
                records.append(
                    {
                        "issue_type": "Schema or data quality",
                        "dataset": dataset,
                        "location": (
                            ", ".join(str(row + 2) for row in result.invalid_rows[:20])
                            if result.invalid_rows
                            else "Dataset"
                        ),
                        "cause": message,
                        "severity": severity,
                        "recommended_fix": recommended_fix,
                    }
                )
    if not records:
        records.append(
            {
                "issue_type": "Validation status",
                "dataset": "All active data",
                "location": "Dataset",
                "cause": "No validation errors or warnings were detected.",
                "severity": "Information",
                "recommended_fix": "No action is required.",
            }
        )
    return pd.DataFrame(records)
