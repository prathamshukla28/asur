"""The on-disk artifact store - ASUR-VERSION-01 and ASUR-HUMAN-01.

A workspace is a plain directory (no git submodules, no remotes, no network).
For Phase 1 the SCRIPT instrument uses the ``.script/`` workspace rooted at a
project directory:

    <project_root>/
      .script/
        artifacts/
          <kind>/
            v0001-<artifact_id>.json
            v0002-<artifact_id>.json
            ...
        index.json              # latest version per kind (fast lookup)

Rules (all fail-closed where it matters):
  - Versions are monotonic per (project, kind). save_artifact() assigns the
    next version automatically; it NEVER overwrites an existing version file.
  - Writing is atomic (write to a temp file, then os.replace), and refuses to
    clobber an existing path (O_EXCL-style), so a crash or a double-run cannot
    silently corrupt or replace a sealed artifact.
  - Superseding is explicit: save a new version and the previous latest is
    marked status="superseded" in a freshly written file (the old file is
    left untouched as history).

This module owns *persistence and version assignment*; envelope.py owns the
*shape and checksum* of an artifact.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .canonical import canonicalize, parse_json
from .envelope import KINDS, Artifact, verify_checksum

__all__ = ["Workspace", "WorkspaceError"]


class WorkspaceError(RuntimeError):
    """Raised on fail-closed workspace conditions (overwrite, corruption)."""


class Workspace:
    """A ``.script/`` artifact store rooted at a project directory."""

    WORKSPACE_DIRNAME = ".script"

    def __init__(self, project_root: str | os.PathLike, project_id: str):
        self.project_root = Path(project_root)
        self.project_id = project_id
        self.root = self.project_root / self.WORKSPACE_DIRNAME
        self.artifacts_dir = self.root / "artifacts"
        self.index_path = self.root / "index.json"

    # -- setup -----------------------------------------------------------
    def ensure(self) -> Workspace:
        """Create the workspace directory tree if absent. Idempotent."""
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self._atomic_write_text(self.index_path, canonicalize({}))
        return self

    # -- version queries -------------------------------------------------
    def latest_version(self, kind: str) -> int:
        """Highest version number stored for *kind*, or 0 if none."""
        self._check_kind(kind)
        kind_dir = self.artifacts_dir / kind
        if not kind_dir.is_dir():
            return 0
        parsed = [
            self._parse_version(p.name)
            for p in kind_dir.glob("v*.json")
        ]
        versions = [v for v in parsed if v is not None]
        return max(versions) if versions else 0

    def next_version(self, kind: str) -> int:
        return self.latest_version(kind) + 1

    # -- write -----------------------------------------------------------
    def save_artifact(self, artifact: Artifact) -> Path:
        """Persist *artifact*, assigning the next version for its kind.

        Fail-closed: refuses to write if the target version file already
        exists, and refuses if the artifact's checksum does not match its
        body (corruption guard).
        """
        self._check_kind(artifact.kind)
        if not verify_checksum(artifact):
            raise WorkspaceError(
                f"checksum mismatch for {artifact.artifact_id}: refusing to save"
            )

        kind_dir = self.artifacts_dir / artifact.kind
        kind_dir.mkdir(parents=True, exist_ok=True)

        version = self.next_version(artifact.kind)
        artifact.version = version
        filename = f"v{version:04d}-{artifact.artifact_id}.json"
        target = kind_dir / filename

        if target.exists():  # pragma: no cover - defensive
            raise WorkspaceError(f"refusing to overwrite existing artifact: {target}")

        self._atomic_write_new(target, canonicalize(artifact.as_dict()))
        self._update_index(artifact.kind, version, artifact.artifact_id)
        return target

    def supersede(self, old_kind: str) -> None:
        """Mark the current latest artifact of *old_kind* as superseded.

        Writes a NEW version file whose status is "superseded"; the original
        file is left intact as history. Used when a stage is re-run.
        """
        latest = self.load_latest(old_kind)
        if latest is None:
            return
        latest.status = "superseded"
        # Re-stamp as a new version so history is append-only.
        self.save_artifact(latest)

    # -- read ------------------------------------------------------------
    def load_latest(self, kind: str) -> Artifact | None:
        """Return the highest-version artifact for *kind*, or None."""
        self._check_kind(kind)
        version = self.latest_version(kind)
        if version == 0:
            return None
        return self._load_version(kind, version)

    def load_artifact(self, kind: str, version: int) -> Artifact | None:
        self._check_kind(kind)
        return self._load_version(kind, version)

    # -- internals -------------------------------------------------------
    def _load_version(self, kind: str, version: int) -> Artifact | None:
        kind_dir = self.artifacts_dir / kind
        matches = list(kind_dir.glob(f"v{version:04d}-*.json")) if kind_dir.is_dir() else []
        if not matches:
            return None
        if len(matches) > 1:  # pragma: no cover - defensive
            raise WorkspaceError(f"ambiguous version {version} for {kind}: {matches}")
        data = parse_json(matches[0].read_text(encoding="utf-8"))
        artifact = Artifact(**data)
        if not verify_checksum(artifact):
            raise WorkspaceError(
                f"checksum mismatch on load for {artifact.artifact_id}"
            )
        return artifact

    def _update_index(self, kind: str, version: int, artifact_id: str) -> None:
        index = {}
        if self.index_path.exists():
            index = parse_json(self.index_path.read_text(encoding="utf-8"))
        index[kind] = {"version": version, "artifact_id": artifact_id}
        self._atomic_write_text(self.index_path, canonicalize(index))

    def _check_kind(self, kind: str) -> None:
        if kind not in KINDS:
            raise ValueError(f"unknown artifact kind: {kind!r}")

    @staticmethod
    def _parse_version(filename: str) -> int | None:
        # "v0003-idea-abc123.json" -> 3
        if not filename.startswith("v"):
            return None
        head = filename[1:].split("-", 1)[0]
        try:
            return int(head)
        except ValueError:
            return None

    @staticmethod
    def _atomic_write_new(target: Path, text: str) -> None:
        """Atomically create *target*, failing if it already exists (O_EXCL)."""
        fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
        except Exception:
            # Best-effort cleanup of a partial file.
            try:
                os.unlink(str(target))
            except OSError:  # pragma: no cover
                pass
            raise

    @staticmethod
    def _atomic_write_text(target: Path, text: str) -> None:
        """Atomically replace *target* (used for the mutable index only)."""
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
            os.replace(tmp, str(target))
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:  # pragma: no cover
                pass
            raise
