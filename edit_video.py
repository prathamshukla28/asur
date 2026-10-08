"""ASUR input-video editor: turn ONE real video into SEVERAL distinct 9:16 edits.

WHAT THIS IS
  A free/local editor for footage you already have. You give it a video file; it
  inspects the file (ffprobe), finds natural scene cuts, reframes to vertical 9:16,
  trims to a short-form length, optionally transcribes the real speech into timed
  captions, and produces several attractive, DIFFERENT edits of the same source:
    - "punchy"    : fast cuts, hard transitions, bold centred captions, high energy.
    - "cinematic" : longer holds, gentle Ken-Burns push, cross-dissolves, a calm
                    lower-third caption, letterbox breathing room.
    - "meme"      : top caption bar (big impact text), hard cuts, punchy grade.
    - "beatcut"   : cuts re-timed to the audio's loud moments, centred captions.
  Every output is a real openable 1080x1920 H.264 + AAC file, checked with ASUR's own
  verify_render harness.

AUTO-CAPTIONS (--captions auto)
  Reads the video's OWN speech with faster-whisper (local, offline model). First run
  downloads a small model (~0.5GB) once; after that it is fully local, no network. If
  faster-whisper is not installed, the editor degrades gracefully: it keeps the fixed
  headline captions and prints how to enable auto-captions. Install once with:
    pip install faster-whisper      (or  pip install -e '.[generation]'  from asur/)

WHAT THIS IS NOT
  It does NOT generate new pixels. It edits the footage you give it (cut, reframe,
  re-time, caption, grade, transition). Regenerating or inventing video is the paid
  frontier-model tier, turned on later via a swappable adapter. This uses only the
  FFmpeg binary + the macOS CoreText caption helper (bundled Swift one-shot) + the
  optional local faster-whisper model for speech-to-caption.

REQUIREMENTS (already present on this Mac): ffmpeg, ffprobe, swift.
OPTIONAL: faster-whisper (only for --captions auto).

RUN (from the asur/ directory):
  PYTHONPATH="$(pwd)" python3 edit_video.py --input /path/to/clip.mp4
  PYTHONPATH="$(pwd)" python3 edit_video.py --input clip.mp4 --styles punchy,meme,beatcut
  PYTHONPATH="$(pwd)" python3 edit_video.py --input clip.mp4 --captions auto
  # no file handy? make a throwaway test clip and edit it:
  PYTHONPATH="$(pwd)" python3 edit_video.py --make-sample
Outputs: ./edit_out/variant_<style>.mp4 for each requested style.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from asur.generation.hero_proof import verify_render

WIDTH = 1080
HEIGHT = 1920
FPS = 30

# Target short-form length. We keep at most this many seconds of the best material.
TARGET_SECONDS = 24.0

# Scene-change sensitivity for ffmpeg's `select='gt(scene,THRESH)'`. Lower = more cuts.
SCENE_THRESHOLD = 0.30

# The styles this editor can produce. Order here is the default production order.
ALL_STYLES = ("punchy", "cinematic", "meme", "beatcut")

# Caption band. This machine's FFmpeg has no freetype/drawtext, so captions are drawn by
# the macOS CoreText engine into transparent PNGs and burned on with overlay.
CAP_W = WIDTH
CAP_H = 560

_SWIFT_TEXTPNG = r'''
import AppKit
let a = CommandLine.arguments
guard a.count >= 6 else { exit(2) }
let text = a[1]; let outPath = a[2]
let w = Int(a[3]) ?? 1080; let h = Int(a[4]) ?? 560
let pt = CGFloat(Double(a[5]) ?? 72)
let img = NSImage(size: NSSize(width: w, height: h))
img.lockFocus()
NSColor.clear.set(); NSBezierPath(rect: NSRect(x:0,y:0,width:w,height:h)).fill()
let style = NSMutableParagraphStyle(); style.alignment = .center; style.lineBreakMode = .byWordWrapping
let shadow = NSShadow(); shadow.shadowColor = NSColor.black.withAlphaComponent(0.9)
shadow.shadowBlurRadius = 12; shadow.shadowOffset = NSSize(width: 0, height: -3)
let attrs: [NSAttributedString.Key: Any] = [
  .font: NSFont.boldSystemFont(ofSize: pt),
  .foregroundColor: NSColor.white,
  .paragraphStyle: style,
  .strokeColor: NSColor.black, .strokeWidth: -4.5,
  .shadow: shadow,
]
let s = NSAttributedString(string: text, attributes: attrs)
let inset: CGFloat = 60
s.draw(in: NSRect(x: inset, y: inset, width: CGFloat(w)-2*inset, height: CGFloat(h)-2*inset))
img.unlockFocus()
guard let tiff = img.tiffRepresentation, let rep = NSBitmapImageRep(data: tiff),
      let png = rep.representation(using: .png, properties: [:]) else { exit(3) }
try! png.write(to: URL(fileURLWithPath: outPath))
'''


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def _run_soft(cmd: list[str]) -> subprocess.CompletedProcess:
    # ffmpeg analysis passes write their report to stderr and may exit non-zero on EOF;
    # callers parse stderr themselves, so do not raise here.
    return subprocess.run(cmd, check=False, capture_output=True, text=True)


def probe(path: Path) -> dict:
    """Inspect the source video -> an input_report-shaped record (ASUR stage-0 idea)."""
    result = _run([
        "ffprobe", "-v", "error",
        "-show_streams", "-show_format", "-of", "json", str(path),
    ])
    data = json.loads(result.stdout)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    has_audio = any(s.get("codec_type") == "audio" for s in data.get("streams", []))
    fps_raw = video.get("avg_frame_rate", "0/1")
    try:
        num, den = fps_raw.split("/")
        fps = float(num) / float(den) if float(den) else 0.0
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    duration = float(data.get("format", {}).get("duration", 0.0) or 0.0)
    return {
        "path": str(path),
        "duration_s": round(duration, 3),
        "width": int(video.get("width", 0) or 0),
        "height": int(video.get("height", 0) or 0),
        "fps": round(fps, 2),
        "video_codec": video.get("codec_name", "unknown"),
        "has_audio": has_audio,
    }


def detect_cuts(path: Path, duration: float) -> list[float]:
    """Find scene-change timestamps; fall back to even slices if none are found."""
    result = _run_soft([
        "ffmpeg", "-i", str(path),
        "-vf", f"select='gt(scene,{SCENE_THRESHOLD})',showinfo",
        "-f", "null", "-",
    ])
    cuts: list[float] = []
    for line in result.stderr.splitlines():
        if "pts_time:" in line and "showinfo" in line:
            try:
                piece = line.split("pts_time:")[1].split()[0]
                cuts.append(round(float(piece), 3))
            except (IndexError, ValueError):
                continue
    cuts = sorted(t for t in cuts if 0.5 < t < duration - 0.3)
    if len(cuts) < 2:
        # No usable scene changes (e.g. one continuous shot): slice evenly instead.
        step = max(duration / 6.0, 2.0)
        cuts = [round(step * i, 3) for i in range(1, int(duration / step) + 1)]
    return cuts


def detect_beats(path: Path, duration: float) -> list[float]:
    """Find loud-moment timestamps from the audio (energy peaks) to cut on.

    Uses ffmpeg's silencedetect inverted: the ends of quiet stretches are where sound
    kicks back in -> natural beats to cut on. Falls back to a steady ~1.6s pulse if the
    clip has no usable audio dynamics.
    """
    result = _run_soft([
        "ffmpeg", "-i", str(path),
        "-af", "silencedetect=noise=-30dB:d=0.3",
        "-f", "null", "-",
    ])
    beats: list[float] = []
    for line in result.stderr.splitlines():
        if "silence_end:" in line:
            try:
                piece = line.split("silence_end:")[1].split()[0]
                beats.append(round(float(piece), 3))
            except (IndexError, ValueError):
                continue
    beats = sorted(t for t in beats if 0.4 < t < duration - 0.3)
    if len(beats) < 2:
        # No dynamics (music bed / flat tone): use a steady pulse so cuts still feel rhythmic.
        step = 1.6
        beats = [round(step * i, 3) for i in range(1, int(duration / step) + 1)]
    return beats


def pick_segments(duration: float, cuts: list[float], max_total: float,
                  max_shot: float = 6.0) -> list[tuple[float, float]]:
    """Turn cut points into (start, length) segments, keeping up to max_total seconds."""
    marks = [0.0] + cuts + [duration]
    raw: list[tuple[float, float]] = []
    for i in range(len(marks) - 1):
        start = marks[i]
        length = marks[i + 1] - start
        if length >= 0.6:  # drop micro-fragments
            raw.append((round(start, 3), round(length, 3)))
    segments: list[tuple[float, float]] = []
    total = 0.0
    for start, length in raw:
        take = min(length, max_shot)  # never hold a single shot too long
        if total + take > max_total:
            take = max_total - total
        if take < 0.5:
            break
        segments.append((start, round(take, 3)))
        total += take
        if total >= max_total:
            break
    return segments or [(0.0, min(duration, max_total))]


# --- auto-captions from the video's own speech (optional, local faster-whisper) --------

def transcribe(path: Path) -> list[dict] | None:
    """Transcribe the source speech into timed phrases, or None if unavailable.

    Returns a list of {start, end, text}. Degrades gracefully: if faster-whisper is not
    installed, returns None (the caller keeps the fixed headline captions and prints how
    to enable this). The model runs fully local/offline after a one-time download.
    """
    try:
        from faster_whisper import WhisperModel  # lazy: only needed for --captions auto
    except ImportError:
        return None
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, _info = model.transcribe(str(path), vad_filter=True)
    phrases: list[dict] = []
    for seg in segments:
        text = (seg.text or "").strip()
        if text:
            phrases.append({"start": round(float(seg.start), 3),
                            "end": round(float(seg.end), 3),
                            "text": text})
    return phrases


def _caption_png(text: str, out_png: Path, swift_src: Path, pt: int) -> Path:
    spoken = text.strip() or "."
    _run(["swift", str(swift_src), spoken, str(out_png), str(CAP_W), str(CAP_H), str(pt)])
    return out_png


def _phrases_in_window(phrases: list[dict], start: float, length: float) -> list[dict]:
    """Phrases (shifted to clip-local time) that overlap this [start, start+length) window."""
    out: list[dict] = []
    end = start + length
    for p in phrases:
        if p["end"] <= start or p["start"] >= end:
            continue
        local_start = max(0.0, p["start"] - start)
        local_end = min(length, p["end"] - start)
        if local_end - local_start >= 0.15:
            out.append({"start": round(local_start, 3),
                        "end": round(local_end, 3),
                        "text": p["text"]})
    return out


def _reframe_filter(style: str) -> str:
    """Build the per-segment video filter: crop/scale to 9:16, then style it."""
    cover = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={WIDTH}:{HEIGHT},setsar=1,fps={FPS}"
    )
    if style in ("punchy", "meme", "beatcut"):
        # Snappy look: a touch more contrast and saturation, cuts carry the energy.
        return cover + ",eq=contrast=1.08:saturation=1.18:brightness=0.02"
    # cinematic: slow push in + mild filmic grade. zoompan drives the Ken-Burns move.
    return (
        cover
        + ",zoompan=z='min(zoom+0.0004,1.10)':d=1:"
        + f"s={WIDTH}x{HEIGHT}:fps={FPS}"
        + ",eq=contrast=1.03:saturation=1.05"
    )


def _caption_y(style: str) -> int:
    """Vertical position of the caption band for each style."""
    if style == "meme":
        return 180                       # top bar impact text
    if style == "cinematic":
        return 1180                      # calm lower third
    return (HEIGHT - CAP_H) // 2         # punchy / beatcut: centred


def _overlay_exprs(style: str, timed: list[dict] | None) -> str:
    """Return the filter_complex overlay chain for a segment's caption(s).

    If `timed` is given (auto-captions), each phrase PNG is overlaid only during its
    own [start,end] window via overlay enable=. Otherwise a single static caption PNG
    is overlaid for the whole segment.
    """
    cap_y = _caption_y(style)
    fade = "" if style in ("punchy", "meme", "beatcut") else ",format=rgba,fade=t=in:st=0:d=0.35:alpha=1"
    if not timed:
        # one static caption (input index 1)
        return (
            f"[0:v]{{VF}}[bg];[1:v]null{fade}[cap];"
            f"[bg][cap]overlay=(W-w)/2:{cap_y}:format=auto[v]"
        )
    # timed captions: inputs 1..N, each enabled only during its window, chained.
    parts = ["[0:v]{VF}[v0]"]
    prev = "[v0]"
    for i, ph in enumerate(timed):
        idx = i + 1
        vout = f"[v{idx}]"
        parts.append(
            f"{prev}[{idx}:v]overlay=(W-w)/2:{cap_y}:format=auto:"
            f"enable='between(t,{ph['start']:.3f},{ph['end']:.3f})'{vout}"
        )
        prev = vout
    # rename final to [v]
    parts[-1] = parts[-1].replace(prev, "[v]")
    return ";".join(parts)


def _cut_segment(
    src: Path, start: float, length: float, style: str, index: int,
    caption_pngs: list[Path], timed: list[dict] | None, work: Path, mute: bool,
) -> Path:
    """Render one reframed, captioned segment from the source."""
    out = work / f"{style}_seg_{index:02d}.mp4"
    vf = _reframe_filter(style)
    cmd = ["ffmpeg", "-y", "-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", str(src)]
    for png in caption_pngs:
        cmd += ["-i", str(png)]
    if caption_pngs:
        fc = _overlay_exprs(style, timed).replace("{VF}", vf)
        cmd += ["-filter_complex", fc, "-map", "[v]"]
    else:
        cmd += ["-vf", vf, "-map", "0:v"]
    if mute:
        cmd += ["-an"]
    else:
        cmd += ["-map", "0:a?", "-c:a", "aac", "-b:a", "128k"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), "-t", f"{length:.3f}", str(out)]
    _run(cmd)
    return out


def _concat_hard(segments: list[Path], out: Path, work: Path) -> None:
    listing = work / f"concat_{out.stem}.txt"
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in segments), encoding="utf-8")
    _run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out),
    ])


def _concat_xfade(segments: list[Path], durations: list[float], out: Path, work: Path) -> None:
    if len(segments) == 1:
        shutil.copyfile(segments[0], out)
        return
    xf = 0.4
    inputs: list[str] = []
    for seg in segments:
        inputs += ["-i", str(seg)]
    vparts: list[str] = []
    prev_v = "[0:v]"
    running = durations[0]
    for i in range(1, len(segments)):
        offset = running - xf
        vout = f"[v{i}]"
        vparts.append(
            f"{prev_v}[{i}:v]xfade=transition=fade:duration={xf}:offset={offset:.3f}{vout}"
        )
        prev_v = vout
        running = running + durations[i] - xf
    _run([
        "ffmpeg", "-y", *inputs,
        "-filter_complex", ";".join(vparts),
        "-map", prev_v,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-movflags", "+faststart", str(out),
    ])


def build_variant(
    src: Path, style: str, headline: str, phrases: list[dict] | None,
    cuts: list[float], beats: list[float], duration: float,
    swift_src: Path, work: Path, has_audio: bool,
) -> Path:
    """Render one styled edit of the source, picking segments + captions for that style."""
    # beatcut re-times its cuts to the audio; others use scene cuts. Shot length varies
    # per style so each edit genuinely feels different.
    if style == "beatcut":
        segments = pick_segments(duration, beats, TARGET_SECONDS, max_shot=2.4)
    elif style == "punchy":
        segments = pick_segments(duration, cuts, TARGET_SECONDS, max_shot=3.2)
    elif style == "meme":
        segments = pick_segments(duration, cuts, TARGET_SECONDS, max_shot=4.0)
    else:  # cinematic
        segments = pick_segments(duration, cuts, TARGET_SECONDS, max_shot=6.0)

    cap_pt = 72 if style == "cinematic" else 96
    static_png = _caption_png(headline, work / f"{style}_cap.png", swift_src, cap_pt)

    cut_paths: list[Path] = []
    cut_lens: list[float] = []
    for i, (start, length) in enumerate(segments):
        if phrases:
            # auto-captions: one PNG per spoken phrase in this window, timed to its moment.
            window = _phrases_in_window(phrases, start, length)
            if window:
                pngs = [
                    _caption_png(ph["text"], work / f"{style}_ac_{i:02d}_{j:02d}.png", swift_src, cap_pt)
                    for j, ph in enumerate(window)
                ]
                seg = _cut_segment(src, start, length, style, i, pngs, window, work, mute=not has_audio)
            else:
                # no speech here: show the headline so the frame is never bare.
                seg = _cut_segment(src, start, length, style, i, [static_png], None, work, mute=not has_audio)
        else:
            seg = _cut_segment(src, start, length, style, i, [static_png], None, work, mute=not has_audio)
        cut_paths.append(seg)
        cut_lens.append(length)

    out = work.parent / f"variant_{style}.mp4"
    if style == "cinematic":
        _concat_xfade(cut_paths, cut_lens, out, work)   # cross-dissolves = calm
    else:
        _concat_hard(cut_paths, out, work)              # hard cuts = energy
    return out


def make_sample(out: Path) -> Path:
    """Create a throwaway 16:9 test clip (colour bars + tone) so the editor can run
    end-to-end even when no footage is supplied."""
    out.parent.mkdir(parents=True, exist_ok=True)
    _run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=20",
        "-f", "lavfi", "-i", "sine=frequency=220:duration=20",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-shortest", str(out),
    ])
    return out


def edit(src: Path, out_dir: Path, styles: list[str],
         headline_a: str, headline_b: str, captions_mode: str) -> list[Path]:
    for tool in ("ffmpeg", "ffprobe", "swift"):
        if shutil.which(tool) is None:
            raise SystemExit(f"missing required tool on PATH: {tool}")
    if not src.is_file():
        raise SystemExit(f"input video not found: {src}")

    out_dir.mkdir(parents=True, exist_ok=True)
    work = out_dir / "_work"
    work.mkdir(exist_ok=True)
    swift_src = work / "textpng.swift"
    swift_src.write_text(_SWIFT_TEXTPNG, encoding="utf-8")

    info = probe(src)
    print("INSPECT (ffprobe)")
    print(f"  file      : {info['path']}")
    print(f"  duration  : {info['duration_s']}s")
    print(f"  size      : {info['width']}x{info['height']}  @ {info['fps']}fps")
    print(f"  codec     : {info['video_codec']}   audio: {'yes' if info['has_audio'] else 'no'}")
    if info["duration_s"] < 2.0:
        raise SystemExit("input is too short to edit (need at least ~2s).")

    cuts = detect_cuts(src, info["duration_s"])
    beats = detect_beats(src, info["duration_s"]) if info["has_audio"] else []
    print(f"CUTS      : {len(cuts)} scene change(s)" + (f", {len(beats)} audio beat(s)" if beats else ""))

    phrases: list[dict] | None = None
    if captions_mode == "auto":
        if not info["has_audio"]:
            print("CAPTIONS  : auto requested but the clip has no audio -> using headline captions.")
        else:
            print("CAPTIONS  : transcribing the clip's own speech (faster-whisper, local)...")
            phrases = transcribe(src)
            if phrases is None:
                print("CAPTIONS  : faster-whisper not installed -> using headline captions.")
                print("            enable with:  pip install faster-whisper")
            else:
                print(f"CAPTIONS  : transcribed {len(phrases)} spoken phrase(s) from the video.")

    outputs: list[Path] = []
    for i, style in enumerate(styles):
        headline = headline_a if i == 0 else headline_b
        print(f"RENDER    : variant '{style}' ...")
        out = build_variant(
            src, style, headline, phrases, cuts, beats, info["duration_s"],
            swift_src, work, info["has_audio"],
        )
        outputs.append(out)
    return outputs


def _parse_styles(raw: str) -> list[str]:
    styles = [s.strip().lower() for s in raw.split(",") if s.strip()]
    bad = [s for s in styles if s not in ALL_STYLES]
    if bad:
        raise SystemExit(f"unknown style(s): {', '.join(bad)}. choose from: {', '.join(ALL_STYLES)}")
    return styles or ["punchy", "cinematic"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="edit_video")
    parser.add_argument("--input", help="path to the source video to edit")
    parser.add_argument("--out", default="edit_out")
    parser.add_argument("--styles", default="punchy,cinematic",
                        help=f"comma-separated subset of: {', '.join(ALL_STYLES)}")
    parser.add_argument("--captions", choices=("headline", "auto"), default="headline",
                        help="'headline' = fixed text; 'auto' = transcribe the clip's speech")
    parser.add_argument("--caption-a", default="Watch this till the end")
    parser.add_argument("--caption-b", default="The part most people miss")
    parser.add_argument("--make-sample", action="store_true",
                        help="generate a throwaway test clip and edit that")
    args = parser.parse_args(argv)

    styles = _parse_styles(args.styles)
    out_dir = Path(args.out)
    if args.make_sample:
        src = make_sample(out_dir / "_work" / "sample_source.mp4")
        print(f"made sample source: {src}")
    elif args.input:
        src = Path(args.input)
    else:
        parser.error("give --input <video> or --make-sample")

    outputs = edit(src, out_dir, styles, args.caption_a, args.caption_b, args.captions)

    print("\nverifying each edit with ASUR's own harness (hero_proof.verify_render)...")
    for out in outputs:
        report = verify_render(out)
        dims = next((c for c in report["checks"] if c["check"] == "dimensions"), None)
        dim_txt = f"{dims['result']}" if dims else "n/a"
        print(f"  {out.name:<26} dimensions:{dim_txt}  status:{report['status']}")

    print(f"\nDONE. {len(outputs)} edit(s) of your video:")
    for out in outputs:
        print(f"  {out.resolve()}")
    print(f"Open them with:  open '{outputs[0].parent.resolve()}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
