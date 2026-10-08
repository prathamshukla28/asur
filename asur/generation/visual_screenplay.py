"""Stage 11 - visual screenplay (local, explainable, stdlib-only).

Takes the ``creative_direction`` and ``script`` artifacts and produces a
``visual_screenplay`` artifact: one scene per script section, each carrying
the semantic visual blueprint the GENERATION layer later renders. No network
(ASUR-LOCAL-01), no media imports.

Every scene says what it MEANS before it says what it shows (semantic visual
design, DATA_MODELS.md) - no generic B-roll, no random zooms. Each scene
records a generation_method so the asset strategy can plan sources.
"""

from __future__ import annotations

from typing import Any

from ..core.envelope import Artifact, make_artifact
from ..core.identity import Identity
from . import source_ref

# Script section order the screenplay walks (matches script_builder SECTION_ORDER).
_SECTION_ORDER = (
    "hook",
    "opening",
    "problem",
    "context",
    "story",
    "value",
    "proof",
    "payoff",
    "cta",
)


def _parse_timing(timing: str) -> tuple[float, float]:
    """Parse '0.0-3.0s' -> (0.0, 3.0). Fail soft to (0.0, 0.0)."""
    try:
        cleaned = timing.replace("s", "").strip()
        start_s, end_s = cleaned.split("-", 1)
        return (float(start_s), float(end_s))
    except (ValueError, AttributeError):
        return (0.0, 0.0)


def _intensity_for(section: str) -> str:
    if section in ("hook", "payoff"):
        return "high"
    if section in ("problem", "cta"):
        return "medium"
    return "low"


def build_visual_screenplay(
    creative_direction_artifact: Artifact,
    script_artifact: Artifact,
    project_id: str,
    *,
    identity: Identity | None = None,
) -> Artifact:
    """Produce a ``visual_screenplay`` artifact from creative_direction + script."""
    cd_body = creative_direction_artifact.body or {}
    subject = cd_body.get("subject", "the topic")
    language = cd_body.get("language", "en")

    sections = (script_artifact.body or {}).get("sections") or {}

    scenes: list[dict[str, Any]] = []
    for index, name in enumerate(_SECTION_ORDER, start=1):
        sec = sections.get(name) or {}
        start, end = _parse_timing(sec.get("timing", "0.0-0.0s"))
        spoken = sec.get("spoken_words", "")
        onscreen = sec.get("onscreen_text", "")
        # Hero words = the on-screen text if present, else first few spoken words.
        if onscreen:
            hero_words = [w for w in onscreen.split() if w]
        else:
            hero_words = spoken.split()[:3]

        scenes.append(
            {
                "scene_id": f"scene-{index:02d}-{name}",
                "section": name,
                "start": start,
                "end": end,
                "spoken_content": spoken,
                "meaning": f"what the viewer should understand in the '{name}' beat",
                "hero_words": hero_words,
                "visual_concept": sec.get(
                    "visual_direction", "clean subject-forward frame"
                ),
                "semantic_metaphor": (
                    f"a concrete image that stands for the '{name}' idea about {subject}"
                ),
                "composition": "center-weighted, safe margins for Reels UI",
                "typography": {
                    "style": "bold sans (en) / shaped Devanagari (hi/hinglish/mr)",
                    "language": language,
                    "emphasis": hero_words,
                },
                "camera": {"move": "locked or slow push", "reason": "motion serves meaning"},
                "background": {
                    "value": sec.get("broll_requirements", "minimal, non-distracting"),
                },
                "graphics": {"onscreen_text": onscreen},
                "motion": {
                    "value": sec.get("transition_requirements", "cut on emphasis"),
                },
                "transition": sec.get("transition_requirements", "cut"),
                "intensity": _intensity_for(name),
                "audio_direction": sec.get("audio_direction", "steady bed"),
                # Default: assets are AI-image backgrounds + on-screen text + voice.
                # Exact source strategy per asset is decided in asset_strategy.
                "assets": [f"{name}-background", f"{name}-onscreen-text"],
                "generation_method": "ai_image" if name != "story" else "user_original",
            }
        )

    body: dict[str, Any] = {
        "subject": subject,
        "language": language,
        "scene_count": len(scenes),
        "scenes": scenes,
        "method": (
            "local heuristic: one scene per script section; semantic-first; "
            "no network, no model"
        ),
    }

    return make_artifact(
        kind="visual_screenplay",
        project_id=project_id,
        body=body,
        status="ready",
        sources=[
            source_ref(creative_direction_artifact),
            source_ref(script_artifact),
        ],
        agent="visual",
        identity=identity,
    )
