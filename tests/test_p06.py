"""P06 tests: section-by-section QA, regenerate-only-failing, and the 5-family
final QA (including the ideas-3 anti-AI Human Pass Test and the duration band)."""

from __future__ import annotations

from asur.core.envelope import verify_checksum
from asur.editing.timeline import (
    build_edit_plan,
    build_timeline_from_generation_plan,
)
from asur.generation.asset_strategy import build_asset_plan
from asur.generation.creative_direction import build_creative_direction
from asur.generation.final_qa import (
    HUMAN_PASS_CHECKS,
    QA_FAMILIES,
    build_final_qa_report,
    platform_family,
    run_final_qa,
    visual_family,
)
from asur.generation.generation_plan import build_generation_plan
from asur.generation.section_qa import (
    build_section_qa_report,
    check_section,
    sections_to_regenerate,
)
from asur.generation.visual_screenplay import build_visual_screenplay
from asur.script.audience import build_audience
from asur.script.hooks import build_hooks
from asur.script.idea import build_idea
from asur.script.research import build_research
from asur.script.script_builder import build_script
from asur.script.strategy import build_strategy

SAMPLE_IDEA = "why most people waste money on AI tools"
PROJECT_ID = "test-p06"


def _chain(project_id=PROJECT_ID):
    """Run the full idea -> edit_plan chain and return the artifacts P06 needs."""
    idea = build_idea(SAMPLE_IDEA, project_id)
    research = build_research(idea, project_id)
    audience = build_audience(idea, research, project_id)
    strategy = build_strategy(idea, audience, project_id)
    hooks = build_hooks(strategy, project_id)
    script = build_script(strategy, hooks, project_id)
    creative = build_creative_direction(strategy, script, project_id)
    screenplay = build_visual_screenplay(creative, script, project_id)
    asset_plan = build_asset_plan(screenplay, project_id)
    gen_plan = build_generation_plan(asset_plan, project_id)
    timeline = build_timeline_from_generation_plan(gen_plan, screenplay, project_id)
    edit_plan = build_edit_plan(timeline, gen_plan, project_id)
    return {"screenplay": screenplay, "edit_plan": edit_plan}


def _all_reviews(decision="approved"):
    """Record a decision for every manual-review check across the families."""
    reviews = {name: decision for name in HUMAN_PASS_CHECKS}
    for name in (
        "voice_clear",
        "music_not_burying_voice",
        "no_clipping",
        "captions_readable",
        "safe_area_respected",
        "shaping_correct",
        "matches_approved_script",
        "no_drift_from_hero_proof",
    ):
        reviews[name] = decision
    return reviews


def test_section_qa_all_pass_is_ready():
    """ASUR-GATE-01: every rendered+approved section passes section QA."""
    chain = _chain()
    sections = [
        {"section": name, "rendered_asset": f"{name}.mp4", "review": "approved"}
        for name in (
            "hook", "opening", "problem", "context", "story",
            "value", "proof", "payoff", "cta",
        )
    ]
    report = build_section_qa_report(chain["screenplay"], sections, PROJECT_ID)
    assert report.body["all_sections_pass"] is True
    assert report.body["regenerate_sections"] == []
    assert report.status == "ready"
    assert report.kind == "qa_report"
    assert verify_checksum(report) is True
    src_ids = [s["artifact_id"] for s in report.sources]
    assert chain["screenplay"].artifact_id in src_ids


def test_regenerate_only_the_failing_section():
    """ASUR-GATE-01: a rejected section is the ONLY one marked to regenerate."""
    sections = [
        {"section": "hook", "rendered_asset": "hook.mp4", "review": "approved"},
        {"section": "story", "rendered_asset": "story.mp4", "review": "rejected"},
        {"section": "cta", "rendered_asset": "cta.mp4", "review": "approved"},
    ]
    reports = [check_section(s) for s in sections]
    to_redo = sections_to_regenerate(reports)
    assert to_redo == ["story"]


def test_section_missing_render_fails_closed():
    """ASUR-GATE-01: a section with no rendered asset fails closed."""
    report = check_section({"section": "proof", "review": "approved"})
    assert report["status"] == "fail"
    assert report["reasons"]


def test_missing_expected_section_is_flagged():
    """ASUR-GATE-01: an expected section not produced appears as a failure."""
    chain = _chain()
    # Produce only one of the nine expected sections.
    sections = [
        {"section": "hook", "rendered_asset": "hook.mp4", "review": "approved"},
    ]
    report = build_section_qa_report(chain["screenplay"], sections, PROJECT_ID)
    assert report.body["all_sections_pass"] is False
    assert report.body["expected_section_count"] == 9
    assert report.body["produced_section_count"] == 1
    assert len(report.body["regenerate_sections"]) >= 8


def test_final_qa_holds_when_human_pass_not_reviewed():
    """ASUR-HONEST-01/G17: anti-AI Human Pass Test unreviewed -> fail closed to HOLD."""
    result = run_final_qa(width=1080, height=1920, duration_s=60.0, reviews={})
    assert result["disposition"] == "HOLD"
    assert result["substate"] == "HUMAN_REVIEW_REQUIRED"


def test_final_qa_ships_when_all_reviews_approved():
    """ASUR-GATE-01: all manual checks approved + correct dimensions -> SHIP."""
    result = run_final_qa(
        width=1080, height=1920, duration_s=60.0, reviews=_all_reviews("approved")
    )
    assert result["disposition"] == "SHIP"


def test_final_qa_blocks_on_rejected_human_pass_check():
    """ASUR-GATE-01/G17: a rejected anti-AI check blocks (QA_FAILED)."""
    reviews = _all_reviews("approved")
    reviews["skin_texture"] = "rejected"
    result = run_final_qa(width=1080, height=1920, duration_s=60.0, reviews=reviews)
    assert result["disposition"] == "BLOCK"
    assert result["substate"] == "QA_FAILED"


def test_visual_family_covers_all_anti_ai_checks():
    """G17: the visual family evaluates every named Human Pass Test check."""
    fam = visual_family({})
    assert fam["family"] == "visual"
    names = {c["check"] for c in fam["checks"]}
    assert names == set(HUMAN_PASS_CHECKS)
    assert len(HUMAN_PASS_CHECKS) == 6
    assert len(QA_FAMILIES) == 5


def test_duration_band_out_of_range_warns_not_fails():
    """G16: duration outside the declared 30-40s band warns, never hard-fails."""
    fam = platform_family(width=1080, height=1920, duration_s=50.0, target_band_s=(30.0, 40.0))
    band = next(c for c in fam["checks"] if c["check"] == "duration_band")
    assert band["status"] == "warn"
    # A warning must not block an otherwise-clean final QA.
    result = run_final_qa(
        width=1080, height=1920, duration_s=50.0,
        target_band_s=(30.0, 40.0), reviews=_all_reviews("approved"),
    )
    assert result["disposition"] == "SHIP"


def test_duration_band_in_range_passes():
    """G16: duration inside the declared band passes."""
    fam = platform_family(width=1080, height=1920, duration_s=35.0, target_band_s=(30.0, 40.0))
    band = next(c for c in fam["checks"] if c["check"] == "duration_band")
    assert band["status"] == "pass"


def test_no_target_band_passes_by_default():
    """G16: no declared band -> duration_band passes (60s default, no warning)."""
    fam = platform_family(width=1080, height=1920, duration_s=60.0, target_band_s=None)
    band = next(c for c in fam["checks"] if c["check"] == "duration_band")
    assert band["status"] == "pass"


def test_wrong_dimensions_block_final_qa():
    """ASUR-GATE-01: a non-9:16 render fails the platform family and blocks."""
    fam = platform_family(width=720, height=1280, duration_s=60.0)
    dims = next(c for c in fam["checks"] if c["check"] == "dimensions")
    assert dims["status"] == "fail"
    result = run_final_qa(
        width=720, height=1280, duration_s=60.0, reviews=_all_reviews("approved")
    )
    assert result["disposition"] == "BLOCK"


def test_final_qa_report_lineage_and_checksum():
    """ASUR-PROV-01/VERSION-01: final QA report links to the edit plan and checksums."""
    chain = _chain()
    report = build_final_qa_report(
        chain["edit_plan"], PROJECT_ID,
        width=1080, height=1920, duration_s=60.0, reviews=_all_reviews("approved"),
    )
    assert report.kind == "qa_report"
    assert report.body["stage"] == "final_qa"
    assert report.status == "ready"
    assert verify_checksum(report) is True
    src_ids = [s["artifact_id"] for s in report.sources]
    assert chain["edit_plan"].artifact_id in src_ids
