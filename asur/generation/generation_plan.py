"""Stage 13/14 - generation plan (local, explainable, stdlib-only).

Takes the ``asset_plan`` artifact and produces a ``generation_plan`` artifact:
an ordered list of concrete generation jobs, one per planned asset. Each job
names the model, its params, what it depends on, its cost estimate, and whether
it runs locally or in the cloud. No network, no media imports here - this is the
control plan only; the media adapters (behind ``asur[generation]``) consume it.

Every locked-stack default runs locally (``cloud_or_local = "local"``,
``cost_estimate = 0.0``). Ordering is deterministic: background and audio jobs
first, then the procedural on-screen-text jobs that depend on them.
"""

from __future__ import annotations

from typing import Any

from ..core.envelope import Artifact, make_artifact
from ..core.identity import Identity
from . import source_ref

# Which source strategies are produced by an external/cloud call. The locked
# stack is entirely local, so this stays empty for default plans - but it is
# named explicitly so a future cloud model is classified (and cost-tracked)
# rather than silently assumed free.
_CLOUD_STRATEGIES: frozenset[str] = frozenset()


def _job_for_asset(asset: dict[str, Any], index: int) -> dict[str, Any]:
    """Build one generation job from one planned asset."""
    asset_ref = asset.get("asset_ref", f"asset-{index:02d}")
    strategy = asset.get("source_strategy", "ai_image")
    model = asset.get("model_choice", "SDXL")
    cost = float(asset.get("estimated_cost_usd", 0.0))
    cloud_or_local = "cloud" if strategy in _CLOUD_STRATEGIES else "local"

    # On-screen procedural text depends on its scene background existing first
    # (it is composited over it). Derive the sibling background ref by name.
    depends_on: list[str] = []
    if asset_ref.endswith("-onscreen-text"):
        depends_on.append(asset_ref.replace("-onscreen-text", "-background"))

    return {
        "job_id": f"job-{index:02d}-{asset_ref}",
        "target_asset": asset_ref,
        "model": model,
        "params": {
            "source_strategy": strategy,
            "media_type": asset.get("media_type", "image"),
        },
        "depends_on": depends_on,
        "cost_estimate_usd": cost,
        "cloud_or_local": cloud_or_local,
    }


def build_generation_plan(
    asset_plan_artifact: Artifact,
    project_id: str,
    *,
    identity: Identity | None = None,
) -> Artifact:
    """Produce a ``generation_plan`` artifact from the asset plan.

    One ordered job per planned asset. Deterministic ordering: non-dependent
    jobs (backgrounds, voice, music) keep their plan order first, then jobs with
    ``depends_on`` follow. All locked-stack jobs run locally at zero cost.
    """
    ap_body = asset_plan_artifact.body or {}
    subject = ap_body.get("subject", "the topic")
    assets = ap_body.get("assets") or []

    numbered = [_job_for_asset(asset, i) for i, asset in enumerate(assets)]
    # Stable split: independent jobs first, dependent jobs after, each keeping
    # original relative order (a deterministic topological-ish ordering).
    independent = [j for j in numbered if not j["depends_on"]]
    dependent = [j for j in numbered if j["depends_on"]]
    jobs = independent + dependent

    total_cost = sum(j.get("cost_estimate_usd", 0.0) for j in jobs)

    body: dict[str, Any] = {
        "subject": subject,
        "job_count": len(jobs),
        "jobs": jobs,
        "total_cost_estimate_usd": total_cost,
        "all_local": all(j["cloud_or_local"] == "local" for j in jobs),
        "method": (
            "local heuristic: one job per planned asset, locked-stack models, "
            "deterministic dependency ordering; no network, no model call"
        ),
    }

    return make_artifact(
        kind="generation_plan",
        project_id=project_id,
        body=body,
        status="ready",
        sources=[source_ref(asset_plan_artifact)],
        agent="generation",
        identity=identity,
    )
