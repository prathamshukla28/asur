"""Stable Audio 3.0 music/SFX adapter (Community, free < $1M rev) - behind asur[generation].

Declaration-only shell. Heavy dep imported lazily inside ``generate``;
local-only, human-run, never in CI (G10). Never imported by the stdlib control
path.
"""

from __future__ import annotations

from typing import Any

MODEL = "Stable Audio 3.0"
LICENSE = "Stable Audio Community"
MEDIA_TYPE = "audio_music"


def generate(prompt: str, *, seconds: float = 10.0, **params: Any) -> dict[str, Any]:
    """Generate an instrumental bed locally. Requires asur[generation]; raises otherwise."""
    try:  # pragma: no cover - requires the generation extra, never in CI
        import stable_audio_tools  # type: ignore[import-not-found]  # noqa: F401
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Stable Audio adapter needs the generation extra: "
            "pip install -e '.[generation]'. This never runs in CI."
        ) from exc
    raise NotImplementedError(  # pragma: no cover
        "Stable Audio local generation is a human-run, local-only step."
    )
