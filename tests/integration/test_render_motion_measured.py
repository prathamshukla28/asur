"""The animated default render, measured by the same probe the viral check uses.

Real ffmpeg (opt-in ``pytest -m integration``). Proves the motion is real pixel
change in the output file - ``freezedetect`` no longer sees frozen cards and
``scdet`` sees the scene changes - and that transitions keep the timeline's
length, so narration stays in sync.
"""

from __future__ import annotations

import pytest

from asur.generation.adapters import ffmpeg
from asur.viral_check import probe

pytestmark = pytest.mark.integration

TIMELINE = {
    "scenes": [
        {"scene_id": "s1", "start": 0.0, "end": 3.0},
        {"scene_id": "s2", "start": 3.0, "end": 6.0},
        {"scene_id": "s3", "start": 6.0, "end": 9.0},
    ],
    "tracks": [],
}


@pytest.fixture(scope="module")
def measured(tmp_path_factory):
    if not probe.tools_available():
        pytest.skip("ffprobe not available")
    root = tmp_path_factory.mktemp("motion")
    out = {}
    for name, trans in (("xfade", None), ("cut", 0)):
        path = root / f"{name}.mp4"
        ffmpeg.render(TIMELINE, str(path), transition_s=trans)
        out[name] = probe.measure_video(path)
    return out


@pytest.mark.parametrize("mode", ["xfade", "cut"])
def test_animated_cards_are_not_frozen(measured, mode):
    facts = measured[mode]
    assert facts["frozen_ratio"] < 0.1, facts
    assert facts["black_total_s"] == 0


@pytest.mark.parametrize("mode", ["xfade", "cut"])
def test_transitions_keep_the_timeline_length(measured, mode):
    assert measured[mode]["duration_s"] == pytest.approx(9.0, abs=0.1)
    assert (measured[mode]["width"], measured[mode]["height"]) == (1080, 1920)


def test_scene_changes_are_measurable(measured):
    assert measured["cut"]["scene_changes_total"] >= 2
    assert measured["xfade"]["scene_changes_total"] >= 1


def test_xfade_failure_falls_back_to_trimmed_hard_cuts(tmp_path, monkeypatch):
    """A failed xfade pass still yields a timeline-length file, with the reason recorded."""
    if not probe.tools_available():
        pytest.skip("ffprobe not available")

    def broken_join(*args, **kwargs):
        raise ffmpeg.RenderError("ffmpeg xfade join failed (killed by SIGKILL):\n(no stderr output)")

    monkeypatch.setattr(ffmpeg, "_xfade_join", broken_join)
    path = tmp_path / "fallback.mp4"
    with pytest.warns(RuntimeWarning, match="hard cuts"):
        result = ffmpeg.render(TIMELINE, str(path))
    facts = probe.measure_video(path)
    assert facts["duration_s"] == pytest.approx(9.0, abs=0.1)
    assert facts["scene_changes_total"] >= 2
    transition = result["provenance"]["motion"]["transition"]
    assert transition["type"] == "cut"
    assert transition["fallback_from"] == ffmpeg._TRANSITION
    assert "SIGKILL" in transition["fallback_reason"]
