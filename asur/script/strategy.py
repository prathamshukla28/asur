"""Stage 4 - strategy (local heuristic, explainable).

Takes the ``idea`` and ``audience`` artifacts and produces a ``strategy``
artifact: the single decision about how this video will win. No network
(ASUR-LOCAL-01). Every field is explainable (ASUR-EXPLAIN-01) and the platform
is locked to Instagram Reels per the user's locked decision.

Strategy is the contract the rest of Phase 1 obeys: one objective, one core
promise, one narrative shape, one call to action. Downstream hook and script
stages read this so they optimize toward the same target.
"""

from __future__ import annotations

from ..core.envelope import Artifact, make_artifact
from ..core.identity import Identity
from . import source_ref

DEFAULT_PLATFORM = "instagram_reels"


def _subject(idea_artifact: Artifact) -> str:
    body = idea_artifact.body or {}
    understanding = body.get("understanding") or {}
    problem = understanding.get("problem") or {}
    return problem.get("value") or body.get("one_line", "the topic")


def _idea_field(idea_artifact: Artifact, name: str, default: str) -> str:
    understanding = (idea_artifact.body or {}).get("understanding") or {}
    field = understanding.get(name) or {}
    return field.get("value") or default


def build_strategy(
    idea_artifact: Artifact,
    audience_artifact: Artifact,
    project_id: str,
    *,
    identity: Identity | None = None,
) -> Artifact:
    """Produce a ``strategy`` artifact from ``idea`` + ``audience``."""
    subject = _subject(idea_artifact)
    emotion = _idea_field(idea_artifact, "emotion", "curiosity")
    action = _idea_field(idea_artifact, "action", "save")
    language = (idea_artifact.body or {}).get("language", "en")

    awareness = (audience_artifact.body or {}).get("awareness_level") or {}
    awareness_value = awareness.get("value", "problem-aware")

    body = {
        "objective": {
            "value": f"Make the viewer understand {subject} and want to {action} it.",
            "how_derived": "idea's desired action + subject",
        },
        "audience_summary": {
            "value": f"Time-pressed, {awareness_value} short-form viewers interested "
            f"in {subject}.",
            "how_derived": "condensed from the audience artifact",
        },
        "format": {
            "value": "vertical 9:16 short, single clear idea",
            "how_derived": "locked platform decision (Instagram Reels first)",
        },
        "platform": DEFAULT_PLATFORM,
        "emotion": {
            "value": emotion,
            "how_derived": "carried from the idea's dominant emotion cue",
        },
        "core_promise": {
            "value": f"In under a minute, you'll get the one thing about {subject} "
            "that actually matters.",
            "how_derived": "single-promise rule for short-form retention",
        },
        "value_prop": {
            "value": f"A clear, honest, quick take on {subject} you can act on.",
            "how_derived": "audience desires (clarity + usefulness + trust)",
        },
        "narrative_structure": {
            "value": "hook -> problem -> context -> story -> value -> proof -> "
            "payoff -> cta",
            "how_derived": "standard high-retention short-form arc",
        },
        "cta": {
            "value": f"Invite the viewer to {action}.",
            "how_derived": "idea's desired action",
        },
        "success_metric": {
            "value": "watch-through and sends/saves, not raw views",
            "how_derived": "platform signals favor watch time + sends (ASUR-HONEST-01)",
        },
        "language": language,
    }

    return make_artifact(
        kind="strategy",
        project_id=project_id,
        body=body,
        status="ready",
        sources=[source_ref(idea_artifact), source_ref(audience_artifact)],
        agent="strategy",
        identity=identity,
    )
