"""VIRAL CHECK verdict: twelve dimensions, risk flags, no single %viral.

This is the evaluation instrument. It reads ONLY the VIRAL_VIEW
projection (ASUR-FIREWALL-01) - it never imports or reads anything
from GENERATION, and it never sees the quality/hardness targets that
define "what good was". It judges the rendered bytes against documented
platform signals, not against the author's playbook.

Honesty rules (ASUR-HONEST-01):
  1. No single "%viral" number. Only the twelve individual 0-100 scores.
  2. Penalties are BINARY RISK FLAGS, never percentage deductions.
  3. The verdict is PASS / PASS-WITH-CHANGES / REJECT.
"""

from __future__ import annotations

from typing import Any

from ..core.envelope import Artifact, make_artifact
from ..core.identity import Identity
from .dimensions import score_all
from . import source_ref

# Verdict vocabulary (closed set).
PASS = "PASS"
PASS_WITH_CHANGES = "PASS-WITH-CHANGES"
REJECT = "REJECT"

# Thresholds on individual dimensions (never aggregated).
_WEAK_DIMENSION = 55

# platform_facts flags that trigger a binary risk flag. Each maps a fact
# key to (is-hard-risk, human-readable flag). Hard risks block a PASS.
_RISK_RULES = (
    ("visible_watermark", True,
     "RISK: visible watermark -> reposted/watermarked suppression on Instagram"),
    ("reposted_elsewhere", True,
     "RISK: already posted elsewhere -> originality ineligibility on Instagram"),
    ("low_resolution", True,
     "RISK: low resolution -> Instagram demotes low-res Reels"),
    ("muted", False,
     "RISK: no audio -> Instagram demotes muted Reels"),
    ("bordered", False,
     "RISK: visible borders -> Instagram demotes bordered Reels"),
    ("majority_text", False,
     "RISK: majority on-screen text -> Instagram demotes text-heavy Reels"),
)


def _facts(view: dict) -> dict:
    facts = view.get("platform_facts")
    return facts if isinstance(facts, dict) else {}


def risk_flags(view: dict) -> list[dict]:
    """Derive binary risk flags from the VIRAL_VIEW. Never a % deduction."""
    facts = _facts(view)
    flags: list[dict] = []
    for key, hard, message in _RISK_RULES:
        if facts.get(key):
            flags.append({"flag": message, "hard": hard})
    return flags


def decide_verdict(dimensions: list[dict], flags: list[dict]) -> str:
    """Map dimension scores + risk flags to a verdict (deterministic).

    - Any HARD risk flag -> REJECT (a reach-breaking defect).
    - Any soft risk flag OR any weak dimension -> PASS-WITH-CHANGES.
    - Otherwise -> PASS.
    No number is summed or averaged; this reads the individual signals.
    """
    if any(f["hard"] for f in flags):
        return REJECT
    weak = any(d["score"] < _WEAK_DIMENSION for d in dimensions)
    if flags or weak:
        return PASS_WITH_CHANGES
    return PASS


def build_viral_check(
    viral_view: dict,
    project_id: str,
    *,
    source_artifacts: list[Artifact] | None = None,
    identity: Identity | None = None,
) -> Artifact:
    """Evaluate a VIRAL_VIEW into a viral_check artifact.

    The body carries the twelve individual dimension scores, the binary
    risk flags, and the verdict - and deliberately NO aggregate score.
    """
    dimensions = score_all(viral_view)
    flags = risk_flags(viral_view)
    verdict = decide_verdict(dimensions, flags)

    weak = [d["dimension"] for d in dimensions if d["score"] < _WEAK_DIMENSION]
    evidence_notes = [
        "Scores rate input quality against documented signals, not outcome.",
        "'Signal exists' (verified) is separate from 'weight known' (unknown).",
        "Platform ranking weights are not published and change over time.",
        "Per-video reach is probabilistic and partly serendipitous.",
    ]

    sources = [source_ref(a) for a in (source_artifacts or [])]
    body = {
        "stage": "viral_check",
        "dimensions": dimensions,
        "risk_flags": flags,
        "weak_dimensions": weak,
        "verdict": verdict,
        "evidence_notes": evidence_notes,
        "method": (
            "Twelve dimensions scored 0-100 individually from the VIRAL_VIEW; "
            "risk flags are binary; no single viral percentage is produced."
        ),
    }
    return make_artifact(
        kind="viral_check",
        project_id=project_id,
        body=body,
        status="ready",
        sources=sources,
        agent="viral-check",
        identity=identity,
    )
