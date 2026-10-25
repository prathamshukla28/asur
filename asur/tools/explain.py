"""``asur explain`` - a read-only decision trail over the SCRIPT workspace.

ASUR-EXPLAIN-01 says every important decision (why this hook, why this verdict,
why this cut) is explainable with a recorded reason. Those reasons already live
in each artifact's body; they are just scattered across versioned files. This
tool walks the stored SCRIPT artifacts in lineage order and surfaces, for each
one, its provenance (kind, version, id, checksum, status, upstream sources) and
the recorded "why" it carries - turning an invariant ASUR *enforces* into
something a human can *read*.

It only ever READS. It never writes and never touches the network
(ASUR-LOCAL-01). It walks the whole pipeline lineage (SCRIPT through LEARNING),
including the recorded viral verdict. That is not a firewall breach: explain is
a human-facing view of the human's OWN workspace (ASUR-HUMAN-01 - humans own all
sides and all history), not a channel that feeds one lane another lane's
playbook. The firewall (ASUR-FIREWALL-01) governs the GENERATION <-> VIRAL CHECK
hand-off via SCRIPT's projections; a person reading their own finished artifacts
is outside it.
"""

from __future__ import annotations

from typing import Any

from ..core.workspace import Workspace

__all__ = ["FULL_CHAIN", "SCRIPT_CHAIN", "build_explanation"]

# The SCRIPT lineage, in the order the stages run.
SCRIPT_CHAIN = (
    "idea",
    "research",
    "audience",
    "strategy",
    "hooks",
    "script",
    "qa_report",
)

# The full pipeline lineage, SCRIPT through LEARNING, in the order the stages
# run. ``explain`` walks these and reports each one present in the workspace, so
# the decision trail covers the whole pipeline - not just SCRIPT. explain is a
# human-facing, read-only view of the human's own workspace (ASUR-HUMAN-01 -
# humans own all sides and all history); it is not a cross-lane channel, so
# surfacing a recorded viral verdict here is not a firewall hand-off.
FULL_CHAIN = (
    *SCRIPT_CHAIN,
    "creative_direction",
    "visual_screenplay",
    "asset_plan",
    "generation_plan",
    "edit_plan",
    "render",
    "viral_check",
    "publish_package",
    "performance",
    "learning",
)

# Top-level body keys that, by convention across the SCRIPT stages, hold a
# recorded, human-readable reason. Only surfaced when present and non-empty, so
# this never invents an explanation that the artifact did not record.
_WHY_KEYS = ("selection_reason", "method", "note")


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _collect_reasons(body: Any) -> list[str]:
    """Pull the recorded reasons out of one artifact body.

    Honest by construction: it only reports strings the stage actually wrote.
    It reads the conventional ``_WHY_KEYS`` plus any ``{value, how_derived}``
    sub-block (the shape idea/audience/strategy use to explain a derived value).
    """
    reasons: list[str] = []
    if not isinstance(body, dict):
        return reasons

    for key in _WHY_KEYS:
        text = _text(body.get(key))
        if text:
            reasons.append(f"{key}: {text}")

    # Nested "{value, how_derived}" explanations (idea/audience/strategy fields).
    for field, value in body.items():
        if isinstance(value, dict):
            how = _text(value.get("how_derived"))
            if how:
                reasons.append(f"{field}: {how}")

    # The quality gate records its reasons as a plain list of strings.
    gate_reasons = body.get("reasons")
    if isinstance(gate_reasons, list):
        reasons.extend(_text(r) for r in gate_reasons if _text(r))

    return reasons


def _headline(kind: str, body: Any) -> str:
    """One-line summary of what this stage decided (recorded facts only)."""
    if not isinstance(body, dict):
        return ""
    if kind == "idea":
        return f'understood the idea: "{_text(body.get("one_line"))}"'
    if kind == "research":
        angles = body.get("angles") or []
        risks = body.get("risks") or []
        return f"{len(angles)} angles, {len(risks)} risks (evidence-classed)"
    if kind == "audience":
        return f"awareness level: {_text(body.get('awareness_level')) or 'recorded'}"
    if kind == "strategy":
        objective = body.get("objective")
        if isinstance(objective, dict):
            return f"objective: {_text(objective.get('value'))}"
        return "strategy recorded"
    if kind == "hooks":
        count = body.get("count", len(body.get("hooks", []) or []))
        return f"{count} hooks scored; selected {_text(body.get('selected_hook_id'))}"
    if kind == "script":
        sections = body.get("sections") or {}
        return (
            f"{len(sections)} sections, "
            f"~{body.get('estimated_duration_s', '?')}s"
        )
    if kind == "qa_report":
        substate = _text(body.get("substate"))
        tail = f" ({substate})" if substate else ""
        return (
            f"quality gate {_text(body.get('disposition')) or 'recorded'}{tail}, "
            f"passed={body.get('passed')}"
        )
    if kind == "creative_direction":
        return "creative direction recorded"
    if kind == "visual_screenplay":
        scenes = body.get("scenes") or []
        return f"{len(scenes)} scenes blocked out" if scenes else "screenplay recorded"
    if kind in ("asset_plan", "generation_plan"):
        jobs = body.get("jobs") or body.get("assets") or []
        return f"{len(jobs)} items planned" if jobs else f"{kind} recorded"
    if kind == "edit_plan":
        return "timeline assembled into an edit plan"
    if kind == "render":
        prov = body.get("provenance") or {}
        res = _text(prov.get("resolution"))
        return f"rendered {res}" if res else "rendered"
    if kind == "viral_check":
        return f"verdict: {_text(body.get('verdict')) or 'recorded'}"
    if kind == "publish_package":
        return "publish package assembled (never auto-posted)"
    if kind == "performance":
        metrics = body.get("metrics") or {}
        return f"measured: {metrics.get('views', '?')} views" if metrics else "performance recorded"
    if kind == "learning":
        diff = body.get("difference") or {}
        return f"prediction vs reality: {_text(diff.get('direction')) or 'recorded'}"
    return ""


def _selected_hook_text(body: Any) -> str:
    """The text of the hook the hooks stage actually selected, if recorded."""
    if not isinstance(body, dict):
        return ""
    selected = body.get("selected_hook_id")
    for hook in body.get("hooks", []) or []:
        if isinstance(hook, dict) and hook.get("hook_id") == selected:
            meta = hook.get("metadata") or {}
            return _text(meta.get("hook"))
    return ""


def build_explanation(workspace: Workspace) -> dict[str, Any]:
    """Walk the SCRIPT chain and return its explainable decision trail.

    Pure and read-only: it loads the latest artifact of each SCRIPT kind, reads
    the reasons recorded in its body, and reports provenance alongside. Returns
    a plain dict so the CLI can format it and tests can assert on it.
    """
    entries: list[dict[str, Any]] = []
    missing: list[str] = []

    for kind in FULL_CHAIN:
        artifact = workspace.load_latest(kind)
        if artifact is None:
            missing.append(kind)
            continue
        entry: dict[str, Any] = {
            "kind": artifact.kind,
            "version": artifact.version,
            "artifact_id": artifact.artifact_id,
            "checksum": artifact.checksum,
            "status": artifact.status,
            "sources": [s.get("artifact_id") for s in artifact.sources],
            "headline": _headline(artifact.kind, artifact.body),
            "reasons": _collect_reasons(artifact.body),
        }
        if artifact.kind == "hooks":
            selected = _selected_hook_text(artifact.body)
            if selected:
                entry["selected_hook"] = selected
        entries.append(entry)

    return {
        "project_id": workspace.project_id,
        "entries": entries,
        "missing": missing,
        "complete": not missing,
    }
