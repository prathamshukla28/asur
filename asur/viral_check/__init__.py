"""VIRAL CHECK - the evaluation / challenge instrument (Phase 7, control logic).

VIRAL CHECK answers one honest question: "Does this video have a realistic
chance of performing exceptionally well?" - never "this will go viral."

Three honesty rules (docs/VIRAL_CHECK.md section 1, ASUR-HONEST-01):

  1. NEVER output a single "% viral" number. Score input quality against
     documented signals, not a predicted outcome.
  2. Separate "signal exists" (VERIFIED) from "weight known" (UNKNOWN).
  3. Penalties are BINARY RISK FLAGS, never percentage deductions.

VIRAL CHECK is structurally independent from GENERATION; they never talk. SCRIPT
is the only bridge, and it hands VIRAL CHECK a VIRAL_VIEW that has had all
quality/hardness TARGETS stripped by name (ASUR-FIREWALL-01). This package may
ONLY read a VIRAL_VIEW and must NEVER import a GENERATION path; a static
cross-import check (tests/test_firewall.py) enforces that.

This is stdlib-only control logic (ASUR-LOCAL-01, AGENTS.md section 4): it
imports no third-party or media library.
"""

from __future__ import annotations

from ..core.envelope import Artifact

__all__ = ["source_ref"]


def source_ref(artifact: Artifact) -> dict:
    """A lineage entry pointing at *artifact* for a downstream sources[] list.

    Mirrors ``asur.script.source_ref`` / ``asur.generation.source_ref``: captures
    id, version, and checksum so each stage is provenance-bound to the ones
    before it (ASUR-PROV-01, ASUR-VERSION-01).
    """
    return {
        "artifact_id": artifact.artifact_id,
        "version": artifact.version,
        "checksum": artifact.checksum,
    }
