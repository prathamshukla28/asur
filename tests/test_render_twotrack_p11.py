"""P11 polish: two-track voice-over-ducked-music audio mix on the real render seam.

Stdlib-only, offline, no-network, no-GPU. These UNIT tests NEVER invoke the real
ffmpeg binary: ``subprocess.run`` is monkeypatched to capture the argv the adapter
builds (and to fake a successful render by touching the output file). The real
end-to-end mixed render lives in the opt-in integration suite
(``tests/integration/test_render_pipeline.py``, ``pytest -m integration``).

The mix contract (ASUR-EXPLAIN-01):

  * When BOTH a voice track AND a music bed are present, the adapter mixes them
    with ``filter_complex``: the voice sits at the reference level and the music
    is ducked well under it so narration stays intelligible. The dB levels come
    from ``asur.editing.audio_mix`` (voice -3dB, music -18dB, duck -8dB).
  * When only ONE audio track (voice OR music) is present the single-track path
    muxes it directly: one audio ``-i`` input, no ``amix`` and no volume graph.
    (The video side may still use ``filter_complex`` for the xfade transitions.)
  * With no audio the render stays silent (no fabricated track).
"""

from __future__ import annotations

from asur.editing.audio_mix import DEFAULT_DUCK_DB, DEFAULT_MUSIC_DB, DEFAULT_VOICE_DB
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
PROJECT_ID = "test-twotrack"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _edit_plan():
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
    def __init__(self, returncode: int = 0, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = ""


def _install_fake_ffmpeg(monkeypatch):
    monkeypatch.setattr(ffmpeg, "_ffmpeg_available", lambda: True)
    captured: list[list[str]] = []

    def fake_run(cmd, *args, **kwargs):
        captured.append(list(cmd))
        from pathlib import Path

        out = Path(cmd[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"\x00")
        return _FakeProc(returncode=0)

    monkeypatch.setattr(ffmpeg.subprocess, "run", fake_run)
    return captured


def _concat_cmd(captured: list[list[str]]) -> list[str]:
    """The final join/mux command: the one that reads the per-scene cards.

    With transitions on (the default) that is the xfade join; with
    ``transition_s=0`` it is the concat-demuxer command. Both mux the audio.
    """
    for cmd in captured:
        joined = " ".join(cmd)
        if "concat.txt" in joined or "xfade=" in joined:
            return cmd
    raise AssertionError("no join/mux command captured")


# --------------------------------------------------------------------------- #
# two-track mix
# --------------------------------------------------------------------------- #


def test_voice_and_music_are_mixed_with_ducking(monkeypatch, tmp_path):
    """Both tracks present -> filter_complex amix with voice/music/duck levels."""
    _, timeline = _edit_plan()
    captured = _install_fake_ffmpeg(monkeypatch)
    voice = tmp_path / "voice.wav"
    voice.write_bytes(b"\x00")
    music = tmp_path / "music.wav"
    music.write_bytes(b"\x00")
    out = tmp_path / "mixed.mp4"

    result = ffmpeg.render(
        timeline, str(out), audio_path=str(voice), music_path=str(music)
    )

    concat = _concat_cmd(captured)
    joined = " ".join(concat)
    # Both audio inputs wired.
    assert str(voice) in joined
    assert str(music) in joined
    # A real mix, not a single pass-through track.
    assert "filter_complex" in joined
    assert "amix" in joined
    # Levels sourced from audio_mix (voice louder, music ducked).
    assert f"{DEFAULT_VOICE_DB}dB" in joined or f"volume={DEFAULT_VOICE_DB}" in joined
    ducked = DEFAULT_MUSIC_DB + DEFAULT_DUCK_DB
    assert f"{ducked}dB" in joined or f"volume={ducked}" in joined
    assert result["provenance"]["audio_present"] is True
    assert result["provenance"]["audio_tracks"] == 2


def test_voice_only_is_single_track_no_mix(monkeypatch, tmp_path):
    """One voice track -> single -i input, no amix (byte-identical single-track)."""
    _, timeline = _edit_plan()
    captured = _install_fake_ffmpeg(monkeypatch)
    voice = tmp_path / "voice.wav"
    voice.write_bytes(b"\x00")
    out = tmp_path / "voice_only.mp4"

    result = ffmpeg.render(timeline, str(out), audio_path=str(voice))

    concat = _concat_cmd(captured)
    joined = " ".join(concat)
    assert str(voice) in joined
    assert "amix" not in joined
    assert "volume=" not in joined
    assert result["provenance"]["audio_present"] is True
    assert result["provenance"]["audio_tracks"] == 1


def test_music_only_without_voice_is_single_track(monkeypatch, tmp_path):
    """Music but no voice -> single-track mux, no ducking/amix."""
    _, timeline = _edit_plan()
    captured = _install_fake_ffmpeg(monkeypatch)
    music = tmp_path / "music.wav"
    music.write_bytes(b"\x00")
    out = tmp_path / "music_only.mp4"

    result = ffmpeg.render(timeline, str(out), music_path=str(music))

    concat = _concat_cmd(captured)
    joined = " ".join(concat)
    assert str(music) in joined
    assert "amix" not in joined
    assert result["provenance"]["audio_present"] is True
    assert result["provenance"]["audio_tracks"] == 1


def test_no_audio_stays_silent(monkeypatch, tmp_path):
    """No audio at all -> silent render, no audio input, no mix."""
    _, timeline = _edit_plan()
    captured = _install_fake_ffmpeg(monkeypatch)
    out = tmp_path / "silent.mp4"

    result = ffmpeg.render(timeline, str(out))

    concat = _concat_cmd(captured)
    joined = " ".join(concat)
    assert "amix" not in joined
    assert "volume=" not in joined
    assert result["provenance"]["audio_present"] is False
    assert result["provenance"]["audio_tracks"] == 0


def test_missing_music_file_is_ignored_not_fabricated(monkeypatch, tmp_path):
    """A music_path that is not on disk is dropped (voice stays single-track)."""
    _, timeline = _edit_plan()
    captured = _install_fake_ffmpeg(monkeypatch)
    voice = tmp_path / "voice.wav"
    voice.write_bytes(b"\x00")
    out = tmp_path / "x.mp4"

    result = ffmpeg.render(
        timeline, str(out), audio_path=str(voice), music_path=str(tmp_path / "nope.wav")
    )

    concat = _concat_cmd(captured)
    joined = " ".join(concat)
    assert "amix" not in joined
    assert result["provenance"]["audio_tracks"] == 1


def test_hard_cut_mode_uses_concat_and_keeps_the_mix(monkeypatch, tmp_path):
    """transition_s=0 joins with the concat demuxer; the two-track mix is unchanged."""
    _, timeline = _edit_plan()
    captured = _install_fake_ffmpeg(monkeypatch)
    voice = tmp_path / "voice.wav"
    voice.write_bytes(b"\x00")
    music = tmp_path / "music.wav"
    music.write_bytes(b"\x00")
    out = tmp_path / "cut.mp4"

    result = ffmpeg.render(
        timeline, str(out), audio_path=str(voice), music_path=str(music), transition_s=0
    )

    joined = " ".join(_concat_cmd(captured))
    assert "concat.txt" in joined and "xfade" not in joined
    assert "amix" in joined and f"volume={DEFAULT_VOICE_DB}dB" in joined
    assert result["provenance"]["motion"]["transition"] == {"type": "cut"}


def test_xfade_mode_maps_audio_after_the_card_inputs(monkeypatch, tmp_path):
    """With transitions, audio inputs follow the N card inputs (indices N, N+1)."""
    _, timeline = _edit_plan()
    captured = _install_fake_ffmpeg(monkeypatch)
    voice = tmp_path / "voice.wav"
    voice.write_bytes(b"\x00")
    out = tmp_path / "x.mp4"

    result = ffmpeg.render(timeline, str(out), audio_path=str(voice))

    cmd = _concat_cmd(captured)
    n_cards = result["provenance"]["scene_count"]
    assert cmd.count("-i") == n_cards + 1
    maps = [cmd[i + 1] for i, tok in enumerate(cmd) if tok == "-map"]
    assert maps == ["[v]", f"{n_cards}:a"]
