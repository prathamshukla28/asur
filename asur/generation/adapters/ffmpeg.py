"""FFmpeg render+compose adapter (LGPL/GPL, cost 0) - behind asur[generation].

The LOCKED default renderer. This is the ONE adapter that runs with zero model
downloads and no GPU: it drives the ``ffmpeg`` *binary* via ``subprocess`` to
assemble a real 1080x1920 H.264 MP4 from a Timeline. It needs no third-party
Python package (FFmpeg is a system binary, not an import), so the module stays
importable in a stdlib-only install and simply **fails closed** with a clear
message when the ``ffmpeg`` binary is absent (ASUR-GATE-01).

It is never imported by the stdlib control path. Structural verification of the
rendered file lives in ``asur.generation.hero_proof.verify_render`` (ffprobe).

Honest scope: with no AI models wired yet, each scene renders as a deterministic
solid-colour 9:16 card (pure FFmpeg ``color`` source). That proves the pipeline
writes true pixels offline. When SDXL/Kokoro are wired, their output files feed
the same concat path - this adapter does not change.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

MODEL = "FFmpeg"
LICENSE = "LGPL/GPL"
MEDIA_TYPE = "video"

TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
FPS = 30

# Deterministic 9:16 card colours (dark, legible). One per scene, cycled.
_PALETTE = (
    "0x11151c",
    "0x1b2a3a",
    "0x24313d",
    "0x2c2340",
    "0x3a2330",
    "0x1d3a34",
    "0x2f2a1c",
    "0x27303a",
    "0x191f2b",
)
_MIN_SCENE_S = 1.0
_DEFAULT_SCENE_S = 3.0


class RenderError(RuntimeError):
    """Raised when the ffmpeg binary is missing or a render command fails."""


def _ffmpeg_available() -> bool:
    """True only if the ffmpeg binary is on PATH (no network/GPU, no import)."""
    return shutil.which("ffmpeg") is not None


def _scene_durations(timeline: dict[str, Any]) -> list[float]:
    """One duration per scene from the timeline, clamped to a sane minimum.

    Uses the timeline's ``scenes`` (start/end) when present; falls back to a
    single default-length card so render never produces a zero-length file.
    """
    scenes = timeline.get("scenes") or []
    durations: list[float] = []
    for scene in scenes:
        start = float(scene.get("start", 0.0) or 0.0)
        end = float(scene.get("end", 0.0) or 0.0)
        durations.append(max(end - start, _MIN_SCENE_S))
    if not durations:
        durations = [_DEFAULT_SCENE_S]
    return durations


def _render_card(index: int, seconds: float, work: Path) -> Path:
    """Render ONE solid-colour 1080x1920 card to its own mp4 (deterministic)."""
    colour = _PALETTE[index % len(_PALETTE)]
    out = work / f"scene_{index:03d}.mp4"
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c={colour}:s={TARGET_WIDTH}x{TARGET_HEIGHT}:r={FPS}:d={seconds:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",  # mandatory: yuv444p shows black on phones
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    if proc.returncode != 0 or not out.is_file():
        raise RenderError(f"ffmpeg card render failed (scene {index}): {proc.stderr[-400:]}")
    return out


def _concat(cards: list[Path], out_path: Path, work: Path) -> None:
    """Join per-scene cards into the final MP4 via the concat demuxer.

    Abs paths need ``-safe 0``. The concat-demuxer re-encodes here (simple,
    robust across mismatched inputs); ``+faststart`` makes the file web-ready.
    """
    listing = work / "concat.txt"
    # concat demuxer wants: file '<abs path>' per line (quotes handle spaces).
    listing.write_text("".join(f"file '{c.resolve()}'\n" for c in cards), encoding="utf-8")
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(listing),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
    if proc.returncode != 0 or not out_path.is_file():
        raise RenderError(f"ffmpeg concat failed: {proc.stderr[-400:]}")


def render(timeline: Any, out_path: str, **params: Any) -> dict[str, Any]:
    """Render a Timeline (dict or ``.to_dict()``-able) to a real MP4 file.

    Returns a provenance+license block (ASUR-PROV-01) describing the output:
    model, license, media type, the output path, and basic structural facts.
    Fails closed (``RenderError``) when the ffmpeg binary is absent, so a
    stdlib-only machine without ffmpeg gets a clear message, never a silent pass.
    """
    if not _ffmpeg_available():
        raise RenderError(
            "FFmpeg adapter needs the ffmpeg binary on PATH "
            "(brew install ffmpeg / apt install ffmpeg). No model download needed."
        )

    tl = timeline.to_dict() if hasattr(timeline, "to_dict") else dict(timeline)
    durations = _scene_durations(tl)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="asur_render_") as tmp:
        work = Path(tmp)
        cards = [_render_card(i, dur, work) for i, dur in enumerate(durations)]
        _concat(cards, out, work)

    total_s = round(sum(durations), 3)
    return {
        "media_type": MEDIA_TYPE,
        "origin": "procedural",
        "file_path": str(out),
        "provenance": {
            "model": MODEL,
            "model_version": "ffmpeg-binary",
            "render_cost_usd": 0,
            "scene_count": len(durations),
            "fps": FPS,
            "resolution": f"{TARGET_WIDTH}x{TARGET_HEIGHT}",
            "duration_s": total_s,
            "note": "deterministic solid-colour 9:16 cards; no model, no network, no GPU",
        },
        "license": {
            "name": LICENSE,
            "commercial_ok": True,
            "note": "FFmpeg is a tool; output of procedural colour cards is unencumbered",
        },
    }
