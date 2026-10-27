"""Boundary import-linter (ADR-0002, SPEC-GAP G7, ASUR-LOCAL-01).

The stdlib-only layers (core + SCRIPT, and later VIRAL CHECK / ORCHESTRATOR /
FIREWALL) must import ONLY the Python standard library or other `asur.*` modules.
No third-party packages, no media libraries, and no network-I/O modules may be
imported by these layers. If this test fails, a stdlib-only install would break.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

STDLIB_ONLY_PACKAGES = (
    "core",
    "script",
    "orchestrator",
    "tools",
    "generation",
    "editing",
    "viral_check",
    "learning",
    "platforms",
)

NETWORK_FORBIDDEN = frozenset(
    {
        "socket",
        "ssl",
        "http",
        "httplib",
        "urllib",
        "urllib2",
        "urllib3",
        "ftplib",
        "telnetlib",
        "smtplib",
        "poplib",
        "imaplib",
        "asyncio",
        "requests",
        "aiohttp",
        "httpx",
    }
)

MEDIA_FORBIDDEN = frozenset(
    {
        "moviepy",
        "ffmpeg",
        "cv2",
        "PIL",
        "numpy",
        "scipy",
        "librosa",
        "soundfile",
        "torch",
        "torchaudio",
        "whisper",
        "faster_whisper",
        "opentimelineio",
        "comfyui",
        "remotion",
    }
)

PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "asur"
# Life Mentor (top-level sibling package) is stdlib-only end to end: every
# module is linted, and it may import only the stdlib, `asur`, or itself.
LIFE_MENTOR_ROOT = Path(__file__).resolve().parent.parent / "products" / "life_mentor"
WEEKLY_TRACKER_ROOT = Path(__file__).resolve().parent.parent / "products" / "weekly_tracker"
ALLOWED_FIRST_PARTY = frozenset({"asur", "life_mentor", "weekly_tracker"})


def _stdlib_names() -> frozenset[str]:
    names = set(getattr(sys, "stdlib_module_names", set()))
    names.update({"__future__"})
    return frozenset(names)


def _iter_stdlib_only_modules():
    for pkg in STDLIB_ONLY_PACKAGES:
        pkg_dir = PACKAGE_ROOT / pkg
        if not pkg_dir.is_dir():
            continue
        for path in sorted(pkg_dir.rglob("*.py")):
            # Media adapters (asur/generation/adapters/) live behind the
            # asur[generation] extra and import heavy deps lazily (AGENTS.md §4).
            # They are intentionally NOT stdlib-only; the control path never
            # imports them, so exclude them from the stdlib boundary linter.
            if "adapters" in path.parts:
                continue
            yield path
    if LIFE_MENTOR_ROOT.is_dir():
        yield from sorted(LIFE_MENTOR_ROOT.rglob("*.py"))
    if WEEKLY_TRACKER_ROOT.is_dir():
        yield from sorted(WEEKLY_TRACKER_ROOT.rglob("*.py"))


def _imported_top_level(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    tops: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                tops.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue
            if node.module:
                tops.add(node.module.split(".")[0])
    return tops


@pytest.mark.parametrize("path", list(_iter_stdlib_only_modules()), ids=lambda p: str(p))
def test_stdlib_only_imports(path: Path) -> None:
    stdlib = _stdlib_names()
    for top in sorted(_imported_top_level(path)):
        if top in ALLOWED_FIRST_PARTY:
            continue
        assert top not in NETWORK_FORBIDDEN, (
            f"{path} imports network module '{top}' (ASUR-LOCAL-01: no network)"
        )
        assert top not in MEDIA_FORBIDDEN, (
            f"{path} imports media dependency '{top}' "
            f"(ADR-0002: media stays behind asur[generation], never in core/script)"
        )
        assert top in stdlib, (
            f"{path} imports non-stdlib module '{top}' "
            f"(ADR-0002: core/script are stdlib-only)"
        )


def test_boundary_covers_modules() -> None:
    found = list(_iter_stdlib_only_modules())
    assert found, "boundary test found no core/script modules to lint (misconfigured)"


def test_boundary_covers_life_mentor() -> None:
    found = [p for p in _iter_stdlib_only_modules() if LIFE_MENTOR_ROOT in p.parents]
    assert found, "boundary test does not lint life_mentor/ (misconfigured)"


def test_boundary_covers_life_mentor_health() -> None:
    health = LIFE_MENTOR_ROOT / "health"
    found = {p.name for p in _iter_stdlib_only_modules() if health in p.parents}
    assert {"usda.py", "foods.py", "nutrition.py", "safety.py"} <= found


def test_life_mentor_bundles_no_restricted_food_tables() -> None:
    # SPEC-GAP LM-G2: only CC0 USDA data may be bundled; never IFCT/INDB/GI tables.
    data = [p.name.casefold() for p in LIFE_MENTOR_ROOT.rglob("*") if p.is_file()]
    assert not [n for n in data if any(t in n for t in ("ifct", "indb", "glycemic_index"))]


@pytest.mark.parametrize(("subpkg", "modules"), [
    ("lifestyle", {"exercise.py", "sleep.py", "habits.py"}),
    ("tracking", {"metrics.py"}),
    ("career", {"offers.py", "education.py", "market.py"}),
])
def test_boundary_covers_life_mentor_lm07_lm08(subpkg: str, modules: set) -> None:
    root = LIFE_MENTOR_ROOT / subpkg
    found = {p.name for p in _iter_stdlib_only_modules() if root in p.parents}
    assert modules <= found


def test_boundary_covers_weekly_tracker() -> None:
    found = {p.relative_to(WEEKLY_TRACKER_ROOT).as_posix() for p in _iter_stdlib_only_modules()
             if WEEKLY_TRACKER_ROOT in p.parents}
    assert {"week.py", "planner.py", "render.py", "cli.py", "sources/git_work.py",
            "sources/life_mentor.py"} <= found


@pytest.mark.parametrize(("rel", "modules"), [
    ("reports", {"render.py", "builders.py"}),
    ("integrations", {"bank_csv.py", "amfi_nav.py"}),
    ("", {"cli.py"}),
])
def test_boundary_covers_life_mentor_lm09_lm10(rel: str, modules: set) -> None:
    root = LIFE_MENTOR_ROOT / rel if rel else LIFE_MENTOR_ROOT
    found = {p.name for p in _iter_stdlib_only_modules() if p.parent == root}
    assert modules <= found


def test_life_mentor_cli_entry_point_declared() -> None:
    text = (PACKAGE_ROOT.parent / "pyproject.toml").read_text(encoding="utf-8")
    for line in ('asur = "asur.cli:main"', 'weekly-tracker = "weekly_tracker.cli:main"',
                 'life-mentor = "life_mentor.cli:main"'):
        assert line in text
