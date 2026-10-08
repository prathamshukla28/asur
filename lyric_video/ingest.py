"""ASUR lyric-video Stage -1: ingest a song from a YouTube URL (audio + DRAFT lyrics).

WHAT THIS IS
  The front door of the lyric-video pipeline. You give it a YouTube URL; it pulls the
  AUDIO (yt-dlp -> song.wav), then runs faster-whisper to produce a DRAFT transcript as
  lyrics_draft.txt. That draft is a STARTING POINT, not the truth. You read it, fix every
  wrong word (fast rap, slang, Hinglish and ad-libs are frequently mis-heard), and save
  the corrected words as lyrics.txt. Only then is the song project ready for timing.

TWO HONEST GATES (nothing proceeds past them)
  1. RIGHTS GATE. Downloading someone's song can break YouTube's terms and the artist's
     copyright. This tool refuses to download until you pass --i-have-rights, confirming
     you own the song or have permission (a portfolio/fan edit still needs the artist's
     OK before anything public). It always credits the artist in the project notes.
  2. LYRICS GATE. Whisper's draft is NOT accepted as final. The real rule (from the
     process guide) is: the lyrics YOU write are the source of truth for the WORDS; the
     audio is the source of truth for the TIMING. So ingest stops and asks you to turn
     lyrics_draft.txt into a corrected lyrics.txt before Stage 1 (timing) can run.

WHAT THIS IS NOT
  It does not create the video, and it does not pretend Whisper's transcript is accurate.
  It gets the audio onto disk and gives you a draft to correct. 100% local after the one
  download: yt-dlp fetches the audio; faster-whisper runs offline (small model cached on
  first use).

REQUIREMENTS: yt-dlp, ffmpeg (both present). OPTIONAL: faster-whisper (for the draft).

RUN (from the asur/ directory):
  PYTHONPATH="$(pwd)" python3 lyric_video/ingest.py --url "<youtube url>" --i-have-rights
  PYTHONPATH="$(pwd)" python3 lyric_video/ingest.py --url "<url>" --name my-song --i-have-rights
Output: lyric_video/project/<name>/song.wav + lyrics_draft.txt + ingest-report.json
Next:   correct lyrics_draft.txt -> save as lyric_video/project/<name>/lyrics.txt
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path("lyric_video") / "project"

# The one honest refusal: never download copyrighted audio without an explicit
# human confirmation of rights. This is the rights gate (ASUR-HUMAN-01 + the guide's
# credit-and-get-permission rule); without the flag the tool exits and does nothing.
RIGHTS_NOTICE = (
    "RIGHTS CHECK\n"
    "  Downloading a song from YouTube can break YouTube's Terms of Service and the\n"
    "  artist's copyright. Only continue if you OWN the song or have the artist's\n"
    "  permission. Even a portfolio / fan edit needs the artist's OK before you post it,\n"
    "  and the artist must be credited. ASUR will not download without your confirmation.\n"
    "  Re-run with  --i-have-rights  to confirm you have the right to use this audio."
)


def _tool_available(name: str) -> bool:
    return shutil.which(name) is not None


def _slugify(text: str) -> str:
    """Turn a title into a safe folder name (lowercase, dashes, no surprises)."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "song"


def _fetch_title(url: str) -> str:
    """Ask yt-dlp for the video title WITHOUT downloading (used to name the project)."""
    try:
        out = subprocess.run(
            ["yt-dlp", "--no-warnings", "--print", "title", url],
            check=True,
            capture_output=True,
            text=True,
        )
        return out.stdout.strip().splitlines()[0] if out.stdout.strip() else "song"
    except (subprocess.CalledProcessError, OSError):
        return "song"


def _download_audio(url: str, project_dir: Path) -> Path:
    """yt-dlp -> best audio -> song.wav (ffmpeg extracts/normalises to a plain WAV)."""
    template = str(project_dir / "song.%(ext)s")
    subprocess.run(
        [
            "yt-dlp",
            "--no-warnings",
            "-f",
            "bestaudio/best",
            "-x",
            "--audio-format",
            "wav",
            "-o",
            template,
            url,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    song = project_dir / "song.wav"
    if not song.is_file():
        raise RuntimeError("yt-dlp finished but song.wav was not produced")
    return song


def _draft_lyrics(song: Path, out_path: Path) -> tuple[bool, str]:
    """faster-whisper DRAFT transcript. Returns (ok, note). Never raises on absence.

    This is a DRAFT only. Whisper mis-hears fast/slang/Hinglish rap; the user must
    correct it into lyrics.txt. We keep one spoken line per whisper segment.
    """
    try:
        from faster_whisper import WhisperModel  # lazy: optional offline model
    except ImportError:
        out_path.write_text(
            "# faster-whisper is not installed, so no draft transcript was made.\n"
            "# Install it once:  pip install faster-whisper\n"
            "# Then write the real lyrics here (one line per lyric line) and save as\n"
            "# lyrics.txt in this folder.\n",
            encoding="utf-8",
        )
        return False, "faster-whisper not installed; wrote an empty draft to fill in"

    model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, _info = model.transcribe(str(song), vad_filter=True)
    lines = [seg.text.strip() for seg in segments if seg.text.strip()]
    header = (
        "# DRAFT transcript from Whisper - NOT the final lyrics.\n"
        "# Fast rap, slang, Hinglish and ad-libs are often wrong here.\n"
        "# Fix every line to the REAL words, keep one lyric line per line, then save\n"
        "# this file as  lyrics.txt  in the same folder. lyrics.txt is the source of\n"
        "# truth for the words; the audio is the source of truth for the timing.\n\n"
    )
    out_path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    return True, f"wrote a {len(lines)}-line Whisper draft to correct"


def ingest(url: str, *, name: str | None, have_rights: bool) -> int:
    """Run Stage -1. Returns a shell exit code (0 ok, 2 refused/error)."""
    if not have_rights:
        print(RIGHTS_NOTICE)
        return 2
    for tool in ("yt-dlp", "ffmpeg"):
        if not _tool_available(tool):
            print(f"error: required tool '{tool}' is not on PATH")
            return 2

    title = _fetch_title(url)
    project_name = _slugify(name or title)
    project_dir = PROJECT_ROOT / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    print(f"project: {project_name}")
    print(f"folder:  {project_dir}")
    print(f"source:  {title}")

    print("downloading audio (yt-dlp)...")
    try:
        song = _download_audio(url, project_dir)
    except (subprocess.CalledProcessError, RuntimeError, OSError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        print(f"error: audio download failed: {str(detail).strip()[:400]}")
        return 2
    print(f"  saved {song} ({song.stat().st_size // 1024} KB)")

    draft_path = project_dir / "lyrics_draft.txt"
    print("transcribing a DRAFT of the lyrics (faster-whisper, offline)...")
    drafted, note = _draft_lyrics(song, draft_path)
    print(f"  {note}")
    print(f"  draft: {draft_path}")

    report = {
        "stage": "ingest",
        "project": project_name,
        "source_title": title,
        "source_url": url,
        "song_file": str(song),
        "song_bytes": song.stat().st_size,
        "lyrics_draft_file": str(draft_path),
        "lyrics_draft_from_whisper": drafted,
        "rights_confirmed_by_user": True,
        "credit": f"Song belongs to its artist ({title}). Credit the artist; "
        "get permission before any public or commercial use.",
        "next_step": "Correct lyrics_draft.txt into lyrics.txt (one lyric line per "
        "line), then run Stage 1 timing.",
    }
    report_path = project_dir / "ingest-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print()
    print("STAGE -1 DONE (ingest).")
    print("NEXT (the lyrics gate): open")
    print(f"  {draft_path}")
    print("fix every wrong word to the REAL lyrics, then save it as")
    print(f"  {project_dir / 'lyrics.txt'}")
    print("The words you write are the truth; the audio stays the truth for timing.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lyric_video/ingest.py",
        description="Stage -1: pull a song's audio from a YouTube URL + a DRAFT transcript.",
    )
    parser.add_argument("--url", required=True, help="YouTube video or song URL")
    parser.add_argument("--name", default=None, help="project folder name (default: slug of title)")
    parser.add_argument(
        "--i-have-rights",
        dest="have_rights",
        action="store_true",
        help="confirm you own the song or have permission to use it (required to download)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return ingest(args.url, name=args.name, have_rights=args.have_rights)


if __name__ == "__main__":
    sys.exit(main())
