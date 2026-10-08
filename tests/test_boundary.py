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
        if top == "asur":
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
