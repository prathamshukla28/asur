"""Stage 7 - script quality gate (local, fail-closed).

Runs thirteen checks over a ``script`` artifact before Phase 1 is allowed to
finish. Built on ``core.gate`` (``run_gate`` + ``Check``). Each check returns a
``(disposition, reason)`` pair; any failure returns HOLD so the pipeline does
not silently advance to GENERATION with a weak script (ASUR-GATE-01). No
network (ASUR-LOCAL-01).

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

from typing import Any

from ..core.envelope import Artifact, make_artifact
from ..core.gate import HOLD, SHIP, Check, GateResult, run_gate
from ..core.identity import Identity
from . import source_ref

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

_MIN_HOOK_LEN = 8
_MAX_HOOK_LEN = 160


def _sections(script_artifact: Artifact) -> dict[str, Any]:
    return (script_artifact.body or {}).get("sections", {}) or {}


def _spoken(section: dict[str, Any]) -> str:
    return (section or {}).get("spoken_words", "") or ""


def _build_checks(
    script_artifact: Artifact,
    hooks_artifact: Artifact | None,
    strategy_artifact: Artifact | None,
) -> list[Check]:
    body = script_artifact.body or {}
    sections = _sections(script_artifact)
    hook = sections.get("hook", {})
    hook_text = _spoken(hook)

    def strong_opening() -> tuple[str, str]:
        if not hook_text.strip():
            return HOLD, "hook section has no spoken words"
        if len(hook_text) < _MIN_HOOK_LEN:
            return HOLD, f"hook too short ({len(hook_text)} chars) to grab attention"
        return SHIP, "hook present and substantive"

    def clear_audience() -> tuple[str, str]:
        if strategy_artifact is None:
            return HOLD, "no strategy artifact to confirm audience"
        aud = (strategy_artifact.body or {}).get("audience_summary") or {}
        if not (aud.get("value") if isinstance(aud, dict) else aud):
            return HOLD, "strategy has no audience summary"
        return SHIP, "audience defined in strategy"

    def clear_promise() -> tuple[str, str]:
        payoff = _spoken(sections.get("payoff", {}))
        value = _spoken(sections.get("value", {}))
        if not payoff.strip() and not value.strip():
            return HOLD, "no value or payoff promise in the script"
        return SHIP, "promise present (value + payoff sections filled)"

    def coherent_story() -> tuple[str, str]:
        required = ("hook", "opening", "problem", "payoff", "cta")
        missing = [name for name in required if not _spoken(sections.get(name, {})).strip()]
        if missing:
            return HOLD, f"missing spoken content in sections: {', '.join(missing)}"
        return SHIP, "core narrative sections are all present"

    def useful_info() -> tuple[str, str]:
        if not _spoken(sections.get("value", {})).strip():
            return HOLD, "value section is empty - no useful takeaway"
        return SHIP, "value section delivers a takeaway"

    def emotional_engagement() -> tuple[str, str]:
        emotions = {
            (sec or {}).get("emotion", "") for sec in sections.values()
        }
        emotions.discard("")
        if len(emotions) < 2:
            return HOLD, "script is emotionally flat (fewer than 2 distinct emotions)"
        return SHIP, f"emotional range present ({len(emotions)} distinct emotions)"

    def credible_claims() -> tuple[str, str]:
        proof = _spoken(sections.get("proof", {}))
        if not proof.strip():
            return HOLD, "proof section empty - claims are unsupported"
        return SHIP, "proof section backs the claims"

    def no_unnecessary_repetition() -> tuple[str, str]:
        spokens = [
            _spoken(sec).strip().lower()
            for sec in sections.values()
            if _spoken(sec).strip()
        ]
        if len(spokens) != len(set(spokens)):
            return HOLD, "two or more sections have identical spoken words"
        return SHIP, "no duplicate spoken lines across sections"

    def strong_payoff() -> tuple[str, str]:
        payoff = _spoken(sections.get("payoff", {}))
        if not payoff.strip():
            return HOLD, "payoff section is empty"
        return SHIP, "payoff section closes the loop"

    def appropriate_cta() -> tuple[str, str]:
        cta = _spoken(sections.get("cta", {}))
        if not cta.strip():
            return HOLD, "cta section is empty - no clear ask"
        return SHIP, "cta present with a clear ask"

    def platform_suitability() -> tuple[str, str]:
        dur = body.get("estimated_duration_s", 0)
        if not isinstance(dur, (int, float)) or dur <= 0:
            return HOLD, "no estimated duration"
        if dur > 90:
            return HOLD, f"estimated {dur}s exceeds Reels sweet spot"
        return SHIP, f"estimated {dur}s fits Instagram Reels"

    def originality() -> tuple[str, str]:
        if hooks_artifact is None:
            return HOLD, "no hooks artifact to judge originality"
        selected_id = (hooks_artifact.body or {}).get("selected_hook_id")
        for h in (hooks_artifact.body or {}).get("hooks", []):
            if h.get("hook_id") == selected_id:
                tmpl_fatigue = h.get("template_fatigue_score", 0)
                if tmpl_fatigue >= 80:
                    return HOLD, "selected hook relies on a tired template"
                verdict = (h.get("originality", {}) or {}).get("verdict", "")
                if verdict == "derivative":
                    return HOLD, "selected hook is derivative of a prior hook"
                return SHIP, f"selected hook originality: {verdict or 'original'}"
        return HOLD, "selected hook not found in hooks artifact"

    def authenticity() -> tuple[str, str]:
        story = _spoken(sections.get("story", {}))
        if not story.strip():
            return HOLD, "story section empty - script lacks a human/authentic beat"
        return SHIP, "story section grounds the script in an authentic voice"

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
