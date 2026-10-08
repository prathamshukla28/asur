"""P07 VIRAL CHECK tests.

Covers: twelve individual dimensions (never a single %viral), the
PASS / PASS-WITH-CHANGES / REJECT verdict, binary risk flags, and the
firewall rule that VIRAL CHECK reads only the VIRAL_VIEW and fails
closed if a quality/hardness target leaks through.
"""

from __future__ import annotations

import pytest

from asur.core.envelope import verify_checksum
from asur.script.evidence import EVIDENCE_CLASSES
from asur.tools.projection import FirewallLeak, build_viral_view
from asur.viral_check.dimensions import DIMENSIONS, score_all
from asur.viral_check.evaluate import (
    PASS,
    PASS_WITH_CHANGES,
    REJECT,
    build_viral_check,
    decide_verdict,
    risk_flags,
)

PROJECT_ID = "test-viral-check"

_VERDICTS = {PASS, PASS_WITH_CHANGES, REJECT}

# Banned aggregate-score names. ASUR-HONEST-01: a viral_check body must
# never carry a single rolled-up "how viral" number.
_FORBIDDEN_AGGREGATE_KEYS = (
    "viral_score",
    "overall_score",
    "overall",
    "aggregate_score",
    "percent_viral",
    "viral_percent",
    "total_score",
    "final_score",
)


def _view(**platform_facts) -> dict:
    """A clean VIRAL_VIEW with the given platform_facts overlaid."""
    return build_viral_view(
        bundle_hashes={"final.mp4": "sha256:abc123"},
        provenance={"renderer": "FFmpeg", "render_cost_usd": 0},
        platform_facts=dict(platform_facts),
        rubric_metadata={"lane": "viral-check", "binding": "run-1"},
    )


def test_twelve_dimensions_exactly():
    """ASUR-HONEST-01: exactly twelve named scoring dimensions."""
    assert len(DIMENSIONS) == 12
    assert DIMENSIONS[0] == "Attention"
    assert DIMENSIONS[-1] == "Platform Fit"
    assert len(set(DIMENSIONS)) == 12


def test_every_dimension_scored_0_to_100():
    """ASUR-HONEST-01: each dimension is an int 0-100, reported on its own."""
    scored = score_all(_view())
    assert len(scored) == 12
    for entry in scored:
        assert entry["dimension"] in DIMENSIONS
        assert isinstance(entry["score"], int)
        assert 0 <= entry["score"] <= 100
        assert entry["evidence_class"] in EVIDENCE_CLASSES
        assert entry["note"]


def test_scoring_is_deterministic():
    """ASUR-EXPLAIN-01: same view yields identical scores (no randomness)."""
    assert score_all(_view(low_resolution=True)) == score_all(_view(low_resolution=True))


def test_verdict_is_from_the_closed_set():
    """ASUR-HONEST-01: verdict is PASS / PASS-WITH-CHANGES / REJECT only."""
    art = build_viral_check(_view(), PROJECT_ID)
    assert art.body["verdict"] in _VERDICTS


def test_clean_bundle_can_pass():
    """A clean, well-formed bundle reaches PASS."""
    view = _view(
        strong_first_three_seconds=True,
        captions_present=True,
        delivers_promise=True,
        aspect_ratio="9:16",
    )
    art = build_viral_check(view, PROJECT_ID)
    assert art.body["verdict"] == PASS
    assert art.body["risk_flags"] == []


def test_watermark_never_passes():
    """ASUR-HONEST-01 rule 3: a hard risk flag blocks a PASS (binary)."""
    art = build_viral_check(_view(visible_watermark=True), PROJECT_ID)
    assert art.body["verdict"] != PASS
    assert any(f["hard"] for f in art.body["risk_flags"])


def test_hard_risk_rejects():
    """A reach-breaking defect (reposted content) yields REJECT."""
    assert decide_verdict(score_all(_view(reposted_elsewhere=True)),
                          risk_flags(_view(reposted_elsewhere=True))) == REJECT


def test_soft_risk_is_pass_with_changes():
    """A soft risk flag (muted) yields PASS-WITH-CHANGES, not REJECT/PASS."""
    art = build_viral_check(_view(muted=True), PROJECT_ID)
    assert art.body["verdict"] == PASS_WITH_CHANGES


def test_risk_flags_are_strings_not_percentages():
    """ASUR-HONEST-01 rule 3: flags are messages, never % deductions."""
    flags = risk_flags(_view(visible_watermark=True, low_resolution=True))
    assert flags
    for f in flags:
        assert isinstance(f["flag"], str)
        assert "%" not in f["flag"]
        assert isinstance(f["hard"], bool)


def test_no_single_viral_percentage_anywhere():
    """ASUR-HONEST-01: the artifact body carries NO aggregate viral number."""
    art = build_viral_check(_view(strong_first_three_seconds=True), PROJECT_ID)
    body = art.body

    def _walk_keys(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                yield k
                yield from _walk_keys(v)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                yield from _walk_keys(item)

    keys = {k.casefold() for k in _walk_keys(body)}
    for banned in _FORBIDDEN_AGGREGATE_KEYS:
        assert banned not in keys, f"forbidden aggregate key leaked: {banned}"
    # The only numeric scores allowed are the twelve per-dimension ones.
    numeric = [d["score"] for d in body["dimensions"]]
    assert len(numeric) == 12


def test_reads_viral_view_shape():
    """ASUR-FIREWALL-01: evaluator consumes the VIRAL_VIEW projection."""
    view = _view()
    assert view["view"] == "VIRAL_VIEW"
    art = build_viral_check(view, PROJECT_ID)
    assert art.kind == "viral_check"
    assert verify_checksum(art)


def test_fails_closed_on_leaked_quality_target():
    """ASUR-FIREWALL-01: a leaked quality/hardness target fails closed.

    The leak is caught at projection time by conformance_scan, so the
    VIRAL_VIEW can never even be built with a forbidden target name.
    """
    with pytest.raises(FirewallLeak):
        build_viral_view(
            bundle_hashes={"final.mp4": "sha256:abc"},
            provenance={"renderer": "FFmpeg"},
            platform_facts={"target_score": 90},
            rubric_metadata={"lane": "viral-check"},
        )


def test_evidence_classes_are_all_known():
    """ASUR-HONEST-01: every dimension cites a real evidence class."""
    for entry in score_all(_view()):
        assert entry["evidence_class"] in EVIDENCE_CLASSES


def test_lineage_is_recorded():
    """ASUR-PROV-01: viral_check records its source artifacts."""
    from asur.core.envelope import make_artifact

    upstream = make_artifact(kind="edit_plan", project_id=PROJECT_ID,
                             body={"subject": "x"}, status="ready")
    art = build_viral_check(_view(), PROJECT_ID, source_artifacts=[upstream])
    refs = [s["artifact_id"] for s in art.sources]
    assert upstream.artifact_id in refs
