"""Derive observable platform_facts for one clip, honestly (SPEC-GAP G30).

A clip's VIRAL_VIEW platform_facts come from two sources, kept strictly
separate so nothing is ever invented (ASUR anti-hallucination rule):

  - Machine-observable facts (aspect_ratio, low_resolution, muted) come from
    a probe. In a real study the probe is produced by ffprobe over the
    downloaded clip; here it is passed in as ``probe`` so tests need no binary.
  - Judgment-call facts (strong_first_three_seconds, delivers_promise) come
    only from a blind human rater's ``ratings``. A missing judgment is OMITTED
    (the scorer then leaves that dimension at its baseline) - it is NEVER
    guessed.
  - captions_present may be asserted by the rater, or probed by the
    faster-whisper adapter in a real run (``captions_probe``). When neither is
    available it is recorded as the string ``"unknown"`` - never a guessed
    boolean, so the dimension stays at baseline and the gap is explicit.

This module is stdlib-only (ASUR-LOCAL-01 / boundary): ffprobe and the
faster-whisper adapter are invoked only in the real-run helpers below, behind
the injection parameters, so importing this module pulls in no media deps.
"""

from __future__ import annotations

from pathlib import Path

# Sentinel distinguishing "no captions probe supplied" from "probe said None".
_UNSET = object()

# Observable facts that a probe may supply, verbatim keys consumed by the
# viral-check dimensions/evaluator.
_PROBE_FACTS = ("aspect_ratio", "low_resolution", "muted")

# Blind-rater judgment booleans. Absent => omitted (never invented).
_JUDGMENT_FACTS = ("strong_first_three_seconds", "delivers_promise")


def derive_platform_facts(
    clip_path: str | Path,
    *,
    ratings: dict | None = None,
    probe: dict | None = None,
    captions_probe=_UNSET,
) -> dict:
    """Build the observable platform_facts dict for one clip.

    ``clip_path`` is recorded for provenance only; this function never opens
    the clip (real probing happens in :func:`probe_clip`). Returns a plain
    dict safe to feed through ``build_viral_view`` - it contains only
    observable signal keys, so the firewall conformance scan passes.
    """
    _ = clip_path  # provenance only; no file read here (stdlib-only, no media)
    ratings = ratings or {}
    probe = probe or {}

    facts: dict = {}

    # Machine-observable facts: copy through only what the probe actually saw.
    for key in _PROBE_FACTS:
        if key in probe:
            facts[key] = probe[key]

    # Judgment booleans: only when the blind rater recorded them. A missing
    # judgment is omitted so the dimension stays at baseline (never invented).
    for key in _JUDGMENT_FACTS:
        if key in ratings:
            facts[key] = ratings[key]

    # captions_present: rater assertion wins; else a probe value; else unknown.
    if "captions_present" in ratings:
        facts["captions_present"] = ratings["captions_present"]
    elif captions_probe is not _UNSET and captions_probe is not None:
        facts["captions_present"] = captions_probe
    else:
        facts["captions_present"] = "unknown"

    return facts


def probe_clip(clip_path: str | Path) -> dict:  # pragma: no cover
    """Real-run observable probe via ffprobe (stdlib subprocess, no media import).

    Returns {aspect_ratio, low_resolution, muted}. Only invoked during an
    actual study against a downloaded clip; tests inject ``probe`` instead.
    """
    import json
    import shutil
    import subprocess

    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        raise RuntimeError("ffprobe not found; install FFmpeg to probe clips")

    cmd = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "stream=width,height,codec_type",
        "-of",
        "json",
        str(clip_path),
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    if out.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {out.stderr[-400:]}")
    data = json.loads(out.stdout or "{}")
    streams = data.get("streams") or []

    width = height = 0
    has_audio = False
    for stream in streams:
        if stream.get("codec_type") == "video" and not width:
            width = int(stream.get("width") or 0)
            height = int(stream.get("height") or 0)
        if stream.get("codec_type") == "audio":
            has_audio = True

    aspect_ratio = _aspect_ratio(width, height)
    low_resolution = bool(height) and min(width, height) < 720
    return {
        "aspect_ratio": aspect_ratio,
        "low_resolution": low_resolution,
        "muted": not has_audio,
    }


def captions_probe(clip_path: str | Path) -> bool | None:  # pragma: no cover
    """Real-run captions probe via the faster-whisper adapter (lazy, fail-open).

    Returns True when a non-trivial transcript is detected, False when the
    audio is silent/empty, or None when the generation extra is not installed
    (so the caller records 'unknown' rather than guessing).
    """
    try:
        from ...generation.adapters import faster_whisper
    except RuntimeError:
        return None
    try:
        result = faster_whisper.transcribe(str(clip_path))
    except RuntimeError:
        # Extra not installed / model unavailable -> unknown, never guessed.
        return None
    transcript = (result.get("transcript") or "").strip()
    return bool(transcript)


def _aspect_ratio(width: int, height: int) -> str | None:
    if not width or not height:
        return None
    from math import gcd

    divisor = gcd(width, height) or 1
    return f"{width // divisor}:{height // divisor}"
