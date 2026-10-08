"""GENERATION - the creation instrument (Phase 4, control logic).

GENERATION turns an approved SCRIPT into a plan for a finished video, then
produces a small HERO PROOF (5-15s) that a human must approve before any
expensive full generation runs.

This package holds only the **stdlib-only control logic** (ASUR-LOCAL-01,
AGENTS.md section 4):

    creative_direction -> visual_screenplay -> asset_strategy -> generation_plan
                                                   |
                                             license_guard (fails closed)
                                                   |
                                              hero_proof (orchestration shell)

It imports no third-party or media library. The real model + render adapters
(Wan 2.2, SDXL, Kokoro, Stable Audio, FFmpeg/MoviePy, faster-whisper) live in
``asur.generation.adapters`` behind the optional ``asur[generation]`` extra and
are NEVER imported by this control path, so a stdlib-only install still runs the
planner and the firewall end to end.

GENERATION may only ever read a GENERATION_VIEW (quality FLOORS, brief, hooks,
cost/license policy). It must NEVER import a VIRAL CHECK path (ASUR-FIREWALL-01);
a static cross-import check enforces this.
"""

from __future__ import annotations

from ..core.envelope import Artifact

__all__ = ["source_ref"]


def source_ref(artifact: Artifact) -> dict:
    """A lineage entry pointing at *artifact* for a downstream sources[] list.

    Mirrors ``asur.script.source_ref``: captures id, version, and checksum so
    each GENERATION stage is provenance-bound to the ones before it
    (ASUR-PROV-01, ASUR-VERSION-01).
    """
    return {
        "artifact_id": artifact.artifact_id,
        "version": artifact.version,
        "checksum": artifact.checksum,
    }
