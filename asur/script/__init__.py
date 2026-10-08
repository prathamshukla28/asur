"""SCRIPT - the intelligence instrument (Phase 1).

SCRIPT is the only instrument that bridges GENERATION and VIRAL CHECK, and in
Phase 1 it owns the full idea -> script pipeline:

    idea -> research -> audience -> strategy -> hooks -> script -> quality gate

Every stage is a pure, local, explainable builder that takes upstream
artifacts and returns a new artifact body (ASUR-EXPLAIN-01, ASUR-LOCAL-01).
Persistence, versioning, and checksums are handled by core/workspace.py and
core/envelope.py; lineage (sources[]) is set via source_ref() so each stage is
provenance-bound to the ones before it (ASUR-PROV-01).

Nothing here touches the network. All "research" is local heuristic reasoning
over the idea text, and every claim is tagged with an evidence class so the
system never presents a guess as a fact (ASUR-HONEST-01).
"""

from __future__ import annotations

from ..core.envelope import Artifact

__all__ = ["source_ref"]


def source_ref(artifact: Artifact) -> dict:
    """A lineage entry pointing at *artifact* for a downstream sources[] list.

    Captures the three things needed to prove provenance and detect drift:
    the id, the version it was at, and the content checksum.
    """
    return {
        "artifact_id": artifact.artifact_id,
        "version": artifact.version,
        "checksum": artifact.checksum,
    }
