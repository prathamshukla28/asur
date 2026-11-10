"""P10b: real timeline render seam -- platform-aware ffmpeg adapter + build_final_render.

Stdlib-only, offline, no-network, no-GPU. These UNIT tests NEVER invoke the real
ffmpeg binary: ``subprocess.run`` is monkeypatched to capture the argv the adapter
builds (and to fake a successful render by touching the output file), and
``ffprobe`` availability / probing is monkeypatched for ``build_final_render``.
The real end-to-end render (an actual .mp4) lives in the opt-in integration suite
(``tests/integration/test_render_pipeline.py``, ``pytest -m integration``).

Covered (P10b, SPEC-GAP G20/G21):

  * adapters/ffmpeg.py ``render(timeline, out_path, *, platform=None)``
      - resolution/fps come from the platform pack's FormatSpec, NOT a hard-coded
        1080x1920 (youtube_long -> 1920x1080); ``platform=None`` stays
        byte-identical to the Instagram-Reels default (ASUR-VERSION-01).
      - fails closed (``RenderError``) when the ffmpeg binary is absent AND when
        the timeline declares an explicit empty scene list (ASUR-GATE-01).
      - the returned provenance resolution string is pack-derived.

  * generation/render.py ``build_final_render(...)``
      - renders through the adapter, probes the file, runs ``verify_render`` with
        the SAME platform, and emits a first-class ``render`` artifact carrying a
        provenance + license block (ASUR-PROV-01).
      - fails closed if structural verification reports ``fail`` (ASUR-GATE-01).
"""

from __future__ import annotations

import pytest

from asur.editing.timeline import build_edit_plan, build_timeline_from_generation_plan
from asur.generation.adapters import ffmpeg
from asur.generation.asset_strategy import build_asset_plan
from asur.generation.creative_direction import build_creative_direction
from asur.generation.generation_plan import build_generation_plan
from asur.generation.visual_screenplay import build_visual_screenplay
from asur.platforms import get_platform
from asur.script.audience import build_audience
from asur.script.hooks import build_hooks
from asur.script.idea import build_idea
from asur.script.research import build_research
from asur.script.script_builder import build_script
from asur.script.strategy import build_strategy

SAMPLE_IDEA = "why most people waste money on AI tools"
PROJECT_ID = "test-p10b"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _edit_plan():
    """Build a real edit_plan artifact + its timeline from one idea."""
    idea = build_idea(SAMPLE_IDEA, PROJECT_ID)
    research = build_research(idea, PROJECT_ID)
    audience = build_audience(idea, research, PROJECT_ID)
    strategy = build_strategy(idea, audience, PROJECT_ID)
    hooks = build_hooks(strategy, PROJECT_ID)
    script = build_script(strategy, hooks, PROJECT_ID)
    creative = build_creative_direction(strategy, script, PROJECT_ID)
    screenplay = build_visual_screenplay(creative, script, PROJECT_ID)
    asset_plan = build_asset_plan(screenplay, PROJECT_ID)
    gen_plan = build_generation_plan(asset_plan, PROJECT_ID)
    timeline = build_timeline_from_generation_plan(gen_plan, screenplay, PROJECT_ID)
    edit_plan = build_edit_plan(timeline, gen_plan, PROJECT_ID)
    return edit_plan, timeline


class _FakeProc:
    """Minimal stand-in for subprocess.CompletedProcess."""

    def __init__(self, returncode: int = 0, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = ""


def _install_fake_ffmpeg(monkeypatch):
    """Monkeypatch so the adapter 'runs' without the real binary.

    Records every argv list the adapter builds, and creates whatever output file
    path an ffmpeg command targets (the last argv entry) so ``is_file`` checks
    pass. Returns the list that will accumulate captured argvs.
    """
    monkeypatch.setattr(ffmpeg, "_ffmpeg_available", lambda: True)
    captured: list[list[str]] = []

    def fake_run(cmd, *args, **kwargs):
        captured.append(list(cmd))
        # The adapter always puts the output path last; touch it so is_file()
        # checks in _render_card / _concat succeed.
        from pathlib import Path

        out = Path(cmd[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"\x00")
        return _FakeProc(returncode=0)

    monkeypatch.setattr(ffmpeg.subprocess, "run", fake_run)
    return captured


def _resolutions_in(captured: list[list[str]]) -> set[str]:
    """Extract every WxH frame size from the cards' lavfi background sources.

    The default card background is the animated ``gradients`` source
    (``gradients=s=1080x1920:r=30:d=...``); its ``s=`` is the frame size.
    """
    found: set[str] = set()
    for cmd in captured:
        for token in cmd:
            if token.startswith("gradients="):
                for part in token[len("gradients="):].split(":"):
                    if part.startswith("s="):
                        found.add(part[2:])
    return found


# --------------------------------------------------------------------------- #
# adapters/ffmpeg.py: platform-aware render
# --------------------------------------------------------------------------- #


def test_render_default_platform_is_byte_identical_vertical(monkeypatch, tmp_path):
    """platform=None keeps the Instagram-Reels 1080x1920 default (ASUR-VERSION-01)."""
    _, timeline = _edit_plan()
    captured = _install_fake_ffmpeg(monkeypatch)
    out = tmp_path / "reel.mp4"

    result = ffmpeg.render(timeline, str(out))

    assert _resolutions_in(captured) == {"1080x1920"}
    assert result["provenance"]["resolution"] == "1080x1920"


def test_render_youtube_long_is_landscape(monkeypatch, tmp_path):
    """platform='youtube_long' renders at the pack's 16:9 1920x1080 (G20)."""
    _, timeline = _edit_plan()
    captured = _install_fake_ffmpeg(monkeypatch)
    out = tmp_path / "long.mp4"

    result = ffmpeg.render(timeline, str(out), platform="youtube_long")

    spec = get_platform("youtube_long").format_spec
    want = f"{spec.width}x{spec.height}"
    assert want == "1920x1080"
    assert _resolutions_in(captured) == {want}
    assert result["provenance"]["resolution"] == want


def test_render_unknown_platform_fails_closed(monkeypatch, tmp_path):
    """An unknown platform id fails closed before any render (ASUR-GATE-01)."""
    from asur.platforms import UnknownPlatform

    _, timeline = _edit_plan()
    _install_fake_ffmpeg(monkeypatch)
    out = tmp_path / "x.mp4"

    with pytest.raises(UnknownPlatform):
        ffmpeg.render(timeline, str(out), platform="tiktok")


def test_render_empty_scenes_fails_closed(monkeypatch, tmp_path):
    """An explicit empty scene list is a fail, never a silent default card."""
    _install_fake_ffmpeg(monkeypatch)
    out = tmp_path / "empty.mp4"
    timeline = {"timeline_id": "tl-empty", "scenes": []}

    with pytest.raises(ffmpeg.RenderError):
        ffmpeg.render(timeline, str(out))


def test_render_without_ffmpeg_binary_fails_closed(monkeypatch, tmp_path):
    """No ffmpeg binary -> clear RenderError, never a silent pass (ASUR-GATE-01)."""
    _, timeline = _edit_plan()
    monkeypatch.setattr(ffmpeg, "_ffmpeg_available", lambda: False)
    out = tmp_path / "x.mp4"

    with pytest.raises(ffmpeg.RenderError):
        ffmpeg.render(timeline, str(out))


# --------------------------------------------------------------------------- #
# generation/render.py: build_final_render
# --------------------------------------------------------------------------- #


def test_build_final_render_emits_render_artifact(monkeypatch, tmp_path):
    """A successful render yields a 'render' artifact with provenance+license."""
    from asur.generation import render as render_mod

    edit_plan, _ = _edit_plan()
    _install_fake_ffmpeg(monkeypatch)
    # Fake the probe so verify_render reports a clean 1080x1920 pass offline.
    monkeypatch.setattr(render_mod.hero_proof, "_ffprobe_available", lambda: True)
    monkeypatch.setattr(
        render_mod.hero_proof,
        "_probe_dimensions_duration",
        lambda _p: (1080, 1920, 6.0),
    )

    art = render_mod.build_final_render(
        edit_plan, PROJECT_ID, out_root=str(tmp_path)
    )

    assert art.kind == "render"
    assert art.artifact_id.startswith("render-")
    assert art.body["provenance"]["model"] == "FFmpeg"
    assert art.body["license"]["name"]
    assert art.body["verify"]["status"] == "pass"
    assert art.body["final_video"]


def test_build_final_render_youtube_long_probes_landscape(monkeypatch, tmp_path):
    """youtube_long render verifies against the pack's 16:9 resolution (G20)."""
    from asur.generation import render as render_mod

    edit_plan, _ = _edit_plan()
    _install_fake_ffmpeg(monkeypatch)
    monkeypatch.setattr(render_mod.hero_proof, "_ffprobe_available", lambda: True)
    monkeypatch.setattr(
        render_mod.hero_proof,
        "_probe_dimensions_duration",
        lambda _p: (1920, 1080, 300.0),
    )

    art = render_mod.build_final_render(
        edit_plan, PROJECT_ID, platform="youtube_long", out_root=str(tmp_path)
    )

    assert art.body["verify"]["status"] == "pass"
    assert art.body["provenance"]["resolution"] == "1920x1080"


def test_build_final_render_fails_closed_on_verify_fail(monkeypatch, tmp_path):
    """A structural verify 'fail' stops the render from being accepted."""
    from asur.generation import render as render_mod

    edit_plan, _ = _edit_plan()
    _install_fake_ffmpeg(monkeypatch)
    # Probe reports wrong dimensions -> verify_render returns 'fail'.
    monkeypatch.setattr(render_mod.hero_proof, "_ffprobe_available", lambda: True)
    monkeypatch.setattr(
        render_mod.hero_proof,
        "_probe_dimensions_duration",
        lambda _p: (640, 480, 6.0),
    )

    with pytest.raises(render_mod.RenderError):
        render_mod.build_final_render(edit_plan, PROJECT_ID, out_root=str(tmp_path))
