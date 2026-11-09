"""Turn measurements of a rendered file into VIRAL_VIEW ``platform_facts``.

Three kinds of input, kept distinguishable in the output (ASUR-HONEST-01):

  * measured  - numbers from ``probe.measure_video`` over the actual MP4
  * plan      - facts read from the edit plan / render artifact bodies (what
                caption text was authored, whether it was actually burned in)
  * declared  - optional human judgments (e.g. a blind rater's
                ``delivers_promise``); never invented, simply absent if not given

The platform contract (expected resolution, aspect, duration band) comes from
the platform pack. This module is pure data transformation: no I/O.
"""

from __future__ import annotations

import math
from typing import Any

from ..platforms import get_platform

__all__ = ["DECLARED_KEYS", "PLATFORM_MAX_S", "build_platform_facts", "plan_facts"]

# Hard upload ceilings (seconds). Instagram Reels: 3 min (Meta, Jan 2025);
# YouTube Shorts: 3 min (YouTube, Oct 2024); long-form: no practical ceiling here.
PLATFORM_MAX_S: dict[str, float | None] = {
    "instagram_reels": 180.0,
    "youtube_shorts": 180.0,
    "youtube_long": None,
}

# Human-supplied judgments the evaluator accepts as "declared" inputs.
DECLARED_KEYS = (
    "strong_first_three_seconds",
    "captions_present",
    "delivers_promise",
    "visible_watermark",
    "reposted_elsewhere",
    "low_resolution",
    "muted",
    "bordered",
    "majority_text",
    "aspect_ratio",
)


def _ratio(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        return "unknown"
    g = math.gcd(width, height)
    return f"{width // g}:{height // g}"


def plan_facts(edit_plan_body: dict | None, render_body: dict | None = None) -> dict[str, Any]:
    """Caption/hook facts from the edit plan, plus what the render actually burned in."""
    out: dict[str, Any] = {}
    timeline = (edit_plan_body or {}).get("timeline") or {}
    captions: list[tuple[float, float, str]] = []
    for track in timeline.get("tracks", []):
        if track.get("type") != "text":
            continue
        for clip in track.get("clips", []):
            for ov in clip.get("overlays", []):
                if ov.get("type") == "caption" and str(ov.get("text", "")).strip():
                    captions.append((float(ov.get("start", 0.0)), float(ov.get("end", 0.0)),
                                     str(ov["text"]).strip()))
    if edit_plan_body is not None:
        out["caption_track_present"] = bool(captions)
    if captions:
        captions.sort()
        hook = captions[0][2] if captions[0][0] <= 0.05 else ""
        if hook:
            out["hook_text"] = hook
            out["hook_word_count"] = len(hook.split())
        rates = [len(t.split()) / (e - s) for s, e, t in captions if e > s]
        if rates:
            out["caption_words_per_second_max"] = round(max(rates), 2)
    prov = (render_body or {}).get("provenance") or {}
    if "captions_burned_in" in prov:
        out["captions_burned_in"] = bool(prov["captions_burned_in"])
        if prov.get("captions_skipped_reason"):
            out["captions_skipped_reason"] = str(prov["captions_skipped_reason"])
    return out


def build_platform_facts(
    measured: dict[str, Any],
    *,
    platform: str | None,
    plan: dict[str, Any] | None = None,
    declared: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the flat platform_facts dict the dimensions + risk flags read."""
    pack = get_platform(platform)
    spec = pack.format_spec
    width, height = int(measured.get("width") or 0), int(measured.get("height") or 0)
    expected_ratio = _ratio(spec.width, spec.height)
    actual = width / height if height else 0.0
    want = spec.width / spec.height
    facts: dict[str, Any] = {
        "platform": pack.platform_id,
        "expected_width": spec.width,
        "expected_height": spec.height,
        "expected_aspect_ratio": expected_ratio,
        "aspect_ratio": expected_ratio if actual and abs(actual - want) / want <= 0.01 else _ratio(width, height),
        "aspect_matches": bool(actual) and abs(actual - want) / want <= 0.01,
        "duration_band_s": list(spec.duration_band_s) if spec.duration_band_s else None,
        "max_duration_s": PLATFORM_MAX_S.get(pack.platform_id),
    }
    facts.update({k: v for k, v in measured.items() if k not in ("file", "scene_change_times_s")})
    facts.update(plan or {})
    for key in DECLARED_KEYS:
        if declared and key in declared and key != "aspect_ratio":
            facts[f"declared_{key}"] = declared[key]
    return facts
