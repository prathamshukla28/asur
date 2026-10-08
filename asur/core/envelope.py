"""The universal artifact envelope - ASUR-VERSION-01 and ASUR-PROV-01.

Every stage of ASUR (idea, research, audience, strategy, hooks, script, ...)
emits exactly one kind of thing: an *artifact*. An artifact is a typed,
versioned, checksummed, provenance-bound record. The envelope is the outer
shell shared by all of them; the stage-specific payload lives in ``body``.

Envelope fields (schema_version "asur.artifact/v1"):
  artifact_id    "<kind>-<shorthash>" - stable id derived from content hash.
  kind           one of the 17 ASUR artifact kinds (see KINDS).
  version        monotonic integer within (project_id, kind). Starts at 1.
  schema_version "asur.artifact/v1".
  project_id     the project this artifact belongs to.
  created_at     UTC ISO-8601 timestamp (Z).
  creator        who produced it: {agent, local_user, git_name, git_email}.
  sources        [{artifact_id, version, checksum}] - upstream lineage.
  status         draft | ready | approved | rejected | superseded.
  review         {reviewer, decision, reason, reviewed_at, self_approved}.
  checksum       sha256 over the canonical BODY (not the whole envelope).
  supersedes     artifact_id of the artifact this one replaces, or null.
  body           the stage-specific payload.

Key design choices:
  - checksum is over the *body* only, so re-reviewing or superseding (which
    changes envelope metadata) does not change the content hash. Content
    identity is about *what was produced*, not *how it was filed*.
  - artifact_id embeds a short prefix of that body checksum, so identical
    bodies in the same kind collide intentionally (same content = same id),
    which is what we want for lineage.
  - nothing here mutates on disk; superseding writes a NEW artifact and marks
    the old one superseded (ASUR-VERSION-01: never silently overwrite).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional

from .canonical import canonical_sha256
from .identity import Identity, get_identity

__all__ = [
    "KINDS",
    "STATUSES",
    "Artifact",
    "make_artifact",
    "verify_checksum",
    "utc_now_iso",
]

# The 17 artifact kinds across the full ASUR lifecycle. Phase 1 produces the
# first six (idea..script) plus the quality gate's qa_report-style output;
# the rest are declared now so ids and validation are stable across phases.
KINDS = (
    "idea",
    "input_report",
    "research",
    "audience",
    "strategy",
    "hooks",
    "script",
    "timing",
    "sync_proof",
    "creative_direction",
    "visual_screenplay",
    "asset_plan",
    "generation_plan",
    "edit_plan",
    "qa_report",
    "viral_check",
    "publish_package",
    "performance",
    "learning",
)

STATUSES = ("draft", "ready", "approved", "rejected", "superseded")

_SHORTHASH_LEN = 12


def utc_now_iso() -> str:
    """Current UTC time as ISO-8601 with a trailing Z, seconds precision."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


@dataclass
class Artifact:
    """The universal envelope. Use :func:`make_artifact` to construct one."""

    artifact_id: str
    kind: str
    version: int
    schema_version: str
    project_id: str
    created_at: str
    creator: dict
    sources: list
    status: str
    review: Optional[dict]
    checksum: str
    supersedes: Optional[str]
    body: Any = field(default=None)

    def as_dict(self) -> dict:
        return asdict(self)

    def recompute_checksum(self) -> str:
        """Content hash over the canonical body only."""
        return canonical_sha256(self.body)


def _short_hash(body: Any) -> str:
    return canonical_sha256(body)[:_SHORTHASH_LEN]


def make_artifact(
    *,
    kind: str,
    project_id: str,
    body: Any,
    version: int = 1,
    sources: Optional[list] = None,
    status: str = "draft",
    supersedes: Optional[str] = None,
    agent: str = "asur",
    identity: Optional[Identity] = None,
) -> Artifact:
    """Build a fully-formed, checksummed artifact envelope.

    The caller supplies the *body* and lineage; this function stamps identity,
    timestamp, content hash, and a derived artifact_id. It does not touch disk
    (see core/workspace.py for persistence and version assignment).
    """
    if kind not in KINDS:
        raise ValueError(f"unknown artifact kind: {kind!r}")
    if status not in STATUSES:
        raise ValueError(f"unknown status: {status!r}")
    if version < 1:
        raise ValueError("version must be >= 1")

    ident = identity or get_identity()
    checksum = canonical_sha256(body)
    artifact_id = f"{kind}-{_short_hash(body)}"

    return Artifact(
        artifact_id=artifact_id,
        kind=kind,
        version=version,
        schema_version="asur.artifact/v1",
        project_id=project_id,
        created_at=utc_now_iso(),
        creator={
            "agent": agent,
            "local_user": ident.local_user,
            "git_name": ident.git_name,
            "git_email": ident.git_email,
        },
        sources=list(sources or []),
        status=status,
        review=None,
        checksum=checksum,
        supersedes=supersedes,
        body=body,
    )


def verify_checksum(artifact: Artifact) -> bool:
    """True iff the recorded checksum matches the canonical body hash.

    Fail-closed callers should treat False as a BLOCK condition: the artifact
    on disk does not match its own content hash (tampering or corruption).
    """
    return artifact.checksum == artifact.recompute_checksum()
