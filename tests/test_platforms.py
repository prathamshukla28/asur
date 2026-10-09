"""P09a - platform registry + packs (tests first).

ASUR's frozen v1 target is an Instagram Reel (9:16). YouTube (SPEC-GAP G19) is a
NEW output surface added as an *additive, opt-in platform pack* - the engine is
not forked. This phase (P09a) is deliberately behaviour-neutral: it introduces a
`platforms` package (FormatSpec + PlatformPack + a fail-closed registry) and the
Instagram pack reproduces exactly today's 9:16 / 1080x1920 / 60s-default numbers,
plus the two YouTube packs. No `generation/` or `publish_package` rewiring here
(that is P09b/P09c), so the existing 223 tests must stay byte-identical.

Every pack carries only documented, data-first facts (ASUR-HONEST-01): no private
algorithm claims, no "% viral" anything. Platform facts used by VIRAL CHECK are
each evidence-classed with a source. An unknown platform fails closed
(ASUR-GATE-01) - never a silent default.
"""

from __future__ import annotations

import pytest

from asur.platforms import (
    PLATFORM_REGISTRY,
    UnknownPlatform,
    get_platform,
)
from asur.platforms.base import FormatSpec, PlatformPack

# Evidence classes allowed on a platform fact (mirror VIRAL_CHECK's four).
_EVIDENCE_CLASSES = {"VERIFIED", "STRONG", "EMPIRICAL", "HYPOTHESIS"}

# "% viral" / single-number virality must never appear anywhere in a pack
# (ASUR-HONEST-01). We grep every string the pack serialises.
_FORBIDDEN_SUBSTRINGS = ("% viral", "%viral", "viral score", "viral_percentage")


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #

def test_registry_has_the_three_launch_platforms() -> None:
    assert set(PLATFORM_REGISTRY) == {
        "instagram_reels",
        "youtube_shorts",
        "youtube_long",
    }


def test_get_platform_returns_the_pack() -> None:
    pack = get_platform("instagram_reels")
    assert isinstance(pack, PlatformPack)
    assert pack.platform_id == "instagram_reels"


def test_instagram_is_the_default_platform() -> None:
    # The locked v1 default is Instagram Reels (MVP.md section 1/7).
    from asur.platforms import DEFAULT_PLATFORM

    assert DEFAULT_PLATFORM == "instagram_reels"
    assert get_platform() is get_platform("instagram_reels")


def test_unknown_platform_fails_closed() -> None:
    # ASUR-GATE-01: an unknown surface is never silently defaulted; it raises
    # (mirrors dispatch.py's DispatchError pattern) and names the bad value.
    with pytest.raises(UnknownPlatform) as exc:
        get_platform("tiktok")
    assert "tiktok" in str(exc.value)


# --------------------------------------------------------------------------- #
# Instagram pack must reproduce today's hard-coded numbers EXACTLY (G19 default,
# behaviour-neutral refactor). These literals are the ones currently in
# generation/hero_proof.py, generation/final_qa.py, learning/publish_package.py.
# --------------------------------------------------------------------------- #

def test_instagram_format_matches_current_hardcoded_reel_spec() -> None:
    fmt = get_platform("instagram_reels").format_spec
    assert isinstance(fmt, FormatSpec)
    assert fmt.aspect_ratio == "9:16"
    assert fmt.width == 1080
    assert fmt.height == 1920
    assert fmt.fps == 30
    # Today's platform-neutral default is 60s with no hard band (G16).
    assert fmt.default_duration_s == 60.0
    assert fmt.duration_band_s is None


def test_instagram_publish_platform_id_is_unchanged() -> None:
    # learning/publish_package.py uses _DEFAULT_PLATFORM = "instagram_reels"
    # and metadata.aspect_ratio = "9:16"; the pack must agree so P09b's rewire
    # is a no-op for Instagram.
    pack = get_platform("instagram_reels")
    assert pack.publish_platform_id == "instagram_reels"
    assert pack.format_spec.aspect_ratio == "9:16"


# --------------------------------------------------------------------------- #
# YouTube Shorts (9:16, <= 60s)
# --------------------------------------------------------------------------- #

def test_youtube_shorts_is_vertical_and_capped_at_60s() -> None:
    fmt = get_platform("youtube_shorts").format_spec
    assert fmt.aspect_ratio == "9:16"
    assert fmt.width == 1080
    assert fmt.height == 1920
    assert fmt.duration_band_s is not None
    low, high = fmt.duration_band_s
    assert low >= 0
    assert high <= 60.0  # Shorts hard ceiling is 60s


# --------------------------------------------------------------------------- #
# YouTube long-form (16:9)
# --------------------------------------------------------------------------- #

def test_youtube_long_is_widescreen_1080p() -> None:
    fmt = get_platform("youtube_long").format_spec
    assert fmt.aspect_ratio == "16:9"
    assert fmt.width == 1920
    assert fmt.height == 1080
    # Long-form carries a target band, not a hard overwrite (G16 pattern).
    assert fmt.duration_band_s is not None
    low, high = fmt.duration_band_s
    assert high > low > 0


def test_youtube_long_publish_fields_cover_title_description_tags_chapters() -> None:
    pack = get_platform("youtube_long")
    assert "title" in pack.publish_fields
    assert "description" in pack.publish_fields
    assert "tags" in pack.publish_fields
    assert "chapters" in pack.publish_fields


# --------------------------------------------------------------------------- #
# Platform facts: documented, evidence-classed, sourced - and NO "% viral".
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("platform_id", sorted({"instagram_reels", "youtube_shorts", "youtube_long"}))
def test_platform_facts_are_evidence_classed_and_sourced(platform_id: str) -> None:
    facts = get_platform(platform_id).platform_facts()
    assert isinstance(facts, dict)
    signals = facts.get("signals")
    assert isinstance(signals, list) and signals, "every pack declares >=1 signal"
    for sig in signals:
        assert sig.get("evidence_class") in _EVIDENCE_CLASSES
        assert sig.get("source"), "ASUR-EXPLAIN-01: every fact cites a source"
        assert sig.get("as_of"), "every fact is dated"
        assert sig.get("signal"), "every fact names the signal"


@pytest.mark.parametrize("platform_id", sorted({"instagram_reels", "youtube_shorts", "youtube_long"}))
def test_no_pack_contains_a_viral_percentage(platform_id: str) -> None:
    # ASUR-HONEST-01: a pack must never smuggle in a "% viral" style claim.
    pack = get_platform(platform_id)
    blob = repr(pack.format_spec) + repr(pack.platform_facts()) + repr(pack.publish_fields)
    low = blob.casefold()
    for bad in _FORBIDDEN_SUBSTRINGS:
        assert bad not in low, f"{platform_id} pack contains forbidden '{bad}'"


@pytest.mark.parametrize("platform_id", sorted({"instagram_reels", "youtube_shorts", "youtube_long"}))
def test_platform_facts_carry_no_quality_or_hardness_targets(platform_id: str) -> None:
    # Firewall pre-check: platform_facts feed VIRAL_VIEW, so they must already be
    # free of the VIRAL_FORBIDDEN names (projection.conformance_scan would fail
    # closed on them later - we assert it up front).
    from asur.tools.projection import VIRAL_FORBIDDEN, conformance_scan

    facts = get_platform(platform_id).platform_facts()
    # Should not raise FirewallLeak.
    conformance_scan({"platform_facts": facts}, VIRAL_FORBIDDEN)


def test_platform_facts_feed_a_valid_viral_view() -> None:
    # End-to-end firewall check: a YouTube pack's facts slot into build_viral_view
    # without leaking a forbidden target (ASUR-FIREWALL-01).
    from asur.tools.projection import build_viral_view

    view = build_viral_view(
        bundle_hashes={"video": "deadbeef"},
        provenance={"assets": []},
        platform_facts=get_platform("youtube_long").platform_facts(),
        rubric_metadata={"lane": "viral_check"},
    )
    assert view["view"] == "VIRAL_VIEW"
    assert view["platform_facts"]["signals"]
