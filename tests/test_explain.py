"""Tests for ``asur explain`` - the read-only SCRIPT decision trail.

ASUR-EXPLAIN-01: every important decision is explainable with a recorded reason.
These tests prove the explainer surfaces those reasons with full provenance,
reads only what the stages actually wrote (never inventing an explanation), and
fails closed (reports what is missing) when the chain is incomplete.
"""

from asur.core.workspace import Workspace
from asur.script.audience import build_audience
from asur.script.hooks import build_hooks
from asur.script.idea import build_idea
from asur.script.quality_gate import build_qa_report
from asur.script.research import build_research
from asur.script.script_builder import build_script
from asur.script.strategy import build_strategy
from asur.tools.explain import SCRIPT_CHAIN, build_explanation

SAMPLE_IDEA = "why most people waste money on AI tools"
PROJECT_ID = "test-explain"


def _save_full_chain(tmp_path, project_id=PROJECT_ID) -> Workspace:
    """Build the SCRIPT chain and persist each artifact into a workspace."""
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


def test_explain_walks_script_chain_in_lineage_order(tmp_path):
    """Every SCRIPT stage appears, in order, with provenance.

    explain now walks the FULL pipeline (SCRIPT through LEARNING); a SCRIPT-only
    workspace therefore shows the seven SCRIPT stages and reports the downstream
    stages as not-yet-produced (so the chain is not 'complete').
    """
    ws = _save_full_chain(tmp_path)
    report = build_explanation(ws)

    kinds = [e["kind"] for e in report["entries"]]
    assert kinds == list(SCRIPT_CHAIN)
    assert report["complete"] is False  # downstream (render, viral_check, ...) not produced
    assert "viral_check" in report["missing"]

    for entry in report["entries"]:
        assert entry["artifact_id"]
        assert entry["checksum"]
        assert entry["version"] >= 1


def test_explain_surfaces_recorded_reasons_only(tmp_path):
    """ASUR-EXPLAIN-01: reasons come from the body; none are invented."""
    ws = _save_full_chain(tmp_path)
    report = build_explanation(ws)
    by_kind = {e["kind"]: e for e in report["entries"]}

    # The hooks stage records a selection_reason and the selected hook text.
    hooks = by_kind["hooks"]
    assert hooks["selected_hook"]
    assert any("selection_reason" in r for r in hooks["reasons"])

    # Every surfaced reason is a real, non-empty recorded string.
    for entry in report["entries"]:
        for reason in entry["reasons"]:
            assert isinstance(reason, str) and reason.strip()


def test_explain_shows_lineage_edges(tmp_path):
    """Downstream stages name the upstream artifacts they were built from."""
    ws = _save_full_chain(tmp_path)
    report = build_explanation(ws)
    by_kind = {e["kind"]: e for e in report["entries"]}

    idea_id = by_kind["idea"]["artifact_id"]
    # research is built from idea, so idea must appear in research's sources.
    assert idea_id in by_kind["research"]["sources"]
    # qa_report carries lineage too.
    assert by_kind["qa_report"]["sources"]


def test_explain_qa_headline_reports_gate_disposition(tmp_path):
    """The quality gate's recorded disposition is explained, not re-derived."""
    ws = _save_full_chain(tmp_path)
    report = build_explanation(ws)
    qa = next(e for e in report["entries"] if e["kind"] == "qa_report")
    assert "quality gate" in qa["headline"]
    assert "passed=" in qa["headline"]


def test_explain_covers_downstream_pipeline_stages(tmp_path):
    """B6: the trail extends past SCRIPT into GENERATION / VIRAL / LEARNING."""
    from asur.generation.creative_direction import build_creative_direction
    from asur.tools.projection import build_viral_view
    from asur.viral_check.evaluate import build_viral_check

    ws = _save_full_chain(tmp_path)
    strategy = ws.load_latest("strategy")
    script = ws.load_latest("script")
    direction = build_creative_direction(strategy, script, PROJECT_ID)
    ws.save_artifact(direction)

    view = build_viral_view(
        bundle_hashes={"final.mp4": "sha256:abc"},
        provenance={"renderer": "FFmpeg", "render_cost_usd": 0},
        platform_facts={"aspect_ratio": "9:16"},
        rubric_metadata={"lane": "viral-check", "binding": "run-1"},
    )
    viral = build_viral_check(view, PROJECT_ID)
    ws.save_artifact(viral)

    report = build_explanation(ws)
    by_kind = {e["kind"]: e for e in report["entries"]}
    assert "creative_direction" in by_kind
    assert "viral_check" in by_kind
    assert "verdict:" in by_kind["viral_check"]["headline"]


def test_explain_fails_closed_on_partial_chain(tmp_path):
    """ASUR-GATE-01: a half-built project explains what exists and flags the rest."""
    ws = Workspace(tmp_path, PROJECT_ID).ensure()
    idea = build_idea(SAMPLE_IDEA, PROJECT_ID)
    ws.save_artifact(idea)

    report = build_explanation(ws)
    assert [e["kind"] for e in report["entries"]] == ["idea"]
    assert report["complete"] is False
    assert "research" in report["missing"]


def test_explain_empty_workspace_is_empty_not_fabricated(tmp_path):
    """An empty project yields no entries - never a fabricated trail."""
    ws = Workspace(tmp_path, PROJECT_ID).ensure()
    report = build_explanation(ws)
    assert report["entries"] == []
    assert report["complete"] is False
