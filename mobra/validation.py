"""Schema mapping and validation for hazard and ORL requirement data."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from .risk import calculate_risk_score, classify_risk
from .validation_findings import (
    FindingCollector,
    ValidationFinding,
    apply_validation_fields,
    finding_counts,
)


@dataclass
class ValidationResult:
    """Validated data plus user-facing diagnostics."""

    data: pd.DataFrame
    findings: list[ValidationFinding] = field(default_factory=list)
    missing_columns: list[str] = field(default_factory=list)
    duplicate_ids: list[str] = field(default_factory=list)
    invalid_rows: list[int] = field(default_factory=list)
    dataset_type: str = "Dataset"
    raw_data: pd.DataFrame = field(default_factory=pd.DataFrame)
    validation_reference_date: str = field(default_factory=lambda: date.today().isoformat())

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
    def all_messages(self) -> list[str]:
        return [*self.errors, *self.warnings, *self.information]

    @property
    def dataset_blocked(self) -> bool:
        return any(
            finding.severity == "Error" and finding.blocks_analysis and finding.row_index is None
            for finding in self.findings
        )

    def __iter__(self):
        """Allow legacy ``validated, errors = validate_*`` unpacking."""
        yield self.data
        yield self.errors

    @property
    def quality(self) -> dict[str, int | float]:
        rows = len(self.data)
        missing = int(self.data.isna().sum().sum()) if rows else 0
        counts = finding_counts(self.findings)
        eligible = int(self.data.get("analysis_eligible", pd.Series(True, index=self.data.index)).fillna(False).sum())
        return {
            "rows": rows,
            "columns": len(self.data.columns),
            "missing_values": missing,
            "duplicate_ids": len(self.duplicate_ids),
            "invalid_rows": len(self.invalid_rows),
            "missing_value_pct": round(100 * missing / max(rows * max(len(self.data.columns), 1), 1), 2),
            "analysis_eligible_records": eligible,
            "excluded_records": rows - eligible,
            **counts,
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


# Structured validation implementation.


def _normalise_with_findings(df: pd.DataFrame, collector: FindingCollector) -> pd.DataFrame:
    out = df.copy()
    names: list[str] = []
    used: dict[str, int] = {}
    originals = [str(column) for column in out.columns]
    bases: list[str] = []
    for raw in originals:
        name = raw.strip().lower()
        name = "".join(char if (char.isascii() and char.isalnum()) else "_" for char in name)
        name = re.sub(r"_+", "_", name).strip("_") or "unnamed"
        bases.append(name)
        used[name] = used.get(name, 0) + 1
        names.append(name if used[name] == 1 else f"{name}_{used[name]}")
    out.columns = names
    duplicate_bases = sorted({name for name in bases if bases.count(name) > 1})
    if duplicate_bases:
        collector.add(
            "Warning",
            "DUPLICATE_NORMALIZED_COLUMN",
            f"{collector.dataset_type}: column names become duplicates after normalization: {', '.join(duplicate_bases)}.",
            original_value=originals,
            normalized_value=names,
            suggested_action="Rename ambiguous source columns so each normalized header is unique.",
        )
    for raw, normalized in zip(originals, names, strict=True):
        if raw != raw.strip():
            collector.add(
                "Warning",
                "TRAILING_OR_LEADING_WHITESPACE",
                f"{collector.dataset_type}: column header {raw!r} contains leading or trailing whitespace.",
                column=normalized,
                original_value=raw,
                normalized_value=normalized,
                suggested_action="Trim the source column header.",
            )
    return out


def _dataset_preflight(
    df: pd.DataFrame,
    collector: FindingCollector,
    recognized_columns: set[str],
) -> tuple[pd.DataFrame, pd.Series]:
    out = _normalise_with_findings(df, collector)
    blank_rows = pd.Series(False, index=out.index, dtype=bool)
    if out.empty or len(out) == 0:
        collector.add(
            "Error",
            "EMPTY_DATASET",
            f"{collector.dataset_type}: the dataset contains no data rows.",
            suggested_action="Upload a file with a header and at least one data row.",
            blocks_analysis=True,
        )
    if len(out.columns) == 0:
        collector.add(
            "Error",
            "EMPTY_DATASET",
            f"{collector.dataset_type}: the dataset contains no readable columns.",
            suggested_action="Upload a readable tabular file with column headers.",
            blocks_analysis=True,
        )
        return out, blank_rows
    blank_rows = out.apply(
        lambda row: all(pd.isna(value) or str(value).strip() == "" for value in row),
        axis=1,
    )
    for index in out.index[blank_rows]:
        collector.add(
            "Error",
            "COMPLETELY_BLANK_ROW",
            f"{collector.dataset_type}: row {index + 2} is completely blank.",
            row_index=index,
            suggested_action="Remove the blank row or populate its required fields.",
            blocks_analysis=True,
        )
    for column in out.columns:
        blank_column = out[column].map(lambda value: pd.isna(value) or str(value).strip() == "").all()
        if blank_column:
            collector.add(
                "Warning",
                "COMPLETELY_BLANK_COLUMN",
                f"{collector.dataset_type}: column {column!r} is completely blank.",
                column=column,
                suggested_action="Remove the unused column or populate it if required.",
            )
    if not recognized_columns.intersection(out.columns):
        cover_tokens = " ".join(out.columns).lower()
        code = (
            "POSSIBLE_INSTRUCTION_SHEET"
            if any(token in cover_tokens for token in ("instruction", "readme", "cover", "guide"))
            else "UNRECOGNIZED_DATASET_TYPE"
        )
        collector.add(
            "Error",
            code,
            f"{collector.dataset_type}: no recognizable data columns were found; this may be an instruction or cover sheet.",
            original_value=list(out.columns),
            suggested_action="Select the worksheet containing the actual tabular records.",
            blocks_analysis=True,
        )
    return out, blank_rows


def _apply_aliases_structured(
    df: pd.DataFrame,
    aliases: Mapping[str, list[str]],
    overrides: Mapping[str, str] | None,
    collector: FindingCollector,
) -> tuple[pd.DataFrame, pd.Series]:
    recognized = {item for options in aliases.values() for item in options} | set(aliases)
    out, blank_rows = _dataset_preflight(df, collector, recognized)
    overrides = overrides or {}
    rename: dict[str, str] = {}
    for target, options in aliases.items():
        requested = overrides.get(target)
        if requested and requested in out.columns:
            rename[requested] = target
        elif target not in out.columns:
            found = next((candidate for candidate in options if candidate in out.columns), None)
            if found:
                rename[found] = target
    return out.rename(columns=rename), blank_rows


def _is_blank(value: object) -> bool:
    return pd.isna(value) or str(value).strip().lower() in {"", "nan", "none", "not provided", "n/a", "na"}


def _record_id(out: pd.DataFrame, index: int, id_column: str) -> object:
    return out.at[index, id_column] if id_column in out.columns and index in out.index else None


def _prepare_ids(
    out: pd.DataFrame,
    collector: FindingCollector,
    id_column: str,
    prefix: str,
) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    generated = id_column not in out.columns
    if generated:
        out.insert(0, id_column, [f"{prefix}{position:03d}" for position in range(1, len(out) + 1)])
        out[f"{id_column}_raw"] = pd.NA
        out[f"{id_column}_generated"] = True
        collector.add(
            "Warning",
            "GENERATED_ROW_ORDER_ID",
            f"{collector.dataset_type}: {id_column} was not supplied; row-order IDs were generated and are unstable unless persisted.",
            column=id_column,
            suggested_action=f"Add and persist a unique {id_column} column in the source file.",
        )
    else:
        out[f"{id_column}_raw"] = out[id_column]
        out[f"{id_column}_generated"] = False
        out[id_column] = out[id_column].astype("string").str.strip()
    valid = pd.Series(True, index=out.index, dtype=bool)
    for index, raw in out[f"{id_column}_raw"].items():
        normalized = out.at[index, id_column]
        if not generated and not pd.isna(raw) and str(raw) != str(raw).strip():
            collector.add(
                "Warning",
                "TRAILING_OR_LEADING_WHITESPACE",
                f"{collector.dataset_type}: {id_column} at row {index + 2} contains surrounding whitespace.",
                row_index=index,
                record_id=normalized,
                column=id_column,
                original_value=raw,
                normalized_value=normalized,
                suggested_action="Remove surrounding whitespace from the source identifier.",
            )
        if _is_blank(normalized):
            valid.loc[index] = False
            collector.add(
                "Error",
                "BLANK_ID",
                f"{collector.dataset_type}: row {index + 2} has a blank {id_column}.",
                row_index=index,
                column=id_column,
                original_value=raw,
                suggested_action=f"Provide a unique nonblank {id_column}.",
                blocks_analysis=True,
            )
        elif not re.fullmatch(rf"{prefix}\d{{3}}", str(normalized)):
            collector.add(
                "Information",
                "INVALID_ID_FORMAT",
                f"{collector.dataset_type}: {normalized!r} does not use the recommended {prefix}001-style format; external IDs remain allowed.",
                row_index=index,
                record_id=normalized,
                column=id_column,
                original_value=raw,
                normalized_value=normalized,
                suggested_action="Keep the external ID if intentional or adopt the recommended format for consistency.",
            )
    values = out[id_column].astype("string")
    duplicate_mask = values.notna() & values.ne("") & values.duplicated(keep=False)
    duplicate_ids = sorted(values[duplicate_mask].dropna().unique().tolist())
    for index in out.index[duplicate_mask]:
        valid.loc[index] = False
        collector.add(
            "Error",
            "DUPLICATE_ID",
            f"{collector.dataset_type}: {id_column} {values.loc[index]!r} is duplicated.",
            row_index=index,
            record_id=values.loc[index],
            column=id_column,
            original_value=out.at[index, f"{id_column}_raw"],
            normalized_value=values.loc[index],
            suggested_action="Assign a unique stable identifier to every record.",
            blocks_analysis=True,
        )
    return out, valid, duplicate_ids


def _validate_required_text(
    out: pd.DataFrame,
    collector: FindingCollector,
    column: str,
    id_column: str,
    *,
    required: bool,
) -> pd.Series:
    valid = pd.Series(True, index=out.index, dtype=bool)
    if column not in out.columns:
        if not required:
            return valid
        return pd.Series(False, index=out.index, dtype=bool)
    for index, value in out[column].items():
        if _is_blank(value):
            valid.loc[index] = False
            collector.add(
                "Error" if required else "Warning",
                "EMPTY_REQUIRED_TEXT" if required else "MISSING_OPERATIONAL_TEXT",
                f"{collector.dataset_type}: {column} is blank for record {_record_id(out, index, id_column) or f'row {index + 2}'}.",
                row_index=index,
                record_id=_record_id(out, index, id_column),
                column=column,
                original_value=value,
                suggested_action=f"Provide a meaningful {column.replace('_', ' ')} value.",
                blocks_analysis=required,
            )
        elif str(value) != str(value).strip():
            collector.add(
                "Warning",
                "TRAILING_OR_LEADING_WHITESPACE",
                f"{collector.dataset_type}: {column} contains surrounding whitespace for record {_record_id(out, index, id_column)}.",
                row_index=index,
                record_id=_record_id(out, index, id_column),
                column=column,
                original_value=value,
                normalized_value=str(value).strip(),
                suggested_action="Trim the source text value.",
            )
    return valid


def _validate_numeric_scale(
    out: pd.DataFrame,
    collector: FindingCollector,
    column: str,
    id_column: str,
    *,
    minimum: int,
    maximum: int,
    allow_missing: bool = False,
) -> tuple[pd.Series, pd.Series]:
    raw_column = f"{column}_raw"
    raw = out[column].copy() if column in out.columns else pd.Series(pd.NA, index=out.index)
    out[raw_column] = raw
    numeric = pd.to_numeric(raw, errors="coerce")
    out[column] = numeric
    valid = pd.Series(True, index=out.index, dtype=bool)
    for index, value in raw.items():
        record_id = _record_id(out, index, id_column)
        blank = _is_blank(value)
        number = numeric.loc[index]
        if blank:
            valid.loc[index] = allow_missing
            if not allow_missing:
                collector.add(
                    "Error",
                    "MISSING_NUMERIC_VALUE",
                    f"{collector.dataset_type}: {column} is missing for record {record_id or f'row {index + 2}'}; expected an integer from {minimum} to {maximum}.",
                    row_index=index,
                    record_id=record_id,
                    column=column,
                    original_value=value,
                    suggested_action=f"Enter an integer from {minimum} to {maximum}.",
                    blocks_analysis=True,
                )
        elif pd.isna(number):
            valid.loc[index] = False
            collector.add(
                "Error",
                "INVALID_NUMERIC_VALUE",
                f"{collector.dataset_type}: {column}={value!r} for record {record_id} is not numeric; expected an integer from {minimum} to {maximum}.",
                row_index=index,
                record_id=record_id,
                column=column,
                original_value=value,
                suggested_action=f"Replace the value with an integer from {minimum} to {maximum}.",
                blocks_analysis=True,
            )
        elif not np.isfinite(number):
            valid.loc[index] = False
            collector.add(
                "Error",
                "NON_FINITE_VALUE",
                f"{collector.dataset_type}: {column}={value!r} for record {record_id} is infinite or non-finite.",
                row_index=index,
                record_id=record_id,
                column=column,
                original_value=value,
                suggested_action=f"Enter a finite integer from {minimum} to {maximum}.",
                blocks_analysis=True,
            )
        elif not float(number).is_integer():
            valid.loc[index] = False
            collector.add(
                "Error",
                "NON_INTEGER_VALUE",
                f"{collector.dataset_type}: {column}={value!r} for record {record_id} is decimal; expected an integer from {minimum} to {maximum}.",
                row_index=index,
                record_id=record_id,
                column=column,
                original_value=value,
                normalized_value=number,
                suggested_action=f"Enter a whole number from {minimum} to {maximum}.",
                blocks_analysis=True,
            )
        elif number < minimum or number > maximum:
            valid.loc[index] = False
            direction = "below" if number < minimum else "above"
            collector.add(
                "Error",
                "VALUE_OUT_OF_RANGE",
                f"{collector.dataset_type}: "
                f"{'invalid requirement value — ' if collector.dataset_type == 'Requirements' else ''}"
                f"{column}={value!r} for record {record_id} is {direction} the allowed {minimum}–{maximum} range.",
                row_index=index,
                record_id=record_id,
                column=column,
                original_value=value,
                normalized_value=number,
                suggested_action=f"Enter an integer from {minimum} to {maximum}.",
                blocks_analysis=True,
            )
    return numeric, valid


def _missing_required_columns(
    out: pd.DataFrame,
    required: list[str],
    collector: FindingCollector,
) -> list[str]:
    missing = [column for column in required if column not in out.columns]
    for column in missing:
        collector.add(
            "Error",
            "MISSING_REQUIRED_COLUMN",
            f"{collector.dataset_type}: required column {column!r} is missing.",
            column=column,
            suggested_action=f"Add a {column} column or map an equivalent source column.",
            blocks_analysis=True,
        )
    return missing


def _finalize_result(
    out: pd.DataFrame,
    collector: FindingCollector,
    *,
    missing_columns: list[str],
    duplicate_ids: list[str],
    eligibility: pd.Series,
    record_id_column: str,
    exclusion_reasons: dict[int, list[str]],
    raw_data: pd.DataFrame,
    validation_reference_date: str,
) -> ValidationResult:
    out = apply_validation_fields(
        out,
        collector.findings,
        analysis_eligible=eligibility,
        record_id_column=record_id_column,
        exclusion_reasons=exclusion_reasons,
    )
    invalid_rows = sorted(int(index) for index in out.index[~eligibility.reindex(out.index, fill_value=False)])
    return ValidationResult(
        data=out,
        findings=collector.findings,
        missing_columns=missing_columns,
        duplicate_ids=duplicate_ids,
        invalid_rows=invalid_rows,
        dataset_type=collector.dataset_type,
        raw_data=raw_data.copy(),
        validation_reference_date=validation_reference_date,
    )


def validate_hazards(
    df: pd.DataFrame,
    overrides: Mapping[str, str] | None = None,
    *,
    validation_reference_date: str | date | pd.Timestamp | None = None,
) -> ValidationResult:
    """Validate hazards with raw traceability and separate inherent/residual eligibility."""
    reference = pd.Timestamp(validation_reference_date or date.today()).date().isoformat()
    collector = FindingCollector("Hazards")
    out, blank_rows = _apply_aliases_structured(df, HAZARD_ALIASES, overrides, collector)
    missing_columns = _missing_required_columns(out, ["hazard", "likelihood", "consequence"], collector)
    out, id_valid, duplicate_ids = _prepare_ids(out, collector, "hazard_id", "H")
    text_valid = (
        _validate_required_text(out, collector, "hazard", "hazard_id", required=True)
        if "hazard" in out
        else pd.Series(False, index=out.index)
    )

    uploaded_score = out["risk_score"].copy() if "risk_score" in out else None
    uploaded_category = out["risk_category"].copy() if "risk_category" in out else None
    if uploaded_score is not None:
        out["uploaded_risk_score"] = uploaded_score
    if uploaded_category is not None:
        out["uploaded_risk_category"] = uploaded_category

    if "likelihood" in out:
        _, likelihood_valid = _validate_numeric_scale(out, collector, "likelihood", "hazard_id", minimum=1, maximum=5)
    else:
        likelihood_valid = pd.Series(False, index=out.index)
        out["likelihood_raw"] = pd.NA
        out["likelihood"] = np.nan
    if "consequence" in out:
        _, consequence_valid = _validate_numeric_scale(out, collector, "consequence", "hazard_id", minimum=1, maximum=5)
    else:
        consequence_valid = pd.Series(False, index=out.index)
        out["consequence_raw"] = pd.NA
        out["consequence"] = np.nan
    inherent_eligible = id_valid & text_valid & likelihood_valid & consequence_valid & ~blank_rows
    out["inherent_risk_eligible"] = inherent_eligible
    out["risk_score"] = calculate_risk_score(out["likelihood"], out["consequence"])
    out.loc[~inherent_eligible, "risk_score"] = np.nan
    out["risk_category"] = out["risk_score"].map(classify_risk)
    out["risk_level"] = out["risk_category"]
    out["risk_value_source"] = "Calculated from likelihood × consequence"

    if uploaded_score is not None:
        uploaded_numeric = pd.to_numeric(uploaded_score, errors="coerce")
        for index in out.index[inherent_eligible & uploaded_numeric.notna() & uploaded_numeric.ne(out["risk_score"])]:
            collector.add(
                "Warning",
                "INCONSISTENT_CALCULATED_RISK",
                f"Hazards: uploaded risk_score={uploaded_score.loc[index]!r} differs from calculated score {out.at[index, 'risk_score']:g} for {out.at[index, 'hazard_id']}.",
                row_index=index,
                record_id=out.at[index, "hazard_id"],
                column="risk_score",
                original_value=uploaded_score.loc[index],
                normalized_value=out.at[index, "risk_score"],
                suggested_action="Review the uploaded score; MOBRA uses likelihood × consequence as the source of truth.",
            )
    if uploaded_category is not None:
        normalized_category = uploaded_category.astype("string").str.strip().str.title()
        known = normalized_category.isin(["Low", "Moderate", "High", "Extreme"])
        for index in out.index[uploaded_category.notna() & ~known]:
            collector.add(
                "Warning",
                "UNKNOWN_CATEGORY",
                f"Hazards: uploaded risk_category={uploaded_category.loc[index]!r} is unknown for {out.at[index, 'hazard_id']}.",
                row_index=index,
                record_id=out.at[index, "hazard_id"],
                column="risk_category",
                original_value=uploaded_category.loc[index],
                normalized_value=normalized_category.loc[index],
                suggested_action="Use Low, Moderate, High, or Extreme.",
            )
        mismatch = inherent_eligible & known & normalized_category.ne(out["risk_category"])
        for index in out.index[mismatch]:
            collector.add(
                "Warning",
                "INCONSISTENT_CALCULATED_RISK",
                f"Hazards: uploaded risk_category={uploaded_category.loc[index]!r} differs from calculated category {out.at[index, 'risk_category']} for {out.at[index, 'hazard_id']}.",
                row_index=index,
                record_id=out.at[index, "hazard_id"],
                column="risk_category",
                original_value=uploaded_category.loc[index],
                normalized_value=out.at[index, "risk_category"],
                suggested_action="Review the uploaded category; MOBRA calculated boundaries remain the source of truth.",
            )

    residual_columns = {"residual_likelihood", "residual_consequence"}
    present_residual = residual_columns.intersection(out.columns)
    uploaded_residual_score = out["residual_risk_score"].copy() if "residual_risk_score" in out else None
    uploaded_residual_category = out["residual_risk_category"].copy() if "residual_risk_category" in out else None
    if uploaded_residual_score is not None:
        out["uploaded_residual_risk_score"] = uploaded_residual_score
    if uploaded_residual_category is not None:
        out["uploaded_residual_risk_category"] = uploaded_residual_category
    if not present_residual:
        collector.add(
            "Information",
            "RESIDUAL_ASSESSMENT_NOT_PROVIDED",
            "Hazards: residual likelihood and consequence were not supplied; inherent risk remains available for explicitly labeled screening.",
            suggested_action="Provide both residual fields when a post-control assessment is available.",
        )
        residual_eligible = pd.Series(False, index=out.index)
        out["residual_likelihood_raw"] = pd.NA
        out["residual_consequence_raw"] = pd.NA
        out["residual_likelihood"] = np.nan
        out["residual_consequence"] = np.nan
    else:
        for column in residual_columns - present_residual:
            out[column] = pd.NA
        _, residual_likelihood_valid = _validate_numeric_scale(
            out, collector, "residual_likelihood", "hazard_id", minimum=1, maximum=5, allow_missing=True
        )
        _, residual_consequence_valid = _validate_numeric_scale(
            out, collector, "residual_consequence", "hazard_id", minimum=1, maximum=5, allow_missing=True
        )
        likelihood_present = ~out["residual_likelihood_raw"].map(_is_blank)
        consequence_present = ~out["residual_consequence_raw"].map(_is_blank)
        partial = likelihood_present ^ consequence_present
        for index in out.index[partial]:
            collector.add(
                "Error",
                "INCOMPLETE_RESIDUAL_PAIR",
                f"Hazards: {out.at[index, 'hazard_id']} supplies only one residual-risk scale value; both are required.",
                row_index=index,
                record_id=out.at[index, "hazard_id"],
                column="residual_likelihood/residual_consequence",
                original_value={
                    "residual_likelihood": out.at[index, "residual_likelihood_raw"],
                    "residual_consequence": out.at[index, "residual_consequence_raw"],
                },
                suggested_action="Provide both residual likelihood and residual consequence or leave both blank.",
                blocks_analysis=True,
            )
        residual_eligible = (
            likelihood_present & consequence_present & residual_likelihood_valid & residual_consequence_valid
        )
    out["residual_risk_eligible"] = residual_eligible
    out["residual_risk_score"] = calculate_risk_score(out["residual_likelihood"], out["residual_consequence"])
    out.loc[~residual_eligible, "residual_risk_score"] = np.nan
    out["residual_risk_category"] = out["residual_risk_score"].map(classify_risk)
    out.loc[~residual_eligible, "residual_risk_category"] = "Not provided"
    higher_residual = residual_eligible & inherent_eligible & out["residual_risk_score"].gt(out["risk_score"])
    for index in out.index[higher_residual]:
        collector.add(
            "Information",
            "RESIDUAL_RISK_HIGHER_THAN_INHERENT",
            f"Hazards: residual score {out.at[index, 'residual_risk_score']:g} is higher than inherent score {out.at[index, 'risk_score']:g} for {out.at[index, 'hazard_id']}.",
            row_index=index,
            record_id=out.at[index, "hazard_id"],
            column="residual_risk_score",
            original_value=out.at[index, "residual_risk_score"],
            normalized_value=out.at[index, "risk_score"],
            suggested_action="Confirm whether controls or reassessment legitimately changed the estimate.",
        )

    if uploaded_residual_score is not None:
        uploaded_numeric = pd.to_numeric(uploaded_residual_score, errors="coerce")
        mismatch = residual_eligible & uploaded_numeric.notna() & uploaded_numeric.ne(out["residual_risk_score"])
        for index in out.index[mismatch]:
            collector.add(
                "Warning",
                "INCONSISTENT_CALCULATED_RISK",
                f"Hazards: uploaded residual_risk_score differs from the calculated residual score for {out.at[index, 'hazard_id']}.",
                row_index=index,
                record_id=out.at[index, "hazard_id"],
                column="residual_risk_score",
                original_value=uploaded_residual_score.loc[index],
                normalized_value=out.at[index, "residual_risk_score"],
                suggested_action="Review the uploaded residual score; calculated residual likelihood × consequence is authoritative.",
            )
    if uploaded_residual_category is not None:
        normalized = uploaded_residual_category.astype("string").str.strip().str.title()
        known = normalized.isin(["Low", "Moderate", "High", "Extreme"])
        for index in out.index[uploaded_residual_category.notna() & ~known]:
            collector.add(
                "Warning",
                "UNKNOWN_CATEGORY",
                f"Hazards: uploaded residual_risk_category={uploaded_residual_category.loc[index]!r} is unknown for {out.at[index, 'hazard_id']}.",
                row_index=index,
                record_id=out.at[index, "hazard_id"],
                column="residual_risk_category",
                original_value=uploaded_residual_category.loc[index],
                normalized_value=normalized.loc[index],
                suggested_action="Use Low, Moderate, High, or Extreme.",
            )
        mismatch = residual_eligible & known & normalized.ne(out["residual_risk_category"])
        for index in out.index[mismatch]:
            collector.add(
                "Warning",
                "INCONSISTENT_CALCULATED_RISK",
                f"Hazards: uploaded residual category differs from the calculated category for {out.at[index, 'hazard_id']}.",
                row_index=index,
                record_id=out.at[index, "hazard_id"],
                column="residual_risk_category",
                original_value=uploaded_residual_category.loc[index],
                normalized_value=out.at[index, "residual_risk_category"],
                suggested_action="Review the uploaded residual category against the fixed MOBRA boundaries.",
            )

    optional_text = (
        "domain",
        "activity",
        "cause",
        "existing_controls",
        "corrective_action",
        "responsible_person",
        "status",
    )
    for column in optional_text:
        if column not in out:
            out[column] = pd.NA
        _validate_required_text(out, collector, column, "hazard_id", required=False)
        out[column] = out[column].where(~out[column].map(_is_blank), "Not provided")
    for column in ("hazard_category", "biological_agent"):
        if column not in out:
            out[column] = "Not provided"
    _parse_dates_structured(out, collector, "hazard_id", reference)
    exclusion_reasons = {
        int(index): ["Invalid hazard ID, required text, likelihood, or consequence prevents inherent-risk calculation."]
        for index in out.index[~inherent_eligible]
    }
    return _finalize_result(
        out,
        collector,
        missing_columns=missing_columns,
        duplicate_ids=duplicate_ids,
        eligibility=inherent_eligible,
        record_id_column="hazard_id",
        exclusion_reasons=exclusion_reasons,
        raw_data=df,
        validation_reference_date=reference,
    )


def _parse_dates_structured(
    out: pd.DataFrame,
    collector: FindingCollector,
    id_column: str,
    reference_date: str,
) -> None:
    out["validation_reference_date"] = reference_date
    if "due_date" not in out.columns:
        out["due_date_raw"] = pd.NA
        out["due_date"] = pd.NA
        out["date_parse_status"] = "Not provided"
        out["overdue"] = False
        return
    raw = out["due_date"].copy()
    out["due_date_raw"] = raw
    parsed = pd.Series(pd.NaT, index=out.index, dtype="datetime64[ns]")
    status = pd.Series("Not provided", index=out.index, dtype="string")
    reference = pd.Timestamp(reference_date).normalize()
    for index, value in raw.items():
        if _is_blank(value):
            continue
        text = str(value).strip()
        ambiguous_match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
        if ambiguous_match and int(ambiguous_match.group(1)) <= 12 and int(ambiguous_match.group(2)) <= 12:
            status.loc[index] = "Ambiguous"
            collector.add(
                "Warning",
                "AMBIGUOUS_DATE",
                f"{collector.dataset_type}: due_date={value!r} for {_record_id(out, index, id_column)} is ambiguous.",
                row_index=index,
                record_id=_record_id(out, index, id_column),
                column="due_date",
                original_value=value,
                suggested_action="Use unambiguous ISO format YYYY-MM-DD.",
            )
            continue
        converted = pd.to_datetime(text, errors="coerce")
        if pd.isna(converted):
            status.loc[index] = "Invalid"
            collector.add(
                "Warning",
                "INVALID_DATE",
                f"{collector.dataset_type}: due_date={value!r} for {_record_id(out, index, id_column)} could not be parsed.",
                row_index=index,
                record_id=_record_id(out, index, id_column),
                column="due_date",
                original_value=value,
                suggested_action="Use a valid unambiguous date such as YYYY-MM-DD.",
            )
            continue
        parsed.loc[index] = converted
        status.loc[index] = "Parsed"
        if converted.normalize() < reference - pd.DateOffset(years=10):
            collector.add(
                "Warning",
                "IMPLAUSIBLE_PAST_DATE",
                f"{collector.dataset_type}: due_date {converted.date()} for {_record_id(out, index, id_column)} is more than 10 years before the validation reference date.",
                row_index=index,
                record_id=_record_id(out, index, id_column),
                column="due_date",
                original_value=value,
                normalized_value=converted.date(),
                suggested_action="Confirm the year and intended target date.",
            )
        if converted.normalize() > reference + pd.DateOffset(years=10):
            collector.add(
                "Warning",
                "IMPLAUSIBLE_FUTURE_DATE",
                f"{collector.dataset_type}: due_date {converted.date()} for {_record_id(out, index, id_column)} is more than 10 years after the validation reference date.",
                row_index=index,
                record_id=_record_id(out, index, id_column),
                column="due_date",
                original_value=value,
                normalized_value=converted.date(),
                suggested_action="Confirm the year and intended target date.",
            )
        action_status = str(out.at[index, "status"]).strip().lower() if "status" in out else ""
        if action_status in {"complete", "completed", "closed", "done"} and converted.normalize() > reference:
            collector.add(
                "Warning",
                "COMPLETED_WITH_FUTURE_DUE_DATE",
                f"{collector.dataset_type}: completed record {_record_id(out, index, id_column)} has a future due date {converted.date()}.",
                row_index=index,
                record_id=_record_id(out, index, id_column),
                column="due_date",
                original_value=value,
                suggested_action="Confirm the completion status or due date.",
            )
        if action_status not in {"complete", "completed", "closed", "done"} and converted.normalize() < reference:
            collector.add(
                "Warning",
                "OVERDUE_OPEN_ACTION",
                f"{collector.dataset_type}: open record {_record_id(out, index, id_column)} was overdue on runtime reference date {reference.date()}.",
                row_index=index,
                record_id=_record_id(out, index, id_column),
                column="due_date",
                original_value=value,
                normalized_value=converted.date(),
                suggested_action="Update the action status or provide a revised target date.",
            )
        if "assessment_date" in out and not _is_blank(out.at[index, "assessment_date"]):
            assessment_date = pd.to_datetime(out.at[index, "assessment_date"], errors="coerce")
            if pd.notna(assessment_date) and converted < assessment_date:
                collector.add(
                    "Warning",
                    "TARGET_BEFORE_ASSESSMENT_DATE",
                    f"{collector.dataset_type}: due date precedes assessment date for {_record_id(out, index, id_column)}.",
                    row_index=index,
                    record_id=_record_id(out, index, id_column),
                    column="due_date",
                    original_value=value,
                    suggested_action="Confirm the assessment and target dates.",
                )
    out["due_date"] = parsed.dt.strftime("%Y-%m-%d")
    out.loc[parsed.isna(), "due_date"] = pd.NA
    out["date_parse_status"] = status
    out["overdue"] = parsed.notna() & parsed.lt(reference)


def validate_requirements(
    df: pd.DataFrame,
    overrides: Mapping[str, str] | None = None,
    *,
    strict_demo_scale: bool = True,
    validation_reference_date: str | date | pd.Timestamp | None = None,
) -> ValidationResult:
    """Validate ORL requirements with separate BRI and critical-control eligibility."""
    reference = pd.Timestamp(validation_reference_date or date.today()).date().isoformat()
    collector = FindingCollector("Requirements")
    out, blank_rows = _apply_aliases_structured(df, REQUIREMENT_ALIASES, overrides, collector)
    missing_columns = _missing_required_columns(out, ["requirement", "observed_score", "maximum_score"], collector)
    out, id_valid, duplicate_ids = _prepare_ids(out, collector, "requirement_id", "R")
    text_valid = (
        _validate_required_text(out, collector, "requirement", "requirement_id", required=True)
        if "requirement" in out
        else pd.Series(False, index=out.index)
    )

    score_maximum = 5 if strict_demo_scale else 1_000_000
    if "observed_score" in out:
        observed, observed_valid = _validate_numeric_scale(
            out, collector, "observed_score", "requirement_id", minimum=0, maximum=score_maximum
        )
    else:
        observed = pd.Series(np.nan, index=out.index)
        observed_valid = pd.Series(False, index=out.index)
        out["observed_score_raw"] = pd.NA
        out["observed_score"] = np.nan
    if "maximum_score" in out:
        raw_maximum = out["maximum_score"].copy()
        maximum, maximum_valid = _validate_numeric_scale(
            out, collector, "maximum_score", "requirement_id", minimum=1, maximum=score_maximum
        )
        numeric_maximum = pd.to_numeric(raw_maximum, errors="coerce")
        zero_or_negative = numeric_maximum.notna() & numeric_maximum.le(0)
        for index in out.index[zero_or_negative]:
            collector.add(
                "Error",
                "ZERO_OR_NEGATIVE_MAXIMUM",
                f"Requirements: maximum_score={raw_maximum.loc[index]!r} for {out.at[index, 'requirement_id']} must be greater than zero.",
                row_index=index,
                record_id=out.at[index, "requirement_id"],
                column="maximum_score",
                original_value=raw_maximum.loc[index],
                suggested_action="Enter a positive integer maximum score.",
                blocks_analysis=True,
            )
    else:
        maximum = pd.Series(np.nan, index=out.index)
        maximum_valid = pd.Series(False, index=out.index)
        out["maximum_score_raw"] = pd.NA
        out["maximum_score"] = np.nan
    exceeds = observed_valid & maximum_valid & observed.gt(maximum)
    for index in out.index[exceeds]:
        collector.add(
            "Error",
            "OBSERVED_EXCEEDS_MAXIMUM",
            f"Requirements: observed_score={observed.loc[index]:g} exceeds maximum_score={maximum.loc[index]:g} for {out.at[index, 'requirement_id']}.",
            row_index=index,
            record_id=out.at[index, "requirement_id"],
            column="observed_score",
            original_value=out.at[index, "observed_score_raw"],
            normalized_value=observed.loc[index],
            suggested_action="Correct the observed or maximum score so observed does not exceed maximum.",
            blocks_analysis=True,
        )
    score_valid = observed_valid & maximum_valid & ~exceeds
    if not strict_demo_scale:
        outside_demo = score_valid & (observed.gt(5) | maximum.gt(5))
        for index in out.index[outside_demo]:
            collector.add(
                "Information",
                "OUTSIDE_DEMONSTRATION_SCALE",
                f"Requirements: {out.at[index, 'requirement_id']} uses scores outside the demonstration 0–5 scale under configurable external-scale mode.",
                row_index=index,
                record_id=out.at[index, "requirement_id"],
                column="observed_score/maximum_score",
                original_value={"observed": observed.loc[index], "maximum": maximum.loc[index]},
                suggested_action="Confirm the external scoring scale is intentional and documented.",
            )

    if "domain" not in out:
        out["domain"] = pd.NA
    _validate_required_text(out, collector, "domain", "requirement_id", required=False)
    out["domain"] = out["domain"].where(~out["domain"].map(_is_blank), "General")

    if "objective_evidence" not in out:
        out["objective_evidence"] = pd.NA
        collector.add(
            "Warning",
            "MISSING_EVIDENCE_COLUMN",
            "Requirements: objective_evidence/evidence column was not supplied.",
            column="objective_evidence",
            suggested_action="Add objective evidence references for control verification.",
        )
    evidence_status = pd.Series("Complete", index=out.index, dtype="string")
    evidence_reason = pd.Series("Evidence text is present.", index=out.index, dtype="string")
    for index, value in out["objective_evidence"].items():
        normalized = "" if pd.isna(value) else str(value).strip().lower()
        if normalized in {"", "nan", "none", "not provided", "n/a", "na"}:
            evidence_status.loc[index] = "Missing"
            evidence_reason.loc[index] = "Objective evidence is blank or a missing-value placeholder."
            collector.add(
                "Warning",
                "MISSING_EVIDENCE",
                f"Requirements: objective evidence is missing for {out.at[index, 'requirement_id']}.",
                row_index=index,
                record_id=out.at[index, "requirement_id"],
                column="objective_evidence",
                original_value=value,
                suggested_action="Provide a specific document, record, observation, or other objective evidence reference.",
            )
        elif normalized in {"pending", "tbd", "to be provided"} or any(
            marker in normalized for marker in ("incomplete", "pending", "overdue", "unavailable", "expired", "draft")
        ):
            evidence_status.loc[index] = "Incomplete"
            evidence_reason.loc[index] = (
                "Evidence text explicitly indicates a pending, incomplete, overdue, or unavailable item."
            )
            collector.add(
                "Warning",
                "INCOMPLETE_EVIDENCE",
                f"Requirements: evidence for {out.at[index, 'requirement_id']} is explicitly incomplete: {value!r}.",
                row_index=index,
                record_id=out.at[index, "requirement_id"],
                column="objective_evidence",
                original_value=value,
                suggested_action="Complete and verify the objective evidence before closure.",
            )
    out["evidence_status"] = evidence_status
    out["evidence_validation_reason"] = evidence_reason
    out["evidence_missing"] = evidence_status.eq("Missing")

    boolean_valid = pd.Series(True, index=out.index, dtype=bool)
    if "critical_control" not in out:
        out["critical_control_raw"] = pd.NA
        out["critical_control"] = pd.Series(False, index=out.index, dtype="boolean")
        boolean_valid[:] = False
        collector.add(
            "Warning",
            "MISSING_CRITICAL_CONTROL_COLUMN",
            "Requirements: critical_control was not supplied; governance eligibility requires review unless a valid separate profile is used.",
            column="critical_control",
            suggested_action="Provide recognized TRUE/FALSE values or use a validated critical-control profile.",
        )
    else:
        out["critical_control_raw"] = out["critical_control"]
        normalized = out["critical_control_raw"].astype("string").str.strip().str.lower()
        true_values = {"true", "1", "yes", "y", "t"}
        false_values = {"false", "0", "no", "n", "f"}
        parsed = pd.Series(pd.NA, index=out.index, dtype="boolean")
        parsed.loc[normalized.isin(true_values)] = True
        parsed.loc[normalized.isin(false_values)] = False
        blank_boolean = out["critical_control_raw"].map(_is_blank)
        unknown = ~blank_boolean & ~normalized.isin(true_values | false_values)
        boolean_valid = normalized.isin(true_values | false_values)
        for index in out.index[unknown]:
            collector.add(
                "Error",
                "INVALID_BOOLEAN",
                f"Requirements: critical_control={out.at[index, 'critical_control_raw']!r} for {out.at[index, 'requirement_id']} is unrecognized.",
                row_index=index,
                record_id=out.at[index, "requirement_id"],
                column="critical_control",
                original_value=out.at[index, "critical_control_raw"],
                suggested_action="Use TRUE/FALSE, yes/no, y/n, or 1/0 and review the critical designation.",
                blocks_analysis=True,
            )
        for index in out.index[blank_boolean]:
            collector.add(
                "Warning",
                "INVALID_BOOLEAN",
                f"Requirements: critical_control is blank for {out.at[index, 'requirement_id']} and requires review.",
                row_index=index,
                record_id=out.at[index, "requirement_id"],
                column="critical_control",
                original_value=out.at[index, "critical_control_raw"],
                suggested_action="Provide an explicit recognized Boolean value.",
            )
        out["critical_control"] = parsed

    if "critical_threshold" in out:
        _, threshold_valid = _validate_numeric_scale(
            out, collector, "critical_threshold", "requirement_id", minimum=0, maximum=5, allow_missing=True
        )
        threshold_present = ~out["critical_threshold_raw"].map(_is_blank)
        above_maximum = threshold_present & threshold_valid & maximum_valid & out["critical_threshold"].gt(maximum)
        for index in out.index[above_maximum]:
            collector.add(
                "Error",
                "THRESHOLD_EXCEEDS_MAXIMUM",
                f"Requirements: critical_threshold exceeds maximum_score for {out.at[index, 'requirement_id']}.",
                row_index=index,
                record_id=out.at[index, "requirement_id"],
                column="critical_threshold",
                original_value=out.at[index, "critical_threshold_raw"],
                normalized_value=out.at[index, "critical_threshold"],
                suggested_action="Set the threshold at or below maximum_score.",
                blocks_analysis=True,
            )
    else:
        out["critical_threshold"] = out["maximum_score"]

    for column in ("corrective_action", "responsible_person"):
        if column not in out:
            out[column] = pd.NA
        _validate_required_text(out, collector, column, "requirement_id", required=False)
        out[column] = out[column].where(~out[column].map(_is_blank), "Not provided")
    if "status" not in out:
        out["status"] = "Not provided"
    _parse_dates_structured(out, collector, "requirement_id", reference)

    bri_eligible = id_valid & text_valid & score_valid & ~blank_rows
    critical_eligible = bri_eligible & boolean_valid
    out["bri_eligible"] = bri_eligible
    out["critical_control_eligible"] = critical_eligible
    out["item_readiness_pct"] = 100 * observed / maximum
    out.loc[~bri_eligible, "item_readiness_pct"] = np.nan
    out["incomplete"] = ~critical_eligible | out["evidence_status"].isin(["Missing", "Incomplete"])
    if "compliance_status" not in out:
        out["compliance_status"] = np.where(
            out["incomplete"], "Incomplete", np.where(observed < maximum, "Below threshold", "Compliant")
        )
    exclusion_reasons = {
        int(index): ["Invalid requirement ID, required text, observed score, or maximum score prevents BRI inclusion."]
        for index in out.index[~bri_eligible]
    }
    return _finalize_result(
        out,
        collector,
        missing_columns=missing_columns,
        duplicate_ids=duplicate_ids,
        eligibility=bri_eligible,
        record_id_column="requirement_id",
        exclusion_reasons=exclusion_reasons,
        raw_data=df,
        validation_reference_date=reference,
    )
