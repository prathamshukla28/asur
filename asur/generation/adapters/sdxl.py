"""SDXL image adapter (OpenRAIL++-M, no revenue cap) - behind asur[generation].

Real local image generation via Hugging Face ``diffusers`` + ``torch`` on
Apple Silicon (MPS) or CPU. The heavy deps are imported LAZILY inside
``generate`` so this module stays stdlib-only at import time: the boundary
import-linter and a stdlib-only ``pip install .`` keep working, and nothing in
the firewalled control path pulls a media dep (AGENTS.md §4, ADR-0002).

Local-only, human-run, never in CI (no GPU / no network / no ~7 GB download in
CI - G10). The model weights (~7 GB fp16) download on first run via diffusers.
"""

from __future__ import annotations

from typing import Any

MODEL = "SDXL"
LICENSE = "OpenRAIL++-M"
MEDIA_TYPE = "image"
MODEL_ID = "stabilityai/stable-diffusion-xl-base-1.0"
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920

# SDXL is trained on ~1 megapixel buckets; 832x1216 is the valid portrait
# bucket closest to 9:16. We generate there, then resize/pad to the reel frame.
_GEN_WIDTH = 832
_GEN_HEIGHT = 1216
_STEPS = 30
_GUIDANCE = 7.0


def generate(prompt: str, out_path: str, *, seed: int = 0, **params: Any) -> dict[str, Any]:
    """Generate one 1080x1920 PNG for ``prompt`` and return provenance+license.

    Requires the ``asur[generation]`` extra (torch + diffusers + Pillow); raises
    a clear RuntimeError otherwise so callers fail closed (ASUR-GATE-01). Runs on
    MPS (Apple GPU) when available, else CPU. Deterministic per ``seed``.
    """
    try:  # pragma: no cover - requires the generation extra, never in CI
        import torch
        from diffusers import StableDiffusionXLPipeline
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "SDXL adapter needs the generation extra: pip install -e '.[generation]'. "
            "This never runs in CI."
        ) from exc

    # pragma: no cover below - real model run is a human-run, local-only step.
    if torch.backends.mps.is_available():  # pragma: no cover
        device, dtype, variant = "mps", torch.float16, "fp16"
    elif torch.cuda.is_available():  # pragma: no cover
        device, dtype, variant = "cuda", torch.float16, "fp16"
    else:  # pragma: no cover
        device, dtype, variant = "cpu", torch.float32, None

    load_kwargs: dict[str, Any] = {"torch_dtype": dtype, "use_safetensors": True}
    if variant is not None:  # pragma: no cover
        load_kwargs["variant"] = variant
    pipe = StableDiffusionXLPipeline.from_pretrained(MODEL_ID, **load_kwargs)  # pragma: no cover
    pipe = pipe.to(device)  # pragma: no cover
    pipe.enable_attention_slicing()  # pragma: no cover

    generator = torch.Generator(device=device).manual_seed(int(seed))  # pragma: no cover
    image = pipe(  # pragma: no cover
        prompt=prompt,
        num_inference_steps=int(params.get("steps", _STEPS)),
        guidance_scale=float(params.get("guidance", _GUIDANCE)),
        width=_GEN_WIDTH,
        height=_GEN_HEIGHT,
        generator=generator,
    ).images[0]

    # Fit the 832x1216 image into a 1080x1920 reel frame: scale to cover width
    # then centre-crop to the exact frame so there are no borders.
    frame = _fit_to_reel(image, Image, TARGET_WIDTH, TARGET_HEIGHT)  # pragma: no cover
    frame.save(out_path, format="PNG")  # pragma: no cover

    return {  # pragma: no cover
        "media_type": "image",
        "origin": "ai_generated",
        "file_path": out_path,
        "provenance": {
            "model": MODEL,
            "model_version": MODEL_ID,
            "prompt": prompt,
            "seed": int(seed),
            "device": device,
            "render_cost_usd": 0,
            "resolution": f"{TARGET_WIDTH}x{TARGET_HEIGHT}",
            "note": "local SDXL on-device (MPS/CPU); no network at inference once cached",
        },
        "license": {
            "name": LICENSE,
            "commercial_ok": True,
            "note": "OpenRAIL++-M: no revenue cap, but not OSI-open - flag in NOTICE",
        },
    }


def _fit_to_reel(image: Any, Image: Any, width: int, height: int) -> Any:  # pragma: no cover
    """Scale ``image`` to cover a width x height frame, then centre-crop to it."""
    src_w, src_h = image.size
    scale = max(width / src_w, height / src_h)
    new_w, new_h = round(src_w * scale), round(src_h * scale)
    resized = image.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - width) // 2
    top = (new_h - height) // 2
    return resized.crop((left, top, left + width, top + height))
