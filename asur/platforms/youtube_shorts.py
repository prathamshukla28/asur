"""YouTube Shorts platform pack - 9:16 vertical, <=60s (SPEC-GAP G19).

Closest surface to Instagram Reels: same 1080x1920 frame, so P09b can reuse the
existing 9:16 render path. Difference is the hard 60s ceiling (a real target
band) and Shorts-specific documented signals.

Platform facts are documented public signals only (ASUR-HONEST-01), each
evidence-classed and sourced; never a predicted outcome, never a "% viral"
number. No private-algorithm claims.
"""

from __future__ import annotations

from .base import FormatSpec, PlatformPack

PACK = PlatformPack(
    platform_id="youtube_shorts",
    format_spec=FormatSpec(
        aspect_ratio="9:16",
        width=1080,
        height=1920,
        fps=30,
        default_duration_s=45.0,
        # Shorts hard ceiling is 60s; target band carried, not a hard overwrite.
        duration_band_s=(15.0, 60.0),
        # Dodge the right-hand action rail + bottom title chrome.
        safe_area={"top": 0.10, "bottom": 0.15, "left": 0.0, "right": 0.12},
    ),
    publish_platform_id="youtube_shorts",
    publish_fields=("title", "description", "hashtags", "thumbnail"),
    _facts=(
        {
            "signal": "swipe_away_first_1_3s",
            "evidence_class": "STRONG",
            "source": "YouTube Creators public Shorts guidance",
            "as_of": "2025",
            "note": "early swipe-away is a documented Shorts retention signal",
        },
        {
            "signal": "loop_and_replay",
            "evidence_class": "EMPIRICAL",
            "source": "widely reported Shorts creator observation",
            "as_of": "2025",
            "note": "loopable structure correlates with Shorts-shelf surfacing",
        },
        {
            "signal": "shorts_shelf_surfacing",
            "evidence_class": "HYPOTHESIS",
            "source": "creator-ecosystem observation",
            "as_of": "2025",
            "note": "surfacing mechanics are not publicly specified; unverified",
        },
        {
            "signal": "hook_to_payoff_timing",
            "evidence_class": "STRONG",
            "source": "YouTube Creators retention guidance",
            "as_of": "2025",
            "note": "a fast, delivered promise sustains the very short watch window",
        },
    ),
)
