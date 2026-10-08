"""ASUR Path-B demo renderer: turn a real ASUR SCRIPT artifact into an openable 9:16 .mp4.

WHAT THIS IS
  A demonstration renderer. It takes the script ASUR actually produces
  (idea -> research -> audience -> strategy -> hooks -> script) and makes a real,
  openable 1080x1920 vertical video with a natural voice-over (macOS `say`, a
  premium voice), gentle Ken-Burns motion, gradient backgrounds, animated
  lower-third captions, and cross-dissolve transitions. It then runs ASUR's own
  verify_render harness on the output to prove the file is structurally what the
  pipeline expects.

WHAT THIS IS NOT
  This is NOT the real AI generation stack (Wan 2.2 video / SDXL images /
  Kokoro voice / Stable Audio music). Those live behind `asur[generation]` + local
  GPU models and are left as human-run adapters by design (ADR-0004, Path A).
  This demo uses only the FFmpeg binary and the built-in macOS `say` voice:
  gradient motion cards + spoken words + captions. Real pixels, real voice, real
  captions, passes ASUR's verifier - but intentionally model-free. It is the FREE
  tier; swapping in a paid frontier generator later is an adapter change, not a
  rewrite.

REQUIREMENTS (all already present on this Mac): ffmpeg, ffprobe, say, swift.

RUN (from the asur/ directory):
  PYTHONPATH="$(pwd)" python3 render_demo.py --idea "why most people waste money on AI tools"
Output: ./render_out/asur_reel.mp4
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import wave
from pathlib import Path

from asur.core.identity import get_identity
from asur.generation.hero_proof import verify_render
from asur.script.audience import build_audience
from asur.script.hooks import build_hooks
from asur.script.idea import build_idea
from asur.script.research import build_research
from asur.script.script_builder import SECTION_ORDER, build_script
from asur.script.strategy import build_strategy

WIDTH = 1080
HEIGHT = 1920
FPS = 30

# A premium built-in macOS voice. "Samantha" is a natural US voice and kills the
# robotic default. A slightly slower rate reads more deliberately on short-form.
VOICE = "Samantha"
VOICE_RATE = 180

# Cross-dissolve length between sections, and the per-section fade padding.
XFADE = 0.45

# This machine's FFmpeg has no freetype, so there is no drawtext filter. We draw
# captions with the macOS built-in CoreText engine (a tiny bundled Swift one-shot)
# into transparent PNGs, then burn them on with FFmpeg's `overlay` filter. No extra
# installs, real system font, real on-screen text.
CAP_W = WIDTH
CAP_H = 620            # caption band height (fits ~4 wrapped lines)
# Caption sits in the lower third so the moving background reads as the subject and
# the text as a subtitle, not a title card.
CAP_Y = 1120

# Per-section background gradient pairs (top -> bottom). A calm, cinematic palette -
# not the "flat over-saturated AI" look the ideas-3 brief warns against. Each entry
# is (top_hex, bottom_hex) in 0xRRGGBB.
GRADIENTS = [
    ("0x1a2740", "0x0a0e16"),
    ("0x2a1838", "0x0d0a14"),
    ("0x10303a", "0x070f12"),
    ("0x3a2318", "0x120a06"),
    ("0x18303a", "0x080f12"),
    ("0x2a2340", "0x0c0a16"),
    ("0x3a1828", "0x12060c"),
    ("0x18283a", "0x080e14"),
    ("0x203a30", "0x0a120e"),
]

# CoreText caption renderer: text -> transparent PNG. Bundled as a string so the
# demo needs no extra files. Large white bold text with a black outline plus a soft
# shadow for contrast against any background.
_SWIFT_TEXTPNG = r'''
import AppKit
let a = CommandLine.arguments
guard a.count >= 5 else { exit(2) }
let text = a[1]; let outPath = a[2]; let w = Int(a[3]) ?? 1080; let h = Int(a[4]) ?? 620
let img = NSImage(size: NSSize(width: w, height: h))
img.lockFocus()
NSColor.clear.set(); NSBezierPath(rect: NSRect(x:0,y:0,width:w,height:h)).fill()
let style = NSMutableParagraphStyle(); style.alignment = .center; style.lineBreakMode = .byWordWrapping
let shadow = NSShadow(); shadow.shadowColor = NSColor.black.withAlphaComponent(0.85)
shadow.shadowBlurRadius = 10; shadow.shadowOffset = NSSize(width: 0, height: -3)
let attrs: [NSAttributedString.Key: Any] = [
  .font: NSFont.boldSystemFont(ofSize: 70),
  .foregroundColor: NSColor.white,
  .paragraphStyle: style,
  .strokeColor: NSColor.black, .strokeWidth: -4.5,
  .shadow: shadow,
]
let s = NSAttributedString(string: text, attributes: attrs)
let inset: CGFloat = 70
s.draw(in: NSRect(x: inset, y: inset, width: CGFloat(w)-2*inset, height: CGFloat(h)-2*inset))
img.unlockFocus()
guard let tiff = img.tiffRepresentation, let rep = NSBitmapImageRep(data: tiff),
      let png = rep.representation(using: .png, properties: [:]) else { exit(3) }
try! png.write(to: URL(fileURLWithPath: outPath))
'''


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def _aiff_duration(path: Path) -> float:
    """Read the real duration of the converted wav so audio and captions stay in sync."""
    with wave.open(str(path), "rb") as handle:
        frames = handle.getnframes()
        rate = handle.getframerate()
        return frames / float(rate) if rate else 0.0


def _say_to_wav(text: str, out_wav: Path, work: Path) -> float:
    """Speak `text` with a premium macOS voice, return the clip's real seconds."""
    raw = work / (out_wav.stem + ".aiff")
    spoken = text.strip() or "."
    _run(["say", "-v", VOICE, "-r", str(VOICE_RATE), "-o", str(raw), spoken])
    # Normalise to a plain 44.1k mono wav so every segment concatenates cleanly.
    _run([
        "ffmpeg", "-y", "-i", str(raw),
        "-ar", "44100", "-ac", "1", str(out_wav),
    ])
    return _aiff_duration(out_wav)


def _caption_png(text: str, out_png: Path, swift_src: Path) -> Path:
    spoken = text.strip() or "."
    _run(["swift", str(swift_src), spoken, str(out_png), str(CAP_W), str(CAP_H)])
    return out_png


def _render_segment(
    index: int, caption_png: Path, audio: Path, seconds: float, work: Path
) -> Path:
    """One section -> a moving gradient background with the caption fading in, plus voice.

    The background is a two-tone vertical gradient rendered large, then slowly zoomed
    (Ken-Burns) so the frame is never static. The caption PNG fades in over 0.4s and
    sits in the lower third.
    """
    top, bottom = GRADIENTS[index % len(GRADIENTS)]
    out = work / f"seg_{index:02d}.mp4"
    frames = max(round(seconds * FPS), 1)
    # gradients draws the base; zoompan does a slow 1.0 -> ~1.12 push for life.
    # The caption is overlaid at a fixed lower-third y, fading in at the start.
    filtergraph = (
        f"[0:v]zoompan=z='min(zoom+0.0006,1.12)':d={frames}:"
        f"s={WIDTH}x{HEIGHT}:fps={FPS}[bg];"
        f"[1:v]fade=t=in:st=0:d=0.4:alpha=1[cap];"
        f"[bg][cap]overlay=(W-w)/2:{CAP_Y}:format=auto[v]"
    )
    _run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i",
        (
            f"gradients=s={WIDTH}x{HEIGHT}:c0={top}:c1={bottom}:x0=0:y0=0:"
            f"x1=0:y1={HEIGHT}:d={seconds:.3f}:r={FPS}"
        ),
        "-i", str(caption_png),
        "-i", str(audio),
        "-filter_complex", filtergraph,
        "-map", "[v]", "-map", "2:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "128k",
        "-t", f"{seconds:.3f}",
        str(out),
    ])
    return out


def _xfade_join(segments: list[Path], durations: list[float], out: Path, work: Path) -> None:
    """Stitch segments with cross-dissolve video transitions and audio cross-fades.

    xfade needs each transition's offset = (sum of prior durations) - (n * XFADE).
    We fold the segments left to right, carrying a running composite.
    """
    if len(segments) == 1:
        shutil.copyfile(segments[0], out)
        return

    inputs: list[str] = []
    for seg in segments:
        inputs += ["-i", str(seg)]

    vparts: list[str] = []
    aparts: list[str] = []
    prev_v = "[0:v]"
    prev_a = "[0:a]"
    running = durations[0]
    for i in range(1, len(segments)):
        offset = running - XFADE
        vout = f"[v{i}]"
        aout = f"[a{i}]"
        vparts.append(
            f"{prev_v}[{i}:v]xfade=transition=fade:duration={XFADE}:"
            f"offset={offset:.3f}{vout}"
        )
        aparts.append(f"{prev_a}[{i}:a]acrossfade=d={XFADE}{aout}")
        prev_v, prev_a = vout, aout
        running = running + durations[i] - XFADE

    filtergraph = ";".join(vparts + aparts)
    _run([
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filtergraph,
        "-map", prev_v, "-map", prev_a,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(out),
    ])


def build_the_script(idea_line: str):
    """Run the real ASUR SCRIPT chain and return the script artifact."""
    ident = get_identity()
    pid = "render-demo"
    idea = build_idea(idea_line, pid, identity=ident)
    research = build_research(idea, pid, identity=ident)
    audience = build_audience(idea, research, pid, identity=ident)
    strategy = build_strategy(idea, audience, pid, identity=ident)
    hooks = build_hooks(strategy, pid, identity=ident)
    script = build_script(strategy, hooks, pid, identity=ident)
    return script


def render(idea_line: str, out_dir: Path) -> Path:
    for tool in ("ffmpeg", "ffprobe", "say", "swift"):
        if shutil.which(tool) is None:
            raise SystemExit(f"missing required tool on PATH: {tool}")

    out_dir.mkdir(parents=True, exist_ok=True)
    work = out_dir / "_work"
    work.mkdir(exist_ok=True)

    # Caption text is drawn by the macOS CoreText engine (bundled Swift one-shot)
    # because this machine's FFmpeg has no freetype/drawtext. Written once, reused.
    swift_src = work / "textpng.swift"
    swift_src.write_text(_SWIFT_TEXTPNG, encoding="utf-8")

    script = build_the_script(idea_line)
    sections = script.body["sections"]

    print(f"idea      : {idea_line}")
    print(f"script id : {script.artifact_id}")
    print(f"sections  : {len(sections)}")
    print(f"voice     : {VOICE} (natural)")
    print("rendering each section (voice + moving gradient + caption)...")

    segments: list[Path] = []
    durations: list[float] = []
    for i, name in enumerate(SECTION_ORDER):
        sec = sections[name]
        spoken = sec.get("spoken_words", "") or name
        caption = sec.get("onscreen_text", "") or spoken
        wav = work / f"voice_{i:02d}.wav"
        seconds = _say_to_wav(spoken, wav, work)
        # Give each line a little breathing room so it does not feel rushed.
        seconds = max(seconds + 0.4, 2.0)
        cap_png = _caption_png(caption, work / f"cap_{i:02d}.png", swift_src)
        seg = _render_segment(i, cap_png, wav, seconds, work)
        segments.append(seg)
        durations.append(seconds)
        print(f"  [{i + 1}/9] {name:<8} {seconds:4.1f}s  - {caption[:48]}")

    final = out_dir / "asur_reel.mp4"
    print("stitching final 9:16 reel (cross-dissolve transitions)...")
    _xfade_join(segments, durations, final, work)
    return final


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="render_demo")
    parser.add_argument("--idea", default="why most people waste money on AI tools")
    parser.add_argument("--out", default="render_out")
    args = parser.parse_args(argv)

    final = render(args.idea, Path(args.out))

    print("\nverifying the file with ASUR's own harness (hero_proof.verify_render)...")
    report = verify_render(final)
    print(f"  status : {report['status']}")
    for check in report["checks"]:
        print(f"    - {check['check']:<20} {check['result']:<8} {check['reason']}")

    print(f"\nDONE. Your video is at: {final.resolve()}")
    print(f"Open it with:  open '{final.resolve()}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
