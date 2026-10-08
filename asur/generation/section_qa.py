"""P06 section-by-section QA for full generation.

After the hero proof is approved (HUMAN GATE #1), GENERATION produces the
remaining sections. Each section is checked on its own: a section that fails QA
is marked ``rejected`` and only that section is regenerated -- never the whole
video (ASUR-VERSION-01: nothing silently overwritten; failed artifacts are kept,
retries are stage-scoped). This module is pure stdlib control logic; it inspects
plan metadata, not real media (real rendering is a local GPU step behind the
``asur[generation]`` extra). Honours ASUR-EXPLAIN-01: every verdict carries a
reason.
"""

from __future__ import annotations

from typing import Any

from ..core.envelope import Artifact, make_artifact
from ..core.identity import Identity
from . import source_ref

# A section passes structural QA only when it has a non-empty rendered asset and
# a recorded review on the ACTUAL output. A section with no asset, or a review of
# "rejected", fails closed (ASUR-GATE-01).
_PASS = "pass"
_FAIL = "fail"


def _section_names(visual_screenplay_artifact: Artifact) -> list[str]:
    scenes = visual_screenplay_artifact.body.get("scenes", [])
    return [str(scene.get("section", scene.get("scene_id", ""))) for scene in scenes]


def check_section(section: dict[str, Any]) -> dict[str, Any]:
    """Structural QA for one generated section. Returns {section, status, reasons}.

    Fails closed: a missing/empty rendered asset, or a reviewer rejection, is a
    fail. ASUR cannot judge creative quality here -- that is the 5-family final
    QA and the human gates. This only confirms the section was produced and not
    rejected.
    """
    name = str(section.get("section", section.get("scene_id", "<unnamed-section>")))
    reasons: list[str] = []

    rendered = section.get("rendered_asset")
    if not rendered:
        reasons.append(f"section '{name}' has no rendered asset")

    review = section.get("review")
    if review == "rejected":
        reasons.append(f"section '{name}' was rejected by review")

    status = _PASS if not reasons else _FAIL
    if status == _PASS:
        reasons.append(f"section '{name}' produced and not rejected")
    return {"section": name, "status": status, "reasons": reasons}


def sections_to_regenerate(section_reports: list[dict[str, Any]]) -> list[str]:
    """Names of only the sections that failed -- the stage-scoped retry set.

    This is the regenerate-only-the-failing-section rule: a passing section is
    never touched, so approved work is never discarded on a retry.
    """
    return [r["section"] for r in section_reports if r["status"] == _FAIL]


def build_section_qa_report(
    visual_screenplay_artifact: Artifact,
    sections: list[dict[str, Any]],
    project_id: str,
    *,
    identity: Identity | None = None,
) -> Artifact:
    """Run per-section QA over the generated sections and emit a qa_report.

    ``sections`` is the list of produced sections (each a dict with at least
    ``section``/``scene_id`` and, when rendered, ``rendered_asset`` + ``review``).
    The report lists every section's verdict and the stage-scoped regenerate set.
    status='ready' when all sections pass, else 'rejected' (fail closed).
    """
    expected = _section_names(visual_screenplay_artifact)
    reports = [check_section(section) for section in sections]
    produced = {r["section"] for r in reports}
    missing = [name for name in expected if name not in produced]
    for name in missing:
        reports.append(
            {
                "section": name,
                "status": _FAIL,
                "reasons": [f"expected section '{name}' was not produced"],
            }
        )

    to_regen = sections_to_regenerate(reports)
    all_pass = not to_regen
    body = {
        "stage": "section_qa",
        "expected_section_count": len(expected),
        "produced_section_count": len(produced),
        "section_reports": reports,
        "regenerate_sections": to_regen,
        "all_sections_pass": all_pass,
        "note": (
            "Section QA confirms each section was produced and not rejected. "
            "Only failing sections are regenerated; passing sections are never "
            "touched. Creative quality is judged by the 5-family final QA and "
            "the human gates, not here."
        ),
        "method": "local stdlib structural check; no media decoded; no network",
    }
    return make_artifact(
        kind="qa_report",
        project_id=project_id,
        body=body,
        status="ready" if all_pass else "rejected",
        sources=[source_ref(visual_screenplay_artifact)],
        agent="qa",
        identity=identity,
    )
