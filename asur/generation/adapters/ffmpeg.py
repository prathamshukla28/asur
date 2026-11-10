"""FFmpeg render+compose adapter (LGPL/GPL, cost 0) - behind asur[generation].

The LOCKED default renderer. This is the ONE adapter that runs with zero model
downloads and no GPU: it drives the ``ffmpeg`` *binary* via ``subprocess`` to
assemble a real 1080x1920 H.264 MP4 from a Timeline. It needs no third-party
Python package (FFmpeg is a system binary, not an import), so the module stays
importable in a stdlib-only install and simply **fails closed** with a clear
message when the ``ffmpeg`` binary is absent (ASUR-GATE-01).

It is never imported by the stdlib control path. Structural verification of the
rendered file lives in ``asur.generation.hero_proof.verify_render`` (ffprobe).

Honest scope: with no AI models wired, each scene renders as a deterministic
animated card, all pure FFmpeg filters (no new dependency, no model):

  * background   - a slowly rotating two-colour gradient (``gradients`` source),
                   or, when a produced image exists, a slow Ken Burns zoom
                   (``zoompan``) over that image;
  * progress bar - a thin bar that fills across the whole video (``overlay`` with
                   a time expression, offset by the scene's start);
  * captions     - authored text only, word-wrapped to the frame, each line
                   fading and sliding in on a fixed stagger (``drawtext`` alpha/y
                   expressions);
  * transitions  - a short ``xfade`` push between consecutive scenes.

Every parameter is a module constant, so the same timeline always yields the
same filtergraph. The motion is real pixel change, so the viral check's
``freezedetect``/``scdet`` measurements see it without any special-casing.
"""

from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import textwrap
import warnings
from pathlib import Path
from typing import Any

from ...core.binaries import ffmpeg_bin, ffmpeg_path
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

# Deterministic card gradients, one (c0, c1) pair per scene, cycled. The list has
# an even length and alternates dark / bright (mean luma ~60 vs ~170), so every
# scene change - including the wrap-around - is a large real visual change and
# is measurable as one; each pair also spans ~50-80 luma levels internally, so
# its slow rotation is visible motion rather than a near-flat field.
_GRADIENTS = (
    ("0x0b1d51", "0x7c3aed"),  # dark:   navy -> violet
    ("0xfde047", "0xf97316"),  # bright: yellow -> orange
    ("0x022c22", "0x0f766e"),  # dark:   pine -> teal
    ("0x67e8f9", "0x3b82f6"),  # bright: light cyan -> blue
    ("0x2e1065", "0xc026d3"),  # dark:   deep purple -> fuchsia
    ("0xfda4af", "0xf43f5e"),  # bright: light rose -> rose
    ("0x450a0a", "0xc2410c"),  # dark:   maroon -> burnt orange
    ("0xbef264", "0x10b981"),  # bright: light lime -> emerald
    ("0x0f172a", "0x6d28d9"),  # dark:   slate -> purple
    ("0xfed7aa", "0xea580c"),  # bright: peach -> orange
)
# Kept for callers that want a flat per-scene colour (first stop of the gradient).
_PALETTE = tuple(c0 for c0, _ in _GRADIENTS)
# Gradient rotation per frame (ffmpeg ``gradients`` speed). Measured: at 0.01 the
# viral check's freezedetect still sees long frozen runs; 0.015 reads as gentle,
# continuous motion.
_GRADIENT_SPEED = 0.015
# Ken Burns zoom over a produced background image: 1.00 -> 1.0 + this per scene.
_KEN_BURNS_ZOOM = 0.08
# Scene transition (xfade). 0 disables transitions (hard cuts via concat).
_TRANSITION = "slideup"
_TRANSITION_S = 0.12
# Progress bar: height = frame height // divisor, drawn at the top margin.
_PROGRESS_BAR_DIVISOR = 160
_PROGRESS_BAR_TOP_FRACTION = 0.02
_MIN_SCENE_S = 1.0
_DEFAULT_SCENE_S = 3.0

# Caption safe-area vertical anchor as a fraction of frame height. 0.78 matches
# the editing layer default (asur.editing.captions.style_caption y_fraction=0.78)
# and sits inside the 0.12..0.88 readable band for every pack's safe_area. A
# multi-line caption moves up so its last line still ends inside the band.
_CAPTION_Y_FRACTION = 0.78
_CAPTION_SAFE_TOP = 0.12
_CAPTION_SAFE_BOTTOM = 0.88
# drawtext styling: white text on a semi-opaque dark box, centred per line.
_CAPTION_FONT_SIZE_DIVISOR = 22  # font size = frame height // divisor
_CAPTION_LINE_SPACING = 1.45  # line pitch = font size x this
_CAPTION_WRAP_WIDTH = 0.86  # usable text width as a share of frame width
_CAPTION_CHAR_WIDTH = 0.55  # average glyph advance as a share of font size
# Reveal animation: line i fades in over _FADE_S starting at FIRST + i x STAGGER,
# sliding up from SLIDE (fraction of frame height) below its resting place.
_CAPTION_FIRST_DELAY_S = 0.10
_CAPTION_STAGGER_S = 0.22
_CAPTION_FADE_S = 0.35
_CAPTION_SLIDE_FRACTION = 0.015
# The hook frame used for the thumbnail: by then a caption of up to six lines
# has fully revealed (0.10 + 5 x 0.22 + 0.35 = 1.55s).
HOOK_FRAME_S = 1.6

# Font for drawtext. ASUR_FONTFILE wins; otherwise the first of these that
# exists. With none found, drawtext falls back to fontconfig's default font.
ENV_FONTFILE = "ASUR_FONTFILE"
_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "C:\\Windows\\Fonts\\arialbd.ttf",
)


class RenderError(RuntimeError):
    """Raised when the ffmpeg binary is missing or a render command fails."""


# Every render call runs ffmpeg with these flags so a failure's stderr holds the
# actual messages, not thousands of progress lines: ``-nostats`` drops the
# ``frame= ... speed=`` updates and ``-loglevel warning`` keeps warnings and
# errors. (A raw ``stderr[-400:]`` used to show only progress, hiding why CI
# renders failed.)
_QUIET = ["-hide_banner", "-nostats", "-loglevel", "warning"]


def _failure(what: str, proc: Any, *, keep: int = 12) -> str:
    """Readable failure text: exit status (including a fatal signal) + stderr head/tail.

    A process killed by a signal (for example the kernel's OOM killer sending
    SIGKILL) prints no error of its own, so the exit status is often the only
    evidence. Progress lines are dropped; the first and last ``keep`` lines of
    what remains are kept, so neither the first error nor the final one is lost.
    """
    code = getattr(proc, "returncode", None)
    if isinstance(code, int) and code < 0:
        try:
            status = f"killed by {signal.Signals(-code).name}"
        except ValueError:
            status = f"killed by signal {-code}"
    else:
        status = f"exit code {code}"
    raw = str(getattr(proc, "stderr", "") or "").replace("\r", "\n")
    lines = [
        ln.rstrip()
        for ln in raw.split("\n")
        if ln.strip() and not ln.lstrip().startswith(("frame=", "size="))
    ]
    if len(lines) > 2 * keep:
        lines = [*lines[:keep], f"... ({len(lines) - 2 * keep} lines omitted) ...", *lines[-keep:]]
    detail = "\n".join(ln[:300] for ln in lines) or "(no stderr output)"
    return f"{what} ({status}):\n{detail}"


def _run_ffmpeg(cmd: list[str], *, timeout: float, what: str) -> Any:
    """``subprocess.run`` for an ffmpeg command; a timeout becomes a ``RenderError``."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RenderError(f"{what}: timed out after {timeout:.0f}s (fail closed)") from exc


def _ffmpeg_available() -> bool:
    """True only if an ffmpeg binary resolves (PATH or ``ASUR_FFMPEG``)."""
    return ffmpeg_path() is not None


def _font_file() -> Path | None:
    """The font drawtext should use: ``ASUR_FONTFILE``, else a known system font."""
    override = os.environ.get(ENV_FONTFILE, "").strip()
    if override:
        path = Path(override).expanduser()
        if not path.is_file():
            raise RenderError(f"{ENV_FONTFILE}={override!r} is not a file (fail closed)")
        return path
    for candidate in _FONT_CANDIDATES:
        path = Path(candidate)
        if path.is_file():
            return path
    return None


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
    image renders the animated gradient card (the fallback), so a render with no
    backgrounds at all is unaffected. A referenced file that is NOT on disk
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


def _escape_option_value(value: str) -> str:
    """Escape *value* for use as one option value inside an ffmpeg filtergraph.

    FFmpeg parses a ``-vf``/``-filter_complex`` string with TWO escaping levels
    (ffmpeg-filters(1), "Notes on filtergraph escaping"):

      1. the filter's option parser treats ``\\``, ``'`` and ``:`` specially
         (``:`` separates options), so each is backslash-escaped;
      2. the filtergraph parser then treats ``\\``, ``'``, ``[``, ``]``, ``,``
         and ``;`` specially, so the level-1 result is backslash-escaped again.

    Applying both levels means any string (a path with spaces, apostrophes,
    colons, commas, brackets or backslashes) reaches the filter verbatim.
    Arguments are passed to ffmpeg as an argv list (no shell), so no shell
    quoting is involved.
    """
    level1 = "".join("\\" + ch if ch in "\\':" else ch for ch in value)
    return "".join("\\" + ch if ch in "\\'[],;" else ch for ch in level1)


def _escape_concat_path(path: str) -> str:
    """Quote *path* for one ``file`` line of an ffmpeg concat-demuxer list.

    The concat demuxer reads ``file '<path>'``; inside single quotes every byte
    is literal except ``'`` itself, which is written as ``'\\''`` (close the
    quote, an escaped apostrophe, reopen) - the same rule as a POSIX shell.
    """
    return "'" + path.replace("'", "'\\''") + "'"


def _caption_font_size(height: int) -> int:
    return max(height // _CAPTION_FONT_SIZE_DIVISOR, 12)


def _wrap_caption(text: str, *, width: int, font_size: int) -> list[str]:
    """Word-wrap *text* into lines that fit the frame (drawtext never wraps).

    The line length is a fixed estimate from the font size, so wrapping is
    deterministic and does not depend on which font the ffmpeg build resolves.
    """
    max_chars = max(8, int(width * _CAPTION_WRAP_WIDTH / (font_size * _CAPTION_CHAR_WIDTH)))
    return textwrap.wrap(" ".join(text.split()), width=max_chars) or []


def _reveal_expr(delay_s: float) -> str:
    """0 -> 1 ramp that starts at *delay_s* and lasts _CAPTION_FADE_S (drawtext ``t``)."""
    return f"min(1,max(0,(t-{delay_s:.3f})/{_CAPTION_FADE_S:.3f}))"


def _caption_block_top(line_count: int, *, height: int, line_px: int) -> int:
    """Top y of a caption block: the 0.78 anchor, moved up to stay in the safe band."""
    top = round(height * _CAPTION_Y_FRACTION)
    bottom_limit = round(height * _CAPTION_SAFE_BOTTOM)
    if top + line_count * line_px > bottom_limit:
        top = bottom_limit - line_count * line_px
    return max(top, round(height * _CAPTION_SAFE_TOP))


def _drawtext_filter(
    textfile: Path,
    *,
    height: int,
    y_px: int | None = None,
    delay_s: float | None = None,
    fontfile: Path | None = None,
) -> str:
    """Build a centred, safe-area drawtext filter for one caption line.

    The caption is read from *textfile* (``textfile=``) instead of being inlined
    as ``text=``: the authored words then never pass through filtergraph
    escaping at all, and ``expansion=none`` stops drawtext from interpreting
    ``%{...}`` sequences, so apostrophes, colons, percent signs and backslashes
    render verbatim. Only the file paths and the animation expressions are
    escaped (see _escape_option_value).

    With ``delay_s`` the line fades in (``alpha``) and slides up into place
    (``y``) starting ``delay_s`` seconds into the card; without it the line is
    static (the pre-animation behaviour).
    """
    font_size = _caption_font_size(height)
    y_rest = round(height * _CAPTION_Y_FRACTION) if y_px is None else y_px
    parts = [
        f"drawtext=textfile={_escape_option_value(str(textfile))}",
        "expansion=none",
    ]
    if fontfile is not None:
        parts.append(f"fontfile={_escape_option_value(str(fontfile))}")
    parts += [
        "fontcolor=white",
        f"fontsize={font_size}",
        "box=1",
        "boxcolor=black@0.55",
        f"boxborderw={max(font_size // 6, 4)}",
        # x centres each line; y sits on its safe-area slot.
        "x=(w-text_w)/2",
    ]
    if delay_s is None:
        parts.append(f"y={y_rest}")
    else:
        ramp = _reveal_expr(delay_s)
        slide = max(round(height * _CAPTION_SLIDE_FRACTION), 1)
        parts.append(f"y={_escape_option_value(f'{y_rest}+{slide}*(1-{ramp})')}")
        parts.append(f"alpha={_escape_option_value(ramp)}")
    return ":".join(parts)


def _caption_filters(
    caption: str,
    index: int,
    work: Path,
    *,
    width: int,
    height: int,
    fontfile: Path | None,
) -> list[str]:
    """One animated drawtext per wrapped caption line (empty caption -> none)."""
    font_size = _caption_font_size(height)
    lines = _wrap_caption(caption, width=width, font_size=font_size)
    line_px = round(font_size * _CAPTION_LINE_SPACING)
    top = _caption_block_top(len(lines), height=height, line_px=line_px)
    filters: list[str] = []
    for i, line in enumerate(lines):
        textfile = work / f"caption_{index:03d}_{i:02d}.txt"
        textfile.write_text(line, encoding="utf-8")
        filters.append(
            _drawtext_filter(
                textfile,
                height=height,
                y_px=top + i * line_px,
                delay_s=_CAPTION_FIRST_DELAY_S + i * _CAPTION_STAGGER_S,
                fontfile=fontfile,
            )
        )
    return filters


def _progress_bar_filters(
    *, width: int, height: int, offset_s: float, total_s: float
) -> tuple[str, str, int]:
    """(track drawbox, overlay filter, bar height) for the whole-video progress bar.

    The bar is a white ``color`` strip overlaid at ``x = W*(offset+t)/total - w``:
    it fills left-to-right across the WHOLE video because each card passes its
    own start time (``offset_s``) and the video's total length.
    """
    bar_h = max(height // _PROGRESS_BAR_DIVISOR, 2)
    y = round(height * _PROGRESS_BAR_TOP_FRACTION)
    track = f"drawbox=x=0:y={y}:w=iw:h={bar_h}:color=white@0.25:t=fill"
    total = max(total_s, 0.001)
    x_expr = _escape_option_value(f"W*({offset_s:.3f}+t)/{total:.3f}-w")
    overlay = f"overlay=x={x_expr}:y={y}:eval=frame"
    return track, overlay, bar_h


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
    offset_s: float = 0.0,
    total_s: float | None = None,
    tail_s: float = 0.0,
    fontfile: Path | None = None,
) -> Path:
    """Render ONE animated card at the given resolution/fps (deterministic).

    Background: when ``background`` is given (a real produced image, e.g. an
    SDXL PNG) it is scaled-to-cover, centre-cropped and slowly zoomed (Ken
    Burns, ``zoompan``) - a true AI visual, not a placeholder (SPEC-GAP G27).
    Otherwise the card is a slowly rotating two-colour gradient (``gradients``).

    On top: the whole-video progress bar (positioned by ``offset_s`` /
    ``total_s``) and, when ``caption`` is non-empty, the authored text burned
    into the safe area line by line with a staggered fade/slide reveal.

    ``tail_s`` extends the card past its scene so the next scene's ``xfade``
    has frames to blend; the scene's own timing is unchanged.
    """
    c0, c1 = _GRADIENTS[index % len(_GRADIENTS)]
    out = work / f"scene_{index:03d}.mp4"
    length = seconds + max(tail_s, 0.0)
    frames = max(round(length * fps), 1)
    total = seconds if total_s is None else total_s
    if background is not None:
        cmd = [
            ffmpeg_bin(),
            "-y",
            *_QUIET,
            "-loop",
            "1",
            "-framerate",
            str(fps),
            "-t",
            f"{length:.3f}",
            "-i",
            str(background),
        ]
        bg_chain = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1,"
            f"zoompan=z=1+{_KEN_BURNS_ZOOM}*on/{frames}"
            ":x=iw/2-(iw/zoom/2):y=ih/2-(ih/zoom/2)"
            f":d=1:s={width}x{height}:fps={fps}"
        )
    else:
        cmd = [
            ffmpeg_bin(),
            "-y",
            *_QUIET,
            "-f",
            "lavfi",
            "-i",
            (
                f"gradients=s={width}x{height}:r={fps}:d={length:.3f}"
                f":c0={c0}:c1={c1}:x0=0:y0=0:x1={width}:y1={height}"
                f":speed={_GRADIENT_SPEED}:seed=0"
            ),
        ]
        bg_chain = "null"
    track, overlay, bar_h = _progress_bar_filters(
        width=width, height=height, offset_s=offset_s, total_s=total
    )
    cmd += [
        "-f",
        "lavfi",
        "-i",
        f"color=c=white:size={width}x{bar_h}:rate={fps}:duration={length:.3f}",
    ]
    graph = f"[0:v]{bg_chain},{track}[bg];[bg][1:v]{overlay}"
    if caption:
        for flt in _caption_filters(
            caption, index, work, width=width, height=height, fontfile=fontfile
        ):
            graph += f",{flt}"
    graph += ",format=yuv420p[v]"
    cmd += [
        "-filter_complex",
        graph,
        "-map",
        "[v]",
        "-frames:v",
        str(frames),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",  # mandatory: yuv444p shows black on phones
        str(out),
    ]
    proc = _run_ffmpeg(cmd, timeout=300, what=f"ffmpeg card render (scene {index})")
    if caption and proc.returncode != 0 and "No such filter: 'drawtext'" in (proc.stderr or ""):
        # This ffmpeg build has no libfreetype. Render the card without text
        # (KEEPING the background and motion) and record the skip so provenance
        # never claims text that is not on screen (ASUR-HONEST-01) instead of
        # failing the render.
        if skipped is not None:
            skipped.append(index)
        return _render_card(
            index,
            seconds,
            work,
            width=width,
            height=height,
            fps=fps,
            background=background,
            offset_s=offset_s,
            total_s=total_s,
            tail_s=tail_s,
        )
    if proc.returncode != 0 or not out.is_file():
        raise RenderError(_failure(f"ffmpeg card render failed (scene {index})", proc))
    return out


def _audio_args(first_index: int, voice: Path | None, music: Path | None) -> tuple[list[str], str, list[str]]:
    """(extra -i inputs, audio filtergraph or "", output args) for the mux.

    Audio has three honest states (never a fabricated track):
      * ``voice`` + ``music`` -> a true two-track mix. Voice sits at
        ``DEFAULT_VOICE_DB`` and music is ducked to ``DEFAULT_MUSIC_DB +
        DEFAULT_DUCK_DB`` so narration stays intelligible, then ``amix`` folds
        them (``asur.editing.audio_mix`` levels).
      * exactly one of them -> single-track mux, trimmed to video length.
      * neither -> silent.
    """
    if voice is not None and music is not None:
        ducked = DEFAULT_MUSIC_DB + DEFAULT_DUCK_DB
        a, m = first_index, first_index + 1
        graph = (
            f"[{a}:a]volume={DEFAULT_VOICE_DB}dB[va];"
            f"[{m}:a]volume={ducked}dB[ma];"
            "[va][ma]amix=inputs=2:duration=longest:dropout_transition=0[a]"
        )
        return (["-i", str(voice), "-i", str(music)], graph,
                ["-map", "[a]", "-c:a", "aac", "-shortest"])
    single = voice if voice is not None else music
    if single is not None:
        return (["-i", str(single)], "",
                ["-map", f"{first_index}:a", "-c:a", "aac", "-shortest"])
    return ([], "", [])


_VIDEO_OUT = ["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
              "-movflags", "+faststart"]


def _concat(
    cards: list[Path],
    out_path: Path,
    work: Path,
    *,
    audio_path: Path | None = None,
    music_path: Path | None = None,
) -> None:
    """Join per-scene cards with hard cuts via the concat demuxer, then mux audio.

    Abs paths need ``-safe 0``. The concat-demuxer re-encodes here (simple,
    robust across mismatched inputs); ``+faststart`` makes the file web-ready.
    See ``_audio_args`` for the audio states.
    """
    listing = work / "concat.txt"
    # concat demuxer wants: file '<abs path>' per line, quoted per its rules.
    listing.write_text(
        "".join(f"file {_escape_concat_path(str(c.resolve()))}\n" for c in cards),
        encoding="utf-8",
    )
    inputs, audio_graph, audio_out = _audio_args(1, audio_path, music_path)
    cmd = [ffmpeg_bin(), "-y", *_QUIET, "-f", "concat", "-safe", "0", "-i", str(listing), *inputs]
    if audio_graph:
        cmd += ["-filter_complex", audio_graph, "-map", "0:v"]
    elif audio_out:
        cmd += ["-map", "0:v"]
    cmd += [*_VIDEO_OUT, *audio_out, str(out_path)]
    proc = _run_ffmpeg(cmd, timeout=300, what="ffmpeg concat")
    if proc.returncode != 0 or not out_path.is_file():
        raise RenderError(_failure("ffmpeg concat failed", proc))


def _xfade_graph(durations: list[float], *, transition: str, transition_s: float) -> str:
    """Chain ``xfade`` over N card inputs; scene k+1 starts at its timeline start.

    Every card except the last carries a ``transition_s`` tail, so after joining
    cards 0..k the stream is ``sum(d[0..k]) + transition_s`` long and the next
    xfade's offset is exactly ``sum(d[0..k])``: the joined video keeps the
    timeline's total length and every scene keeps its start time.
    """
    parts: list[str] = []
    prev = "[0:v]"
    offset = 0.0
    for k in range(1, len(durations)):
        offset += durations[k - 1]
        label = "[v]" if k == len(durations) - 1 else f"[x{k}]"
        parts.append(
            f"{prev}[{k}:v]xfade=transition={transition}:duration={transition_s:.3f}"
            f":offset={offset:.3f}{label}"
        )
        prev = label
    return ";".join(parts)


def _trimmed_cut_join(
    cards: list[Path],
    durations: list[float],
    out_path: Path,
    *,
    audio_path: Path | None = None,
    music_path: Path | None = None,
) -> None:
    """Hard-cut join of xfade-ready cards, each trimmed back to its scene length.

    Cards rendered for ``xfade`` carry a transition tail; ``trim`` drops it so
    every scene keeps its timeline start and the total length is unchanged. The
    ``concat`` filter reads its inputs one after another.
    """
    cmd = [ffmpeg_bin(), "-y", *_QUIET]
    for card in cards:
        cmd += ["-i", str(card)]
    inputs, audio_graph, audio_out = _audio_args(len(cards), audio_path, music_path)
    cmd += inputs
    parts = [
        f"[{k}:v]trim=duration={dur:.3f},setpts=PTS-STARTPTS[c{k}]"
        for k, dur in enumerate(durations)
    ]
    labels = "".join(f"[c{k}]" for k in range(len(durations)))
    graph = ";".join(parts) + f";{labels}concat=n={len(durations)}:v=1:a=0[v]"
    if audio_graph:
        graph += ";" + audio_graph
    cmd += ["-filter_complex", graph, "-map", "[v]", *_VIDEO_OUT, *audio_out, str(out_path)]
    proc = _run_ffmpeg(cmd, timeout=600, what="ffmpeg hard-cut join")
    if proc.returncode != 0 or not out_path.is_file():
        raise RenderError(_failure("ffmpeg hard-cut join failed", proc))


def _xfade_join(
    cards: list[Path],
    durations: list[float],
    out_path: Path,
    *,
    audio_path: Path | None = None,
    music_path: Path | None = None,
    transition: str = _TRANSITION,
    transition_s: float = _TRANSITION_S,
) -> None:
    """Join cards with ``xfade`` transitions and mux audio in one ffmpeg pass."""
    cmd = [ffmpeg_bin(), "-y", *_QUIET]
    for card in cards:
        cmd += ["-i", str(card)]
    inputs, audio_graph, audio_out = _audio_args(len(cards), audio_path, music_path)
    cmd += inputs
    graph = _xfade_graph(durations, transition=transition, transition_s=transition_s)
    if audio_graph:
        graph += ";" + audio_graph
    cmd += ["-filter_complex", graph, "-map", "[v]", *_VIDEO_OUT, *audio_out, str(out_path)]
    proc = _run_ffmpeg(cmd, timeout=600, what="ffmpeg xfade join")
    if proc.returncode != 0 or not out_path.is_file():
        raise RenderError(_failure("ffmpeg xfade join failed", proc))


def render(
    timeline: Any,
    out_path: str,
    *,
    platform: str | None = None,
    audio_path: str | None = None,
    music_path: str | None = None,
    backgrounds: dict[str, str] | None = None,
    transition_s: float | None = None,
    **params: Any,
) -> dict[str, Any]:
    """Render a Timeline (dict or ``.to_dict()``-able) to a real MP4 file.

    Resolution and fps come from the chosen platform pack's ``FormatSpec``
    (SPEC-GAP G20): ``platform=None`` resolves to the Instagram-Reels default at
    1080x1920 (ASUR-VERSION-01), while ``youtube_long`` renders 16:9 1920x1080.
    An unknown platform id fails closed via ``get_platform`` (UnknownPlatform)
    before any work.

    ``transition_s`` overrides the xfade length between scenes (``0`` = hard
    cuts through the concat demuxer). It is clamped below the shortest scene.

    Returns a provenance+license block (ASUR-PROV-01) describing the output:
    model, license, media type, the output path, structural facts, and the
    motion design actually applied. Fails closed (``RenderError``) when the
    ffmpeg binary is absent and when the timeline declares an explicit empty
    scene list, so a stdlib-only machine without ffmpeg - or an edit plan with
    nothing to render - gets a clear message, never a silent pass
    (ASUR-GATE-01).
    """
    spec = get_platform(platform).format_spec
    width, height, fps = spec.width, spec.height, spec.fps

    if not _ffmpeg_available():
        raise RenderError(
            "FFmpeg adapter needs an ffmpeg binary on PATH or in ASUR_FFMPEG "
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
    fontfile = _font_file() if any(captions) else None

    trans = _TRANSITION_S if transition_s is None else max(float(transition_s), 0.0)
    if len(durations) < 2:
        trans = 0.0
    trans = min(trans, round(min(durations) / 2, 3))

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
    total_s = round(sum(durations), 3)

    with tempfile.TemporaryDirectory(prefix="asur_render_") as tmp:
        work = Path(tmp)
        cards: list[Path] = []
        offset = 0.0
        for i, dur in enumerate(durations):
            cards.append(
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
                    offset_s=offset,
                    total_s=total_s,
                    tail_s=trans if i < len(durations) - 1 else 0.0,
                    fontfile=fontfile,
                )
            )
            offset += dur
        xfade_fallback: str | None = None
        if trans > 0:
            try:
                _xfade_join(cards, durations, out, audio_path=voice, music_path=music,
                            transition_s=trans)
            except RenderError as exc:
                # One ffmpeg pass holding every scene open for the xfade chain
                # has died on some builds (CI, ffmpeg 8.0.1 amd64v3) with no
                # error message of its own. Keep the render: join the same
                # cards with hard cuts, trimmed to the timeline so timing is
                # unchanged, and record why in provenance (never a silent swap).
                xfade_fallback = str(exc)
                warnings.warn(
                    f"xfade transitions failed; rendered with hard cuts instead: {exc}",
                    RuntimeWarning,
                    stacklevel=2,
                )
                out.unlink(missing_ok=True)
                _trimmed_cut_join(cards, durations, out, audio_path=voice, music_path=music)
        else:
            _concat(cards, out, work, audio_path=voice, music_path=music)

    backgrounds_used = sum(1 for bg in scene_backgrounds if bg is not None)
    captions_burned_in = any(c for i, c in enumerate(captions) if i not in skipped)
    captions_skipped_reason = (
        "ffmpeg build lacks the drawtext filter (libfreetype); "
        f"{len(skipped)} caption card(s) rendered without text"
        if skipped
        else None
    )
    motion = {
        "background": (
            f"ken-burns zoom 1.00->{1 + _KEN_BURNS_ZOOM:.2f} on produced images; "
            f"rotating gradient (speed {_GRADIENT_SPEED}) elsewhere"
            if backgrounds_used
            else f"rotating two-colour gradient (ffmpeg gradients, speed {_GRADIENT_SPEED})"
        ),
        "progress_bar": True,
        "caption_reveal": (
            f"per-line fade+slide, {_CAPTION_FADE_S}s each, {_CAPTION_STAGGER_S}s stagger"
            if captions_burned_in
            else None
        ),
        "transition": (
            {"type": "cut", "fallback_from": _TRANSITION, "fallback_reason": xfade_fallback}
            if xfade_fallback is not None
            else {"type": _TRANSITION, "duration_s": trans} if trans > 0 else {"type": "cut"}
        ),
    }
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
            "caption_font": fontfile.name if fontfile is not None and captions_burned_in else None,
            "audio_present": audio_present,
            "audio_tracks": audio_tracks,
            "motion": motion,
            "note": (
                f"{backgrounds_used} scene(s) composited over real AI background "
                f"image(s); remaining scenes are deterministic animated-gradient "
                f"{spec.aspect_ratio} cards"
                if backgrounds_used
                else (
                    f"deterministic animated-gradient {spec.aspect_ratio} cards "
                    "(pure ffmpeg filters); no model, no network, no GPU"
                )
            ),
        },
        "license": {
            "name": LICENSE,
            "commercial_ok": True,
            "note": "FFmpeg is a tool; output of procedural gradient cards is unencumbered",
        },
    }


def thumbnail_timestamp(duration_s: float | None) -> float:
    """When to grab the thumbnail: the settled hook frame, inside short videos too."""
    if not duration_s or duration_s <= 0:
        return 0.0
    return round(min(HOOK_FRAME_S, duration_s / 2), 3)


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
            "FFmpeg adapter needs an ffmpeg binary on PATH or in ASUR_FFMPEG to grab "
            "a thumbnail (brew install ffmpeg / apt install ffmpeg)."
        )
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_bin(),
        "-y",
        *_QUIET,
        "-ss",
        f"{timestamp_s:.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        str(out),
    ]
    proc = _run_ffmpeg(cmd, timeout=120, what="ffmpeg thumbnail grab")
    if proc.returncode != 0 or not out.is_file():
        raise RenderError(_failure("ffmpeg thumbnail grab failed", proc))
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
            "note": "frame of a procedural gradient-card render; unencumbered",
        },
    }
