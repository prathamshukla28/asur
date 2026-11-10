"""ffmpeg/ffprobe binary resolution: PATH by default, ASUR_FFMPEG/ASUR_FFPROBE override.

Stdlib-only and offline: fake executables are tiny shell scripts in tmp_path and
``subprocess.run`` is monkeypatched where a call would otherwise run.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from asur.core import binaries
from asur.generation.adapters import ffmpeg
from asur.viral_check import probe


def _fake_exe(path: Path) -> Path:
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(binaries.ENV_FFMPEG, raising=False)
    monkeypatch.delenv(binaries.ENV_FFPROBE, raising=False)


def test_default_is_the_path_lookup(monkeypatch):
    monkeypatch.setattr(binaries.shutil, "which", lambda name: f"/usr/bin/{name}")
    assert binaries.ffmpeg_path() == "/usr/bin/ffmpeg"
    assert binaries.ffprobe_path() == "/usr/bin/ffprobe"


def test_env_override_points_at_an_executable(monkeypatch, tmp_path):
    exe = _fake_exe(tmp_path / "ffmpeg-static")
    monkeypatch.setenv(binaries.ENV_FFMPEG, str(exe))
    monkeypatch.setattr(binaries.shutil, "which", lambda name: f"/usr/bin/{name}")
    assert binaries.ffmpeg_path() == str(exe)
    assert binaries.ffmpeg_bin() == str(exe)
    # the two overrides are independent: ffprobe still comes from PATH
    assert binaries.ffprobe_path() == "/usr/bin/ffprobe"


def test_env_override_expands_user(monkeypatch, tmp_path):
    exe = _fake_exe(tmp_path / "ffprobe")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv(binaries.ENV_FFPROBE, "~/ffprobe")
    assert binaries.ffprobe_path() == str(exe)


def test_bad_override_fails_closed_without_falling_back_to_path(monkeypatch, tmp_path):
    monkeypatch.setattr(binaries.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setenv(binaries.ENV_FFMPEG, str(tmp_path / "missing"))
    assert binaries.ffmpeg_path() is None
    not_exec = tmp_path / "plain-file"
    not_exec.write_text("x", encoding="utf-8")
    not_exec.chmod(0o644)
    monkeypatch.setenv(binaries.ENV_FFMPEG, str(not_exec))
    assert binaries.ffmpeg_path() is None
    # argv[0] falls back to the bare name, so the call fails loudly, never silently
    assert binaries.ffmpeg_bin() == "ffmpeg"


def test_bare_command_name_override_uses_path(monkeypatch):
    monkeypatch.setattr(binaries.shutil, "which",
                        lambda name: "/opt/ff/bin/ffmpeg7" if name == "ffmpeg7" else None)
    monkeypatch.setenv(binaries.ENV_FFMPEG, "ffmpeg7")
    assert binaries.ffmpeg_path() == "/opt/ff/bin/ffmpeg7"
    monkeypatch.setenv(binaries.ENV_FFMPEG, "nope" + os.sep + "ffmpeg7")
    assert binaries.ffmpeg_path() is None


def test_probe_and_adapter_follow_the_override(monkeypatch, tmp_path):
    monkeypatch.setattr(binaries.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setenv(binaries.ENV_FFMPEG, str(tmp_path / "missing"))
    assert probe.tools_available() is False
    assert ffmpeg._ffmpeg_available() is False
    with pytest.raises(ffmpeg.RenderError, match="ASUR_FFMPEG"):
        ffmpeg.render({"scenes": [{"start": 0.0, "end": 2.0}]}, str(tmp_path / "x.mp4"))


def test_render_invokes_the_override_binary(monkeypatch, tmp_path):
    exe = _fake_exe(tmp_path / "ffmpeg-with-drawtext")
    monkeypatch.setenv(binaries.ENV_FFMPEG, str(exe))
    captured: list[list[str]] = []

    class _Proc:
        returncode = 0
        stderr = ""
        stdout = ""

    def fake_run(cmd, *args, **kwargs):
        captured.append(list(cmd))
        Path(cmd[-1]).write_bytes(b"\x00")
        return _Proc()

    monkeypatch.setattr(ffmpeg.subprocess, "run", fake_run)
    timeline = {"scenes": [{"start": 0.0, "end": 2.0}, {"start": 2.0, "end": 4.0}]}
    ffmpeg.render(timeline, str(tmp_path / "out.mp4"))
    assert captured and all(cmd[0] == str(exe) for cmd in captured)
