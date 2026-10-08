"""ASUR lyric-video Stage 0-1: word-level timing (the DATA half of the pipeline).

WHAT THIS IS
  Takes a frozen song project (song.wav + your corrected lyrics.txt) and works out
  WHEN every word is sung, to the fraction of a second. It isolates the vocal from the
  beat, then forced-aligns YOUR words against that vocal, and writes three files the
  video stages read later:
    word-timestamps.json  - every word with {word, start, end, score}
    phrases.json          - the same words grouped back into your lyric lines
    confidence-report.txt  - which lines aligned cleanly vs which to eyeball

THE ONE RULE (from the process guide)
  lyrics.txt is the source of truth for the WORDS. The audio is the source of truth for
  the TIMING. We NEVER transcribe-and-replace: alignment only decides WHEN your words
  land, never WHAT the words are. If a word aligns poorly it is flagged, not rewritten.

HOW (100% local, offline)
  1. Demucs (htdemucs) splits song.wav into stems; we keep the isolated vocal so the
     aligner hears the voice, not the drums.
  2. The vocal is resampled to 16 kHz mono (what the aligner wants).
  3. uroman romanizes each lyric line so one multilingual aligner handles Hindi /
     English / Hinglish / Marathi in a single pass.
  4. torchaudio's MMS_FA forced aligner places each romanized token on the timeline.
  5. Those timings are mapped back onto your ORIGINAL words and grouped by line.

FAIL CLOSED (ASUR-GATE-01)
  Runs only if BOTH song.wav and a corrected lyrics.txt exist in the project. The
  Whisper draft (lyrics_draft.txt) is never used here - you must confirm lyrics.txt
  first (the lyrics gate from Stage -1).

FREEZE (ASUR-VERSION-01)
  After you review the confidence report, pass --freeze to record sha256 checksums of
  the three outputs + lyrics.txt into frozen.json. Later stages read those files and
  must never change them.

REQUIREMENTS (all already installed): torch, torchaudio, demucs, uroman, soundfile.

RUN (from the asur/ directory):
  PYTHONPATH="$(pwd)" python3 lyric_video/timing.py --project lyric_video/project/<name>
  PYTHONPATH="$(pwd)" python3 lyric_video/timing.py --project <dir> --freeze
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SAMPLE_RATE = 16000  # what MMS_FA expects
# Alignment scores are log-probabilities; below this a word is worth a human glance.
# Chosen conservatively so the report over-flags rather than hides a bad spot.
_LOW_SCORE = 0.40


def _require(path: Path, what: str) -> None:
    """Fail closed with a plain message if a needed input is missing."""
    if not path.is_file():
        raise SystemExit(f"missing {what}: {path}  (cannot continue)")


def _read_lyrics(path: Path) -> list[list[str]]:
    """Read lyrics.txt into lines of words, skipping blanks and [section] markers."""
    lines: list[list[str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        text = raw.strip()
        if not text or text.startswith("#") or (text.startswith("[") and text.endswith("]")):
            continue
        words = text.split()
        if words:
            lines.append(words)
    return lines


def _isolate_vocal(song: Path, work: Path) -> Path:
    """Demucs htdemucs -> keep the vocal stem, resampled to 16 kHz mono."""
    import torch  # pragma: no cover - heavy dep, lazy
    import torchaudio  # pragma: no cover
    from demucs.apply import apply_model  # pragma: no cover
    from demucs.pretrained import get_model  # pragma: no cover

    wav, sr = torchaudio.load(str(song))
    if wav.shape[0] == 1:  # demucs wants stereo
        wav = wav.repeat(2, 1)
    model = get_model("htdemucs")
    model.eval()
    with torch.no_grad():
        stems = apply_model(model, wav[None], split=True, overlap=0.1)[0]
    vocal = stems[model.sources.index("vocals")]  # (channels, samples)
    vocal = vocal.mean(dim=0, keepdim=True)  # to mono
    if sr != SAMPLE_RATE:
        vocal = torchaudio.functional.resample(vocal, sr, SAMPLE_RATE)
    out = work / "vocals16k.wav"
    torchaudio.save(str(out), vocal, SAMPLE_RATE)
    return out


def _romanize(lines: list[list[str]]) -> list[list[str]]:
    """uroman each word -> lowercase ascii tokens the multilingual aligner can read."""
    import uroman as _uroman  # pragma: no cover - lazy

    roman = _uroman.Uroman()
    out: list[list[str]] = []
    for line in lines:
        romline: list[str] = []
        for word in line:
            tok = re.sub(r"[^a-z']", "", roman.romanize_string(word).lower())
            romline.append(tok or "*")  # empty -> wildcard so counts stay aligned
        out.append(romline)
    return out


def _align(vocal: Path, roman_lines: list[list[str]]) -> list[tuple[float, float, float]]:
    """MMS_FA forced alignment -> one (start, end, score) per romanized word, in order."""
    import torch  # pragma: no cover
    import torchaudio  # pragma: no cover

    bundle = torchaudio.pipelines.MMS_FA
    model = bundle.get_model()
    tokenizer = bundle.get_tokenizer()
    aligner = bundle.get_aligner()

    waveform, sr = torchaudio.load(str(vocal))
    if sr != bundle.sample_rate:
        waveform = torchaudio.functional.resample(waveform, sr, bundle.sample_rate)

    flat = [w for line in roman_lines for w in line]
    with torch.inference_mode():
        emission, _ = model(waveform)
        token_spans = aligner(emission[0], tokenizer(flat))

    ratio = waveform.size(1) / emission.size(1) / bundle.sample_rate
    out: list[tuple[float, float, float]] = []
    for spans in token_spans:  # one list of token-spans per word
        start = round(spans[0].start * ratio, 3)
        end = round(spans[-1].end * ratio, 3)
        score = round(sum(s.score * len(s) for s in spans) / sum(len(s) for s in spans), 3)
        out.append((start, end, score))
    return out


def _grade(score: float) -> str:
    return "low" if score < _LOW_SCORE else ("med" if score < 0.70 else "high")


def _build_outputs(
    lines: list[list[str]], timings: list[tuple[float, float, float]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Map alignment timings back onto the ORIGINAL words; group into phrases; grade."""
    words: list[dict[str, Any]] = []
    phrases: list[dict[str, Any]] = []
    report: list[str] = []
    cursor = 0
    for li, line in enumerate(lines):
        line_words: list[dict[str, Any]] = []
        lows = 0
        for word in line:
            start, end, score = timings[cursor] if cursor < len(timings) else (0.0, 0.0, 0.0)
            entry = {"word": word, "start": start, "end": end, "score": score}
            words.append(entry)
            line_words.append(entry)
            if score < _LOW_SCORE:
                lows += 1
            cursor += 1
        if line_words:
            p_start = line_words[0]["start"]
            p_end = line_words[-1]["end"]
            line_score = round(sum(w["score"] for w in line_words) / len(line_words), 3)
            phrases.append(
                {
                    "line": li,
                    "text": " ".join(line),
                    "start": p_start,
                    "end": p_end,
                    "words": line_words,
                    "confidence": _grade(line_score),
                }
            )
            flag = "  <-- review" if lows else ""
            report.append(
                f"L{li:03d} [{_grade(line_score)}] {p_start:6.2f}-{p_end:6.2f}s  "
                f"{lows}/{len(line_words)} low  | {' '.join(line)}{flag}"
            )
    return words, phrases, report


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def time_project(project: Path, *, freeze: bool = False) -> int:
    song = project / "song.wav"
    lyrics = project / "lyrics.txt"
    _require(song, "song.wav")
    _require(lyrics, "corrected lyrics.txt (fix lyrics_draft.txt and save as lyrics.txt)")

    work = project / "_work"
    work.mkdir(parents=True, exist_ok=True)

    lines = _read_lyrics(lyrics)
    if not lines:
        raise SystemExit(f"lyrics.txt has no words: {lyrics}")
    print(f"timing: {sum(len(l) for l in lines)} words across {len(lines)} lines")

    print("timing: isolating vocal (Demucs htdemucs)...")
    vocal = _isolate_vocal(song, work)
    print("timing: forced-aligning your words to the vocal (MMS_FA)...")
    timings = _align(vocal, _romanize(lines))

    words, phrases, report = _build_outputs(lines, timings)

    (project / "word-timestamps.json").write_text(
        json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (project / "phrases.json").write_text(
        json.dumps(phrases, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    low_lines = sum(1 for p in phrases if p["confidence"] == "low")
    header = (
        f"CONFIDENCE REPORT  ({len(words)} words, {len(phrases)} lines, "
        f"{low_lines} low-confidence lines)\n"
        "Review the lines marked '<-- review'. These are spots to eyeball in the\n"
        "sync-test video (Stage 2). The WORDS are yours and correct; only the TIMING\n"
        "on flagged lines may need a nudge.\n"
        + ("-" * 72) + "\n"
    )
    (project / "confidence-report.txt").write_text(
        header + "\n".join(report) + "\n", encoding="utf-8"
    )

    print(
        f"timing: wrote word-timestamps.json + phrases.json + confidence-report.txt "
        f"({low_lines} lines flagged)"
    )

    if freeze:
        names = ["lyrics.txt", "word-timestamps.json", "phrases.json"]
        frozen = {n: _sha256(project / n) for n in names}
        (project / "frozen.json").write_text(
            json.dumps({"stage": "timing", "checksums": frozen}, indent=2), encoding="utf-8"
        )
        print("timing: FROZEN (frozen.json). Later stages read these files, never change them.")
    else:
        print(
            "GATE: open confidence-report.txt and watch the Stage 2 sync-test before "
            "trusting the timing. When it looks right, re-run with --freeze."
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ASUR lyric-video Stage 0-1: word timing.")
    parser.add_argument("--project", required=True, help="project dir with song.wav + lyrics.txt")
    parser.add_argument(
        "--freeze",
        action="store_true",
        help="record sha256 checksums of the outputs after you have reviewed them",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return time_project(Path(args.project), freeze=args.freeze)


if __name__ == "__main__":
    sys.exit(main())
