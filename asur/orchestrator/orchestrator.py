"""The control-tokens-only orchestrator (P02, SPEC-GAP G6/G11/G13).

The orchestrator advances the 18-state project machine one gated step at a
time. It is the conductor from docs/AGENTS.md: it carries ONLY control tokens
(state, gate name, disposition, digest, residency) and NEVER findings,
pass-criteria, quality/hardness targets, or evidence bytes (ASUR-FIREWALL-01).

Each step:
    1. Determine the single legal forward state (states.next_state); fail
       closed if none.
    2. Refuse to enter an EXPENSIVE stage before the stage-18 human gate
       (HERO_PROOF_APPROVED) has been cleared (SPEC-GAP G13 / ASUR-GATE-01).
    3. Run the step's gate:
         - a human-gate target state uses approval_gate (producer != approver;
           single-user self-approval -> HOLD:SELF_APPROVED, ASUR-HUMAN-01);
         - every other state uses run_gate over the caller-supplied checks.
    4. Advance only on SHIP; otherwise stay put and report the disposition.
    5. Record a control-token event to the append-only run log (G12).

The orchestrator never writes artifacts itself; artifact writes happen in the
stage builders via the versioned append-only Workspace (ASUR-VERSION-01).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..core.gate import BLOCK, HOLD, SHIP, Check, GateResult, approval_gate, run_gate
from ..core.identity import Identity, get_identity
from .observability import RunLog
from .states import (
    HUMAN_GATE_STATES,
    STATE_INDEX,
    STATES,
    CostTier,
    cost_tier_for_stage,
    is_terminal,
    next_state,
    stage_of,
)

__all__ = ["ControlToken", "Orchestrator", "StepResult"]


@dataclass
class ControlToken:
    """The only thing the orchestrator carries between stages.

    Deliberately narrow: state + gate + disposition + digest + residency.
    No findings, no criteria, no targets (ASUR-FIREWALL-01).
    """

    state: str
    gate: str | None = None
    disposition: str | None = None
    digest: str | None = None
    residency: int = 0

    def as_dict(self) -> dict:
        return {
            "state": self.state,
            "gate": self.gate,
            "disposition": self.disposition,
            "digest": self.digest,
            "residency": self.residency,
        }


@dataclass
class StepResult:
    """Outcome of attempting one forward transition."""

    advanced: bool
    from_state: str
    to_state: str | None
    result: GateResult
    reasons: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "advanced": self.advanced,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "disposition": self.result.disposition,
            "substate": self.result.substate,
            "reasons": list(self.reasons),
        }


class Orchestrator:
    """Drives one project run through the gated state machine."""

    def __init__(
        self,
        project_root,
        run_id: str,
        *,
        state: str = "DRAFT",
        identity: Identity | None = None,
    ):
        if state not in STATE_INDEX:
            raise ValueError(f"unknown start state {state!r}")
        self.identity = identity or get_identity()
        self.state = state
        self.run_id = run_id
        self.log = RunLog(project_root, run_id).ensure()
        self.residency = 0
        self.log.record("run_start", tokens={"state": self.state}, identity=self.identity)

    # -- queries ---------------------------------------------------------------
    def token(self, *, gate=None, disposition=None, digest=None) -> ControlToken:
        return ControlToken(
            state=self.state,
            gate=gate,
            disposition=disposition,
            digest=digest,
            residency=self.residency,
        )

    def is_done(self) -> bool:
        return is_terminal(self.state)

    def _expensive_blocked(self, target: str) -> str | None:
        """Return a reason string if entering *target* is expensive-before-gate.

        Expensive stages (>= EXPENSIVE_FLOOR_STAGE) are unreachable until the
        stage-18 human gate HERO_PROOF_APPROVED has been reached. Compared by
        state order so it is purely local and deterministic (SPEC-GAP G13).
        """
        tier = cost_tier_for_stage(stage_of(target))
        if tier != CostTier.EXPENSIVE:
            return None
        gate_idx = STATE_INDEX["HERO_PROOF_APPROVED"]
        if STATE_INDEX[self.state] < gate_idx:
            return (
                f"refusing to enter expensive stage {target!r}: the stage-18 "
                f"human gate (HERO_PROOF_APPROVED) has not been cleared "
                f"(ASUR-GATE-01, cost discipline)"
            )
        return None

    # -- the one operation -----------------------------------------------------
    def step(
        self,
        *,
        checks: list[Check] | None = None,
        approver: Identity | None = None,
        digest: str | None = None,
        allow_self_approval: bool = False,
    ) -> StepResult:
        """Attempt the single legal forward transition from the current state.

        * Terminal state -> HOLD (nothing to advance to).
        * Human-gate target -> approval_gate (producer != approver).
        * Otherwise -> run_gate over *checks*.
        Advances only on SHIP.
        """
        target = next_state(self.state)
        if target is None:
            res = GateResult(HOLD, "TERMINAL", [
                {"check": "transition", "disposition": HOLD,
                 "reason": f"state {self.state!r} is terminal; no forward step"}
            ])
            return self._stay(res)

        # Cost discipline: expensive stages gated behind the hero-proof gate.
        blocked = self._expensive_blocked(target)
        if blocked is not None:
            res = GateResult(BLOCK, "COST_TIER", [
                {"check": "cost_tier", "disposition": BLOCK, "reason": blocked}
            ])
            self.log.record(
                "step_blocked",
                tokens={"state": self.state, "next_state": target,
                        "disposition": BLOCK, "substate": "COST_TIER"},
                identity=self.identity,
            )
            return self._stay(res, to=target)

        gate_name = f"enter:{target}"
        if target in HUMAN_GATE_STATES:
            res = approval_gate(
                gate_name,
                producer=self.identity,
                approver=approver,
                checks=checks,
                allow_self_approval=allow_self_approval,
            )
        else:
            res = run_gate(gate_name, checks or [])

        self.log.record(
            "step_eval",
            tokens={"state": self.state, "next_state": target, "gate": gate_name,
                    "disposition": res.disposition, "substate": res.substate,
                    "digest": digest},
            identity=self.identity,
        )

        if res.disposition == SHIP:
            self.state = target
            self.residency = 0
            self.log.record(
                "advanced",
                tokens={"state": self.state, "disposition": SHIP, "digest": digest},
                identity=self.identity,
            )
            return StepResult(True, STATES[STATE_INDEX[self.state] - 1], self.state,
                              res, res.reasons)
        return self._stay(res, to=target)

    def _stay(self, res: GateResult, to: str | None = None) -> StepResult:
        self.residency += 1
        return StepResult(False, self.state, to, res, res.reasons)
