"""Stage 21 - final render orchestration (stdlib-only control shell).

``build_final_render`` is the seam that turns an approved ``edit_plan`` into a
real rendered video plus a first-class, checksummed ``render`` artifact. The
heavy lifting (the actual pixels) is done by the LOCKED FFmpeg adapter behind
``asur[generation]``; this module stays in the stdlib control path and only
orchestrates: render -> structurally verify -> record provenance.

Fail-closed contract (ASUR-GATE-01): the render is accepted only if structural
verification does not report ``fail``. A missing ffprobe DEGRADES verification to
``skipped`` (G10) and is accepted - absence of the probe is not evidence of a bad
render, but a probe that reports wrong dimensions/duration IS a fail and stops
the artifact from being produced.

The adapter import is LAZY (inside the function) so this module stays importable
in a stdlib-only install and the boundary import-linter stays green: nothing at
GENERATION's control level imports a media dependency at module load.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..core.envelope import Artifact, make_artifact
from ..core.identity import Identity
from ..platforms import get_platform
from . import hero_proof, source_ref

# Re-exported so callers (and tests) catch the one render failure type here.
from .adapters.ffmpeg import RenderError

__all__ = ["RenderError", "build_final_render"]


def build_final_render(
    edit_plan_artifact: Artifact,
    project_id: str,
    *,
    platform: str | None = None,
    out_root: str,
    identity: Identity | None = None,
) -> Artifact:
    """Render an approved edit plan to a real MP4 and record a ``render`` artifact.

    Renders the edit plan's timeline through the FFmpeg adapter at the platform
    pack's resolution, structurally verifies the output with the SAME platform,
    and emits a ``render`` artifact carrying the adapter's provenance + license
    block (ASUR-PROV-01) and the verification report (ASUR-EXPLAIN-01).

    Raises ``RenderError`` if verification reports ``fail`` (ASUR-GATE-01).
    """
    from .adapters import ffmpeg

    edit_body = edit_plan_artifact.body or {}
    subject = edit_body.get("subject", "")
    timeline = edit_body.get("timeline") or {}

    out_dir = Path(out_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "final-video.mp4"

    adapter_result = ffmpeg.render(timeline, str(out_path), platform=platform)

    # A FULL final render is not a hero proof: its duration ceiling is the
    # platform band's upper bound, not the short hero cap. An undeclared band
    # (Instagram) imposes no upper duration cap here; the platform band is a QA
    # warn-not-fail concern (G16), handled in final_qa, not a hard render gate.
    band = get_platform(platform).format_spec.duration_band_s
    final_cap = float("inf") if band is None else float(band[1])
    verify = hero_proof.verify_render(
        out_path, platform=platform, max_duration_s=final_cap
    )
    if verify["status"] == "fail":
        raise RenderError(
            f"rendered output failed structural verification: {verify['reasons']}"
        )

    body: dict[str, Any] = {
        "subject": subject,
        "platform": platform or "instagram_reels",
        "final_video": str(out_path),
        "provenance": adapter_result["provenance"],
        "license": adapter_result["license"],
        "verify": verify,
        "method": (
            "FFmpeg LOCKED renderer (zero marginal cost); structural verify via "
            "ffprobe, degrading to skipped offline (G10)"
        ),
    }

    return make_artifact(
        kind="render",
        project_id=project_id,
        body=body,
        status="ready",
        sources=[source_ref(edit_plan_artifact)],
        agent="generation",
        identity=identity,
    )
