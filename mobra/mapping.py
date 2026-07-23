"""Validation and analysis for many-to-many requirement-to-hazard mappings."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .validation_findings import FindingCollector, ValidationFinding, apply_validation_fields, finding_counts

MAPPING_REQUIRED_COLUMNS = (
    "mapping_id",
    "requirement_id",
    "hazard_id",
    "relationship_type",
    "mapping_rationale",
    "control_role",
    "critical_link",
    "source_status",
)
ALLOWED_RELATIONSHIP_TYPES = ("Preventive", "Detective", "Corrective", "Recovery", "Governance", "Mixed")
ALLOWED_CONTROL_ROLES = ("Primary", "Supporting", "Indirect")
REPRESENTATIVE_SOURCE_STATUS = "Representative Demonstration Mapping"


@dataclass
class MappingValidationResult:
    """Validated mapping data with errors warnings and quality details."""

    data: pd.DataFrame = field(default_factory=pd.DataFrame)
    findings: list[ValidationFinding] = field(default_factory=list)
    quality: dict[str, object] = field(default_factory=dict)
    missing_columns: list[str] = field(default_factory=list)
    duplicate_ids: list[str] = field(default_factory=list)
    invalid_rows: list[int] = field(default_factory=list)
    dataset_type: str = "Mapping"

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


def _known_ids(df: pd.DataFrame, column: str) -> set[str]:
    if column not in df.columns:
        return set()
    return set(df[column].dropna().astype(str).str.strip().str.upper()) - {""}


def _mapped_ids(mapping_df: pd.DataFrame, column: str, known_ids: set[str]) -> set[str]:
    if column not in mapping_df.columns:
        return set()
    values = set(mapping_df[column].dropna().astype(str).str.strip().str.upper()) - {""}
    return values & known_ids


def _critical_mask(mapping_df: pd.DataFrame) -> pd.Series:
    if "critical_link" not in mapping_df.columns:
        return pd.Series(False, index=mapping_df.index, dtype=bool)

    def is_true(value: object) -> bool:
        if isinstance(value, bool):
            return value
        if pd.isna(value):
            return False
        return str(value).strip().lower() in {"true", "1", "yes", "y"}

    return mapping_df["critical_link"].map(is_true).astype(bool)


def hazards_without_requirements(mapping_df: pd.DataFrame, hazards_df: pd.DataFrame) -> pd.DataFrame:
    """Return hazard records that have no mapped requirement."""
    if "hazard_id" not in hazards_df.columns:
        return hazards_df.iloc[0:0].copy()
    known_ids = _known_ids(hazards_df, "hazard_id")
    mapped_ids = _mapped_ids(mapping_df, "hazard_id", known_ids)
    return hazards_df.loc[~hazards_df["hazard_id"].astype(str).str.strip().str.upper().isin(mapped_ids)].copy()


def requirements_without_hazards(mapping_df: pd.DataFrame, requirements_df: pd.DataFrame) -> pd.DataFrame:
    """Return requirement records that have no mapped hazard."""
    if "requirement_id" not in requirements_df.columns:
        return requirements_df.iloc[0:0].copy()
    known_ids = _known_ids(requirements_df, "requirement_id")
    mapped_ids = _mapped_ids(mapping_df, "requirement_id", known_ids)
    return requirements_df.loc[
        ~requirements_df["requirement_id"].astype(str).str.strip().str.upper().isin(mapped_ids)
    ].copy()


def mapping_coverage_summary(
    mapping_df: pd.DataFrame,
    requirements_df: pd.DataFrame,
    hazards_df: pd.DataFrame,
) -> dict[str, int | float]:
    """Summarize link volume and hazard and requirement coverage."""
    hazard_ids = _known_ids(hazards_df, "hazard_id")
    requirement_ids = _known_ids(requirements_df, "requirement_id")
    mapped_hazards = _mapped_ids(mapping_df, "hazard_id", hazard_ids)
    mapped_requirements = _mapped_ids(mapping_df, "requirement_id", requirement_ids)
    links = 0
    if {"requirement_id", "hazard_id"}.issubset(mapping_df.columns):
        links = int(mapping_df[["requirement_id", "hazard_id"]].drop_duplicates().shape[0])
    return {
        "mapping_links": links,
        "hazards_mapped": len(mapped_hazards),
        "hazards_total": len(hazard_ids),
        "hazard_coverage_pct": round(100 * len(mapped_hazards) / len(hazard_ids), 2) if hazard_ids else 0.0,
        "requirements_mapped": len(mapped_requirements),
        "requirements_total": len(requirement_ids),
        "requirement_coverage_pct": (
            round(100 * len(mapped_requirements) / len(requirement_ids), 2) if requirement_ids else 0.0
        ),
        "critical_links": int(_critical_mask(mapping_df).sum()),
    }


def get_requirements_for_hazard(mapping_df: pd.DataFrame, hazard_id: str) -> pd.DataFrame:
    """Return mapping rows for one hazard ID."""
    if "hazard_id" not in mapping_df.columns:
        return mapping_df.iloc[0:0].copy()
    return mapping_df.loc[mapping_df["hazard_id"].astype(str).str.upper().eq(str(hazard_id).upper())].copy()


def get_hazards_for_requirement(mapping_df: pd.DataFrame, requirement_id: str) -> pd.DataFrame:
    """Return mapping rows for one requirement ID."""
    if "requirement_id" not in mapping_df.columns:
        return mapping_df.iloc[0:0].copy()
    return mapping_df.loc[mapping_df["requirement_id"].astype(str).str.upper().eq(str(requirement_id).upper())].copy()


def enrich_mapping(
    mapping_df: pd.DataFrame,
    requirements_df: pd.DataFrame,
    hazards_df: pd.DataFrame,
) -> pd.DataFrame:
    """Add requirement evidence and hazard context without changing the mapping schema."""
    requirement_columns = [
        column
        for column in ("requirement_id", "requirement", "domain", "objective_evidence", "evidence")
        if column in requirements_df
    ]
    requirement_details = (
        requirements_df[requirement_columns]
        .drop_duplicates("requirement_id")
        .rename(
            columns={
                "requirement": "requirement_wording",
                "domain": "requirement_domain",
                "evidence": "objective_evidence",
            }
        )
    )
    hazard_columns = [
        column
        for column in ("hazard_id", "hazard", "domain", "activity", "cause", "existing_controls")
        if column in hazards_df
    ]
    hazard_details = (
        hazards_df[hazard_columns]
        .drop_duplicates("hazard_id")
        .rename(
            columns={
                "hazard": "hazard_name",
                "domain": "hazard_domain",
                "activity": "hazard_activity",
                "cause": "hazard_cause",
            }
        )
    )
    return mapping_df.merge(requirement_details, on="requirement_id", how="left").merge(
        hazard_details, on="hazard_id", how="left"
    )


def hazard_mapping_ranking(mapping_df: pd.DataFrame, hazards_df: pd.DataFrame) -> pd.DataFrame:
    """Rank hazards by their number of distinct linked requirements."""
    counts = (
        mapping_df.groupby("hazard_id")["requirement_id"].nunique().rename("linked_requirements").reset_index()
        if {"hazard_id", "requirement_id"}.issubset(mapping_df.columns)
        else pd.DataFrame(columns=["hazard_id", "linked_requirements"])
    )
    details = hazards_df[
        [column for column in ("hazard_id", "hazard", "domain") if column in hazards_df]
    ].drop_duplicates("hazard_id")
    return (
        details.merge(counts, on="hazard_id", how="left")
        .fillna({"linked_requirements": 0})
        .sort_values(["linked_requirements", "hazard_id"], ascending=[False, True])
    )


def requirement_mapping_ranking(mapping_df: pd.DataFrame, requirements_df: pd.DataFrame) -> pd.DataFrame:
    """Rank requirements by their number of distinct linked hazards."""
    counts = (
        mapping_df.groupby("requirement_id")["hazard_id"].nunique().rename("linked_hazards").reset_index()
        if {"requirement_id", "hazard_id"}.issubset(mapping_df.columns)
        else pd.DataFrame(columns=["requirement_id", "linked_hazards"])
    )
    details = requirements_df[
        [column for column in ("requirement_id", "requirement", "domain") if column in requirements_df]
    ].drop_duplicates("requirement_id")
    return (
        details.merge(counts, on="requirement_id", how="left")
        .fillna({"linked_hazards": 0})
        .sort_values(["linked_hazards", "requirement_id"], ascending=[False, True])
    )


def coverage_by_requirement_domain(mapping_df: pd.DataFrame, requirements_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate requirement coverage and mapping-link counts by domain."""
    if not {"requirement_id", "domain"}.issubset(requirements_df.columns):
        return pd.DataFrame(
            columns=["requirement_domain", "requirements_linked", "requirements_total", "coverage_pct", "mapping_links"]
        )
    requirements = requirements_df[["requirement_id", "domain"]].drop_duplicates("requirement_id").copy()
    link_counts = (
        mapping_df.groupby("requirement_id")["hazard_id"].nunique().rename("mapping_links")
        if {"requirement_id", "hazard_id"}.issubset(mapping_df.columns)
        else pd.Series(dtype=int, name="mapping_links")
    )
    requirements = requirements.join(link_counts, on="requirement_id")
    requirements["mapping_links"] = requirements["mapping_links"].fillna(0).astype(int)
    requirements["linked"] = requirements["mapping_links"].gt(0)
    result = (
        requirements.groupby("domain", dropna=False)
        .agg(
            requirements_linked=("linked", "sum"),
            requirements_total=("requirement_id", "nunique"),
            mapping_links=("mapping_links", "sum"),
        )
        .reset_index()
        .rename(columns={"domain": "requirement_domain"})
    )
    result["coverage_pct"] = (100 * result["requirements_linked"] / result["requirements_total"]).round(2)
    return result[
        ["requirement_domain", "requirements_linked", "requirements_total", "coverage_pct", "mapping_links"]
    ].sort_values("requirement_domain")


def mapping_coverage_table(
    mapping_df: pd.DataFrame,
    requirements_df: pd.DataFrame,
    hazards_df: pd.DataFrame,
) -> pd.DataFrame:
    """Create a portable overall and domain-level mapping coverage table."""
    summary = mapping_coverage_summary(mapping_df, requirements_df, hazards_df)
    rows = [
        {
            "coverage_scope": "Hazards",
            "group": "All hazards",
            "linked_records": summary["hazards_mapped"],
            "total_records": summary["hazards_total"],
            "coverage_pct": summary["hazard_coverage_pct"],
            "mapping_links": summary["mapping_links"],
        },
        {
            "coverage_scope": "Requirements",
            "group": "All requirements",
            "linked_records": summary["requirements_mapped"],
            "total_records": summary["requirements_total"],
            "coverage_pct": summary["requirement_coverage_pct"],
            "mapping_links": summary["mapping_links"],
        },
    ]
    for domain in coverage_by_requirement_domain(mapping_df, requirements_df).itertuples(index=False):
        rows.append(
            {
                "coverage_scope": "Requirement domain",
                "group": domain.requirement_domain,
                "linked_records": int(domain.requirements_linked),
                "total_records": int(domain.requirements_total),
                "coverage_pct": float(domain.coverage_pct),
                "mapping_links": int(domain.mapping_links),
            }
        )
    return pd.DataFrame(rows)


def _structured_mapping_headers(mapping_df: pd.DataFrame, collector: FindingCollector) -> pd.DataFrame:
    out = mapping_df.copy()
    original = [str(column) for column in out.columns]
    bases = [column.strip().lower().replace(" ", "_").replace("-", "_") for column in original]
    used: dict[str, int] = {}
    normalized: list[str] = []
    for name in bases:
        used[name] = used.get(name, 0) + 1
        normalized.append(name if used[name] == 1 else f"{name}_{used[name]}")
    out.columns = normalized
    duplicates = sorted({name for name in bases if bases.count(name) > 1})
    if duplicates:
        collector.add(
            "Warning",
            "DUPLICATE_NORMALIZED_COLUMN",
            f"Mapping: column names become duplicates after normalization: {', '.join(duplicates)}.",
            original_value=original,
            normalized_value=normalized,
            suggested_action="Rename ambiguous source columns before upload.",
        )
    return out


def validate_mapping(
    mapping_df: pd.DataFrame,
    requirements_df: pd.DataFrame,
    hazards_df: pd.DataFrame,
    *,
    require_full_hazard_coverage: bool = True,
) -> MappingValidationResult:
    """Validate mapping rows with structured findings and explicit eligibility."""
    collector = FindingCollector("Mapping")
    out = _structured_mapping_headers(mapping_df, collector)
    if out.empty:
        collector.add(
            "Error",
            "EMPTY_DATASET",
            "Mapping: the dataset contains no data rows.",
            suggested_action="Provide at least one requirement-to-hazard link.",
            blocks_analysis=True,
        )
    if len(out.columns) and not set(MAPPING_REQUIRED_COLUMNS).intersection(out.columns):
        collector.add(
            "Error",
            "UNRECOGNIZED_DATASET_TYPE",
            "Mapping: no recognizable mapping columns were found; this may be an instruction or cover sheet.",
            original_value=list(out.columns),
            suggested_action="Select the worksheet containing the requirement-to-hazard mapping table.",
            blocks_analysis=True,
        )
    blank_rows = (
        out.apply(lambda row: all(pd.isna(value) or str(value).strip() == "" for value in row), axis=1)
        if len(out.columns)
        else pd.Series(True, index=out.index)
    )
    for index in out.index[blank_rows]:
        collector.add(
            "Error",
            "COMPLETELY_BLANK_ROW",
            f"Mapping: row {index + 2} is completely blank.",
            row_index=index,
            suggested_action="Remove the blank row or provide a complete link.",
            blocks_analysis=True,
        )
    for column in out.columns:
        if out[column].map(lambda value: pd.isna(value) or str(value).strip() == "").all():
            collector.add(
                "Warning",
                "COMPLETELY_BLANK_COLUMN",
                f"Mapping: column {column!r} is completely blank.",
                column=column,
                suggested_action="Remove the unused column or populate it if required.",
            )
    missing_columns = [column for column in MAPPING_REQUIRED_COLUMNS if column not in out.columns]
    for column in missing_columns:
        collector.add(
            "Error",
            "MISSING_REQUIRED_COLUMN",
            f"Mapping: required column {column!r} is missing.",
            column=column,
            suggested_action=f"Add the required {column} column.",
            blocks_analysis=True,
        )
    if missing_columns:
        eligibility = pd.Series(False, index=out.index)
        out = apply_validation_fields(
            out,
            collector.findings,
            analysis_eligible=eligibility,
            record_id_column="mapping_id",
            exclusion_reasons={int(index): ["Missing required mapping columns."] for index in out.index},
        )
        return MappingValidationResult(
            data=out,
            findings=collector.findings,
            quality={
                "mapping_rows": len(out),
                "missing_columns": missing_columns,
                **finding_counts(collector.findings),
            },
            missing_columns=missing_columns,
            invalid_rows=out.index.tolist(),
        )

    for column in ("mapping_id", "requirement_id", "hazard_id", "mapping_rationale", "source_status"):
        out[f"{column}_raw"] = out[column]
        out[column] = out[column].astype("string").str.strip()
    out["relationship_type_raw"] = out["relationship_type"]
    out["control_role_raw"] = out["control_role"]
    out["critical_link_raw"] = out["critical_link"]
    out["relationship_type"] = out["relationship_type"].astype("string").str.strip().str.title()
    out["control_role"] = out["control_role"].astype("string").str.strip().str.title()
    row_eligible = pd.Series(True, index=out.index, dtype=bool) & ~blank_rows

    for column in ("mapping_id", "requirement_id", "hazard_id"):
        for index, raw in out[f"{column}_raw"].items():
            normalized = out.at[index, column]
            if not pd.isna(raw) and str(raw) != str(raw).strip():
                collector.add(
                    "Warning",
                    "TRAILING_OR_LEADING_WHITESPACE",
                    f"Mapping: {column}={raw!r} at row {index + 2} contains surrounding whitespace.",
                    row_index=index,
                    record_id=out.at[index, "mapping_id"],
                    column=column,
                    original_value=raw,
                    normalized_value=normalized,
                    suggested_action="Remove surrounding whitespace from the source identifier.",
                )
            if pd.isna(normalized) or str(normalized).strip() == "":
                row_eligible.loc[index] = False
                collector.add(
                    "Error",
                    "BLANK_ID",
                    f"Mapping: row {index + 2} has a blank {column}.",
                    row_index=index,
                    record_id=out.at[index, "mapping_id"],
                    column=column,
                    original_value=raw,
                    suggested_action=f"Provide a nonblank {column}.",
                    blocks_analysis=True,
                )

    duplicate_mask = out["mapping_id"].notna() & out["mapping_id"].ne("") & out["mapping_id"].duplicated(keep=False)
    duplicate_ids = sorted(out.loc[duplicate_mask, "mapping_id"].astype(str).unique())
    for index in out.index[duplicate_mask]:
        row_eligible.loc[index] = False
        collector.add(
            "Error",
            "DUPLICATE_ID",
            f"Duplicate mapping_id {out.at[index, 'mapping_id']!r} in Mapping.",
            row_index=index,
            record_id=out.at[index, "mapping_id"],
            column="mapping_id",
            original_value=out.at[index, "mapping_id_raw"],
            normalized_value=out.at[index, "mapping_id"],
            suggested_action="Assign a unique mapping_id to each link.",
            blocks_analysis=True,
        )
    pair_present = out["requirement_id"].notna() & out["hazard_id"].notna()
    duplicate_pairs = pair_present & out.duplicated(["requirement_id", "hazard_id"], keep=False)
    for index in out.index[duplicate_pairs]:
        row_eligible.loc[index] = False
        collector.add(
            "Error",
            "DUPLICATE_MAPPING_PAIR",
            f"Duplicate requirement-hazard pair {out.at[index, 'requirement_id']}+{out.at[index, 'hazard_id']} in Mapping.",
            row_index=index,
            record_id=out.at[index, "mapping_id"],
            column="requirement_id/hazard_id",
            original_value=f"{out.at[index, 'requirement_id_raw']}+{out.at[index, 'hazard_id_raw']}",
            suggested_action="Keep only one row for each requirement-hazard pair.",
            blocks_analysis=True,
        )

    requirement_ids = set(requirements_df.get("requirement_id", pd.Series(dtype=str)).dropna().astype(str).str.strip())
    hazard_ids = set(hazards_df.get("hazard_id", pd.Series(dtype=str)).dropna().astype(str).str.strip())
    for column, known_ids, code in (
        ("requirement_id", requirement_ids, "UNKNOWN_REQUIREMENT_ID"),
        ("hazard_id", hazard_ids, "UNKNOWN_HAZARD_ID"),
    ):
        for index, value in out[column].items():
            if pd.isna(value) or str(value) == "":
                continue
            text = str(value)
            if text not in known_ids:
                case_match = next((known for known in known_ids if known.casefold() == text.casefold()), None)
                row_eligible.loc[index] = False
                collector.add(
                    "Error",
                    "CASE_ONLY_ID_MISMATCH" if case_match else code,
                    (
                        f"{'Unknown requirement ID' if column == 'requirement_id' else 'Unknown hazard ID'} "
                        f"{text!r} in Mapping row {out.at[index, 'mapping_id']}; it does not exactly match a known record."
                    ),
                    row_index=index,
                    record_id=out.at[index, "mapping_id"],
                    column=column,
                    original_value=out.at[index, f"{column}_raw"],
                    normalized_value=case_match or text,
                    suggested_action=f"Use an existing exact {column} value.",
                    blocks_analysis=True,
                )

    for index, value in out["mapping_rationale"].items():
        if pd.isna(value) or str(value).strip() == "":
            row_eligible.loc[index] = False
            collector.add(
                "Error",
                "EMPTY_REQUIRED_TEXT",
                f"Mapping row {out.at[index, 'mapping_id']} has missing rationale.",
                row_index=index,
                record_id=out.at[index, "mapping_id"],
                column="mapping_rationale",
                original_value=out.at[index, "mapping_rationale_raw"],
                suggested_action="Explain why the requirement is linked to the hazard.",
                blocks_analysis=True,
            )
    for column, allowed, code in (
        ("relationship_type", set(ALLOWED_RELATIONSHIP_TYPES), "INVALID_RELATIONSHIP_TYPE"),
        ("control_role", set(ALLOWED_CONTROL_ROLES), "INVALID_CONTROL_ROLE"),
    ):
        invalid = ~out[column].isin(allowed)
        for index in out.index[invalid]:
            row_eligible.loc[index] = False
            collector.add(
                "Error",
                code,
                f"Invalid {'relationship type' if column == 'relationship_type' else 'control role'} "
                f"{out.at[index, column]!r} for Mapping row {out.at[index, 'mapping_id']}.",
                row_index=index,
                record_id=out.at[index, "mapping_id"],
                column=column,
                original_value=out.at[index, f"{column}_raw"],
                normalized_value=out.at[index, column],
                suggested_action=f"Use one of: {', '.join(sorted(allowed))}.",
                blocks_analysis=True,
            )

    critical_text = out["critical_link_raw"].astype("string").str.strip().str.lower()
    true_values, false_values = {"true", "1", "yes", "y"}, {"false", "0", "no", "n"}
    parsed_critical = pd.Series(pd.NA, index=out.index, dtype="boolean")
    parsed_critical.loc[critical_text.isin(true_values)] = True
    parsed_critical.loc[critical_text.isin(false_values)] = False
    invalid_critical = ~critical_text.isin(true_values | false_values)
    for index in out.index[invalid_critical]:
        row_eligible.loc[index] = False
        code = (
            "BLANK_CRITICAL_LINK"
            if pd.isna(out.at[index, "critical_link_raw"]) or str(out.at[index, "critical_link_raw"]).strip() == ""
            else "INVALID_BOOLEAN"
        )
        collector.add(
            "Error",
            code,
            (
                f"Mapping row {out.at[index, 'mapping_id']} has a blank critical_link."
                if code == "BLANK_CRITICAL_LINK"
                else f"Mapping: critical_link={out.at[index, 'critical_link_raw']!r} is invalid for {out.at[index, 'mapping_id']}."
            ),
            row_index=index,
            record_id=out.at[index, "mapping_id"],
            column="critical_link",
            original_value=out.at[index, "critical_link_raw"],
            suggested_action="Use TRUE/FALSE, yes/no, y/n, or 1/0.",
            blocks_analysis=True,
        )
    out["critical_link"] = parsed_critical

    invalid_source = out["source_status"].ne(REPRESENTATIVE_SOURCE_STATUS)
    for index in out.index[invalid_source]:
        row_eligible.loc[index] = False
        collector.add(
            "Error",
            "UNKNOWN_SOURCE_STATUS",
            f"Mapping: source_status={out.at[index, 'source_status']!r} is not recognized for {out.at[index, 'mapping_id']}.",
            row_index=index,
            record_id=out.at[index, "mapping_id"],
            column="source_status",
            original_value=out.at[index, "source_status_raw"],
            normalized_value=out.at[index, "source_status"],
            suggested_action=f"Use {REPRESENTATIVE_SOURCE_STATUS!r} for the demonstration mapping.",
            blocks_analysis=True,
        )

    eligible_mapping = out.loc[row_eligible]
    mapped_hazards = set(eligible_mapping["hazard_id"].dropna().astype(str)) & hazard_ids
    mapped_requirements = set(eligible_mapping["requirement_id"].dropna().astype(str)) & requirement_ids
    for hazard_id in sorted(hazard_ids - mapped_hazards):
        collector.add(
            "Error" if require_full_hazard_coverage else "Warning",
            "UNMAPPED_HAZARD",
            f"Mapping: hazard {hazard_id} has no eligible linked requirement.",
            record_id=hazard_id,
            column="hazard_id",
            suggested_action="Add at least one valid mapping link for the hazard.",
            blocks_analysis=require_full_hazard_coverage,
        )
    for requirement_id in sorted(requirement_ids - mapped_requirements):
        collector.add(
            "Warning",
            "UNMAPPED_REQUIREMENT",
            f"Requirements without linked hazards: {requirement_id}.",
            record_id=requirement_id,
            column="requirement_id",
            suggested_action="Review whether a representative hazard link should be added.",
        )
    hazard_link_counts = eligible_mapping.groupby("hazard_id")["requirement_id"].nunique()
    requirement_link_counts = eligible_mapping.groupby("requirement_id")["hazard_id"].nunique()
    for hazard_id, count in hazard_link_counts.items():
        collector.add(
            "Information",
            "HAZARD_LINK_COUNT",
            f"Mapping: hazard {hazard_id} has {int(count)} distinct linked requirement(s).",
            record_id=hazard_id,
            column="hazard_id",
            normalized_value=int(count),
            suggested_action="Review link density as part of coverage analysis.",
        )
    for requirement_id, count in requirement_link_counts.items():
        collector.add(
            "Information",
            "REQUIREMENT_LINK_COUNT",
            f"Mapping: requirement {requirement_id} has {int(count)} distinct linked hazard(s).",
            record_id=requirement_id,
            column="requirement_id",
            normalized_value=int(count),
            suggested_action="Review link density as part of coverage analysis.",
        )
    exclusion = {
        int(index): ["Mapping row has one or more blocking validation findings."] for index in out.index[~row_eligible]
    }
    out = apply_validation_fields(
        out,
        collector.findings,
        analysis_eligible=row_eligible,
        record_id_column="mapping_id",
        exclusion_reasons=exclusion,
    )
    invalid_rows = sorted(int(index) for index in out.index[~row_eligible])
    quality = {
        "mapping_rows": len(out),
        "unique_mapping_ids": int(out["mapping_id"].nunique()),
        "unique_requirement_hazard_pairs": int(out[["requirement_id", "hazard_id"]].drop_duplicates().shape[0]),
        "hazards_mapped": len(mapped_hazards),
        "hazards_total": len(hazard_ids),
        "requirements_mapped": len(mapped_requirements),
        "requirements_total": len(requirement_ids),
        "critical_links": int(out["critical_link"].fillna(False).sum()),
        "analysis_eligible_records": int(row_eligible.sum()),
        "excluded_records": int((~row_eligible).sum()),
        **finding_counts(collector.findings),
    }
    return MappingValidationResult(
        data=out,
        findings=collector.findings,
        quality=quality,
        missing_columns=missing_columns,
        duplicate_ids=duplicate_ids,
        invalid_rows=invalid_rows,
    )
