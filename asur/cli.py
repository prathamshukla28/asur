"""asur - local, key-free command-line front door.

Phase 1 ships one subcommand, ``asur script``, which turns a one-line idea
into a full, scored, structured script - 100% locally, with no network and no
keys (ASUR-LOCAL-01). Every stage writes a versioned, checksummed artifact into
the project's ``.script/`` workspace (ASUR-VERSION-01), carries lineage back to
the stages before it (ASUR-PROV-01), and explains itself as it goes
(ASUR-EXPLAIN-01). The run ends at a fail-closed 13-check quality gate
(ASUR-GATE-01): exit code 0 means the script cleared the quality floor, non-zero
means it was held for revision.

    asur script --idea "why most people waste money on AI tools" --project .

Usage is deliberately plain so a non-expert can read the output top to bottom.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core.gate import SHIP, HOLD
from .core.identity import get_identity
from .core.workspace import Workspace, WorkspaceError
from .orchestrator import Orchestrator
from .script.idea import build_idea
from .script.research import build_research
from .script.audience import build_audience
from .script.strategy import build_strategy
from .script.hooks import build_hooks
from .script.hook_memory import HookMemory
from .script.script_builder import build_script
from .script.quality_gate import build_qa_report


def _derive_project_id(project_root: Path, explicit: str | None) -> str:
    """Project id from --project-id, else the project directory name."""
    if explicit:
        return explicit.strip()
    name = project_root.name.strip()
    return name or "asur-project"


def _emit(line: str = "") -> None:
    """Print one plain line of progress (kept simple for non-expert users)."""
    print(line)


def _emit_stage(ws: Workspace, artifact, note: str) -> None:
    """Save a stage artifact and report what it produced in one line."""
    ws.save_artifact(artifact)
    _emit(
        f"  [{artifact.version:>2}] {artifact.kind:<9} {artifact.artifact_id}"
        f"  - {note}"
    )


def _run_script(args: argparse.Namespace) -> int:
    idea_text = (args.idea or "").strip()
    if not idea_text:
        _emit("error: --idea must not be empty")
        return 2

    project_root = Path(args.project).expanduser().resolve()
    if not project_root.exists():
        _emit(f"error: project directory does not exist: {project_root}")
        return 2
    if not project_root.is_dir():
        _emit(f"error: --project is not a directory: {project_root}")
        return 2

    project_id = _derive_project_id(project_root, args.project_id)
    identity = get_identity()

    try:
        ws = Workspace(project_root, project_id).ensure()
    except WorkspaceError as exc:
        _emit(f"error: could not open workspace: {exc}")
        return 2

    _emit(f"ASUR SCRIPT - Phase 1 (intelligence)")
    _emit(f"  project : {project_id}")
    _emit(f"  root    : {project_root / '.script'}")
    _emit(f"  creator : {identity.principal()}")
    _emit(f"  idea    : {idea_text}")
    _emit()
    _emit("Building (each line is a versioned, checksummed artifact):")

    try:
        idea = build_idea(
            idea_text,
            project_id,
            platform=args.platform,
            language=args.language,
            identity=identity,
        )
        _emit_stage(ws, idea, "understood the idea (what/who/why/problem/emotion/action)")

        research = build_research(idea, project_id, identity=identity)
        _emit_stage(ws, research, "angles, supporting points, risks (evidence-classed)")

        audience = build_audience(idea, research, project_id, identity=identity)
        _emit_stage(ws, audience, "pains, desires, objections, awareness level")

        strategy = build_strategy(idea, audience, project_id, identity=identity)
        _emit_stage(ws, strategy, "objective, single promise, narrative, CTA, success metric")

        memory = HookMemory(project_root).ensure()
        prior_hooks = memory.prior_hook_texts()
        hooks = build_hooks(
            strategy, project_id, identity=identity, prior_hooks=prior_hooks
        )
        hook_count = len(hooks.body.get("hooks", []))
        _emit_stage(
            ws,
            hooks,
            f"{hook_count} hooks scored on 15 dimensions, best one selected"
            f" (compared against {len(prior_hooks)} remembered)",
        )
        recorded = memory.record_many(
            hooks.body.get("hooks", []),
            event="generated",
            project_id=project_id,
            identity=identity,
        )
        _emit(f"       hook memory: recorded {recorded} hooks (append-only)")

        script = build_script(strategy, hooks, project_id, identity=identity)
        section_count = len(script.body.get("sections", {}))
        _emit_stage(ws, script, f"structured script: {section_count} sections + pattern interrupts")

        qa, result = build_qa_report(
            script,
            project_id,
            hooks_artifact=hooks,
            strategy_artifact=strategy,
            identity=identity,
        )
        _emit_stage(ws, qa, f"13-check quality gate -> {result.disposition}")
    except WorkspaceError as exc:
        _emit()
        _emit(f"error: workspace refused a write (fail-closed): {exc}")
        return 2
    except ValueError as exc:
        _emit()
        _emit(f"error: a stage rejected its input: {exc}")
        return 2

    _emit()
    _emit("Quality gate:")
    _emit(f"  disposition : {result.disposition}"
          + (f" ({result.substate})" if result.substate else ""))
    _emit(f"  passed      : {'yes' if result.passed else 'no'}")
    if result.reasons:
        _emit("  notes:")
        for reason in result.reasons:
            _emit(f"    - {reason}")

    _emit()
    if result.disposition == SHIP:
        _emit("Result: script cleared the quality floor. Ready for the next phase (GENERATION).")
        return 0

    _emit("Result: script was HELD for revision - it did not clear the quality floor.")
    _emit("Nothing was overwritten; revise and re-run to produce a new version.")
    return 1


def _resolve_project(args: argparse.Namespace) -> tuple[Path, str] | int:
    """Resolve + validate --project (fail closed, exit 2 if missing/not a dir)."""
    project_root = Path(args.project).expanduser().resolve()
    if not project_root.exists():
        _emit(f"error: project directory does not exist: {project_root}")
        return 2
    if not project_root.is_dir():
        _emit(f"error: --project is not a directory: {project_root}")
        return 2
    return project_root, _derive_project_id(project_root, args.project_id)


def _run_run(args: argparse.Namespace) -> int:
    """Drive the orchestrator forward through the states that exist today.

    Phase 2 ships the state-machine runtime and orchestrator only. SCRIPT is
    built; GENERATION / VIRAL CHECK / EDITING / LEARNING are not. So `run`
    honestly advances only as far as the built instruments allow, then HOLDs
    fail-closed (ASUR-GATE-01) at the first gate it cannot clear. It never
    fakes work it cannot do (anti-hallucination, AGENTS.md section 7).
    """
    resolved = _resolve_project(args)
    if isinstance(resolved, int):
        return resolved
    project_root, project_id = resolved
    identity = get_identity()

    try:
        orch = Orchestrator(project_root, args.run_id, identity=identity)
    except (WorkspaceError, ValueError) as exc:
        _emit(f"error: could not start run: {exc}")
        return 2

    _emit("ASUR RUN - Phase 2 (controller)")
    _emit(f"  project : {project_id}")
    _emit(f"  run id  : {args.run_id}")
    _emit(f"  creator : {identity.principal()}")
    _emit(f"  state   : {orch.state}")
    _emit()
    _emit("The orchestrator carries only control tokens (state/gate/disposition);")
    _emit("it never carries findings, criteria, or targets (ASUR-FIREWALL-01).")
    _emit()

    # The first real gate past DRAFT (INPUTS_VERIFIED) needs inputs that are
    # supplied by the SCRIPT phase / a human. With no checks wired for it here,
    # the gate fails closed to HOLD:NO_CHECKS - which is the honest answer.
    step = orch.step(checks=[])
    _emit("Attempted one forward step:")
    _emit(f"  from        : {step.from_state}")
    _emit(f"  toward      : {step.to_state}")
    _emit(f"  disposition : {step.result.disposition}"
          + (f" ({step.result.substate})" if step.result.substate else ""))
    _emit(f"  advanced    : {'yes' if step.advanced else 'no'}")
    _emit()
    if step.advanced:
        _emit(f"Result: advanced to {orch.state}. Run log: .asur/runs/{args.run_id}.jsonl")
        return 0
    _emit("Result: HELD fail-closed. Later phases wire the gate checks that let a run")
    _emit("advance past this point. Run log: .asur/runs/" + f"{args.run_id}.jsonl")
    return 1


def _run_not_yet(verb: str, instrument: str, phase: str) -> int:
    """Honest placeholder for a verb whose instrument is not built yet.

    Fail-closed + anti-hallucination (AGENTS.md section 7): report the gap, do
    not pretend the instrument ran. Exit 1 = HELD (missing, not broken).
    """
    _emit(f"ASUR {verb.upper()}")
    _emit(f"  disposition : {HOLD} (INSTRUMENT_NOT_AVAILABLE)")
    _emit()
    _emit(f"The {instrument} instrument is not built yet - it lands in {phase}.")
    _emit(f"'asur {verb}' is reserved and fails closed rather than faking work.")
    return 1


def _run_generate(args: argparse.Namespace) -> int:
    resolved = _resolve_project(args)
    if isinstance(resolved, int):
        return resolved
    return _run_not_yet("generate", "GENERATION", "Phase 4 (hero proof) onward")


def _run_viral_check(args: argparse.Namespace) -> int:
    resolved = _resolve_project(args)
    if isinstance(resolved, int):
        return resolved
    return _run_not_yet("viral-check", "VIRAL CHECK", "Phase 7")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="asur",
        description="ASUR - local, key-free AI content creation OS (Phase 1: SCRIPT).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    script_p = sub.add_parser(
        "script",
        help="Turn a one-line idea into a full, scored, structured script (local).",
    )
    script_p.add_argument(
        "--idea",
        required=True,
        help="One-line content idea, e.g. 'why most people waste money on AI tools'.",
    )
    script_p.add_argument(
        "--project",
        default=".",
        help="Project directory (holds the .script/ workspace). Default: current dir.",
    )
    script_p.add_argument(
        "--project-id",
        default=None,
        help="Explicit project id. Default: the project directory name.",
    )
    script_p.add_argument(
        "--language",
        default="en",
        help="Primary language for hooks and script (en|hi|hinglish|indian-en|mr). Default: en.",
    )
    script_p.add_argument(
        "--platform",
        default="instagram_reels",
        help="Target platform. Default: instagram_reels.",
    )
    script_p.set_defaults(func=_run_script)

    run_p = sub.add_parser(
        "run",
        help="Drive the orchestrator forward through the states built so far (local).",
    )
    run_p.add_argument("--project", default=".", help="Project directory. Default: current dir.")
    run_p.add_argument("--project-id", default=None, help="Explicit project id. Default: dir name.")
    run_p.add_argument("--run-id", default="run-1", help="Run identifier for the run log. Default: run-1.")
    run_p.set_defaults(func=_run_run)

    gen_p = sub.add_parser(
        "generate",
        help="(Reserved) GENERATION instrument - not built until a later phase.",
    )
    gen_p.add_argument("--project", default=".", help="Project directory. Default: current dir.")
    gen_p.add_argument("--project-id", default=None, help="Explicit project id. Default: dir name.")
    gen_p.set_defaults(func=_run_generate)

    vc_p = sub.add_parser(
        "viral-check",
        help="(Reserved) VIRAL CHECK instrument - not built until a later phase.",
    )
    vc_p.add_argument("--project", default=".", help="Project directory. Default: current dir.")
    vc_p.add_argument("--project-id", default=None, help="Explicit project id. Default: dir name.")
    vc_p.set_defaults(func=_run_viral_check)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
