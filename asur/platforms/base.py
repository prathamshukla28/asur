"""Platform packs - the data-first description of an output surface (P09a).

ASUR's engine is platform-shaped in exactly three seams (see
docs/build/YOUTUBE_EXTENSION_PLAN.md section 2):

  1. FORMAT facts    - aspect ratio, resolution, fps, duration band, safe areas.
  2. PLATFORM facts  - documented public ranking/retention signals the honest
                       VIRAL CHECK may weigh (fed into VIRAL_VIEW's platform_facts).
  3. PUBLISH fields  - the platform-facing metadata a human reviews before posting.

A ``PlatformPack`` bundles those three for one surface. Packs are pure data +
stdlib only (ASUR-LOCAL-01): no media imports, no network, no third-party deps.

Hard rules baked in here:
  - ASUR-HONEST-01: platform facts are documented signals, each evidence-classed
    and sourced. NEVER a predicted outcome, never a single "% viral" number.
  - ASUR-FIREWALL-01: platform facts must be free of quality/hardness TARGET
    names (they flow into VIRAL_VIEW, which strips those by name and fails closed).
  - ASUR-EXPLAIN-01: every fact cites a source + an as-of date.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["FormatSpec", "PlatformPack"]


@dataclass(frozen=True)
class FormatSpec:
    """The render/format contract for one platform surface.

    ``duration_band_s`` is a *target band*, never a hard overwrite (SPEC-GAP G16
    pattern): a duration outside it is a QA warning, not a hard fail. ``None``
    means "no band declared" (today's platform-neutral Instagram behaviour).

    ``safe_area`` fractions are margins to keep clear of platform UI chrome
    (e.g. a Shorts right-hand action rail, a long-form progress bar / end-screen).
    """

    aspect_ratio: str
    width: int
    height: int
    fps: int = 30
    default_duration_s: float = 60.0
    duration_band_s: tuple[float, float] | None = None
    # UI-chrome margins as fractions of height/width (top, bottom, left, right).
    safe_area: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class PlatformPack:
    """Everything the engine needs to target one output surface.

    ``publish_platform_id`` is the id written into a publish_package's
    ``platform`` field (it equals ``platform_id`` for every launch pack, but is
    kept explicit so a surface could post under a different platform label later).

    ``publish_fields`` is the ordered set of metadata fields this surface's
    publish package should carry (e.g. a long-form pack adds ``description``,
    ``tags``, ``chapters``).

    ``_facts`` holds the documented public signals; ``platform_facts()`` returns
    them wrapped for VIRAL_VIEW. It is a plain method (not a stored dict) so a
    pack can be a frozen dataclass while still returning a fresh copy each call.
    """

    platform_id: str
    format_spec: FormatSpec
    publish_platform_id: str
    publish_fields: tuple[str, ...]
    _facts: tuple[dict, ...] = ()

    def platform_facts(self) -> dict:
        """The documented public signals, shaped for VIRAL_VIEW.platform_facts.

        Returns a fresh dict every call (no shared mutable state). Each signal is
        a dict: {signal, evidence_class, source, as_of, note}. These are inputs
        the honest evaluator may weigh - never an outcome, never a % number
        (ASUR-HONEST-01).
        """
        return {
            "platform_id": self.platform_id,
            "signals": [dict(s) for s in self._facts],
        }
