"""CLI wiring: script / generate / viral-check / run (fast paths)."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from asur.cli import main
from asur.core.workspace import Workspace

IDEA = "why most people waste money on AI tools"
TAKEAWAY = "list every AI subscription you pay for and cancel the ones that use the same model"
HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.delenv("ASUR_LLM", raising=False)


def test_script_without_takeaway_is_held(tmp_path, capsys):
    assert main(["script", "--idea", IDEA, "--project", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "useful_info" in out and "HOLD" in out


def test_script_with_takeaway_ships(tmp_path, capsys):
    assert main(["script", "--idea", IDEA, "--takeaway", TAKEAWAY, "--project", str(tmp_path)]) == 0
    assert "[template]" in capsys.readouterr().out


def test_unknown_llm_provider_is_a_usage_error(tmp_path):
    assert main(["script", "--idea", IDEA, "--project", str(tmp_path), "--llm", "magic"]) == 2


def test_generate_without_script_holds(tmp_path, capsys):
    assert main(["generate", "--project", str(tmp_path)]) == 1
    assert "NO_SCRIPT" in capsys.readouterr().out


def test_generate_refuses_unapproved_script(tmp_path, capsys):
    main(["script", "--idea", IDEA, "--project", str(tmp_path)])
    assert main(["generate", "--project", str(tmp_path)]) == 1
    assert "SCRIPT_NOT_APPROVED" in capsys.readouterr().out


def test_viral_check_missing_file_fails_closed(tmp_path, capsys):
    assert main(["viral-check", str(tmp_path / "nope.mp4"), "--project", str(tmp_path)]) == 1
    assert "NOT_MEASURABLE" in capsys.readouterr().out


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg/ffprobe not on PATH")
def test_viral_check_on_a_real_file_saves_an_artifact(tmp_path, capsys):
    clip = tmp_path / "landscape.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "testsrc2=s=640x360:r=30:d=2", "-pix_fmt", "yuv420p", str(clip)], check=True)
    assert main(["viral-check", str(clip), "--project", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "REJECT" in out and "unknown" in out
    viral = Workspace(tmp_path, tmp_path.name).load_latest("viral_check")
    assert viral is not None and viral.body["verdict"] == "REJECT"


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg/ffprobe not on PATH")
def test_run_stops_at_the_first_human_gate_without_approval(tmp_path, capsys):
    code = main(["run", "--idea", IDEA, "--takeaway", TAKEAWAY, "--project", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1
    assert "HERO_PROOF_READY" in out and "HELD at HERO_PROOF_APPROVED" in out
    assert "HUMAN_APPROVAL_REQUIRED" in out
    assert (tmp_path / "youtube" / tmp_path.name / "render" / "hero-proof.mp4").is_file()


def test_run_holds_at_script_gate_without_takeaway(tmp_path, capsys):
    assert main(["run", "--idea", IDEA, "--project", str(tmp_path), "--self-approve"]) == 1
    assert "HELD at SCRIPT_APPROVED" in capsys.readouterr().out
