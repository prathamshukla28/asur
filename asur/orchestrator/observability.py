"""Append-only local run-log (P02, SPEC-GAP G12).

Every important orchestrator operation is recorded as one canonical-JSON line
in an append-only log under ``<project_root>/.asur/runs/<run_id>.jsonl``.

This is LOCAL observability only (ASUR-LOCAL-01): no network, no telemetry, no
remote sink. It is append-only (ASUR-VERSION-01): lines are only ever added,
never edited or deleted. It records control tokens and decisions, never
findings / pass-criteria / quality-hardness targets (ASUR-FIREWALL-01).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..core.canonical import canonicalize, parse_json
from ..core.envelope import utc_now_iso
from ..core.identity import Identity, get_identity

__all__ = ["RunLog", "LogEvent"]

# The control-only fields an event may carry. Deliberately NARROW so no
# findings / criteria / targets can be logged (ASUR-FIREWALL-01).
_ALLOWED_TOKEN_KEYS = frozenset(
    {"state", "next_state", "gate", "disposition", "substate", "digest", "residency"}
)


@dataclass
class LogEvent:
    """One recorded operation (a control-token snapshot + a short action)."""

    action: str
    at: str
    actor: dict
    tokens: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "action": self.action,
            "at": self.at,
            "actor": self.actor,
            "tokens": dict(self.tokens),
        }


class RunLog:
    """Append-only json-lines run log for a single orchestrator run.

    Layout: ``<project_root>/.asur/runs/<run_id>.jsonl`` (one event per line).
    """

    ASUR_DIRNAME = ".asur"
    RUNS_DIRNAME = "runs"

    def __init__(self, project_root, run_id: str):
        self.project_root = Path(project_root)
        self.run_id = run_id
        self.dir = self.project_root / self.ASUR_DIRNAME / self.RUNS_DIRNAME
        self.path = self.dir / f"{run_id}.jsonl"

    def ensure(self) -> "RunLog":
        self.dir.mkdir(parents=True, exist_ok=True)
        return self

    def record(
        self,
        action: str,
        *,
        tokens: Optional[dict] = None,
        identity: Optional[Identity] = None,
    ) -> LogEvent:
        """Append one event. Fail-closed on any non-control token key.

        Only keys in ``_ALLOWED_TOKEN_KEYS`` may appear in ``tokens`` - this
        structurally prevents findings/criteria/targets from being logged
        (ASUR-FIREWALL-01). An out-of-vocabulary key raises ValueError.
        """
        tokens = dict(tokens or {})
        bad = set(tokens) - _ALLOWED_TOKEN_KEYS
        if bad:
            raise ValueError(
                f"run-log tokens may only carry control fields "
                f"{sorted(_ALLOWED_TOKEN_KEYS)}; refused {sorted(bad)} "
                f"(ASUR-FIREWALL-01)"
            )
        ident = identity or get_identity()
        event = LogEvent(
            action=action,
            at=utc_now_iso(),
            actor=ident.as_dict(),
            tokens=tokens,
        )
        self._append_line(canonicalize(event.as_dict()).rstrip("\n"))
        return event

    def all_events(self) -> list:
        """Return events in append order ([] if the log does not exist yet)."""
        if not self.path.exists():
            return []
        out: list = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(parse_json(line))
        return out

    def _append_line(self, line: str) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, (line + "\n").encode("utf-8"))
        finally:
            os.close(fd)
