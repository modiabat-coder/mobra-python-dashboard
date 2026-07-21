"""Input/output helpers for CSV and Excel files."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, BinaryIO

import pandas as pd


SUPPORTED_EXTENSIONS = (".csv", ".xlsx", ".xls")


def _source_bytes(source: Any) -> bytes:
    """Return bytes from a path, uploaded-file object, or bytes-like value."""
    if isinstance(source, bytes):
        return source
    if isinstance(source, bytearray):
        return bytes(source)
    if isinstance(source, (str, Path)):
        return Path(source).read_bytes()
    if hasattr(source, "getvalue"):
        return source.getvalue()
    if hasattr(source, "read"):
        position = source.tell() if hasattr(source, "tell") else None
        data = source.read()
        if position is not None and hasattr(source, "seek"):
            source.seek(position)
        return data
    raise TypeError("Expected a file path, bytes, or an uploaded file object.")


def source_name(source: Any, fallback: str = "uploaded_file") -> str:
    """Get a useful display name for a file-like input."""
    if hasattr(source, "name"):
        return Path(str(source.name)).name
    if isinstance(source, (str, Path)):
        return Path(source).name
    return fallback


def list_excel_sheets(source: Any) -> list[str]:
    """Return sheet names for XLS/XLSX input."""
    name = source_name(source).lower()
    if not name.endswith((".xlsx", ".xls")):
        return []
    data = _source_bytes(source)
    engine = "xlrd" if name.endswith(".xls") else "openpyxl"
    return pd.ExcelFile(io.BytesIO(data), engine=engine).sheet_names


def read_data_file(source: Any, *, name: str | None = None, sheet_name: str | int = 0) -> pd.DataFrame:
    """Read CSV, XLSX, or XLS data with encoding fallbacks.

    ``source`` can be a ``Path``, bytes, or a Streamlit UploadedFile. Excel
    sheet selection is explicit and defaults to the first sheet.
    """
    filename = (name or source_name(source)).lower()
    if not filename.endswith(SUPPORTED_EXTENSIONS):
        raise ValueError("Supported formats are CSV, XLSX, and XLS.")
    data = _source_bytes(source)
    if filename.endswith(".csv"):
        last_error: UnicodeDecodeError | None = None
        for encoding in ("utf-8-sig", "utf-8", "cp1256", "latin-1"):
            try:
                return pd.read_csv(io.BytesIO(data), encoding=encoding)
            except UnicodeDecodeError as exc:
                last_error = exc
        raise ValueError("Could not decode the CSV file with UTF-8 or common fallbacks.") from last_error
    engine = "xlrd" if filename.endswith(".xls") else "openpyxl"
    try:
        return pd.read_excel(io.BytesIO(data), sheet_name=sheet_name, engine=engine)
    except ValueError as exc:
        raise ValueError(f"Could not read Excel sheet {sheet_name!r}: {exc}") from exc


def split_unified_file(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split a unified file into hazards and requirements.

    A ``record_type``/``record_type`` column is preferred. If absent, rows are
    inferred from the presence of hazard versus requirement fields. The
    original columns are not modified.
    """
    from .validation import normalise_columns

    normalized = normalise_columns(df)
    type_column = next((c for c in ("record_type", "record_kind", "dataset") if c in normalized), None)
    if type_column:
        values = normalized[type_column].astype(str).str.strip().str.lower()
        hazard_mask = values.str.contains("hazard|risk", regex=True, na=False)
        requirement_mask = values.str.contains("requirement|orl|control", regex=True, na=False)
        hazards, requirements = normalized.loc[hazard_mask].copy(), normalized.loc[requirement_mask].copy()
        if hazards.empty or requirements.empty:
            raise ValueError("Unified record_type must contain at least one hazard row and one requirement row.")
        return hazards, requirements

    hazard_columns = {"hazard", "likelihood", "consequence"}
    requirement_columns = {"requirement", "observed_score", "maximum_score"}
    has_hazard = hazard_columns.issubset(normalized.columns)
    has_requirement = requirement_columns.issubset(normalized.columns)
    if has_hazard and has_requirement:
        hazard_mask = normalized["hazard"].notna() | normalized["likelihood"].notna()
        requirement_mask = normalized["requirement"].notna() | normalized["observed_score"].notna()
        hazards, requirements = normalized.loc[hazard_mask].copy(), normalized.loc[requirement_mask].copy()
        if hazards.empty or requirements.empty:
            raise ValueError("Unified file inference found no rows for one of the two required record types.")
        return hazards, requirements
    raise ValueError(
        "Unified files need a record_type column (hazard/requirement) or both hazard and requirement field sets."
    )
