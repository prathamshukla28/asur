"""Stage 5 - hook intelligence (local, deterministic, explainable).

Takes the ``strategy`` artifact and produces a ``hooks`` artifact: at least 20
original hook candidates spanning several strategic directions, each scored on
15 dimensions and tagged with the deep hook-intelligence metadata from
DATA_MODELS.md s4.1. No network (ASUR-LOCAL-01). Scoring is deterministic -
the same strategy always yields the same scores (ASUR-HONEST-01 reproducibility,
no un-seeded randomness).

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
from typing import Any

from ..core.envelope import Artifact, make_artifact
from ..core.identity import Identity
from . import source_ref

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


def _det_unit(seed: str) -> float:
    """Deterministic value in [0, 1) derived from a string seed.

    Pure hash-based; no randomness, so runs are reproducible (ASUR-HONEST-01).
    """
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _clamp(value: float) -> int:
    return max(0, min(100, round(value)))


# Each template produces one hook from a subject + action. ``base`` dims give
# the structural strengths/weaknesses of that pattern before subject-specific
# jitter is applied. Everything here is editable, explainable heuristic.
_TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "category": "curiosity",
        "pattern": "open_loop",
        "language": "en",
        "psychology": ["curiosity", "open_loop"],
        "emotion": "curiosity",
        "render": lambda s, a: f"Most people get {s} completely wrong - here's why.",
        "base": {"attention": 82, "curiosity": 90, "clarity": 70, "payoff": 68},
    },
    {
        "category": "contrarian",
        "pattern": "challenge_belief",
        "language": "en",
        "psychology": ["contradiction", "identity"],
        "emotion": "surprise",
        "render": lambda s, a: f"Everything you believe about {s} is holding you back.",
        "base": {"attention": 85, "novelty": 80, "credibility": 60, "emotional": 72},
    },
    {
        "category": "story",
        "pattern": "personal_stakes",
        "language": "en",
        "psychology": ["story", "emotional_connection"],
        "emotion": "empathy",
        "render": lambda s, a: f"I wasted months on {s} before I understood this.",
        "base": {"authenticity": 88, "emotional": 82, "attention": 72, "specificity": 70},
    },
    {
        "category": "data",
        "pattern": "surprising_number",
        "language": "en",
        "psychology": ["specificity", "credibility"],
        "emotion": "surprise",
        "render": lambda s, a: f"Nine out of ten people handle {s} the expensive way.",
        "base": {"specificity": 85, "credibility": 78, "clarity": 80, "novelty": 66},
    },
    {
        "category": "authority",
        "pattern": "earned_lesson",
        "language": "en",
        "psychology": ["authority", "usefulness"],
        "emotion": "aspiration",
        "render": lambda s, a: f"After years around {s}, here's the one rule that matters.",
        "base": {"credibility": 84, "clarity": 76, "payoff": 78, "authenticity": 74},
    },
    {
        "category": "practical",
        "pattern": "fast_win",
        "language": "en",
        "psychology": ["usefulness", "specificity"],
        "emotion": "aspiration",
        "render": lambda s, a: f"Get {s} right in the next 30 seconds - no fluff.",
        "base": {"clarity": 86, "payoff": 80, "platform_fit": 82, "specificity": 74},
    },
    {
        "category": "question",
        "pattern": "direct_question",
        "language": "en",
        "psychology": ["curiosity", "identity"],
        "emotion": "curiosity",
        "render": lambda s, a: f"Why does {s} feel so much harder than it should?",
        "base": {"curiosity": 82, "relevance": 80, "attention": 74, "clarity": 72},
    },
    {
        "category": "cost",
        "pattern": "loss_framing",
        "language": "en",
        "psychology": ["loss_aversion", "urgency"],
        "emotion": "concern",
        "render": lambda s, a: f"The hidden cost of getting {s} wrong is bigger than you think.",
        "base": {"emotional": 80, "attention": 78, "curiosity": 76, "payoff": 70},
    },
    {
        "category": "transformation",
        "pattern": "before_after",
        "language": "en",
        "psychology": ["transformation", "aspiration"],
        "emotion": "aspiration",
        "render": lambda s, a: f"Here's what changes the moment {s} finally clicks.",
        "base": {"emotional": 78, "payoff": 82, "curiosity": 74, "visual_potential": 80},
    },
    {
        "category": "myth",
        "pattern": "bust_myth",
        "language": "en",
        "psychology": ["contradiction", "credibility"],
        "emotion": "surprise",
        "render": lambda s, a: f"The most repeated advice about {s} is quietly wrong.",
        "base": {"novelty": 78, "credibility": 70, "curiosity": 80, "attention": 76},
    },
    {
        "category": "hinglish",
        "pattern": "insider_secret",
        "language": "hinglish",
        "psychology": ["curiosity", "authority"],
        "emotion": "curiosity",
        "render": lambda s, a: f"{s} ke baare mein ye baat koi nahi batata.",
        "base": {"attention": 84, "curiosity": 86, "authenticity": 80, "audience_fit": 78},
    },
    {
        "category": "hinglish",
        "pattern": "challenge_belief",
        "language": "hinglish",
        "psychology": ["contradiction", "identity"],
        "emotion": "surprise",
        "render": lambda s, a: f"Sab bol rahe the {s} aise nahi chalega - galat the.",
        "base": {"attention": 83, "novelty": 76, "emotional": 74, "audience_fit": 80},
    },
    {
        "category": "hindi",
        "pattern": "direct_question",
        "language": "hi",
        "psychology": ["curiosity", "relevance"],
        "emotion": "curiosity",
        "render": lambda s, a: f"{s} itna mushkil kyun lagta hai, pata hai?",
        "base": {"curiosity": 80, "relevance": 82, "authenticity": 82, "audience_fit": 80},
    },
    {
        "category": "indian-en",
        "pattern": "fast_win",
        "language": "indian-en",
        "psychology": ["usefulness", "specificity"],
        "emotion": "aspiration",
        "render": lambda s, a: f"One simple shift and {s} finally gets easy.",
        "base": {"clarity": 84, "payoff": 78, "platform_fit": 80, "audience_fit": 78},
    },
)

# Second pass of variants so we always clear MIN_HOOKS with genuine variety:
# re-skin the strongest patterns with different angles.
_VARIANT_SUFFIXES: tuple[dict[str, Any], ...] = (
    {
        "tag": "specific",
        "psychology": ["specificity"],
        "render": lambda s, a: f"The one detail about {s} that changes the whole outcome.",
        "base": {"specificity": 84, "clarity": 80, "payoff": 76, "curiosity": 74},
        "category": "practical",
        "pattern": "single_detail",
        "language": "en",
        "emotion": "curiosity",
    },
    {
        "tag": "mistake",
        "psychology": ["loss_aversion"],
        "render": lambda s, a: f"This tiny mistake with {s} costs people the most.",
        "base": {"attention": 80, "emotional": 76, "curiosity": 78, "relevance": 78},
        "category": "cost",
        "pattern": "small_mistake",
        "language": "en",
        "emotion": "concern",
    },
    {
        "tag": "proof",
        "psychology": ["credibility", "proof"],
        "render": lambda s, a: f"I tested the usual advice on {s}. Here's what actually held up.",
        "base": {"credibility": 82, "authenticity": 82, "payoff": 78, "specificity": 76},
        "category": "data",
        "pattern": "tested_claim",
        "language": "en",
        "emotion": "surprise",
    },
    {
        "tag": "reframe",
        "psychology": ["novelty", "transformation"],
        "render": lambda s, a: f"Stop thinking of {s} as hard. Think of it like this.",
        "base": {"novelty": 80, "clarity": 78, "emotional": 74, "payoff": 76},
        "category": "transformation",
        "pattern": "reframe",
        "language": "en",
        "emotion": "aspiration",
    },
    {
        "tag": "insider-en",
        "psychology": ["authority", "curiosity"],
        "render": lambda s, a: f"What people who are great at {s} never say out loud.",
        "base": {"curiosity": 84, "credibility": 80, "attention": 80, "novelty": 76},
        "category": "authority",
        "pattern": "unspoken_rule",
        "language": "en",
        "emotion": "curiosity",
    },
    {
        "tag": "question-stakes",
        "psychology": ["curiosity", "loss_aversion"],
        "render": lambda s, a: f"What if the way you learned {s} was the slow way?",
        "base": {"curiosity": 82, "attention": 76, "emotional": 74, "relevance": 78},
        "category": "question",
        "pattern": "what_if",
        "language": "en",
        "emotion": "curiosity",
    },
    {
        "tag": "story-turn",
        "psychology": ["story", "transformation"],
        "render": lambda s, a: f"The day {s} finally made sense, everything got easier.",
        "base": {"authenticity": 84, "emotional": 80, "payoff": 78, "visual_potential": 76},
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


def _score_hook(
    template: dict[str, Any],
    text: str,
    subject: str,
    strategy_emotion: str,
    language_target: str,
) -> tuple[dict[str, int], int, str]:
    base = template.get("base", {})
    scores: dict[str, int] = {}
    for dim in SCORE_DIMS:
        # Start from the template's structural strength for this dim, or a
        # neutral 65 if the template is silent on it.
        start = base.get(dim)
        if not start:
            start = 65
        # Deterministic +/-6 jitter keyed by (text, dim) so ranking is stable
        # but not perfectly flat across hooks.
        jitter = (_det_unit(f"{text}|{dim}") - 0.5) * 12
        value = start + jitter
        # Emotion alignment nudges emotional/relevance up.
        if dim in ("emotional", "relevance") and template.get("emotion") == strategy_emotion:
            value += 5
        # Platform fit: short lines favored on Reels.
        if dim == "platform_fit":
            value += 6 if len(text) <= 70 else -6
        # Language fit: reward matching the strategy's target language.
        if dim == "audience_fit" and template.get("language") == language_target:
            value += 6
        scores[dim] = _clamp(value)

    # Originality: penalise tired templates.
    fatigue_score, fatigue_reason = _template_fatigue(text)
    if fatigue_score >= 80:
        scores["originality"] = _clamp(scores["originality"] - 30)

    return scores, fatigue_score, fatigue_reason


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


def build_hooks(
    strategy_artifact: Artifact,
    project_id: str,
    *,
    identity: Identity | None = None,
    prior_hooks: list[str] | None = None,
) -> Artifact:
    """Produce a ``hooks`` artifact (>=20 scored, ranked hooks) from strategy.

    ``prior_hooks`` is an optional list of hook texts this creator has used
    before, enabling the originality + hook-fatigue checks. In Phase 1 this is
    typically empty; it is wired for SCRIPT memory in later phases.
    """
    subject = _subject(strategy_artifact)
    strategy_emotion = _strategy_field(strategy_artifact, "emotion", "curiosity")
    language_target = (strategy_artifact.body or {}).get("language", "en")
    action = "save"
    prior_texts = list(prior_hooks or [])

    templates = list(_TEMPLATES) + list(_VARIANT_SUFFIXES)

    generated: list[dict[str, Any]] = []
    seen_texts: list[str] = []
    for idx, template in enumerate(templates):
        text = template["render"](subject, action).strip()
        scores, tmpl_fatigue, tmpl_reason = _score_hook(
            template, text, subject, strategy_emotion, language_target
        )
        aggregate = _aggregate(scores)
        originality = _originality_verdict(text, prior_texts + seen_texts)
        # Hook fatigue: has this creator already used a near-identical hook?
        hook_fatigue = _clamp(
            80 if originality["distance"] <= 0.4 and prior_texts else 12
        )
        hook_id = f"hook-{hashlib.sha256(text.encode('utf-8')).hexdigest()[:10]}"
        generated.append(
            {
                "hook_id": hook_id,
                "scores": scores,
                "aggregate": aggregate,
                "hook_fatigue_score": hook_fatigue,
                "template_fatigue_score": tmpl_fatigue,
                "template_fatigue_reason": tmpl_reason,
                "originality": originality,
                "first_three_seconds": _first_three_seconds(template, subject),
                "metadata": {
                    "hook": text,
                    "language": template.get("language", "en"),
                    "category": template.get("category", "general"),
                    "pattern": template.get("pattern", "unknown"),
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

    # Rank by aggregate (desc), tie-broken by hook_id for determinism.
    ranked = sorted(
        generated, key=lambda h: (-h["aggregate"], h["hook_id"])
    )
    for rank, hook in enumerate(ranked, start=1):
        hook["rank"] = rank

    selected_hook_id = ranked[0]["hook_id"] if ranked else None
    ab_variants = _ab_variants(ranked)

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
            "highest aggregate across 15 dimensions; ties broken deterministically "
            "by hook id (reproducible, ASUR-HONEST-01)"
        ),
        "first_three_seconds_blueprint": (
            "0.0-0.5s pattern interrupt / 0.5-1.5s core hook / "
            "1.5-2.5s curiosity promise / 2.5-3.0s transition"
        ),
        "method": "local heuristic hook engine; deterministic scoring; no network",
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
