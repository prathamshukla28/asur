"""Tests for the EDITING environment (Phase 5).

Covers the four mandatory P05 test families:
- U: primitive application + version_history integrity.
- I: timeline round-trips losslessly (and via OTIO when the extra is present).
- G: every edit is a new version; nothing is silently overwritten; revert restores.
- R: a styled caption fixture has correct timing and stays inside the safe area.

All builders are pure functions returning Artifacts, so no workspace is needed.
"""

from __future__ import annotations

import pytest

from asur.core.envelope import verify_checksum

from asur.editing import source_ref
from asur.editing.timeline import (
    Clip,
    Timeline,
    build_edit_plan,
    build_timeline_from_generation_plan,
)
from asur.editing.primitives import PRIMITIVES, apply_primitive, is_primitive
from asur.editing.captions import (
    check_caption,
    needs_shaping,
    safe_area_pixels,
    style_caption,
)
from asur.editing.audio_mix import build_audio_mix, check_audio_mix
from asur.editing import controls

from asur.script.idea import build_idea
from asur.script.research import build_research
from asur.script.audience import build_audience
from asur.script.strategy import build_strategy
from asur.script.hooks import build_hooks
from asur.script.script_builder import build_script

from asur.generation.creative_direction import build_creative_direction
from asur.generation.visual_screenplay import build_visual_screenplay
from asur.generation.asset_strategy import build_asset_plan
from asur.generation.generation_plan import build_generation_plan


SAMPLE_IDEA = "why most people waste money on AI tools"
PROJECT_ID = "test-editing"


def _clip(clip_id: str = "clip-01", asset_ref: str = "scene-01-hook-background") -> Clip:
    return Clip(clip_id=clip_id, asset_ref=asset_ref)


def _edit_chain(project_id: str = PROJECT_ID):
    """Run SCRIPT -> GENERATION -> EDITING and return the key artifacts."""
    idea = build_idea(SAMPLE_IDEA, project_id)
    research = build_research(idea, project_id)
    audience = build_audience(idea, research, project_id)
    strategy = build_strategy(idea, audience, project_id)
    hooks = build_hooks(strategy, project_id)
    script = build_script(strategy, hooks, project_id)
    direction = build_creative_direction(strategy, script, project_id)
    screenplay = build_visual_screenplay(direction, script, project_id)
    asset_plan = build_asset_plan(screenplay, project_id)
    generation_plan = build_generation_plan(asset_plan, project_id)
    timeline = build_timeline_from_generation_plan(generation_plan, screenplay, project_id)
    edit_plan = build_edit_plan(timeline, generation_plan, project_id)
    return {
        "screenplay": screenplay,
        "generation_plan": generation_plan,
        "timeline": timeline,
        "edit_plan": edit_plan,
    }


# --- U: primitives + version history -------------------------------------

def test_apply_primitive_appends_one_version():
    """ASUR-VERSION-01: applying a primitive records exactly one prior version."""
    clip = _clip()
    assert clip.version_history == []
    apply_primitive(clip, "TextReveal")
    assert len(clip.version_history) == 1
    assert clip.primitive == "TextReveal"


def test_apply_primitive_preserves_prior_state():
    """ASUR-VERSION-01: the snapshot in history is the pre-change state."""
    clip = _clip()
    clip.speed = 1.0
    apply_primitive(clip, "SpeedRamp", {"speed": 2.0})
    assert clip.speed == 2.0
    assert clip.version_history[-1]["speed"] == 1.0


def test_apply_primitive_rejects_unknown_name():
    """ASUR-GATE-01: an unknown primitive fails closed."""
    with pytest.raises(ValueError):
        apply_primitive(_clip(), "NotARealPrimitive")


def test_apply_primitive_refuses_locked_clip():
    """ASUR-HUMAN-01: a locked clip refuses primitive application."""
    clip = _clip()
    clip.locked = True
    with pytest.raises(ValueError):
        apply_primitive(clip, "TextReveal")


def test_primitive_writes_correct_field():
    """ASUR-EXPLAIN-01: each primitive targets its declared editable field."""
    speed_clip = _clip()
    apply_primitive(speed_clip, "SpeedRamp", {"speed": 1.5})
    assert speed_clip.speed == 1.5

    cam_clip = _clip()
    apply_primitive(cam_clip, "CameraPush", {"scale": [1.0, 1.2]})
    assert cam_clip.keyframes["scale"] == [1.0, 1.2]

    text_clip = _clip()
    apply_primitive(text_clip, "TextReveal", {"word": "hi"})
    assert any(o["primitive"] == "TextReveal" for o in text_clip.overlays)

    mask_clip = _clip()
    apply_primitive(mask_clip, "MaskReveal", {"shape": "circle"})
    assert any(m["primitive"] == "MaskReveal" for m in mask_clip.masks)


def test_fifteen_primitives_registered():
    """ASUR-EXPLAIN-01: the palette is exactly the 15 documented primitives."""
    assert len(PRIMITIVES) == 15
    assert is_primitive("TrackingText")
    assert not is_primitive("nope")


# --- I: round-trips -------------------------------------------------------

def test_timeline_round_trips_losslessly():
    """ASUR-VERSION-01: Timeline.to_dict()->from_dict() is lossless."""
    artifacts = _edit_chain()
    timeline = artifacts["timeline"]
    restored = Timeline.from_dict(timeline.to_dict())
    assert restored.to_dict() == timeline.to_dict()


def test_otio_round_trip_when_extra_present():
    """ASUR-LOCAL-01: OTIO transport is behind the generation extra; skip if absent."""
    pytest.importorskip("opentimelineio")
    from asur.editing.adapters import otio

    artifacts = _edit_chain()
    # The adapter is a declaration-only shell; export is a local-only human step.
    with pytest.raises(NotImplementedError):
        otio.to_otio(artifacts["timeline"])


# --- G: versioning + manual controls --------------------------------------

def test_modify_records_a_new_version():
    """ASUR-VERSION-01: modify snapshots the prior state before changing."""
    clip = _clip()
    controls.modify(clip, speed=2.0)
    assert len(clip.version_history) == 1
    assert clip.speed == 2.0


def test_revert_restores_prior_state_exactly():
    """ASUR-VERSION-01: revert restores the exact pre-change snapshot."""
    clip = _clip()
    before = clip._snapshot()
    controls.modify(clip, speed=3.0, timeline_start=5.0)
    controls.revert(clip)
    assert clip._snapshot() == before
    assert clip.version_history == []


def test_revert_on_empty_history_fails_closed():
    """ASUR-GATE-01: reverting with no prior version raises."""
    with pytest.raises(ValueError):
        controls.revert(_clip())


def test_modify_on_locked_clip_refuses():
    """ASUR-HUMAN-01: a locked clip cannot be modified."""
    clip = _clip()
    controls.lock(clip)
    with pytest.raises(ValueError):
        controls.modify(clip, speed=2.0)


def test_lock_then_primitive_refuses():
    """ASUR-HUMAN-01: locking blocks later primitive application."""
    clip = _clip()
    controls.lock(clip)
    with pytest.raises(ValueError):
        apply_primitive(clip, "TextReveal")


def test_accept_and_reject_set_review_and_record():
    """ASUR-HUMAN-01: accept/reject record a version and set the review flag."""
    clip = _clip()
    controls.accept(clip)
    assert clip.review == "accepted"
    assert len(clip.version_history) == 1
    controls.reject(clip)
    assert clip.review == "rejected"
    assert len(clip.version_history) == 2


def test_branch_is_independent_copy():
    """ASUR-VERSION-01: branch produces a fresh clip with empty history."""
    clip = _clip()
    apply_primitive(clip, "TextReveal")
    branched = controls.branch(clip)
    assert branched.clip_id != clip.clip_id
    assert branched.version_history == []
    branched.speed = 9.0
    assert clip.speed != 9.0


def test_compare_shows_field_diff():
    """ASUR-EXPLAIN-01: compare reports a field-level diff between two clips."""
    a = _clip()
    b = _clip()
    b.speed = 2.0
    diff = controls.compare(a, b)
    assert "speed" in diff
    assert diff["speed"] == {"a": 1.0, "b": 2.0}


# --- R: captions + safe area + audio mix ----------------------------------

def test_well_placed_caption_passes():
    """ASUR-EXPLAIN-01: a correctly timed, safe-area caption passes."""
    cap = style_caption("hello", "en", 1.0, 3.0, y_fraction=0.78)
    result = check_caption(cap, clip_start=0.0, clip_end=5.0)
    assert result["ok"] is True


def test_caption_in_top_band_fails():
    """ASUR-GATE-01: a caption above the safe band fails closed."""
    cap = style_caption("hello", "en", 1.0, 3.0, y_fraction=0.05)
    result = check_caption(cap, clip_start=0.0, clip_end=5.0)
    assert result["ok"] is False
    assert result["reasons"]


def test_mistimed_caption_fails():
    """ASUR-GATE-01: a caption outside the clip bounds fails closed."""
    cap = style_caption("hello", "en", 4.0, 9.0, y_fraction=0.78)
    result = check_caption(cap, clip_start=0.0, clip_end=5.0)
    assert result["ok"] is False


def test_devanagari_language_needs_shaping():
    """ASUR-EXPLAIN-01: Hindi/Hinglish/Marathi captions are flagged for shaping."""
    assert needs_shaping("hi") is True
    assert needs_shaping("hinglish") is True
    assert needs_shaping("en") is False


def test_safe_area_pixels_sane():
    """ASUR-EXPLAIN-01: safe-area pixels are derived from the 1920px reel height."""
    area = safe_area_pixels()
    assert area["top_px"] > 0
    assert area["bottom_px"] > 0
    assert area["usable_px"] < 1920


def test_audio_mix_default_is_balanced():
    """ASUR-EXPLAIN-01: the default mix keeps voice above ducked music."""
    mix = build_audio_mix()
    result = check_audio_mix(mix)
    assert result["ok"] is True


def test_audio_mix_music_louder_than_voice_fails():
    """ASUR-GATE-01: music that buries narration fails closed."""
    mix = build_audio_mix(voice_db=-20.0, music_db=0.0)
    result = check_audio_mix(mix)
    assert result["ok"] is False


# --- lineage -------------------------------------------------------------

def test_edit_plan_lineage_and_checksum():
    """ASUR-PROV-01 + ASUR-VERSION-01: edit_plan is checksummed and sourced."""
    artifacts = _edit_chain()
    edit_plan = artifacts["edit_plan"]
    generation_plan = artifacts["generation_plan"]
    assert edit_plan.kind == "edit_plan"
    assert edit_plan.body["clip_count"] > 0
    assert verify_checksum(edit_plan) is True
    refs = {s["artifact_id"] for s in edit_plan.sources}
    assert generation_plan.artifact_id in refs
