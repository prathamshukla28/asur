"""Learning fold - where a published video's real results teach the next one.

This is the step that closes ASUR's loop. It compares what VIRAL CHECK predicted
against what actually happened (performance), records honest, creator-specific
learnings (EMPIRICAL - measured from this creator's own data, never claimed as
universal fact), tracks content/template fatigue, proposes the next experiment,
and emits knowledge-graph edges. It also folds the published hook back into SCRIPT
memory so the very next idea is informed by measured reality.

Nothing here reaches the network, and nothing publishes - publishing is the human
gate in publish_gate() (ASUR-HUMAN-01). Learnings are EMPIRICAL, not universal.
"""

from __future__ import annotations

from typing import Optional

from ..core.envelope import Artifact, make_artifact
from ..core.identity import Identity
from ..script.evidence import EMPIRICAL, claim
from ..script.hook_memory import HookMemory
from . import source_ref

# A template/content signature repeated this many times (including the current
# video) is flagged as fatiguing - the loop warns a creator before an audience
# tires of a pattern. Deterministic, explainable (ASUR-EXPLAIN-01).
_FATIGUE_THRESHOLD = 3


def _verdict(viral_body: dict) -> str:
    return str(viral_body.get("verdict", "unknown"))


def _completion(performance_body: dict) -> float:
    metrics = performance_body.get("metrics", {}) or {}
    try:
        return float(metrics.get("completion_pct", 0))
    except (TypeError, ValueError):
        return 0.0


def build_learning(
    viral_check_artifact: Artifact,
    performance_artifact: Artifact,
    project_id: str,
    *,
    prior_template_count: int = 0,
    identity: Optional[Identity] = None,
) -> Artifact:
    """Fold prediction (viral check) against reality (performance) into learnings.

    `prior_template_count` is how many earlier videos used this video's template
    signature; combined with this one it drives the fatigue flag. The diff is a
    plain, explainable comparison of the predicted verdict to the measured
    completion - never a single fabricated accuracy %.
    """
    viral_body = viral_check_artifact.body or {}
    perf_body = performance_artifact.body or {}

    predicted_verdict = _verdict(viral_body)
    completion = _completion(perf_body)
    metrics = perf_body.get("metrics", {}) or {}

    # Honest, directional diff: did reality land above/below what the verdict implied?
    # A PASS that completed poorly, or a REJECT that completed well, is the signal.
    if predicted_verdict == "PASS":
        beat = "missed" if completion < 50 else "matched"
    elif predicted_verdict == "REJECT":
        beat = "beat" if completion >= 50 else "matched"
    else:
        beat = "matched"

    template_uses = prior_template_count + 1
    template_fatigue = template_uses >= _FATIGUE_THRESHOLD

    learnings = [
        claim(
            f"On this creator's own video, the '{predicted_verdict}' verdict came with "
            f"{completion:.0f}% completion ({beat} the prediction's implied direction).",
            EMPIRICAL,
            basis="this creator's measured performance; not a universal rule",
        ),
    ]
    if template_fatigue:
        learnings.append(
            claim(
                f"This template signature has now been used {template_uses} times; "
                "watch for audience fatigue on the next video.",
                EMPIRICAL,
                basis="repetition count across this creator's own published videos",
            )
        )

    knowledge_graph_edges = [
        {
            "from": viral_check_artifact.artifact_id,
            "to": performance_artifact.artifact_id,
            "relation": "predicted_then_measured",
        },
    ]

    body = {
        "stage": "learning",
        "prediction": {"verdict": predicted_verdict},
        "actual": {"completion_pct": completion, "metrics": metrics},
        "difference": {"direction": beat},
        "learnings": learnings,
        "template_fatigue": {"uses": template_uses, "fatiguing": template_fatigue},
        "next_experiment": (
            "vary the hook direction (A/B) and re-measure"
            if beat != "matched"
            else "hold the hook direction and vary pacing next"
        ),
        "knowledge_graph_edges": knowledge_graph_edges,
        "method": (
            "local prediction-vs-reality fold; learnings are EMPIRICAL (this creator's "
            "own data), never universal; no network"
        ),
    }

    return make_artifact(
        kind="learning",
        project_id=project_id,
        body=body,
        status="ready",
        sources=[source_ref(viral_check_artifact), source_ref(performance_artifact)],
        agent="learning",
        identity=identity,
    )


def fold_hook_into_memory(
    project_root,
    *,
    hook_text: str,
    project_id: str,
    performance_artifact: Artifact,
    identity: Optional[Identity] = None,
) -> dict:
    """Record the published hook (with its measured result) into SCRIPT memory.

    This is the move that makes the NEXT idea informed: a later build_hooks() can
    pass HookMemory(project_root).prior_hook_texts() and see this published hook.
    Append-only, local, no overwrite (ASUR-VERSION-01, ASUR-LOCAL-01).
    """
    memory = HookMemory(project_root).ensure()
    perf_body = performance_artifact.body or {}
    return memory.record(
        hook_text=hook_text,
        event="published",
        project_id=project_id,
        metadata={"performance": perf_body.get("metrics", {})},
        identity=identity,
    )
