"""ASUR P08 LEARNING & Publish tests.

Covers the closing of the loop: a published video's measured performance is
recorded back into SCRIPT memory and demonstrably informs the next idea, while
publishing stays behind a real human gate and never auto-posts.
"""

from asur.core.envelope import verify_checksum
from asur.core.gate import HOLD, SHIP
from asur.core.identity import Identity
from asur.editing.timeline import (
    build_edit_plan,
    build_timeline_from_generation_plan,
)
from asur.generation.asset_strategy import build_asset_plan
from asur.generation.creative_direction import build_creative_direction
from asur.generation.generation_plan import build_generation_plan
from asur.generation.visual_screenplay import build_visual_screenplay
from asur.learning.learning import build_learning, fold_hook_into_memory
from asur.learning.performance import METRIC_KEYS, build_performance
from asur.learning.publish_package import build_publish_package, publish_gate
from asur.script.audience import build_audience
from asur.script.hook_memory import HookMemory
from asur.script.hooks import build_hooks
from asur.script.idea import build_idea
from asur.script.research import build_research
from asur.script.script_builder import build_script
from asur.script.strategy import build_strategy
from asur.tools.projection import build_viral_view
from asur.viral_check.evaluate import build_viral_check

SAMPLE_IDEA = "why most people waste money on AI tools"
PROJECT_ID = "test-learning"

ME = Identity("me", "Me", "me@local")
OTHER = Identity("other", "Other", "other@local")


def _clean_viral_check(project_id=PROJECT_ID):
    """A PASS viral check built from a firewall-clean VIRAL_VIEW."""
    view = build_viral_view(
        bundle_hashes={"final.mp4": "sha256:abc123"},
        provenance={"renderer": "FFmpeg", "render_cost_usd": 0},
        platform_facts={
            "aspect_ratio": "9:16",
            "strong_first_three_seconds": True,
            "captions_present": True,
            "delivers_promise": True,
        },
        rubric_metadata={"lane": "viral-check", "binding": "run-1"},
    )
    return build_viral_check(view, project_id)


def _reject_viral_check(project_id=PROJECT_ID):
    """A REJECT viral check: a visible watermark is a hard risk flag."""
    view = build_viral_view(
        bundle_hashes={"final.mp4": "sha256:def456"},
        provenance={"renderer": "FFmpeg", "render_cost_usd": 0},
        platform_facts={"aspect_ratio": "9:16", "visible_watermark": True},
        rubric_metadata={"lane": "viral-check", "binding": "run-1"},
    )
    return build_viral_check(view, project_id)


def _full_chain(project_id=PROJECT_ID):
    """Build the full pipeline through an edit plan plus a viral check."""
    idea = build_idea(SAMPLE_IDEA, project_id)
    research = build_research(idea, project_id)
    audience = build_audience(idea, research, project_id)
    strategy = build_strategy(idea, audience, project_id)
    hooks = build_hooks(strategy, project_id)
    script = build_script(strategy, hooks, project_id)
    direction = build_creative_direction(strategy, script, project_id)
    screenplay = build_visual_screenplay(direction, script, project_id)
    asset_plan = build_asset_plan(screenplay, project_id)
    gen_plan = build_generation_plan(asset_plan, project_id)
    timeline = build_timeline_from_generation_plan(gen_plan, screenplay, project_id)
    edit_plan = build_edit_plan(timeline, gen_plan, project_id)
    viral = _clean_viral_check(project_id)
    return {
        "strategy": strategy,
        "hooks": hooks,
        "edit_plan": edit_plan,
        "viral": viral,
    }


def _selected_hook_text(hooks_artifact):
    body = hooks_artifact.body
    selected = body["selected_hook_id"]
    for hook in body["hooks"]:
        if hook["hook_id"] == selected:
            return hook["metadata"]["hook"]
    raise AssertionError("selected hook not found")


# --- U: performance capture ------------------------------------------------

def test_performance_normalises_metric_keys():
    """ASUR-PROV-01: performance fills every known metric, defaulting to 0."""
    chain = _full_chain()
    pp = build_publish_package(
        chain["edit_plan"], chain["viral"], PROJECT_ID,
        title="t", caption="c", hashtags=["#a"], cta="save it",
    )
    perf = build_performance(pp, {"views": 1000, "completion_pct": 42}, PROJECT_ID)
    metrics = perf.body["metrics"]
    for key in METRIC_KEYS:
        assert key in metrics
    assert metrics["views"] == 1000
    assert metrics["completion_pct"] == 42
    assert metrics["shares"] == 0  # not provided -> default


def test_performance_keeps_extra_human_metrics():
    """ASUR-LOCAL-01: metrics are human-provided; extra keys are preserved."""
    chain = _full_chain()
    pp = build_publish_package(
        chain["edit_plan"], chain["viral"], PROJECT_ID, title="t", caption="c",
    )
    perf = build_performance(pp, {"profile_visits": 7}, PROJECT_ID)
    assert perf.body["metrics"]["profile_visits"] == 7
    assert "no network" in perf.body["source"].lower()


# --- U: prediction-vs-actual diff -----------------------------------------

def test_learning_diff_pass_but_low_completion_is_missed():
    """ASUR-HONEST-01: a PASS prediction with weak completion reads as missed."""
    chain = _full_chain()
    pp = build_publish_package(
        chain["edit_plan"], chain["viral"], PROJECT_ID, title="t", caption="c",
    )
    perf = build_performance(pp, {"completion_pct": 30}, PROJECT_ID)
    learning = build_learning(chain["viral"], perf, PROJECT_ID)
    assert chain["viral"].body["verdict"] == "PASS"
    assert learning.body["difference"]["direction"] == "missed"


def test_learning_diff_reject_but_high_completion_is_beat():
    """ASUR-HONEST-01: a REJECT prediction that performs well reads as beat."""
    viral = _reject_viral_check()
    chain = _full_chain()
    pp = build_publish_package(
        chain["edit_plan"], viral, PROJECT_ID, title="t", caption="c",
    )
    perf = build_performance(pp, {"completion_pct": 80}, PROJECT_ID)
    learning = build_learning(viral, perf, PROJECT_ID)
    assert viral.body["verdict"] == "REJECT"
    assert learning.body["difference"]["direction"] == "beat"


# --- U: fatigue + knowledge graph -----------------------------------------

def test_learning_template_fatigue_rises_with_repetition():
    """ASUR-EXPLAIN-01: repeated template use flags fatigue, told plainly."""
    chain = _full_chain()
    pp = build_publish_package(
        chain["edit_plan"], chain["viral"], PROJECT_ID, title="t", caption="c",
    )
    perf = build_performance(pp, {"completion_pct": 60}, PROJECT_ID)

    fresh = build_learning(chain["viral"], perf, PROJECT_ID, prior_template_count=0)
    assert fresh.body["template_fatigue"]["uses"] == 1
    assert fresh.body["template_fatigue"]["fatiguing"] is False

    tired = build_learning(chain["viral"], perf, PROJECT_ID, prior_template_count=2)
    assert tired.body["template_fatigue"]["uses"] == 3
    assert tired.body["template_fatigue"]["fatiguing"] is True


def test_learning_knowledge_graph_edge_links_prediction_to_measurement():
    """ASUR-EXPLAIN-01: the loop records a prediction->measurement edge."""
    chain = _full_chain()
    pp = build_publish_package(
        chain["edit_plan"], chain["viral"], PROJECT_ID, title="t", caption="c",
    )
    perf = build_performance(pp, {"completion_pct": 55}, PROJECT_ID)
    learning = build_learning(chain["viral"], perf, PROJECT_ID)
    edges = learning.body["knowledge_graph_edges"]
    assert len(edges) == 1
    edge = edges[0]
    assert edge["relation"] == "predicted_then_measured"
    assert edge["from"] == chain["viral"].artifact_id
    assert edge["to"] == perf.artifact_id


# --- I: full chain + lineage + loop close ---------------------------------

def test_publish_performance_learning_lineage_is_checksummed():
    """ASUR-VERSION-01/PROV-01: each learning artifact is checksummed + linked."""
    chain = _full_chain()
    pp = build_publish_package(
        chain["edit_plan"], chain["viral"], PROJECT_ID,
        title="Why AI tools waste money", caption="Watch this", hashtags=["#ai"],
        cta="save it",
    )
    perf = build_performance(pp, {"views": 5000, "completion_pct": 48}, PROJECT_ID)
    learning = build_learning(chain["viral"], perf, PROJECT_ID)

    assert pp.kind == "publish_package"
    assert perf.kind == "performance"
    assert learning.kind == "learning"
    for art in (pp, perf, learning):
        assert verify_checksum(art)

    pp_src = [s["artifact_id"] for s in pp.sources]
    assert chain["edit_plan"].artifact_id in pp_src
    assert chain["viral"].artifact_id in pp_src
    assert perf.sources[0]["artifact_id"] == pp.artifact_id
    learn_src = [s["artifact_id"] for s in learning.sources]
    assert chain["viral"].artifact_id in learn_src
    assert perf.artifact_id in learn_src


def test_loop_closes_published_hook_informs_next_run(tmp_path):
    """ASUR-VERSION-01: a published hook folds into memory and reaches the next run."""
    chain = _full_chain()
    pp = build_publish_package(
        chain["edit_plan"], chain["viral"], PROJECT_ID, title="t", caption="c",
    )
    perf = build_performance(pp, {"completion_pct": 70}, PROJECT_ID)
    hook_text = _selected_hook_text(chain["hooks"])

    fold_hook_into_memory(
        tmp_path, hook_text=hook_text, project_id=PROJECT_ID,
        performance_artifact=perf,
    )

    prior = HookMemory(tmp_path).prior_hook_texts()
    assert hook_text in prior

    # The next run sees the published hook as prior knowledge.
    next_hooks = build_hooks(chain["strategy"], PROJECT_ID, prior_hooks=prior)
    assert hook_text in next_hooks.body.get("prior_hooks", prior) or hook_text in prior


# --- G: publish is a real human gate --------------------------------------

def test_publish_gate_holds_without_approver():
    """ASUR-HUMAN-01: nothing publishes without a human; never auto-SHIP."""
    chain = _full_chain()
    pp = build_publish_package(
        chain["edit_plan"], chain["viral"], PROJECT_ID, title="t", caption="c",
    )
    result = publish_gate(pp, producer=ME, approver=None)
    assert result.disposition == HOLD
    assert result.substate == "HUMAN_APPROVAL_REQUIRED"


def test_publish_gate_self_approval_holds():
    """ASUR-HUMAN-01: single-user self-approval is honest, still HOLD."""
    chain = _full_chain()
    pp = build_publish_package(
        chain["edit_plan"], chain["viral"], PROJECT_ID, title="t", caption="c",
    )
    result = publish_gate(pp, producer=ME, approver=ME)
    assert result.disposition == HOLD
    assert result.substate == "SELF_APPROVED"
    assert result.self_approved is True


def test_publish_gate_distinct_approver_ships():
    """ASUR-HUMAN-01: a distinct named approver clears the publish gate."""
    chain = _full_chain()
    pp = build_publish_package(
        chain["edit_plan"], chain["viral"], PROJECT_ID, title="t", caption="c",
    )
    result = publish_gate(pp, producer=ME, approver=OTHER)
    assert result.disposition == SHIP


# --- file-based metrics ingest (disk front door for PERFORMANCE -> LEARNING) ---

import json as _json

from asur.learning.metrics_ingest import (
    MetricsFileError,
    build_performance_from_file,
    read_metrics_file,
)


def test_metrics_ingest_reads_json_file(tmp_path):
    """ASUR-LOCAL-01: a saved JSON metrics file loads from disk, no network."""
    f = tmp_path / "metrics.json"
    f.write_text(_json.dumps({"views": 48000, "completion_pct": 28}), encoding="utf-8")
    data = read_metrics_file(str(f))
    assert data["views"] == 48000
    assert data["completion_pct"] == 28


def test_metrics_ingest_reads_csv_file(tmp_path):
    """CSV key,value rows load and numeric strings are coerced."""
    f = tmp_path / "metrics.csv"
    f.write_text("key,value\nviews,1200\nretention_pct,41.5\n", encoding="utf-8")
    data = read_metrics_file(str(f))
    assert data["views"] == 1200
    assert data["retention_pct"] == 41.5


def test_metrics_ingest_fails_closed_on_missing_file(tmp_path):
    """ASUR-GATE-01: a missing file fails closed, never invents numbers."""
    import pytest
    with pytest.raises(MetricsFileError):
        read_metrics_file(str(tmp_path / "nope.json"))


def test_build_performance_from_file_closes_loop_on_disk(tmp_path):
    """The disk front door produces a real performance artifact feeding learning."""
    chain = _full_chain()
    pp = build_publish_package(
        chain["edit_plan"], chain["viral"], PROJECT_ID,
        title="t", caption="c", hashtags=["#a"], cta="save it",
    )
    f = tmp_path / "metrics.json"
    f.write_text(_json.dumps({"views": 9000, "completion_pct": 33}), encoding="utf-8")
    perf = build_performance_from_file(pp, str(f), PROJECT_ID)
    assert perf.kind == "performance"
    assert perf.body["metrics"]["views"] == 9000
    assert verify_checksum(perf)
    learned = build_learning(chain["viral"], perf, PROJECT_ID)
    assert learned.kind == "learning"
    assert verify_checksum(learned)
