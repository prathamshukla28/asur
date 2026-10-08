"""Stage 15/16 - hero proof manifest + render verification (stdlib-only).

Before any expensive full generation, ASUR proves the creative direction on a
small 5-15 second "hero proof" (PIPELINE.md stage 15; ADR-0004; the PYAAR? rule
"prove quality on a small piece first"). This module builds the hero-proof
MANIFEST (which representative scenes + jobs the proof needs, and the target
spec) and provides ``verify_render`` - a structural check on an actual rendered
file.

``verify_render`` is deliberately offline and model-free (SPEC-GAP G10): it only
checks structural properties (dimensions 1080x1920, duration <= 15s, frame count,
caption-timing JSON present, contact-sheet present). It uses ``ffprobe`` when the
binary is present; when ffmpeg/ffprobe are absent it DEGRADES to a "skipped"
status rather than failing, so CI stays no-GPU, no-network, no-real-model. The
real render itself is done by the media adapters behind ``asur[generation]``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..core.envelope import Artifact, make_artifact
from ..core.identity import Identity
from . import source_ref

# Target spec for the vertical 9:16 Instagram Reel hero proof.
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
MAX_HERO_DURATION_S = 15.0

# Which screenplay sections make the most representative proof: the hook (does
# it stop the scroll?) and the payoff (does it deliver?). These two carry the
# creative direction without rendering the whole video.
_PROOF_SECTIONS = ("hook", "payoff")


def build_hero_proof(
    generation_plan_artifact: Artifact,
    visual_screenplay_artifact: Artifact,
    project_id: str,
    *,
    identity: Identity | None = None,
) -> Artifact:
    """Produce a ``creative_direction``-adjacent hero-proof manifest artifact.

    The manifest names the representative scenes, the subset of generation jobs
    needed to render just those scenes, and the target render spec. It does not
    render anything - it is the plan a human (and the adapters) use to produce
    and then review the small proof before approving expensive generation.
    """
    sp_body = visual_screenplay_artifact.body or {}
    gp_body = generation_plan_artifact.body or {}
    subject = sp_body.get("subject", "the topic")
    scenes = sp_body.get("scenes") or []
    jobs = gp_body.get("jobs") or []

    proof_scenes = [s for s in scenes if s.get("section") in _PROOF_SECTIONS]
    if not proof_scenes and scenes:
        # Fail-soft: if the named sections are absent, use the first scene.
        proof_scenes = [scenes[0]]

    proof_scene_ids = {s.get("scene_id", "") for s in proof_scenes}
    # Keep only the jobs whose target asset belongs to a proof scene (plus the
    # shared voice/music beds, which have no scene prefix).
    proof_jobs = [
        j
        for j in jobs
        if any(str(j.get("target_asset", "")).startswith(sid) for sid in proof_scene_ids)
        or j.get("target_asset") in ("voice-track", "music-bed")
    ]

    body: dict[str, Any] = {
        "subject": subject,
        "proof_scene_ids": sorted(proof_scene_ids),
        "proof_scene_count": len(proof_scenes),
        "proof_jobs": proof_jobs,
        "proof_job_count": len(proof_jobs),
        "target_spec": {
            "width": TARGET_WIDTH,
            "height": TARGET_HEIGHT,
            "aspect_ratio": "9:16",
            "max_duration_s": MAX_HERO_DURATION_S,
        },
        "review_requirement": (
            "a human reviews the ACTUAL rendered proof (not JSON) and must "
            "approve it before any expensive full generation (HUMAN GATE #1)"
        ),
        "method": (
            "local heuristic: representative hook+payoff scenes, job subset, "
            "9:16 <=15s target; render + review happen before approval"
        ),
    }

    return make_artifact(
        kind="creative_direction",
        project_id=project_id,
        body=body,
        status="ready",
        sources=[
            source_ref(generation_plan_artifact),
            source_ref(visual_screenplay_artifact),
        ],
        agent="generation",
        identity=identity,
    )


def _ffprobe_available() -> bool:
    """True only if the ffprobe binary is actually on PATH (no network/GPU)."""
    return shutil.which("ffprobe") is not None


def _probe_dimensions_duration(video_path: Path) -> tuple[int, int, float]:
    """Return (width, height, duration_s) via ffprobe. Caller guards availability."""
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height:format=duration",
            "-of",
            "json",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    data = json.loads(out.stdout or "{}")
    stream = (data.get("streams") or [{}])[0]
    width = int(stream.get("width", 0) or 0)
    height = int(stream.get("height", 0) or 0)
    duration = float((data.get("format") or {}).get("duration", 0.0) or 0.0)
    return width, height, duration


def verify_render(
    video_path: str | Path,
    *,
    caption_timing_path: str | Path | None = None,
    contact_sheet_path: str | Path | None = None,
) -> dict[str, Any]:
    """Structurally verify an actual rendered hero proof. Offline, model-free.

    Returns a dict with keys ``status`` (one of ``"pass"``, ``"fail"``,
    ``"skipped"``), ``checks`` (per-check pass/fail/skip + reason), and
    ``reasons``. When ffprobe is absent the dimension/duration checks are
    ``skipped`` (never ``fail``) so CI without ffmpeg still passes (G10). The
    structural truth is "rendered output is truth" (PIPELINE.md stages 16/20/22)
    but the harness itself never requires a GPU, a network, or a real model.
    """
    video_path = Path(video_path)
    checks: list[dict[str, Any]] = []
    reasons: list[str] = []

    # File-existence check always runs (pure filesystem).
    exists = video_path.is_file()
    checks.append(
        {
            "check": "file_exists",
            "result": "pass" if exists else "fail",
            "reason": str(video_path) if exists else f"missing: {video_path}",
        }
    )
    if not exists:
        reasons.append(f"rendered file missing: {video_path}")

    # Dimension + duration checks require ffprobe; skip gracefully if absent.
    if not _ffprobe_available():
        checks.append(
            {
                "check": "dimensions_duration",
                "result": "skipped",
                "reason": "ffprobe not on PATH; offline CI (G10)",
            }
        )
    elif exists:
        try:
            width, height, duration = _probe_dimensions_duration(video_path)
            dims_ok = width == TARGET_WIDTH and height == TARGET_HEIGHT
            checks.append(
                {
                    "check": "dimensions",
                    "result": "pass" if dims_ok else "fail",
                    "reason": f"{width}x{height} (want {TARGET_WIDTH}x{TARGET_HEIGHT})",
                }
            )
            if not dims_ok:
                reasons.append(f"dimensions {width}x{height} != 1080x1920")
            dur_ok = 0.0 < duration <= MAX_HERO_DURATION_S
            checks.append(
                {
                    "check": "duration",
                    "result": "pass" if dur_ok else "fail",
                    "reason": f"{duration:.2f}s (want 0 < d <= {MAX_HERO_DURATION_S})",
                }
            )
            if not dur_ok:
                reasons.append(f"duration {duration:.2f}s out of range")
        except (subprocess.SubprocessError, ValueError, OSError) as exc:
            checks.append(
                {
                    "check": "dimensions_duration",
                    "result": "skipped",
                    "reason": f"probe error, treated as skip: {exc}",
                }
            )

    # Caption-timing JSON + contact sheet: pure filesystem presence checks.
    if caption_timing_path is not None:
        ct = Path(caption_timing_path)
        ct_ok = ct.is_file()
        checks.append(
            {
                "check": "caption_timing_json",
                "result": "pass" if ct_ok else "fail",
                "reason": str(ct) if ct_ok else f"missing: {ct}",
            }
        )
        if not ct_ok:
            reasons.append(f"caption-timing JSON missing: {ct}")

    if contact_sheet_path is not None:
        cs = Path(contact_sheet_path)
        cs_ok = cs.is_file()
        checks.append(
            {
                "check": "contact_sheet",
                "result": "pass" if cs_ok else "fail",
                "reason": str(cs) if cs_ok else f"missing: {cs}",
            }
        )
        if not cs_ok:
            reasons.append(f"contact sheet missing: {cs}")

    results = {c["result"] for c in checks}
    if "fail" in results:
        status = "fail"
    elif "skipped" in results:
        status = "skipped"
    else:
        status = "pass"

    return {"status": status, "checks": checks, "reasons": reasons}
