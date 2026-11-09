"""Stage 7 - script quality gate (local, fail-closed).

Runs thirteen checks over a ``script`` artifact before Phase 1 is allowed to
finish. Built on ``core.gate`` (``run_gate`` + ``Check``). Each check returns a
``(disposition, reason)`` pair; any failure returns HOLD so the pipeline does
not silently advance to GENERATION with a weak script (ASUR-GATE-01). No
network (ASUR-LOCAL-01).

Checks are content checks, not "section exists" checks: hook length and hook
score floor, a concrete creator/LLM takeaway (a generic template value line
HOLDs), unsourced statistics and invented first-person anecdotes, near-duplicate
lines and mechanical subject repetition, a real CTA verb, contiguous timings, and
the estimated duration against the target platform's band.

The gate is deliberately a quality floor, not a viral predictor - it never
produces a "% viral" number (ASUR-HONEST-01). It only answers: "Is this script
structurally strong enough to build on?" The result is wrapped in a
``qa_report`` artifact so the decision and its reasons are versioned and
explainable (ASUR-EXPLAIN-01, ASUR-VERSION-01 when saved).

The firewall note: this gate reads only the script-side artifact. It encodes
*quality floors*, never the VIRAL CHECK instrument's pass criteria
(ASUR-FIREWALL-01).
"""

from __future__ import annotations

import re
from typing import Any

from ..core.envelope import Artifact, make_artifact
from ..core.gate import HOLD, SHIP, Check, GateResult, run_gate
from ..core.identity import Identity
from ..platforms import get_platform
from . import source_ref
from .script_builder import SECTION_ORDER

GATE_NAME = "script_quality"

# The thirteen required checks (DATA_MODELS/MVP script quality gate).
CHECK_NAMES = (
    "strong_opening",
    "clear_audience",
    "clear_promise",
    "coherent_story",
    "useful_info",
    "emotional_engagement",
    "credible_claims",
    "no_unnecessary_repetition",
    "strong_payoff",
    "appropriate_cta",
    "platform_suitability",
    "originality",
    "authenticity",
)

# Thresholds (all documented, all checkable by hand).
_HOOK_WORDS = (4, 14)          # a hook must land inside the first ~5s of narration
_MIN_HOOK_AGGREGATE = 65       # selected hook's feature score floor (hooks.py)
_MIN_VALUE_WORDS = 8           # the takeaway line must say something concrete
_MAX_SUBJECT_REPEATS = 4       # subject phrase named in at most 4 sections
_NEAR_DUPLICATE = 0.6          # word-set Jaccard overlap that counts as repetition
_MIN_DURATION_S = 5.0
_UNBANDED_MAX_S = 180.0        # Reels/Shorts upload ceiling when no band is declared
_CTA_VERBS = frozenset(
    "save share send follow comment subscribe try download join tell watch".split()
)
_STAT_CLAIM = re.compile(
    r"\b\d+\s*%|\b\d+ out of \d+\b|\b(one|two|three|four|five|six|seven|eight|nine) "
    r"out of (ten|\w+)\b|\bstudies (show|prove)\b|\bscience says\b",
    re.IGNORECASE,
)
_FIRST_PERSON_CLAIM = re.compile(
    r"\bi(?:'ve| have)? (tested|wasted|learned|spent|tried|lost|made|discovered)\b"
    r"|\bafter years\b|\bthe hard way\b",
    re.IGNORECASE,
)
_WORD = re.compile(r"[a-z0-9']+")


def _words(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def _overlap(a: str, b: str) -> float:
    wa, wb = _words(a), _words(b)
    return len(wa & wb) / len(wa | wb) if wa and wb else 0.0


def _parse_timing(timing: str) -> tuple[float, float] | None:
    try:
        start, end = timing.rstrip("s").split("-", 1)
        return float(start), float(end)
    except (ValueError, AttributeError):
        return None


def _sections(script_artifact: Artifact) -> dict[str, Any]:
    return (script_artifact.body or {}).get("sections", {}) or {}


def _spoken(section: dict[str, Any]) -> str:
    return (section or {}).get("spoken_words", "") or ""


def _selected_hook(hooks_artifact: Artifact | None) -> dict[str, Any] | None:
    if hooks_artifact is None:
        return None
    body = hooks_artifact.body or {}
    for h in body.get("hooks", []):
        if h.get("hook_id") == body.get("selected_hook_id"):
            return h
    return None


def _build_checks(
    script_artifact: Artifact,
    hooks_artifact: Artifact | None,
    strategy_artifact: Artifact | None,
) -> list[Check]:
    body = script_artifact.body or {}
    sections = _sections(script_artifact)
    hook_text = _spoken(sections.get("hook", {}))
    subject = str(body.get("subject", "") or "")
    strategy_body = (strategy_artifact.body or {}) if strategy_artifact else {}
    all_spoken = {name: _spoken(sec) for name, sec in sections.items()}

    def strong_opening() -> tuple[str, str]:
        n = len(hook_text.split())
        if not hook_text.strip():
            return HOLD, "hook section has no spoken words"
        if not _HOOK_WORDS[0] <= n <= _HOOK_WORDS[1]:
            return HOLD, f"hook is {n} words; must be {_HOOK_WORDS[0]}-{_HOOK_WORDS[1]} to land in ~5s"
        hook = _selected_hook(hooks_artifact)
        if hook is not None and int(hook.get("aggregate", 0)) < _MIN_HOOK_AGGREGATE:
            return HOLD, (f"selected hook scores {hook.get('aggregate')} "
                          f"(< {_MIN_HOOK_AGGREGATE} on the hook feature model)")
        return SHIP, f"hook is {n} words and clears the hook-score floor"

    def clear_audience() -> tuple[str, str]:
        if strategy_artifact is None:
            return HOLD, "no strategy artifact to confirm audience"
        aud = strategy_body.get("audience_summary") or {}
        value = aud.get("value") if isinstance(aud, dict) else aud
        if not value:
            return HOLD, "strategy has no audience summary"
        if not subject.strip() or subject.strip().lower() == "the topic":
            return HOLD, "subject could not be extracted from the idea (placeholder 'the topic')"
        return SHIP, "audience and subject defined"

    def clear_promise() -> tuple[str, str]:
        payoff = all_spoken.get("payoff", "")
        if not payoff.strip() or not all_spoken.get("value", "").strip():
            return HOLD, "value or payoff line is missing"
        if subject and not (_words(subject) & _words(payoff + " " + all_spoken.get("value", ""))):
            return HOLD, "value/payoff never refer back to the subject"
        return SHIP, "promise stated and tied to the subject"

    def coherent_story() -> tuple[str, str]:
        required = ("hook", "opening", "problem", "payoff", "cta")
        missing = [name for name in required if not all_spoken.get(name, "").strip()]
        if missing:
            return HOLD, f"missing spoken content in sections: {', '.join(missing)}"
        cursor = None
        # Walk in narrative order (stored JSON sorts keys, so dict order is not it).
        for name in SECTION_ORDER:
            sec = sections.get(name)
            span = _parse_timing((sec or {}).get("timing", ""))
            if span is None or span[1] <= span[0]:
                return HOLD, f"section {name!r} has no valid timing"
            if cursor is not None and abs(span[0] - cursor) > 0.05:
                return HOLD, f"section {name!r} timing is not contiguous with the previous one"
            cursor = span[1]
        return SHIP, "core sections present with contiguous timings"

    def useful_info() -> tuple[str, str]:
        value = all_spoken.get("value", "")
        if body.get("value_source") == "template-generic":
            return HOLD, ("no concrete takeaway: the value line is a generic template; "
                          "pass --takeaway or enable an LLM (ASUR_LLM)")
        if len(value.split()) < _MIN_VALUE_WORDS:
            return HOLD, f"value line has fewer than {_MIN_VALUE_WORDS} words"
        return SHIP, f"value line carries a concrete takeaway (source: {body.get('value_source', '?')})"

    def emotional_engagement() -> tuple[str, str]:
        emotions = {(sec or {}).get("emotion", "") for sec in sections.values()}
        emotions.discard("")
        if len(emotions) < 3:
            return HOLD, f"script is emotionally flat ({len(emotions)} distinct emotions, need 3)"
        return SHIP, f"emotional range present ({len(emotions)} distinct emotions)"

    def credible_claims() -> tuple[str, str]:
        if not all_spoken.get("proof", "").strip():
            return HOLD, "proof section empty - claims are unsupported"
        stats = [n for n, t in all_spoken.items() if _STAT_CLAIM.search(t)]
        if stats:
            return HOLD, f"unsourced statistic in: {', '.join(stats)} (cite a source or remove it)"
        return SHIP, "no unsourced statistics; proof beat present"

    def no_unnecessary_repetition() -> tuple[str, str]:
        names = [n for n in SECTION_ORDER if all_spoken.get(n, "").strip()]
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                if _overlap(all_spoken[a], all_spoken[b]) >= _NEAR_DUPLICATE:
                    return HOLD, f"sections {a!r} and {b!r} are near-duplicates"
        if subject:
            repeats = sum(1 for t in all_spoken.values() if subject.lower() in t.lower())
            if repeats > _MAX_SUBJECT_REPEATS:
                return HOLD, (f"subject phrase repeated in {repeats} sections "
                              f"(max {_MAX_SUBJECT_REPEATS}); reads as a template")
        return SHIP, "no near-duplicate lines; subject not mechanically repeated"

    def strong_payoff() -> tuple[str, str]:
        payoff = all_spoken.get("payoff", "")
        if not payoff.strip():
            return HOLD, "payoff section is empty"
        if _overlap(payoff, hook_text) >= _NEAR_DUPLICATE:
            return HOLD, "payoff just repeats the hook"
        return SHIP, "payoff closes the loop with new words"

    def appropriate_cta() -> tuple[str, str]:
        cta = all_spoken.get("cta", "")
        if not cta.strip():
            return HOLD, "cta section is empty - no clear ask"
        if not (_words(cta) & _CTA_VERBS):
            return HOLD, "cta has no concrete action verb (save/share/follow/...)"
        return SHIP, "cta asks for a concrete action"

    def platform_suitability() -> tuple[str, str]:
        dur = body.get("estimated_duration_s", 0)
        if not isinstance(dur, (int, float)) or dur <= 0:
            return HOLD, "no estimated duration"
        platform_id = strategy_body.get("platform") or "instagram_reels"
        try:
            band = get_platform(platform_id).format_spec.duration_band_s
        except Exception:
            return HOLD, f"unknown platform {platform_id!r}"
        low, high = band if band else (_MIN_DURATION_S, _UNBANDED_MAX_S)
        if not low <= dur <= high:
            return HOLD, f"estimated {dur}s is outside {platform_id} band {low:g}-{high:g}s"
        return SHIP, f"estimated {dur}s fits {platform_id} ({low:g}-{high:g}s)"

    def originality() -> tuple[str, str]:
        if hooks_artifact is None:
            return HOLD, "no hooks artifact to judge originality"
        h = _selected_hook(hooks_artifact)
        if h is None:
            return HOLD, "selected hook not found in hooks artifact"
        if h.get("template_fatigue_score", 0) >= 80:
            return HOLD, "selected hook relies on a tired template"
        verdict = (h.get("originality", {}) or {}).get("verdict", "")
        if verdict == "derivative":
            return HOLD, "selected hook is derivative of a prior hook"
        return SHIP, f"selected hook originality: {verdict or 'original'}"

    def authenticity() -> tuple[str, str]:
        if not all_spoken.get("story", "").strip():
            return HOLD, "story section empty - script lacks a human beat"
        claims = [n for n, t in all_spoken.items() if _FIRST_PERSON_CLAIM.search(t)]
        if claims:
            return HOLD, (f"first-person experience claimed in: {', '.join(claims)} - "
                          "only keep it if it really happened to the creator")
        return SHIP, "no fabricated personal-experience claims"

    fns = {
        "strong_opening": strong_opening,
        "clear_audience": clear_audience,
        "clear_promise": clear_promise,
        "coherent_story": coherent_story,
        "useful_info": useful_info,
        "emotional_engagement": emotional_engagement,
        "credible_claims": credible_claims,
        "no_unnecessary_repetition": no_unnecessary_repetition,
        "strong_payoff": strong_payoff,
        "appropriate_cta": appropriate_cta,
        "platform_suitability": platform_suitability,
        "originality": originality,
        "authenticity": authenticity,
    }
    return [Check(name=name, fn=fns[name]) for name in CHECK_NAMES]


def run_quality_gate(
    script_artifact: Artifact,
    *,
    hooks_artifact: Artifact | None = None,
    strategy_artifact: Artifact | None = None,
) -> GateResult:
    """Run the 13-check gate over a script artifact and return the GateResult."""
    checks = _build_checks(script_artifact, hooks_artifact, strategy_artifact)
    return run_gate(GATE_NAME, checks)


def build_qa_report(
    script_artifact: Artifact,
    project_id: str,
    *,
    hooks_artifact: Artifact | None = None,
    strategy_artifact: Artifact | None = None,
    identity: Identity | None = None,
) -> tuple[Artifact, GateResult]:
    """Run the gate and wrap the result in a versioned ``qa_report`` artifact.

    Returns ``(qa_report_artifact, gate_result)``. The artifact status is
    ``ready`` if the gate passed (SHIP) else ``rejected`` (HOLD/BLOCK), making
    the fail-closed decision explicit and versioned.
    """
    result = run_quality_gate(
        script_artifact,
        hooks_artifact=hooks_artifact,
        strategy_artifact=strategy_artifact,
    )
    sources = [source_ref(script_artifact)]
    if hooks_artifact is not None:
        sources.append(source_ref(hooks_artifact))

    body = {
        "gate": GATE_NAME,
        "stage": "script_quality",
        "disposition": result.disposition,
        "substate": result.substate,
        "passed": result.passed,
        "checks_total": len(CHECK_NAMES),
        "reasons": result.reasons,
        "note": (
            "Quality floor only - this is not a viral prediction and carries no "
            "'% viral' number (ASUR-HONEST-01). Fail-closed: any HOLD/BLOCK "
            "sends the script back rather than advancing to GENERATION."
        ),
    }
    status = "ready" if result.disposition == SHIP else "rejected"

    artifact = make_artifact(
        kind="qa_report",
        project_id=project_id,
        body=body,
        status=status,
        sources=sources,
        agent="qa",
        identity=identity,
    )
    return artifact, result
