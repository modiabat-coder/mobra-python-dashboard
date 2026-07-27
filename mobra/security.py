"""Security helpers for portable exports, archives, and project-local assets."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
import re
from typing import Any

import pandas as pd


_SPREADSHEET_FORMULA_PREFIXES = ("=", "+", "-", "@")
_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")


def spreadsheet_safe_value(value: Any) -> Any:
    """Neutralize formulas in text cells while preserving numeric values."""
    if not isinstance(value, str):
        return value
    stripped = value.lstrip()
    if (
        value.startswith(("\t", "\r", "\n"))
        or (stripped and stripped.startswith(_SPREADSHEET_FORMULA_PREFIXES))
    ):
        return f"'{value}"
    return value


def spreadsheet_safe_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Return an export copy with formula-like text cells neutralized."""
    safe = frame.copy()
    for column in safe.columns:
        safe[column] = safe[column].map(spreadsheet_safe_value)
    return safe


def safe_archive_name(name: str) -> str:
    """Return a portable ZIP member name or reject an unsafe path."""
    normalized = str(name).replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or "\x00" in normalized
        or path.is_absolute()
        or _DRIVE_PREFIX.match(normalized)
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"Unsafe archive member name: {name!r}.")
    return path.as_posix()


def resolve_within(root: Path, value: str | Path) -> Path:
    """Resolve a path and require it to remain inside ``root``."""
    trusted_root = root.resolve()
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = trusted_root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(trusted_root)
    except ValueError as exc:
        raise ValueError(f"Path must remain inside {trusted_root}.") from exc
    return resolved
