"""Caption styling + safe-area model (EDITING environment).

Captions on a 9:16 Reel must sit inside the platform safe area (the top and
bottom bands reserved for platform UI), be legible, and be timed inside the clip
they annotate. Scripts and hooks are multilingual (en/hi/hinglish/indian-en/mr),
so Devanagari-script captions (hi, hinglish, mr) are flagged for complex-text
shaping (HarfBuzz/libraqm) at render time; the control logic here only records
that requirement and checks structural correctness. No rendering happens here.
"""

from __future__ import annotations

from .timeline import REEL_HEIGHT

# Instagram Reels reserves roughly the top and bottom ~10-12% for UI chrome.
# Captions are kept out of those bands. These fractions are the structural
# safe-area contract the checker enforces (ASUR-EXPLAIN-01); real per-platform
# values can be refined via a Brand entity later (would be a SPEC-GAP).
SAFE_TOP_FRACTION = 0.12
SAFE_BOTTOM_FRACTION = 0.12

# Languages whose captions need complex-text shaping at render time.
_SHAPED_LANGUAGES = frozenset({"hi", "hinglish", "mr"})


def needs_shaping(language: str) -> bool:
    return language.casefold() in _SHAPED_LANGUAGES


def style_caption(
    text: str,
    language: str,
    start: float,
    end: float,
    *,
    y_fraction: float = 0.78,
) -> dict:
    """Build a styled caption record (pure data; no render).

    ``y_fraction`` is the vertical anchor as a fraction of frame height
    (0 = top, 1 = bottom); default 0.78 sits captions in the lower-middle, clear
    of both safe bands. Shaped languages are flagged for complex-text shaping.
    """
    return {
        "text": text,
        "language": language,
        "start": float(start),
        "end": float(end),
        "y_fraction": float(y_fraction),
        "needs_shaping": needs_shaping(language),
        "shaping_note": (
            "complex-text shaping (HarfBuzz/libraqm) required at render"
            if needs_shaping(language)
            else "simple Latin shaping"
        ),
    }


def check_caption(caption: dict, *, clip_start: float, clip_end: float) -> dict:
    """Structurally verify a caption: timing inside the clip, inside safe area.

    Returns a report dict ``{ok, reasons}``; ``ok`` is False (fail closed) if the
    caption is mistimed or lands in a reserved safe band (ASUR-GATE-01).
    """
    reasons: list[str] = []
    start = float(caption.get("start", 0.0))
    end = float(caption.get("end", 0.0))
    y = float(caption.get("y_fraction", 0.5))

    if end <= start:
        reasons.append(f"caption end {end} not after start {start}")
    if start < clip_start - 1e-9 or end > clip_end + 1e-9:
        reasons.append(
            f"caption [{start}, {end}] outside clip [{clip_start}, {clip_end}]"
        )
    if y < SAFE_TOP_FRACTION:
        reasons.append(f"y_fraction {y} inside top safe band (< {SAFE_TOP_FRACTION})")
    if y > (1.0 - SAFE_BOTTOM_FRACTION):
        reasons.append(
            f"y_fraction {y} inside bottom safe band (> {1.0 - SAFE_BOTTOM_FRACTION})"
        )

    return {"ok": not reasons, "reasons": reasons}


def safe_area_pixels(height: int = REEL_HEIGHT) -> dict:
    """The safe band boundaries in pixels, for a render adapter to consume."""
    top = round(height * SAFE_TOP_FRACTION)
    bottom = round(height * (1.0 - SAFE_BOTTOM_FRACTION))
    return {"top_px": top, "bottom_px": bottom, "usable_px": bottom - top}
