"""VIRAL CHECK over REAL rendered files (ffmpeg-generated fixtures).

Proves the scores and risk flags are functions of what is actually in the MP4:
different files -> different measurements -> different scores/flags. Skipped
when ffmpeg/ffprobe are not on PATH.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from asur.core import binaries
from asur.viral_check import probe
from asur.viral_check.check import check_video
from asur.viral_check.evaluate import PASS, REJECT
from asur.viral_check.facts import build_platform_facts, plan_facts
from asur.viral_check.probe import ProbeUnavailable, measure_video

pytestmark = pytest.mark.skipif(not probe.tools_available(), reason="ffmpeg/ffprobe not on PATH")


def _ffmpeg(*args: str) -> None:
    subprocess.run([binaries.ffmpeg_bin(), "-y", "-loglevel", "error", *args], check=True,
                   capture_output=True)


@pytest.fixture(scope="module")
def clips(tmp_path_factory) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("viral_fixtures")
    good = root / "good.mp4"
    # 9:16, moving picture with hard cuts every 2s, continuous tone near -14 LUFS.
    _ffmpeg(
        "-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=2",
        "-f", "lavfi", "-i", "smptehdbars=s=1080x1920:r=30:d=2",
        "-f", "lavfi", "-i", "testsrc=s=1080x1920:r=30:d=2",
        "-f", "lavfi", "-i", "sine=f=330:d=6",
        "-filter_complex",
        "[0:v][1:v][2:v]concat=n=3:v=1[v];"
        "[3:a]volume=9dB[a]",
        "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "ultrafast",
        "-pix_fmt", "yuv420p", "-c:a", "aac", str(good),
    )
    static_landscape = root / "static_landscape.mp4"
    _ffmpeg("-f", "lavfi", "-i", "color=c=0x1b2a3a:s=1920x1080:r=30:d=4",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            str(static_landscape))
    lowres = root / "lowres.mp4"
    _ffmpeg("-f", "lavfi", "-i", "testsrc2=s=360x640:r=30:d=3",
            "-f", "lavfi", "-i", "sine=f=440:d=3",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(lowres))
    return {"good": good, "static_landscape": static_landscape, "lowres": lowres}


def _dims(artifact) -> dict[str, dict]:
    return {d["dimension"]: d for d in artifact.body["dimensions"]}


def _codes(artifact) -> set[str]:
    return {f["code"] for f in artifact.body["risk_flags"]}


def test_measurements_reflect_the_file(clips):
    good = measure_video(clips["good"])
    assert (good["width"], good["height"]) == (1080, 1920)
    assert abs(good["duration_s"] - 6.0) < 0.2
    assert good["audio_present"] is True
    assert good["integrated_lufs"] is not None
    assert good["scene_changes_total"] >= 2
    assert good["sha256"].startswith("sha256:")

    static = measure_video(clips["static_landscape"])
    assert (static["width"], static["height"]) == (1920, 1080)
    assert static["audio_present"] is False
    assert static["scene_changes_total"] == 0
    assert static["frozen_ratio"] > 0.8


def test_good_vertical_clip_scores_high_and_passes(clips):
    art = check_video(clips["good"], "p", platform="instagram_reels")
    dims = _dims(art)
    assert dims["Platform Fit"]["score"] >= 85
    assert dims["Visual Quality"]["score"] >= 90
    assert dims["Attention"]["status"] == "scored"
    assert not any(f["hard"] for f in art.body["risk_flags"])
    assert art.body["verdict"] == PASS, art.body["risk_flags"]


def test_static_landscape_silent_clip_is_rejected_with_measured_reasons(clips):
    art = check_video(clips["static_landscape"], "p", platform="instagram_reels")
    assert art.body["verdict"] == REJECT
    assert {"wrong_aspect", "muted", "static_opening", "mostly_static"} <= _codes(art)
    good = check_video(clips["good"], "p", platform="instagram_reels")
    for name in ("Platform Fit", "Attention", "Retention"):
        assert _dims(art)[name]["score"] < _dims(good)[name]["score"]


def test_same_landscape_file_fits_youtube_long_aspect(clips):
    art = check_video(clips["static_landscape"], "p", platform="youtube_long")
    assert "wrong_aspect" not in _codes(art)
    assert "outside_duration_band" in _codes(art)  # 4s is far below the 3-20 min band


def test_low_resolution_is_a_hard_flag(clips):
    art = check_video(clips["lowres"], "p", platform="instagram_reels")
    assert "low_resolution" in _codes(art)
    assert art.body["verdict"] == REJECT
    good = check_video(clips["good"], "p", platform="instagram_reels")
    assert _dims(art)["Visual Quality"]["score"] < _dims(good)["Visual Quality"]["score"] - 25


def test_artifact_is_bound_to_the_measured_bytes(clips):
    art = check_video(clips["good"], "p", platform="instagram_reels")
    assert art.body["coverage"]["unknown"] == 8  # semantic + undeclared dimensions
    digest = measure_video(clips["good"])["sha256"]
    assert digest in art.body["bundle_hashes"].values()
    # the facts actually used are recorded per component
    comps = {c["name"] for c in _dims(art)["Platform Fit"]["components"]}
    assert {"aspect", "duration", "audio", "loudness"} <= comps


def test_plan_captions_not_burned_in_is_flagged(clips):
    edit_plan = {"timeline": {"tracks": [{"type": "text", "clips": [
        {"overlays": [{"type": "caption", "text": "Stop paying twice", "start": 0.0, "end": 2.0}]}
    ]}]}}
    render = {"provenance": {"captions_burned_in": False,
                             "captions_skipped_reason": "ffmpeg build lacks drawtext"}}
    plan = plan_facts(edit_plan, render)
    assert plan["hook_word_count"] == 3
    art = check_video(clips["good"], "p", platform="instagram_reels", plan=plan)
    assert "captions_missing" in _codes(art)
    captions = next(c for c in _dims(art)["Retention"]["components"] if c["name"] == "captions")
    assert captions["value"] == 0.0


def test_unmeasurable_file_fails_closed(tmp_path, monkeypatch):
    with pytest.raises(ProbeUnavailable):
        measure_video(tmp_path / "missing.mp4")
    bogus = tmp_path / "not_video.mp4"
    bogus.write_bytes(b"not a video")
    with pytest.raises(ProbeUnavailable):
        measure_video(bogus)
    monkeypatch.delenv("ASUR_FFMPEG", raising=False)
    monkeypatch.delenv("ASUR_FFPROBE", raising=False)
    monkeypatch.setattr(binaries.shutil, "which", lambda name: None)
    with pytest.raises(ProbeUnavailable):
        measure_video(bogus)


def test_platform_facts_record_expected_contract():
    facts = build_platform_facts({"width": 1080, "height": 1920, "duration_s": 30.0},
                                 platform="youtube_shorts")
    assert facts["aspect_matches"] is True
    assert facts["duration_band_s"] == [15.0, 60.0]
    assert facts["max_duration_s"] == 180.0
