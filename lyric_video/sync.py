"""ASUR lyric-video Stage 2: the sync-test video (a QA check, not the real video).

WHAT THIS IS
  The plainest possible video that proves the Stage 0-1 timing is right: a black
  1080x1920 frame, the current lyric phrase centred, and the word being sung RIGHT NOW
  highlighted in red - driven entirely by the exact word timestamps. A small debug line
  at the bottom shows the song time, line number, word, and its start->end. No effects,
  no art direction: if the red word lands on the beat here, the timing is trustworthy
  and we can freeze it and move to the real creative stages.

WHY IT MATTERS (the process-guide rule)
  "Review a picture, not code." Before building anything beautiful, you watch this ugly
  video once and confirm the words land where they are sung. Only then do we freeze the
  timing (Stage 1 --freeze) and start the creative engine.

HOW (100% local, offline)
  ffmpeg on this machine has no freetype, so text is drawn by a bundled macOS CoreText
  one-shot (Swift) which also shapes Devanagari correctly. We render one PNG per word
  (its phrase, that word in red), hold each PNG for exactly the word's [start, end], mux
  the project's song.wav, and write sync-test.mp4.

FAIL CLOSED (ASUR-GATE-01)
  Runs only if BOTH phrases.json (from Stage 1 timing) and song.wav exist in the project.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

WIDTH = 1080
HEIGHT = 1920
FPS = 30

# CoreText one-shot: draw a phrase centred on a transparent canvas with ONE word in red.
# Args: text, highlightStart, highlightLen, debug, outPath, w, h. CoreText applies a
# per-range colour so only the sung word is red; it also shapes Devanagari aksharas
# correctly (no libraqm needed). Bundled as a string so the stage needs no extra files.
_SWIFT_SYNC = r'''
import AppKit
let a = CommandLine.arguments
guard a.count >= 8 else { exit(2) }
let text = a[1]
let hiStart = Int(a[2]) ?? 0
let hiLen = Int(a[3]) ?? 0
let debug = a[4]
let outPath = a[5]
let w = Int(a[6]) ?? 1080
let h = Int(a[7]) ?? 1920
let img = NSImage(size: NSSize(width: w, height: h))
img.lockFocus()
NSColor.clear.set(); NSBezierPath(rect: NSRect(x:0,y:0,width:w,height:h)).fill()
let style = NSMutableParagraphStyle(); style.alignment = .center; style.lineBreakMode = .byWordWrapping
let base: [NSAttributedString.Key: Any] = [
  .font: NSFont.boldSystemFont(ofSize: 92),
  .foregroundColor: NSColor.white,
  .paragraphStyle: style,
]
let phrase = NSMutableAttributedString(string: text, attributes: base)
let chars = (text as NSString).length
if hiLen > 0 && hiStart >= 0 && hiStart + hiLen <= chars {
  phrase.addAttribute(.foregroundColor, value: NSColor(calibratedRed: 0.90, green: 0.12, blue: 0.20, alpha: 1.0),
                      range: NSRange(location: hiStart, length: hiLen))
}
let inset: CGFloat = 90
// Phrase sits in the vertical middle third.
phrase.draw(in: NSRect(x: inset, y: CGFloat(h)*0.34, width: CGFloat(w)-2*inset, height: CGFloat(h)*0.4))
// Small grey debug line near the bottom.
let dstyle = NSMutableParagraphStyle(); dstyle.alignment = .center
let dattrs: [NSAttributedString.Key: Any] = [
  .font: NSFont.monospacedSystemFont(ofSize: 34, weight: .regular),
  .foregroundColor: NSColor(white: 0.55, alpha: 1.0),
  .paragraphStyle: dstyle,
]
NSAttributedString(string: debug, attributes: dattrs).draw(in: NSRect(x: 40, y: 120, width: CGFloat(w)-80, height: 80))
img.unlockFocus()
guard let tiff = img.tiffRepresentation, let rep = NSBitmapImageRep(data: tiff),
      let png = rep.representation(using: .png, properties: [:]) else { exit(3) }
try! png.write(to: URL(fileURLWithPath: outPath))
'''


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def _require(path: Path, what: str) -> None:
    """Fail closed (ASUR-GATE-01) if a required input is missing."""
    if not path.is_file():
        print(f"ERROR: missing {what}: {path}", file=sys.stderr)
        raise SystemExit(2)


def _char_range(phrase: str, word_index: int) -> tuple[int, int]:
    """Character offset+length of the word_index-th space-split token in `phrase`."""
    cursor = 0
    tokens = phrase.split(" ")
    for i, tok in enumerate(tokens):
        if i == word_index:
            return cursor, len(tok)
        cursor += len(tok) + 1  # token + the single space
    return 0, 0


def _blank_png(out_png: Path, swift_src: Path) -> Path:
    """An all-transparent frame for the silent gaps between sung words."""
    _run(["swift", str(swift_src), "", "0", "0", "", str(out_png), str(WIDTH), str(HEIGHT)])
    return out_png


def _word_png(
    phrase_text: str, word_index: int, debug: str, out_png: Path, swift_src: Path
) -> Path:
    start, length = _char_range(phrase_text, word_index)
    _run([
        "swift", str(swift_src), phrase_text, str(start), str(length), debug,
        str(out_png), str(WIDTH), str(HEIGHT),
    ])
    return out_png


def _segments(phrases: list[dict[str, Any]]) -> list[tuple[float, float, Path | None, str, int, str]]:
    """Flatten phrases into an ordered list of (start, end, pngspec) windows.

    Each sung word gets a window holding its highlighted phrase; the gaps between words
    get a blank window. Returned as (start, end, phrase_text_or_None, debug, word_index).
    """
    windows: list[tuple[float, float, str | None, str, int]] = []
    clock = 0.0
    for p in phrases:
        text = str(p.get("text", ""))
        line_no = p.get("line", 0)
        for wi, wobj in enumerate(p.get("words", [])):
            ws = float(wobj.get("start", clock))
            we = float(wobj.get("end", ws))
            if we <= ws:
                we = ws + 0.08  # keep every word visible for at least a few frames
            if ws > clock + 0.02:
                windows.append((clock, ws, None, "", -1))  # a gap (blank frame)
            word = str(wobj.get("word", ""))
            debug = f"t={ws:6.2f}  L{line_no:03d}  '{word}'  {ws:.2f}->{we:.2f}"
            windows.append((ws, we, text, debug, wi))
            clock = we
    return windows  # type: ignore[return-value]


def build_sync_test(project: str) -> int:
    """Stage 2: render project/sync-test.mp4 from phrases.json + song.wav. Returns exit code."""
    for tool in ("ffmpeg", "swift"):
        if shutil.which(tool) is None:
            print(f"ERROR: '{tool}' is not on PATH; cannot build the sync test.", file=sys.stderr)
            return 2

    project_dir = Path(project)
    phrases_path = project_dir / "phrases.json"
    song_path = project_dir / "song.wav"
    _require(phrases_path, "phrases.json (run Stage 1 timing first)")
    _require(song_path, "song.wav (run Stage -1 ingest first)")

    phrases = json.loads(phrases_path.read_text(encoding="utf-8"))
    if not phrases:
        print("ERROR: phrases.json is empty - nothing to sync.", file=sys.stderr)
        return 2

    work = project_dir / "_sync_work"
    work.mkdir(parents=True, exist_ok=True)
    swift_src = work / "synctext.swift"
    swift_src.write_text(_SWIFT_SYNC, encoding="utf-8")

    windows = _segments(phrases)

    # One PNG per window; hold it for its exact [start, end] via the concat demuxer.
    concat_lines: list[str] = []
    for idx, (ws, we, text, debug, wi) in enumerate(windows):
        png = work / f"f_{idx:05d}.png"
        if text is None:
            _blank_png(png, swift_src)
        else:
            _word_png(text, wi, debug, png, swift_src)
        dur = max(we - ws, 1.0 / FPS)
        concat_lines.append(f"file '{png.resolve()}'")
        concat_lines.append(f"duration {dur:.3f}")
    # Concat quirk: repeat the final frame without a duration so it isn't dropped.
    if windows:
        last_png = work / f"f_{len(windows) - 1:05d}.png"
        concat_lines.append(f"file '{last_png.resolve()}'")

    concat_txt = work / "frames.txt"
    concat_txt.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")

    # Burn the held PNGs over solid black, then mux the real song audio. No effects.
    overlay = work / "overlay.mp4"
    _run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=black:s={WIDTH}x{HEIGHT}:r={FPS}",
        "-f", "concat", "-safe", "0", "-i", str(concat_txt),
        "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto,format=yuv420p[v]",
        "-map", "[v]", "-r", str(FPS), "-shortest",
        "-c:v", "libx264", "-preset", "veryfast", str(overlay),
    ])

    out = project_dir / "sync-test.mp4"
    _run([
        "ffmpeg", "-y",
        "-i", str(overlay), "-i", str(song_path),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart", str(out),
    ])

    print(f"SYNC TEST written: {out}")
    print()
    print("GATE - watch it before freezing the timing:")
    print(f"  open \"{out.resolve()}\"")
    print("  Confirm the RED word lands on the word being sung, for the whole song.")
    print("  If it drifts, fix lyrics.txt or re-run Stage 1 timing; do NOT freeze yet.")
    print("  When it looks right, freeze Stage 1:")
    print(f"    python3 lyric_video/timing.py --project {project} --freeze")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lyric-video-sync",
        description="Stage 2: render the plain sync-test video to QA the word timing.",
    )
    parser.add_argument("--project", required=True, help="project dir with phrases.json + song.wav")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return build_sync_test(args.project)


if __name__ == "__main__":
    raise SystemExit(main())
