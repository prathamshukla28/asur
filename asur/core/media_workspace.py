"""The on-disk MEDIA store - ASUR-VERSION-01 and ASUR-HUMAN-01.

Where ``workspace.py`` owns JSON artifacts under ``.script/``, this module owns
the *rendered media* a human can browse and hand-upload. It is deliberately a
separate, visible tree so a creator can open a folder and see the finished work:

    <project_root>/
      youtube/
        <project_id>/
          render/       # rendered video files (vNNNN-<name>)
          package/      # ready-to-upload bundle (vNNNN-<name>)
          _work/        # scratch for intermediate render fragments

Rules (fail-closed, mirroring Workspace):
  - Only the three known subdirs (render, package, _work) are writable; any
    other subdir name is refused (no arbitrary path writes).
  - Writing is O_EXCL: it NEVER overwrites an existing file. A crash or a
    double-run cannot silently replace a rendered asset (ASUR-VERSION-01).
  - ``next_version`` assigns a monotonic ``vNNNN-<name>`` so re-renders append
    rather than clobber.

This module is pure standard library (ASUR-LOCAL-01 / §4 stdlib-only core). It
stores bytes only; JSON artifacts stay in the ``.script/`` Workspace.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["MediaWorkspace", "MediaWorkspaceError"]


class MediaWorkspaceError(RuntimeError):
    """Raised on fail-closed media-workspace conditions (overwrite, bad subdir)."""


class MediaWorkspace:
    """A browsable ``youtube/<project_id>/`` media store rooted at a project."""

    MEDIA_DIRNAME = "youtube"
    SUBDIRS = ("render", "package", "_work")

    def __init__(self, project_root: str | os.PathLike, project_id: str):
        self.project_root = Path(project_root)
        self.project_id = project_id
        self.base = self.project_root / self.MEDIA_DIRNAME / project_id

    # -- setup -----------------------------------------------------------
    def ensure(self) -> MediaWorkspace:
        """Create the media directory tree if absent. Idempotent."""
        for subdir in self.SUBDIRS:
            (self.base / subdir).mkdir(parents=True, exist_ok=True)
        return self

    # -- version queries -------------------------------------------------
    def next_version(self, subdir: str, name: str) -> str:
        """Next ``vNNNN-<name>`` filename for *subdir*; first is ``v0001-``."""
        self._check_subdir(subdir)
        target_dir = self.base / subdir
        if not target_dir.is_dir():
            return f"v0001-{name}"
        parsed = [
            self._parse_version(p.name, name)
            for p in target_dir.glob(f"v*-{name}")
        ]
        versions = [v for v in parsed if v is not None]
        nxt = (max(versions) + 1) if versions else 1
        return f"v{nxt:04d}-{name}"

    # -- write -----------------------------------------------------------
    def write_text(self, subdir: str, name: str, text: str) -> Path:
        """Create ``<base>/<subdir>/<name>`` with *text*; refuse to overwrite."""
        target = self._target(subdir, name)
        self._atomic_write_new_bytes(target, text.encode("utf-8"))
        return target

    def write_bytes(self, subdir: str, name: str, data: bytes) -> Path:
        """Create ``<base>/<subdir>/<name>`` with *data*; refuse to overwrite."""
        target = self._target(subdir, name)
        self._atomic_write_new_bytes(target, data)
        return target

    # -- internals -------------------------------------------------------
    def _target(self, subdir: str, name: str) -> Path:
        self._check_subdir(subdir)
        target_dir = self.base / subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / name

    def _check_subdir(self, subdir: str) -> None:
        if subdir not in self.SUBDIRS:
            raise MediaWorkspaceError(
                f"unknown media subdir: {subdir!r} (allowed: {', '.join(self.SUBDIRS)})"
            )

    @staticmethod
    def _parse_version(filename: str, name: str) -> int | None:
        # "v0003-final.mp4" with name="final.mp4" -> 3
        suffix = f"-{name}"
        if not filename.startswith("v") or not filename.endswith(suffix):
            return None
        head = filename[1:-len(suffix)]
        try:
            return int(head)
        except ValueError:
            return None

    @staticmethod
    def _atomic_write_new_bytes(target: Path, data: bytes) -> None:
        """Atomically create *target*, failing if it already exists (O_EXCL)."""
        try:
            fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError as exc:
            raise MediaWorkspaceError(
                f"refusing to overwrite existing media file: {target}"
            ) from exc
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
        except Exception:
            # Best-effort cleanup of a partial file.
            try:
                os.unlink(str(target))
            except OSError:  # pragma: no cover
                pass
            raise
