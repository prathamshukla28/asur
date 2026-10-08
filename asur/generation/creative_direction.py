"""Stage 8 - creative direction (local, explainable, stdlib-only).

Takes the ``strategy`` and ``script`` artifacts and produces a
``creative_direction`` artifact: the visual, emotional, and motion language
that every later generation decision must stay consistent with. No network
(ASUR-LOCAL-01), no media imports (ASUR-GENERATION reads only control data).

This is pure control logic: it decides *how the video should feel and look*,
not how to run a model. Every field records how it was derived
(ASUR-EXPLAIN-01).
"""

from __future__ import annotations

from typing import Any

from ..core.envelope import Artifact, make_artifact
from ..core.identity import Identity
from . import source_ref


def _script_val(script_artifact: Artifact, section: str, field: str, default: str) -> str:
    sections = (script_artifact.body or {}).get("sections") or {}
    sec = sections.get(section) or {}
    if isinstance(sec, dict):
        return sec.get(field) or default
    return default


def _strategy_val(strategy_artifact: Artifact, name: str, default: str) -> str:
    field = (strategy_artifact.body or {}).get(name) or {}
    if isinstance(field, dict):
        return field.get("value") or default
    if isinstance(field, str):
        return field or default
    return default


def build_creative_direction(
    strategy_artifact: Artifact,
    script_artifact: Artifact,
    project_id: str,
    *,
    identity: Identity | None = None,
) -> Artifact:
    """Produce a ``creative_direction`` artifact from ``strategy`` + ``script``."""
    subject = (script_artifact.body or {}).get("subject", "the topic")
    language = (script_artifact.body or {}).get("language", "en")
    emotion = _strategy_val(strategy_artifact, "emotion", "curiosity")
    hook_emotion = _script_val(script_artifact, "hook", "emotion", emotion)

    visual_language = {
        "color": {
            "value": "high-contrast, one accent color on a restrained base",
            "how_derived": "9:16 mobile legibility; accent draws the eye to hero words",
        },
        "composition": {
            "value": "center-weighted subject with safe margins for Reels UI",
            "how_derived": "platform-fit: avoid text under the caption/CTA overlay zones",
        },
        "texture": {
            "value": "clean, minimal grain; no busy backgrounds behind text",
            "how_derived": "keep attention on hero words and the speaker",
        },
        "lighting": {
            "value": "bright, even key light; subject clearly separated from background",
            "how_derived": "IG demotes low-quality/dim footage (platform signal)",
        },
        "typography": {
            "value": "bold sans for English; shaped Devanagari for hi/hinglish/mr",
            "how_derived": f"language={language}; captions must render correctly per script",
        },
        "framing": {
            "value": "tight on the subject; headroom trimmed for vertical",
            "how_derived": "vertical 9:16 rewards tight framing over wide shots",
        },
        "camera": {
            "value": "mostly locked or slow push; motion serves meaning, not decoration",
            "how_derived": "avoid random zooms (semantic visual design, DATA_MODELS.md)",
        },
    }

    emotional_language = {
        "arc": {
            "value": f"{hook_emotion} -> concern -> curiosity -> empathy -> payoff",
            "how_derived": "mirrors the script's section emotions in order",
        },
        "dominant": {
            "value": hook_emotion,
            "how_derived": "anchored to the selected hook's emotion",
        },
        "tone": {
            "value": "honest and direct; no manufactured hype (ASUR-HONEST-01 spirit)",
            "how_derived": "authenticity scores higher than clickbait over time",
        },
    }

    motion_language = {
        "pace": {
            "value": "fast on the hook, steady through the body, deliberate on the payoff",
            "how_derived": "first 3s must stop the scroll; payoff needs room to land",
        },
        "style": {
            "value": "sharp cuts on emphasis words; smooth transitions between ideas",
            "how_derived": "cut-on-beat and word-punch serve the story, not spectacle",
        },
        "intensity": {
            "value": "peaks at the hook and the payoff, calm in the middle",
            "how_derived": "a single rising line keeps retention without exhausting",
        },
    }

    recurring_motifs = [
        {
            "motif": "hero-word on-screen text",
            "how_derived": "the one word that carries each beat gets visual weight",
        },
        {
            "motif": "accent-color underline on the promise",
            "how_derived": "ties every section back to the core promise visually",
        },
    ]

    body: dict[str, Any] = {
        "subject": subject,
        "language": language,
        "visual_language": visual_language,
        "emotional_language": emotional_language,
        "motion_language": motion_language,
        "recurring_motifs": recurring_motifs,
        "method": "local heuristic derived from strategy + script; no network, no model",
    }

    return make_artifact(
        kind="creative_direction",
        project_id=project_id,
        body=body,
        status="ready",
        sources=[source_ref(strategy_artifact), source_ref(script_artifact)],
        agent="visual",
        identity=identity,
    )
