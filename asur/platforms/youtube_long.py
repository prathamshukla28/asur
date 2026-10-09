"""YouTube long-form platform pack - 16:9 widescreen (SPEC-GAP G19).

The genuinely new surface: 1920x1080 landscape, minutes not seconds, and a
publish package that carries title + description + tags + timestamped chapters +
end-screen/cards plan. Long-form retention behaves differently from a vertical
clip (browse/suggested/search traffic, CTR x average-view-duration interplay,
the first-30s cliff, per-chapter retention).

Platform facts are documented public signals only (ASUR-HONEST-01), each
evidence-classed and sourced; never a predicted outcome, never a "% viral"
number. No private-algorithm claims.
"""

from __future__ import annotations

from .base import FormatSpec, PlatformPack

PACK = PlatformPack(
    platform_id="youtube_long",
    format_spec=FormatSpec(
        aspect_ratio="16:9",
        width=1920,
        height=1080,
        fps=30,
        default_duration_s=480.0,  # 8 min - a common mid-length default
        # Target band (G16 pattern): outside => QA warning, never a hard fail.
        duration_band_s=(180.0, 1200.0),  # 3-20 min
        # Dodge the bottom progress bar + the last-~20s end-screen zone is a
        # temporal concern handled in editing; spatial chrome is light here.
        safe_area={"top": 0.05, "bottom": 0.10, "left": 0.05, "right": 0.05},
    ),
    publish_platform_id="youtube_long",
    publish_fields=(
        "title",
        "description",
        "tags",
        "chapters",
        "thumbnail",
        "category",
        "end_screen",
        "cards",
    ),
    _facts=(
        {
            "signal": "ctr_x_average_view_duration",
            "evidence_class": "STRONG",
            "source": "YouTube Creators public documentation",
            "as_of": "2025",
            "note": "CTR and AVD interact; a high CTR with low AVD is self-limiting",
        },
        {
            "signal": "first_30s_retention_cliff",
            "evidence_class": "STRONG",
            "source": "YouTube Studio retention-curve guidance",
            "as_of": "2025",
            "note": "the opening is where most long-form drop-off happens",
        },
        {
            "signal": "browse_suggested_search_mix",
            "evidence_class": "EMPIRICAL",
            "source": "YouTube Studio traffic-source analytics (public feature)",
            "as_of": "2025",
            "note": "traffic-source mix shapes which videos surface where",
        },
        {
            "signal": "chapter_segment_retention",
            "evidence_class": "EMPIRICAL",
            "source": "Studio per-moment retention (public feature)",
            "as_of": "2025",
            "note": "weak segments can be identified and recut per chapter",
        },
        {
            "signal": "end_screen_and_card_clicks",
            "evidence_class": "EMPIRICAL",
            "source": "YouTube Studio end-screen/card reporting",
            "as_of": "2025",
            "note": "session continuation via end-screens is a measurable input",
        },
    ),
)
