"""Persisted, append-only hook memory (SPEC-GAP G3).

Every hook this creator generates, uses, rejects, or publishes is recorded as
one line in an append-only log inside the SCRIPT workspace:

    <project_root>/.script/memory/hooks.jsonl

Each line is one canonical-JSON record. The file is only ever appended to -
records are never edited or deleted (ASUR-VERSION-01). Reading back the hook
texts feeds ``build_hooks(prior_hooks=...)`` so the originality + hook-fatigue
checks compare new hooks against what this creator has actually done before,
across runs.

Local only, stdlib only, no network (ASUR-LOCAL-01). A record carries the
reason it exists so nothing is a black box (ASUR-EXPLAIN-01).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable, Optional

from ..core.canonical import canonicalize, parse_json
from ..core.envelope import utc_now_iso
from ..core.identity import Identity, get_identity

__all__ = ["HookMemory", "HOOK_EVENTS"]

HOOK_EVENTS = ("generated", "used", "rejected", "published")


class HookMemory:
    """Append-only JSONL store of hook events under the SCRIPT workspace."""

    MEMORY_DIRNAME = "memory"
    HOOKS_FILENAME = "hooks.jsonl"

    def __init__(self, project_root: str | os.PathLike):
        self.project_root = Path(project_root)
        self.dir = self.project_root / ".script" / self.MEMORY_DIRNAME
        self.path = self.dir / self.HOOKS_FILENAME

    def ensure(self) -> "HookMemory":
        self.dir.mkdir(parents=True, exist_ok=True)
        return self

    def record(
        self,
        *,
        hook_text: str,
        event: str,
        project_id: str,
        metadata: Optional[dict[str, Any]] = None,
        identity: Optional[Identity] = None,
    ) -> dict[str, Any]:
        """Append one hook event. Returns the stored record.

        Fail-closed: an unknown event is rejected (ASUR-GATE-01) rather than
        silently recorded, so the memory stays trustworthy.
        """
        if event not in HOOK_EVENTS:
            raise ValueError(
                f"unknown hook event {event!r}; expected one of {HOOK_EVENTS}"
            )
        ident = identity or get_identity()
        record = {
            "hook": hook_text,
            "event": event,
            "project_id": project_id,
            "recorded_at": utc_now_iso(),
            "recorded_by": ident.as_dict(),
            "metadata": metadata or {},
        }
        self.ensure()
        self._append_line(canonicalize(record).rstrip("\n"))
        return record

    def record_many(
        self,
        hooks: Iterable[dict[str, Any]],
        *,
        event: str,
        project_id: str,
        identity: Optional[Identity] = None,
    ) -> int:
        """Record every hook in *hooks* (each a hooks-artifact hook dict).

        Returns the number of records appended.
        """
        count = 0
        for hook in hooks:
            meta = hook.get("metadata", {})
            self.record(
                hook_text=meta.get("hook", ""),
                event=event,
                project_id=project_id,
                metadata={
                    "hook_id": hook.get("hook_id"),
                    "category": meta.get("category"),
                    "pattern": meta.get("pattern"),
                    "language": meta.get("language"),
                    "aggregate": hook.get("aggregate"),
                },
                identity=identity,
            )
            count += 1
        return count

    def all_records(self) -> list[dict[str, Any]]:
        """Read every stored record in append order. Empty list if none."""
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                records.append(parse_json(line))
        return records

    def prior_hook_texts(self, *, events: Iterable[str] = HOOK_EVENTS) -> list[str]:
        """Distinct hook texts seen in the given *events*, in first-seen order.

        This is what feeds ``build_hooks(prior_hooks=...)``.
        """
        wanted = set(events)
        seen: list[str] = []
        seen_set: set[str] = set()
        for rec in self.all_records():
            if rec.get("event") in wanted:
                text = rec.get("hook", "")
                if text and text not in seen_set:
                    seen_set.add(text)
                    seen.append(text)
        return seen

    def _append_line(self, line: str) -> None:
        fd = os.open(
            str(self.path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644
        )
        with os.fdopen(fd, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
