"""Instagram Reels platform pack - ASUR's locked v1 default surface.

This pack reproduces EXACTLY the numbers currently hard-coded across the engine
(generation/hero_proof.py TARGET_WIDTH/HEIGHT, generation/final_qa.py
_REEL_WIDTH/HEIGHT + 60s default, learning/publish_package.py _DEFAULT_PLATFORM
+ metadata.aspect_ratio). P09a is behaviour-neutral: routing Instagram through
this pack must not change a single artifact byte, which is why these literals
match the existing code 1:1.

Platform facts are documented public signals (ASUR-HONEST-01), each evidence-
classed and sourced; never a predicted outcome, never a "% viral" number.
"""

from __future__ import annotations

from .base import FormatSpec, PlatformPack

PACK = PlatformPack(
    platform_id="instagram_reels",
    format_spec=FormatSpec(
        aspect_ratio="9:16",
        width=1080,
        height=1920,
        fps=30,
        default_duration_s=60.0,
        # No hard band today (SPEC-GAP G16: 60s stays band-free unless a brief
        # declares a target). Keeping None preserves current behaviour exactly.
        duration_band_s=None,
        safe_area={"top": 0.12, "bottom": 0.12, "left": 0.0, "right": 0.0},
    ),
    publish_platform_id="instagram_reels",
    publish_fields=("title", "caption", "hashtags", "cta", "thumbnail"),
    _facts=(
        {
            "signal": "first_3s_retention",
            "evidence_class": "STRONG",
            "source": "Instagram Creators / public retention guidance",
            "as_of": "2025",
            "note": "the opening hook disproportionately drives watch-through",
        },
        {
            "signal": "watch_through_and_replays",
            "evidence_class": "STRONG",
            "source": "Meta public creator docs",
            "as_of": "2025",
            "note": "completion and loops are documented Reels distribution inputs",
        },
        {
            "signal": "shares_and_saves",
            "evidence_class": "EMPIRICAL",
            "source": "widely reported creator A/B observation",
            "as_of": "2025",
            "note": "sends/saves correlate with reach; not a guaranteed algorithm fact",
        },
        {
            "signal": "original_audio_and_trends",
            "evidence_class": "HYPOTHESIS",
            "source": "creator-ecosystem observation",
            "as_of": "2025",
            "note": "trend/audio participation may aid surfacing; unverified",
        },
    ),
)
