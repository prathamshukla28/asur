"""Stage 1 - Idea intake.

Turns a one-line idea string into a structured, explainable ``idea`` artifact.
This is the single human input that seeds the whole Phase 1 pipeline (spec
STEP1 / pipeline Stage 3 "Content Understanding").

The builder does NOT invent facts about the world. It parses intent from the
line the human gave and records six things explicitly so every later stage has
a stable source of truth to point at:

    what      what is being communicated (the subject)
    who       who it is for (best-effort from the line; refined by audience)
    why       why it matters
    problem   the problem it solves (if any)
    emotion   the primary emotion to evoke
    action    the desired viewer action

Local only, no network (ASUR-LOCAL-01). Fully explainable (ASUR-EXPLAIN-01).
"""

from __future__ import annotations

import re
from typing import Optional

from ..core.envelope import Artifact, make_artifact
from ..core.identity import Identity

__all__ = ["build_idea", "DEFAULT_PLATFORM"]

DEFAULT_PLATFORM = "instagram_reels"

# Light heuristic cue lists - used only to derive an explainable first guess at
# emotion / desired action from the idea text. These are NOT claims about the
# world; they are parsing aids and every derived field records how it was set.
_EMOTION_CUES = {
    "curiosity": ("why", "secret", "nobody", "truth", "really", "actually", "hidden"),
    "surprise": ("shocking", "surprising", "unexpected", "you won't believe"),
    "concern": ("mistake", "waste", "wrong", "stop", "avoid", "danger", "risk"),
    "aspiration": ("how to", "grow", "build", "master", "best", "win", "success"),
    "empathy": ("struggle", "hard", "fail", "lonely", "stuck", "overwhelmed"),
}

_ACTION_CUES = {
    "save": ("tips", "steps", "how to", "checklist", "guide", "framework"),
    "comment": ("agree", "think", "opinion", "debate", "unpopular"),
    "follow": ("series", "part 1", "more", "everyday", "daily"),
    "share": ("everyone", "friend", "tell", "spread"),
}


def _first_cue(text: str, table: dict[str, tuple]) -> Optional[str]:
    low = text.lower()
    for label, cues in table.items():
        if any(cue in low for cue in cues):
            return label
    return None


# Verbs that become a natural "-ing" topic phrase when a hook needs a noun.
# e.g. "why people waste money" -> subject "wasting money".
_VERB_GERUND = {
    "waste": "wasting",
    "wastes": "wasting",
    "spend": "spending",
    "spends": "spending",
    "lose": "losing",
    "loses": "losing",
    "make": "making",
    "makes": "making",
    "use": "using",
    "uses": "using",
    "buy": "buying",
    "buys": "buying",
    "pick": "picking",
    "picks": "picking",
    "choose": "choosing",
    "chooses": "choosing",
    "ignore": "ignoring",
    "ignores": "ignoring",
    "avoid": "avoiding",
    "avoids": "avoiding",
    "fail": "failing",
    "fails": "failing",
    "get": "getting",
    "gets": "getting",
}


def _derive_subject(one_line: str) -> str:
    """Expose a clean, natural topic noun phrase from the idea line.

    Hooks weave the subject into a sentence, so a verbatim line like
    "why most people waste money on AI tools" must become a phrase that reads
    naturally inside a template ("... AI tools ke baare mein ..."). We strip
    production framing, then leading question words and quantifier framing, and
    convert a leading action verb to its gerund so the result is a noun phrase.
    Deterministic + stdlib only (ASUR-LOCAL-01 / ASUR-EXPLAIN-01).
    """
    s = one_line.strip()

    # 1. Strip "make a 30-second reel about ..." style production framing.
    s = re.sub(
        r"^(i want to |can you )?(make|create|do|film|shoot|record)\s+(a|an|the)?\s*"
        r"(\d+[- ]?second\s+)?(instagram\s+)?(reel|video|short|clip)?\s*"
        r"(about|on|explaining|showing|that explains|that shows)?\s*",
        "",
        s,
        flags=re.IGNORECASE,
    )

    # 2. Strip a leading question word + optional quantifier/subject framing,
    #    e.g. "why most people", "how you", "what everyone".
    s = re.sub(
        r"^(why|how|what|when|where|the reason|the way)\s+"
        r"(do |does |did )?"
        r"(most |some |many |a lot of )?"
        r"(people|you|we|everyone|anyone|beginners|creators|they)?\s*",
        "",
        s,
        flags=re.IGNORECASE,
    )

    s = s.strip()
    if not s:
        return one_line.strip()

    # 3. If the phrase now opens with a known action verb, make it a gerund so
    #    the subject reads as a noun phrase ("waste money" -> "wasting money").
    words = s.split()
    first = words[0].lower()
    if first in _VERB_GERUND:
        words[0] = _VERB_GERUND[first]
        s = " ".join(words)

    return s.strip() or one_line.strip()


def build_idea(
    one_line: str,
    project_id: str,
    *,
    platform: str = DEFAULT_PLATFORM,
    language: str = "en",
    identity: Optional[Identity] = None,
) -> Artifact:
    """Build the ``idea`` artifact from a single human-supplied line."""
    if not one_line or not one_line.strip():
        raise ValueError("idea line is empty")

    subject = _derive_subject(one_line)
    emotion = _first_cue(one_line, _EMOTION_CUES) or "curiosity"
    action = _first_cue(one_line, _ACTION_CUES) or "save"

    body = {
        "one_line": one_line.strip(),
        "language": language,
        "platform": platform,
        "understanding": {
            "what": {
                "value": subject,
                "how_derived": "subject extracted from idea line by stripping framing verbs",
            },
            "who": {
                "value": "unspecified - refined by audience stage",
                "how_derived": "idea stage does not assume an audience; see audience artifact",
            },
            "why": {
                "value": f"the creator believes '{subject}' is worth the viewer's attention",
                "how_derived": "stated intent of the idea line",
            },
            "problem": {
                "value": subject,
                "how_derived": "treated as the implicit problem/topic the video addresses",
            },
            "emotion": {
                "value": emotion,
                "how_derived": "matched against emotion cue words in the idea line (default curiosity)",
            },
            "action": {
                "value": action,
                "how_derived": "matched against desired-action cue words in the idea line (default save)",
            },
        },
    }

    return make_artifact(
        kind="idea",
        project_id=project_id,
        body=body,
        status="ready",
        identity=identity,
    )
