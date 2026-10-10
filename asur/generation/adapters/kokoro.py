"""Kokoro-82M voice adapter (Apache-2.0, no cloning) - behind asur[generation].

Real local text-to-speech via the ``kokoro`` KPipeline. The heavy deps are
imported LAZILY inside ``synthesize`` so this module stays stdlib-only at import
time: the boundary import-linter and a stdlib-only ``pip install .`` keep
working, and nothing in the firewalled control path pulls a media dep
(AGENTS.md §4, ADR-0002).

Local-only, human-run, never in CI (no GPU / no network / no model download in
CI - G10). The model weights download on first run via the kokoro package.
"""

from __future__ import annotations

from typing import Any

MODEL = "Kokoro-82M"
LICENSE = "Apache-2.0"
MEDIA_TYPE = "audio_voice"
MODEL_ID = "hexgrad/Kokoro-82M"

# 24 kHz mono is Kokoro's native output rate; American-English voice + lang code
# are the documented defaults. Narration is deterministic for a given voice+text.
_SAMPLE_RATE = 24000
_DEFAULT_VOICE = "af_heart"
_LANG_CODE = "a"


def synthesize(text: str, out_path: str, *, voice: str = "default", **params: Any) -> dict[str, Any]:
    """Synthesize narration for ``text`` to a WAV at ``out_path``; return provenance+license.

    Requires the ``asur[generation]`` extra (kokoro + soundfile); raises a clear
    RuntimeError otherwise so callers fail closed (ASUR-GATE-01). Runs on CUDA
    when available, else CPU. Concatenates all synthesized segments into one
    24 kHz mono WAV file.
    """
    try:  # pragma: no cover - requires the generation extra, never in CI
        import numpy as np
        import soundfile as sf  # type: ignore[import-untyped]
        from kokoro import KPipeline  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Kokoro adapter needs the generation extra: pip install -e '.[generation]'. "
            "This never runs in CI."
        ) from exc

    # pragma: no cover below - real voice synthesis is a human-run, local-only step.
    voice_id = _DEFAULT_VOICE if voice == "default" else voice  # pragma: no cover
    lang_code = str(params.get("lang_code", _LANG_CODE))  # pragma: no cover
    speed = float(params.get("speed", 1.0))  # pragma: no cover

    pipeline = KPipeline(lang_code=lang_code)  # pragma: no cover
    chunks: list[Any] = []  # pragma: no cover
    for _graphemes, _phonemes, audio in pipeline(text, voice=voice_id, speed=speed):  # pragma: no cover
        chunks.append(audio)

    if not chunks:  # pragma: no cover
        raise RuntimeError("Kokoro produced no audio for the given text.")

    waveform = np.concatenate(chunks)  # pragma: no cover
    sf.write(out_path, waveform, _SAMPLE_RATE)  # pragma: no cover
    duration_s = round(len(waveform) / float(_SAMPLE_RATE), 3)  # pragma: no cover

    return {  # pragma: no cover
        "media_type": MEDIA_TYPE,
        "origin": "ai_generated",
        "file_path": out_path,
        "provenance": {
            "model": MODEL,
            "model_version": MODEL_ID,
            "text": text,
            "voice": voice_id,
            "lang_code": lang_code,
            "speed": speed,
            "sample_rate": _SAMPLE_RATE,
            "duration_s": duration_s,
            "render_cost_usd": 0,
            "note": "local Kokoro-82M on-device; no network at inference once cached",
        },
        "license": {
            "name": LICENSE,
            "commercial_ok": True,
            "note": "Apache-2.0: permissive, no revenue cap, no voice cloning",
        },
    }
