"""Mypy is a blocking CI gate for the asur package (DEFERRED 'Type safety').

CI used to run `mypy asur || true` (advisory). Once the asur package type-checked
clean the gate was made blocking and scoped to asur (life_mentor/weekly_tracker
stay advisory, not asur's concern). These tests pin that contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# tomllib is stdlib only on Python >= 3.11; on 3.10 skip this module's config checks.
tomllib = pytest.importorskip("tomllib")

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CI_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_PYPROJECT = _REPO_ROOT / "pyproject.toml"


def _ci_mypy_line() -> str:
    lines = _CI_WORKFLOW.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if "name: Mypy" in line:
            return lines[i + 1]
    raise AssertionError("no 'name: Mypy' step found in ci.yml")


def test_ci_mypy_step_is_blocking_and_asur_scoped() -> None:
    run = _ci_mypy_line()
    assert "mypy asur" in run
    assert "|| true" not in run


def test_pyproject_has_a_mypy_config() -> None:
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    assert "mypy" in data.get("tool", {})
