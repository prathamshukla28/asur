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


def _prompt_for_asset(
    asset_ref: str,
    media_type: str,
    scenes_by_id: dict[str, dict[str, Any]] | None,
) -> str | None:
    """Derive a real generation prompt from the owning screenplay scene.

    Closes the crude-prompt gap (SPEC-GAP G26): the adapter was previously
    handed the bare asset-ref string (e.g. ``"scene-01-hook-background"``) as
    its prompt. Here we look the asset back to its screenplay scene and build
    the prompt ONLY from already-authored scene fields - never inventing text
    (AGENTS.md §7). When no screenplay is supplied, or the owning scene/field is
    absent, we return ``None`` so the caller omits the key and the dispatcher
    falls back to the old ref-string behaviour (fail soft, byte-identical).

      * image background -> ``"{visual_concept}. {semantic_metaphor}. {composition}"``
      * shared voice-track -> the joined spoken content of every scene
      * shared music-bed  -> the first scene's authored audio direction
      * procedural on-screen-text -> ``None`` (FFmpeg draws it, not an AI model)
    """
    if scenes_by_id is None:
        return None
    if asset_ref.endswith("-onscreen-text"):
        return None

    if asset_ref == "voice-track":
        spoken = [
            str(scene.get("spoken_content", "")).strip()
            for scene in scenes_by_id.values()
        ]
        joined = " ".join(chunk for chunk in spoken if chunk)
        return joined or None

    if asset_ref == "music-bed":
        for scene in scenes_by_id.values():
            direction = str(scene.get("audio_direction", "")).strip()
            if direction:
                return direction
        return None

    if media_type == "image" and asset_ref.endswith("-background"):
        bg_scene = scenes_by_id.get(asset_ref[: -len("-background")])
        if not bg_scene:
            return None
        concept = str(bg_scene.get("visual_concept", "")).strip()
        metaphor = str(bg_scene.get("semantic_metaphor", "")).strip()
        composition = str(bg_scene.get("composition", "")).strip()
        parts = [p for p in (concept, metaphor, composition) if p]
        if not parts:
            return None
        return ". ".join(parts)

    return None


def _job_for_asset(
    asset: dict[str, Any],
    index: int,
    scenes_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build one generation job from one planned asset."""
    asset_ref = asset.get("asset_ref", f"asset-{index:02d}")
    strategy = asset.get("source_strategy", "ai_image")
    model = asset.get("model_choice", "SDXL")
    cost = float(asset.get("estimated_cost_usd", 0.0))
    cloud_or_local = "cloud" if strategy in _CLOUD_STRATEGIES else "local"
    media_type = asset.get("media_type", "image")

    # On-screen procedural text depends on its scene background existing first
    # (it is composited over it). Derive the sibling background ref by name.
    depends_on: list[str] = []
    if asset_ref.endswith("-onscreen-text"):
        depends_on.append(asset_ref.replace("-onscreen-text", "-background"))

    params: dict[str, Any] = {
        "source_strategy": strategy,
        "media_type": media_type,
    }
    # Thread a real screenplay-derived prompt when a screenplay is in scope
    # (G26). Absent screenplay/scene/field -> no key -> dispatcher falls back to
    # the asset ref, keeping the pre-P11a plan byte-identical (ASUR-VERSION-01).
    prompt = _prompt_for_asset(asset_ref, media_type, scenes_by_id)
    if prompt is not None:
        params["prompt"] = prompt

    return {
        "job_id": f"job-{index:02d}-{asset_ref}",
        "target_asset": asset_ref,
        "model": model,
        "params": params,
        "depends_on": depends_on,
        "cost_estimate_usd": cost,
        "cloud_or_local": cloud_or_local,
    }


def build_generation_plan(
    asset_plan_artifact: Artifact,
    project_id: str,
    *,
    visual_screenplay_artifact: Artifact | None = None,
    identity: Identity | None = None,
) -> Artifact:
    """Produce a ``generation_plan`` artifact from the asset plan.

    One ordered job per planned asset. Deterministic ordering: non-dependent
    jobs (backgrounds, voice, music) keep their plan order first, then jobs with
    ``depends_on`` follow. All locked-stack jobs run locally at zero cost.

    When ``visual_screenplay_artifact`` is supplied, each AI job gains a real
    ``params['prompt']`` derived from its owning scene (SPEC-GAP G26). Omitting
    it keeps the pre-P11a plan byte-identical (ASUR-VERSION-01).
    """
    ap_body = asset_plan_artifact.body or {}
    subject = ap_body.get("subject", "the topic")
    assets = ap_body.get("assets") or []

    scenes_by_id: dict[str, dict[str, Any]] | None = None
    if visual_screenplay_artifact is not None:
        sp_body = visual_screenplay_artifact.body or {}
        scenes_by_id = {
            str(scene.get("scene_id", "")): scene
            for scene in (sp_body.get("scenes") or [])
        }

    numbered = [
        _job_for_asset(asset, i, scenes_by_id) for i, asset in enumerate(assets)
    ]
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
