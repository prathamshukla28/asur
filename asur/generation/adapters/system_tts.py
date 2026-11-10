"""Offline narration from the OS speech engine (macOS ``say`` / ``espeak-ng``).

A zero-download voice so the default render is not silent: each script scene's
spoken line is synthesized, time-fitted to that scene's duration (``atempo`` if
the speech runs long, ``apad`` to fill the rest), and the scene clips are joined
into one narration WAV aligned with the timeline. Needs the ``ffmpeg`` binary
plus one of the engines; otherwise ``TTSUnavailable`` is raised and the caller
renders silently (and the viral check flags the missing audio).

License honesty (ASUR-PROV-01): macOS system voices are licensed for personal,
non-commercial use under the macOS licence; espeak-ng output is unencumbered.
The provenance block records which applies. Kokoro (``adapters/kokoro.py``) is
the commercial-friendly neural voice behind ``asur[generation]``.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from ...core.binaries import ffmpeg_bin, ffmpeg_path, ffprobe_bin, ffprobe_path

SAMPLE_RATE = 44100
DEFAULT_RATE_WPM = 175


class TTSUnavailable(RuntimeError):
    """No usable speech engine (or ffmpeg) on this machine."""


def available_engine() -> str | None:
    if ffmpeg_path() is None or ffprobe_path() is None:
        return None
    for engine in ("say", "espeak-ng", "espeak"):
        if shutil.which(engine):
            return engine
    return None


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    if proc.returncode != 0:
        raise TTSUnavailable(f"{cmd[0]} failed: {proc.stderr.strip()[-300:]}")


def _duration(path: Path) -> float:
    proc = subprocess.run(
        [ffprobe_bin(), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, timeout=60, check=False,
    )
    try:
        return float(proc.stdout.strip())
    except ValueError as exc:
        raise TTSUnavailable(f"could not measure synthesized speech {path}") from exc


def _speak(engine: str, text: str, out: Path, rate_wpm: int) -> None:
    if engine == "say":
        _run(["say", "-r", str(rate_wpm), "-o", str(out), "--", text])
    else:
        _run([engine, "-s", str(rate_wpm), "-w", str(out), "--", text])


def synthesize_narration(
    segments: list[dict[str, Any]],
    out_path: str | Path,
    *,
    rate_wpm: int = DEFAULT_RATE_WPM,
) -> dict[str, Any]:
    """Write one narration WAV whose segment i spans exactly segments[i] duration.

    ``segments`` is a list of ``{"start": s, "end": e, "text": str}`` in timeline
    order. Empty text (or a "(none ...)" visual beat) becomes silence.
    """
    engine = available_engine()
    if engine is None:
        raise TTSUnavailable("no system speech engine (say/espeak-ng) and ffmpeg found")
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fitted = 0
    with tempfile.TemporaryDirectory(prefix="asur_tts_") as tmp:
        work = Path(tmp)
        parts: list[Path] = []
        for i, seg in enumerate(segments):
            dur = max(0.1, float(seg["end"]) - float(seg["start"]))
            text = " ".join(str(seg.get("text", "")).split())
            part = work / f"part_{i:03d}.wav"
            if not text or text.startswith("(none"):
                _run([ffmpeg_bin(), "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                      f"anullsrc=r={SAMPLE_RATE}:cl=mono", "-t", f"{dur:.3f}", str(part)])
            else:
                raw = work / f"raw_{i:03d}.{'aiff' if engine == 'say' else 'wav'}"
                _speak(engine, text, raw, rate_wpm)
                spoken = _duration(raw)
                # Leave 0.15s of air at the cut; speed up (max 1.6x) only if needed.
                tempo = min(1.6, max(1.0, spoken / max(0.1, dur - 0.15)))
                fitted += int(tempo > 1.0)
                _run([ffmpeg_bin(), "-y", "-loglevel", "error", "-i", str(raw), "-af",
                      f"atempo={tempo:.4f},apad=whole_dur={dur:.3f},atrim=0:{dur:.3f}",
                      "-ar", str(SAMPLE_RATE), "-ac", "1", str(part)])
            parts.append(part)
        listing = work / "parts.txt"
        listing.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
        _run([ffmpeg_bin(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
              "-i", str(listing), "-c:a", "pcm_s16le", str(out)])
    commercial = engine != "say"
    return {
        "media_type": "audio",
        "origin": "system-tts",
        "file_path": str(out),
        "provenance": {
            "model": f"system TTS ({engine})",
            "rate_wpm": rate_wpm,
            "segments": len(segments),
            "segments_sped_up_to_fit": fitted,
            "duration_s": round(_duration(out), 3),
            "render_cost_usd": 0,
        },
        "license": {
            "name": "macOS system voice" if engine == "say" else "espeak-ng (GPL-3.0 tool)",
            "commercial_ok": commercial,
            "note": (
                "macOS voices: personal, non-commercial use per the macOS licence; "
                "use Kokoro or espeak-ng for commercial posting"
                if engine == "say"
                else "synthesized speech output is not encumbered by the tool licence"
            ),
        },
    }
