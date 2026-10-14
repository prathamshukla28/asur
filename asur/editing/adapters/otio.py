"""OpenTimelineIO interchange adapter (Apache-2.0) - behind asur[generation].

Declaration-only shell. OTIO is the timeline interchange format; it lets an ASUR
Timeline round-trip to/from the industry-standard .otio form so other tools can
read it. The heavy dependency is imported lazily inside each call and raises a
clear error when the generation extra is absent. Module level stays stdlib-only
so the boundary linter and the stdlib control path never see opentimelineio.

The ASUR Timeline dict shape (``asur.editing.timeline.Timeline.to_dict()``) is
the source of truth; OTIO is only a transport. These functions never mutate the
Timeline and never touch the network.
"""

from __future__ import annotations

import json
from typing import Any

# OTIO metadata namespace that carries the authoritative ASUR Timeline dict. The
# ASUR dict is the source of truth (ASUR-VERSION-01); OTIO is a lossless transport,
# so we round-trip the full dict verbatim rather than lossily mapping fields. OTIO's
# AnyDictionary coerces nested Python containers on assignment, so the dict is stashed
# as a JSON string (which survives untouched) and parsed back on import.
_ASUR_METADATA_KEY = "asur"


def _require_otio() -> Any:
    """Import opentimelineio or raise a clear, actionable error. Never in CI."""
    try:  # pragma: no cover - requires the generation extra, never in CI
        import opentimelineio as otio  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "OTIO adapter needs the generation extra: "
            "pip install -e '.[generation]'. This never runs in CI."
        ) from exc
    return otio  # pragma: no cover


def _timeline_dict(timeline: Any) -> dict:
    to_dict = getattr(timeline, "to_dict", None)
    return to_dict() if callable(to_dict) else dict(timeline)


def to_otio(timeline: Any) -> Any:  # pragma: no cover - needs the generation extra
    """Convert an ASUR Timeline (or its to_dict()) to an OTIO Timeline.

    Requires asur[generation]; raises RuntimeError otherwise. Human-run, local-only.
    Builds the standard OTIO track/clip structure for interoperability, and stashes
    the authoritative ASUR dict in timeline metadata so ``from_otio`` is lossless.
    """
    otio = _require_otio()
    data = _timeline_dict(timeline)
    resolution = data.get("resolution", {})

    otio_timeline = otio.schema.Timeline(name=str(data.get("timeline_id", "")))
    otio_timeline.metadata[_ASUR_METADATA_KEY] = json.dumps(data, sort_keys=True)
    otio_timeline.metadata["resolution"] = {
        "width": resolution.get("w"),
        "height": resolution.get("h"),
    }

    rate = float(data.get("fps", 30))
    for track in data.get("tracks", []):
        otio_track = otio.schema.Track(name=str(track.get("track_id", "")))
        for clip in track.get("clips", []):
            start = otio.opentime.RationalTime(float(clip.get("in", 0.0)), rate)
            dur_s = max(float(clip.get("out", 0.0)) - float(clip.get("in", 0.0)), 0.0)
            duration = otio.opentime.RationalTime(dur_s, rate)
            otio_clip = otio.schema.Clip(
                name=str(clip.get("clip_id", "")),
                source_range=otio.opentime.TimeRange(start_time=start, duration=duration),
            )
            otio_clip.metadata[_ASUR_METADATA_KEY] = json.dumps(clip, sort_keys=True)
            otio_track.append(otio_clip)
        otio_timeline.tracks.append(otio_track)
    return otio_timeline


def from_otio(otio_obj: Any) -> dict:  # pragma: no cover - needs the generation extra
    """Convert an OTIO Timeline back into an ASUR Timeline dict.

    Requires asur[generation]; raises RuntimeError otherwise. Human-run, local-only.
    Reads back the authoritative ASUR dict stashed in metadata so the round-trip is
    lossless; fails closed (ASUR-GATE-01) if the OTIO object was not produced by
    ``to_otio`` and carries no ASUR metadata.
    """
    _require_otio()
    metadata = getattr(otio_obj, "metadata", {}) or {}
    payload = metadata.get(_ASUR_METADATA_KEY)
    if not isinstance(payload, str):
        raise TypeError(
            "OTIO object carries no ASUR timeline metadata; refusing to guess "
            "a lossy reconstruction (ASUR-GATE-01)."
        )
    return json.loads(payload)
