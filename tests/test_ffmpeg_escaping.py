"""FFmpeg filtergraph / concat-list escaping (adapter correctness).

Unit tests pin the escaping rules; the real-binary tests prove them against the
actual ffmpeg parsers (skipped when ffmpeg is not on PATH).
"""

from __future__ import annotations

import re
import shutil
import subprocess

import pytest

from asur.generation.adapters import ffmpeg

HAS_FFMPEG = shutil.which("ffmpeg") is not None
needs_ffmpeg = pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg binary not on PATH")

NASTY = "it's 100%: a\\b, [x]; done"


def _has_filter(name: str) -> bool:
    if not HAS_FFMPEG:
        return False
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True, check=False
    ).stdout
    return re.search(rf"^\s*\S+\s+{re.escape(name)}\s", out, re.MULTILINE) is not None


# -- unit: the escaping rules ------------------------------------------------


def test_option_value_escapes_both_filtergraph_levels():
    # level 1 escapes \ ' : ; level 2 escapes \ ' [ ] , ; again.
    assert ffmpeg._escape_option_value("a:b") == "a\\\\:b"
    assert ffmpeg._escape_option_value("it's") == "it\\\\\\'s"
    assert ffmpeg._escape_option_value("a,b") == "a\\,b"
    assert ffmpeg._escape_option_value("[x];") == "\\[x\\]\\;"
    assert ffmpeg._escape_option_value("c:\\d") == "c\\\\:\\\\\\\\d"
    # percent is not special to the filtergraph parser (drawtext expansion is
    # disabled separately with expansion=none).
    assert ffmpeg._escape_option_value("100%") == "100%"


def test_concat_path_quoting_handles_apostrophes():
    assert ffmpeg._escape_concat_path("/tmp/a b/c.mp4") == "'/tmp/a b/c.mp4'"
    assert ffmpeg._escape_concat_path("/tmp/it's/c.mp4") == "'/tmp/it'\\''s/c.mp4'"


def test_drawtext_reads_caption_from_textfile_with_expansion_off(tmp_path):
    textfile = tmp_path / "cap.txt"
    textfile.write_text(NASTY, encoding="utf-8")
    flt = ffmpeg._drawtext_filter(textfile, height=1920)
    assert flt.startswith("drawtext=textfile=")
    assert ":expansion=none" in flt
    # the authored words never pass through filtergraph escaping
    assert "100%" not in flt and "done" not in flt


# -- real binary: the parsers agree with the rules -----------------------------


@needs_ffmpeg
def test_escaped_path_round_trips_through_real_filtergraph_parser(tmp_path):
    weird_dir = tmp_path / "we'ird, [dir]; 100%"
    weird_dir.mkdir()
    clip = weird_dir / "a:b's,c\\d.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
         "testsrc=s=64x64:d=0.3", str(clip)],
        check=True, capture_output=True,
    )
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-f", "lavfi", "-i",
         f"movie={ffmpeg._escape_option_value(str(clip))}", "-f", "null", "-"],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr[-400:]


@needs_ffmpeg
def test_concat_handles_card_paths_containing_apostrophes(tmp_path):
    work = tmp_path / "creator's work"
    work.mkdir()
    cards = []
    for i in range(2):
        card = work / f"it's card {i}.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
             "color=c=red:s=64x64:r=30:d=0.5", "-pix_fmt", "yuv420p", str(card)],
            check=True, capture_output=True,
        )
        cards.append(card)
    out = tmp_path / "joined.mp4"
    ffmpeg._concat(cards, out, work)
    assert out.is_file() and out.stat().st_size > 0


@pytest.mark.skipif(not _has_filter("drawtext"), reason="ffmpeg build lacks drawtext")
def test_real_drawtext_renders_nasty_caption(tmp_path):
    card = ffmpeg._render_card(
        0, 1.0, tmp_path, width=180, height=320, fps=30, caption=NASTY, skipped=[]
    )
    assert card.is_file()
