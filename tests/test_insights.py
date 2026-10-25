"""Tests for the creator insights view and the A/B experiment resolver (B4, B5).

Covers the learning loop made visible: aggregation of a creator's own hook
memory into EMPIRICAL learnings with no aggregate score, and a measured-winner
A/B resolution that fails closed until real performance exists.
"""

from asur.core.gate import HOLD, SHIP
from asur.learning.ab_resolution import resolve_ab_experiment
from asur.learning.insights import build_insights
from asur.script.hook_memory import HookMemory
from asur.script.hooks import build_hooks
from asur.script.idea import build_idea

PROJECT_ID = "test-insights"


def _strategy():
    """A strategy artifact to feed build_hooks (minimal real chain)."""
    from asur.script.audience import build_audience
    from asur.script.research import build_research
    from asur.script.strategy import build_strategy

    idea = build_idea("why most people waste money on AI tools", PROJECT_ID)
    research = build_research(idea, PROJECT_ID)
    audience = build_audience(idea, research, PROJECT_ID)
    return build_strategy(idea, audience, PROJECT_ID)


def _record_published(mem, hook_text, *, category, pattern, completion):
    mem.record(
        hook_text=hook_text,
        event="published",
        project_id=PROJECT_ID,
        metadata={
            "category": category,
            "pattern": pattern,
            "performance": {"completion_pct": completion},
        },
    )


# --- B4: insights ----------------------------------------------------------

def test_insights_empty_memory_is_honest(tmp_path):
    """No memory yet: a truthful 'seed the loop' learning, no fabricated numbers."""
    report = build_insights(tmp_path, PROJECT_ID)
    assert report["totals"]["records"] == 0
    assert report["learnings"]
    assert "no" in report["learnings"][0]["text"].lower()
    # No aggregate score / % viral anywhere.
    assert "stage" in report and report["stage"] == "insights"


def test_insights_ranks_directions_by_measured_completion(tmp_path):
    """The direction with the best measured completion surfaces first."""
    mem = HookMemory(tmp_path).ensure()
    _record_published(mem, "curious hook", category="curiosity", pattern="q", completion=70)
    _record_published(mem, "contrarian hook", category="contrarian", pattern="c", completion=40)

    report = build_insights(tmp_path, PROJECT_ID)
    assert report["totals"]["published"] == 2
    assert report["totals"]["with_measured_performance"] == 2
    top = report["by_direction"][0]
    assert top["direction"] == "curiosity"
    assert top["avg_completion"] == 70.0
    assert any("curiosity" in c["text"] for c in report["learnings"])


def test_insights_flags_pattern_fatigue(tmp_path):
    """A pattern used 3+ times is flagged as fatiguing (EMPIRICAL)."""
    mem = HookMemory(tmp_path).ensure()
    for i in range(3):
        _record_published(mem, f"hook {i}", category="curiosity", pattern="question", completion=50)
    report = build_insights(tmp_path, PROJECT_ID)
    fatigue = {row["pattern"]: row for row in report["fatigue"]}
    assert fatigue["question"]["uses"] == 3
    assert fatigue["question"]["fatiguing"] is True
    assert any("question" in c["text"] for c in report["learnings"])


def test_insights_published_without_metrics_asks_for_them(tmp_path):
    """Published but unmeasured: it asks for metrics rather than inventing them."""
    mem = HookMemory(tmp_path).ensure()
    mem.record(hook_text="h", event="published", project_id=PROJECT_ID,
               metadata={"category": "story", "pattern": "p"})
    report = build_insights(tmp_path, PROJECT_ID)
    assert report["totals"]["with_measured_performance"] == 0
    assert "record" in report["next_experiment"].lower()


# --- B5: A/B resolution ----------------------------------------------------

def test_ab_resolve_holds_without_enough_measured_variants(tmp_path):
    """ASUR-HONEST-01: no winner implied until >=2 variants have real results."""
    hooks = build_hooks(_strategy(), PROJECT_ID)
    report = resolve_ab_experiment(hooks, HookMemory(tmp_path).all_records())
    assert report["status"] == "insufficient_data"
    assert report["winner"] is None
    assert report["disposition"] == HOLD


def test_ab_resolve_picks_measured_winner(tmp_path):
    """With real performance for two variants, the higher completion wins."""
    hooks = build_hooks(_strategy(), PROJECT_ID)
    variants = hooks.body["ab_variants"]["variants"]
    assert len(variants) >= 2, "need at least two variants to test resolution"

    mem = HookMemory(tmp_path).ensure()
    # Give the SECOND variant the better measured completion.
    _record_published(
        mem, variants[0]["chosen_hook"], category="a", pattern="p", completion=35
    )
    _record_published(
        mem, variants[1]["chosen_hook"], category="b", pattern="p", completion=72
    )

    report = resolve_ab_experiment(hooks, mem.all_records())
    assert report["status"] == "resolved"
    assert report["disposition"] == SHIP
    assert report["winner"]["variant"] == variants[1]["variant"]
    assert report["winner"]["measured_completion"] == 72.0


def test_ab_resolve_ignores_unmeasured_variant(tmp_path):
    """A variant with only one measured result still HOLDs (needs two)."""
    hooks = build_hooks(_strategy(), PROJECT_ID)
    variants = hooks.body["ab_variants"]["variants"]
    mem = HookMemory(tmp_path).ensure()
    _record_published(
        mem, variants[0]["chosen_hook"], category="a", pattern="p", completion=55
    )
    report = resolve_ab_experiment(hooks, mem.all_records())
    assert report["status"] == "insufficient_data"
