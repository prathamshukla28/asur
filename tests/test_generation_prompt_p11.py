"""P11a: real prompt threading seam (SPEC-GAP G26).

Stdlib-only, offline, no-network, no-GPU. These UNIT tests NEVER invoke a real
AI model: the dispatcher's adapter is monkeypatched to capture the prompt it is
handed, so we assert the *wiring* carries real screenplay intent rather than the
bare asset-ref string. The real model runs (SDXL/Kokoro/Stable Audio) live in the
double-gated opt-in integration suite (``pytest -m integration`` + importorskip).

Covered (P11a, SPEC-GAP G26 - the crude-prompt gap):

  * generation_plan.py ``build_generation_plan(..., visual_screenplay_artifact=...)``
      - when the screenplay is supplied, every image/voice/music job carries a
        real ``params['prompt']`` derived ONLY from already-authored screenplay
        fields (visual_concept/semantic_metaphor/composition for images,
        spoken_content for voice, audio_direction for music) - never invented (AGENTS.md §7).
      - when the screenplay is OMITTED, behaviour is byte-identical to the
        pre-P11a plan (no ``prompt`` key) - the 10 existing call sites stay green
        (ASUR-VERSION-01).

  * dispatch.py ``run_job``
      - passes ``params['prompt']`` to the SDXL/Kokoro/Stable Audio adapter when
        present; falls back to the ``target_asset`` ref string when absent
        (preserving old behaviour). FFmpeg is unaffected.
"""

from __future__ import annotations

from asur.generation import dispatch
from asur.generation.asset_strategy import build_asset_plan
from asur.generation.creative_direction import build_creative_direction
from asur.generation.generation_plan import build_generation_plan
from asur.generation.visual_screenplay import build_visual_screenplay
from asur.script.audience import build_audience
from asur.script.hooks import build_hooks
from asur.script.idea import build_idea
from asur.script.research import build_research
from asur.script.script_builder import build_script
from asur.script.strategy import build_strategy

SAMPLE_IDEA = "why most people waste money on AI tools"
PROJECT_ID = "test-p11-prompt"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _screenplay_and_assets():
    """Build a real screenplay + asset_plan artifact from one idea."""
    idea = build_idea(SAMPLE_IDEA, PROJECT_ID)
    research = build_research(idea, PROJECT_ID)
    audience = build_audience(idea, research, PROJECT_ID)
    strategy = build_strategy(idea, audience, PROJECT_ID)
    hooks = build_hooks(strategy, PROJECT_ID)
    script = build_script(strategy, hooks, PROJECT_ID)
    creative = build_creative_direction(strategy, script, PROJECT_ID)
    screenplay = build_visual_screenplay(creative, script, PROJECT_ID)
    asset_plan = build_asset_plan(screenplay, PROJECT_ID)
    return screenplay, asset_plan


def _scenes_by_id(screenplay):
    return {s["scene_id"]: s for s in screenplay.body["scenes"]}


def _job_by_target(plan, target):
    for job in plan.body["jobs"]:
        if job["target_asset"] == target:
            return job
    raise AssertionError(f"no job for target {target!r}")


# --------------------------------------------------------------------------- #
# generation_plan: prompt threading (G26)
# --------------------------------------------------------------------------- #


def test_plan_without_screenplay_is_byte_identical():
    """Omitting the screenplay keeps the pre-P11a behaviour (no prompt key)."""
    _screenplay, asset_plan = _screenplay_and_assets()
    plan = build_generation_plan(asset_plan, PROJECT_ID)
    for job in plan.body["jobs"]:
        assert "prompt" not in job["params"]


def test_image_job_prompt_is_real_screenplay_intent_not_asset_ref():
    """A background image job carries the scene's visual intent, not its ref."""
    screenplay, asset_plan = _screenplay_and_assets()
    plan = build_generation_plan(
        asset_plan, PROJECT_ID, visual_screenplay_artifact=screenplay
    )
    scenes = _scenes_by_id(screenplay)
    # find any ai_image background job
    bg_jobs = [
        j
        for j in plan.body["jobs"]
        if j["params"].get("media_type") == "image"
        and j["target_asset"].endswith("-background")
    ]
    assert bg_jobs, "expected at least one ai_image background job"
    for job in bg_jobs:
        scene_id = job["target_asset"][: -len("-background")]
        scene = scenes[scene_id]
        prompt = job["params"]["prompt"]
        assert isinstance(prompt, str) and prompt.strip()
        # prompt is NOT merely the asset ref
        assert prompt != job["target_asset"]
        # prompt is built from already-authored scene fields (no invention)
        assert scene["visual_concept"] in prompt
        assert scene["semantic_metaphor"] in prompt
        assert scene["composition"] in prompt


def test_voice_job_prompt_is_spoken_content():
    """The shared voice-track job carries the spoken content as its prompt."""
    screenplay, asset_plan = _screenplay_and_assets()
    plan = build_generation_plan(
        asset_plan, PROJECT_ID, visual_screenplay_artifact=screenplay
    )
    voice = _job_by_target(plan, "voice-track")
    assert voice["params"]["media_type"] == "audio_voice"
    prompt = voice["params"]["prompt"]
    assert isinstance(prompt, str) and prompt.strip()
    assert prompt != "voice-track"
    # it is the joined spoken content of the real screenplay scenes
    spoken = [s["spoken_content"] for s in screenplay.body["scenes"] if s["spoken_content"]]
    assert any(chunk and chunk in prompt for chunk in spoken)


def test_music_job_prompt_is_audio_direction():
    """The shared music-bed job carries audio direction as its prompt."""
    screenplay, asset_plan = _screenplay_and_assets()
    plan = build_generation_plan(
        asset_plan, PROJECT_ID, visual_screenplay_artifact=screenplay
    )
    music = _job_by_target(plan, "music-bed")
    assert music["params"]["media_type"] == "audio_music"
    prompt = music["params"]["prompt"]
    assert isinstance(prompt, str) and prompt.strip()
    assert prompt != "music-bed"


def test_onscreen_text_job_has_no_ai_prompt():
    """Procedural FFmpeg on-screen-text jobs get no AI prompt (not an AI model)."""
    screenplay, asset_plan = _screenplay_and_assets()
    plan = build_generation_plan(
        asset_plan, PROJECT_ID, visual_screenplay_artifact=screenplay
    )
    text_jobs = [
        j for j in plan.body["jobs"] if j["target_asset"].endswith("-onscreen-text")
    ]
    assert text_jobs, "expected on-screen-text jobs"
    for job in text_jobs:
        assert "prompt" not in job["params"]


# --------------------------------------------------------------------------- #
# dispatch.run_job: pass the real prompt to the adapter (G26)
# --------------------------------------------------------------------------- #


def _install_capturing_adapter(monkeypatch, model_name):
    """Make ``dispatch._resolve`` return an adapter that records its first arg."""
    captured: dict[str, object] = {}

    def fake_adapter(first, *args, **kwargs):
        captured["prompt"] = first
        captured["args"] = args
        captured["kwargs"] = kwargs
        return {
            "media_type": "image",
            "origin": "ai_generated",
            "file_path": args[0] if args else "",
            "provenance": {"model": model_name},
            "license": {"name": "test", "commercial_ok": True},
        }

    monkeypatch.setattr(dispatch, "_resolve", lambda _model: fake_adapter)
    return captured


def test_run_job_passes_real_prompt_to_image_adapter(monkeypatch, tmp_path):
    """When the job carries params['prompt'], the adapter receives it (not the ref)."""
    captured = _install_capturing_adapter(monkeypatch, "SDXL")
    job = {
        "job_id": "job-00-scene-01-hook-background",
        "target_asset": "scene-01-hook-background",
        "model": "SDXL",
        "params": {
            "media_type": "image",
            "source_strategy": "ai_image",
            "prompt": "a clean subject-forward frame. a concrete image. center-weighted.",
        },
    }
    dispatch.run_job(job, out_dir=str(tmp_path))
    assert captured["prompt"] == job["params"]["prompt"]
    assert captured["prompt"] != job["target_asset"]


def test_run_job_falls_back_to_asset_ref_without_prompt(monkeypatch, tmp_path):
    """No params['prompt'] -> old behaviour: adapter gets the target_asset ref."""
    captured = _install_capturing_adapter(monkeypatch, "SDXL")
    job = {
        "job_id": "job-00-scene-01-hook-background",
        "target_asset": "scene-01-hook-background",
        "model": "SDXL",
        "params": {"media_type": "image", "source_strategy": "ai_image"},
    }
    dispatch.run_job(job, out_dir=str(tmp_path))
    assert captured["prompt"] == job["target_asset"]
