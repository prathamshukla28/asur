"""The 18-state project machine + cost tiers (P02, SPEC-GAP G6/G11/G13).

This is the runtime form of docs/STATE_MACHINE.md. It is pure data + pure
functions: no I/O, no network, stdlib-only (ADR-0002). The orchestrator uses
it to decide the single legal forward transition at each step.

Rules enforced here (ASUR-GATE-01 fail-closed, ASUR-VERSION-01 forward-only):
    * States are a fixed ordered tuple; movement is forward-only, one step.
    * next_state() refuses any non-adjacent or backward move (returns None).
    * Two states are HUMAN gates (stage 18 hero-proof, stage 25 publish).
    * Cost tiers: cheap (stages 0-6), moderate (7-16), expensive (19-21).
      Expensive work is UNREACHABLE before the stage-18 human approval, so the
      expensive floor is recorded and the orchestrator must refuse to enter an
      expensive stage until HERO_PROOF_APPROVED has been reached.
"""

from __future__ import annotations

from typing import Optional

__all__ = [
    "STATES",
    "STATE_INDEX",
    "TRANSITIONS",
    "HUMAN_GATE_STATES",
    "TERMINAL_STATE",
    "CostTier",
    "EXPENSIVE_FLOOR_STAGE",
    "next_state",
    "is_terminal",
    "stage_of",
    "cost_tier_for_stage",
]

# The 18 ordered states (docs/STATE_MACHINE.md). Forward-only, one step each.
STATES = (
    "DRAFT",
    "INPUTS_VERIFIED",
    "RESEARCH_COMPLETE",
    "STRATEGY_APPROVED",
    "HOOK_APPROVED",
    "SCRIPT_APPROVED",
    "TIMING_VERIFIED",
    "CREATIVE_DIRECTION_APPROVED",
    "SCREENPLAY_APPROVED",
    "HERO_PROOF_READY",
    "HERO_PROOF_APPROVED",   # human gate #1 (stage 18)
    "FULL_GENERATION",
    "QA",
    "VIRAL_CHECK_APPROVED",
    "PUBLISH_READY",         # human gate #2 (stage 25)
    "PUBLISHED",
    "PERFORMANCE_CAPTURED",
    "LEARNED",
)

STATE_INDEX = {name: i for i, name in enumerate(STATES)}

TERMINAL_STATE = STATES[-1]  # LEARNED

# The two states a HUMAN must clear (ASUR-HUMAN-01). Entering these requires a
# distinct-approver approval_gate; single-user self-approval is HOLD:SELF_APPROVED.
HUMAN_GATE_STATES = frozenset({"HERO_PROOF_APPROVED", "PUBLISH_READY"})

# Forward-only adjacency: each state maps to the single next legal state.
TRANSITIONS = {
    STATES[i]: STATES[i + 1] for i in range(len(STATES) - 1)
}
TRANSITIONS[TERMINAL_STATE] = None  # LEARNED has no successor


# --- Cost tiers (SPEC-GAP G13) -------------------------------------------------
# The 26-stage content pipeline maps onto the 18 project states. Cost discipline
# is expressed by pipeline-stage number: cheap 0-6, moderate 7-16, expensive
# 19-21. Expensive generation must be UNREACHABLE before the stage-18 human gate.
class CostTier:
    CHEAP = "cheap"
    MODERATE = "moderate"
    EXPENSIVE = "expensive"


# The pipeline stage at/after which expensive work may begin is strictly AFTER
# the stage-18 human approval. Anything expensive is gated behind this floor.
EXPENSIVE_FLOOR_STAGE = 19

# Map each project state to its representative pipeline stage number.
# (docs/PIPELINE.md 26-stage pipeline; the state machine is the gated spine.)
_STATE_STAGE = {
    "DRAFT": 0,
    "INPUTS_VERIFIED": 1,
    "RESEARCH_COMPLETE": 4,
    "STRATEGY_APPROVED": 5,
    "HOOK_APPROVED": 6,
    "SCRIPT_APPROVED": 7,
    "TIMING_VERIFIED": 9,
    "CREATIVE_DIRECTION_APPROVED": 11,
    "SCREENPLAY_APPROVED": 12,
    "HERO_PROOF_READY": 16,
    "HERO_PROOF_APPROVED": 18,   # human gate #1
    "FULL_GENERATION": 19,       # first EXPENSIVE stage, only reachable post-gate
    "QA": 20,
    "VIRAL_CHECK_APPROVED": 23,
    "PUBLISH_READY": 25,         # human gate #2
    "PUBLISHED": 25,
    "PERFORMANCE_CAPTURED": 26,
    "LEARNED": 26,
}


def stage_of(state: str) -> int:
    """Return the representative pipeline-stage number for a project state.

    Fail-closed: an unknown state maps to the expensive floor so nothing cheap
    is ever mis-classified as reachable without a gate.
    """
    return _STATE_STAGE.get(state, EXPENSIVE_FLOOR_STAGE)


def cost_tier_for_stage(stage: int) -> str:
    """Classify a pipeline-stage number into a cost tier (SPEC-GAP G13).

    cheap 0-6, moderate 7 .. EXPENSIVE_FLOOR_STAGE-1, expensive >= the floor.
    The review/approval stages (incl. the stage-18 hero-proof human gate) are
    deliberately NOT expensive: expensive generation begins only at stage 19,
    so the gate that unlocks it must itself be reachable.
    """
    if stage <= 6:
        return CostTier.CHEAP
    if stage < EXPENSIVE_FLOOR_STAGE:
        return CostTier.MODERATE
    return CostTier.EXPENSIVE


def next_state(current: str) -> Optional[str]:
    """Return the single legal forward state, or None if terminal/unknown.

    Fail-closed: an unknown state has no successor (None), so the orchestrator
    cannot advance from a state it does not recognise.
    """
    return TRANSITIONS.get(current, None)


def is_terminal(state: str) -> bool:
    return state == TERMINAL_STATE
