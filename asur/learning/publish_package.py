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

from ..core.envelope import Artifact, make_artifact
from ..core.gate import GateResult, approval_gate
from ..core.identity import Identity
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
