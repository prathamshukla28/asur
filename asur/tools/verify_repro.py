"""``asur verify-repro`` - prove the SCRIPT chain reproduces byte-for-byte.

ASUR-VERSION-01 and ASUR-HONEST-01 claim "same inputs -> same checksums". This
tool makes that a checkable guarantee rather than a promise. For each stored
SCRIPT stage it rebuilds the artifact *from its on-disk upstream artifacts* -
the exact inputs the stage ran on - recomputes the body checksum, and compares
it to the checksum stored on disk.

A match proves the stage is deterministic and the stored body was not altered
out from under its checksum. A mismatch FAILS CLOSED (ASUR-GATE-01): it means
either the stage is non-deterministic or a stored artifact was tampered with -
both of which a creator must know about before trusting the lineage.

Pure, local, stdlib only; no network (ASUR-LOCAL-01). It only rebuilds and
compares - it never writes a new artifact into the workspace.
"""

from __future__ import annotations

from typing import Any

from ..core.envelope import Artifact
from ..core.gate import HOLD, SHIP
from ..core.workspace import Workspace
from ..script.audience import build_audience
from ..script.hook_memory import HookMemory
from ..script.hooks import build_hooks
from ..script.idea import build_idea
from ..script.quality_gate import build_qa_report
from ..script.research import build_research
from ..script.script_builder import build_script
from ..script.strategy import build_strategy

__all__ = ["REBUILDABLE", "verify_reproducible"]

# The kinds verify-repro can rebuild as a pure function of on-disk upstream
# artifacts, using stdlib-only builders. SCRIPT plus the GENERATION/EDITING
# PLANNING stages (all deterministic control-data transforms). Deliberately
# excluded: ``render`` (needs the media path), ``viral_check`` (its input is a
# computed VIRAL_VIEW, not a stored artifact), ``publish_package`` (needs
# human-supplied title/caption), ``performance`` (human-entered input), and
# ``learning`` (folds performance). Those present stages are reported as skipped
# with an honest reason rather than claimed reproduced (ASUR-HONEST-01).
REBUILDABLE = (
    "idea",
    "research",
    "audience",
    "strategy",
    "hooks",
    "script",
    "qa_report",
    "creative_direction",
    "visual_screenplay",
    "asset_plan",
    "generation_plan",
    "edit_plan",
)


def _rebuild(
    kind: str,
    stored: dict[str, Artifact],
    project_id: str,
    prior_hooks: list[str],
) -> Artifact | None:
    """Rebuild one stage from the stored upstream artifacts it depends on.

    Returns the freshly built artifact, or None if a required upstream artifact
    is not present on disk (so the stage cannot be rebuilt to compare).
    """
    idea = stored.get("idea")
    research = stored.get("research")
    audience = stored.get("audience")
    strategy = stored.get("strategy")
    hooks = stored.get("hooks")
    script = stored.get("script")

    if kind == "idea" and idea is not None:
        body = idea.body or {}
        return build_idea(
            body.get("one_line", ""),
            project_id,
            platform=body.get("platform", "instagram_reels"),
            language=body.get("language", "en"),
            takeaway=body.get("creator_takeaway"),
        )
    if kind == "research" and idea is not None:
        return build_research(idea, project_id)
    if kind == "audience" and idea is not None and research is not None:
        return build_audience(idea, research, project_id)
    if kind == "strategy" and idea is not None and audience is not None:
        return build_strategy(idea, audience, project_id)
    if kind == "hooks" and strategy is not None:
        return build_hooks(strategy, project_id, prior_hooks=prior_hooks)
    if kind == "script" and strategy is not None and hooks is not None:
        return build_script(strategy, hooks, project_id)
    if kind == "qa_report" and script is not None:
        qa, _result = build_qa_report(
            script,
            project_id,
            hooks_artifact=hooks,
            strategy_artifact=strategy,
        )
        return qa

    # GENERATION / EDITING planning stages (deterministic, stdlib-only).
    direction = stored.get("creative_direction")
    screenplay = stored.get("visual_screenplay")
    asset_plan = stored.get("asset_plan")
    gen_plan = stored.get("generation_plan")

    if kind == "creative_direction" and strategy is not None and script is not None:
        from ..generation.creative_direction import build_creative_direction
        return build_creative_direction(strategy, script, project_id)
    if kind == "visual_screenplay" and direction is not None and script is not None:
        from ..generation.visual_screenplay import build_visual_screenplay
        return build_visual_screenplay(direction, script, project_id)
    if kind == "asset_plan" and screenplay is not None:
        from ..generation.asset_strategy import build_asset_plan
        return build_asset_plan(screenplay, project_id)
    if kind == "generation_plan" and asset_plan is not None:
        from ..generation.generation_plan import build_generation_plan
        return build_generation_plan(
            asset_plan, project_id, visual_screenplay_artifact=screenplay
        )
    if kind == "edit_plan" and gen_plan is not None and screenplay is not None:
        timing = (stored["edit_plan"].body or {}).get("timing") or {}
        if timing.get("source") == "measured_narration":
            # Timed from measured speech: rebuild from the upstream plan plus the
            # recorded measurements (the speech itself is engine output).
            from ..editing.narration_timing import timed_edit_plan
            return timed_edit_plan(
                gen_plan, screenplay, project_id, list(timing.get("speech_s") or []),
                engine=str(timing.get("engine", "")),
            )
        from ..editing.timeline import (
            build_edit_plan,
            build_timeline_from_generation_plan,
        )
        timeline = build_timeline_from_generation_plan(gen_plan, screenplay, project_id)
        return build_edit_plan(timeline, gen_plan, project_id)
    return None


def _check_hooks(
    stored: dict[str, Artifact],
    project_id: str,
    prior_hooks: list[str],
) -> dict[str, Any]:
    """Hooks reproduction, accounting for memory not captured in the body.

    The ``prior_hooks`` a run saw are an input to the hooks stage but are NOT
    recorded in the hooks body, so an exact rebuild depends on hook-memory
    state. We try the current memory first, then an empty prior set (a first
    run), and report a match if either reproduces the stored checksum. Honest
    either way: a genuine mismatch is still reported as a mismatch, with the
    caveat recorded so nothing is silently rubber-stamped (ASUR-HONEST-01).
    """
    strategy = stored.get("strategy")
    stored_hooks = stored.get("hooks")
    assert strategy is not None and stored_hooks is not None  # guarded by caller
    caveat = (
        "hook reproduction depends on hook-memory state, which is not captured "
        "in the hooks body; tried current memory then an empty prior set"
    )
    for candidate in (prior_hooks, []):
        rebuilt = build_hooks(strategy, project_id, prior_hooks=candidate)
        if rebuilt.checksum == stored_hooks.checksum:
            return {
                "kind": "hooks",
                "stored_checksum": stored_hooks.checksum,
                "rebuilt_checksum": rebuilt.checksum,
                "match": True,
                "note": caveat,
            }
    return {
        "kind": "hooks",
        "stored_checksum": stored_hooks.checksum,
        "rebuilt_checksum": rebuilt.checksum,
        "match": False,
        "note": caveat,
    }


def verify_reproducible(workspace: Workspace) -> dict[str, Any]:
    """Rebuild every stored SCRIPT stage and compare checksums.

    Returns a plain dict: a per-stage list of {kind, stored_checksum,
    rebuilt_checksum, match, note}, whether every present stage reproduced, and
    a fail-closed disposition (SHIP only if all present stages matched and the
    chain has at least an idea to verify).
    """
    from .explain import FULL_CHAIN  # local import avoids a cycle at import time

    stored: dict[str, Artifact] = {}
    for kind in FULL_CHAIN:
        artifact = workspace.load_latest(kind)
        if artifact is not None:
            stored[kind] = artifact

    prior_hooks = HookMemory(workspace.project_root).prior_hook_texts()
    project_id = workspace.project_id

    stages: list[dict[str, Any]] = []
    for kind in FULL_CHAIN:
        if kind not in stored:
            continue
        if kind not in REBUILDABLE:
            # Present but not a deterministic stdlib rebuild (render/eval/human
            # input): report it honestly, exclude it from the verdict.
            stages.append(
                {
                    "kind": kind,
                    "stored_checksum": stored[kind].checksum,
                    "rebuilt_checksum": None,
                    "match": None,
                    "note": "skipped: not a deterministic stdlib rebuild target",
                }
            )
            continue
        generator = str((stored[kind].body or {}).get("generator", "template"))
        if "llm:" in generator:
            # An LLM draft cannot be rebuilt byte-for-byte offline; say so.
            stages.append(
                {
                    "kind": kind,
                    "stored_checksum": stored[kind].checksum,
                    "rebuilt_checksum": None,
                    "match": None,
                    "note": f"skipped: drafted by {generator} (not deterministically rebuildable)",
                }
            )
            continue
        if kind == "hooks":
            stages.append(_check_hooks(stored, project_id, prior_hooks))
            continue
        rebuilt = _rebuild(kind, stored, project_id, prior_hooks)
        if rebuilt is None:
            # A present stage whose upstream is missing cannot be verified;
            # fail closed rather than claim it reproduced.
            stages.append(
                {
                    "kind": kind,
                    "stored_checksum": stored[kind].checksum,
                    "rebuilt_checksum": None,
                    "match": False,
                    "note": "upstream artifact missing; cannot rebuild to compare",
                }
            )
            continue
        stages.append(
            {
                "kind": kind,
                "stored_checksum": stored[kind].checksum,
                "rebuilt_checksum": rebuilt.checksum,
                "match": rebuilt.checksum == stored[kind].checksum,
                "note": "rebuilt from on-disk upstream artifact(s)",
            }
        )

    # The verdict is computed over the VERIFIABLE stages only (match is True or
    # False). Skipped stages (match is None) are reported but never counted - we
    # never claim reproducibility for something we did not rebuild.
    verifiable = [s for s in stages if s["match"] is not None]
    reproducible = bool(verifiable) and all(s["match"] for s in verifiable)
    disposition = SHIP if (reproducible and "idea" in stored) else HOLD

    return {
        "project_id": project_id,
        "stages": stages,
        "reproducible": reproducible,
        "disposition": disposition,
    }
