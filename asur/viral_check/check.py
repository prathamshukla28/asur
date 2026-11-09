"""One-call VIRAL CHECK over a rendered file: measure -> facts -> VIRAL_VIEW -> verdict."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..core.envelope import Artifact
from ..core.identity import Identity
from ..tools.projection import build_viral_view
from .evaluate import build_viral_check
from .facts import build_platform_facts
from .probe import measure_video

__all__ = ["check_video"]


def check_video(
    video_path: str | Path,
    project_id: str,
    *,
    platform: str | None = None,
    plan: dict[str, Any] | None = None,
    declared: dict[str, Any] | None = None,
    render_provenance: dict[str, Any] | None = None,
    source_artifacts: list[Artifact] | None = None,
    identity: Identity | None = None,
) -> Artifact:
    """Measure *video_path* and return a ``viral_check`` artifact bound to its sha256.

    Raises ``probe.ProbeUnavailable`` when the file cannot be measured (callers
    fail closed). ``plan`` is the output of ``facts.plan_facts``; ``declared``
    holds optional human judgments (never inferred).
    """
    measured = measure_video(video_path)
    facts = build_platform_facts(measured, platform=platform, plan=plan, declared=declared)
    view = build_viral_view(
        bundle_hashes={Path(video_path).name: measured["sha256"]},
        provenance=dict(render_provenance or {"renderer": "unknown"}),
        platform_facts=facts,
        rubric_metadata={"lane": "viral-check", "binding": project_id,
                         "measured_by": measured["measured_by"]},
    )
    return build_viral_check(view, project_id, source_artifacts=source_artifacts,
                             identity=identity)
