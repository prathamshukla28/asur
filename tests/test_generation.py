"""P04 GENERATION + Hero Proof tests.

Covers the founding invariants for the generation layer:

  ASUR-PROV-01     every asset carries a provenance + license block
  ASUR-GATE-01     the license guard fails closed, naming the offending asset
  ASUR-FIREWALL-01 GENERATION reads no VIRAL CHECK path (see test_firewall.py)
  ASUR-LOCAL-01    locked stack is local, render_cost_usd:0, no network/GPU
  ASUR-VERSION-01  the screenplay -> asset_plan -> generation_plan chain is linked

All tests are stdlib-only, deterministic, and offline. No test calls a real
model or renderer (G10): the media adapters live behind asur[generation] and
are never imported here; the render harness degrades to 'skipped' when ffprobe
is absent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from asur.core.envelope import verify_checksum
from asur.generation import hero_proof
from asur.generation.asset_strategy import _DEFAULT_MODEL, build_asset_plan
from asur.generation.creative_direction import build_creative_direction
from asur.generation.generation_plan import build_generation_plan
from asur.generation.hero_proof import build_hero_proof, verify_render
from asur.generation.license_guard import (
    TRAP_LIST,
    LicenseViolation,
    check_asset_license,
)
from asur.generation.visual_screenplay import build_visual_screenplay
from asur.script.audience import build_audience
from asur.script.hooks import build_hooks
from asur.script.idea import build_idea
from asur.script.research import build_research
from asur.script.script_builder import build_script
from asur.script.strategy import build_strategy

SAMPLE_IDEA = "why most people waste money on AI tools"
PROJECT_ID = "test-generation"


def _generation_chain(project_id=PROJECT_ID, *, monetized=True):
    """Build the full SCRIPT + GENERATION chain and return every artifact."""
    idea = build_idea(SAMPLE_IDEA, project_id)
    research = build_research(idea, project_id)
    audience = build_audience(idea, research, project_id)
    strategy = build_strategy(idea, audience, project_id)
    hooks = build_hooks(strategy, project_id)
    script = build_script(strategy, hooks, project_id)
    creative = build_creative_direction(strategy, script, project_id)
    screenplay = build_visual_screenplay(creative, script, project_id)
    asset_plan = build_asset_plan(screenplay, project_id, monetized=monetized)
    gen_plan = build_generation_plan(asset_plan, project_id)
    hero = build_hero_proof(gen_plan, screenplay, project_id)
    return {
        "idea": idea,
        "research": research,
        "audience": audience,
        "strategy": strategy,
        "hooks": hooks,
        "script": script,
        "creative": creative,
        "screenplay": screenplay,
        "asset_plan": asset_plan,
        "gen_plan": gen_plan,
        "hero": hero,
    }


def _clean_asset(model: str) -> dict:
    """A minimal asset with a clean, commercial-OK license block."""
    return {
        "asset_ref": f"{model}-asset",
        "provenance": {"model": model},
        "license": {
            "name": "clean",
            "commercial_ok": True,
            "revenue_cap_usd": None,
            "territory_exclusions": [],
        },
    }


# -- U: asset strategy picks the locked stack -------------------------------


def test_asset_plan_uses_locked_stack_defaults():
    """ASUR-LOCAL-01: the asset plan uses only locked-stack, license-clean models."""
    chain = _generation_chain()
    models = {a["model_choice"] for a in chain["asset_plan"].body["assets"]}
    # Locked stack: SDXL (images), Kokoro (voice), Stable Audio (music), FFmpeg.
    assert "SDXL" in models
    assert "Kokoro-82M" in models
    assert "Stable Audio 3.0" in models
    assert "FFmpeg" in models
    # Everything local -> zero marginal render cost.
    assert chain["asset_plan"].body["total_estimated_cost_usd"] == 0.0


def test_default_model_table_has_no_trapped_models():
    """ASUR-PROV-01: no locked-stack default is on the license trap list."""
    for model, _media, _license in _DEFAULT_MODEL.values():
        assert model.casefold() not in TRAP_LIST


# -- U: license guard fires on every trap class ----------------------------


@pytest.mark.parametrize(
    "model",
    ["flux.1 dev", "xtts v2", "musicgen", "suno", "udio", "sora"],
)
def test_license_guard_fires_on_trapped_models(model):
    """ASUR-GATE-01: a trapped model fails closed, naming the asset."""
    asset = _clean_asset(model)
    with pytest.raises(LicenseViolation) as exc:
        check_asset_license(asset, monetized=True)
    assert asset["asset_ref"] in str(exc.value)


def test_license_guard_avoid_fires_even_when_not_monetized():
    """ASUR-GATE-01: 'avoid' traps (Suno/Udio/Sora) fire even unmonetized."""
    with pytest.raises(LicenseViolation):
        check_asset_license(_clean_asset("sora"), monetized=False)


def test_license_guard_fires_on_non_commercial_license_block():
    """ASUR-GATE-01: an asset whose own license forbids commercial use fails."""
    asset = _clean_asset("some-model")
    asset["license"]["commercial_ok"] = False
    with pytest.raises(LicenseViolation):
        check_asset_license(asset, monetized=True)


def test_license_guard_fires_on_revenue_cap_exceeded():
    """ASUR-GATE-01: exceeding an asset's revenue cap fails closed."""
    asset = _clean_asset("capped-model")
    asset["license"]["revenue_cap_usd"] = 1000.0
    with pytest.raises(LicenseViolation):
        check_asset_license(asset, monetized=True, expected_revenue_usd=5000.0)


def test_license_guard_fires_on_territory_exclusion():
    """ASUR-GATE-01: a target territory in the exclusion list fails closed."""
    asset = _clean_asset("geo-model")
    asset["license"]["territory_exclusions"] = ["KR"]
    with pytest.raises(LicenseViolation):
        check_asset_license(asset, monetized=True, target_territory="KR")


def test_license_guard_fires_on_mau_cap():
    """ASUR-GATE-01: HunyuanVideo over its MAU cap fails closed."""
    with pytest.raises(LicenseViolation):
        check_asset_license(
            _clean_asset("hunyuanvideo"),
            monetized=True,
            expected_mau=200_000_000,
        )


def test_license_guard_fires_on_traffic_cap():
    """ASUR-GATE-01: CogVideoX-5B over its traffic cap fails closed."""
    with pytest.raises(LicenseViolation):
        check_asset_license(
            _clean_asset("cogvideox-5b"),
            monetized=True,
            expected_visits_month=2_000_000,
        )


def test_clean_locked_stack_asset_passes():
    """A clean locked-stack asset passes the guard (no false positive)."""
    check_asset_license(_clean_asset("SDXL"), monetized=True)  # no raise


# -- I: full lineage is linked + checksummed --------------------------------


def test_generation_lineage_is_linked_and_checksummed():
    """ASUR-VERSION-01/PROV-01: each stage references its upstream source."""
    chain = _generation_chain()
    for art in chain.values():
        assert verify_checksum(art)

    def _refs(artifact):
        return {s["artifact_id"] for s in artifact.sources}

    assert chain["script"].artifact_id in _refs(chain["creative"])
    assert chain["strategy"].artifact_id in _refs(chain["creative"])
    assert chain["creative"].artifact_id in _refs(chain["screenplay"])
    assert chain["screenplay"].artifact_id in _refs(chain["asset_plan"])
    assert chain["asset_plan"].artifact_id in _refs(chain["gen_plan"])
    assert chain["gen_plan"].artifact_id in _refs(chain["hero"])


def test_screenplay_has_one_scene_per_script_section():
    """The screenplay turns the 9 script sections into 9 scenes."""
    chain = _generation_chain()
    assert chain["screenplay"].body["scene_count"] == 9


def test_every_asset_carries_provenance_and_license():
    """ASUR-PROV-01: every planned asset has a provenance + license block."""
    chain = _generation_chain()
    for asset in chain["asset_plan"].body["assets"]:
        assert "provenance" in asset and "model" in asset["provenance"]
        assert "license" in asset and "name" in asset["license"]
        assert asset["license_precheck"] == "pass"


# -- G: monetized plan with a trapped asset fails closed --------------------


def test_asset_plan_fails_closed_on_trapped_asset(monkeypatch):
    """ASUR-GATE-01: a trapped model in a monetized plan blocks plan creation."""
    from asur.generation import asset_strategy

    # Force the image default to a trapped, non-commercial model.
    patched = dict(asset_strategy._DEFAULT_MODEL)
    patched["ai_image"] = ("FLUX.1 dev", "image", "non-commercial")
    monkeypatch.setattr(asset_strategy, "_DEFAULT_MODEL", patched)

    idea = build_idea(SAMPLE_IDEA, PROJECT_ID)
    research = build_research(idea, PROJECT_ID)
    audience = build_audience(idea, research, PROJECT_ID)
    strategy = build_strategy(idea, audience, PROJECT_ID)
    hooks = build_hooks(strategy, PROJECT_ID)
    script = build_script(strategy, hooks, PROJECT_ID)
    creative = build_creative_direction(strategy, script, PROJECT_ID)
    screenplay = build_visual_screenplay(creative, script, PROJECT_ID)
    with pytest.raises(LicenseViolation):
        build_asset_plan(screenplay, PROJECT_ID, monetized=True)


def test_expensive_generation_blocked_before_hero_proof_approval():
    """ASUR-GATE-01: FULL_GENERATION (stage 19) is unreachable pre hero-proof."""
    from asur.orchestrator import Orchestrator

    orch = Orchestrator(Path("/tmp"), "run-x", state="DRAFT")
    blocked = orch._expensive_blocked("FULL_GENERATION")
    assert blocked is not None
    assert "HERO_PROOF_APPROVED" in blocked


# -- R: hero proof render verification (offline) ----------------------------


def test_hero_proof_targets_vertical_reel_spec():
    """The hero proof manifest targets a 9:16 1080x1920 proof <= 15s."""
    chain = _generation_chain()
    spec = chain["hero"].body["target_spec"]
    assert spec["width"] == 1080
    assert spec["height"] == 1920
    assert spec["aspect_ratio"] == "9:16"
    assert spec["max_duration_s"] == 15.0


def test_verify_render_missing_file_fails_closed(tmp_path):
    """ASUR-GATE-01: verifying a non-existent render fails closed."""
    result = verify_render(tmp_path / "nope.mp4")
    assert result["status"] == "fail"


def test_verify_render_degrades_when_ffprobe_absent(tmp_path, monkeypatch):
    """G10: with no ffprobe the structural probe is skipped, never failed."""
    monkeypatch.setattr(hero_proof, "_ffprobe_available", lambda: False)
    video = tmp_path / "proof.mp4"
    video.write_bytes(b"")  # file exists so file_exists check passes
    result = verify_render(video)
    assert result["status"] == "skipped"


# -- G8: Sora is absent everywhere except as a forbidden marker -------------

_ASUR_ROOT = Path(__file__).resolve().parent.parent / "asur"


def test_sora_only_appears_as_a_forbidden_marker():
    """ADR-0004/G8: 'sora' appears only as an 'avoid' trap, never as an option."""
    assert TRAP_LIST["sora"]["kind"] == "avoid"
    # No locked-stack default is Sora.
    for model, _m, _l in _DEFAULT_MODEL.values():
        assert "sora" not in model.casefold()


def test_no_adapter_offers_sora():
    """ADR-0004/G8: no media adapter OFFERS Sora as a model.

    We check each adapter's module-level MODEL constant rather than raw file
    text, because adapters/__init__.py legitimately names Sora in a docstring
    as a removed/forbidden marker. The real guarantee is that no adapter
    exposes Sora as an offered model. Importing these modules is safe: their
    module level is stdlib-only; heavy media imports are lazy, inside functions.
    """
    from asur.generation.adapters import (
        faster_whisper,
        ffmpeg,
        kokoro,
        sdxl,
        stable_audio,
        wan22,
    )

    for mod in (wan22, sdxl, kokoro, stable_audio, ffmpeg, faster_whisper):
        assert "sora" not in getattr(mod, "MODEL", "").casefold()
