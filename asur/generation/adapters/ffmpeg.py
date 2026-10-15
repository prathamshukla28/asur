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

from ...editing.audio_mix import DEFAULT_DUCK_DB, DEFAULT_MUSIC_DB, DEFAULT_VOICE_DB
from ...platforms import get_platform

MODEL = "FFmpeg"
LICENSE = "LGPL/GPL"
MEDIA_TYPE = "video"

# Instagram-Reels fallback dimensions. A ``platform=None`` render reads these so
# the default stays byte-identical (ASUR-VERSION-01; G19 "IG reproduced
# byte-for-byte"). Other platforms read width/height/fps from their FormatSpec
# via the pack registry (SPEC-GAP G20 - resolution must come from the pack, not
# a hard-coded 1080x1920 literal).
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

# Caption safe-area vertical anchor as a fraction of frame height. 0.78 matches
# the editing layer default (asur.editing.captions.style_caption y_fraction=0.78)
# and sits inside the 0.12..0.88 readable band for every pack's safe_area.
_CAPTION_Y_FRACTION = 0.78
# drawtext box styling: white text, semi-opaque dark box, centred horizontally.
_CAPTION_FONT_SIZE_DIVISOR = 22  # font size = frame height // divisor


class RenderError(RuntimeError):
    """Raised when the ffmpeg binary is missing or a render command fails."""


def _ffmpeg_available() -> bool:
    """True only if the ffmpeg binary is on PATH (no network/GPU, no import)."""
    return shutil.which("ffmpeg") is not None


def _scene_captions(timeline: dict[str, Any]) -> list[str]:
    """One caption string per scene index, sourced ONLY from authored overlays.

    Reads the text track's clip overlays (threaded from the screenplay's authored
    ``onscreen_text`` in ``build_timeline_from_generation_plan``). A caption is
    burned only when a text-track clip's ``timeline_start`` lines up with a scene's
    ``start`` AND that clip carries a ``caption`` overlay. No overlay => empty
    string => a clean card with no text (ASUR-HONEST-01 / anti-hallucination §7:
    never invent on-screen words; only authored text is ever drawn).
    """
    scenes = timeline.get("scenes") or []
    # Map scene start time -> caption text from text-track overlays.
    by_start: dict[float, str] = {}
    for track in timeline.get("tracks", []):
        if track.get("type") != "text":
            continue
        for clip in track.get("clips", []):
            for overlay in clip.get("overlays", []):
                if overlay.get("type") != "caption":
                    continue
                text = str(overlay.get("text", "")).strip()
                if not text:
                    continue
                start = float(overlay.get("start", clip.get("timeline_start", 0.0)) or 0.0)
                by_start.setdefault(round(start, 3), text)
    captions: list[str] = []
    for scene in scenes:
        start = round(float(scene.get("start", 0.0) or 0.0), 3)
        captions.append(by_start.get(start, ""))
    return captions


def _scene_backgrounds(
    timeline: dict[str, Any], backgrounds: dict[str, str] | None
) -> list[Path | None]:
    """One background Path (or None) per scene index, matched by scene id (G27).

    A produced background is keyed in ``backgrounds`` by its scene id; the asset
    ref that produced it is ``f"{scene_id}-background"``. A scene with no produced
    image renders a solid colour card (the P10 fallback), so a render with no
    backgrounds at all is byte-identical. A referenced file that is NOT on disk
    fails closed (``RenderError``, ASUR-GATE-01): we never silently drop a visual
    the plan said exists.
    """
    scenes = timeline.get("scenes") or []
    if not backgrounds:
        return [None for _ in scenes]
    resolved: list[Path | None] = []
    for scene in scenes:
        scene_id = str(scene.get("scene_id", ""))
        ref = backgrounds.get(scene_id)
        if not ref:
            resolved.append(None)
            continue
        path = Path(ref)
        if not path.is_file():
            raise RenderError(
                f"background image for scene {scene_id!r} is missing on disk "
                f"({ref!r}); fail closed (ASUR-GATE-01)"
            )
        resolved.append(path)
    return resolved


def _escape_drawtext(text: str) -> str:
    """Escape a caption string for an ffmpeg drawtext ``text=`` value.

    drawtext treats ``\\``, ``:``, ``'``, and ``%`` specially; a filtergraph also
    splits on unescaped commas. Escape conservatively so the real authored words
    render verbatim (no invention, no silent truncation).
    """
    out = text.replace("\\", "\\\\")
    out = out.replace(":", "\\:")
    out = out.replace("'", "\\'")
    out = out.replace("%", "\\%")
    out = out.replace(",", "\\,")
    return out


def _drawtext_filter(text: str, *, height: int) -> str:
    """Build a centred, safe-area drawtext filter for one card's caption."""
    font_size = max(height // _CAPTION_FONT_SIZE_DIVISOR, 12)
    y_px = round(height * _CAPTION_Y_FRACTION)
    escaped = _escape_drawtext(text)
    # x centres the box; y sits on the safe-area anchor; a translucent box keeps
    # white text legible over any card colour.
    return (
        f"drawtext=text='{escaped}'"
        f":fontcolor=white:fontsize={font_size}"
        ":box=1:boxcolor=black@0.5:boxborderw=12"
        f":x=(w-text_w)/2:y={y_px}"
    )


def _scene_durations(timeline: dict[str, Any]) -> list[float]:
    """One duration per scene from the timeline, clamped to a sane minimum.

    A timeline with NO ``scenes`` key at all falls back to a single default-length
    card (a bare {} dict is a minimal valid timeline, not an authored-empty one).
    But an *explicit* empty scene list means "an edit plan was built yet has
    nothing to render" - that fails closed in ``render`` (ASUR-GATE-01), never a
    silent default card.
    """
    scenes = timeline.get("scenes")
    if scenes is None:
        return [_DEFAULT_SCENE_S]
    durations: list[float] = []
    for scene in scenes:
        start = float(scene.get("start", 0.0) or 0.0)
        end = float(scene.get("end", 0.0) or 0.0)
        durations.append(max(end - start, _MIN_SCENE_S))
    return durations


def _render_card(
    index: int,
    seconds: float,
    work: Path,
    *,
    width: int,
    height: int,
    fps: int,
    caption: str = "",
    background: Path | None = None,
    skipped: list[int] | None = None,
) -> Path:
    """Render ONE card at the given resolution/fps (deterministic).

    When ``background`` is given (a real produced image, e.g. an SDXL PNG), the
    card is that image scaled-to-cover and centre-cropped to the frame - a true
    AI visual, not a placeholder (SPEC-GAP G27). When ``background`` is None the
    card is a deterministic solid colour (the P10 fallback), so a render with no
    produced backgrounds is byte-identical.

    When ``caption`` is non-empty, the authored text is burned into the safe area
    via drawtext (joined onto the SAME ``-vf`` chain as any scale/crop), so an
    empty caption + no background renders the exact pre-P11b clean card.
    """
    colour = _PALETTE[index % len(_PALETTE)]
    out = work / f"scene_{index:03d}.mp4"
    # Build the video-filter chain. A background image needs scale-to-cover +
    # centre-crop to the exact frame; the solid-colour source already fills it.
    vf_parts: list[str] = []
    if background is not None:
        cmd = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-framerate",
            str(fps),
            "-t",
            f"{seconds:.3f}",
            "-i",
            str(background),
        ]
        vf_parts.append(
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1"
        )
    else:
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={colour}:s={width}x{height}:r={fps}:d={seconds:.3f}",
        ]
    if caption:
        vf_parts.append(_drawtext_filter(caption, height=height))
    if vf_parts:
        cmd += ["-vf", ",".join(vf_parts)]
    cmd += [
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",  # mandatory: yuv444p shows black on phones
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    if caption and proc.returncode != 0 and "No such filter: 'drawtext'" in (proc.stderr or ""):
        # This ffmpeg build has no libfreetype. Render the card clean (KEEPING the
        # background image) and record the skip so provenance never claims text
        # that is not on screen (ASUR-HONEST-01) instead of failing the render.
        if skipped is not None:
            skipped.append(index)
        return _render_card(
            index, seconds, work, width=width, height=height, fps=fps, background=background
        )
    if proc.returncode != 0 or not out.is_file():
        raise RenderError(f"ffmpeg card render failed (scene {index}): {proc.stderr[-400:]}")
    return out


def _concat(
    cards: list[Path],
    out_path: Path,
    work: Path,
    *,
    audio_path: Path | None = None,
    music_path: Path | None = None,
) -> None:
    """Join per-scene cards into the final MP4 via the concat demuxer.

    Abs paths need ``-safe 0``. The concat-demuxer re-encodes here (simple,
    robust across mismatched inputs); ``+faststart`` makes the file web-ready.

    Audio has three honest states (never a fabricated track):
      * ``audio_path`` + ``music_path`` -> a true two-track mix. Voice sits at
        ``DEFAULT_VOICE_DB`` and music is ducked to ``DEFAULT_MUSIC_DB +
        DEFAULT_DUCK_DB`` so narration stays intelligible, then ``amix`` folds
        them (``asur.editing.audio_mix`` levels).
      * exactly one of them -> single-track mux, trimmed to video length.
      * neither -> silent.
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
    ]
    two_track = audio_path is not None and music_path is not None
    single = (audio_path is not None) ^ (music_path is not None)
    if two_track:
        cmd += ["-i", str(audio_path), "-i", str(music_path)]
    elif single:
        cmd += ["-i", str(audio_path if audio_path is not None else music_path)]
    cmd += [
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
    ]
    if two_track:
        # Voice (input 1) over ducked music (input 2); amix keeps both audible.
        ducked = DEFAULT_MUSIC_DB + DEFAULT_DUCK_DB
        cmd += [
            "-filter_complex",
            (
                f"[1:a]volume={DEFAULT_VOICE_DB}dB[v];"
                f"[2:a]volume={ducked}dB[m];"
                "[v][m]amix=inputs=2:duration=longest:dropout_transition=0[a]"
            ),
            "-map",
            "0:v",
            "-map",
            "[a]",
            "-c:a",
            "aac",
            "-shortest",
        ]
    elif single:
        cmd += ["-c:a", "aac", "-shortest"]
    cmd += [str(out_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
    if proc.returncode != 0 or not out_path.is_file():
        raise RenderError(f"ffmpeg concat failed: {proc.stderr[-400:]}")


def render(
    timeline: Any,
    out_path: str,
    *,
    platform: str | None = None,
    audio_path: str | None = None,
    music_path: str | None = None,
    backgrounds: dict[str, str] | None = None,
    **params: Any,
) -> dict[str, Any]:
    """Render a Timeline (dict or ``.to_dict()``-able) to a real MP4 file.

    Resolution and fps come from the chosen platform pack's ``FormatSpec``
    (SPEC-GAP G20): ``platform=None`` resolves to the Instagram-Reels default and
    stays byte-identical at 1080x1920 (ASUR-VERSION-01), while ``youtube_long``
    renders 16:9 1920x1080. An unknown platform id fails closed via
    ``get_platform`` (UnknownPlatform) before any work.

    Returns a provenance+license block (ASUR-PROV-01) describing the output:
    model, license, media type, the output path, and basic structural facts.
    Fails closed (``RenderError``) when the ffmpeg binary is absent and when the
    timeline declares an explicit empty scene list, so a stdlib-only machine
    without ffmpeg - or an edit plan with nothing to render - gets a clear
    message, never a silent pass (ASUR-GATE-01).
    """
    spec = get_platform(platform).format_spec
    width, height, fps = spec.width, spec.height, spec.fps

    if not _ffmpeg_available():
        raise RenderError(
            "FFmpeg adapter needs the ffmpeg binary on PATH "
            "(brew install ffmpeg / apt install ffmpeg). No model download needed."
        )

    tl = timeline.to_dict() if hasattr(timeline, "to_dict") else dict(timeline)
    durations = _scene_durations(tl)
    if not durations:
        raise RenderError(
            "timeline declares an empty scene list; nothing to render "
            "(fail closed, ASUR-GATE-01)"
        )
    captions = _scene_captions(tl)
    scene_backgrounds = _scene_backgrounds(tl, backgrounds)
    skipped: list[int] = []

    voice = Path(audio_path) if audio_path else None
    if voice is None or not voice.is_file():
        voice = None
    music = Path(music_path) if music_path else None
    if music is None or not music.is_file():
        music = None
    audio_tracks = int(voice is not None) + int(music is not None)
    audio_present = audio_tracks >= 1

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="asur_render_") as tmp:
        work = Path(tmp)
        cards = [
            _render_card(
                i,
                dur,
                work,
                width=width,
                height=height,
                fps=fps,
                caption=captions[i] if i < len(captions) else "",
                background=scene_backgrounds[i] if i < len(scene_backgrounds) else None,
                skipped=skipped,
            )
            for i, dur in enumerate(durations)
        ]
        _concat(cards, out, work, audio_path=voice, music_path=music)

    total_s = round(sum(durations), 3)
    backgrounds_used = sum(1 for bg in scene_backgrounds if bg is not None)
    captions_burned_in = any(c for i, c in enumerate(captions) if i not in skipped)
    captions_skipped_reason = (
        "ffmpeg build lacks the drawtext filter (libfreetype); "
        f"{len(skipped)} caption card(s) rendered clean"
        if skipped
        else None
    )
    return {
        "media_type": MEDIA_TYPE,
        "origin": "procedural",
        "file_path": str(out),
        "provenance": {
            "model": MODEL,
            "model_version": "ffmpeg-binary",
            "render_cost_usd": 0,
            "scene_count": len(durations),
            "fps": fps,
            "resolution": f"{width}x{height}",
            "duration_s": total_s,
            "backgrounds_used": backgrounds_used,
            "captions_burned_in": captions_burned_in,
            "captions_skipped_reason": captions_skipped_reason,
            "audio_present": audio_present,
            "audio_tracks": audio_tracks,
            "note": (
                f"deterministic solid-colour {spec.aspect_ratio} cards; "
                "no model, no network, no GPU"
            ),
        },
        "license": {
            "name": LICENSE,
            "commercial_ok": True,
            "note": "FFmpeg is a tool; output of procedural colour cards is unencumbered",
        },
    }


def grab_thumbnail(
    video_path: str,
    out_path: str,
    *,
    timestamp_s: float = 0.0,
) -> dict[str, Any]:
    """Extract ONE still frame from a rendered MP4 as the upload thumbnail (G23).

    Zero new dependencies and no AI: a single ffmpeg frame-grab at the given
    timestamp (the hero/payoff moment of the real render). Fails closed
    (``RenderError``) when the ffmpeg binary is absent or the grab produces no
    file (ASUR-GATE-01). Returns a provenance+license block (ASUR-PROV-01) whose
    origin is ``ffmpeg-framegrab`` and which records the exact source video and
    timestamp, so the thumbnail is never a black box.
    """
    if not _ffmpeg_available():
        raise RenderError(
            "FFmpeg adapter needs the ffmpeg binary on PATH to grab a thumbnail "
            "(brew install ffmpeg / apt install ffmpeg)."
        )
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{timestamp_s:.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    if proc.returncode != 0 or not out.is_file():
        raise RenderError(f"ffmpeg thumbnail grab failed: {proc.stderr[-400:]}")
    return {
        "media_type": "image",
        "origin": "ffmpeg-framegrab",
        "file_path": str(out),
        "provenance": {
            "model": MODEL,
            "model_version": "ffmpeg-binary",
            "origin": "ffmpeg-framegrab",
            "timestamp_s": round(float(timestamp_s), 3),
            "source_video": str(video_path),
            "render_cost_usd": 0,
            "note": "single frame grabbed from the real render; no model, no network, no GPU",
        },
        "license": {
            "name": LICENSE,
            "commercial_ok": True,
            "note": "frame of a procedural colour-card render; unencumbered",
        },
    }
