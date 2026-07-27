"""Portable input helpers for CSV, Excel, and JSON assessment files."""

from __future__ import annotations

import io
import json
import csv
from pathlib import Path
from typing import Any

import pandas as pd

from .config import MAX_UPLOAD_BYTES, SUPPORTED_EXTENSIONS


def _duplicate_headers(values: list[object]) -> list[str]:
    """Return duplicate non-empty header names using case-insensitive comparison."""
    seen: dict[str, str] = {}
    duplicates: set[str] = set()
    for value in values:
        label = str(value or "").strip()
        if not label:
            continue
        key = label.casefold()
        if key in seen:
            duplicates.add(seen[key])
        else:
            seen[key] = label
    return sorted(duplicates)


def _raise_for_duplicate_headers(values: list[object]) -> None:
    duplicates = _duplicate_headers(values)
    if duplicates:
        raise ValueError(
            "The source table contains duplicate column names: "
            + ", ".join(duplicates)
            + ". Rename each column uniquely before import."
        )


def _known_source_size(source: Any) -> int | None:
    """Return a source size without reading its contents when possible."""
    if isinstance(source, (bytes, bytearray)):
        return len(source)
    if isinstance(source, (str, Path)):
        return Path(source).stat().st_size
    size = getattr(source, "size", None)
    if isinstance(size, int):
        return size
    if hasattr(source, "getbuffer"):
        try:
            return int(source.getbuffer().nbytes)
        except (AttributeError, TypeError, ValueError):
            return None
    return None


def _raise_for_oversized_source(size: int | None) -> None:
    if size is not None and size > MAX_UPLOAD_BYTES:
        limit_mb = MAX_UPLOAD_BYTES // (1024 * 1024)
        raise ValueError(
            f"The selected file exceeds {limit_mb} MB. "
            "Split it into smaller assessment files before import."
        )


def source_bytes(source: Any) -> bytes:
    """Return bytes from a path, uploaded-file object, or bytes-like value."""
    _raise_for_oversized_source(_known_source_size(source))
    if isinstance(source, bytes):
        data = source
    elif isinstance(source, bytearray):
        data = bytes(source)
    elif isinstance(source, (str, Path)):
        data = Path(source).read_bytes()
    elif hasattr(source, "getvalue"):
        data = source.getvalue()
    elif hasattr(source, "read"):
        position = source.tell() if hasattr(source, "tell") else None
        data = source.read()
        if position is not None and hasattr(source, "seek"):
            source.seek(position)
    else:
        raise TypeError("Expected a file path, bytes, or an uploaded file object.")
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("The selected file did not provide binary content.")
    result = bytes(data)
    _raise_for_oversized_source(len(result))
    return result


def source_name(source: Any, fallback: str = "uploaded_file") -> str:
    """Get a useful display name for a file-like input."""
    if hasattr(source, "name"):
        return Path(str(source.name)).name
    if isinstance(source, (str, Path)):
        return Path(source).name
    return fallback


def list_excel_sheets(source: Any) -> list[str]:
    """Return worksheet names for XLS or XLSX input."""
    name = source_name(source).lower()
    if not name.endswith((".xlsx", ".xls")):
        return []
    data = source_bytes(source)
    engine = "xlrd" if name.endswith(".xls") else "openpyxl"
    return pd.ExcelFile(io.BytesIO(data), engine=engine).sheet_names


def auto_detect_excel_sheet(source: Any, kind: str) -> str | None:
    """Select the worksheet whose headers best match a MOBRA dataset kind."""
    sheets = list_excel_sheets(source)
    if not sheets:
        return None
    from .validation import (
        HAZARD_ALIASES,
        REQUIREMENT_ALIASES,
        normalise_columns,
    )

    if kind == "hazards":
        expected = set(HAZARD_ALIASES)
    elif kind == "requirements":
        expected = set(REQUIREMENT_ALIASES)
    else:
        expected = {"record_type", *HAZARD_ALIASES, *REQUIREMENT_ALIASES}
    best_sheet, best_score = sheets[0], -1
    for sheet in sheets:
        try:
            preview = read_data_file(source, sheet_name=sheet)
            headers = set(normalise_columns(preview.head(0)).columns)
            score = len(headers & expected)
            if "record_type" in headers and kind == "unified":
                score += 6
        except (ValueError, OSError):
            score = -1
        if score > best_score:
            best_sheet, best_score = sheet, score
    return best_sheet


def _json_collections(payload: object) -> list[tuple[str, list[object]]]:
    """Find record collections without discarding their JSON paths."""
    found: list[tuple[str, list[object]]] = []

    def visit(value: object, path: str, depth: int) -> None:
        if depth > 8:
            return
        if isinstance(value, list):
            if value and all(isinstance(item, dict) for item in value):
                found.append((path or "$", value))
            return
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, f"{path}.{key}" if path else str(key), depth + 1)

    visit(payload, "", 0)
    return found


def _records_to_frame(records: list[object], path: str) -> pd.DataFrame:
    """Flatten one record collection while preserving non-scalar nested values."""
    frame = pd.json_normalize(records, sep=".")
    if frame.empty:
        raise ValueError(f"The JSON record collection at {path!r} is empty.")
    if frame.columns.duplicated().any():
        duplicates = frame.columns[frame.columns.duplicated()].tolist()
        raise ValueError(
            "JSON normalization produced duplicate fields: "
            + ", ".join(map(str, duplicates))
            + ". Rename the conflicting fields before import."
        )
    for column in frame.columns:
        nested = frame[column].map(lambda value: isinstance(value, (list, dict)))
        if nested.any():
            frame.loc[nested, column] = frame.loc[nested, column].map(
                lambda value: json.dumps(value, ensure_ascii=False)
            )
    return frame


def read_json_collections(source: Any) -> dict[str, pd.DataFrame]:
    """Return every safe tabular record collection detected in a JSON file."""
    data = source_bytes(source)
    if not data:
        raise ValueError("The JSON file is empty.")
    try:
        payload = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            "The JSON file is not valid UTF-8 JSON. Save it as UTF-8 and check commas, quotes, and brackets."
        ) from exc
    if isinstance(payload, list):
        if not payload:
            raise ValueError("The JSON file contains an empty top-level list.")
        if not all(isinstance(item, dict) for item in payload):
            raise ValueError(
                "A top-level JSON list must contain record objects, not isolated scalar values."
            )
    if isinstance(payload, dict):
        if all(not isinstance(value, (list, dict)) for value in payload.values()):
            return {"$": pd.json_normalize([payload], sep=".")}
    candidates = _json_collections(payload)
    if not candidates:
        raise ValueError(
            "No safe record collection was found. Provide a list of record objects "
            "or a dictionary containing a nested list such as records, data, hazards, or requirements."
        )
    return {
        path: _records_to_frame(records, path)
        for path, records in candidates
    }


def _read_json(data: bytes) -> pd.DataFrame:
    """Read the most suitable tabular collection from a JSON payload."""
    collections = read_json_collections(data)
    preferred_names = ("records", "data", "rows", "hazards", "requirements")
    ranked = sorted(
        collections.items(),
        key=lambda item: (
            any(item[0].lower().endswith(name) for name in preferred_names),
            len(item[1]),
            len(item[1].columns),
        ),
        reverse=True,
    )
    return ranked[0][1]


def read_data_file(
    source: Any,
    *,
    name: str | None = None,
    sheet_name: str | int = 0,
) -> pd.DataFrame:
    """Read CSV, XLSX, XLS, or JSON with safe encoding and worksheet handling."""
    filename = (name or source_name(source)).lower()
    if not filename.endswith(SUPPORTED_EXTENSIONS):
        raise ValueError("Supported formats are CSV, XLSX, XLS, and JSON.")
    data = source_bytes(source)
    if not data:
        raise ValueError("The selected file is empty.")
    if filename.endswith(".json"):
        return _read_json(data)
    if filename.endswith(".csv"):
        last_error: UnicodeDecodeError | None = None
        for encoding in ("utf-8-sig", "utf-8", "cp1256", "latin-1"):
            try:
                text = data.decode(encoding)
                header = next(csv.reader(io.StringIO(text)), [])
                if not header:
                    raise ValueError("The CSV file has no header row.")
                _raise_for_duplicate_headers(header)
                frame = pd.read_csv(io.StringIO(text))
                if frame.empty:
                    raise ValueError("The CSV file contains headers but no data records.")
                return frame
            except UnicodeDecodeError as exc:
                last_error = exc
        raise ValueError(
            "The CSV file could not be decoded using UTF-8 or supported fallbacks."
        ) from last_error
    engine = "xlrd" if filename.endswith(".xls") else "openpyxl"
    try:
        frame = pd.read_excel(
            io.BytesIO(data),
            sheet_name=sheet_name,
            engine=engine,
        )
        if frame.empty:
            raise ValueError(
                f"The Excel worksheet {sheet_name!r} contains no data records."
            )
        _raise_for_duplicate_headers(frame.columns.tolist())
        return frame
    except (ValueError, OSError) as exc:
        raise ValueError(
            f"The Excel worksheet {sheet_name!r} could not be read. "
            "Choose another worksheet or verify the workbook."
        ) from exc


def split_unified_file(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split a unified file into hazard and requirement records."""
    from .validation import normalise_columns

    normalized = normalise_columns(df)
    type_column = next(
        (column for column in ("record_type", "record_kind", "dataset") if column in normalized),
        None,
    )
    if type_column:
        values = normalized[type_column].astype(str).str.strip().str.lower()
        hazard_mask = values.str.contains("hazard|risk", regex=True, na=False)
        requirement_mask = values.str.contains(
            "requirement|orl|control",
            regex=True,
            na=False,
        )
        hazards = normalized.loc[hazard_mask].copy()
        requirements = normalized.loc[requirement_mask].copy()
        if hazards.empty or requirements.empty:
            raise ValueError(
                "The unified record_type field must contain at least one hazard "
                "and one requirement record."
            )
        return hazards, requirements

    hazard_columns = {"hazard", "likelihood", "consequence"}
    requirement_columns = {"requirement", "observed_score", "maximum_score"}
    if hazard_columns.issubset(normalized.columns) and requirement_columns.issubset(
        normalized.columns
    ):
        hazard_mask = normalized["hazard"].notna() | normalized["likelihood"].notna()
        requirement_mask = (
            normalized["requirement"].notna()
            | normalized["observed_score"].notna()
        )
        hazards = normalized.loc[hazard_mask].copy()
        requirements = normalized.loc[requirement_mask].copy()
        if hazards.empty or requirements.empty:
            raise ValueError(
                "The unified file did not contain rows for both required record types."
            )
        return hazards, requirements
    raise ValueError(
        "A unified file needs a record_type field or both the hazard and "
        "requirement field sets on separate rows."
    )
