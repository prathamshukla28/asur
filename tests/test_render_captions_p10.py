"""P10b-captions: honest burned-in captions on the real render seam (SPEC-GAP G20).

Stdlib-only, offline, no-network, no-GPU. These UNIT tests NEVER invoke the real
ffmpeg binary: ``subprocess.run`` is monkeypatched to capture the argv the adapter
builds (and to fake a successful render by touching the output file). The real
end-to-end render with burned captions lives in the opt-in integration suite
(``tests/integration/test_render_pipeline.py``, ``pytest -m integration``).

The honesty contract (ASUR-HONEST-01 + anti-hallucination §7):

  * Caption text is NEVER invented. The only text that may be burned in is the
    real on-screen text the screenplay already authored
    (``scene['graphics']['onscreen_text']``). Section labels like "Hook" are NOT
    captions and must never be drawn.
  * The timeline is the single carrier: ``build_timeline_from_generation_plan``
    threads each scene's real on-screen text onto the matching text-track
    ``Clip.overlays`` (sourced from the screenplay it already receives). A text
    clip with no matching on-screen text keeps ``overlays == []``.
  * The ffmpeg adapter burns a ``drawtext`` filter ONLY for clips that carry
    overlay text, positioned inside the platform safe area and timed to the clip.
    No overlays -> no ``drawtext`` -> clean cards (byte-identical to pre-captions).
  * Audio is only muxed when a referenced audio file actually exists on disk. No
    real audio files exist yet (Kokoro / Stable Audio are deferred to P11), so no
    fabricated sound is ever added.
"""

from __future__ import annotations

from pathlib import Path

from asur.editing.timeline import build_edit_plan, build_timeline_from_generation_plan
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
PROJECT_ID = "test-captions"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _chain():
    """Build the full chain; return (screenplay, gen_plan, timeline, edit_plan)."""
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
    return screenplay, gen_plan, timeline, edit_plan


def _text_clips(timeline) -> list[dict]:
    """Return the caption-track clip dicts from a Timeline (or its dict form)."""
    tl = timeline.to_dict() if hasattr(timeline, "to_dict") else dict(timeline)
    for track in tl.get("tracks", []):
        if track.get("type") == "text":
            return list(track.get("clips", []))
    return []


def _onscreen_by_scene(screenplay) -> dict[str, str]:
    """Map scene_id -> real authored on-screen text from the screenplay."""
    mapping: dict[str, str] = {}
    for scene in screenplay.body.get("scenes", []):
        text = scene.get("graphics", {}).get("onscreen_text", "")
        if text:
            mapping[scene["scene_id"]] = text
    return mapping


class _FakeProc:
    def __init__(self, returncode: int = 0, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = ""


def _install_fake_ffmpeg(monkeypatch):
    """Monkeypatch so the adapter 'runs' without the real binary.

    Records every argv list the adapter builds, and creates whatever output file
    the command targets (last argv entry) so ``is_file`` checks pass.
    """
    monkeypatch.setattr(ffmpeg, "_ffmpeg_available", lambda: True)
    captured: list[list[str]] = []

    def fake_run(cmd, *args, **kwargs):
        argv = list(cmd)
        # Captions are passed via drawtext textfile=; inline the file's text
        # into the recorded argv so assertions can see what would be burned.
        for i, token in enumerate(argv):
            if "drawtext=textfile=" in token:
                raw = token.split("drawtext=textfile=", 1)[1].split(":expansion", 1)[0]
                path = raw.replace("\\\\", "\x00").replace("\\", "").replace("\x00", "\\")
                argv[i] = token + " #text=" + Path(path).read_text(encoding="utf-8")
        captured.append(argv)
        out = Path(cmd[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"\x00")
        return _FakeProc(returncode=0)

    monkeypatch.setattr(ffmpeg.subprocess, "run", fake_run)
    return captured


def _drawtext_tokens(captured: list[list[str]]) -> list[str]:
    """Every argv token (across all commands) that contains a drawtext filter."""
    tokens: list[str] = []
    for cmd in captured:
        for token in cmd:
            if "drawtext" in token:
                tokens.append(token)
    return tokens


# --------------------------------------------------------------------------- #
# timeline.py: honest overlay threading
# --------------------------------------------------------------------------- #


def test_text_clips_carry_real_onscreen_text_overlay():
    """Each caption clip's overlays carry the exact authored on-screen text."""
    screenplay, _gp, timeline, _edit = _chain()
    onscreen = _onscreen_by_scene(screenplay)
    assert onscreen, "screenplay should author on-screen text for at least one scene"

    text_clips = _text_clips(timeline)
    assert text_clips, "timeline should have a caption (text) track with clips"

    matched = 0
    for clip in text_clips:
        asset_ref = clip["asset_ref"]
        assert asset_ref.endswith("-onscreen-text")
        scene_id = asset_ref[: -len("-onscreen-text")]
        overlays = clip.get("overlays", [])
        if scene_id in onscreen:
            texts = [ov.get("text") for ov in overlays if isinstance(ov, dict)]
            assert onscreen[scene_id] in texts, (
                f"clip {asset_ref} must carry the real authored on-screen text, "
                f"got overlays={overlays!r}"
            )
            matched += 1
    assert matched >= 1, "at least one caption clip should carry authored text"


def test_overlay_text_is_never_a_section_label():
    """No overlay text is a bare section label (that would be invented content)."""
    screenplay, _gp, timeline, _edit = _chain()
    onscreen = set(_onscreen_by_scene(screenplay).values())
    section_labels = {"hook", "opening", "problem", "context", "story",
                      "value", "proof", "payoff", "cta", "Hook", "CTA"}

    for clip in _text_clips(timeline):
        for ov in clip.get("overlays", []):
            if isinstance(ov, dict) and ov.get("text"):
                text = ov["text"]
                assert text not in section_labels, (
                    f"overlay text {text!r} is a section label, not authored content"
                )
                assert text in onscreen, (
                    f"overlay text {text!r} is not authored screenplay on-screen text"
                )


def test_overlay_carries_safe_area_timing():
    """Overlay records its own start/end inside the clip span, in the safe area."""
    _sp, _gp, timeline, _edit = _chain()
    for clip in _text_clips(timeline):
        overlays = [ov for ov in clip.get("overlays", []) if isinstance(ov, dict)]
        if not overlays:
            continue
        clip_start = clip["timeline_start"]
        clip_end = clip_start + clip["out"]
        for ov in overlays:
            # timing is within the clip span
            assert ov["start"] >= clip_start - 1e-6
            assert ov["end"] <= clip_end + 1e-6
            assert ov["end"] > ov["start"]
            # vertical placement is inside the safe band (0.12..0.88)
            assert 0.12 <= ov["y_fraction"] <= 0.88


# --------------------------------------------------------------------------- #
# ffmpeg.py: burn drawtext only for real caption text
# --------------------------------------------------------------------------- #


def test_render_burns_real_caption_text(monkeypatch, tmp_path):
    """A timeline with on-screen text produces drawtext argv carrying that text."""
    screenplay, _gp, timeline, _edit = _chain()
    onscreen = _onscreen_by_scene(screenplay)
    captured = _install_fake_ffmpeg(monkeypatch)
    out = tmp_path / "reel.mp4"

    result = ffmpeg.render(timeline, str(out))

    drawtexts = _drawtext_tokens(captured)
    assert drawtexts, "render should burn drawtext for scenes with on-screen text"
    joined = "\n".join(drawtexts)
    # at least one real authored caption appears in the burned filter graph
    assert any(text in joined for text in onscreen.values())
    # provenance records that captions were burned in (ASUR-EXPLAIN-01)
    assert result["provenance"]["captions_burned_in"] is True


def test_render_without_overlays_has_no_drawtext(monkeypatch, tmp_path):
    """A timeline whose text clips carry no overlays burns NO text (clean cards)."""
    captured = _install_fake_ffmpeg(monkeypatch)
    out = tmp_path / "clean.mp4"
    # minimal valid timeline: scenes present, no overlays anywhere
    timeline = {
        "timeline_id": "tl-clean",
        "scenes": [
            {"scene_id": "scene-01-hook", "start": 0.0, "end": 3.0},
            {"scene_id": "scene-02-cta", "start": 3.0, "end": 6.0},
        ],
        "tracks": [],
    }

    result = ffmpeg.render(timeline, str(out))

    assert _drawtext_tokens(captured) == []
    assert result["provenance"]["captions_burned_in"] is False


def test_render_default_resolution_unchanged_with_captions(monkeypatch, tmp_path):
    """Burning captions must not change the pack-derived resolution (ASUR-VERSION-01)."""
    _sp, _gp, timeline, _edit = _chain()
    captured = _install_fake_ffmpeg(monkeypatch)
    out = tmp_path / "reel.mp4"

    result = ffmpeg.render(timeline, str(out))

    assert result["provenance"]["resolution"] == "1080x1920"
    # the card source still targets the IG default resolution
    assert any("s=1080x1920" in tok for cmd in captured for tok in cmd)


# --------------------------------------------------------------------------- #
# ffmpeg.py: audio mux only when a real file exists
# --------------------------------------------------------------------------- #


def test_render_no_audio_when_no_real_file(monkeypatch, tmp_path):
    """With no real audio asset on disk, no -i audio input is added (no fake sound)."""
    _sp, _gp, timeline, _edit = _chain()
    captured = _install_fake_ffmpeg(monkeypatch)
    out = tmp_path / "reel.mp4"

    result = ffmpeg.render(timeline, str(out))

    # no audio filter / amix anywhere in the captured argvs
    assert not any("amix" in tok for cmd in captured for tok in cmd)
    assert result["provenance"]["audio_present"] is False


def test_render_muxes_audio_when_file_exists(monkeypatch, tmp_path):
    """When a referenced audio file exists on disk it is muxed in (-i <file>)."""
    _sp, _gp, timeline, _edit = _chain()
    captured = _install_fake_ffmpeg(monkeypatch)
    out = tmp_path / "reel.mp4"

    # create a real audio file and reference it on a voice clip
    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"\x00" * 16)

    result = ffmpeg.render(timeline, str(out), audio_path=str(audio))

    assert any(str(audio) in tok for cmd in captured for tok in cmd)
    assert result["provenance"]["audio_present"] is True
