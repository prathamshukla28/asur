"""Stage 5 - hook intelligence (local, deterministic, explainable).

Takes the ``strategy`` artifact and produces a ``hooks`` artifact: at least 20
original hook candidates spanning several strategic directions, each scored on
15 dimensions and tagged with the deep hook-intelligence metadata from
DATA_MODELS.md s4.1. Scoring is deterministic - the same candidates always yield
the same scores - and every score is a documented function of measurable text
features of the hook itself (see ``hook_features`` and ``_DIM_FORMULAS``). There
is no hash jitter and no per-template prior: two hooks only score differently
because their text differs in a way the features can name.

Candidates come from the template library and, optionally, from an LLM provider
(``asur.llm``); both are scored by the same feature model and each hook records
which generator produced it.

Hooks are psychological patterns, not copied templates. The library categories
(curiosity / contrarian / story / data / authority / practical / question /
Hindi-Hinglish) only seed *structure*; the subject is woven in to produce an
original line. Every score carries a transparent basis so nothing is a black
box (ASUR-EXPLAIN-01).

The first three seconds are treated as one creative unit (visual pattern
interrupt -> core hook -> curiosity promise -> transition), so each hook also
records a ``first_frame`` and ``first_motion`` intent.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from ..core.envelope import Artifact, make_artifact
from ..core.identity import Identity
from ..llm import TEMPLATE, LLMProvider, draft_or_fallback
from . import source_ref
from .llm_schema import clean_text

# 15 scoring dimensions, each 0-100 (DATA_MODELS.md s4.1).
SCORE_DIMS = (
    "attention",
    "curiosity",
    "clarity",
    "specificity",
    "relevance",
    "novelty",
    "credibility",
    "emotional",
    "payoff",
    "authenticity",
    "visual_potential",
    "retention_potential",
    "audience_fit",
    "platform_fit",
    "originality",
)

MIN_HOOKS = 20

# Over-used openers we must not lean on. Presence of one of these phrasings
# raises template_fatigue_score and is penalised in the originality dimension.
_TIRED_TEMPLATES = (
    "3 things",
    "three things",
    "nobody tells you",
    "here's the secret",
    "here is the secret",
    "stop doing this",
    "you're doing it wrong",
    "the truth about",
    "what they don't want you to know",
)


def _subject(strategy_artifact: Artifact) -> str:
    body = strategy_artifact.body or {}
    promise = body.get("core_promise") or {}
    # strategy fields are {value, how_derived}; fall back gracefully.
    audience = body.get("audience_summary") or {}
    # Prefer an explicit subject threaded through objective.
    objective = body.get("objective") or {}
    obj_val = objective.get("value", "")
    # objective reads "Make the viewer understand {subject} and want to ...".
    if "understand " in obj_val and " and want to" in obj_val:
        return obj_val.split("understand ", 1)[1].split(" and want to", 1)[0].strip()
    if isinstance(promise.get("value"), str) and " about " in promise["value"]:
        return promise["value"].split(" about ", 1)[1].split(" that", 1)[0].strip()
    if isinstance(audience.get("value"), str) and " in " in audience["value"]:
        return audience["value"].rsplit(" in ", 1)[1].strip(" .")
    return "the topic"


def _strategy_field(strategy_artifact: Artifact, name: str, default: str) -> str:
    field = (strategy_artifact.body or {}).get(name) or {}
    if isinstance(field, dict):
        return field.get("value") or default
    if isinstance(field, str):
        return field or default
    return default


def _clamp(value: float) -> int:
    return max(0, min(100, round(value)))


# Each template produces one hook from a subject + action. The template only
# supplies structure + metadata; the score comes from the rendered text.
_TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "category": "curiosity",
        "pattern": "open_loop",
        "language": "en",
        "psychology": ["curiosity", "open_loop"],
        "emotion": "curiosity",
        "render": lambda s, a: f"Most people get {s} completely wrong - here's why.",
    },
    {
        "category": "contrarian",
        "pattern": "challenge_belief",
        "language": "en",
        "psychology": ["contradiction", "identity"],
        "emotion": "surprise",
        "render": lambda s, a: f"Everything you believe about {s} is holding you back.",
    },
    {
        "category": "story",
        "pattern": "personal_stakes",
        "language": "en",
        "psychology": ["story", "emotional_connection"],
        "emotion": "empathy",
        "render": lambda s, a: f"I wasted months on {s} before I understood this.",
    },
    {
        "category": "data",
        "pattern": "surprising_number",
        "language": "en",
        "psychology": ["specificity", "credibility"],
        "emotion": "surprise",
        "render": lambda s, a: f"Nine out of ten people handle {s} the expensive way.",
    },
    {
        "category": "authority",
        "pattern": "earned_lesson",
        "language": "en",
        "psychology": ["authority", "usefulness"],
        "emotion": "aspiration",
        "render": lambda s, a: f"After years around {s}, here's the one rule that matters.",
    },
    {
        "category": "practical",
        "pattern": "fast_win",
        "language": "en",
        "psychology": ["usefulness", "specificity"],
        "emotion": "aspiration",
        "render": lambda s, a: f"Get {s} right in the next 30 seconds - no fluff.",
    },
    {
        "category": "question",
        "pattern": "direct_question",
        "language": "en",
        "psychology": ["curiosity", "identity"],
        "emotion": "curiosity",
        "render": lambda s, a: f"Why does {s} feel so much harder than it should?",
    },
    {
        "category": "cost",
        "pattern": "loss_framing",
        "language": "en",
        "psychology": ["loss_aversion", "urgency"],
        "emotion": "concern",
        "render": lambda s, a: f"The hidden cost of getting {s} wrong is bigger than you think.",
    },
    {
        "category": "transformation",
        "pattern": "before_after",
        "language": "en",
        "psychology": ["transformation", "aspiration"],
        "emotion": "aspiration",
        "render": lambda s, a: f"Here's what changes the moment {s} finally clicks.",
    },
    {
        "category": "myth",
        "pattern": "bust_myth",
        "language": "en",
        "psychology": ["contradiction", "credibility"],
        "emotion": "surprise",
        "render": lambda s, a: f"The most repeated advice about {s} is quietly wrong.",
    },
    {
        "category": "hinglish",
        "pattern": "insider_secret",
        "language": "hinglish",
        "psychology": ["curiosity", "authority"],
        "emotion": "curiosity",
        "render": lambda s, a: f"{s} ke baare mein ye baat koi nahi batata.",
    },
    {
        "category": "hinglish",
        "pattern": "challenge_belief",
        "language": "hinglish",
        "psychology": ["contradiction", "identity"],
        "emotion": "surprise",
        "render": lambda s, a: f"Sab bol rahe the {s} aise nahi chalega - galat the.",
    },
    {
        "category": "hindi",
        "pattern": "direct_question",
        "language": "hi",
        "psychology": ["curiosity", "relevance"],
        "emotion": "curiosity",
        "render": lambda s, a: f"{s} itna mushkil kyun lagta hai, pata hai?",
    },
    {
        "category": "indian-en",
        "pattern": "fast_win",
        "language": "indian-en",
        "psychology": ["usefulness", "specificity"],
        "emotion": "aspiration",
        "render": lambda s, a: f"One simple shift and {s} finally gets easy.",
    },
)

# Second pass of variants so we always clear MIN_HOOKS with genuine variety:
# re-skin the strongest patterns with different angles.
_VARIANT_SUFFIXES: tuple[dict[str, Any], ...] = (
    {
        "tag": "specific",
        "psychology": ["specificity"],
        "render": lambda s, a: f"The one detail about {s} that changes the whole outcome.",
        "category": "practical",
        "pattern": "single_detail",
        "language": "en",
        "emotion": "curiosity",
    },
    {
        "tag": "mistake",
        "psychology": ["loss_aversion"],
        "render": lambda s, a: f"This tiny mistake with {s} costs people the most.",
        "category": "cost",
        "pattern": "small_mistake",
        "language": "en",
        "emotion": "concern",
    },
    {
        "tag": "proof",
        "psychology": ["credibility", "proof"],
        "render": lambda s, a: f"I tested the usual advice on {s}. Here's what actually held up.",
        "category": "data",
        "pattern": "tested_claim",
        "language": "en",
        "emotion": "surprise",
    },
    {
        "tag": "reframe",
        "psychology": ["novelty", "transformation"],
        "render": lambda s, a: f"Stop thinking of {s} as hard. Think of it like this.",
        "category": "transformation",
        "pattern": "reframe",
        "language": "en",
        "emotion": "aspiration",
    },
    {
        "tag": "insider-en",
        "psychology": ["authority", "curiosity"],
        "render": lambda s, a: f"What people who are great at {s} never say out loud.",
        "category": "authority",
        "pattern": "unspoken_rule",
        "language": "en",
        "emotion": "curiosity",
    },
    {
        "tag": "question-stakes",
        "psychology": ["curiosity", "loss_aversion"],
        "render": lambda s, a: f"What if the way you learned {s} was the slow way?",
        "category": "question",
        "pattern": "what_if",
        "language": "en",
        "emotion": "curiosity",
    },
    {
        "tag": "story-turn",
        "psychology": ["story", "transformation"],
        "render": lambda s, a: f"The day {s} finally made sense, everything got easier.",
        "category": "story",
        "pattern": "turning_point",
        "language": "en",
        "emotion": "empathy",
    },
)


def _first_three_seconds(template: dict[str, Any], subject: str) -> dict[str, dict[str, str]]:
    """Hook + visual as one unit: the first-3-seconds blueprint."""
    return {
        "0.0-0.5s_pattern_interrupt": {
            "value": "sharp visual cut or unexpected first frame",
            "how_derived": "blueprint: stop the scroll before the words land",
        },
        "0.5-1.5s_core_hook": {
            "value": "the spoken hook line itself",
            "how_derived": "blueprint: deliver the promise/tension immediately",
        },
        "1.5-2.5s_curiosity_promise": {
            "value": f"tease the one thing they'll learn about {subject}",
            "how_derived": "blueprint: open a loop the payoff will close",
        },
        "2.5-3.0s_transition": {
            "value": "motion/cut into the opening line",
            "how_derived": "blueprint: carry momentum into the body",
        },
    }


def _template_fatigue(text: str) -> tuple[int, str]:
    low = text.lower()
    for tired in _TIRED_TEMPLATES:
        if tired in low:
            return 80, f"uses tired opener '{tired}'"
    return 10, "no over-used template phrasing detected"


# -- feature model -----------------------------------------------------------
#
# Every hook score is a weighted sum of these text features (each in [0, 1]).
# They are deliberately simple and inspectable; each hook records its feature
# values so any score can be recomputed by hand from ``_DIM_FORMULAS``.

_WORD = re.compile(r"[a-z0-9']+")
_NUMBER_WORDS = frozenset(
    "one two three four five six seven eight nine ten eleven twelve twenty thirty "
    "hundred thousand million half".split()
)
_SECOND_PERSON = frozenset({"you", "your", "you're", "yours", "yourself", "aap", "tum", "tumhe"})
_VAGUE = frozenset({"thing", "things", "stuff", "everything", "something", "anything"})
_STOPWORDS = frozenset(
    "a an the of on in to for and or with about is are be it this that how why what "
    "most people".split()
)
# Curiosity-gap cues: an open question or a withheld answer.
_CURIOSITY = (
    r"\bwhy\b", r"\bwhat\b", r"\bhere'?s (why|what|how)\b", r"\bthe one\b",
    r"\bnever\b", r"\b(secret|hidden|nobody|koi nahi)\b", r"\?\s*$",
    r"\bbefore\b", r"\bwhat if\b", r"\bactually\b",
)
# Contrast / stakes cues: contradiction or loss framing.
_CONTRAST = (
    r"\bwrong\b", r"\bmyth\b", r"\bstop\b", r"\bmistake\b", r"\bcosts?\b",
    r"\bwast", r"\bholding you back\b", r"\bgalat\b", r"\bexpensive\b", r"\bhidden cost\b",
)
# Payoff-promise cues: the hook commits to giving something.
_PROMISE = (
    r"\bhere'?s\b", r"\bthe one\b", r"\brule\b", r"\bfix", r"\bright\b",
    r"\bchanges\b", r"\bthink of it\b", r"\bheld up\b", r"\beasy\b", r"\bclicks\b",
)
# Claims the system cannot verify: invented statistics or first-person experience.
_UNVERIFIABLE = (
    r"\b\d+\s*%", r"\b\d+ out of \d+\b",
    r"\b(one|two|three|four|five|six|seven|eight|nine) out of (ten|\w+)\b",
    r"\bstudies show\b",
    r"\bi (tested|wasted|learned|spent|tried|lost|made)\b", r"\bafter years\b",
)


def _count(patterns: tuple[str, ...], low: str) -> int:
    return sum(1 for pat in patterns if re.search(pat, low))


def hook_features(
    text: str,
    *,
    subject: str,
    language: str,
    language_target: str,
    emotion: str,
    strategy_emotion: str,
    novelty_vs_prior: float,
) -> dict[str, float]:
    """Measure the documented text features of one hook (all in [0, 1]).

    - length: 1.0 for 6-14 words; decays linearly outside (0 at <=0 / >=24 words)
    - number: 1.0 if the hook contains a digit or a number word
    - second_person: 1.0 if it addresses the viewer ("you", "your", "aap", ...)
    - curiosity: 0.5 per curiosity-gap cue, capped at 1.0
    - contrast: 0.5 per contradiction / loss-framing cue, capped at 1.0
    - promise: 0.5 per payoff-promise cue, capped at 1.0
    - question: 1.0 if the hook ends with "?"
    - subject: share of the subject's content words that appear in the hook
    - concrete: 1 - 3 x (share of vague words like "thing(s)", "stuff")
    - verifiable: 0.0 if the hook asserts a statistic or personal experience the
      system cannot verify (e.g. "nine out of ten", "I tested"), else 1.0
    - not_tired: 0.0 if it uses an over-used template opener, else 1.0
    - language_match: 1.0 if the hook's language is the strategy's target
    - emotion_match: 1.0 if the hook's emotion is the strategy's emotion
    - novel_vs_prior: word-overlap distance to the nearest remembered hook
    """
    low = text.lower()
    words = _WORD.findall(low)
    n = len(words)
    if 6 <= n <= 14:
        length = 1.0
    elif n < 6:
        length = max(0.0, n / 6)
    else:
        length = max(0.0, 1 - (n - 14) / 10)
    subject_terms = [w for w in _WORD.findall(subject.lower()) if w not in _STOPWORDS]
    subject_hit = (
        sum(1 for w in subject_terms if w in words) / len(subject_terms) if subject_terms else 0.0
    )
    vague = sum(1 for w in words if w in _VAGUE)
    fatigue, _reason = _template_fatigue(text)
    return {
        "length": round(length, 3),
        "number": 1.0 if (re.search(r"\d", low) or any(w in _NUMBER_WORDS for w in words)) else 0.0,
        "second_person": 1.0 if any(w in _SECOND_PERSON for w in words) else 0.0,
        "curiosity": min(1.0, 0.5 * _count(_CURIOSITY, low)),
        "contrast": min(1.0, 0.5 * _count(_CONTRAST, low)),
        "promise": min(1.0, 0.5 * _count(_PROMISE, low)),
        "question": 1.0 if low.rstrip().endswith("?") else 0.0,
        "subject": round(subject_hit, 3),
        "concrete": round(max(0.0, 1 - 3 * (vague / n if n else 1.0)), 3),
        "verifiable": 0.0 if _count(_UNVERIFIABLE, low) else 1.0,
        "not_tired": 0.0 if fatigue >= 80 else 1.0,
        "language_match": 1.0 if language == language_target else 0.0,
        "emotion_match": 1.0 if emotion == strategy_emotion else 0.0,
        "novel_vs_prior": round(max(0.0, min(1.0, novelty_vs_prior)), 3),
    }


# score(dim) = round(100 * (bias + sum(weight * feature))); each row sums to 1.0,
# so every dimension spans 0-100 and is fully determined by the features above.
_DIM_FORMULAS: dict[str, tuple[float, dict[str, float]]] = {
    "attention": (0.30, {"curiosity": 0.25, "contrast": 0.20, "second_person": 0.10, "length": 0.15}),
    "curiosity": (0.20, {"curiosity": 0.60, "question": 0.10, "contrast": 0.10}),
    "clarity": (0.20, {"length": 0.40, "concrete": 0.40}),
    "specificity": (0.15, {"number": 0.30, "concrete": 0.30, "subject": 0.25}),
    "relevance": (0.20, {"subject": 0.50, "second_person": 0.15, "emotion_match": 0.15}),
    "novelty": (0.30, {"contrast": 0.35, "not_tired": 0.35}),
    "credibility": (0.40, {"verifiable": 0.40, "concrete": 0.20}),
    "emotional": (0.25, {"contrast": 0.30, "second_person": 0.20, "emotion_match": 0.25}),
    "payoff": (0.25, {"promise": 0.45, "subject": 0.30}),
    "authenticity": (0.40, {"verifiable": 0.40, "not_tired": 0.20}),
    "visual_potential": (0.30, {"concrete": 0.35, "number": 0.15, "contrast": 0.20}),
    "retention_potential": (0.20, {"curiosity": 0.40, "promise": 0.25, "length": 0.15}),
    "audience_fit": (0.30, {"language_match": 0.40, "second_person": 0.30}),
    "platform_fit": (0.30, {"length": 0.50, "not_tired": 0.20}),
    "originality": (0.20, {"not_tired": 0.40, "novel_vs_prior": 0.40}),
}


def score_from_features(features: dict[str, float]) -> dict[str, int]:
    """Apply ``_DIM_FORMULAS`` to a feature vector -> 15 dimension scores (0-100)."""
    scores: dict[str, int] = {}
    for dim in SCORE_DIMS:
        bias, weights = _DIM_FORMULAS[dim]
        scores[dim] = _clamp(100 * (bias + sum(w * features[f] for f, w in weights.items())))
    return scores


def _aggregate(scores: dict[str, int]) -> int:
    return _clamp(sum(scores.values()) / len(scores))


def _originality_verdict(text: str, prior_texts: list[str]) -> dict[str, Any]:
    """Compare against prior hooks (Jaccard word overlap) - no network."""
    words = set(text.lower().split())
    nearest = ""
    best = 0.0
    for prior in prior_texts:
        pw = set(prior.lower().split())
        if not pw:
            continue
        overlap = len(words & pw) / len(words | pw)
        if overlap > best:
            best = overlap
            nearest = prior
    if best >= 0.6:
        verdict = "derivative"
    elif best >= 0.35:
        verdict = "familiar-structure-fresh-execution"
    else:
        verdict = "original"
    return {
        "verdict": verdict,
        "nearest_prior": nearest,
        "distance": round(1.0 - best, 3),
    }


def _strength_label(aggregate: int) -> str:
    if aggregate >= 80:
        return "high"
    if aggregate >= 68:
        return "medium"
    return "low"


# A/B variant grouping (DATA ONLY, SPEC-GAP G2).
#
# We organise the ranked hooks into up to four labelled variants A/B/C/D, each
# anchored on a *distinct strategic direction* (a different psychological angle),
# so a future experiment can compare genuinely different openings for the same
# video. This is organisation only: NOTHING is tested live here. Live A/B testing
# waits for VIRAL CHECK + LEARNING, which own real performance data. Keeping this
# data-only honours ASUR-HONEST-01 (we never imply a measured winner we do not
# have) and ASUR-FIREWALL-01 (SCRIPT does not peek at viral-checker criteria).
_VARIANT_LABELS = ("A", "B", "C", "D")

# Each strategic direction maps a set of hook categories to one angle name. The
# order here is the priority order in which variants are assigned A -> B -> C -> D.
_STRATEGIC_DIRECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("curiosity", ("curiosity", "question", "myth")),
    ("contrarian", ("contrarian", "cost")),
    ("story", ("story", "transformation")),
    ("authority", ("authority", "data", "practical")),
)


def _direction_for_category(category: str) -> str:
    for direction, categories in _STRATEGIC_DIRECTIONS:
        if category in categories:
            return direction
    return "other"


def _ab_variants(ranked: list[dict[str, Any]]) -> dict[str, Any]:
    """Group ranked hooks into up to 4 distinct-direction variants A/B/C/D.

    Data-only: each variant records its angle, the chosen (highest-ranked) hook
    for that angle, and the other candidate hook_ids in that angle. No winner is
    declared and no experiment is run (SPEC-GAP G2 conservative default).
    """
    # Bucket ranked hooks by strategic direction, preserving rank order.
    buckets: dict[str, list[dict[str, Any]]] = {}
    for hook in ranked:
        direction = _direction_for_category(hook["metadata"]["category"])
        buckets.setdefault(direction, []).append(hook)

    # Assign variants in the fixed strategic-direction priority order, but only
    # for directions that actually produced at least one hook. This keeps the
    # labels stable and deterministic.
    variants: list[dict[str, Any]] = []
    for direction, _categories in _STRATEGIC_DIRECTIONS:
        hooks_in_dir = buckets.get(direction)
        if not hooks_in_dir:
            continue
        if len(variants) >= len(_VARIANT_LABELS):
            break
        label = _VARIANT_LABELS[len(variants)]
        chosen = hooks_in_dir[0]  # highest-ranked hook in this angle
        variants.append(
            {
                "variant": label,
                "direction": direction,
                "chosen_hook_id": chosen["hook_id"],
                "chosen_hook": chosen["metadata"]["hook"],
                "candidate_hook_ids": [h["hook_id"] for h in hooks_in_dir],
                "how_derived": (
                    f"highest-ranked hook in the '{direction}' direction; "
                    "grouped for future A/B testing, not tested live"
                ),
            }
        )

    return {
        "status": "data-only (no live experiment run)",
        "labels": [v["variant"] for v in variants],
        "variants": variants,
        "note": (
            "Variants group distinct strategic angles so VIRAL CHECK + LEARNING "
            "can later compare them on real performance. No winner is implied here "
            "(ASUR-HONEST-01)."
        ),
    }


_LLM_SYSTEM = (
    "You write opening hooks for short vertical videos. Reply with ONE JSON object "
    "only. Hooks must be one sentence, under 16 words, and must not invent "
    "statistics or claim personal experience."
)
_CATEGORY_DEFAULTS = {t["category"]: t for t in _TEMPLATES if t.get("language") == "en"}
MAX_LLM_HOOKS = 8


def _validate_llm_hooks(data: Any) -> list[dict[str, str]]:
    """Coerce an LLM reply into up to MAX_LLM_HOOKS {text, category} candidates."""
    items = data.get("hooks") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("expected a 'hooks' list")
    out: list[dict[str, str]] = []
    for item in items[:MAX_LLM_HOOKS]:
        text = item.get("hook") if isinstance(item, dict) else item
        category = item.get("category", "curiosity") if isinstance(item, dict) else "curiosity"
        out.append({"text": clean_text(text, max_chars=160), "category": str(category)})
    if not out:
        raise ValueError("no hooks in reply")
    return out


def _no_llm_hooks() -> list[dict[str, str]]:
    return []


def _llm_candidates(
    generator: LLMProvider | None, subject: str, strategy_emotion: str
) -> tuple[list[tuple[dict[str, Any], str, str]], dict[str, Any]]:
    """Ask the LLM for extra hook lines; returns (candidates, provenance)."""
    if generator is None:
        return [], {"generator": TEMPLATE}
    cats = ", ".join(sorted(_CATEGORY_DEFAULTS))
    drafted, provenance = draft_or_fallback(
        generator,
        prompt=(
            f"Topic: {subject!r}. Target emotion: {strategy_emotion}.\n"
            f'Return JSON {{"hooks": [{{"hook": str, "category": one of [{cats}]}}]}} '
            f"with {MAX_LLM_HOOKS} distinct hooks."
        ),
        system=_LLM_SYSTEM,
        validate=_validate_llm_hooks,
        fallback=_no_llm_hooks,
    )
    candidates = []
    for item in drafted:
        template = _CATEGORY_DEFAULTS.get(item["category"], _CATEGORY_DEFAULTS["curiosity"])
        candidates.append((template, item["text"], provenance["generator"]))
    return candidates, provenance


def build_hooks(
    strategy_artifact: Artifact,
    project_id: str,
    *,
    identity: Identity | None = None,
    prior_hooks: list[str] | None = None,
    generator: LLMProvider | None = None,
) -> Artifact:
    """Produce a ``hooks`` artifact (>=20 scored, ranked hooks) from strategy.

    ``prior_hooks`` is an optional list of hook texts this creator has used
    before, enabling the originality + hook-fatigue checks. ``generator`` is an
    optional LLM provider whose hooks join the template candidates and are scored
    by the same feature model.

    Ranking: aggregate score (desc), then fewer words (shorter hooks land inside
    the first seconds), then candidate order (templates in library order, then
    LLM hooks in reply order). Deterministic for a given candidate list.
    """
    subject = _subject(strategy_artifact)
    strategy_emotion = _strategy_field(strategy_artifact, "emotion", "curiosity")
    language_target = (strategy_artifact.body or {}).get("language", "en")
    action = "save"
    prior_texts = list(prior_hooks or [])

    candidates: list[tuple[dict[str, Any], str, str]] = [
        (template, template["render"](subject, action).strip(), TEMPLATE)
        for template in list(_TEMPLATES) + list(_VARIANT_SUFFIXES)
    ]
    llm_candidates, llm_provenance = _llm_candidates(generator, subject, strategy_emotion)
    candidates += llm_candidates

    generated: list[dict[str, Any]] = []
    seen_texts: list[str] = []
    for order, (template, text, made_by) in enumerate(candidates):
        if text.lower() in (t.lower() for t in seen_texts):
            continue  # an LLM may echo a template line; keep the first
        originality = _originality_verdict(text, prior_texts + seen_texts)
        features = hook_features(
            text,
            subject=subject,
            language=template.get("language", "en"),
            language_target=language_target,
            emotion=template.get("emotion", "curiosity"),
            strategy_emotion=strategy_emotion,
            novelty_vs_prior=originality["distance"],
        )
        scores = score_from_features(features)
        tmpl_fatigue, tmpl_reason = _template_fatigue(text)
        aggregate = _aggregate(scores)
        # Hook fatigue: has this creator already used a near-identical hook?
        hook_fatigue = _clamp(
            80 if originality["distance"] <= 0.4 and prior_texts else 12
        )
        hook_id = f"hook-{hashlib.sha256(text.encode('utf-8')).hexdigest()[:10]}"
        generated.append(
            {
                "hook_id": hook_id,
                "scores": scores,
                "features": features,
                "aggregate": aggregate,
                "hook_fatigue_score": hook_fatigue,
                "template_fatigue_score": tmpl_fatigue,
                "template_fatigue_reason": tmpl_reason,
                "originality": originality,
                "first_three_seconds": _first_three_seconds(template, subject),
                "candidate_order": order,
                "metadata": {
                    "hook": text,
                    "generator": made_by,
                    "language": template.get("language", "en"),
                    "category": template.get("category", "general"),
                    "pattern": template.get("pattern", "unknown") if made_by == TEMPLATE else "llm_drafted",
                    "psychology": template.get("psychology", []),
                    "emotion": template.get("emotion", "curiosity"),
                    "promise": f"one clear, honest takeaway about {subject}",
                    "audience_stage": "problem-aware",
                    "content_types": ["educational", "short-form"],
                    "strength": _strength_label(aggregate),
                },
            }
        )
        seen_texts.append(text)

    ranked = sorted(
        generated,
        key=lambda h: (-h["aggregate"], len(h["metadata"]["hook"].split()), h["candidate_order"]),
    )
    for rank, hook in enumerate(ranked, start=1):
        hook["rank"] = rank

    selected_hook_id = ranked[0]["hook_id"] if ranked else None
    ab_variants = _ab_variants(ranked)
    llm_used = any(h["metadata"]["generator"] != TEMPLATE for h in ranked)

    body = {
        "subject": subject,
        "language": language_target,
        "count": len(ranked),
        "min_required": MIN_HOOKS,
        "score_dimensions": list(SCORE_DIMS),
        "hooks": ranked,
        "selected_hook_id": selected_hook_id,
        "ab_variants": ab_variants,
        "selection_reason": (
            "highest aggregate (mean of 15 feature-derived dimensions); ties broken by "
            "fewer words, then candidate order (reproducible, ASUR-HONEST-01)"
        ),
        "scoring_model": {
            "features": "see asur.script.hooks.hook_features (each hook records its values)",
            "formula": "score(dim) = round(100 * (bias + sum(weight * feature)))",
            "weights": {dim: {"bias": b, **w} for dim, (b, w) in _DIM_FORMULAS.items()},
        },
        "first_three_seconds_blueprint": (
            "0.0-0.5s pattern interrupt / 0.5-1.5s core hook / "
            "1.5-2.5s curiosity promise / 2.5-3.0s transition"
        ),
        "generator": f"{TEMPLATE}+{llm_provenance['generator']}" if llm_used else TEMPLATE,
        **({"llm_fallback": llm_provenance["llm_fallback"]} if "llm_fallback" in llm_provenance else {}),
        "method": "template + optional LLM candidates; deterministic text-feature scoring",
    }

    return make_artifact(
        kind="hooks",
        project_id=project_id,
        body=body,
        status="ready",
        sources=[source_ref(strategy_artifact)],
        agent="hook",
        identity=identity,
    )
