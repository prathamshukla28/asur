"""P10c: materialize the ready-to-upload package + thumbnail + content report.

Stdlib-only, offline, no-network, no-GPU. These UNIT tests NEVER invoke the real
ffmpeg binary: ``subprocess.run`` is monkeypatched so the thumbnail frame-grab is
captured (argv recorded, output file touched) rather than really decoded. The
real end-to-end folder (an actual .mp4 + .jpg a human can open) lives in the
opt-in integration suite (``pytest -m integration``).

Covered (P10c, SPEC-GAP G22/G23/G25):

  * learning/publish_package.py ``materialize_package(...)``
      - writes EXACTLY the authoritative ready-to-upload file set into
        ``youtube/<project_id>/package/`` via the O_EXCL MediaWorkspace: the
        DATA_MODELS.md set final-video.mp4 / thumbnail.jpg / title.txt /
        description.txt / tags.txt / platform-metadata.json / content-report.json
        (G22). No invented extra files.
      - thumbnail.jpg is produced by an FFmpeg frame-grab and carries a
        provenance + license block (G23, ASUR-PROV-01).
      - content-report.json is an honest lineage/explainability digest: artifact
        ids + checksums, QA disposition, viral verdict AS RECORDED (never a %),
        render provenance, probed dims; ``experiment_id`` null; no invented
        metrics and no "%" anywhere (G25, ASUR-HONEST-01 / ASUR-EXPLAIN-01).
      - re-running appends a new ``vNNNN-`` version rather than overwriting
        (ASUR-VERSION-01); fails closed if the render has no real video file.
"""

from __future__ import annotations

import json

import pytest

from asur.core.envelope import make_artifact
from asur.editing.timeline import build_edit_plan, build_timeline_from_generation_plan
from asur.generation import render as render_mod
from asur.generation.adapters import ffmpeg
from asur.generation.asset_strategy import build_asset_plan
from asur.generation.creative_direction import build_creative_direction
from asur.generation.generation_plan import build_generation_plan
from asur.generation.render import RenderError, build_final_render
from asur.generation.visual_screenplay import build_visual_screenplay
from asur.learning.publish_package import build_publish_package, materialize_package
from asur.script.audience import build_audience
from asur.script.hooks import build_hooks
from asur.script.idea import build_idea
from asur.script.research import build_research
from asur.script.script_builder import build_script
from asur.script.strategy import build_strategy

SAMPLE_IDEA = "why most people waste money on AI tools"
PROJECT_ID = "test-p10c"

# The authoritative ready-to-upload file set (DATA_MODELS.md L132). Each written
# file is versioned ``vNNNN-<name>`` by MediaWorkspace; we assert the base names.
_EXPECTED_NAMES = {
    "final-video.mp4",
    "thumbnail.jpg",
    "title.txt",
    "description.txt",
    "tags.txt",
    "platform-metadata.json",
    "content-report.json",
}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _chain():
    """Full chain through edit_plan + a viral_check artifact."""
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
    viral = make_artifact(
        kind="viral_check",
        project_id=PROJECT_ID,
        body={"verdict": "proceed"},
        status="ready",
        agent="viral-check",
    )
    return edit_plan, viral


class _FakeProc:
    def __init__(self, returncode: int = 0, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = ""


def _install_fake_ffmpeg(monkeypatch) -> list[list[str]]:
    """Fake the ffmpeg binary: record argv, touch the output file (last arg)."""
    captured: list[list[str]] = []

    def fake_run(cmd, *a, **k):
        captured.append(list(cmd))
        from pathlib import Path

        out = Path(cmd[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"\x00")
        return _FakeProc(0)

    monkeypatch.setattr(ffmpeg, "_ffmpeg_available", lambda: True)
    monkeypatch.setattr(ffmpeg.subprocess, "run", fake_run)
    return captured


def _fake_probe(monkeypatch, *, width=1080, height=1920, duration=6.0):
    """build_final_render probes via hero_proof; fake it to a passing result."""
    monkeypatch.setattr(render_mod.hero_proof, "_ffprobe_available", lambda: True)
    monkeypatch.setattr(
        render_mod.hero_proof,
        "_probe_dimensions_duration",
        lambda _p: (width, height, duration),
    )


def _render_artifact(monkeypatch, tmp_path, *, platform=None, width=1080, height=1920):
    """Produce a real-on-disk render artifact (fake ffmpeg) for packaging."""
    edit_plan, _ = _chain()
    _install_fake_ffmpeg(monkeypatch)
    _fake_probe(monkeypatch, width=width, height=height)
    out_root = tmp_path / "render-out"
    return build_final_render(
        edit_plan, PROJECT_ID, platform=platform, out_root=str(out_root)
    )


def _publish_artifact(platform="instagram_reels"):
    edit_plan, viral = _chain()
    return build_publish_package(
        edit_plan,
        viral,
        PROJECT_ID,
        title="Why most people waste money on AI tools",
        caption="A quick breakdown.",
        hashtags=["ai", "money"],
        platform=platform,
    )


def _written_names(paths) -> set[str]:
    """Strip the ``vNNNN-`` version prefix from each written path name."""
    names = set()
    for p in paths:
        name = p.name
        if name.startswith("v") and "-" in name:
            name = name.split("-", 1)[1]
        names.add(name)
    return names


def _read_by_name(paths, base_name: str) -> str:
    for p in paths:
        stripped = p.name.split("-", 1)[1] if p.name.startswith("v") and "-" in p.name else p.name
        if stripped == base_name:
            return p.read_text(encoding="utf-8")
    raise AssertionError(f"{base_name} not found in {[p.name for p in paths]}")


# --------------------------------------------------------------------------- #
# tests
# --------------------------------------------------------------------------- #


def test_materialize_writes_exact_authoritative_file_set(monkeypatch, tmp_path):
    render = _render_artifact(monkeypatch, tmp_path)
    publish = _publish_artifact()
    _install_fake_ffmpeg(monkeypatch)  # for the thumbnail frame-grab
    result = materialize_package(
        publish, render, PROJECT_ID, out_root=str(tmp_path / "proj")
    )
    assert _written_names(result["files"]) == _EXPECTED_NAMES


def test_package_lives_in_browsable_youtube_folder(monkeypatch, tmp_path):
    render = _render_artifact(monkeypatch, tmp_path)
    publish = _publish_artifact()
    _install_fake_ffmpeg(monkeypatch)
    root = tmp_path / "proj"
    result = materialize_package(publish, render, PROJECT_ID, out_root=str(root))
    for p in result["files"]:
        assert (root / "youtube" / PROJECT_ID / "package") in p.parents


def test_thumbnail_is_an_ffmpeg_framegrab(monkeypatch, tmp_path):
    render = _render_artifact(monkeypatch, tmp_path)
    publish = _publish_artifact()
    captured = _install_fake_ffmpeg(monkeypatch)
    materialize_package(publish, render, PROJECT_ID, out_root=str(tmp_path / "proj"))
    # A single-frame grab: -frames:v 1 output ending in .jpg, from the render mp4.
    grab = [c for c in captured if any(str(tok).endswith(".jpg") for tok in c)]
    assert grab, "expected an ffmpeg frame-grab for thumbnail.jpg"
    argv = grab[0]
    assert "-frames:v" in argv
    assert any("final-video.mp4" in str(tok) for tok in argv)


def test_content_report_is_honest_and_has_no_percent(monkeypatch, tmp_path):
    render = _render_artifact(monkeypatch, tmp_path)
    publish = _publish_artifact()
    _install_fake_ffmpeg(monkeypatch)
    result = materialize_package(
        publish, render, PROJECT_ID, out_root=str(tmp_path / "proj")
    )
    report_text = _read_by_name(result["files"], "content-report.json")
    assert "%" not in report_text  # ASUR-HONEST-01: never a % score
    report = json.loads(report_text)
    # lineage: ids + checksums of the source artifacts
    lineage = report["lineage"]
    ids = {entry["artifact_id"] for entry in lineage}
    assert publish.artifact_id in ids
    assert render.artifact_id in ids
    for entry in lineage:
        assert entry["checksum"]
    # viral verdict carried AS RECORDED, never a number
    assert report["viral_verdict"] == "proceed"
    # explicit null experiment id (no learning experiment attached yet)
    assert report["experiment_id"] is None
    # render provenance + probed dims carried through
    assert report["render"]["provenance"]["model"] == "FFmpeg"
    assert report["render"]["resolution"] == "1080x1920"


def test_metadata_json_carries_platform_and_title(monkeypatch, tmp_path):
    render = _render_artifact(monkeypatch, tmp_path)
    publish = _publish_artifact()
    _install_fake_ffmpeg(monkeypatch)
    result = materialize_package(
        publish, render, PROJECT_ID, out_root=str(tmp_path / "proj")
    )
    meta = json.loads(_read_by_name(result["files"], "platform-metadata.json"))
    assert meta["platform"] == "instagram_reels"
    assert meta["title"] == "Why most people waste money on AI tools"
    tags = _read_by_name(result["files"], "tags.txt")
    assert "ai" in tags


def test_rerun_appends_new_version_not_overwrite(monkeypatch, tmp_path):
    render = _render_artifact(monkeypatch, tmp_path)
    publish = _publish_artifact()
    root = str(tmp_path / "proj")
    _install_fake_ffmpeg(monkeypatch)
    first = materialize_package(publish, render, PROJECT_ID, out_root=root)
    _install_fake_ffmpeg(monkeypatch)
    second = materialize_package(publish, render, PROJECT_ID, out_root=root)
    first_versions = {p.name for p in first["files"]}
    second_versions = {p.name for p in second["files"]}
    # Nothing overwritten: the second run's filenames are all new (v0002-).
    assert first_versions.isdisjoint(second_versions)
    assert any(p.name.startswith("v0002-") for p in second["files"])


def test_materialize_fails_closed_without_real_video(monkeypatch, tmp_path):
    # A render artifact whose final_video points at a non-existent file.
    render = make_artifact(
        kind="render",
        project_id=PROJECT_ID,
        body={
            "subject": "x",
            "platform": "instagram_reels",
            "final_video": str(tmp_path / "missing" / "final-video.mp4"),
            "provenance": {"model": "FFmpeg", "resolution": "1080x1920"},
            "license": {"name": "LGPL/GPL", "commercial_ok": True},
            "verify": {"status": "pass", "checks": [], "reasons": []},
            "method": "x",
        },
        status="ready",
        agent="generation",
    )
    publish = _publish_artifact()
    _install_fake_ffmpeg(monkeypatch)
    with pytest.raises(RenderError):
        materialize_package(publish, render, PROJECT_ID, out_root=str(tmp_path / "proj"))


def test_youtube_long_description_carries_chapters(monkeypatch, tmp_path):
    render = _render_artifact(
        monkeypatch, tmp_path, platform="youtube_long", width=1920, height=1080
    )
    publish = _publish_artifact(platform="youtube_long")
    _install_fake_ffmpeg(monkeypatch)
    result = materialize_package(
        publish,
        render,
        PROJECT_ID,
        out_root=str(tmp_path / "proj"),
    )
    description = _read_by_name(result["files"], "description.txt")
    assert "Chapters:" in description
