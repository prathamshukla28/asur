"""PLATFORMS - the output-surface registry (P09a, SPEC-GAP G19).

ASUR's frozen v1 surface is an Instagram Reel (9:16). YouTube (long-form 16:9 +
Shorts 9:16) is added here as an *additive, opt-in* platform pack - the engine is
not forked. A platform is chosen by id; an unknown id FAILS CLOSED (ASUR-GATE-01)
and never silently defaults.

Stdlib-only (ASUR-LOCAL-01): this package imports no media/third-party module and
is covered by the boundary import-linter (tests/test_boundary.py).

Usage:
    from asur.platforms import get_platform, DEFAULT_PLATFORM
    pack = get_platform()                 # -> Instagram Reels (the default)
    pack = get_platform("youtube_long")   # -> YouTube long-form
    get_platform("tiktok")                # -> raises UnknownPlatform
"""

from __future__ import annotations

from .base import FormatSpec, PlatformPack
from .instagram_reels import PACK as _INSTAGRAM_REELS
from .youtube_long import PACK as _YOUTUBE_LONG
from .youtube_shorts import PACK as _YOUTUBE_SHORTS

__all__ = [
    "DEFAULT_PLATFORM",
    "PLATFORM_REGISTRY",
    "FormatSpec",
    "PlatformPack",
    "UnknownPlatform",
    "get_platform",
]

# The locked v1 default (MVP.md section 1/7): Instagram Reels, 9:16.
DEFAULT_PLATFORM = "instagram_reels"

PLATFORM_REGISTRY: dict[str, PlatformPack] = {
    _INSTAGRAM_REELS.platform_id: _INSTAGRAM_REELS,
    _YOUTUBE_SHORTS.platform_id: _YOUTUBE_SHORTS,
    _YOUTUBE_LONG.platform_id: _YOUTUBE_LONG,
}


class UnknownPlatform(ValueError):
    """Raised (fail-closed) when an unregistered platform id is requested.

    Mirrors generation/dispatch.py's DispatchError pattern: an unknown surface is
    never a silent default - it names the bad value and stops (ASUR-GATE-01).
    """


def get_platform(platform_id: str | None = None) -> PlatformPack:
    """Return the :class:`PlatformPack` for *platform_id*.

    ``None`` -> the locked default (Instagram Reels). An unregistered id raises
    :class:`UnknownPlatform` naming the offending value and listing the known
    platforms, so a caller can never proceed on an undefined surface.
    """
    pid = DEFAULT_PLATFORM if platform_id is None else platform_id
    try:
        return PLATFORM_REGISTRY[pid]
    except KeyError:
        known = ", ".join(sorted(PLATFORM_REGISTRY))
        raise UnknownPlatform(
            f"unknown platform {pid!r}; known platforms: {known} "
            f"(ASUR-GATE-01: no silent default)"
        ) from None
