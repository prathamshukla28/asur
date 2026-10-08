"""Model-name -> adapter dispatcher for GENERATION jobs.

A generation plan (``generation_plan.py``) describes jobs that each carry a
``model`` NAME string (e.g. "FFmpeg", "SDXL", "Kokoro-82M"). Nothing in the
plan actually runs a model; this module is the single place that maps a model
name to the adapter function that produces the asset.

WHY THIS MODULE EXISTS (SPEC-GAP, logged in docs/build/OPEN_QUESTIONS.md):
the plan and the adapters existed, but no code connected a job's ``model``
string to an adapter function. This dispatcher is that missing seam.

HARD RULES (AGENTS.md §4, ADR-0002):
  * Module level is stdlib-only (``os``/``typing``). Every adapter import is
    LAZY, inside ``run_job`` - so the stdlib control path and the boundary
    import-linter stay clean, and a stdlib-only install never pulls a media dep.
  * Unknown model names FAIL CLOSED (ASUR-GATE-01) - we never silently skip.
  * Each adapter returns a provenance + license dict (ASUR-PROV-01); this
    dispatcher returns that dict unchanged plus the originating job id.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

# Map a model NAME (as carried on a plan job) to (adapter module, function).
# The module path is resolved lazily so importing this file pulls no media dep.
_ROUTES: dict[str, tuple[str, str]] = {
    "FFmpeg": ("asur.generation.adapters.ffmpeg", "render"),
    "SDXL": ("asur.generation.adapters.sdxl", "generate"),
    "Kokoro-82M": ("asur.generation.adapters.kokoro", "synthesize"),
    "Stable Audio 3.0": ("asur.generation.adapters.stable_audio", "generate"),
    "Wan 2.2 TI2V-5B": ("asur.generation.adapters.wan22", "generate"),
    "faster-whisper": ("asur.generation.adapters.faster_whisper", "transcribe"),
}


class DispatchError(RuntimeError):
    """Raised when a job names a model with no registered adapter."""


def known_models() -> tuple[str, ...]:
    """Return the model names this dispatcher can route (sorted, stable)."""
    return tuple(sorted(_ROUTES))


def _resolve(model: str) -> Callable[..., dict[str, Any]]:
    """Lazily import and return the adapter function for ``model``."""
    try:
        module_path, func_name = _ROUTES[model]
    except KeyError as exc:  # fail closed - never route an unknown model
        raise DispatchError(
            f"no adapter registered for model {model!r}; "
            f"known models: {', '.join(known_models())}"
        ) from exc
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, func_name)


def run_job(job: dict[str, Any], *, timeline: Any = None, out_dir: str) -> dict[str, Any]:
    """Run one generation-plan job through its model's adapter.

    ``job`` is one entry from ``generation_plan`` body['jobs'] (carries
    ``job_id``, ``target_asset``, ``model``, ``params``). ``out_dir`` is where
    the produced file lands. Returns the adapter's provenance+license dict with
    the originating ``job_id`` attached.

    This only INVOKES adapters - it does not install anything. If the model's
    adapter needs the ``asur[generation]`` extra (SDXL/Kokoro/etc.) the adapter
    itself raises a clear RuntimeError; the FFmpeg adapter needs only the ffmpeg
    binary. Fails closed on an unknown model (ASUR-GATE-01).
    """
    model = str(job.get("model", "")).strip()
    if not model:
        raise DispatchError(f"job {job.get('job_id', '<unknown>')!r} has no model name")
    adapter = _resolve(model)
    target = str(job.get("target_asset", job.get("job_id", "asset")))
    media_type = str(job.get("params", {}).get("media_type", "video"))
    ext = {"video": "mp4", "image": "png", "audio_voice": "wav", "audio_music": "wav"}.get(
        media_type, "out"
    )
    out_path = os.path.join(out_dir, f"{target}.{ext}")

    # FFmpeg renders a timeline; image adapters write a PNG to out_path; audio
    # adapters take text. We pass what each shape needs and let the adapter
    # raise if its extra is absent (NOTE: target is the asset ref today; real
    # screenplay scene text is a crude-prompt gap tracked in DEFERRED.md).
    if model == "FFmpeg":
        result = adapter(timeline, out_path)
    elif media_type == "image":
        result = adapter(target, out_path)
    elif media_type == "audio_voice":
        result = adapter(target, voice=job.get("params", {}).get("voice", "default"))
    else:
        result = adapter(target)

    out: dict[str, Any] = dict(result)
    out["job_id"] = job.get("job_id")
    return out
