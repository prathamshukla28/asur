"""Measure a RENDERED video file with ffprobe/ffmpeg (stdlib-only, subprocess).

This is what makes VIRAL CHECK judge bytes instead of a plan. ``measure_video``
runs three local, offline passes over the actual MP4 and returns plain numbers:

  1. ffprobe   - container + stream facts: duration, width/height, fps, codecs,
                 whether an audio stream exists, file size, bitrate.
  2. audio     - one ffmpeg pass with ``ebur128`` (integrated loudness, LUFS),
                 ``volumedetect`` (mean/max dBFS) and ``silencedetect``
                 (silent intervals below -50 dBFS lasting >= 0.5s).
  3. video     - one ffmpeg pass (downscaled to 270px wide for speed) with
                 ``scdet`` (scene-change times + scores), ``blackdetect`` (black
                 intervals) and ``freezedetect`` (static/frozen intervals).

It also hashes the file (sha256) so the viral_check artifact is bound to the
exact bytes it measured. Nothing here imports a media library: ffmpeg is a
system binary. If the binaries are missing, ``ProbeUnavailable`` is raised and
callers must fail closed (no measurement is never "looks fine").
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from ..core.binaries import ffmpeg_bin, ffmpeg_path, ffprobe_bin, ffprobe_path

__all__ = [
    "OPENING_WINDOW_S",
    "SCENE_THRESHOLD",
    "ProbeUnavailable",
    "measure_video",
    "tools_available",
]

# scdet score (0-100) above which a frame counts as a scene change.
SCENE_THRESHOLD = 10.0
# The "first three seconds" window the opening measurements cover.
OPENING_WINDOW_S = 3.0
SILENCE_NOISE_DB = -50
SILENCE_MIN_S = 0.5
FREEZE_MIN_S = 0.5
BLACK_MIN_S = 0.1


class ProbeUnavailable(RuntimeError):
    """ffprobe/ffmpeg are missing or the file could not be read as video."""


def tools_available() -> bool:
    return ffprobe_path() is not None and ffmpeg_path() is not None


def _run(cmd: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProbeUnavailable(f"{cmd[0]} failed to run: {exc}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _fps(rate: str | None) -> float | None:
    if not rate or rate == "0/0":
        return None
    num, _, den = rate.partition("/")
    try:
        return round(float(num) / float(den or 1), 3)
    except (ValueError, ZeroDivisionError):
        return None


def _intervals(log: str, start_key: str, end_key: str, total: float) -> list[tuple[float, float]]:
    """Pair start/end markers from an ffmpeg log; an open interval ends at EOF."""
    events = re.findall(rf"({re.escape(start_key)}|{re.escape(end_key)})\s*:?\s*(-?[\d.]+)", log)
    spans: list[tuple[float, float]] = []
    open_at: float | None = None
    for key, value in events:
        t = float(value)
        if key == start_key:
            open_at = t
        elif open_at is not None:
            spans.append((max(0.0, open_at), min(total, t)))
            open_at = None
    if open_at is not None and total > open_at:
        spans.append((max(0.0, open_at), total))
    return spans


def _overlap(spans: list[tuple[float, float]], lo: float, hi: float) -> float:
    return sum(max(0.0, min(e, hi) - max(s, lo)) for s, e in spans)


def _probe_streams(path: Path, timeout: float) -> dict[str, Any]:
    proc = _run(
        [ffprobe_bin(), "-v", "error", "-show_entries",
         "format=duration,size,bit_rate:stream=codec_type,codec_name,width,height,"
         "r_frame_rate,sample_rate,channels",
         "-of", "json", str(path)],
        timeout,
    )
    if proc.returncode != 0:
        raise ProbeUnavailable(f"ffprobe could not read {path}: {proc.stderr.strip()[-300:]}")
    data = json.loads(proc.stdout or "{}")
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if video is None:
        raise ProbeUnavailable(f"{path} has no video stream")
    fmt = data.get("format") or {}
    return {
        "duration_s": round(float(fmt.get("duration") or 0.0), 3),
        "size_bytes": int(fmt.get("size") or 0),
        "bit_rate": int(fmt.get("bit_rate") or 0),
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "fps": _fps(video.get("r_frame_rate")),
        "video_codec": video.get("codec_name"),
        "audio_present": audio is not None,
        "audio_codec": audio.get("codec_name") if audio else None,
    }


def _audio_pass(path: Path, duration: float, timeout: float) -> dict[str, Any]:
    proc = _run(
        [ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af",
         f"ebur128=framelog=quiet,volumedetect,"
         f"silencedetect=noise={SILENCE_NOISE_DB}dB:d={SILENCE_MIN_S}",
         "-f", "null", "-"],
        timeout,
    )
    log = proc.stderr or ""
    lufs = re.findall(r"\bI:\s*(-?[\d.]+|-inf)\s*LUFS", log)
    mean = re.search(r"mean_volume:\s*(-?[\d.]+|-inf)\s*dB", log)
    peak = re.search(r"max_volume:\s*(-?[\d.]+|-inf)\s*dB", log)
    silences = _intervals(log, "silence_start", "silence_end", duration)

    def num(text: str | None) -> float | None:
        if text is None or text == "-inf":
            return None
        return float(text)

    return {
        "integrated_lufs": num(lufs[-1]) if lufs else None,
        "mean_volume_db": num(mean.group(1)) if mean else None,
        "max_volume_db": num(peak.group(1)) if peak else None,
        "silence_total_s": round(sum(e - s for s, e in silences), 3),
        "longest_silence_s": round(max((e - s for s, e in silences), default=0.0), 3),
    }


def _video_pass(path: Path, duration: float, timeout: float) -> dict[str, Any]:
    proc = _run(
        [ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(path), "-an", "-vf",
         f"scale=270:-2,scdet=threshold={SCENE_THRESHOLD},"
         f"blackdetect=d={BLACK_MIN_S}:pix_th=0.10,"
         f"freezedetect=n=0.003:d={FREEZE_MIN_S}",
         "-f", "null", "-"],
        timeout,
    )
    log = proc.stderr or ""
    cuts = [
        (float(t), float(sc))
        for sc, t in re.findall(r"lavfi\.scd\.score:\s*([\d.]+),\s*lavfi\.scd\.time:\s*([\d.]+)", log)
    ]
    blacks = [
        (float(s), float(e))
        for s, e in re.findall(r"black_start:\s*([\d.]+)\s+black_end:\s*([\d.]+)", log)
    ]
    freezes = _intervals(
        log, "lavfi.freezedetect.freeze_start", "lavfi.freezedetect.freeze_end", duration
    )
    window = min(OPENING_WINDOW_S, duration)
    opening_cuts = [c for c in cuts if 0.0 < c[0] <= window]
    black_start = next((e - s for s, e in blacks if s <= 0.05), 0.0)
    frozen_total = _overlap(freezes, 0.0, duration)
    return {
        "scene_changes_total": len(cuts),
        "scene_change_times_s": [round(t, 3) for t, _ in cuts],
        "cuts_per_minute": round(len(cuts) / (duration / 60.0), 2) if duration > 0 else 0.0,
        "scene_changes_first_3s": len(opening_cuts),
        "max_scene_score_first_3s": round(max((sc for _, sc in opening_cuts), default=0.0), 3),
        "black_at_start_s": round(black_start, 3),
        "black_total_s": round(_overlap(blacks, 0.0, duration), 3),
        "frozen_total_s": round(frozen_total, 3),
        "frozen_ratio": round(frozen_total / duration, 3) if duration > 0 else 0.0,
        "opening_frozen_s": round(_overlap(freezes, 0.0, window), 3),
    }


def measure_video(path: str | Path, *, timeout_s: float = 300.0) -> dict[str, Any]:
    """Measure a rendered video. Raises ProbeUnavailable if it cannot be measured."""
    video = Path(path)
    if not video.is_file():
        raise ProbeUnavailable(f"video file not found: {video}")
    if not tools_available():
        raise ProbeUnavailable(
            "ffprobe/ffmpeg not found (PATH, or ASUR_FFMPEG/ASUR_FFPROBE); cannot measure the render"
        )
    facts: dict[str, Any] = {"file": str(video), "sha256": _sha256(video)}
    facts.update(_probe_streams(video, timeout_s))
    duration = float(facts["duration_s"])
    if facts["audio_present"]:
        facts.update(_audio_pass(video, duration, timeout_s))
    facts.update(_video_pass(video, duration, timeout_s))
    facts["measured_by"] = "ffprobe+ffmpeg (ebur128, volumedetect, silencedetect, scdet, blackdetect, freezedetect)"
    return facts
