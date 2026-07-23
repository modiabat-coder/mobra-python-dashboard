"""Local-only repository safety and hostile-input checks."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from mobra.io import read_data_file_with_validation
from mobra.validation_exports import invalid_records_workbook_bytes

pytestmark = pytest.mark.security


def _tracked_files(repo_root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    return [repo_root / item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def test_no_environment_file_is_tracked(repo_root: Path) -> None:
    tracked = _tracked_files(repo_root)
    assert not any(path.name == ".env" or path.name.startswith(".env.") for path in tracked)


def test_no_common_secret_pattern_in_tracked_source(repo_root: Path) -> None:
    patterns = [
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"sk-[A-Za-z0-9]{20,}"),
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        re.compile(r"(?i)(?:api[_-]?key|secret[_-]?key)\s*[:=]\s*['\"][^'\"]{12,}['\"]"),
    ]
    findings: list[str] = []
    for path in _tracked_files(repo_root):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".py", ".md", ".toml", ".yml", ".yaml", ".ps1"}:
            continue
        if path.name == "test_security.py":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in patterns):
            findings.append(str(path.relative_to(repo_root)))
    assert findings == []


def test_sample_data_contains_only_approved_demonstration_files(repo_root: Path) -> None:
    sample = repo_root / "sample_data"
    approved = {
        "critical_control_profile.csv",
        "hazards_sample.csv",
        "hazards_template.csv",
        "requirement_hazard_mapping.csv",
        "requirements_sample.csv",
        "requirements_template.csv",
    }
    assert {path.name for path in sample.iterdir() if path.is_file()} == approved
    prohibited_columns = {
        "patient_name",
        "person_name",
        "email",
        "phone",
        "address",
        "national_id",
        "medical_record_number",
    }
    for path in sample.glob("*.csv"):
        columns = {str(column).strip().lower() for column in pd.read_csv(path, nrows=0).columns}
        assert not columns & prohibited_columns


def test_uploaded_macro_workbook_is_rejected_without_execution() -> None:
    marker = {"executed": False}
    result = read_data_file_with_validation(b"not executable", name="hostile.xlsm")
    assert not result.ok
    assert result.findings[0].code == "UNSUPPORTED_FILE_TYPE"
    assert marker["executed"] is False


@pytest.mark.io
def test_export_bytes_cannot_escape_temporary_directory(tmp_path: Path) -> None:
    before = set(tmp_path.parent.iterdir())
    payload = invalid_records_workbook_bytes([], [], {})
    requested_name = "../../outside.xlsx"
    safe_target = tmp_path / Path(requested_name).name
    safe_target.write_bytes(payload)
    after = set(tmp_path.parent.iterdir())
    assert safe_target.resolve().parent == tmp_path.resolve()
    assert after == before
