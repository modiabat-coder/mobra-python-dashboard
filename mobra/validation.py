"""Schema mapping and validation for hazard and ORL requirement data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

import numpy as np
import pandas as pd

from .risk import calculate_risk_score, classify_risk, valid_scale


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
    "corrective_action": ["corrective_action", "recommended_action", "action"],
    "responsible_person": ["responsible_person", "responsible", "owner", "assignee"],
    "status": ["status", "action_status", "outcome"],
    "due_date": ["due_date", "target_date", "action_due_date"],
}

REQUIREMENT_ALIASES = {
    "requirement_id": ["requirement_id", "id", "orl_id", "control_id"],
    "requirement": ["requirement", "requirement_text", "item", "control", "description"],
    "domain": ["domain", "operational_domain"],
    "objective_evidence": ["objective_evidence", "evidence", "evidence_description"],
    "observed_score": ["observed_score", "observed", "score", "actual_score"],
    "maximum_score": ["maximum_score", "maximum", "max_score", "possible_score"],
    "critical_control": ["critical_control", "mission_critical", "critical", "is_critical"],
    "compliance_status": ["compliance_status", "status", "compliance"],
    "corrective_action": ["corrective_action", "recommended_action", "action"],
    "responsible_person": ["responsible_person", "responsible", "owner", "assignee"],
    "due_date": ["due_date", "target_date", "action_due_date"],
    "critical_threshold": ["critical_threshold", "accepted_threshold", "minimum_score"],
}


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
        result.warnings.append(f"{int(invalid.sum())} due-date value(s) could not be parsed and were left blank.")
    df["due_date"] = parsed.dt.strftime("%Y-%m-%d")
    df.loc[parsed.isna(), "due_date"] = pd.NA
    df["overdue"] = parsed.notna() & (parsed.dt.normalize() < pd.Timestamp.now().normalize())


def validate_hazards(df: pd.DataFrame, overrides: Mapping[str, str] | None = None) -> ValidationResult:
    """Map and validate hazard records; invalid rows remain visible but are not analyzable."""
    out = _apply_aliases(df, HAZARD_ALIASES, overrides)
    result = ValidationResult(out)
    required = ["hazard", "likelihood", "consequence"]
    result.missing_columns = [column for column in required if column not in out.columns]
    if result.missing_columns:
        result.errors.append(f"Missing required hazard columns: {', '.join(result.missing_columns)}.")
        return result
    if "hazard_id" not in out.columns:
        out.insert(0, "hazard_id", [f"H{i:03d}" for i in range(1, len(out) + 1)])
        result.warnings.append("hazard_id was not supplied; stable row-based IDs were generated.")
    result.duplicate_ids = _duplicate_ids(out, "hazard_id")
    if result.duplicate_ids:
        result.errors.append(f"Duplicate hazard_id value(s): {', '.join(result.duplicate_ids)}.")
    blank_ids = _blank_ids(out, "hazard_id")
    if blank_ids:
        result.errors.append(f"{blank_ids} hazard_id value(s) are blank.")

    for column in ("likelihood", "consequence"):
        numeric = pd.to_numeric(out[column], errors="coerce")
        out[column] = numeric
        invalid = ~numeric.map(valid_scale)
        if invalid.any():
            result.invalid_rows.extend(out.index[invalid].tolist())
            result.errors.append(f"{int(invalid.sum())} invalid '{column}' value(s); use integer values from 1 to 5.")
    out["risk_score"] = calculate_risk_score(out["likelihood"], out["consequence"])
    valid_risk = out["likelihood"].map(valid_scale) & out["consequence"].map(valid_scale)
    out.loc[~valid_risk, "risk_score"] = np.nan
    out["risk_category"] = out["risk_score"].map(classify_risk)
    out["risk_level"] = out["risk_category"]
    out["risk_value_source"] = "Calculated from likelihood × consequence"

    for optional in ("hazard_category", "domain", "activity", "biological_agent", "cause", "existing_controls", "corrective_action", "responsible_person", "status"):
        if optional not in out.columns:
            out[optional] = "Not provided"
    residual_present = {"residual_likelihood", "residual_consequence"}.intersection(out.columns)
    if residual_present and residual_present != {"residual_likelihood", "residual_consequence"}:
        result.warnings.append("Only one residual-risk field was supplied; residual risk was not calculated.")
    if residual_present == {"residual_likelihood", "residual_consequence"}:
        for column in ("residual_likelihood", "residual_consequence"):
            numeric = pd.to_numeric(out[column], errors="coerce")
            out[column] = numeric
            invalid = numeric.notna() & ~numeric.map(valid_scale)
            if invalid.any():
                result.errors.append(f"{int(invalid.sum())} invalid '{column}' value(s); use integers from 1 to 5.")
                result.invalid_rows.extend(out.index[invalid].tolist())
        residual_valid = out["residual_likelihood"].map(valid_scale) & out["residual_consequence"].map(valid_scale)
        out["residual_risk_score"] = calculate_risk_score(out["residual_likelihood"], out["residual_consequence"])
        out.loc[~residual_valid, "residual_risk_score"] = np.nan
        out["residual_risk_category"] = out["residual_risk_score"].map(classify_risk)
    else:
        out["residual_risk_score"] = np.nan
        out["residual_risk_category"] = "Not provided"
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
        result.warnings.append(f"{int(unknown.sum())} critical-control flag(s) were not recognized and treated as false.")
    return normalized.isin(true_values)


def validate_requirements(df: pd.DataFrame, overrides: Mapping[str, str] | None = None) -> ValidationResult:
    """Map and validate ORL requirement records and derive readiness fields."""
    out = _apply_aliases(df, REQUIREMENT_ALIASES, overrides)
    result = ValidationResult(out)
    required = ["requirement", "observed_score", "maximum_score"]
    result.missing_columns = [column for column in required if column not in out.columns]
    if result.missing_columns:
        result.errors.append(f"Missing required requirement columns: {', '.join(result.missing_columns)}.")
        return result
    if "requirement_id" not in out.columns:
        out.insert(0, "requirement_id", [f"R{i:03d}" for i in range(1, len(out) + 1)])
        result.warnings.append("requirement_id was not supplied; stable row-based IDs were generated.")
    result.duplicate_ids = _duplicate_ids(out, "requirement_id")
    if result.duplicate_ids:
        result.errors.append(f"Duplicate requirement_id value(s): {', '.join(result.duplicate_ids)}.")
    blank_ids = _blank_ids(out, "requirement_id")
    if blank_ids:
        result.errors.append(f"{blank_ids} requirement_id value(s) are blank.")

    observed = pd.to_numeric(out["observed_score"], errors="coerce")
    maximum = pd.to_numeric(out["maximum_score"], errors="coerce")
    out["observed_score"], out["maximum_score"] = observed, maximum
    invalid = observed.isna() | maximum.isna() | (maximum <= 0) | (observed < 0) | (observed > maximum)
    if invalid.any():
        result.invalid_rows.extend(out.index[invalid].tolist())
        result.errors.append(
            f"{int(invalid.sum())} invalid requirement row(s): observed must be ≥0, observed ≤ maximum, and maximum >0."
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
            result.warnings.append(f"{int(blank.sum())} critical-control flag(s) are blank and treated as false.")
        out["critical_control"] = _parse_boolean(out["critical_control"], result)
    out["evidence_missing"] = out["objective_evidence"].isna() | out["objective_evidence"].astype(str).str.strip().isin(["", "nan", "none", "not provided"])
    out["incomplete"] = invalid | out["evidence_missing"]
    if "compliance_status" not in out.columns:
        out["compliance_status"] = np.where(out["incomplete"], "Incomplete", np.where(out["observed_score"] < out["maximum_score"], "Below threshold", "Compliant"))
    for optional in ("corrective_action", "responsible_person"):
        if optional not in out.columns:
            out[optional] = "Not provided"
    if "critical_threshold" in out.columns:
        out["critical_threshold"] = pd.to_numeric(out["critical_threshold"], errors="coerce")
    else:
        out["critical_threshold"] = out["maximum_score"]
    _parse_dates(out, result)
    result.data = out
    result.invalid_rows = sorted(set(result.invalid_rows))
    return result
