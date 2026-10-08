"""P02 controller tests: state machine, cost tiers, run log, orchestrator.

Each test is tied to the invariant / SPEC-GAP it guards via its docstring,
matching the house convention. All writes go to pytest tmp_path so nothing
touches the real repo and no network/GPU is used.
"""

from __future__ import annotations

import pytest

from asur.core.gate import SHIP, HOLD, BLOCK, Check
from asur.core.identity import Identity
from asur.orchestrator import (
    STATES,
    STATE_INDEX,
    TRANSITIONS,
    HUMAN_GATE_STATES,
    TERMINAL_STATE,
    CostTier,
    EXPENSIVE_FLOOR_STAGE,
    next_state,
    is_terminal,
    stage_of,
    cost_tier_for_stage,
    Orchestrator,
    RunLog,
)


# --- state machine shape (ASUR-VERSION-01 forward-only, SPEC-GAP G6) ----------

def test_states_are_18_and_ordered():
    """ASUR-SM-01: the project machine is exactly the 18 ordered states."""
    assert len(STATES) == 18
    assert STATES[0] == "DRAFT"
    assert STATES[-1] == "LEARNED"
    assert TERMINAL_STATE == "LEARNED"


def test_forward_only_adjacency():
    """ASUR-SM-02: next_state advances exactly one step, never backward/skip."""
    for i in range(len(STATES) - 1):
        assert next_state(STATES[i]) == STATES[i + 1]
    # terminal has no successor
    assert next_state(TERMINAL_STATE) is None
    assert is_terminal(TERMINAL_STATE) is True
    assert is_terminal("DRAFT") is False


def test_unknown_state_has_no_successor():
    """ASUR-GATE-01: an unrecognised state fails closed (no forward move)."""
    assert next_state("NOT_A_STATE") is None


def test_two_human_gate_states():
    """ASUR-HUMAN-01: exactly the hero-proof and publish states are human gates."""
    assert HUMAN_GATE_STATES == frozenset({"HERO_PROOF_APPROVED", "PUBLISH_READY"})


# --- cost tiers (SPEC-GAP G13) -------------------------------------------------

def test_cost_tier_boundaries():
    """ASUR-COST-01: cheap 0-6, moderate 7-16, expensive >=19."""
    assert cost_tier_for_stage(0) == CostTier.CHEAP
    assert cost_tier_for_stage(6) == CostTier.CHEAP
    assert cost_tier_for_stage(7) == CostTier.MODERATE
    assert cost_tier_for_stage(16) == CostTier.MODERATE
    assert cost_tier_for_stage(EXPENSIVE_FLOOR_STAGE) == CostTier.EXPENSIVE
    assert cost_tier_for_stage(21) == CostTier.EXPENSIVE


def test_stage_of_unknown_is_expensive_floor():
    """ASUR-GATE-01: an unknown state maps to the expensive floor (fail closed)."""
    assert stage_of("NOT_A_STATE") == EXPENSIVE_FLOOR_STAGE
    assert stage_of("FULL_GENERATION") == EXPENSIVE_FLOOR_STAGE


# --- orchestrator construction -------------------------------------------------

def test_orchestrator_unknown_start_state_raises(tmp_path):
    """ASUR-GATE-01: constructing a run at an unknown state fails closed."""
    with pytest.raises(ValueError):
        Orchestrator(tmp_path, "run-x", state="NOWHERE")


def test_orchestrator_records_run_start(tmp_path):
    """ASUR-EXPLAIN-01: a new run writes a run_start event to the log."""
    orch = Orchestrator(tmp_path, "run-start", state="DRAFT")
    events = orch.log.all_events()
    assert events
    assert events[0]["action"] == "run_start"
    assert events[0]["tokens"]["state"] == "DRAFT"


# --- expensive-before-gate guard (SPEC-GAP G13) --------------------------------

def test_expensive_blocked_before_hero_proof_gate(tmp_path):
    """ASUR-GATE-01: expensive stages are refused before HERO_PROOF_APPROVED."""
    orch = Orchestrator(tmp_path, "run-cost", state="DRAFT")
    reason = orch._expensive_blocked("FULL_GENERATION")
    assert reason is not None
    assert "HERO_PROOF_APPROVED" in reason


def test_expensive_allowed_after_hero_proof_gate(tmp_path):
    """ASUR-GATE-01: once the hero-proof gate is cleared, expensive is allowed."""
    orch = Orchestrator(tmp_path, "run-cost2", state="HERO_PROOF_APPROVED")
    assert orch._expensive_blocked("FULL_GENERATION") is None


# --- step(): advance / hold (ASUR-GATE-01) -------------------------------------

def test_step_advances_on_ship(tmp_path):
    """ASUR-GATE-01: a SHIP check advances exactly one state and resets residency."""
    orch = Orchestrator(tmp_path, "run-ship", state="DRAFT")
    res = orch.step(checks=[Check("ok", lambda: (SHIP, "ready"))])
    assert res.advanced is True
    assert res.from_state == "DRAFT"
    assert res.to_state == "INPUTS_VERIFIED"
    assert orch.state == "INPUTS_VERIFIED"
    assert orch.residency == 0


def test_step_holds_on_hold_check(tmp_path):
    """ASUR-GATE-01: a HOLD check does not advance; residency increments."""
    orch = Orchestrator(tmp_path, "run-hold", state="DRAFT")
    res = orch.step(checks=[Check("wait", lambda: (HOLD, "not ready"))])
    assert res.advanced is False
    assert orch.state == "DRAFT"
    assert res.to_state == "INPUTS_VERIFIED"
    assert orch.residency == 1


def test_step_no_checks_holds_no_checks(tmp_path):
    """ASUR-GATE-01: a non-human state with no checks fails closed to HOLD."""
    orch = Orchestrator(tmp_path, "run-empty", state="DRAFT")
    res = orch.step(checks=[])
    assert res.advanced is False
    assert res.result.disposition == HOLD
    assert res.result.substate == "NO_CHECKS"


def test_step_block_check_stays(tmp_path):
    """ASUR-GATE-01: a BLOCK check refuses and does not advance."""
    orch = Orchestrator(tmp_path, "run-block", state="DRAFT")
    res = orch.step(checks=[Check("defect", lambda: (BLOCK, "broken"))])
    assert res.advanced is False
    assert res.result.disposition == BLOCK
    assert orch.state == "DRAFT"


def test_step_terminal_holds(tmp_path):
    """ASUR-GATE-01: stepping from the terminal state holds (nothing to advance)."""
    orch = Orchestrator(tmp_path, "run-term", state="LEARNED")
    res = orch.step(checks=[Check("ok", lambda: (SHIP, "ready"))])
    assert res.advanced is False
    assert res.result.substate == "TERMINAL"
    assert orch.state == "LEARNED"


# --- human gates (ASUR-HUMAN-01) -----------------------------------------------

def _ident(user, email):
    return Identity(local_user=user, git_name="", git_email=email)


def test_human_gate_requires_approver(tmp_path):
    """ASUR-HUMAN-01: a human-gate state with no approver holds for a human."""
    orch = Orchestrator(
        tmp_path, "run-hg1", state="HERO_PROOF_READY",
        identity=_ident("alice", "alice@x"),
    )
    res = orch.step(checks=[Check("ok", lambda: (SHIP, "ready"))])
    assert res.advanced is False
    assert res.result.substate == "HUMAN_APPROVAL_REQUIRED"
    assert orch.state == "HERO_PROOF_READY"


def test_human_gate_self_approval_holds(tmp_path):
    """ASUR-HUMAN-01: approver==producer is recorded HOLD:SELF_APPROVED, not SHIP."""
    me = _ident("alice", "alice@x")
    orch = Orchestrator(tmp_path, "run-hg2", state="HERO_PROOF_READY", identity=me)
    res = orch.step(checks=[Check("ok", lambda: (SHIP, "ready"))], approver=me)
    assert res.advanced is False
    assert res.result.substate == "SELF_APPROVED"
    assert res.result.self_approved is True
    assert orch.state == "HERO_PROOF_READY"


def test_human_gate_distinct_approver_advances(tmp_path):
    """ASUR-HUMAN-01: a distinct local approver clears the human gate."""
    producer = _ident("alice", "alice@x")
    approver = _ident("bob", "bob@x")
    orch = Orchestrator(tmp_path, "run-hg3", state="HERO_PROOF_READY", identity=producer)
    res = orch.step(checks=[Check("ok", lambda: (SHIP, "ready"))], approver=approver)
    assert res.advanced is True
    assert orch.state == "HERO_PROOF_APPROVED"


# --- run log (SPEC-GAP G12 + ASUR-FIREWALL-01 + ASUR-VERSION-01) ---------------

def test_runlog_append_only_roundtrip(tmp_path):
    """ASUR-VERSION-01: run-log events persist in append order across reopen."""
    log = RunLog(tmp_path, "run-log").ensure()
    log.record("a", tokens={"state": "DRAFT"})
    log.record("b", tokens={"state": "INPUTS_VERIFIED"})
    events = log.all_events()
    assert [e["action"] for e in events] == ["a", "b"]
    # a fresh instance over the same dir sees the same persisted lines
    reopened = RunLog(tmp_path, "run-log").all_events()
    assert [e["action"] for e in reopened] == ["a", "b"]
    assert log.path == tmp_path / ".asur" / "runs" / "run-log.jsonl"


def test_runlog_rejects_non_control_token(tmp_path):
    """ASUR-FIREWALL-01: the run log refuses any non-control token key."""
    log = RunLog(tmp_path, "run-firewall").ensure()
    with pytest.raises(ValueError):
        log.record("leak", tokens={"findings": "secret target score"})
