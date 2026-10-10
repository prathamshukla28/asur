"""Stable Audio 3.0 music/SFX adapter (Community, free < $1M rev) - behind asur[generation].

Real local instrumental generation via ``stable_audio_tools``. The heavy deps
are imported LAZILY inside ``generate`` so this module stays stdlib-only at
import time: the boundary import-linter and a stdlib-only ``pip install .`` keep
working, and nothing in the firewalled control path pulls a media dep
(AGENTS.md §4, ADR-0002).

Local-only, human-run, never in CI (no GPU / no network / no model download in
CI - G10). The model weights download on first run via stable_audio_tools.
"""

from __future__ import annotations

from typing import Any

MODEL = "Stable Audio 3.0"
LICENSE = "Stable Audio Community"
MEDIA_TYPE = "audio_music"
MODEL_ID = "stabilityai/stable-audio-open-1.0"

# Stable Audio Open is trained at 44.1 kHz stereo; those are its native output
# params. Generation is deterministic for a given seed + prompt + duration.
_SAMPLE_RATE = 44100
_STEPS = 100
_CFG_SCALE = 7.0


def generate(prompt: str, out_path: str, *, seconds: float = 10.0, **params: Any) -> dict[str, Any]:
    """Generate an instrumental bed for ``prompt`` to a WAV at ``out_path``.

    Requires the ``asur[generation]`` extra (stable_audio_tools + torch +
    torchaudio); raises a clear RuntimeError otherwise so callers fail closed
    (ASUR-GATE-01). Runs on CUDA when available, else CPU. Deterministic per
    ``seed``.
    """
    try:  # pragma: no cover - requires the generation extra, never in CI
        import torch
        import torchaudio  # type: ignore[import-untyped]
        from stable_audio_tools import (  # type: ignore[import-not-found]
            get_pretrained_model,
        )
        from stable_audio_tools.inference.generation import (  # type: ignore[import-not-found]
            generate_diffusion_cond,
        )
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Stable Audio adapter needs the generation extra: "
            "pip install -e '.[generation]'. This never runs in CI."
        ) from exc

    # pragma: no cover below - real audio generation is a human-run, local-only step.
    device = "cuda" if torch.cuda.is_available() else "cpu"  # pragma: no cover
    seed = int(params.get("seed", 0))  # pragma: no cover

    model, model_config = get_pretrained_model(MODEL_ID)  # pragma: no cover
    sample_rate = int(model_config["sample_rate"])  # pragma: no cover
    sample_size = int(model_config["sample_size"])  # pragma: no cover
    model = model.to(device)  # pragma: no cover

    conditioning = [  # pragma: no cover
        {"prompt": prompt, "seconds_start": 0, "seconds_total": float(seconds)}
    ]
    output = generate_diffusion_cond(  # pragma: no cover
        model,
        steps=int(params.get("steps", _STEPS)),
        cfg_scale=float(params.get("cfg_scale", _CFG_SCALE)),
        conditioning=conditioning,
        sample_size=sample_size,
        device=device,
        seed=seed,
    )

    # (batch, channels, samples) -> (channels, samples), peak-normalised int16.
    output = output.squeeze(0)  # pragma: no cover
    output = output.div(torch.max(torch.abs(output))).clamp(-1, 1)  # pragma: no cover
    output = output.mul(32767).to(torch.int16).cpu()  # pragma: no cover
    torchaudio.save(out_path, output, sample_rate)  # pragma: no cover
    duration_s = round(output.shape[-1] / float(sample_rate), 3)  # pragma: no cover

    return {  # pragma: no cover
        "media_type": MEDIA_TYPE,
        "origin": "ai_generated",
        "file_path": out_path,
        "provenance": {
            "model": MODEL,
            "model_version": MODEL_ID,
            "prompt": prompt,
            "seed": seed,
            "device": device,
            "sample_rate": sample_rate,
            "requested_seconds": float(seconds),
            "duration_s": duration_s,
            "render_cost_usd": 0,
            "note": "local Stable Audio Open on-device; no network at inference once cached",
        },
        "license": {
            "name": LICENSE,
            "commercial_ok": True,
            "revenue_cap_usd": 1_000_000,
            "note": "Stable Audio Community: free under $1M annual revenue; flag in NOTICE",
        },
    }
