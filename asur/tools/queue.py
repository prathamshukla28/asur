"""Hash-chained hand-off queue - the only channel from GENERATION to VIRAL CHECK.

ASUR-FIREWALL-01 + ASUR-VERSION-01 + STATE_MACHINE.md s5 (HEAD/digest binding).

The queue is a local append-only json-lines log at
``<project_root>/.asur/queue/<run_id>.jsonl``. Its lifecycle mirrors Trinity's
route -> seal -> claim -> verdict -> place, kept entirely key-free (SHA-256 +
atomic file ops only, no signing):

  seal(run_id, task_id, bundle)
      GENERATION hands off a rendered bundle. We compute its canonical SHA-256
      digest and append a 'seal' line. Once sealed the bundle is FROZEN - a
      second seal of the SAME task_id with DIFFERENT bytes is refused
      (task-collision, QueueError). Returns the sealed digest.

  claim(run_id, task_id)
      VIRAL CHECK atomically claims a sealed bundle (one claimant only, via an
      O_EXCL lock file). Evaluation then happens AT the sealed digest.

  verdict(run_id, task_id, digest, disposition)
      VIRAL CHECK records the digest it actually evaluated plus its disposition.

  place(run_id, task_id)
      Advancing the bundle succeeds ONLY when sealed digest == verdict digest ==
      on-disk digest (3-way agreement). Any mismatch -> BLOCK (QueueError). This
      guarantees the verdict is about the same bytes that exist on disk.

De-keying: integrity here is pure SHA-256 over canonical bytes (KEEP). There is
no signature of authorship (DROPPED); who sealed/claimed is recorded via local
identity only.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from ..core.canonical import canonical_sha256, canonicalize, parse_json
from ..core.identity import Identity, get_identity

__all__ = ["HandoffQueue", "QueueError"]

# Event kinds appended to the queue log.
_SEAL = "seal"
_CLAIM = "claim"
_VERDICT = "verdict"
_PLACE = "place"


class QueueError(RuntimeError):
    """Fail-closed queue error. Maps to BLOCK at the gate layer."""


class HandoffQueue:
    """Append-only, hash-chained hand-off queue for one run.

    Layout: ``<project_root>/.asur/queue/<run_id>.jsonl`` plus per-task
    ``<task_id>.claim`` lock files in the same directory.
    """

    ASUR_DIRNAME = ".asur"
    QUEUE_DIRNAME = "queue"

    def __init__(self, project_root, run_id: str):
        self.project_root = Path(project_root)
        self.run_id = run_id
        self.dir = self.project_root / self.ASUR_DIRNAME / self.QUEUE_DIRNAME
        self.path = self.dir / f"{run_id}.jsonl"

    def ensure(self) -> "HandoffQueue":
        self.dir.mkdir(parents=True, exist_ok=True)
        return self

    # -- public lifecycle ---------------------------------------------------

    def seal(
        self,
        task_id: str,
        bundle: dict,
        *,
        identity: Optional[Identity] = None,
    ) -> str:
        """Seal a rendered bundle; freeze it; return its content digest.

        Re-sealing the same task_id with identical bytes is idempotent (returns
        the same digest). Re-sealing with DIFFERENT bytes is a task-collision and
        fails closed (QueueError) - a sealed bundle is frozen (ASUR-VERSION-01).
        """
        digest = canonical_sha256(bundle)
        prior = self._latest(_SEAL, task_id)
        if prior is not None and prior.get("digest") != digest:
            raise QueueError(
                f"task '{task_id}' already sealed with a different digest "
                f"(frozen on seal); refusing re-seal with new bytes "
                f"(ASUR-VERSION-01)"
            )
        self._append(
            _SEAL,
            task_id,
            {"digest": digest, "bundle": bundle},
            identity=identity,
        )
        return digest

    def claim(
        self,
        task_id: str,
        *,
        identity: Optional[Identity] = None,
    ) -> str:
        """Atomically claim a sealed bundle (one claimant). Return sealed digest.

        Fails closed if the task was never sealed, or if it is already claimed
        (the O_EXCL lock file guarantees a single claimant).
        """
        sealed = self._latest(_SEAL, task_id)
        if sealed is None:
            raise QueueError(
                f"cannot claim task '{task_id}': never sealed (fail closed)"
            )
        lock = self.dir / f"{task_id}.claim"
        try:
            fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError as exc:
            raise QueueError(
                f"task '{task_id}' already claimed (single claimant only)"
            ) from exc
        os.close(fd)
        self._append(_CLAIM, task_id, {"digest": sealed["digest"]}, identity=identity)
        return sealed["digest"]

    def verdict(
        self,
        task_id: str,
        digest: str,
        disposition: str,
        *,
        identity: Optional[Identity] = None,
    ) -> None:
        """Record the digest VIRAL CHECK actually evaluated + its disposition."""
        if self._latest(_CLAIM, task_id) is None:
            raise QueueError(
                f"cannot record verdict for unclaimed task '{task_id}' "
                f"(fail closed)"
            )
        self._append(
            _VERDICT,
            task_id,
            {"digest": digest, "disposition": disposition},
            identity=identity,
        )

    def place(
        self,
        task_id: str,
        *,
        identity: Optional[Identity] = None,
    ) -> str:
        """Advance the bundle iff sealed == verdict == on-disk digest (3-way).

        Returns the agreed digest on success. Any mismatch or missing step is a
        BLOCK (QueueError): the verdict must be about the exact bytes on disk
        (STATE_MACHINE.md s5 HEAD/digest binding).
        """
        sealed = self._latest(_SEAL, task_id)
        verdict = self._latest(_VERDICT, task_id)
        if sealed is None:
            raise QueueError(f"cannot place task '{task_id}': never sealed")
        if verdict is None:
            raise QueueError(f"cannot place task '{task_id}': no verdict")
        on_disk = canonical_sha256(sealed["bundle"])
        sealed_digest = sealed.get("digest")
        verdict_digest = verdict.get("digest")
        if not (sealed_digest == verdict_digest == on_disk):
            raise QueueError(
                f"digest mismatch for task '{task_id}': "
                f"sealed={sealed_digest} verdict={verdict_digest} "
                f"on_disk={on_disk}; refusing to place (BLOCK, "
                f"HEAD/digest binding)"
            )
        self._append(
            _PLACE,
            task_id,
            {"digest": on_disk, "disposition": verdict.get("disposition")},
            identity=identity,
        )
        return on_disk

    def events(self) -> list:
        """All queue events in append order ([] if the log does not exist)."""
        if not self.path.exists():
            return []
        out: list = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(parse_json(line))
        return out

    # -- internals ----------------------------------------------------------

    def _latest(self, kind: str, task_id: str) -> Optional[dict]:
        found: Optional[dict] = None
        for event in self.events():
            if event.get("kind") == kind and event.get("task_id") == task_id:
                found = event
        return found

    def _append(
        self,
        kind: str,
        task_id: str,
        payload: dict,
        *,
        identity: Optional[Identity] = None,
    ) -> None:
        ident = identity or get_identity()
        from ..core.envelope import utc_now_iso

        record = {
            "kind": kind,
            "task_id": task_id,
            "run_id": self.run_id,
            "at": utc_now_iso(),
            "by": ident.as_dict(),
            **payload,
        }
        self.dir.mkdir(parents=True, exist_ok=True)
        line = canonicalize(record).rstrip("\n")
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, (line + "\n").encode("utf-8"))
        finally:
            os.close(fd)
