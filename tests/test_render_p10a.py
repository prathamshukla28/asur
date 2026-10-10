"""P10a: render-kind envelope, media workspace, and the G24 chapters fix.

Stdlib-only, offline, no-network, no-GPU. No ffmpeg is invoked here; P10a is the
behaviour-neutral groundwork for the real render path (P10b/P10c). It covers:

  * core/envelope.py -- a new ``render`` artifact kind (a rendered .mp4 is a
    first-class, versioned, checksummed artifact like every other stage output).
    Unknown kinds must still be rejected (fail-closed, ASUR-GATE-01).

  * core/media_workspace.py -- a browsable per-project media store rooted at
    ``<project_root>/youtube/<project_id>/`` with ``render/``, ``package/`` and
    ``_work/`` subfolders. Writes are O_EXCL append-only: a second write to the
    same relative path is refused (ASUR-VERSION-01). JSON artifacts keep living
    in ``.script/``; this store holds media + the ready-to-upload bundle only.

  * learning/publish_package.py -- G24 bug fix. ``_chapters_from_edit`` read a
    top-level ``edit_body['clips']`` key that ``build_edit_plan`` never writes
    (clips live under ``body['timeline']['tracks'][*]['clips']`` and scenes under
    ``body['timeline']['scenes']``), so long-form chapters were ALWAYS empty for
    a real edit_plan. The fix reads chapters from ``timeline.scenes`` while the
    Instagram default stays byte-identical (IG declares no ``description`` field,
    so no long-form keys are ever emitted).
"""

from __future__ import annotations

import pytest

from asur.core.envelope import KINDS, make_artifact
from asur.editing.timeline import build_edit_plan, build_timeline_from_generation_plan
from asur.generation.asset_strategy import build_asset_plan
from asur.generation.creative_direction import build_creative_direction
from asur.generation.generation_plan import build_generation_plan
from asur.generation.visual_screenplay import build_visual_screenplay
from asur.learning.publish_package import build_publish_package
from asur.script.audience import build_audience
from asur.script.hooks import build_hooks
from asur.script.idea import build_idea
from asur.script.research import build_research
from asur.script.script_builder import build_script
from asur.script.strategy import build_strategy

SAMPLE_IDEA = "why most people waste money on AI tools"
PROJECT_ID = "test-p10a"


# --------------------------------------------------------------------------- #
# core/envelope.py: the new ``render`` kind
# --------------------------------------------------------------------------- #


def test_render_is_a_known_kind():
    """A rendered video is a first-class artifact kind."""
    assert "render" in KINDS


def test_render_artifact_builds():
    art = make_artifact(
        kind="render",
        project_id=PROJECT_ID,
        body={"final_video": "render/v0001-final.mp4", "width": 1920, "height": 1080},
        status="ready",
        agent="generation",
    )
    assert art.kind == "render"
    assert art.artifact_id.startswith("render-")


def test_unknown_kind_still_rejected():
    """Fail-closed: a bogus kind is still refused (ASUR-GATE-01)."""
    with pytest.raises(ValueError):
        make_artifact(
            kind="definitely_not_a_kind",
            project_id=PROJECT_ID,
            body={},
            status="ready",
            agent="generation",
        )


# --------------------------------------------------------------------------- #
# core/media_workspace.py: browsable per-project media store
# --------------------------------------------------------------------------- #


def _media_workspace(tmp_path):
    from asur.core.media_workspace import MediaWorkspace

    return MediaWorkspace(tmp_path, PROJECT_ID)


def test_media_workspace_layout(tmp_path):
    _media_workspace(tmp_path).ensure()
    base = tmp_path / "youtube" / PROJECT_ID
    assert (base / "render").is_dir()
    assert (base / "package").is_dir()
    assert (base / "_work").is_dir()


def test_media_workspace_write_text_and_bytes(tmp_path):
    ws = _media_workspace(tmp_path).ensure()
    tpath = ws.write_text("package", "title.txt", "My Title")
    bpath = ws.write_bytes("render", "clip.bin", b"\x00\x01\x02")
    assert tpath.read_text(encoding="utf-8") == "My Title"
    assert bpath.read_bytes() == b"\x00\x01\x02"
    base = tmp_path / "youtube" / PROJECT_ID
    assert tpath == base / "package" / "title.txt"
    assert bpath == base / "render" / "clip.bin"


def test_media_workspace_refuses_overwrite(tmp_path):
    """O_EXCL append-only: a second write to the same path fails closed."""
    from asur.core.media_workspace import MediaWorkspaceError

    ws = _media_workspace(tmp_path).ensure()
    ws.write_text("package", "title.txt", "first")
    with pytest.raises(MediaWorkspaceError):
        ws.write_text("package", "title.txt", "second")


def test_media_workspace_next_version(tmp_path):
    """next_version hands out monotonically increasing vNNNN- prefixes."""
    ws = _media_workspace(tmp_path).ensure()
    first = ws.next_version("render", "final.mp4")
    ws.write_bytes("render", first, b"a")
    second = ws.next_version("render", "final.mp4")
    ws.write_bytes("render", second, b"b")
    assert first == "v0001-final.mp4"
    assert second == "v0002-final.mp4"


def test_media_workspace_rejects_unknown_subdir(tmp_path):
    """Only the declared subfolders are writable (fail-closed)."""
    from asur.core.media_workspace import MediaWorkspaceError

    ws = _media_workspace(tmp_path).ensure()
    with pytest.raises(MediaWorkspaceError):
        ws.write_text("secrets", "leak.txt", "nope")


# --------------------------------------------------------------------------- #
# learning/publish_package.py: G24 chapters-from-timeline fix
# --------------------------------------------------------------------------- #


def _real_edit_plan(project_id: str = PROJECT_ID):
    """A real edit_plan artifact whose body carries a timeline with scenes."""
    idea = build_idea(SAMPLE_IDEA, project_id)
    research = build_research(idea, project_id)
    audience = build_audience(idea, research, project_id)
    strategy = build_strategy(idea, audience, project_id)
    hooks = build_hooks(strategy, project_id)
    script = build_script(strategy, hooks, project_id)
    creative = build_creative_direction(strategy, script, project_id)
    screenplay = build_visual_screenplay(creative, script, project_id)
    asset_plan = build_asset_plan(screenplay, project_id, monetized=True)
    gen_plan = build_generation_plan(asset_plan, project_id)
    timeline = build_timeline_from_generation_plan(gen_plan, screenplay, project_id)
    return build_edit_plan(timeline, gen_plan, project_id), timeline


def _viral():
    return make_artifact(
        kind="viral_check",
        project_id=PROJECT_ID,
        body={"verdict": "proceed"},
        status="ready",
        agent="viral-check",
    )


def test_chapters_populated_from_real_timeline_scenes():
    """G24: long-form chapters come from timeline.scenes, not a phantom key."""
    edit, timeline = _real_edit_plan()
    pkg = build_publish_package(
        edit, _viral(), PROJECT_ID, title="t", caption="c", platform="youtube_long"
    )
    chapters = pkg.body["chapters"]
    assert isinstance(chapters, list)
    assert len(chapters) == len(timeline.scenes)
    assert len(chapters) > 0
    for chapter in chapters:
        assert isinstance(chapter["start_s"], float)
        assert isinstance(chapter["title"], str) and chapter["title"]
    # Chapters are ordered by start time (a valid YouTube chapter list must be).
    starts = [c["start_s"] for c in chapters]
    assert starts == sorted(starts)
    # First chapter must start at 0 for YouTube to accept the chapter list.
    assert chapters[0]["start_s"] == 0.0


def test_description_embeds_chapter_timestamps():
    """The long-form description surfaces the timestamped chapter list (G24)."""
    edit, _timeline = _real_edit_plan()
    pkg = build_publish_package(
        edit, _viral(), PROJECT_ID, title="t", caption="c", platform="youtube_long"
    )
    description = pkg.body["description"]
    assert "Chapters:" in description
    assert "00:00" in description


def test_instagram_default_still_byte_identical_with_timeline():
    """The G24 fix must not leak long-form keys into the Instagram default."""
    edit, _timeline = _real_edit_plan()
    pkg = build_publish_package(edit, _viral(), PROJECT_ID, title="t", caption="c")
    for key in ("description", "tags", "chapters", "category", "end_screen", "cards"):
        assert key not in pkg.body
