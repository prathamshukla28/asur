"""Stage 2 - research (local heuristic, evidence-classed).

Takes an ``idea`` artifact and produces a ``research`` artifact: the topic
restated, several angles worth exploring, supporting points, risks, and
counterarguments. There is NO network here (ASUR-LOCAL-01). This is structured
local reasoning over the idea text, and every world-claim is tagged with an
evidence class so a guess is never presented as a fact (ASUR-HONEST-01).

The point of this stage is not to invent facts the system cannot know. It is to
lay out the shape of the topic - what to say, what to be careful about, what a
skeptic would push back on - so later stages have an explicit, inspectable map
instead of hidden assumptions (ASUR-EXPLAIN-01).
"""

from __future__ import annotations

from ..core.envelope import Artifact, make_artifact
from ..core.identity import Identity
from . import source_ref
from .evidence import HYPOTHESIS, STRONG_EVIDENCE, VERIFIED_FACT, claim


def _subject(idea_artifact: Artifact) -> str:
    body = idea_artifact.body or {}
    understanding = body.get("understanding") or {}
    problem = understanding.get("problem") or {}
    return problem.get("value") or body.get("one_line", "the topic")


def build_research(
    idea_artifact: Artifact,
    project_id: str,
    *,
    identity: Identity | None = None,
) -> Artifact:
    """Produce a ``research`` artifact from an ``idea`` artifact."""
    subject = _subject(idea_artifact)

    angles = [
        {
            "angle": "educational",
            "summary": f"Explain {subject} plainly so a beginner gets it fast.",
            "why": "Clear teaching earns saves and watch-through.",
        },
        {
            "angle": "contrarian",
            "summary": f"Challenge the common belief about {subject}.",
            "why": "A credible disagreement creates curiosity and comments.",
        },
        {
            "angle": "story",
            "summary": f"Tell a short real story that makes {subject} concrete.",
            "why": "Specific stories carry emotion and hold attention.",
        },
        {
            "angle": "practical",
            "summary": f"Give a small, do-it-now takeaway about {subject}.",
            "why": "Usefulness drives shares and saves.",
        },
    ]

    supporting_points = [
        claim(
            f"The audience needs {subject} framed around a single clear outcome.",
            STRONG_EVIDENCE,
            basis="short-form retention favors one tight promise over many ideas",
        ),
        claim(
            "The first three seconds disproportionately decide watch-through.",
            STRONG_EVIDENCE,
            basis="ad-recall studies (Nielsen/Meta) transferred by analogy to feed",
        ),
        claim(
            f"Concrete specifics about {subject} beat vague generalities.",
            HYPOTHESIS,
            basis="common creator practice; not rigorously isolated as a cause",
        ),
    ]

    risks = [
        claim(
            f"{subject} may be over-covered, making originality harder.",
            HYPOTHESIS,
            basis="saturation is topic-dependent and not measured here",
        ),
        claim(
            "Overclaiming results would damage credibility and trust.",
            VERIFIED_FACT,
            basis="misleading claims violate ASUR-HONEST-01 by construction",
        ),
    ]

    counterarguments = [
        {
            "objection": f"'Everyone already knows {subject}.'",
            "response": "Lead with a specific, lesser-known angle, not the basics.",
        },
        {
            "objection": "'This is just another AI-made clip.'",
            "response": "Ground it in a real example and the creator's own voice.",
        },
    ]

    body = {
        "topic": subject,
        "angles": angles,
        "supporting_points": supporting_points,
        "risks": risks,
        "counterarguments": counterarguments,
        "method": "local heuristic reasoning over the idea; no network used",
    }

    return make_artifact(
        kind="research",
        project_id=project_id,
        body=body,
        status="ready",
        sources=[source_ref(idea_artifact)],
        agent="research",
        identity=identity,
    )
