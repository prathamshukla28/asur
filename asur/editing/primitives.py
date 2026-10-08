"""The 15 editing primitives, as a reusable component PALETTE.

A primitive is a named, reusable motion/typography/transition move. It is a tool
the creative direction reaches for — it is NEVER the creative driver. The same
primitive serves many different concepts; the concept decides when and why it is
used (DATA_MODELS.md section 5). This module applies a primitive as data onto a
clip; it never decides on its own what a video should look like.

Applying a primitive is a versioned edit: the clip's prior state is pushed onto
``version_history`` before the change, so nothing is silently overwritten
(ASUR-VERSION-01). A locked clip refuses all primitives (fail closed,
ASUR-GATE-01).
"""

from __future__ import annotations

from .timeline import Clip

PRIMITIVES = (
    "TextReveal",
    "WordPunch",
    "CameraPush",
    "CameraPull",
    "BlurTransition",
    "CutOnBeat",
    "HighlightWord",
    "SubtitleEmphasis",
    "ImageParallax",
    "MotionBackground",
    "ShapeReveal",
    "ScreenShake",
    "SpeedRamp",
    "MaskReveal",
    "TrackingText",
)

_PRIMITIVE_SET = frozenset(PRIMITIVES)

# Which editable clip field each primitive writes into, so the palette stays
# honest about what it changes (ASUR-EXPLAIN-01). Keyframe-driven moves write
# keyframes; SpeedRamp writes speed; text/overlay moves write overlays.
_PRIMITIVE_FIELD = {
    "TextReveal": "overlays",
    "WordPunch": "overlays",
    "HighlightWord": "overlays",
    "SubtitleEmphasis": "overlays",
    "TrackingText": "overlays",
    "ShapeReveal": "overlays",
    "MotionBackground": "overlays",
    "CameraPush": "keyframes",
    "CameraPull": "keyframes",
    "ImageParallax": "keyframes",
    "ScreenShake": "keyframes",
    "MaskReveal": "masks",
    "BlurTransition": "overlays",
    "CutOnBeat": "overlays",
    "SpeedRamp": "speed",
}


def is_primitive(name: str) -> bool:
    return name in _PRIMITIVE_SET


def apply_primitive(clip: Clip, primitive_name: str, params: dict | None = None) -> Clip:
    """Apply a named primitive to *clip* as a new version.

    Fails closed on an unknown primitive or a locked clip (ValueError,
    ASUR-GATE-01). Pushes the prior clip state onto ``version_history`` before
    changing anything (ASUR-VERSION-01), then records the primitive and writes
    its parameters into the relevant editable field. Returns the same clip,
    mutated with history preserved.
    """
    if primitive_name not in _PRIMITIVE_SET:
        raise ValueError(
            f"unknown primitive {primitive_name!r}; must be one of {', '.join(PRIMITIVES)}"
        )
    if clip.locked:
        raise ValueError(
            f"clip {clip.clip_id!r} is locked; unlock before applying a primitive"
        )

    clip.version_history.append(clip._snapshot())
    clip.primitive = primitive_name

    params = params or {}
    field = _PRIMITIVE_FIELD[primitive_name]
    if field == "speed":
        clip.speed = float(params.get("speed", clip.speed))
    elif field == "keyframes":
        for axis, frames in params.items():
            if axis in clip.keyframes and isinstance(frames, list):
                clip.keyframes[axis] = list(frames)
    elif field == "masks":
        clip.masks.append({"primitive": primitive_name, "params": params})
    else:
        clip.overlays.append({"primitive": primitive_name, "params": params})

    return clip
