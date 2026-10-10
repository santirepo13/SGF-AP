"""Discover and execute the complete SGF-AP pytest suite.

Usage from the project root::

    python3 tests/coverage.py
    python3 tests/coverage.py --integration
    python3 tests/coverage.py --unit-only
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import shutil

TESTS_DIR = Path(__file__).resolve().parent
TEST_FILES = tuple(sorted(TESTS_DIR.glob("test_*.py")))


def _pytest_command(arguments: list[str]) -> list[str]:
    try:
        import pytest  # noqa: F401
    except ModuleNotFoundError:
        pytest_executable = shutil.which("pytest")
        if pytest_executable is None:
            raise RuntimeError("pytest is not installed; run: python -m pip install -r tests/requirements.txt")
        return [pytest_executable, "-vv", *arguments, *(str(path) for path in TEST_FILES)]
    return [sys.executable, "-m", "pytest", "-vv", *arguments, *(str(path) for path in TEST_FILES)]


def run_all_tests(arguments: list[str] | None = None) -> int:
    """Run every discovered test once and return the process status."""
    arguments = list(arguments or [])
    if "--integration" in arguments:
        arguments.remove("--integration")
        os.environ["RUN_POSTGRES_INTEGRATION"] = "1"
    if "--unit-only" in arguments:
        arguments.remove("--unit-only")
        arguments.extend(["-m", "not integration"])

    return subprocess.run(_pytest_command(arguments), cwd=TESTS_DIR.parent, check=False).returncode


if __name__ == "__main__":
    sys.exit(run_all_tests(sys.argv[1:]))
