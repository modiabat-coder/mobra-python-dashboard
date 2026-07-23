"""Run the complete local MOBRA quality gate on any supported platform."""

from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_OUTPUTS = ("coverage.xml", "MOBRA_Demo_Report.html")
REQUIRED_MODULES = (
    "black",
    "hypothesis",
    "jinja2",
    "numpy",
    "openpyxl",
    "pandas",
    "plotly",
    "pytest",
    "pytest_cov",
    "ruff",
    "streamlit",
    "xlrd",
)


def run(label: str, command: list[str]) -> None:
    """Run one required verification step and stop on failure."""
    print(f"\n== {label} ==", flush=True)
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def check_dependencies() -> None:
    """Import every runtime and development dependency needed by verification."""
    print("\n== Dependency check ==", flush=True)
    failures: list[str] = []
    for module_name in REQUIRED_MODULES:
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            failures.append(f"{module_name}: {exc}")
            continue
        version = getattr(module, "__version__", "installed")
        print(f"{module_name}: {version}")
    if failures:
        raise RuntimeError("Missing dependencies:\n" + "\n".join(failures))


def check_outputs() -> None:
    """Require nonempty coverage and demonstration-report artifacts."""
    print("\n== Required outputs ==", flush=True)
    for relative_path in REQUIRED_OUTPUTS:
        path = PROJECT_ROOT / relative_path
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"Required output is missing or empty: {relative_path}")
        print(f"{relative_path}: {path.stat().st_size:,} bytes")


def main() -> int:
    print(f"Python {sys.version.split()[0]} ({sys.executable})")
    try:
        check_dependencies()
        run("Ruff", [sys.executable, "-m", "ruff", "check", "."])
        run("Black", [sys.executable, "-m", "black", "--check", "."])
        run(
            "Pytest and coverage",
            [
                sys.executable,
                "-m",
                "pytest",
                "--cov=mobra",
                "--cov=app",
                "--cov-report=term-missing",
                "--cov-report=xml",
            ],
        )
        run("Demonstration report", [sys.executable, "generate_demo_report.py"])
        check_outputs()
        if shutil.which("git"):
            run("Git whitespace check", ["git", "diff", "--check"])
        else:
            print("\nGit is not available; skipped git diff --check.")
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"\nVerification failed: {exc}", file=sys.stderr)
        return 1
    print("\nMOBRA project verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
