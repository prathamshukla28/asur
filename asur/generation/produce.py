"""Stage 14b - produce the real AI assets a generation plan calls for (G27).

``produce_assets`` is the seam between the generation PLAN (control data) and the
actual produced media files. It walks the plan's jobs in dependency order, runs
each AI job through the dispatcher, and groups the produced files by their role
so the render step can composite them:

    {"backgrounds": {scene_id: png_path, ...},
     "voice": wav_path | None,
     "music": wav_path | None,
     "assets": [provenance+license dict, ...],
     "skipped": [job_id, ...]}

WHAT IS PRODUCED HERE vs NOT:
  * AI image backgrounds (SDXL), the shared voice track (Kokoro), and the shared
    music bed (Stable Audio) ARE produced here - they are real files on disk.
  * On-screen hero text is model ``FFmpeg`` (media_type ``graphic``): it is NOT
    produced here. FFmpeg draws it as a burned-in caption at RENDER time over the
    composited background, so running it here would need a timeline and duplicate
    work. Those jobs are SKIPPED (recorded, never silently dropped).
  * User-original footage is model ``user-camera``: there is no adapter to run
    (the creator owns it). Those jobs are SKIPPED too.

HARD RULES (AGENTS.md §4):
  * Module level is stdlib-only. The dispatcher + the ffmpeg RenderError import
    are LAZY, inside the function, so this module stays importable in a
    stdlib-only install and the boundary import-linter stays green.
  * Fail closed (ASUR-GATE-01): if an adapter raises (e.g. its extra is missing)
    the error propagates - never a silent partial asset set. If an adapter claims
    a file that is not actually on disk, that is also a fail.
  * Every produced asset carries the adapter's provenance+license block
    (ASUR-PROV-01); they are collected verbatim into ``assets``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..core.envelope import Artifact

__all__ = ["produce_assets"]

# Models that are NOT produced by an AI adapter in this step.
#   FFmpeg      -> on-screen text is burned in at render time (needs the timeline)
#   user-camera -> creator-owned footage; there is no adapter to run
_SKIP_MODELS = frozenset({"FFmpeg", "user-camera"})


def produce_assets(
    generation_plan_artifact: Artifact,
    *,
    out_dir: str,
    screenplay: Artifact | None = None,
) -> dict[str, Any]:
    """Run a generation plan's AI jobs and group the produced files by role.

    ``out_dir`` is where produced files land (the caller typically passes a
    per-project media-workspace ``_work`` directory). Returns the grouped result
    described in the module docstring. Fails closed on a raising adapter or a
    produced file that is missing from disk (ASUR-GATE-01).
    """
    # Lazy so a stdlib-only import of this module pulls no media dependency and
    # the boundary import-linter stays green.
    from . import dispatch
    from .adapters.ffmpeg import RenderError

    body = generation_plan_artifact.body or {}
    jobs = body.get("jobs") or []

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    backgrounds: dict[str, str] = {}
    voice: str | None = None
    music: str | None = None
    assets: list[dict[str, Any]] = []
    skipped: list[str] = []

    for job in jobs:
        model = str(job.get("model", "")).strip()
        if model in _SKIP_MODELS:
            skipped.append(str(job.get("job_id", job.get("target_asset", "<job>"))))
            continue

        # Run the real adapter. A raising adapter (missing extra) propagates -
        # we never swallow it into a partial set (ASUR-GATE-01).
        result = dispatch.run_job(job, out_dir=str(out))

        file_path = str(result.get("file_path", ""))
        if not file_path or not Path(file_path).is_file():
            raise RenderError(
                f"adapter for job {job.get('job_id', '<job>')!r} reported no file "
                f"on disk (got {file_path!r}); fail closed (ASUR-GATE-01)"
            )

        assets.append(result)

        media_type = str(job.get("params", {}).get("media_type", ""))
        target = str(job.get("target_asset", ""))
        if media_type == "image" and target.endswith("-background"):
            scene_id = target[: -len("-background")]
            backgrounds[scene_id] = file_path
        elif media_type == "audio_voice":
            voice = file_path
        elif media_type == "audio_music":
            music = file_path

    return {
        "backgrounds": backgrounds,
        "voice": voice,
        "music": music,
        "assets": assets,
        "skipped": skipped,
    }
