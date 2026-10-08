"""The fail-closed disposition gate - ASUR-GATE-01 and ASUR-HUMAN-01.

A gate is a checkpoint between pipeline stages. It answers one question:
"may the project advance past this point?" and returns a *disposition* in the
closed vocabulary:

    SHIP   - advance; all checks passed and (where required) a distinct human
             approved.
    HOLD   - do not advance yet; something is missing but not wrong (e.g. no
             independent approver yet, or a quality check wants changes).
    BLOCK  - refuse; something is wrong (checksum mismatch, license violation,
             firewall leak).

Fail-closed means: the DEFAULT outcome of an unknown or missing condition is
never SHIP. Absence caps at HOLD; contradiction caps at BLOCK.

De-keying: Trinity proved "producer != approver" with signatures. ASUR proves
it by comparing local identities (git/OS principal). If the approver's
principal equals the producer's, that is allowed for a single-user machine,
but it is recorded honestly as ``self_approved=True`` and the disposition is
capped at ``HOLD:SELF_APPROVED`` unless the gate explicitly permits
self-approval. No keys, no network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from .identity import Identity, get_identity

__all__ = [
    "SHIP",
    "HOLD",
    "BLOCK",
    "Check",
    "GateResult",
    "run_gate",
    "approval_gate",
]

SHIP = "SHIP"
HOLD = "HOLD"
BLOCK = "BLOCK"

# Severity ordering so we can take the "worst" outcome across many checks.
_RANK = {SHIP: 0, HOLD: 1, BLOCK: 2}


@dataclass
class Check:
    """One named condition evaluated by a gate.

    ``fn`` returns a tuple (disposition, reason). A check that merely passes
    returns (SHIP, "..."); a check that wants changes returns (HOLD, ...);
    a check that detects something wrong returns (BLOCK, ...).
    """

    name: str
    fn: Callable[[], tuple[str, str]]


@dataclass
class GateResult:
    """The outcome of running a gate: a disposition plus an explainable trail."""

    disposition: str
    substate: Optional[str]
    reasons: list = field(default_factory=list)
    self_approved: bool = False

    @property
    def passed(self) -> bool:
        return self.disposition == SHIP

    def as_dict(self) -> dict:
        return {
            "disposition": self.disposition,
            "substate": self.substate,
            "reasons": list(self.reasons),
            "self_approved": self.self_approved,
        }


def _worst(a: str, b: str) -> str:
    return a if _RANK[a] >= _RANK[b] else b


def run_gate(name: str, checks: list[Check]) -> GateResult:
    """Evaluate *checks* and return the worst (most restrictive) disposition.

    Fail-closed: if ``checks`` is empty we HOLD (nothing was actually
    verified, so we cannot SHIP). Any check that raises is treated as BLOCK -
    an error in a safety check must never silently pass.
    """
    if not checks:
        return GateResult(
            disposition=HOLD,
            substate="NO_CHECKS",
            reasons=[f"gate {name!r}: no checks supplied; cannot advance"],
        )

    disposition = SHIP
    reasons: list = []
    for check in checks:
        try:
            result, reason = check.fn()
        except Exception as exc:  # fail closed on a broken check
            result, reason = BLOCK, f"check {check.name!r} raised: {exc!r}"
        if result not in _RANK:  # unknown disposition -> fail closed
            result, reason = BLOCK, f"check {check.name!r} returned unknown: {result!r}"
        reasons.append({"check": check.name, "disposition": result, "reason": reason})
        disposition = _worst(disposition, result)

    return GateResult(disposition=disposition, substate=None, reasons=reasons)


def approval_gate(
    name: str,
    *,
    producer: Identity,
    approver: Optional[Identity] = None,
    checks: Optional[list[Check]] = None,
    allow_self_approval: bool = False,
) -> GateResult:
    """A gate that requires human approval plus (optionally) content checks.

    - No approver supplied        -> HOLD:HUMAN_APPROVAL_REQUIRED.
    - Approver == producer        -> self_approved=True; SHIP only if
                                     ``allow_self_approval``, else
                                     HOLD:SELF_APPROVED.
    - Approver != producer        -> treated as independent approval; the
                                     disposition is then whatever the content
                                     checks yield (default SHIP).
    Content checks can still force HOLD/BLOCK regardless of approval.
    """
    content = run_gate(name, checks) if checks else GateResult(SHIP, None, [])
    # A BLOCK from content checks dominates everything.
    if content.disposition == BLOCK:
        return GateResult(BLOCK, "CONTENT_BLOCK", content.reasons)

    if approver is None:
        return GateResult(
            HOLD,
            "HUMAN_APPROVAL_REQUIRED",
            content.reasons + [{"check": "approval", "disposition": HOLD,
                                "reason": "no approver recorded"}],
        )

    self_approved = approver.principal() == producer.principal()
    if self_approved and not allow_self_approval:
        return GateResult(
            HOLD,
            "SELF_APPROVED",
            content.reasons + [{"check": "approval", "disposition": HOLD,
                                "reason": f"approver {approver.principal()!r} is the "
                                          f"producer; needs a distinct approver"}],
            self_approved=True,
        )

    # Independent approval (or explicitly permitted self-approval): take the
    # content disposition (SHIP unless a content check asked to HOLD).
    reason = ("self-approval explicitly permitted" if self_approved
              else f"approved by distinct principal {approver.principal()!r}")
    return GateResult(
        content.disposition,
        None if content.disposition == SHIP else "CONTENT_HOLD",
        content.reasons + [{"check": "approval", "disposition": SHIP, "reason": reason}],
        self_approved=self_approved,
    )
