"""Publish package - the final bundle a human reviews before posting (Stage 24).

A publish_package gathers everything needed to post the finished Reel: the final
video reference, a thumbnail, and the platform-facing metadata (title, caption,
hashtags, CTA). It carries lineage back to the edit_plan (the assembled video)
and the viral_check (the honest evaluation that preceded human approval), so the
decision to publish is always traceable (ASUR-PROV-01, ASUR-EXPLAIN-01).

Building the package does NOT publish anything. Publishing is a human gate
(ASUR-HUMAN-01); see publish_gate() in this package.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ..core.envelope import Artifact, make_artifact
from ..core.gate import GateResult, approval_gate
from ..core.identity import Identity
from ..core.media_workspace import MediaWorkspace
from ..platforms import DEFAULT_PLATFORM as _DEFAULT_PLATFORM
from ..platforms import get_platform
from . import source_ref


def _as_float(value: object, default: float) -> float:
    """Coerce a possibly-missing timeline value to float, failing safe to default."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _scene_title(scene_id: str, index: int) -> str:
    """Derive a human chapter title from a ``scene-NN-<section>`` id.

    Honest derivation only (ASUR-HONEST-01 / §7 anti-hallucination): the title
    comes from the scene_id's section token, never an invented label. e.g.
    ``scene-01-hook`` -> ``Hook``. Unparseable ids fall back to the raw id.
    """
    parts = str(scene_id).split("-")
    # "scene-01-hook" -> parts = ["scene", "01", "hook"]; section token is the tail.
    if len(parts) >= 3:
        section = "-".join(parts[2:]).strip()
        if section:
            return section.replace("_", " ").title()
    return str(scene_id) or f"Section {index + 1}"


def _chapters_from_edit(edit_body: dict) -> list[dict]:
    """Build YouTube chapters from the edit plan's timeline scenes.

    The edit_plan body stores scenes under ``body['timeline']['scenes']`` as
    ``{scene_id, start, end}`` (see editing/timeline.py). Earlier code read a
    non-existent top-level ``clips`` key, so chapters were always empty (G24).
    Keeps the ``{start_s, title}`` shape so long-form publish fields and the
    P09c anchors are unaffected; an edit_body with no timeline yields ``[]``.
    """
    timeline = edit_body.get("timeline")
    if not isinstance(timeline, dict):
        return []
    scenes = timeline.get("scenes")
    if not isinstance(scenes, list):
        return []
    chapters: list[dict] = []
    for index, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            continue
        start = _as_float(scene.get("start"), 0.0)
        title = _scene_title(scene.get("scene_id", ""), index)
        chapters.append({"start_s": start, "title": title})
    return chapters


def _description_with_chapters(subject: str, caption: str, chapters: list[dict]) -> str:
    lines = [caption] if caption else []
    if chapters:
        lines.append("")
        lines.append("Chapters:")
        for chapter in chapters:
            total = int(chapter["start_s"])
            stamp = f"{total // 60:02d}:{total % 60:02d}"
            lines.append(f"{stamp} {chapter['title']}")
    return "\n".join(lines)


def _longform_fields(pack, edit_body: dict, caption: str, hashtags: list) -> dict:
    subject = edit_body.get("subject", "")
    chapters = _chapters_from_edit(edit_body)
    fields = {
        "description": _description_with_chapters(subject, caption, chapters),
        "chapters": chapters,
        "tags": list(hashtags),
    }
    if "category" in pack.publish_fields:
        fields["category"] = ""
    if "end_screen" in pack.publish_fields:
        fields["end_screen"] = []
    if "cards" in pack.publish_fields:
        fields["cards"] = []
    return fields


def build_publish_package(
    edit_plan_artifact: Artifact,
    viral_check_artifact: Artifact,
    project_id: str,
    *,
    title: str,
    caption: str,
    hashtags: list | None = None,
    cta: str = "",
    platform: str = _DEFAULT_PLATFORM,
    identity: Identity | None = None,
) -> Artifact:
    """Assemble the publish package from the assembled video + its evaluation.

    The final_video_ref points at the edit_plan (the assembled timeline is the
    source of truth for what gets rendered). The verdict from the viral check is
    carried along so a reviewer sees the honest evaluation next to what they are
    about to post - never a single % number, just the recorded verdict.
    """
    edit_body = edit_plan_artifact.body or {}
    viral_body = viral_check_artifact.body or {}
    subject = edit_body.get("subject", "")

    # get_platform fails closed on an unknown id (ASUR-GATE-01); the default
    # Instagram pack returns '9:16', keeping today's output byte-identical.
    pack = get_platform(platform)

    body = {
        "subject": subject,
        "platform": platform,
        "final_video_ref": edit_plan_artifact.artifact_id,
        "thumbnail_ref": f"{project_id}-thumbnail",
        "title": title,
        "caption": caption,
        "hashtags": list(hashtags or []),
        "cta": cta,
        "viral_verdict": viral_body.get("verdict", "unknown"),
        "metadata": {
            "aspect_ratio": pack.format_spec.aspect_ratio,
            "clip_count": edit_body.get("clip_count", 0),
        },
        "method": (
            "local assembly of the approved video and its honest evaluation; "
            "publishing is a separate human gate and never automatic"
        ),
    }

    # Long-form packs (e.g. youtube_long) declare extra publish fields the Reels
    # default never carries. We emit those keys ONLY when the chosen pack declares
    # them, so the Instagram default body stays byte-identical (ASUR-VERSION-01).
    # Every value is derived from recorded inputs or left as an explicit empty
    # placeholder for the human to fill - we invent no content (ASUR-HONEST-01,
    # anti-hallucination §7).
    if "description" in pack.publish_fields:
        body.update(_longform_fields(pack, edit_body, caption, hashtags or []))

    return make_artifact(
        kind="publish_package",
        project_id=project_id,
        body=body,
        status="ready",
        sources=[source_ref(edit_plan_artifact), source_ref(viral_check_artifact)],
        agent="learning",
        identity=identity,
    )


def publish_gate(
    publish_package_artifact: Artifact,
    *,
    producer: Identity,
    approver: Identity | None = None,
    allow_self_approval: bool = False,
) -> GateResult:
    """The publish gate (Stage 25) - the second and final human gate.

    ASUR never auto-publishes (ASUR-HUMAN-01). With no approver the gate holds at
    HUMAN_APPROVAL_REQUIRED. A single-user who approves their own work is recorded
    honestly as SELF_APPROVED (held unless self-approval is explicitly permitted).
    Only a distinct, declared approver clears the gate to SHIP.
    """
    return approval_gate(
        "publish",
        producer=producer,
        approver=approver,
        allow_self_approval=allow_self_approval,
    )


# The exact, authoritative ready-to-upload file set (DATA_MODELS.md L132). The
# human opens this folder and uploads these files by hand - ASUR never posts
# (ASUR-HUMAN-01). caption.txt / cta.txt are written only when the pack declares
# them; everything else is always present.
_PACKAGE_FINAL_VIDEO = "final-video.mp4"
_PACKAGE_THUMBNAIL = "thumbnail.jpg"
_PACKAGE_TITLE = "title.txt"
_PACKAGE_DESCRIPTION = "description.txt"
_PACKAGE_TAGS = "tags.txt"
_PACKAGE_METADATA = "platform-metadata.json"
_PACKAGE_REPORT = "content-report.json"


def _lineage_entry(artifact: Artifact) -> dict:
    return {
        "artifact_id": artifact.artifact_id,
        "checksum": artifact.checksum,
        "kind": artifact.kind,
    }


def materialize_package(
    publish_package_artifact: Artifact,
    render_artifact: Artifact,
    project_id: str,
    *,
    out_root,
    identity: Identity | None = None,
) -> dict:
    """Write the ready-to-upload file set to a browsable per-project folder.

    Materializes the approved publish package + its real render into
    ``<out_root>/youtube/<project_id>/package/`` as the authoritative DATA_MODELS
    file set (G22). The thumbnail is a frame grabbed from the real render (G23);
    content-report.json is an honest explainability digest (G25) - artifact
    lineage, the recorded viral verdict (never a "% viral" number), render
    provenance, and probed dimensions - with no invented metrics.

    Fails closed (ASUR-GATE-01): if the render's final video is not a real file
    on disk, raises ``RenderError`` rather than packaging a phantom. Every write
    is append-only and versioned through ``MediaWorkspace`` (ASUR-VERSION-01); a
    re-run never overwrites, it appends ``v0002-``.

    The render adapter + its ``RenderError`` are imported lazily so the learning
    layer never imports the GENERATION media path at module load (ASUR-FIREWALL /
    stdlib-core boundary).
    """
    from ..generation.adapters import ffmpeg as _ffmpeg
    from ..generation.render import RenderError

    pub_body = publish_package_artifact.body or {}
    render_body = render_artifact.body or {}
    platform = pub_body.get("platform", _DEFAULT_PLATFORM)

    final_video = render_body.get("final_video", "")
    if not final_video or not Path(final_video).is_file():
        raise RenderError(
            "cannot materialize a package without a real rendered video; "
            f"render artifact points at a missing file: {final_video!r} "
            "(fail closed, ASUR-GATE-01)"
        )

    workspace = MediaWorkspace(out_root, project_id).ensure()
    files: list[Path] = []

    def _write_bytes(base: str, data: bytes) -> Path:
        name = workspace.next_version("package", base)
        return workspace.write_bytes("package", name, data)

    def _write_text(base: str, text: str) -> Path:
        name = workspace.next_version("package", base)
        return workspace.write_text("package", name, text)

    files.append(_write_bytes(_PACKAGE_FINAL_VIDEO, Path(final_video).read_bytes()))

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_jpg = Path(tmpdir) / "thumb.jpg"
        # The settled hook frame: captions reveal over the first ~1.5s, so t=0
        # would be a frame with no text yet.
        duration = (render_body.get("provenance") or {}).get("duration_s")
        stamp = _ffmpeg.thumbnail_timestamp(duration if isinstance(duration, (int, float)) else None)
        thumb = _ffmpeg.grab_thumbnail(final_video, str(tmp_jpg), timestamp_s=stamp)
        files.append(_write_bytes(_PACKAGE_THUMBNAIL, tmp_jpg.read_bytes()))

    title = str(pub_body.get("title", ""))
    description = str(pub_body.get("description") or pub_body.get("caption", ""))
    tags = pub_body.get("tags") or pub_body.get("hashtags") or []
    files.append(_write_text(_PACKAGE_TITLE, title))
    files.append(_write_text(_PACKAGE_DESCRIPTION, description))
    files.append(_write_text(_PACKAGE_TAGS, "\n".join(str(t) for t in tags)))

    metadata = {
        "platform": platform,
        "title": title,
        "caption": pub_body.get("caption", ""),
        "hashtags": list(pub_body.get("hashtags") or []),
        "cta": pub_body.get("cta", ""),
        "aspect_ratio": pub_body.get("metadata", {}).get("aspect_ratio", ""),
    }
    for longform_key in ("description", "chapters", "tags", "category", "end_screen", "cards"):
        if longform_key in pub_body:
            metadata[longform_key] = pub_body[longform_key]
    files.append(_write_text(_PACKAGE_METADATA, json.dumps(metadata, indent=2)))

    provenance = render_body.get("provenance", {})
    report = {
        "schema": "asur.content-report/v1",
        "project_id": project_id,
        "platform": platform,
        "content_category": platform,
        "experiment_id": None,
        "lineage": [
            _lineage_entry(publish_package_artifact),
            _lineage_entry(render_artifact),
        ],
        "viral_verdict": pub_body.get("viral_verdict", "unknown"),
        "qa_disposition": None,
        "render": {
            "provenance": provenance,
            "resolution": provenance.get("resolution"),
            "duration_s": provenance.get("duration_s"),
            "verify": render_body.get("verify", {}),
        },
        "thumbnail": {"provenance": thumb.get("provenance", {})},
        "note": (
            "honest digest of recorded inputs; the viral verdict is the evaluator's "
            "recorded label, not a predicted outcome, and no metric is invented"
        ),
    }
    report_text = json.dumps(report, indent=2)
    files.append(_write_text(_PACKAGE_REPORT, report_text))

    return {"files": files, "folder": workspace.base / "package"}
