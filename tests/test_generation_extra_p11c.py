"""P11c — the `asur[generation]` extra is complete and pinned (SPEC-GAP G28).

Every adapter that P11a/P11b wired to a real model (SDXL image, Kokoro voice,
Stable Audio music, faster-whisper captions) imports a third-party package
behind the optional `generation` extra. The extra must therefore *declare* all
of those packages, and each must be **pinned** to a known-good version so a
`pip install -e .[generation]` is reproducible (ASUR-VERSION-01 in spirit;
AGENTS.md §4 — media behind the extra).

This is pure packaging metadata, so the test only reads `pyproject.toml`; it
never imports torch/diffusers/etc and so stays stdlib-only, no-network, no-GPU.

It also guards ASUR-LOCAL-01: `[project].dependencies` MUST stay empty, so a
stdlib-only install keeps running SCRIPT + VIRAL CHECK + orchestration.
"""

from __future__ import annotations

from pathlib import Path

import pytest

tomllib = pytest.importorskip(
    "tomllib",
    reason="tomllib is stdlib only on Python >= 3.11; skip the metadata check below it",
)

# Every third-party package the real generation path now imports. Names match
# the import/distribution names pip resolves (not the Python module names).
REQUIRED_GENERATION_PACKAGES = (
    "moviepy",            # FFmpeg-backed editing/compositing
    "faster-whisper",     # word-level caption timing
    "librosa",            # beat map / audio analysis
    "opentimelineio",     # timeline interchange (OTIO)
    "torch",              # tensor runtime (SDXL + Stable Audio)
    "diffusers",          # SDXL image pipeline
    "transformers",       # SDXL text encoders
    "accelerate",         # diffusers device placement
    "safetensors",        # weight format
    "Pillow",             # frame resize/crop
    "kokoro",             # Kokoro-82M voice synthesis
    "soundfile",          # Kokoro WAV writing
    "numpy",              # audio buffer concat
    "stable-audio-tools", # Stable Audio music generation
    "torchaudio",         # Stable Audio WAV writing
)


def _load_pyproject() -> dict:
    path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _generation_requirements() -> list[str]:
    data = _load_pyproject()
    optional = data["project"]["optional-dependencies"]
    return list(optional["generation"])


def _requirement_name(requirement: str) -> str:
    """Return the distribution name from a PEP 508 requirement string."""
    name = requirement.strip()
    for sep in ("==", ">=", "<=", "~=", "!=", "<", ">", "[", ";", " "):
        idx = name.find(sep)
        if idx != -1:
            name = name[:idx]
    return name.strip().lower()


def test_generation_extra_lists_every_real_adapter_dependency() -> None:
    declared = {_requirement_name(req) for req in _generation_requirements()}
    for package in REQUIRED_GENERATION_PACKAGES:
        assert package.lower() in declared, (
            f"generation extra is missing {package!r} "
            f"(a real adapter imports it); declared={sorted(declared)}"
        )


def test_every_generation_dependency_is_pinned() -> None:
    for req in _generation_requirements():
        assert "==" in req, (
            f"generation dependency {req!r} is not pinned to a known-good "
            f"version (== required for a reproducible install, SPEC-GAP G28)"
        )


def test_core_dependencies_stay_empty() -> None:
    # ASUR-LOCAL-01: a stdlib-only install MUST keep working.
    data = _load_pyproject()
    assert data["project"]["dependencies"] == [], (
        "[project].dependencies must stay empty (ASUR-LOCAL-01); "
        "media deps live only under the optional 'generation' extra"
    )
