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
from . import source_ref

_DEFAULT_PLATFORM = "instagram_reels"


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
            "aspect_ratio": "9:16",
            "clip_count": edit_body.get("clip_count", 0),
        },
        "method": (
            "local assembly of the approved video and its honest evaluation; "
            "publishing is a separate human gate and never automatic"
        ),
    }

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
