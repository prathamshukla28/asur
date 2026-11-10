"""Animated default cards: gradient motion, progress bar, caption reveal, xfade.

Stdlib-only, offline: ``subprocess.run`` is monkeypatched to capture the argv
the ffmpeg adapter builds (the real render + measurement of the motion lives in
``tests/integration/test_render_motion_measured.py``). These tests pin that
the motion is deterministic, timed to the timeline, and never invents text.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from asur.generation.adapters import ffmpeg

SCENES = [
    {"scene_id": "scene-01-hook", "start": 0.0, "end": 4.0},
    {"scene_id": "scene-02-value", "start": 4.0, "end": 9.5},
    {"scene_id": "scene-03-cta", "start": 9.5, "end": 12.0},
]
HOOK = "Most people get wasting money on AI tools completely wrong - here's why."


def _timeline(captions: dict[int, str] | None = None) -> dict:
    clips = []
    for i, scene in enumerate(SCENES):
        text = (captions or {}).get(i)
        overlays = (
            [{"type": "caption", "text": text, "start": scene["start"], "end": scene["end"]}]
            if text
            else []
        )
        clips.append({"timeline_start": scene["start"], "overlays": overlays})
    return {"scenes": SCENES, "tracks": [{"type": "text", "clips": clips}]}


class _Proc:
    def __init__(self, returncode: int = 0, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = ""


@pytest.fixture
def captured(monkeypatch, tmp_path):
    monkeypatch.setattr(ffmpeg, "_ffmpeg_available", lambda: True)
    monkeypatch.delenv(ffmpeg.ENV_FONTFILE, raising=False)
    calls: list[list[str]] = []

    def fake_run(cmd, *args, **kwargs):
        calls.append(list(cmd))
        Path(cmd[-1]).write_bytes(b"\x00")
        return _Proc()

    monkeypatch.setattr(ffmpeg.subprocess, "run", fake_run)
    return calls


def _card_cmds(calls: list[list[str]]) -> list[list[str]]:
    return [c for c in calls if Path(c[-1]).name.startswith("scene_")]


def _graph(cmd: list[str]) -> str:
    return cmd[cmd.index("-filter_complex") + 1]


def _gradient_source(cmd: list[str]) -> dict[str, str]:
    token = next(t for t in cmd if t.startswith("gradients="))
    return dict(part.split("=", 1) for part in token[len("gradients="):].split(":"))


# -- pure helpers --------------------------------------------------------------


def test_wrap_caption_fits_the_frame_and_keeps_every_word():
    font = ffmpeg._caption_font_size(1920)
    lines = ffmpeg._wrap_caption(HOOK, width=1080, font_size=font)
    max_chars = int(1080 * ffmpeg._CAPTION_WRAP_WIDTH / (font * ffmpeg._CAPTION_CHAR_WIDTH))
    assert len(lines) > 1
    assert all(len(line) <= max_chars for line in lines)
    assert " ".join(lines) == HOOK
    assert ffmpeg._wrap_caption("   ", width=1080, font_size=font) == []


def test_caption_block_stays_inside_the_safe_band():
    for n in range(1, 9):
        top = ffmpeg._caption_block_top(n, height=1920, line_px=126)
        assert top >= round(1920 * ffmpeg._CAPTION_SAFE_TOP)
        if n <= 3:
            assert top + n * 126 <= round(1920 * ffmpeg._CAPTION_SAFE_BOTTOM)
    assert ffmpeg._caption_block_top(1, height=1920, line_px=126) == round(1920 * 0.78)


def test_animated_drawtext_escapes_its_expressions(tmp_path):
    flt = ffmpeg._drawtext_filter(tmp_path / "c.txt", height=1920, y_px=1400, delay_s=0.32)
    assert flt.startswith("drawtext=textfile=") and ":expansion=none" in flt
    # commas inside the alpha/y expressions are filtergraph-escaped
    assert "alpha=min(1\\,max(0\\,(t-0.320)/0.350))" in flt
    assert "y=1400+" in flt
    static = ffmpeg._drawtext_filter(tmp_path / "c.txt", height=1920)
    assert "alpha=" not in static and f"y={round(1920 * 0.78)}" in static


def test_xfade_graph_offsets_are_the_scene_boundaries():
    graph = ffmpeg._xfade_graph([4.0, 5.5, 2.5], transition="slideup", transition_s=0.12)
    assert graph == (
        "[0:v][1:v]xfade=transition=slideup:duration=0.120:offset=4.000[x1];"
        "[x1][2:v]xfade=transition=slideup:duration=0.120:offset=9.500[v]"
    )


# -- render argv ---------------------------------------------------------------


def test_cards_are_animated_gradients_with_a_tail_for_the_transition(captured, tmp_path):
    result = ffmpeg.render(_timeline(), str(tmp_path / "out.mp4"))
    cards = _card_cmds(captured)
    assert len(cards) == 3
    lengths = [float(_gradient_source(c)["d"]) for c in cards]
    t = ffmpeg._TRANSITION_S
    assert lengths == [pytest.approx(4.0 + t), pytest.approx(5.5 + t), pytest.approx(2.5)]
    for i, card in enumerate(cards):
        src = _gradient_source(card)
        assert float(src["speed"]) == ffmpeg._GRADIENT_SPEED > 0
        assert (src["c0"], src["c1"]) == ffmpeg._GRADIENTS[i]
    prov = result["provenance"]
    assert prov["duration_s"] == 12.0
    assert prov["motion"]["transition"] == {"type": ffmpeg._TRANSITION, "duration_s": t}
    assert prov["motion"]["progress_bar"] is True


def test_consecutive_cards_alternate_dark_and_bright():
    def luma(hex_colour: str) -> float:
        r, g, b = (int(hex_colour[i:i + 2], 16) for i in (2, 4, 6))
        return 0.299 * r + 0.587 * g + 0.114 * b

    means = [(luma(c0) + luma(c1)) / 2 for c0, c1 in ffmpeg._GRADIENTS]
    assert len(means) % 2 == 0  # the cycle wraps dark -> bright too
    for i, mean in enumerate(means):
        nxt = means[(i + 1) % len(means)]
        assert abs(mean - nxt) >= 70, (i, mean, nxt)


def test_progress_bar_runs_across_the_whole_video(captured, tmp_path):
    ffmpeg.render(_timeline(), str(tmp_path / "out.mp4"))
    offsets = []
    for card in _card_cmds(captured):
        match = re.search(r"overlay=x=W\*\(([\d.]+)\+t\)/([\d.]+)-w", _graph(card))
        assert match, _graph(card)
        offsets.append(float(match.group(1)))
        assert float(match.group(2)) == 12.0
    assert offsets == [0.0, 4.0, 9.5]


def test_join_uses_xfade_at_the_timeline_boundaries(captured, tmp_path):
    ffmpeg.render(_timeline(), str(tmp_path / "out.mp4"))
    final = captured[-1]
    graph = _graph(final)
    assert re.findall(r"offset=([\d.]+)", graph) == ["4.000", "9.500"]
    assert "concat.txt" not in " ".join(final)


def test_transition_zero_is_hard_cuts_without_tails(captured, tmp_path):
    result = ffmpeg.render(_timeline(), str(tmp_path / "out.mp4"), transition_s=0)
    lengths = [float(_gradient_source(c)["d"]) for c in _card_cmds(captured)]
    assert lengths == [4.0, 5.5, 2.5]
    assert "concat.txt" in " ".join(captured[-1])
    assert result["provenance"]["motion"]["transition"] == {"type": "cut"}


def test_transition_is_clamped_below_the_shortest_scene(captured, tmp_path):
    timeline = {"scenes": [{"start": 0.0, "end": 1.0}, {"start": 1.0, "end": 3.0}]}
    result = ffmpeg.render(timeline, str(tmp_path / "out.mp4"), transition_s=5.0)
    assert result["provenance"]["motion"]["transition"]["duration_s"] == 0.5


def test_single_scene_has_no_transition(captured, tmp_path):
    result = ffmpeg.render({"scenes": [SCENES[0]]}, str(tmp_path / "hero.mp4"))
    assert result["provenance"]["motion"]["transition"] == {"type": "cut"}
    assert len(_card_cmds(captured)) == 1


def test_caption_lines_reveal_on_a_stagger_and_only_authored_text(captured, tmp_path):
    result = ffmpeg.render(_timeline({0: HOOK}), str(tmp_path / "out.mp4"))
    cards = _card_cmds(captured)
    hook_graph = _graph(cards[0])
    delays = [float(d) for d in re.findall(r"alpha=min\(1\\,max\(0\\,\(t-([\d.]+)\)", hook_graph)]
    assert len(delays) >= 2
    assert delays == sorted(delays) and delays[0] == ffmpeg._CAPTION_FIRST_DELAY_S
    # scenes without authored text get no drawtext at all
    assert all("drawtext" not in _graph(c) for c in cards[1:])
    assert result["provenance"]["captions_burned_in"] is True
    assert result["provenance"]["motion"]["caption_reveal"]


def test_render_argv_is_deterministic(captured, tmp_path):
    def normalised(calls: list[list[str]]) -> list[list[str]]:
        out = []
        for cmd in calls:
            out.append([re.sub(r"asur_render_[^/\\]+", "WORK", tok) for tok in cmd[1:]])
        return out

    ffmpeg.render(_timeline({0: HOOK, 2: "Save this"}), str(tmp_path / "a.mp4"))
    first = normalised(captured)
    captured.clear()
    ffmpeg.render(_timeline({0: HOOK, 2: "Save this"}), str(tmp_path / "a.mp4"))
    assert normalised(captured) == first


def test_fontfile_override_and_fail_closed(captured, tmp_path, monkeypatch):
    font = tmp_path / "My Font.ttf"
    font.write_bytes(b"\x00")
    monkeypatch.setenv(ffmpeg.ENV_FONTFILE, str(font))
    result = ffmpeg.render(_timeline({0: "Hello"}), str(tmp_path / "out.mp4"))
    assert "fontfile=" in _graph(_card_cmds(captured)[0])
    assert result["provenance"]["caption_font"] == "My Font.ttf"
    monkeypatch.setenv(ffmpeg.ENV_FONTFILE, str(tmp_path / "missing.ttf"))
    with pytest.raises(ffmpeg.RenderError, match="ASUR_FONTFILE"):
        ffmpeg.render(_timeline({0: "Hello"}), str(tmp_path / "out.mp4"))


def test_missing_drawtext_keeps_the_motion_and_records_the_skip(monkeypatch, tmp_path):
    monkeypatch.setattr(ffmpeg, "_ffmpeg_available", lambda: True)
    calls: list[list[str]] = []

    def fake_run(cmd, *args, **kwargs):
        calls.append(list(cmd))
        graph = cmd[cmd.index("-filter_complex") + 1] if "-filter_complex" in cmd else ""
        if "drawtext" in graph:
            return _Proc(returncode=1, stderr="No such filter: 'drawtext'")
        Path(cmd[-1]).write_bytes(b"\x00")
        return _Proc()

    monkeypatch.setattr(ffmpeg.subprocess, "run", fake_run)
    result = ffmpeg.render(_timeline({0: HOOK}), str(tmp_path / "out.mp4"))
    prov = result["provenance"]
    assert prov["captions_burned_in"] is False
    assert "drawtext" in prov["captions_skipped_reason"]
    retry = [c for c in calls if Path(c[-1]).name == "scene_000.mp4"][-1]
    assert any(t.startswith("gradients=") for t in retry)
    assert "overlay=x=" in _graph(retry)


def test_background_image_gets_a_ken_burns_zoom(captured, tmp_path):
    image = tmp_path / "bg.png"
    image.write_bytes(b"\x00")
    result = ffmpeg.render(
        _timeline(), str(tmp_path / "out.mp4"), backgrounds={"scene-01-hook": str(image)}
    )
    first = _card_cmds(captured)[0]
    assert str(image) in first
    assert "zoompan=z=1+" in _graph(first)
    assert result["provenance"]["backgrounds_used"] == 1
    assert "ken-burns" in result["provenance"]["motion"]["background"]


def test_thumbnail_waits_for_the_hook_caption_to_settle():
    last_line_done = ffmpeg._CAPTION_FIRST_DELAY_S + 5 * ffmpeg._CAPTION_STAGGER_S + ffmpeg._CAPTION_FADE_S
    assert ffmpeg.HOOK_FRAME_S >= last_line_done
    assert ffmpeg.thumbnail_timestamp(53.6) == ffmpeg.HOOK_FRAME_S
    assert ffmpeg.thumbnail_timestamp(2.0) == 1.0  # stays inside a short video
    assert ffmpeg.thumbnail_timestamp(None) == 0.0
