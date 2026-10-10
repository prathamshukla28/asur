"""faster-whisper caption adapter (MIT) - behind asur[generation].

Real local word-level transcription via ``faster-whisper`` (CTranslate2 Whisper).
The heavy dep is imported LAZILY inside ``transcribe`` so this module stays
stdlib-only at import time: the boundary import-linter and a stdlib-only
``pip install .`` keep working, and nothing in the firewalled control path pulls
a media dep (AGENTS.md §4, ADR-0002).

Local-only, human-run, never in CI (no GPU / no network / no model download in
CI - G10). The model weights download on first run via faster-whisper.
"""

from __future__ import annotations

from typing import Any

MODEL = "faster-whisper"
LICENSE = "MIT"
MEDIA_TYPE = "captions"
MODEL_SIZE = "base"

# Greedy decode (beam_size=1) + word timestamps keeps output deterministic for a
# given audio file and model size, which is what the caption/timeline step needs.
_BEAM_SIZE = 1


def transcribe(audio_path: str, *, language: str = "en", **params: Any) -> dict[str, Any]:
    """Produce word-timed captions for ``audio_path`` and return provenance+license.

    Requires the ``asur[generation]`` extra (faster-whisper); raises a clear
    RuntimeError otherwise so callers fail closed (ASUR-GATE-01). Runs on CUDA
    when available, else CPU. Returns the full transcript plus per-word
    ``start``/``end``/``word`` timings the timeline and caption steps consume.
    """
    try:  # pragma: no cover - requires the generation extra, never in CI
        from faster_whisper import WhisperModel  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "faster-whisper adapter needs the generation extra: "
            "pip install -e '.[generation]'. This never runs in CI."
        ) from exc

    # pragma: no cover below - real transcription is a human-run, local-only step.
    try:  # pragma: no cover
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:  # pragma: no cover - torch optional for CPU-only whisper
        device = "cpu"
    compute_type = "float16" if device == "cuda" else "int8"  # pragma: no cover

    model_size = str(params.get("model_size", MODEL_SIZE))  # pragma: no cover
    model = WhisperModel(model_size, device=device, compute_type=compute_type)  # pragma: no cover

    segments, info = model.transcribe(  # pragma: no cover
        audio_path,
        language=None if language == "auto" else language,
        beam_size=int(params.get("beam_size", _BEAM_SIZE)),
        word_timestamps=True,
    )

    words: list[dict[str, Any]] = []  # pragma: no cover
    text_parts: list[str] = []  # pragma: no cover
    for segment in segments:  # pragma: no cover
        text_parts.append(segment.text)
        for word in segment.words or []:  # pragma: no cover
            words.append(
                {
                    "word": word.word,
                    "start_s": round(float(word.start), 3),
                    "end_s": round(float(word.end), 3),
                    "probability": round(float(word.probability), 4),
                }
            )

    transcript = "".join(text_parts).strip()  # pragma: no cover
    detected_language = getattr(info, "language", language)  # pragma: no cover
    duration_s = round(float(getattr(info, "duration", 0.0)), 3)  # pragma: no cover

    return {  # pragma: no cover
        "media_type": MEDIA_TYPE,
        "origin": "ai_generated",
        "file_path": audio_path,
        "transcript": transcript,
        "words": words,
        "provenance": {
            "model": MODEL,
            "model_version": model_size,
            "source_audio": audio_path,
            "language": detected_language,
            "device": device,
            "duration_s": duration_s,
            "word_count": len(words),
            "render_cost_usd": 0,
            "note": "local faster-whisper on-device; no network at inference once cached",
        },
        "license": {
            "name": LICENSE,
            "commercial_ok": True,
            "note": "MIT: permissive, no revenue cap",
        },
    }
