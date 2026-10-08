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

from .states import (
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
)
from .observability import RunLog, LogEvent
from .orchestrator import Orchestrator, ControlToken, StepResult

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
    "RunLog",
    "LogEvent",
    "Orchestrator",
    "ControlToken",
    "StepResult",
]
