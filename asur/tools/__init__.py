"""ASUR firewall tooling (P03) - the only bridge between GENERATION and VIRAL CHECK.

This package implements ASUR-FIREWALL-01. GENERATION and VIRAL CHECK never
communicate directly; SCRIPT bridges them through two computed projections
(`projection.py`) and a hash-chained hand-off queue (`queue.py`).

Stdlib-only (ADR-0002): this package imports only the Python standard library
and other `asur.*` modules. It performs no network I/O and uses no media deps.
"""

from __future__ import annotations

from .projection import (
    GENERATION_FORBIDDEN,
    VIRAL_FORBIDDEN,
    FirewallLeak,
    build_generation_view,
    build_viral_view,
    conformance_scan,
)
from .queue import (
    HandoffQueue,
    QueueError,
)

__all__ = [
    "GENERATION_FORBIDDEN",
    "VIRAL_FORBIDDEN",
    "FirewallLeak",
    "build_generation_view",
    "build_viral_view",
    "conformance_scan",
    "HandoffQueue",
    "QueueError",
]
