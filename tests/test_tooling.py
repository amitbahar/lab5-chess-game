"""The linter, formatter and type checker pass, so they can be part of every test run."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent


@pytest.mark.parametrize(
    "command",
    [
        ["ruff", "check", "."],
        ["ruff", "format", "--check", "."],
        ["mypy"],
    ],
    ids=["lint", "format", "types"],
)
def test_tool_passes(command):
    result = subprocess.run(
        [sys.executable, "-m", *command], cwd=ROOT, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
