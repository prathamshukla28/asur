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

from typing import Any


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


def to_otio(timeline: Any) -> Any:
    """Convert an ASUR Timeline (or its to_dict()) to an OTIO Timeline.

    Requires asur[generation]; raises RuntimeError otherwise. Human-run, local-only.
    """
    _require_otio()  # pragma: no cover
    raise NotImplementedError(  # pragma: no cover
        "OTIO export is a human-run, local-only step (needs asur[generation])."
    )


def from_otio(otio_obj: Any) -> Any:
    """Convert an OTIO Timeline back into an ASUR Timeline dict.

    Requires asur[generation]; raises RuntimeError otherwise. Human-run, local-only.
    """
    _require_otio()  # pragma: no cover
    raise NotImplementedError(  # pragma: no cover
        "OTIO import is a human-run, local-only step (needs asur[generation])."
    )
