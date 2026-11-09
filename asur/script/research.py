"""Stage 2 - research (local heuristic, evidence-classed).

Takes an ``idea`` artifact and produces a ``research`` artifact: the topic
restated, several angles worth exploring, supporting points, risks, and
counterarguments. By default this is a deterministic template over the idea
text (no network). When an LLM provider is supplied (see ``asur.llm``), the
model drafts the angles/points instead; its claims are always tagged HYPOTHESIS
because a model cannot verify facts, and ``body["generator"]`` records which
generator produced the artifact (ASUR-HONEST-01).

The point of this stage is not to invent facts the system cannot know. It is to
lay out the shape of the topic - what to say, what to be careful about, what a
skeptic would push back on - so later stages have an explicit, inspectable map
instead of hidden assumptions (ASUR-EXPLAIN-01).
"""

from __future__ import annotations

from typing import Any

from ..core.envelope import Artifact, make_artifact
from ..core.identity import Identity
from ..llm import LLMProvider, draft_or_fallback
from . import source_ref
from .evidence import HYPOTHESIS, STRONG_EVIDENCE, VERIFIED_FACT, claim
from .llm_schema import as_object_list, as_str_list

_SYSTEM = (
    "You are a research assistant for a short-form video creator. Reply with ONE "
    "JSON object only. Do not invent statistics, studies, or quotes; if a point "
    "needs a source, say so in the text."
)


def _subject(idea_artifact: Artifact) -> str:
    body = idea_artifact.body or {}
    understanding = body.get("understanding") or {}
    problem = understanding.get("problem") or {}
    return problem.get("value") or body.get("one_line", "the topic")


def _llm_prompt(idea_artifact: Artifact, subject: str) -> str:
    one_line = (idea_artifact.body or {}).get("one_line", subject)
    return (
        f"Video idea: {one_line!r}. Topic: {subject!r}.\n"
        "Return JSON with keys:\n"
        '  "angles": 3-5 objects {"angle": short label, "summary": one sentence, '
        '"why": one sentence},\n'
        '  "supporting_points": 2-5 short strings,\n'
        '  "risks": 1-4 short strings,\n'
        '  "counterarguments": 1-4 objects {"objection": str, "response": str}.'
    )


def _validate_llm(data: Any, label: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    basis = f"drafted by {label}; not independently verified"
    return {
        "angles": as_object_list(data.get("angles"), ("angle", "summary", "why"), 3, 6),
        "supporting_points": [
            claim(t, HYPOTHESIS, basis=basis)
            for t in as_str_list(data.get("supporting_points"), 2, 6)
        ],
        "risks": [claim(t, HYPOTHESIS, basis=basis) for t in as_str_list(data.get("risks"), 1, 5)],
        "counterarguments": as_object_list(
            data.get("counterarguments"), ("objection", "response"), 1, 5
        ),
    }


def build_research(
    idea_artifact: Artifact,
    project_id: str,
    *,
    identity: Identity | None = None,
    generator: LLMProvider | None = None,
) -> Artifact:
    """Produce a ``research`` artifact from an ``idea`` artifact.

    ``generator`` is an optional LLM provider; without one (or if its output
    fails validation) the deterministic template below is used.
    """
    subject = _subject(idea_artifact)
    drafted, provenance = draft_or_fallback(
        generator,
        prompt=_llm_prompt(idea_artifact, subject),
        system=_SYSTEM,
        validate=lambda data: _validate_llm(data, generator.label if generator else ""),
        fallback=lambda: _template_sections(subject),
    )
    body = {
        "topic": subject,
        **drafted,
        **provenance,
        "method": (
            "local heuristic reasoning over the idea; no network used"
            if provenance["generator"] == "template"
            else f"drafted by {provenance['generator']}; claims tagged HYPOTHESIS"
        ),
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


def _template_sections(subject: str) -> dict[str, Any]:
    """The deterministic offline research template (the default generator)."""
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

    return {
        "angles": angles,
        "supporting_points": supporting_points,
        "risks": risks,
        "counterarguments": counterarguments,
    }
