"""P06 five-family final QA on the fully rendered video.

Five QA families run on the ACTUAL rendered output (stage 22 "rendered output is
truth"): visual, audio, text/typography, content, platform. ASUR cannot
auto-certify creative or photorealistic quality (ASUR-HONEST-01), so the
subjective checks -- especially the ideas-3 anti-AI "Human Pass Test" (G17) --
are recorded as reviewer decisions on the real output. A required human-review
check with no recorded decision fails closed to HOLD (ASUR-GATE-01). Structural
checks (dimensions, duration band) are machine-decidable and run offline on tiny
fixtures (no GPU, no network, never a real model -- the G10 pattern).
"""

from __future__ import annotations

from typing import Any

from ..core.envelope import Artifact, make_artifact
from ..core.identity import Identity
from . import source_ref

QA_FAMILIES = ("visual", "audio", "text_typography", "content", "platform")

# G17 -- ideas-3 anti-AI "Human Pass Test" named checks. Each is a MANUAL review
# flag: ASUR prompts a human to confirm it on the real render, it never claims to
# measure photorealism itself. Missing decision => HOLD (fail closed).
HUMAN_PASS_CHECKS = (
    "human_pass_test",          # passes as 100% human-created live-action
    "natural_motion",           # micro-expressions, blinking, hair sway
    "skin_texture",             # pores/imperfections, no plastic AI skin
    "lighting_shadow_continuity",
    "physics_continuity",       # no morphing/warping/glitching-hands/floating-objects
    "color_grading",            # context-aware; no flat/over-saturated AI palette
)

_PASS = "pass"
_FAIL = "fail"
_HOLD = "hold"
_WARN = "warn"

_REEL_WIDTH = 1080
_REEL_HEIGHT = 1920


def _review_check(name: str, reviews: dict[str, Any]) -> dict[str, Any]:
    """A manual-review check. reviews maps check name -> 'approved'|'rejected'.

    Not recorded => HOLD (ASUR cannot self-certify). 'rejected' => FAIL.
    'approved' => PASS. ASUR-EXPLAIN-01: always carries a reason.
    """
    decision = reviews.get(name)
    if decision is None:
        return {"check": name, "status": _HOLD, "reason": f"'{name}' not reviewed on the rendered output"}
    if decision == "rejected":
        return {"check": name, "status": _FAIL, "reason": f"reviewer rejected '{name}'"}
    if decision == "approved":
        return {"check": name, "status": _PASS, "reason": f"reviewer approved '{name}'"}
    return {"check": name, "status": _HOLD, "reason": f"'{name}' has an unknown decision '{decision}'"}


def _family_status(checks: list[dict[str, Any]]) -> str:
    """Worst-of family status: fail dominates, then hold, then warn, then pass."""
    statuses = {c["status"] for c in checks}
    for worst in (_FAIL, _HOLD, _WARN):
        if worst in statuses:
            return worst
    return _PASS


def visual_family(reviews: dict[str, Any]) -> dict[str, Any]:
    """Visual QA = the ideas-3 anti-AI Human Pass Test, all manual-review flags."""
    checks = [_review_check(name, reviews) for name in HUMAN_PASS_CHECKS]
    return {"family": "visual", "status": _family_status(checks), "checks": checks}


def audio_family(reviews: dict[str, Any]) -> dict[str, Any]:
    checks = [
        _review_check("voice_clear", reviews),
        _review_check("music_not_burying_voice", reviews),
        _review_check("no_clipping", reviews),
    ]
    return {"family": "audio", "status": _family_status(checks), "checks": checks}


def text_typography_family(reviews: dict[str, Any]) -> dict[str, Any]:
    checks = [
        _review_check("captions_readable", reviews),
        _review_check("safe_area_respected", reviews),
        _review_check("shaping_correct", reviews),  # Devanagari hi/hinglish/mr
    ]
    return {"family": "text_typography", "status": _family_status(checks), "checks": checks}


def content_family(reviews: dict[str, Any]) -> dict[str, Any]:
    checks = [
        _review_check("matches_approved_script", reviews),
        _review_check("no_drift_from_hero_proof", reviews),
    ]
    return {"family": "content", "status": _family_status(checks), "checks": checks}


def platform_family(
    *,
    width: int,
    height: int,
    duration_s: float,
    target_band_s: tuple[float, float] | None = None,
) -> dict[str, Any]:
    """Platform QA = machine-decidable structural checks (no review needed).

    Dimensions must be exactly 1080x1920 (9:16). Duration-band (G16): if a target
    band is declared on the brief, a duration outside it is a WARNING, never a
    hard fail -- ASUR keeps the 60s default band-free.
    """
    checks: list[dict[str, Any]] = []

    if width == _REEL_WIDTH and height == _REEL_HEIGHT:
        checks.append({"check": "dimensions", "status": _PASS, "reason": "1080x1920 9:16"})
    else:
        checks.append({"check": "dimensions", "status": _FAIL, "reason": f"{width}x{height} is not 1080x1920"})

    if target_band_s is None:
        checks.append({"check": "duration_band", "status": _PASS, "reason": "no target band declared (default)"})
    else:
        low, high = target_band_s
        if low <= duration_s <= high:
            checks.append({"check": "duration_band", "status": _PASS, "reason": f"{duration_s}s within {low}-{high}s"})
        else:
            checks.append({"check": "duration_band", "status": _WARN, "reason": f"{duration_s}s outside target {low}-{high}s"})

    return {"family": "platform", "status": _family_status(checks), "checks": checks}


def run_final_qa(
    *,
    width: int = _REEL_WIDTH,
    height: int = _REEL_HEIGHT,
    duration_s: float = 60.0,
    target_band_s: tuple[float, float] | None = None,
    reviews: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run all five QA families. Returns {disposition, substate, families}.

    Disposition: BLOCK if any family fails; else HOLD if any family is awaiting a
    human review (fail closed per ASUR-HONEST-01/GATE-01); else SHIP. Warnings
    (e.g. duration band) do not block.
    """
    reviews = reviews or {}
    families = [
        visual_family(reviews),
        audio_family(reviews),
        text_typography_family(reviews),
        content_family(reviews),
        platform_family(width=width, height=height, duration_s=duration_s, target_band_s=target_band_s),
    ]
    statuses = {f["status"] for f in families}
    if _FAIL in statuses:
        disposition, substate = "BLOCK", "QA_FAILED"
    elif _HOLD in statuses:
        disposition, substate = "HOLD", "HUMAN_REVIEW_REQUIRED"
    else:
        disposition, substate = "SHIP", None
    return {"disposition": disposition, "substate": substate, "families": families}


def build_final_qa_report(
    edit_plan_artifact: Artifact,
    project_id: str,
    *,
    width: int = _REEL_WIDTH,
    height: int = _REEL_HEIGHT,
    duration_s: float = 60.0,
    target_band_s: tuple[float, float] | None = None,
    reviews: dict[str, Any] | None = None,
    identity: Identity | None = None,
) -> Artifact:
    """Emit a qa_report for the 5-family final QA on the rendered video.

    status='ready' only on SHIP; 'rejected' on BLOCK or HOLD (fail closed -- the
    video is not final-QA-clean until a human records the anti-AI review).
    """
    result = run_final_qa(
        width=width,
        height=height,
        duration_s=duration_s,
        target_band_s=target_band_s,
        reviews=reviews,
    )
    body = {
        "stage": "final_qa",
        "disposition": result["disposition"],
        "substate": result["substate"],
        "families": result["families"],
        "family_names": list(QA_FAMILIES),
        "human_pass_checks": list(HUMAN_PASS_CHECKS),
        "note": (
            "Five-family final QA on the ACTUAL rendered output. The visual "
            "family is the anti-AI Human Pass Test: ASUR cannot certify "
            "photorealism, so each is a reviewer decision recorded on the real "
            "render. A missing decision holds; a rejection blocks."
        ),
        "method": "local stdlib checks + recorded human reviews; no media decoded; no network",
    }
    return make_artifact(
        kind="qa_report",
        project_id=project_id,
        body=body,
        status="ready" if result["disposition"] == "SHIP" else "rejected",
        sources=[source_ref(edit_plan_artifact)],
        agent="qa",
        identity=identity,
    )
