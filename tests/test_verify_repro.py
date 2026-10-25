"""Tests for ``asur verify-repro`` - reproducibility as a checkable guarantee.

ASUR-VERSION-01 / ASUR-HONEST-01: "same inputs -> same checksums". These tests
prove the verifier rebuilds each stored SCRIPT stage from its on-disk upstream
artifacts, confirms byte-identical checksums, and FAILS CLOSED when a stored
artifact has been altered out from under its checksum.
"""

import json

from asur.core.gate import HOLD, SHIP
from asur.core.workspace import Workspace
from asur.script.audience import build_audience
from asur.script.hooks import build_hooks
from asur.script.idea import build_idea
from asur.script.quality_gate import build_qa_report
from asur.script.research import build_research
from asur.script.script_builder import build_script
from asur.script.strategy import build_strategy
from asur.tools.verify_repro import verify_reproducible

SAMPLE_IDEA = "why most people waste money on AI tools"
PROJECT_ID = "test-repro"


def _save_full_chain(tmp_path, project_id=PROJECT_ID) -> Workspace:
    ws = Workspace(tmp_path, project_id).ensure()
    idea = build_idea(SAMPLE_IDEA, project_id)
    research = build_research(idea, project_id)
    audience = build_audience(idea, research, project_id)
    strategy = build_strategy(idea, audience, project_id)
    hooks = build_hooks(strategy, project_id)
    script = build_script(strategy, hooks, project_id)
    qa, _result = build_qa_report(
        script, project_id, hooks_artifact=hooks, strategy_artifact=strategy
    )
    for art in (idea, research, audience, strategy, hooks, script, qa):
        ws.save_artifact(art)
    return ws


def test_verify_repro_full_chain_reproduces(tmp_path):
    """A clean, deterministically-built chain reproduces byte-for-byte."""
    ws = _save_full_chain(tmp_path)
    report = verify_reproducible(ws)

    assert report["reproducible"] is True
    assert report["disposition"] == SHIP
    assert {s["kind"] for s in report["stages"]} == {
        "idea", "research", "audience", "strategy", "hooks", "script", "qa_report",
    }
    for stage in report["stages"]:
        assert stage["match"] is True
        assert stage["rebuilt_checksum"] == stage["stored_checksum"]


def test_verify_repro_detects_a_tampered_body(tmp_path):
    """ASUR-GATE-01: altering a stored body's content is caught and fails closed.

    We rewrite a stored strategy file's BODY (and re-stamp its checksum so the
    load-time checksum guard still passes) - exactly what a silent edit would
    look like. verify-repro rebuilds from the real upstream and the strategy no
    longer matches, so the whole run is held.
    """
    ws = _save_full_chain(tmp_path)

    strat_dir = ws.artifacts_dir / "strategy"
    strat_file = next(strat_dir.glob("v0001-*.json"))
    data = json.loads(strat_file.read_text(encoding="utf-8"))
    data["body"]["objective"]["value"] = "a different objective nobody chose"
    # Re-stamp the checksum so the tamper survives the load-time integrity check
    # (this is what a determined silent edit would do; verify-repro still catches it).
    from asur.core.canonical import canonical_sha256
    data["checksum"] = canonical_sha256(data["body"])
    strat_file.write_text(json.dumps(data), encoding="utf-8")

    report = verify_reproducible(ws)
    assert report["reproducible"] is False
    assert report["disposition"] == HOLD
    strategy_stage = next(s for s in report["stages"] if s["kind"] == "strategy")
    assert strategy_stage["match"] is False


def test_verify_repro_extends_to_generation_editing_planning(tmp_path):
    """B6: the reproducibility guarantee reaches the GENERATION/EDITING planning stages."""
    from asur.editing.timeline import (
        build_edit_plan,
        build_timeline_from_generation_plan,
    )
    from asur.generation.asset_strategy import build_asset_plan
    from asur.generation.creative_direction import build_creative_direction
    from asur.generation.generation_plan import build_generation_plan
    from asur.generation.visual_screenplay import build_visual_screenplay

    ws = _save_full_chain(tmp_path)
    strategy = ws.load_latest("strategy")
    script = ws.load_latest("script")
    direction = build_creative_direction(strategy, script, PROJECT_ID)
    ws.save_artifact(direction)
    screenplay = build_visual_screenplay(direction, script, PROJECT_ID)
    ws.save_artifact(screenplay)
    asset_plan = build_asset_plan(screenplay, PROJECT_ID)
    ws.save_artifact(asset_plan)
    gen_plan = build_generation_plan(
        asset_plan, PROJECT_ID, visual_screenplay_artifact=screenplay
    )
    ws.save_artifact(gen_plan)
    timeline = build_timeline_from_generation_plan(gen_plan, screenplay, PROJECT_ID)
    edit_plan = build_edit_plan(timeline, gen_plan, PROJECT_ID)
    ws.save_artifact(edit_plan)

    report = verify_reproducible(ws)
    kinds = {s["kind"] for s in report["stages"] if s["match"] is True}
    for kind in ("creative_direction", "visual_screenplay", "asset_plan",
                 "generation_plan", "edit_plan"):
        assert kind in kinds, f"{kind} did not reproduce"
    assert report["reproducible"] is True
    assert report["disposition"] == SHIP


def test_verify_repro_skips_non_deterministic_stages(tmp_path):
    """A present viral_check is reported as skipped, not claimed reproduced."""
    from asur.tools.projection import build_viral_view
    from asur.viral_check.evaluate import build_viral_check

    ws = _save_full_chain(tmp_path)
    view = build_viral_view(
        bundle_hashes={"final.mp4": "sha256:abc"},
        provenance={"renderer": "FFmpeg", "render_cost_usd": 0},
        platform_facts={"aspect_ratio": "9:16"},
        rubric_metadata={"lane": "viral-check", "binding": "run-1"},
    )
    ws.save_artifact(build_viral_check(view, PROJECT_ID))

    report = verify_reproducible(ws)
    viral_stage = next(s for s in report["stages"] if s["kind"] == "viral_check")
    assert viral_stage["match"] is None
    assert "skipped" in viral_stage["note"]
    # The SCRIPT stages still reproduce, so the overall verdict is still SHIP.
    assert report["disposition"] == SHIP


def test_verify_repro_empty_workspace_holds(tmp_path):
    """Nothing to verify fails closed rather than claiming reproducibility."""
    ws = Workspace(tmp_path, PROJECT_ID).ensure()
    report = verify_reproducible(ws)
    assert report["stages"] == []
    assert report["reproducible"] is False
    assert report["disposition"] == HOLD


def test_verify_repro_is_read_only(tmp_path):
    """Verifying must not add any new artifact version to the workspace."""
    ws = _save_full_chain(tmp_path)
    before = {k: ws.latest_version(k) for k in (
        "idea", "research", "audience", "strategy", "hooks", "script", "qa_report",
    )}
    verify_reproducible(ws)
    after = {k: ws.latest_version(k) for k in before}
    assert before == after
