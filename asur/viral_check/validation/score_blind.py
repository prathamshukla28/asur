"""Blind scoring pass for the validation study (SPEC-GAP G30).

Scores every clip in a study directory using the REAL viral-check instrument,
with the observed view counts kept SEALED. The hard invariant enforced here
and tested in ``tests/test_viral_validation_v1a.py`` is that this module never
opens ``views.sealed.json`` - scoring must be blind to the outcome it will
later be correlated against.

Stdlib-only (ASUR-LOCAL-01 / boundary): the only ASUR imports are the stdlib
viral-check instrument and projection; observable facts arrive already derived.
"""

from __future__ import annotations

import json
from pathlib import Path

from ...tools.projection import build_viral_view
from ..evaluate import build_viral_check
from .derive import derive_platform_facts

# The sealed outcome file. This module must NEVER read it (blind scoring).
SEALED_VIEWS = "views.sealed.json"

_PLACEHOLDER_HASH = "sha256:" + "0" * 64


def score_one(clip_id: str, platform_facts: dict) -> dict:
    """Score one clip's observable platform_facts into a viral_check body.

    Feeds the facts through ``build_viral_view`` first, so any leaked
    quality/hardness target name fails closed with FirewallLeak
    (ASUR-FIREWALL-01). Returns the viral_check artifact body: twelve
    per-dimension scores, binary risk flags, weak dimensions, and the
    PASS/PASS-WITH-CHANGES/REJECT verdict - with no aggregate score.
    """
    view = build_viral_view(
        bundle_hashes={"final.mp4": _PLACEHOLDER_HASH},
        provenance={"renderer": "FFmpeg", "render_cost_usd": 0},
        platform_facts=platform_facts,
        rubric_metadata={"lane": "viral-check", "binding": clip_id},
    )
    artifact = build_viral_check(view, project_id=clip_id)
    return artifact.body


def score_study(study_dir: str | Path) -> dict:
    """Score every clip in ``study_dir`` blind; write ``scores/<clip>.json``.

    Reads ``clip_meta.json`` (each clip carries a ``pre_derived`` probe block)
    and ``ratings/<clip_id>.json`` (the blind rater's judgments), derives the
    observable facts, scores them, and persists one score file per clip.
    Returns {clip_id: body} for convenience. NEVER reads the sealed views.
    """
    root = Path(study_dir)
    meta = json.loads((root / "clip_meta.json").read_text(encoding="utf-8"))
    clips = meta.get("clips") or []

    scores_dir = root / "scores"
    scores_dir.mkdir(parents=True, exist_ok=True)

    results: dict = {}
    for clip in clips:
        clip_id = str(clip["clip_id"])
        probe = clip.get("pre_derived") or {}
        ratings = _load_ratings(root, clip_id)
        facts = derive_platform_facts(
            f"{clip_id}.mp4", ratings=ratings, probe=probe
        )
        body = score_one(clip_id, facts)
        results[clip_id] = body
        (scores_dir / f"{clip_id}.json").write_text(
            json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return results


def _load_ratings(root: Path, clip_id: str) -> dict:
    """Load the blind rater's judgments for one clip, if any were recorded."""
    path = root / "ratings" / f"{clip_id}.json"
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    judgments = payload.get("judgments")
    return judgments if isinstance(judgments, dict) else {}
