"""Resolve a hook A/B experiment from MEASURED performance (closes SPEC-GAP G2).

The hooks stage groups hooks into data-only A/B/C/D variants but - correctly -
never declares a winner, because SCRIPT has no performance data (ASUR-HONEST-01).
This is the honest other half: once videos have actually been published and their
results folded into hook memory, this picks the measured winner among the
variants whose hooks were really used.

It declares a winner ONLY when at least two variants carry a measured result -
otherwise it HOLDs with ``insufficient_data`` and names what is missing. It never
implies a winner it cannot measure (ASUR-HONEST-01) and never reaches the network
(ASUR-LOCAL-01). Pure, local, stdlib-only; reads memory, writes nothing.
"""

from __future__ import annotations

from typing import Any

from ..core.envelope import Artifact
from ..core.gate import HOLD, SHIP

__all__ = ["resolve_ab_experiment"]


def _completion_by_hook(memory_records: list[dict]) -> dict[str, float]:
    """Best measured completion % per published hook text (latest wins on ties)."""
    out: dict[str, float] = {}
    for rec in memory_records:
        if rec.get("event") != "published":
            continue
        hook = rec.get("hook")
        perf = (rec.get("metadata") or {}).get("performance") or {}
        value = perf.get("completion_pct")
        if not isinstance(hook, str) or value is None:
            continue
        try:
            out[hook] = float(value)
        except (TypeError, ValueError):
            continue
    return out


def resolve_ab_experiment(
    hooks_artifact: Artifact,
    memory_records: list[dict],
) -> dict[str, Any]:
    """Pick the measured-winner variant from this creator's real performance.

    ``hooks_artifact`` supplies the A/B/C/D variants (each with a chosen hook).
    ``memory_records`` is ``HookMemory.all_records()`` - the published hooks and
    the performance folded in with them. Returns a plain dict: each variant with
    its measured completion (or None), the winner (or None), and a fail-closed
    disposition.
    """
    body = hooks_artifact.body or {}
    variants = (body.get("ab_variants") or {}).get("variants") or []
    measured = _completion_by_hook(memory_records)

    rows: list[dict[str, Any]] = []
    for variant in variants:
        chosen = variant.get("chosen_hook", "")
        completion = measured.get(chosen)
        rows.append(
            {
                "variant": variant.get("variant"),
                "direction": variant.get("direction"),
                "chosen_hook": chosen,
                "measured_completion": completion,
            }
        )

    with_data = [r for r in rows if r["measured_completion"] is not None]
    if len(with_data) >= 2:
        winner = max(with_data, key=lambda r: r["measured_completion"])
        return {
            "stage": "ab_resolution",
            "status": "resolved",
            "variants": rows,
            "winner": {
                "variant": winner["variant"],
                "direction": winner["direction"],
                "measured_completion": winner["measured_completion"],
            },
            "disposition": SHIP,
            "method": (
                "measured winner chosen from this creator's real published "
                "performance; no winner implied without data (ASUR-HONEST-01)"
            ),
        }

    return {
        "stage": "ab_resolution",
        "status": "insufficient_data",
        "variants": rows,
        "winner": None,
        "disposition": HOLD,
        "reason": (
            f"only {len(with_data)} variant(s) carry a measured result; at least 2 "
            "are needed to declare a winner - publish and measure more variants"
        ),
        "method": (
            "fail closed: a real A/B winner requires measured performance for at "
            "least two variants (ASUR-GATE-01/HONEST-01)"
        ),
    }
