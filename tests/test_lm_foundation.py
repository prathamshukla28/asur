"""LM00 foundation: the Life Mentor package skeleton, charter, and wiring."""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
LM = REPO / "life_mentor"

PLACEHOLDER_SUBPACKAGES = (
    "health",
    "finance",
    "career",
    "lifestyle",
    "decision_engine",
    "tracking",
    "reports",
    "integrations",
)
BUILT_SUBPACKAGES = ("profile", "security", "research")


def test_import_life_mentor_in_fresh_interpreter() -> None:
    out = subprocess.run(
        [sys.executable, "-c", "import life_mentor; print(life_mentor.DISPLAY_NAME)"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "Life Mentor"


@pytest.mark.parametrize("name", BUILT_SUBPACKAGES + PLACEHOLDER_SUBPACKAGES)
def test_subpackage_importable_with_docstring(name: str) -> None:
    mod = importlib.import_module(f"life_mentor.{name}")
    assert mod.__doc__ and mod.__doc__.strip(), f"life_mentor.{name} lacks a docstring"


@pytest.mark.parametrize("name", PLACEHOLDER_SUBPACKAGES)
def test_placeholder_docstring_names_its_phase(name: str) -> None:
    mod = importlib.import_module(f"life_mentor.{name}")
    assert "LM0" in (mod.__doc__ or "") or "LM1" in (mod.__doc__ or "")


def test_rules_directory_reserved() -> None:
    assert (LM / "rules").is_dir()


def test_charter_states_invariants_and_exclusions() -> None:
    charter = (LM / "docs" / "CHARTER.md").read_text(encoding="utf-8")
    low = charter.casefold()
    for needle in (
        "~/.life_mentor",
        "life_mentor_home",
        "verified",
        "user_estimate",
        "assumption",
        "unknown",
        "hold",
        "block",
        "no diagnosis",
        "no transactions",
        "no guaranteed returns",
        "no network",
        "filevault",
        "hash-chained",
        "consent",
    ):
        assert needle in low, f"CHARTER.md missing {needle!r}"


def test_pyproject_includes_life_mentor() -> None:
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    # weekly_tracker joined the include list (weekly tracker task); life_mentor stays included.
    assert 'include = ["asur*", "life_mentor*", "weekly_tracker*"]' in text


def test_ci_import_check_and_mypy_cover_life_mentor() -> None:
    ci = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "import life_mentor" in ci
    assert "mypy asur life_mentor" in ci


def test_docs_dir_not_duplicated_outside_package() -> None:
    # Approved decision 1: docs live only at life_mentor/docs/.
    assert not (REPO / "docs" / "life_mentor").exists()


def test_open_questions_has_lm_gaps() -> None:
    text = (REPO / "docs" / "build" / "OPEN_QUESTIONS.md").read_text(encoding="utf-8")
    for gap in ("| LM-G1 |", "| LM-G2 |", "| LM-G3 |", "| LM-G4 |"):
        assert gap in text


def test_deferred_and_changelog_mention_life_mentor() -> None:
    deferred = (REPO / "DEFERRED.md").read_text(encoding="utf-8")
    assert "cryptography" in deferred and "Life Mentor" in deferred
    changelog = (REPO / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")
    unreleased = changelog.split("## [Unreleased]", 1)[1]
    assert "LM00" in unreleased and "LM03" in unreleased


def test_importing_life_mentor_pulls_no_network_module() -> None:
    code = (
        "import sys\n"
        "before=set(sys.modules)\n"
        "import life_mentor, life_mentor.profile, life_mentor.security, life_mentor.research\n"
        "new={m.split('.')[0] for m in set(sys.modules)-before}\n"
        "bad=new & {'socket','ssl','http','urllib','requests','httpx','aiohttp','urllib3'}\n"
        "print(sorted(bad))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True,
        check=False, timeout=60,
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "[]"
