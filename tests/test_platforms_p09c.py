"""P09c: long-form (16:9) hero-proof routing + long-form publish fields.

Stdlib-only, offline, no-network, no-GPU. Adapters are never imported (G10);
when ffprobe is absent the render verifier degrades to 'skipped'.

These tests pin two seams that P09c closes:

  * generation/hero_proof.py  -- target spec + render verification must read
    the chosen platform pack's FormatSpec instead of the 1080x1920 literal,
    while the default (no platform) call stays byte-identical to Instagram
    Reels (ASUR-VERSION-01 / G19 "IG default reproduced byte-for-byte").

  * learning/publish_package.py -- when the pack declares long-form publish
    fields (description/tags/chapters/category/end_screen/cards) the package
    must carry them; the Instagram default must emit none of them.

Routing choice recorded under G19 (no new SPEC-GAP): the long-form hero-proof
max duration is sourced from the pack's already-declared ``duration_band_s``
upper bound (youtube_long -> 1200.0). Instagram declares no band, so the hero
cap falls back to the module default (15.0), keeping the default byte-identical.
"""

from __future__ import annotations

import pytest

from asur.core.envelope import make_artifact
from asur.generation import hero_proof
from asur.generation.asset_strategy import build_asset_plan
from asur.generation.creative_direction import build_creative_direction
from asur.generation.generation_plan import build_generation_plan
from asur.generation.hero_proof import build_hero_proof, verify_render
from asur.generation.visual_screenplay import build_visual_screenplay
from asur.learning.publish_package import build_publish_package
from asur.platforms import UnknownPlatform, get_platform
from asur.script.audience import build_audience
from asur.script.hooks import build_hooks
from asur.script.idea import build_idea
from asur.script.research import build_research
from asur.script.script_builder import build_script
from asur.script.strategy import build_strategy

SAMPLE_IDEA = "why most people waste money on AI tools"
PROJECT_ID = "test-p09c"


def _gen_inputs(project_id: str = PROJECT_ID):
    """Build the (generation_plan, visual_screenplay) pair build_hero_proof needs.

    Mirrors tests/test_generation.py::_generation_chain but returns only the two
    artifacts the hero-proof seam consumes.
    """
    idea = build_idea(SAMPLE_IDEA, project_id)
    research = build_research(idea, project_id)
    audience = build_audience(idea, research, project_id)
    strategy = build_strategy(idea, audience, project_id)
    hooks = build_hooks(strategy, project_id)
    script = build_script(strategy, hooks, project_id)
    creative = build_creative_direction(strategy, script, project_id)
    screenplay = build_visual_screenplay(creative, script, project_id)
    asset_plan = build_asset_plan(screenplay, project_id, monetized=True)
    gen_plan = build_generation_plan(asset_plan, project_id)
    return gen_plan, screenplay


def _edit_and_viral():
    """Fixture pair for publish-package tests (mirrors test_platforms_wiring)."""
    edit = make_artifact(
        kind="edit_plan",
        project_id="proj-pp",
        body={"subject": "demo", "clip_count": 3},
        status="ready",
        agent="editing",
    )
    viral = make_artifact(
        kind="viral_check",
        project_id="proj-pp",
        body={"verdict": "proceed"},
        status="ready",
        agent="viral-check",
    )
    return edit, viral


# --------------------------------------------------------------------------- #
# hero_proof: platform routing
# --------------------------------------------------------------------------- #


def test_hero_proof_default_still_vertical():
    """Regression anchor: default (no platform) stays 9:16 / 1080x1920 / 15s."""
    gen_plan, screenplay = _gen_inputs()
    hero = build_hero_proof(gen_plan, screenplay, PROJECT_ID)
    spec = hero.body["target_spec"]
    assert spec["width"] == 1080
    assert spec["height"] == 1920
    assert spec["aspect_ratio"] == "9:16"
    assert spec["max_duration_s"] == 15.0


def test_hero_proof_youtube_long_is_landscape():
    """Long-form hero proof reads the 16:9 pack; cap comes from the pack band."""
    gen_plan, screenplay = _gen_inputs()
    hero = build_hero_proof(gen_plan, screenplay, PROJECT_ID, platform="youtube_long")
    spec = hero.body["target_spec"]
    assert spec["width"] == 1920
    assert spec["height"] == 1080
    assert spec["aspect_ratio"] == "16:9"
    # Sourced from the pack's declared duration_band_s upper bound (1200.0),
    # not an invented long-form constant (ASUR anti-hallucination, G19).
    band = get_platform("youtube_long").format_spec.duration_band_s
    assert band is not None
    assert spec["max_duration_s"] == band[1]


def test_hero_proof_unknown_platform_fails_closed():
    gen_plan, screenplay = _gen_inputs()
    with pytest.raises(UnknownPlatform):
        build_hero_proof(gen_plan, screenplay, PROJECT_ID, platform="tiktok")


def test_verify_render_accepts_platform_and_degrades(tmp_path, monkeypatch):
    """verify_render threads a platform; with ffprobe absent it degrades (G10)."""
    monkeypatch.setattr(hero_proof, "_ffprobe_available", lambda: False)
    video = tmp_path / "hero.mp4"
    video.write_bytes(b"")
    result = verify_render(video, platform="youtube_long")
    assert result["status"] == "skipped"


def test_verify_render_unknown_platform_fails_closed(tmp_path):
    video = tmp_path / "hero.mp4"
    video.write_bytes(b"")
    with pytest.raises(UnknownPlatform):
        verify_render(video, platform="tiktok")


# --------------------------------------------------------------------------- #
# publish_package: long-form fields
# --------------------------------------------------------------------------- #

_LONGFORM_KEYS = ("description", "tags", "chapters", "category", "end_screen", "cards")


def test_publish_default_has_no_longform_keys():
    """Instagram default emits none of the long-form keys (byte-identical)."""
    edit, viral = _edit_and_viral()
    pkg = build_publish_package(edit, viral, "proj-pp", title="t", caption="c")
    for key in _LONGFORM_KEYS:
        assert key not in pkg.body


def test_publish_youtube_long_emits_longform_fields():
    edit, viral = _edit_and_viral()
    pkg = build_publish_package(
        edit, viral, "proj-pp", title="t", caption="c", platform="youtube_long"
    )
    body = pkg.body
    assert isinstance(body["description"], str)
    assert isinstance(body["chapters"], list)
    assert isinstance(body["tags"], list)
    assert "category" in body
    assert "end_screen" in body
    assert "cards" in body


def test_publish_youtube_long_unknown_fails_closed():
    edit, viral = _edit_and_viral()
    with pytest.raises(UnknownPlatform):
        build_publish_package(
            edit, viral, "proj-pp", title="t", caption="c", platform="tiktok"
        )
