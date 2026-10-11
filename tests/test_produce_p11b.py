"""P11b: produce real AI assets + composite them into the render (SPEC-GAP G27).

Stdlib-only, offline, no-network, no-GPU. These UNIT tests NEVER invoke a real AI
model or the real ffmpeg binary:

  * ``asur.generation.dispatch.run_job`` is monkeypatched so ``produce_assets``
    exercises its orchestration (dependency ordering, media-type routing, the
    skip of FFmpeg/user-camera jobs, fail-closed on a raising adapter or a
    missing output file) WITHOUT any model download.
  * ``asur.generation.adapters.ffmpeg.subprocess.run`` is monkeypatched (the same
    fake-ffmpeg harness as P10b) so the compositing argv the adapter builds can be
    inspected, and so ``is_file`` checks pass.

The real end-to-end produce+composite (actual SDXL PNGs -> real ffmpeg) lives in
the opt-in, double-gated integration suite.

Covered (P11b, SPEC-GAP G27):

  * generation/produce.py ``produce_assets(generation_plan_artifact, *, out_dir)``
      - returns {backgrounds: {scene_id: png_path}, voice: wav|None,
        music: wav|None, assets: [provenance...], skipped: [job_id...]}.
      - SKIPS FFmpeg-model (on-screen-text / graphic) and user-camera
        (user_original footage) jobs - those are composited/kept at render time,
        not produced by an AI adapter here.
      - fails closed (propagates) when an adapter raises, and fails closed when an
        adapter claims a file that is not on disk (ASUR-GATE-01).

  * adapters/ffmpeg.py ``render(timeline, out_path, *, backgrounds=None, ...)``
      - a scene WITH a real background PNG is composited (``-loop 1 ... -i <png>``
        + scale/crop) instead of a solid ``color=`` card; other scenes stay cards.
      - ``backgrounds=None`` (or all-missing) is byte-identical to the P10 render
        (only ``color=`` sources; provenance gains no new used-count).
      - a referenced background file that is absent fails closed (``RenderError``).

  * generation/render.py ``build_final_render(..., assets=None)``
      - ``assets=None`` forwards nothing and stays byte-identical to P10.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from asur.generation import dispatch
from asur.generation.adapters import ffmpeg
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
PROJECT_ID = "test-p11b"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _chain():
    """Build screenplay + generation_plan (with real prompts) from one idea."""
    idea = build_idea(SAMPLE_IDEA, PROJECT_ID)
    research = build_research(idea, PROJECT_ID)
    audience = build_audience(idea, research, PROJECT_ID)
    strategy = build_strategy(idea, audience, PROJECT_ID)
    hooks = build_hooks(strategy, PROJECT_ID)
    script = build_script(strategy, hooks, PROJECT_ID)
    creative = build_creative_direction(strategy, script, PROJECT_ID)
    screenplay = build_visual_screenplay(creative, script, PROJECT_ID)
    asset_plan = build_asset_plan(screenplay, PROJECT_ID)
    gen_plan = build_generation_plan(
        asset_plan, PROJECT_ID, visual_screenplay_artifact=screenplay
    )
    return screenplay, gen_plan


def _install_fake_dispatch(monkeypatch, *, raise_on: str | None = None, ghost: str | None = None):
    """Monkeypatch dispatch.run_job so produce_assets runs with no real models.

    For every job, writes a fake output file at ``<out_dir>/<target>.<ext>`` and
    returns a provenance+license dict shaped like a real adapter result. Options:
      * ``raise_on`` - if a job's media_type == this, raise RuntimeError (simulate
        an adapter whose extra is missing) to test fail-closed propagation.
      * ``ghost`` - if a job's media_type == this, return a result that names a
        file WITHOUT creating it, to test the missing-output fail-closed guard.

    Records every (job, out_dir) it was called with.
    """
    calls: list[dict] = []

    ext = {"image": "png", "audio_voice": "wav", "audio_music": "wav", "captions": "json"}

    def fake_run_job(job, *, timeline=None, out_dir):
        media_type = str(job.get("params", {}).get("media_type", ""))
        model = str(job.get("model", ""))
        calls.append({"job_id": job.get("job_id"), "media_type": media_type, "model": model, "out_dir": out_dir})
        if raise_on is not None and media_type == raise_on:
            raise RuntimeError(f"adapter for {media_type} needs the asur[generation] extra")
        target = str(job.get("target_asset", "asset"))
        file_path = str(Path(out_dir) / f"{target}.{ext.get(media_type, 'out')}")
        if not (ghost is not None and media_type == ghost):
            p = Path(file_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"\x00")
        return {
            "media_type": media_type,
            "origin": "ai_generated",
            "file_path": file_path,
            "provenance": {"model": model, "prompt": job.get("params", {}).get("prompt", "")},
            "license": {"name": "test", "commercial_ok": True},
            "job_id": job.get("job_id"),
        }

    monkeypatch.setattr(dispatch, "run_job", fake_run_job)
    return calls


class _FakeProc:
    def __init__(self, returncode: int = 0, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = ""


def _install_fake_ffmpeg(monkeypatch):
    """Fake ffmpeg: record every argv, touch the output (last argv) so is_file passes."""
    monkeypatch.setattr(ffmpeg, "_ffmpeg_available", lambda: True)
    captured: list[list[str]] = []

    def fake_run(cmd, *args, **kwargs):
        captured.append(list(cmd))
        out = Path(cmd[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"\x00")
        return _FakeProc(returncode=0)

    monkeypatch.setattr(ffmpeg.subprocess, "run", fake_run)
    return captured


def _card_cmds(captured: list[list[str]]) -> list[list[str]]:
    """Only the per-scene card render commands (scene_NNN.mp4 output), not concat."""
    return [cmd for cmd in captured if cmd and str(cmd[-1]).endswith(".mp4") and "scene_" in str(cmd[-1])]


# --------------------------------------------------------------------------- #
# produce_assets
# --------------------------------------------------------------------------- #


def test_produce_returns_backgrounds_voice_music(monkeypatch, tmp_path):
    """produce_assets runs the AI jobs and groups results by role."""
    from asur.generation.produce import produce_assets

    _, gen_plan = _chain()
    _install_fake_dispatch(monkeypatch)

    result = produce_assets(gen_plan, out_dir=str(tmp_path))

    assert isinstance(result["backgrounds"], dict)
    assert result["backgrounds"], "expected at least one AI background"
    # scene_id keys, png values that exist on disk
    for scene_id, png in result["backgrounds"].items():
        assert scene_id.startswith("scene-")
        assert Path(png).is_file()
    assert result["voice"] is not None and Path(result["voice"]).is_file()
    assert result["music"] is not None and Path(result["music"]).is_file()
    assert isinstance(result["assets"], list) and result["assets"]


def test_produce_skips_ffmpeg_and_user_camera_jobs(monkeypatch, tmp_path):
    """On-screen-text (FFmpeg) and user_original (user-camera) jobs are NOT produced here."""
    from asur.generation.produce import produce_assets

    _, gen_plan = _chain()
    calls = _install_fake_dispatch(monkeypatch)

    result = produce_assets(gen_plan, out_dir=str(tmp_path))

    # Dispatch was never asked to run an FFmpeg-model or a user-camera job.
    for call in calls:
        assert call["model"] != "FFmpeg"
        assert call["model"] != "user-camera"
    # Those jobs are recorded as skipped, not silently dropped.
    assert any("onscreen-text" in str(s) for s in result["skipped"])


def test_produce_fails_closed_when_adapter_raises(monkeypatch, tmp_path):
    """A raising adapter (missing extra) propagates - never a silent partial set."""
    from asur.generation.produce import produce_assets

    _, gen_plan = _chain()
    _install_fake_dispatch(monkeypatch, raise_on="image")

    with pytest.raises(RuntimeError):
        produce_assets(gen_plan, out_dir=str(tmp_path))


def test_produce_fails_closed_when_output_missing(monkeypatch, tmp_path):
    """An adapter that claims a file it did not write fails closed (ASUR-GATE-01)."""
    from asur.generation.produce import produce_assets

    _, gen_plan = _chain()
    _install_fake_dispatch(monkeypatch, ghost="audio_music")

    with pytest.raises(ffmpeg.RenderError):
        produce_assets(gen_plan, out_dir=str(tmp_path))


# --------------------------------------------------------------------------- #
# adapters/ffmpeg.py: background compositing
# --------------------------------------------------------------------------- #


def test_render_composites_background_image(monkeypatch, tmp_path):
    """A scene with a real background PNG is composited via -loop 1 -i <png> + scale/crop."""
    captured = _install_fake_ffmpeg(monkeypatch)

    bg = tmp_path / "scene-01-hook-background.png"
    bg.write_bytes(b"\x00")
    timeline = {
        "timeline_id": "tl-bg",
        "scenes": [
            {"scene_id": "scene-01-hook", "start": 0.0, "end": 3.0},
            {"scene_id": "scene-02-opening", "start": 3.0, "end": 7.0},
        ],
    }
    out = tmp_path / "composed.mp4"

    result = ffmpeg.render(
        timeline, str(out), backgrounds={"scene-01-hook": str(bg)}
    )

    cards = _card_cmds(captured)
    assert len(cards) == 2
    joined = [" ".join(cmd) for cmd in cards]
    # Scene 0 uses the PNG as a looped image input + scale/crop.
    scene0 = joined[0]
    assert "-loop" in scene0 and str(bg) in scene0
    assert "scale=" in scene0 and "crop=" in scene0
    # Scene 1 (no background) stays a solid colour card.
    assert "color=" in joined[1]
    assert result["provenance"]["backgrounds_used"] == 1


def test_render_without_backgrounds_is_byte_identical(monkeypatch, tmp_path):
    """backgrounds=None keeps the P10 solid-card render (no new provenance key)."""
    captured = _install_fake_ffmpeg(monkeypatch)
    timeline = {
        "timeline_id": "tl-none",
        "scenes": [
            {"scene_id": "scene-01-hook", "start": 0.0, "end": 3.0},
            {"scene_id": "scene-02-opening", "start": 3.0, "end": 7.0},
        ],
    }
    out = tmp_path / "plain.mp4"

    result = ffmpeg.render(timeline, str(out))

    for cmd in _card_cmds(captured):
        joined = " ".join(cmd)
        assert "color=" in joined
        assert "-loop" not in joined
    assert result["provenance"].get("backgrounds_used", 0) == 0


def test_render_missing_background_file_fails_closed(monkeypatch, tmp_path):
    """A referenced background PNG that is absent fails closed (ASUR-GATE-01)."""
    _install_fake_ffmpeg(monkeypatch)
    timeline = {
        "timeline_id": "tl-missing",
        "scenes": [{"scene_id": "scene-01-hook", "start": 0.0, "end": 3.0}],
    }
    out = tmp_path / "x.mp4"
    missing = tmp_path / "does-not-exist.png"

    with pytest.raises(ffmpeg.RenderError):
        ffmpeg.render(timeline, str(out), backgrounds={"scene-01-hook": str(missing)})


def test_render_composite_default_resolution_unchanged(monkeypatch, tmp_path):
    """Compositing a background still renders at the pack resolution (1080x1920)."""
    captured = _install_fake_ffmpeg(monkeypatch)
    bg = tmp_path / "scene-01-hook-background.png"
    bg.write_bytes(b"\x00")
    timeline = {
        "timeline_id": "tl-res",
        "scenes": [{"scene_id": "scene-01-hook", "start": 0.0, "end": 3.0}],
    }
    out = tmp_path / "r.mp4"

    ffmpeg.render(timeline, str(out), backgrounds={"scene-01-hook": str(bg)})

    joined = " ".join(_card_cmds(captured)[0])
    assert "scale=1080:1920" in joined
    assert "crop=1080:1920" in joined


# --------------------------------------------------------------------------- #
# generation/render.py: build_final_render(assets=None) stays byte-identical
# --------------------------------------------------------------------------- #


def test_build_final_render_assets_none_is_byte_identical(monkeypatch, tmp_path):
    """build_final_render(assets=None) forwards nothing -> exact P10 behaviour."""
    # Reuse the P10b chain helper shape via the local _chain's edit plan path.
    from asur.editing.timeline import (
        build_edit_plan,
        build_timeline_from_generation_plan,
    )
    from asur.generation import render as render_mod

    screenplay, gen_plan = _chain()
    timeline = build_timeline_from_generation_plan(gen_plan, screenplay, PROJECT_ID)
    edit_plan = build_edit_plan(timeline, gen_plan, PROJECT_ID)

    _install_fake_ffmpeg(monkeypatch)
    monkeypatch.setattr(render_mod.hero_proof, "_ffprobe_available", lambda: True)
    monkeypatch.setattr(
        render_mod.hero_proof,
        "_probe_dimensions_duration",
        lambda _p: (1080, 1920, 6.0),
    )

    art = render_mod.build_final_render(
        edit_plan, PROJECT_ID, out_root=str(tmp_path), assets=None
    )

    assert art.kind == "render"
    assert art.body["provenance"]["resolution"] == "1080x1920"
    # No asset wiring recorded when assets is None (byte-identical to P10).
    assert "assets" not in art.body
