"""Full `asur run`: real render + measured viral check + publish gate (needs ffmpeg)."""

from __future__ import annotations

import json

import pytest

from asur.cli import main
from asur.core.workspace import Workspace

pytestmark = pytest.mark.integration


def test_run_end_to_end_produces_mp4_trail_and_measured_check(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("ASUR_LLM", raising=False)
    code = main([
        "run", "--idea", "why most people waste money on AI tools",
        "--takeaway", "cancel AI subscriptions that run the same underlying model",
        "--project", str(tmp_path), "--self-approve", "--platform", "youtube_shorts",
    ])
    out = capsys.readouterr().out
    assert code in (0, 1)
    assert "VIRAL_CHECK_APPROVED" in out  # measured check ran on the real file
    ws = Workspace(tmp_path, tmp_path.name)
    render = ws.load_latest("render")
    viral = ws.load_latest("viral_check")
    assert render is not None and viral is not None
    video = render.body["final_video"]
    assert video.endswith(".mp4")
    # The viral check is bound to the exact bytes on disk.
    from asur.tools.pipeline import file_sha256

    assert file_sha256(video) in viral.body["bundle_hashes"].values()
    # Every scored dimension is backed by measured/plan components.
    for d in viral.body["dimensions"]:
        assert (d["score"] is None) == (d["status"] == "unknown")
    # The run log records the state machine's real progress.
    log = (tmp_path / ".asur" / "runs" / "run-1.jsonl").read_text().splitlines()
    states = [json.loads(line).get("tokens", {}).get("state") for line in log]
    assert "QA" in states
