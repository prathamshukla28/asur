"""The twelve VIRAL CHECK dimensions, scored ONLY from measured inputs (ASUR-HONEST-01).

Each dimension is reported on its own - never collapsed into a "% viral". A
dimension is either:

  * ``scored``  - a 0-100 number that is a documented function of measured
                  inputs (see the ``components`` each entry carries), or
  * ``unknown`` - ``score: None`` plus the reason it cannot be measured honestly
                  from a rendered file. No fabricated baseline number.

Inputs come from the VIRAL_VIEW ``platform_facts`` (built by
``asur.viral_check.facts.build_platform_facts``):

  measured  - ffprobe/ffmpeg numbers over the actual MP4 (``probe.py``)
  plan      - authored caption text + whether the render burned it in
  declared  - optional human judgments (``declared_<key>`` or legacy bare keys)

Formula for every scored dimension:

    score = round(100 * sum(w_i * c_i) / sum(w_i))   over AVAILABLE components

where each component ``c_i`` is in [0, 1] and is listed below. Components whose
inputs are absent are skipped (and named in the note); if none is available the
dimension is ``unknown``.

Attention       opening_change (0.5): 1.0 if a scene change (scdet > 10) occurs in
                the first 3s; else 0.6 x the share of the first 3s that is not frozen
                opening_not_black (0.2): 1.0 if black at start <= 0.1s, 0 at >= 1.0s
                hook_length (0.3): 1.0 for a 4-12 word hook, 0 at 0 or >= 24 words
                declared strong_first_three_seconds (0.5)
Retention       captions (0.3): authored captions actually burned in (or declared)
                pacing (0.3): 1.0 for 6-40 scene changes/min, 0 at 0 or >= 90
                motion (0.2): 1 - frozen_ratio (freezedetect)
                speech_continuity (0.2): 1 - 2 x silent share (0 if no audio)
Satisfaction    declared delivers_promise only (a payoff cannot be measured from bytes)
Visual Quality  resolution (0.5): short side / platform short side, capped at 1
                fps (0.2): 1.0 at >= 24 fps, 0 at <= 10
                not_black (0.3): 1 - black share of duration
                declared low_resolution (0.5)
Originality     declared reposted_elsewhere only
Platform Fit    aspect (0.35): 1.0 if aspect ratio matches the platform within 1%
                duration (0.25): 1.0 inside the platform band, 0.5 outside it but under
                the upload ceiling, 0 over the ceiling
                audio (0.2): an audio stream with signal is present
                loudness (0.2): 1.0 within 2 LU of -14 LUFS, 0 at >= 12 LU away
                declared visible_watermark (0.35)
Value, Shareability, Saveability, Replayability, Authenticity, Audience Fit:
                always ``unknown`` - they depend on meaning and audience response,
                which a file probe cannot measure. LEARNING measures them later
                from real performance data.

Deterministic: the same facts always yield the same output.
"""

from __future__ import annotations

from typing import Any

from ..script.evidence import (
    EMPIRICAL,
    HYPOTHESIS,
    STRONG_EVIDENCE,
    VERIFIED_FACT,
)

DIMENSIONS = (
    "Attention",
    "Retention",
    "Satisfaction",
    "Value",
    "Shareability",
    "Saveability",
    "Replayability",
    "Originality",
    "Authenticity",
    "Visual Quality",
    "Audience Fit",
    "Platform Fit",
)

SCORED = "scored"
UNKNOWN = "unknown"

_EVIDENCE = {
    "Attention": STRONG_EVIDENCE,
    "Retention": STRONG_EVIDENCE,
    "Satisfaction": HYPOTHESIS,
    "Value": HYPOTHESIS,
    "Shareability": EMPIRICAL,
    "Saveability": EMPIRICAL,
    "Replayability": HYPOTHESIS,
    "Originality": VERIFIED_FACT,
    "Authenticity": HYPOTHESIS,
    "Visual Quality": VERIFIED_FACT,
    "Audience Fit": EMPIRICAL,
    "Platform Fit": VERIFIED_FACT,
}

_NOT_MEASURABLE = {
    "Value": "usefulness depends on meaning; not measurable from a file probe",
    "Shareability": "send/share behaviour needs real audience data (LEARNING)",
    "Saveability": "save behaviour needs real audience data (LEARNING)",
    "Replayability": "loop/replay behaviour needs real audience data (LEARNING)",
    "Authenticity": "perceived authenticity needs a human rating; not measured",
    "Audience Fit": "fit to a real audience needs performance data (LEARNING)",
}

TARGET_LUFS = -14.0
OPENING_WINDOW_S = 3.0


def _num(facts: dict, key: str) -> float | None:
    value = facts.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _declared(facts: dict, key: str) -> bool | None:
    value = facts.get(f"declared_{key}", facts.get(key))
    return value if isinstance(value, bool) else None


def _ramp(x: float, zero: float, full: float) -> float:
    """Linear 0..1 between *zero* and *full* (works for rising or falling ramps)."""
    if full == zero:
        return 1.0 if x >= full else 0.0
    return max(0.0, min(1.0, (x - zero) / (full - zero)))


def _band(x: float, lo: float, hi: float, zero_lo: float, zero_hi: float) -> float:
    """1.0 inside [lo, hi], ramping to 0 at zero_lo / zero_hi."""
    if lo <= x <= hi:
        return 1.0
    return _ramp(x, zero_lo, lo) if x < lo else _ramp(x, zero_hi, hi)


Component = tuple[str, float, float, str, Any]  # name, value, weight, source, input


def _attention(f: dict) -> list[Component]:
    out: list[Component] = []
    cuts = _num(f, "scene_changes_first_3s")
    frozen = _num(f, "opening_frozen_s")
    duration = _num(f, "duration_s")
    if cuts is not None and frozen is not None and duration:
        window = min(OPENING_WINDOW_S, duration)
        value = 1.0 if cuts >= 1 else 0.6 * (1 - min(1.0, frozen / window))
        out.append(("opening_change", value, 0.5, "measured",
                    {"scene_changes_first_3s": cuts, "opening_frozen_s": frozen}))
    black = _num(f, "black_at_start_s")
    if black is not None:
        out.append(("opening_not_black", _ramp(black, 1.0, 0.1), 0.2, "measured",
                    {"black_at_start_s": black}))
    words = _num(f, "hook_word_count")
    if words is not None:
        out.append(("hook_length", _band(words, 4, 12, 0, 24), 0.3, "plan",
                    {"hook_word_count": words}))
    rated = _declared(f, "strong_first_three_seconds")
    if rated is not None:
        out.append(("strong_first_three_seconds", float(rated), 0.5, "declared", rated))
    return out


def _retention(f: dict) -> list[Component]:
    out: list[Component] = []
    burned = f.get("captions_burned_in")
    planned = f.get("caption_track_present")
    if isinstance(burned, bool) or planned is False:
        value = 1.0 if (burned is True and planned is not False) else 0.0
        out.append(("captions", value, 0.3, "plan",
                    {"caption_track_present": planned, "captions_burned_in": burned}))
    else:
        rated = _declared(f, "captions_present")
        if rated is not None:
            out.append(("captions", float(rated), 0.3, "declared", rated))
    cpm = _num(f, "cuts_per_minute")
    if cpm is not None:
        out.append(("pacing", _band(cpm, 6, 40, 0, 90), 0.3, "measured", {"cuts_per_minute": cpm}))
    frozen = _num(f, "frozen_ratio")
    if frozen is not None:
        out.append(("motion", 1 - min(1.0, frozen), 0.2, "measured", {"frozen_ratio": frozen}))
    duration = _num(f, "duration_s")
    if isinstance(f.get("audio_present"), bool) and duration:
        silence = _num(f, "silence_total_s") or 0.0
        value = (1 - min(1.0, 2 * silence / duration)) if f["audio_present"] else 0.0
        out.append(("speech_continuity", value, 0.2, "measured",
                    {"audio_present": f["audio_present"], "silence_total_s": silence}))
    return out


def _satisfaction(f: dict) -> list[Component]:
    rated = _declared(f, "delivers_promise")
    return [] if rated is None else [("delivers_promise", float(rated), 1.0, "declared", rated)]


def _originality(f: dict) -> list[Component]:
    rated = _declared(f, "reposted_elsewhere")
    return [] if rated is None else [("not_reposted", float(not rated), 1.0, "declared", rated)]


def _visual(f: dict) -> list[Component]:
    out: list[Component] = []
    w, h = _num(f, "width"), _num(f, "height")
    ew, eh = _num(f, "expected_width"), _num(f, "expected_height")
    if w and h and ew and eh:
        out.append(("resolution", min(1.0, min(w, h) / min(ew, eh)), 0.5, "measured",
                    {"width": w, "height": h}))
    fps = _num(f, "fps")
    if fps is not None:
        out.append(("fps", _ramp(fps, 10, 24), 0.2, "measured", {"fps": fps}))
    black, duration = _num(f, "black_total_s"), _num(f, "duration_s")
    if black is not None and duration:
        out.append(("not_black", 1 - min(1.0, black / duration), 0.3, "measured",
                    {"black_total_s": black}))
    rated = _declared(f, "low_resolution")
    if rated is not None:
        out.append(("declared_resolution_ok", float(not rated), 0.5, "declared", rated))
    return out


def _platform_fit(f: dict) -> list[Component]:
    out: list[Component] = []
    if isinstance(f.get("aspect_matches"), bool):
        out.append(("aspect", float(f["aspect_matches"]), 0.35, "measured",
                    {"aspect_ratio": f.get("aspect_ratio"), "expected": f.get("expected_aspect_ratio")}))
    elif isinstance(f.get("aspect_ratio"), str):
        expected = f.get("expected_aspect_ratio", "9:16")
        out.append(("aspect", float(f["aspect_ratio"] == expected), 0.35, "declared",
                    {"aspect_ratio": f["aspect_ratio"], "expected": expected}))
    duration = _num(f, "duration_s")
    if duration is not None:
        band = f.get("duration_band_s")
        ceiling = _num(f, "max_duration_s")
        if ceiling is not None and duration > ceiling:
            value = 0.0
        elif band and not band[0] <= duration <= band[1]:
            value = 0.5
        else:
            value = 1.0
        out.append(("duration", value, 0.25, "measured",
                    {"duration_s": duration, "band_s": band, "max_s": ceiling}))
    if isinstance(f.get("audio_present"), bool):
        mean = _num(f, "mean_volume_db")
        has_signal = f["audio_present"] and (mean is None or mean > -60)
        out.append(("audio", float(has_signal), 0.2, "measured",
                    {"audio_present": f["audio_present"], "mean_volume_db": mean}))
    else:
        rated = _declared(f, "muted")
        if rated is not None:
            out.append(("audio", float(not rated), 0.2, "declared", rated))
    lufs = _num(f, "integrated_lufs")
    if lufs is not None:
        out.append(("loudness", _ramp(abs(lufs - TARGET_LUFS), 12, 2), 0.2, "measured",
                    {"integrated_lufs": lufs, "target_lufs": TARGET_LUFS}))
    rated = _declared(f, "visible_watermark")
    if rated is not None:
        out.append(("no_watermark", float(not rated), 0.35, "declared", rated))
    return out


_SCORERS = {
    "Attention": _attention,
    "Retention": _retention,
    "Satisfaction": _satisfaction,
    "Originality": _originality,
    "Visual Quality": _visual,
    "Platform Fit": _platform_fit,
}


def _facts(view: dict) -> dict:
    facts = view.get("platform_facts")
    return facts if isinstance(facts, dict) else {}


def score_dimension(name: str, view: dict) -> dict:
    """Score one dimension from measured/declared facts, or mark it unknown."""
    if name not in _EVIDENCE:
        raise ValueError(f"unknown dimension: {name}")
    entry: dict[str, Any] = {"dimension": name, "evidence_class": _EVIDENCE[name]}
    scorer = _SCORERS.get(name)
    components = scorer(_facts(view)) if scorer else []
    if not components:
        entry.update({
            "status": UNKNOWN,
            "score": None,
            "note": _NOT_MEASURABLE.get(name, "no measured input available for this dimension"),
            "components": [],
        })
        return entry
    total_w = sum(c[2] for c in components)
    score = round(100 * sum(c[1] * c[2] for c in components) / total_w)
    weakest = min(components, key=lambda c: c[1])
    entry.update({
        "status": SCORED,
        "score": max(0, min(100, score)),
        "note": (f"weighted mean of {len(components)} component(s); weakest: "
                 f"{weakest[0]}={weakest[1]:.2f}"),
        "components": [
            {"name": n, "value": round(v, 3), "weight": w, "source": src, "input": inp}
            for n, v, w, src, inp in components
        ],
    })
    return entry


def score_all(view: dict) -> list[dict]:
    """Score all twelve dimensions. Returns a list, never a single number."""
    return [score_dimension(name, view) for name in DIMENSIONS]
