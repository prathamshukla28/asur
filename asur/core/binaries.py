"""Locate the ``ffmpeg`` / ``ffprobe`` binaries (stdlib only, no import of media libs).

Every subprocess call ASUR makes to FFmpeg resolves its binary here, so one
place decides which build runs. By default that is whatever ``ffmpeg`` /
``ffprobe`` is first on ``PATH``. Two environment variables override it:

  ``ASUR_FFMPEG``   path to (or command name of) the ffmpeg binary to use
  ``ASUR_FFPROBE``  path to (or command name of) the ffprobe binary to use

They are independent: a static ffmpeg build that carries ``drawtext`` (e.g. the
one ``pip install imageio-ffmpeg`` ships) can render while the system ffprobe
keeps probing. An override that does not point at an executable resolves to
``None`` - callers then fail closed with their usual "binary missing" error. It
never silently falls back to the ``PATH`` binary, because the user asked for a
specific build (a fallback could quietly render without captions again).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

__all__ = [
    "ENV_FFMPEG",
    "ENV_FFPROBE",
    "ffmpeg_bin",
    "ffmpeg_path",
    "ffprobe_bin",
    "ffprobe_path",
]

ENV_FFMPEG = "ASUR_FFMPEG"
ENV_FFPROBE = "ASUR_FFPROBE"


def _resolve(default_name: str, env_var: str) -> str | None:
    override = os.environ.get(env_var, "").strip()
    if not override:
        return shutil.which(default_name)
    candidate = Path(override).expanduser()
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    # A bare command name (no path separator) is looked up on PATH.
    if os.sep not in override and (found := shutil.which(override)):
        return found
    return None


def ffmpeg_path() -> str | None:
    """Absolute path of the ffmpeg binary to use, or None if unavailable."""
    return _resolve("ffmpeg", ENV_FFMPEG)


def ffprobe_path() -> str | None:
    """Absolute path of the ffprobe binary to use, or None if unavailable."""
    return _resolve("ffprobe", ENV_FFPROBE)


def ffmpeg_bin() -> str:
    """argv[0] for an ffmpeg call: the resolved path, else the bare name.

    The bare-name fallback only matters when the binary is missing; the call
    then fails with the usual OS error, which callers already turn into a
    fail-closed message.
    """
    return ffmpeg_path() or "ffmpeg"


def ffprobe_bin() -> str:
    """argv[0] for an ffprobe call: the resolved path, else the bare name."""
    return ffprobe_path() or "ffprobe"
