"""EDITING - the shared, human-controlled editing environment (Phase 5).

EDITING is NOT a fourth instrument. It is the timeline environment where a human
shapes generated assets + original footage into the finished video. AI
accelerates editing; the human always retains control (ASUR-HUMAN-01).

This package holds only the **stdlib-only control logic** (ASUR-LOCAL-01,
AGENTS.md section 4):

    timeline (versioned model) --> primitives (palette, never the driver)
                   |                      |
                captions / audio_mix      controls (accept/reject/modify/
                                          regenerate/lock/compare/branch/revert)

Every edit produces a NEW version; nothing is silently overwritten and every
object keeps its version_history (ASUR-VERSION-01). The timeline interchange
format is OpenTimelineIO (OTIO, Apache-2.0); because OTIO is a media dependency
it lives behind the ``asur[generation]`` extra in ``asur.editing.adapters`` and
is NEVER imported by this control path.

EDITING reads a GENERATION_VIEW only and must NEVER import a VIRAL CHECK path
(ASUR-FIREWALL-01); a static cross-import check enforces this.
"""

from __future__ import annotations

from ..core.envelope import Artifact

__all__ = ["source_ref"]


def source_ref(artifact: Artifact) -> dict:
    """A lineage entry pointing at *artifact* for a downstream sources[] list.

    Mirrors ``asur.generation.source_ref``: captures id, version, and checksum so
    each EDITING artifact is provenance-bound to the ones before it
    (ASUR-PROV-01, ASUR-VERSION-01).
    """
    return {
        "artifact_id": artifact.artifact_id,
        "version": artifact.version,
        "checksum": artifact.checksum,
    }
