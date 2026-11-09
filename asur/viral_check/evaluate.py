"""VIRAL CHECK verdict: twelve dimensions, risk flags, no single %viral.

This is the evaluation instrument. It reads ONLY the VIRAL_VIEW
projection (ASUR-FIREWALL-01) - it never imports or reads anything
from GENERATION, and it never sees the author's targets. The facts it
judges are measured from the rendered MP4 by ``probe.measure_video``
(ffprobe/ffmpeg) and assembled by ``facts.build_platform_facts``; see
``dimensions.py`` for every formula. A dimension with no measurable
input is reported as unknown rather than given a made-up number.

Honesty rules (ASUR-HONEST-01):
  1. No single "%viral" number. Only the twelve individual 0-100 scores.
  2. Penalties are BINARY RISK FLAGS, never percentage deductions.
  3. The verdict is PASS / PASS-WITH-CHANGES / REJECT.
"""

from __future__ import annotations

from ..core.envelope import Artifact, make_artifact
from ..core.identity import Identity
from . import source_ref
from .dimensions import score_all

# Verdict vocabulary (closed set).
PASS = "PASS"
PASS_WITH_CHANGES = "PASS-WITH-CHANGES"
REJECT = "REJECT"

# Thresholds on individual dimensions (never aggregated).
_WEAK_DIMENSION = 55

# Measured-risk thresholds (documented; each flag records the measured value).
_MIN_SHORT_SIDE_PX = 720        # below 720p-equivalent -> low resolution
_LOUDNESS_TOLERANCE_LU = 6.0    # further than this from -14 LUFS -> loudness risk
_LONG_SILENCE_S = 2.0           # a silent gap this long inside the video
_MOSTLY_STATIC = 0.5            # half the runtime frozen (freezedetect)
_MAX_CAPTION_WPS = 3.5          # faster than comfortable reading speed
_DIGITAL_SILENCE_DB = -60.0     # mean volume at/below this counts as muted

# Declared (human-judged) facts that trigger a binary risk flag.
_DECLARED_RULES = (
    ("visible_watermark", True,
     "RISK: visible watermark -> reposted/watermarked suppression on Instagram"),
    ("reposted_elsewhere", True,
     "RISK: already posted elsewhere -> originality ineligibility on Instagram"),
    ("low_resolution", True,
     "RISK: low resolution -> Instagram demotes low-res Reels"),
    ("muted", False,
     "RISK: no audio -> Instagram demotes muted Reels"),
    ("bordered", False,
     "RISK: visible borders -> Instagram demotes bordered Reels"),
    ("majority_text", False,
     "RISK: majority on-screen text -> Instagram demotes text-heavy Reels"),
)


def _facts(view: dict) -> dict:
    facts = view.get("platform_facts")
    return facts if isinstance(facts, dict) else {}


def _flag(code: str, hard: bool, message: str, measured: object = None) -> dict:
    return {"code": code, "flag": message, "hard": hard, "measured": measured}


def _measured_flags(f: dict) -> list[dict]:
    flags: list[dict] = []
    if f.get("aspect_matches") is False:
        flags.append(_flag("wrong_aspect", True,
                           f"RISK: aspect {f.get('aspect_ratio')} is not the platform's "
                           f"{f.get('expected_aspect_ratio')} -> letterboxed/cropped in feed",
                           f.get("aspect_ratio")))
    w, h = f.get("width"), f.get("height")
    if isinstance(w, int) and isinstance(h, int) and w and h and min(w, h) < _MIN_SHORT_SIDE_PX:
        flags.append(_flag("low_resolution", True,
                           f"RISK: {w}x{h} is below 720p -> platforms demote low-res video",
                           f"{w}x{h}"))
    duration, ceiling = f.get("duration_s"), f.get("max_duration_s")
    if isinstance(duration, (int, float)):
        band = f.get("duration_band_s")
        if isinstance(ceiling, (int, float)) and duration > ceiling:
            flags.append(_flag("over_max_duration", True,
                               f"RISK: {duration:.1f}s exceeds the {ceiling:g}s upload ceiling",
                               duration))
        elif band and not band[0] <= duration <= band[1]:
            flags.append(_flag("outside_duration_band", False,
                               f"RISK: {duration:.1f}s is outside the target band "
                               f"{band[0]:g}-{band[1]:g}s", duration))
    if f.get("audio_present") is False:
        flags.append(_flag("muted", False, "RISK: no audio stream -> muted videos are demoted",
                           False))
    elif f.get("audio_present") is True:
        mean = f.get("mean_volume_db")
        if mean is None or mean <= _DIGITAL_SILENCE_DB:
            flags.append(_flag("muted", False,
                               "RISK: audio stream is digitally silent -> treated as muted", mean))
        lufs = f.get("integrated_lufs")
        if isinstance(lufs, (int, float)) and abs(lufs + 14.0) > _LOUDNESS_TOLERANCE_LU:
            flags.append(_flag("loudness_off_target", False,
                               f"RISK: integrated loudness {lufs:.1f} LUFS is far from the "
                               "-14 LUFS platforms normalise to", lufs))
        gap = f.get("longest_silence_s")
        if isinstance(gap, (int, float)) and gap >= _LONG_SILENCE_S:
            flags.append(_flag("long_silence", False,
                               f"RISK: {gap:.1f}s silent gap -> dead air invites a swipe", gap))
    cuts, opening_frozen = f.get("scene_changes_first_3s"), f.get("opening_frozen_s")
    if cuts == 0 and isinstance(opening_frozen, (int, float)) and isinstance(duration, (int, float)):
        if opening_frozen >= 0.9 * min(3.0, duration):
            flags.append(_flag("static_opening", False,
                               "RISK: no cut or motion in the first 3s -> weak scroll-stop",
                               opening_frozen))
    frozen = f.get("frozen_ratio")
    if isinstance(frozen, (int, float)) and frozen >= _MOSTLY_STATIC:
        flags.append(_flag("mostly_static", False,
                           f"RISK: {frozen:.2f} of the runtime is frozen frames (static cards)",
                           frozen))
    if f.get("caption_track_present") is True and f.get("captions_burned_in") is False:
        reason = f.get("captions_skipped_reason") or "not burned in"
        flags.append(_flag("captions_missing", False,
                           f"RISK: captions were authored but are not on screen ({reason})",
                           False))
    wps = f.get("caption_words_per_second_max")
    if isinstance(wps, (int, float)) and wps > _MAX_CAPTION_WPS and f.get("captions_burned_in"):
        flags.append(_flag("text_dense", False,
                           f"RISK: a caption runs at {wps:.1f} words/s (> {_MAX_CAPTION_WPS}) "
                           "-> hard to read", wps))
    return flags


def risk_flags(view: dict) -> list[dict]:
    """Binary risk flags from measured facts and declared judgments. Never a % deduction."""
    f = _facts(view)
    flags = _measured_flags(f)
    seen = {fl["code"] for fl in flags}
    for key, hard, message in _DECLARED_RULES:
        value = f.get(f"declared_{key}", f.get(key))
        if value is True and key not in seen:
            flags.append(_flag(key, hard, message + " (declared)", True))
    return flags


def decide_verdict(dimensions: list[dict], flags: list[dict]) -> str:
    """Map dimension scores + risk flags to a verdict (deterministic).

    - Any HARD risk flag -> REJECT (a reach-breaking defect).
    - Any soft risk flag OR any weak dimension -> PASS-WITH-CHANGES.
    - Otherwise -> PASS.
    No number is summed or averaged; this reads the individual signals.
    """
    if any(f["hard"] for f in flags):
        return REJECT
    weak = any(d["score"] is not None and d["score"] < _WEAK_DIMENSION for d in dimensions)
    if flags or weak:
        return PASS_WITH_CHANGES
    return PASS


def build_viral_check(
    viral_view: dict,
    project_id: str,
    *,
    source_artifacts: list[Artifact] | None = None,
    identity: Identity | None = None,
) -> Artifact:
    """Evaluate a VIRAL_VIEW into a viral_check artifact.

    The body carries the twelve individual dimension scores, the binary
    risk flags, and the verdict - and deliberately NO aggregate score.
    """
    dimensions = score_all(viral_view)
    flags = risk_flags(viral_view)
    verdict = decide_verdict(dimensions, flags)

    weak = [d["dimension"] for d in dimensions
            if d["score"] is not None and d["score"] < _WEAK_DIMENSION]
    unknown = [d["dimension"] for d in dimensions if d["score"] is None]
    evidence_notes = [
        "Scores are functions of measured file facts (ffprobe/ffmpeg) and any declared "
        "human judgments; dimensions with no measurable input are 'unknown', not guessed.",
        "Scores rate input quality against documented signals, not outcome.",
        "'Signal exists' (verified) is separate from 'weight known' (unknown).",
        "Platform ranking weights are not published and change over time.",
        "Per-video reach is probabilistic and partly serendipitous.",
    ]

    sources = [source_ref(a) for a in (source_artifacts or [])]
    body = {
        "stage": "viral_check",
        "bundle_hashes": dict(viral_view.get("bundle_hashes") or {}),
        "dimensions": dimensions,
        "risk_flags": flags,
        "weak_dimensions": weak,
        "unknown_dimensions": unknown,
        "coverage": {"scored": len(dimensions) - len(unknown), "unknown": len(unknown)},
        "verdict": verdict,
        "verdict_scope": (
            f"verdict covers the {len(dimensions) - len(unknown)} measured dimension(s) "
            "and risk flags only"
        ),
        "evidence_notes": evidence_notes,
        "method": (
            "Twelve dimensions, each scored 0-100 from measured inputs or reported "
            "'unknown'; risk flags are binary; no single viral percentage is produced."
        ),
    }
    return make_artifact(
        kind="viral_check",
        project_id=project_id,
        body=body,
        status="ready",
        sources=sources,
        agent="viral-check",
        identity=identity,
    )
