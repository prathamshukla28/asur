"""Creator insights - the learning loop made visible (read-only analytics).

ASUR's moat is the closed loop: each video informed by the measured performance
of the last. The machinery is built (hook memory + performance + the learning
fold), but it was only *wired*, not *visible*. This read-only view aggregates a
creator's own append-only hook memory into an honest picture: which hook
directions they have actually published, which carry measured results, and which
patterns are fatiguing - so the next idea is made with the last one's reality in
hand.

Every statement is EMPIRICAL (this creator's own data, never a universal rule)
and there is no aggregate "% viral" or single score (ASUR-HONEST-01). Pure,
local, stdlib-only; no network (ASUR-LOCAL-01). It reads memory; it writes
nothing.
"""

from __future__ import annotations

import os
from typing import Any

from ..script.evidence import EMPIRICAL, claim
from ..script.hook_memory import HookMemory

__all__ = ["build_insights"]

# A pattern/category used at least this many times is flagged as fatiguing - the
# same deterministic, explainable threshold the learning fold uses.
_FATIGUE_THRESHOLD = 3


def _completion(record: dict) -> float | None:
    """Measured completion % recorded with a published hook, if any."""
    perf = (record.get("metadata") or {}).get("performance") or {}
    value = perf.get("completion_pct")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def build_insights(
    project_root: str | os.PathLike[str],
    project_id: str,
) -> dict[str, Any]:
    """Aggregate this creator's hook memory into an honest, EMPIRICAL read.

    Returns a plain dict (so the CLI formats it and tests assert on it): totals,
    a per-direction breakdown with any measured completion, fatigue flags, a set
    of EMPIRICAL learnings, and a next-experiment suggestion. Never a score.
    """
    memory = HookMemory(project_root)
    records = memory.all_records()

    published = [r for r in records if r.get("event") == "published"]
    measured = [(r, c) for r in published if (c := _completion(r)) is not None]

    # Per strategic direction (we use the recorded hook category as the key).
    by_direction: dict[str, dict[str, Any]] = {}
    for rec in records:
        meta = rec.get("metadata") or {}
        key = str(meta.get("category") or "uncategorised")
        slot = by_direction.setdefault(
            key, {"direction": key, "seen": 0, "published": 0, "measured_completion": []}
        )
        slot["seen"] += 1
        if rec.get("event") == "published":
            slot["published"] += 1
            comp = _completion(rec)
            if comp is not None:
                slot["measured_completion"].append(comp)

    directions: list[dict[str, Any]] = []
    for slot in by_direction.values():
        comps = slot["measured_completion"]
        slot["avg_completion"] = round(sum(comps) / len(comps), 1) if comps else None
        directions.append(slot)
    directions.sort(key=lambda d: (d["avg_completion"] is None, -(d["avg_completion"] or 0)))

    # Pattern fatigue (deterministic repetition count).
    pattern_counts: dict[str, int] = {}
    for rec in records:
        pattern = str((rec.get("metadata") or {}).get("pattern") or "unknown")
        pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
    fatigue = [
        {"pattern": p, "uses": n, "fatiguing": n >= _FATIGUE_THRESHOLD}
        for p, n in sorted(pattern_counts.items(), key=lambda kv: -kv[1])
    ]

    learnings: list[dict[str, Any]] = []
    if not records:
        learnings.append(
            claim(
                "No hook memory yet - run the loop and record real performance so "
                "the next idea is informed by measured reality.",
                EMPIRICAL,
                basis="this creator's (empty) hook memory",
            )
        )
    else:
        best = next((d for d in directions if d["avg_completion"] is not None), None)
        if best is not None:
            learnings.append(
                claim(
                    f"Your '{best['direction']}' hooks have the highest measured "
                    f"completion so far ({best['avg_completion']}% over "
                    f"{len(best['measured_completion'])} published video(s)).",
                    EMPIRICAL,
                    basis="this creator's own measured performance; not a universal rule",
                )
            )
        else:
            learnings.append(
                claim(
                    f"{len(published)} hook(s) published but none carry measured "
                    "performance yet - record metrics to make the loop teach.",
                    EMPIRICAL,
                    basis="this creator's hook memory (no performance folded in yet)",
                )
            )
        for row in fatigue:
            if row["fatiguing"]:
                learnings.append(
                    claim(
                        f"The '{row['pattern']}' pattern has been used {row['uses']} "
                        "times; vary it before the audience tires of it.",
                        EMPIRICAL,
                        basis="repetition count across this creator's own hooks",
                    )
                )

    if measured:
        next_experiment = (
            "double down on your best-measured direction, and A/B a fresh angle "
            "against it to keep learning"
        )
    elif published:
        next_experiment = "record the real metrics for your published videos so the loop can teach"
    else:
        next_experiment = "publish one video and record its metrics to seed the loop"

    return {
        "stage": "insights",
        "project_id": project_id,
        "totals": {
            "records": len(records),
            "published": len(published),
            "with_measured_performance": len(measured),
        },
        "by_direction": directions,
        "fatigue": fatigue,
        "learnings": learnings,
        "next_experiment": next_experiment,
        "method": (
            "local aggregation of this creator's own append-only hook memory; "
            "EMPIRICAL only; no aggregate score, no '% viral'; no network"
        ),
    }
