"""Wan 2.2 TI2V-5B video adapter (Apache-2.0) - behind asur[generation].

Declaration-only shell. The heavy dependency (ComfyUI / torch pipeline for Wan
2.2) is imported lazily inside ``generate`` and only runs locally when a human
has installed the extra. Never imported by the stdlib control path; never called
in tests (no GPU/network/real-model in CI - G10).
"""

from __future__ import annotations

from typing import Any

MODEL = "Wan 2.2 TI2V-5B"
LICENSE = "Apache-2.0"
MEDIA_TYPE = "video"


def generate(prompt: str, *, seed: int = 0, **params: Any) -> dict[str, Any]:
    """Generate a local video clip. Requires asur[generation]; raises otherwise."""
    try:  # pragma: no cover - requires the generation extra + GPU, never in CI
        import torch  # noqa: F401  (heavy dep, imported lazily on purpose)
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Wan 2.2 adapter needs the generation extra: pip install -e '.[generation]' "
            "(plus a local ComfyUI/Wan 2.2 install). This never runs in CI."
        ) from exc
    raise NotImplementedError(  # pragma: no cover
        "Wan 2.2 local generation is a human-run, local-only step (GPU required)."
    )
