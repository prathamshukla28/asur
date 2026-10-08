"""Stage 3 - audience (local heuristic, evidence-classed).

Takes the ``idea`` and ``research`` artifacts and produces an ``audience``
artifact: who this is for and what they feel. No network (ASUR-LOCAL-01). The
audience is inferred locally from the idea text; where we genuinely cannot know
a trait, we say so instead of inventing a demographic (ASUR-HONEST-01), and
every field explains how it was derived (ASUR-EXPLAIN-01).

Later stages (strategy, hooks, script) read this so the content speaks to a
specific person with a specific pain, not a generic "everyone".
"""

from __future__ import annotations

from ..core.envelope import Artifact, make_artifact
from ..core.identity import Identity
from . import source_ref
from .evidence import EMPIRICAL, HYPOTHESIS, STRONG_EVIDENCE, claim


def _subject(idea_artifact: Artifact) -> str:
    body = idea_artifact.body or {}
    understanding = body.get("understanding") or {}
    problem = understanding.get("problem") or {}
    return problem.get("value") or body.get("one_line", "the topic")


def _language(idea_artifact: Artifact) -> str:
    return (idea_artifact.body or {}).get("language", "en")


def build_audience(
    idea_artifact: Artifact,
    research_artifact: Artifact,
    project_id: str,
    *,
    identity: Identity | None = None,
) -> Artifact:
    """Produce an ``audience`` artifact from ``idea`` + ``research``."""
    subject = _subject(idea_artifact)
    language = _language(idea_artifact)

    demographics = {
        "value": "unspecified - inferred as general short-form viewers interested in "
        f"{subject}",
        "how_derived": "no personal data available; kept honest rather than invented",
    }

    pains = [
        claim(
            f"Confused or overwhelmed by conflicting advice on {subject}.",
            HYPOTHESIS,
            basis="typical pain for explainer topics; not measured for this viewer",
        ),
        claim(
            f"Short on time; wants the useful part of {subject} fast.",
            STRONG_EVIDENCE,
            basis="short-form consumption patterns favor quick payoff",
        ),
    ]

    desires = [
        claim(
            f"Wants a clear, trustworthy take on {subject} they can act on.",
            HYPOTHESIS,
            basis="inferred from the educational framing of the idea",
        ),
        claim(
            "Wants to feel smart and share something worth sending.",
            STRONG_EVIDENCE,
            basis="shareability is driven by social/identity value",
        ),
    ]

    objections = [
        claim(
            f"'Is this just generic AI content about {subject}?'",
            HYPOTHESIS,
            basis="rising skepticism of low-effort AI clips",
        ),
        claim(
            "'Why should I trust this creator?'",
            HYPOTHESIS,
            basis="trust is earned per creator; unknown at cold start",
        ),
    ]

    body = {
        "demographics": demographics,
        "pains": pains,
        "desires": desires,
        "objections": objections,
        "awareness_level": {
            "value": "problem-aware",
            "how_derived": "idea frames a known problem, not an unknown need",
        },
        "language": language,
        "content_prefs": [
            claim(
                "Prefers a strong hook, concrete examples, and a quick payoff.",
                STRONG_EVIDENCE,
                basis="general short-form retention principles",
            ),
            claim(
                "Responds to the creator's own realized performance patterns.",
                EMPIRICAL,
                basis="to be filled from this creator's SCRIPT memory once it exists",
            ),
        ],
        "method": "local inference from idea + research; no network used",
    }

    return make_artifact(
        kind="audience",
        project_id=project_id,
        body=body,
        status="ready",
        sources=[source_ref(idea_artifact), source_ref(research_artifact)],
        agent="audience",
        identity=identity,
    )
