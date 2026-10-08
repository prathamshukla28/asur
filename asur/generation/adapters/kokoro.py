"""Kokoro-82M voice adapter (Apache-2.0, no cloning) - behind asur[generation].

Declaration-only shell. Heavy dep imported lazily inside ``synthesize``;
local-only, human-run, never in CI (G10). Never imported by the stdlib control
path.
"""

from __future__ import annotations

from typing import Any

MODEL = "Kokoro-82M"
LICENSE = "Apache-2.0"
MEDIA_TYPE = "audio_voice"


def synthesize(text: str, *, voice: str = "default", **params: Any) -> dict[str, Any]:
    """Synthesize narration locally. Requires asur[generation]; raises otherwise."""
    try:  # pragma: no cover - requires the generation extra, never in CI
        import kokoro  # noqa: F401
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Kokoro adapter needs the generation extra: pip install -e '.[generation]'. "
            "This never runs in CI."
        ) from exc
    raise NotImplementedError(  # pragma: no cover
        "Kokoro local voice synthesis is a human-run, local-only step."
    )
