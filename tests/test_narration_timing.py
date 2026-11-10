"""Scenes timed from MEASURED narration: no dead air at the end of each scene.

Root cause this guards against: the planner sizes scenes at 2.5 words/s, real
speech engines talk faster, and the narration used to be padded to the planned
span, leaving up to 2.7 s of silence per scene (the viral check's
``long_silence`` flag on the README demo).

The regression test synthesizes narration through the real ffmpeg path with a
stand-in "speech engine" (a tone whose length is proportional to the word
count, with leading/trailing silence like a real engine), then measures the
WAV with the viral check's own silencedetect pass.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from asur.core.binaries import ffmpeg_bin, ffmpeg_path, ffprobe_path
from asur.editing import narration_timing as nt
from asur.editing.narration_timing import fit_scene_durations, timed_edit_plan
from asur.generation.adapters import system_tts
from asur.viral_check import probe

HAS_FFMPEG = ffmpeg_path() is not None and ffprobe_path() is not None
_LONG_SILENCE_S = 2.0  # asur.viral_check.evaluate._LONG_SILENCE_S

# Planned like the script builder plans them (2.5 words/s), from the demo.
SEGMENTS = [
    {"start": 0.0, "end": 4.8, "text": "Most people get this completely wrong and here is why."},
    {"start": 4.8, "end": 9.2, "text": "If this sounds familiar the next thirty seconds are for you."},
    {"start": 9.2, "end": 14.0, "text": "Save this so you have it the next time."},
]
SECONDS_PER_WORD = 0.2  # ~5 words/s: faster than the 2.5 words/s plan, like `say`


def _scenes(caption: str = "short") -> list[dict]:
    return [{"start": s["start"], "end": s["end"], "graphics": {"onscreen_text": caption}}
            for s in SEGMENTS]


# -- pure timing rules -----------------------------------------------------------


def test_scene_lasts_as_long_as_its_speech_plus_a_bounded_pad():
    assert fit_scene_durations(_scenes(), [2.04, 3.0, 1.71]) == [2.4, 3.3, 2.1]


def test_scene_is_never_shorter_than_its_caption_takes_to_read():
    caption = " ".join(["word"] * 18)
    (dur,) = fit_scene_durations([{"graphics": {"onscreen_text": caption}}], [4.07])
    assert dur >= 18 / nt.READING_WPS
    assert 18 / dur <= 3.5  # under the viral check's caption-density limit


def test_unnarrated_beat_is_capped_and_short_lines_get_the_minimum():
    scenes = [{"start": 0.0, "end": 6.0}, {"start": 6.0, "end": 7.0}]
    assert fit_scene_durations(scenes, [None, 0.2]) == [nt.UNNARRATED_MAX_S, nt.MIN_SCENE_S]
    assert nt.UNNARRATED_MAX_S < _LONG_SILENCE_S


def test_fit_rejects_a_measurement_count_mismatch():
    with pytest.raises(ValueError):
        fit_scene_durations(_scenes(), [1.0])


def test_timed_edit_plan_moves_scenes_and_captions_and_is_reproducible():
    from asur.editing.timeline import (
        build_edit_plan,
        build_timeline_from_generation_plan,
    )
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

    pid = "timing"
    idea = build_idea("why most people waste money on AI tools", pid)
    research = build_research(idea, pid)
    strategy = build_strategy(idea, build_audience(idea, research, pid), pid)
    script = build_script(strategy, build_hooks(strategy, pid), pid)
    screenplay = build_visual_screenplay(build_creative_direction(strategy, script, pid), script, pid)
    gen_plan = build_generation_plan(build_asset_plan(screenplay, pid), pid,
                                     visual_screenplay_artifact=screenplay)
    planned = build_edit_plan(build_timeline_from_generation_plan(gen_plan, screenplay, pid),
                              gen_plan, pid)
    n = len(screenplay.body["scenes"])
    speech = [2.0] * n

    timed = timed_edit_plan(gen_plan, screenplay, pid, speech, engine="test")
    scenes = timed.body["timeline"]["scenes"]
    assert scenes[0]["start"] == 0.0
    assert all(a["end"] == b["start"] for a, b in zip(scenes, scenes[1:]))
    assert timed.body["timing"]["source"] == nt.TIMING_SOURCE
    assert timed.body["timing"]["total_s"] == scenes[-1]["end"]
    assert scenes[-1]["end"] < planned.body["timeline"]["scenes"][-1]["end"]
    # every caption overlay sits inside its (retimed) scene
    spans = {s["scene_id"]: (s["start"], s["end"]) for s in scenes}
    for track in timed.body["timeline"]["tracks"]:
        for clip in track["clips"]:
            for ov in clip.get("overlays", []):
                sid = clip["asset_ref"][: -len("-onscreen-text")]
                assert spans[sid][0] <= ov["start"] < ov["end"] <= spans[sid][1]
    # the saved screenplay is untouched; the rebuild is deterministic
    assert screenplay.body["scenes"][-1]["end"] == planned.body["timeline"]["scenes"][-1]["end"]
    again = timed_edit_plan(gen_plan, screenplay, pid, speech, engine="test")
    assert again.checksum == timed.checksum


# -- regression: measured silence in the synthesized narration ------------------


@pytest.fixture
def fake_engine(monkeypatch):
    """A deterministic stand-in speech engine driven through the real ffmpeg path."""
    import subprocess

    def speak(engine, text, out, rate_wpm):
        words = len(text.split())
        subprocess.run(
            [ffmpeg_bin(), "-y", "-loglevel", "error", "-f", "lavfi", "-i",
             f"sine=frequency=220:duration={words * SECONDS_PER_WORD:.3f}",
             # engine-style padding: 0.25 s of silence before and after the words
             "-af", "adelay=250,apad=pad_dur=0.25", "-ac", "1", "-ar", "22050", str(out)],
            check=True, capture_output=True,
        )

    monkeypatch.setattr(system_tts, "available_engine", lambda: "espeak-ng")
    monkeypatch.setattr(system_tts, "_speak", speak)


def _longest_silence(wav: Path) -> float:
    return probe._audio_pass(wav, system_tts._duration(wav), 60.0)["longest_silence_s"]


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg/ffprobe not available")
def test_planned_padding_leaves_a_long_silent_gap(fake_engine, tmp_path):
    """The OLD behaviour (pad speech to the planned span) fails the silence check."""
    out = system_tts.synthesize_narration(SEGMENTS, tmp_path / "planned.wav")
    assert out["provenance"]["timing"] == "planned"
    assert _longest_silence(Path(out["file_path"])) > _LONG_SILENCE_S


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg/ffprobe not available")
def test_measured_timing_removes_the_dead_air(fake_engine, tmp_path):
    scenes = _scenes()
    out = system_tts.synthesize_narration(
        SEGMENTS, tmp_path / "timed.wav",
        fit_durations=lambda speech: fit_scene_durations(scenes, speech),
    )
    prov = out["provenance"]
    assert prov["timing"] == "measured"
    # engine padding was trimmed before measuring: speech_s is the words only
    for seg, spoken in zip(SEGMENTS, prov["speech_s"]):
        assert spoken == pytest.approx(len(seg["text"].split()) * SECONDS_PER_WORD, abs=0.06)
    assert prov["segments_sped_up_to_fit"] == 0
    assert _longest_silence(Path(out["file_path"])) < 0.5
    assert prov["duration_s"] == pytest.approx(sum(prov["segment_durations_s"]), abs=0.05)
