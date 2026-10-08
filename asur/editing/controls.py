"""Manual human controls for the EDITING environment (ASUR-HUMAN-01).

EDITING is a shared, human-controlled environment, not an autonomous instrument.
Every control here operates on a ``Clip`` and preserves history: each mutating
control snapshots the clip's prior state onto ``version_history`` BEFORE changing
anything, so nothing is ever silently overwritten (ASUR-VERSION-01). ``revert``
is the one exception: it consumes history to restore the prior state exactly.

Pure stdlib. No media, no network.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from .timeline import Clip

_ACCEPTED = "accepted"
_REJECTED = "rejected"


def _record(clip: Clip) -> None:
    """Push the current editable state onto ``version_history`` before a change."""
    clip.version_history.append(clip._snapshot())


def accept(clip: Clip) -> Clip:
    """Mark a clip accepted (records a new version)."""
    _record(clip)
    clip.review = _ACCEPTED
    return clip


def reject(clip: Clip) -> Clip:
    """Mark a clip rejected (records a new version)."""
    _record(clip)
    clip.review = _REJECTED
    return clip


def modify(clip: Clip, **changes: Any) -> Clip:
    """Apply field changes to a clip (records a new version). Refuses a locked
    clip and refuses unknown fields (fail closed, ASUR-GATE-01)."""
    if clip.locked:
        raise ValueError(f"clip {clip.clip_id} is locked; unlock before modify")
    allowed = {"in_point", "out_point", "timeline_start", "speed", "crop"}
    unknown = set(changes) - allowed
    if unknown:
        raise ValueError(f"unknown clip fields: {sorted(unknown)}")
    _record(clip)
    for name, value in changes.items():
        setattr(clip, name, value)
    return clip


def regenerate(clip: Clip, new_asset_ref: str) -> Clip:
    """Swap the underlying asset (records a new version). Refuses a locked clip."""
    if clip.locked:
        raise ValueError(f"clip {clip.clip_id} is locked; unlock before regenerate")
    _record(clip)
    clip.asset_ref = new_asset_ref
    return clip


def lock(clip: Clip) -> Clip:
    """Freeze a clip so edits/primitives are refused until unlocked."""
    _record(clip)
    clip.locked = True
    return clip


def unlock(clip: Clip) -> Clip:
    """Release a lock."""
    _record(clip)
    clip.locked = False
    return clip


def revert(clip: Clip) -> Clip:
    """Restore the clip to its most recent prior version EXACTLY. Consumes the
    last ``version_history`` entry. Fails closed if there is no history."""
    if not clip.version_history:
        raise ValueError(f"clip {clip.clip_id} has no prior version to revert to")
    prior = clip.version_history.pop()
    clip.asset_ref = prior["asset_ref"]
    clip.in_point = prior["in"]
    clip.out_point = prior["out"]
    clip.timeline_start = prior["timeline_start"]
    clip.speed = prior["speed"]
    clip.keyframes = prior["keyframes"]
    clip.crop = prior["crop"]
    clip.masks = prior["masks"]
    clip.overlays = prior["overlays"]
    clip.primitive = prior["primitive"]
    clip.locked = prior["locked"]
    clip.review = prior.get("review")
    return clip


def branch(clip: Clip) -> Clip:
    """Return an independent copy of the clip with a new id and fresh history, so
    alternatives can be explored without touching the original."""
    twin = replace(
        clip,
        clip_id=f"{clip.clip_id}-branch",
        keyframes={k: list(v) for k, v in clip.keyframes.items()},
        crop=dict(clip.crop),
        masks=list(clip.masks),
        overlays=list(clip.overlays),
        version_history=[],
    )
    return twin


def compare(clip_a: Clip, clip_b: Clip) -> dict:
    """Return a field-level diff ``{field: {'a': ..., 'b': ...}}`` of the two
    clips' editable state (version_history excluded)."""
    a = clip_a._snapshot()
    b = clip_b._snapshot()
    diff: dict = {}
    for key in sorted(set(a) | set(b)):
        if a.get(key) != b.get(key):
            diff[key] = {"a": a.get(key), "b": b.get(key)}
    return diff
