"""ASUR ORCHESTRATOR - the control-tokens-only conductor (P02).

The orchestrator sequences the 18-state project machine. It carries ONLY
control tokens between stages - state, gate name, disposition, digest, and a
residency count - and NEVER findings, pass-criteria, quality/hardness targets,
or evidence bytes (ASUR-FIREWALL-01). It is stdlib-only (ADR-0002).

Public surface:
    STATES, STATE_INDEX, TRANSITIONS, next_state, is_terminal  (states)
    HUMAN_GATE_STATES                                          (states)
    cost_tier_for_stage, CostTier, EXPENSIVE_FLOOR_STAGE       (states)
    RunLog, LogEvent                                           (observability)
    Orchestrator, ControlToken, StepResult                    (orchestrator)
"""

from __future__ import annotations

from .observability import LogEvent, RunLog
from .orchestrator import ControlToken, Orchestrator, StepResult
from .states import (
    EXPENSIVE_FLOOR_STAGE,
    HUMAN_GATE_STATES,
    STATE_INDEX,
    STATES,
    TERMINAL_STATE,
    TRANSITIONS,
    CostTier,
    cost_tier_for_stage,
    is_terminal,
    next_state,
    stage_of,
)

__all__ = [
    "EXPENSIVE_FLOOR_STAGE",
    "HUMAN_GATE_STATES",
    "STATES",
    "STATE_INDEX",
    "TERMINAL_STATE",
    "TRANSITIONS",
    "ControlToken",
    "CostTier",
    "LogEvent",
    "Orchestrator",
    "RunLog",
    "StepResult",
    "cost_tier_for_stage",
    "is_terminal",
    "next_state",
    "stage_of",
]
