"""faster-whisper caption adapter (MIT) - behind asur[generation].

Declaration-only shell. Heavy dep imported lazily inside ``transcribe``;
local-only, human-run, never in CI (G10). Never imported by the stdlib control
path.
"""

from __future__ import annotations

from typing import Any

MODEL = "faster-whisper"
LICENSE = "MIT"
MEDIA_TYPE = "captions"


def transcribe(audio_path: str, *, language: str = "en", **params: Any) -> dict[str, Any]:
    """Produce word-timed captions locally. Requires asur[generation]; raises otherwise."""
    try:  # pragma: no cover - requires the generation extra, never in CI
        import faster_whisper  # type: ignore[import-untyped]  # noqa: F401
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "faster-whisper adapter needs the generation extra: "
            "pip install -e '.[generation]'. This never runs in CI."
        ) from exc
    raise NotImplementedError(  # pragma: no cover
        "faster-whisper local transcription is a human-run, local-only step."
    )
