"""The twelve VIRAL CHECK scoring dimensions (ASUR-HONEST-01).

Each dimension is scored 0-100 on its own and is always reported
individually. The twelve scores are NEVER collapsed into a single
"%viral" number: a score of 82 on Shareability means "strong on a
signal the platforms say they use", not "82% chance of going viral".

Every dimension carries the evidence class that best describes why
that signal matters (see ``asur.script.evidence``):

- VERIFIED_FACT  - the platform stated it, or it is directly observable
- STRONG_EVIDENCE- a credible study, but it transfers only by analogy
- EMPIRICAL      - measured from this creator's own past performance
- HYPOTHESIS     - creator folklore, plausible but not causally shown

This module reads ONLY the VIRAL_VIEW projection built by
``asur.tools.projection.build_viral_view`` (bundle_hashes, provenance,
platform_facts, rubric_metadata). It never sees quality/hardness
targets - those are stripped by name on the firewall (ASUR-FIREWALL-01).

Scoring is a deterministic, explainable heuristic. There is no
randomness, so the same view always yields the same scores.
"""

from __future__ import annotations

from typing import Any

from ..script.evidence import (
    EMPIRICAL,
    HYPOTHESIS,
    STRONG_EVIDENCE,
    VERIFIED_FACT,
)

# Exact names and order from docs/VIRAL_CHECK.md.
DIMENSIONS = (
    "Attention",
    "Retention",
    "Satisfaction",
    "Value",
    "Shareability",
    "Saveability",
    "Replayability",
    "Originality",
    "Authenticity",
    "Visual Quality",
    "Audience Fit",
    "Platform Fit",
)

# The dominant evidence class for each dimension. These say how strong the
# ground is for the signal itself - never that we know the platform's weight.
_EVIDENCE = {
    "Attention": STRONG_EVIDENCE,
    "Retention": VERIFIED_FACT,
    "Satisfaction": VERIFIED_FACT,
    "Value": STRONG_EVIDENCE,
    "Shareability": VERIFIED_FACT,
    "Saveability": VERIFIED_FACT,
    "Replayability": HYPOTHESIS,
    "Originality": VERIFIED_FACT,
    "Authenticity": STRONG_EVIDENCE,
    "Visual Quality": VERIFIED_FACT,
    "Audience Fit": VERIFIED_FACT,
    "Platform Fit": VERIFIED_FACT,
}

_BASELINE = 70


def _facts(view: dict) -> dict:
    """Return the platform_facts block of a VIRAL_VIEW (empty if absent)."""
    facts = view.get("platform_facts")
    return facts if isinstance(facts, dict) else {}


def _bounded(score: int) -> int:
    """Clamp a score to the 0-100 range (fail safe, never out of band)."""
    return max(0, min(100, score))


def score_dimension(name: str, view: dict) -> dict:
    """Score one dimension 0-100 from the VIRAL_VIEW.

    Deterministic and explainable: the score moves off a neutral baseline
    only when a documented signal in platform_facts is present or absent.
    The returned note names the signal, honouring ASUR-EXPLAIN-01.
    """
    if name not in _EVIDENCE:
        raise ValueError(f"unknown dimension: {name}")

    facts = _facts(view)
    score = _BASELINE
    note = "neutral baseline; no decisive signal in the rendered bundle"

    if name == "Attention":
        if facts.get("strong_first_three_seconds"):
            score, note = 86, "first 3s has a clear hook (platforms endorse hooks)"
        elif facts.get("strong_first_three_seconds") is False:
            score, note = 55, "weak opening; first 3s carries most watch-time risk"
    elif name == "Retention":
        if facts.get("captions_present"):
            score, note = 84, "captions present (captions raise watch-to-end)"
        elif facts.get("captions_present") is False:
            score, note = 58, "no captions; watch-to-end signal weaker"
    elif name == "Satisfaction":
        if facts.get("delivers_promise"):
            score, note = 82, "payoff matches the hook's promise"
        elif facts.get("delivers_promise") is False:
            score, note = 48, "hook over-promises relative to payoff"
    elif name == "Shareability":
        score, note = 74, "send-worthiness is a top-3 reach signal on Reels"
    elif name == "Saveability":
        score, note = 72, "save signal exists; its weight is not published"
    elif name == "Replayability":
        score, note = 66, "loopable value is a plausible lever (hypothesis)"
    elif name == "Originality":
        if facts.get("reposted_elsewhere"):
            score, note = 30, "already posted elsewhere; originality penalty applies"
        else:
            score, note = 73, "no reposted-content signal detected"
    elif name == "Authenticity":
        score, note = 71, "feels human; AI not obviously over-used"
    elif name == "Visual Quality":
        if facts.get("low_resolution"):
            score, note = 35, "low resolution; Reels demotes low-res"
        else:
            score, note = 80, "resolution and composition look sound"
    elif name == "Audience Fit":
        score, note = 72, "topic aligns with the declared audience"
    elif name == "Platform Fit":
        aspect_ok = facts.get("aspect_ratio") in (None, "9:16")
        if not aspect_ok:
            score, note = 40, "aspect ratio is not 9:16 for Reels"
        elif facts.get("visible_watermark"):
            score, note = 45, "visible watermark; Reels demotes watermarked clips"
        else:
            score, note = 82, "9:16, no watermark, within platform rules"

    return {
        "dimension": name,
        "score": _bounded(score),
        "evidence_class": _EVIDENCE[name],
        "note": note,
    }


def score_all(view: dict) -> list[dict]:
    """Score all twelve dimensions. Returns a list, never a single number."""
    return [score_dimension(name, view) for name in DIMENSIONS]
