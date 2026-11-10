"""Render failures must say why: quiet ffmpeg flags, exit status, stderr head + tail.

CI once failed with ``ffmpeg xfade join failed: <400 chars of progress lines>``:
the progress meter had pushed every real message out of the tail. Stdlib-only,
offline: ``subprocess.run`` is monkeypatched.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from asur.generation.adapters import ffmpeg


class _Proc:
    def __init__(self, returncode: int = 0, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = ""


def test_failure_names_a_fatal_signal():
    msg = ffmpeg._failure("ffmpeg xfade join failed", _Proc(-9, ""))
    assert "killed by SIGKILL" in msg
    assert "(no stderr output)" in msg


def test_failure_drops_progress_and_keeps_head_and_tail():
    progress = "\r".join(f"frame= {i} fps=90 size= 1KiB time=00:00:01.00 speed=3x" for i in range(500))
    stderr = "[in#0] first real error\n" + progress + "\n" + "\n".join(f"warn {i}" for i in range(40)) + "\nlast real error\n"
    msg = ffmpeg._failure("ffmpeg xfade join failed", _Proc(1, stderr), keep=5)
    assert "exit code 1" in msg
    assert "first real error" in msg and "last real error" in msg
    assert "frame=" not in msg
    assert "lines omitted" in msg


def test_timeout_becomes_render_error(monkeypatch):
    def fake_run(cmd, *args, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))

    monkeypatch.setattr(ffmpeg.subprocess, "run", fake_run)
    with pytest.raises(ffmpeg.RenderError, match="timed out"):
        ffmpeg._run_ffmpeg(["ffmpeg"], timeout=5, what="ffmpeg xfade join")


def test_every_render_command_runs_quiet(monkeypatch, tmp_path):
    monkeypatch.setattr(ffmpeg, "_ffmpeg_available", lambda: True)
    calls: list[list[str]] = []

    def fake_run(cmd, *args, **kwargs):
        calls.append(list(cmd))
        Path(cmd[-1]).write_bytes(b"\x00")
        return _Proc()

    monkeypatch.setattr(ffmpeg.subprocess, "run", fake_run)
    scenes = [
        {"scene_id": "a", "start": 0.0, "end": 2.0},
        {"scene_id": "b", "start": 2.0, "end": 4.0},
    ]
    ffmpeg.render({"scenes": scenes}, str(tmp_path / "out.mp4"))
    ffmpeg.grab_thumbnail(str(tmp_path / "out.mp4"), str(tmp_path / "thumb.jpg"))
    assert len(calls) >= 4  # 2 cards + join + thumbnail
    for cmd in calls:
        assert "-nostats" in cmd and "-hide_banner" in cmd, cmd


def test_failed_join_reports_the_real_error(monkeypatch, tmp_path):
    monkeypatch.setattr(ffmpeg, "_ffmpeg_available", lambda: True)

    def fake_run(cmd, *args, **kwargs):
        if "-filter_complex" in cmd and any("xfade" in t for t in cmd):
            return _Proc(-9, "frame= 1316 fps= 91 size= 3584KiB time=00:00:43.80 speed=3.02x")
        Path(cmd[-1]).write_bytes(b"\x00")
        return _Proc()

    monkeypatch.setattr(ffmpeg.subprocess, "run", fake_run)
    cards = [tmp_path / "scene_000.mp4", tmp_path / "scene_001.mp4"]
    with pytest.raises(ffmpeg.RenderError, match="killed by SIGKILL") as info:
        ffmpeg._xfade_join(cards, [2.0, 2.0], tmp_path / "out.mp4", transition_s=0.12)
    assert "frame=" not in str(info.value)


def test_xfade_failure_falls_back_to_a_trimmed_hard_cut_join(monkeypatch, tmp_path):
    monkeypatch.setattr(ffmpeg, "_ffmpeg_available", lambda: True)
    calls: list[list[str]] = []

    def fake_run(cmd, *args, **kwargs):
        calls.append(list(cmd))
        graph = cmd[cmd.index("-filter_complex") + 1] if "-filter_complex" in cmd else ""
        if "xfade=" in graph:
            return _Proc(-9, "")
        Path(cmd[-1]).write_bytes(b"\x00")
        return _Proc()

    monkeypatch.setattr(ffmpeg.subprocess, "run", fake_run)
    scenes = [
        {"scene_id": "a", "start": 0.0, "end": 2.0},
        {"scene_id": "b", "start": 2.0, "end": 4.5},
    ]
    with pytest.warns(RuntimeWarning, match="hard cuts"):
        result = ffmpeg.render({"scenes": scenes}, str(tmp_path / "out.mp4"))
    join = calls[-1]
    graph = join[join.index("-filter_complex") + 1]
    assert "trim=duration=2.000" in graph and "trim=duration=2.500" in graph
    assert "concat=n=2:v=1:a=0[v]" in graph
    transition = result["provenance"]["motion"]["transition"]
    assert transition["type"] == "cut" and transition["fallback_from"] == ffmpeg._TRANSITION
    assert "killed by SIGKILL" in transition["fallback_reason"]
