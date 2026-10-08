"""LEARNING - the loop-closing instrument (Phase 8).

LEARNING is where a finished video becomes knowledge. It packages the approved
video for publishing, captures the real performance a human reports back, folds
prediction-vs-actual into SCRIPT memory, and tracks fatigue so the next idea is
better informed than the last. This is the closed loop that makes ASUR more than
a one-shot generator.

Everything here is pure, local, stdlib-only control logic (ASUR-LOCAL-01). It
never touches the network: performance metrics are human-provided files, never
fetched. Publishing is never automatic - it stops at a human gate
(ASUR-HUMAN-01). Learnings about a creator are recorded as EMPIRICAL
observations from that creator's own data, never as universal facts
(ASUR-HONEST-01).
"""

from __future__ import annotations

from ..core.envelope import Artifact

__all__ = ["source_ref"]


def source_ref(artifact: Artifact) -> dict:
    """A lineage entry pointing at *artifact* for a downstream sources[] list."""
    return {
        "artifact_id": artifact.artifact_id,
        "version": artifact.version,
        "checksum": artifact.checksum,
    }
