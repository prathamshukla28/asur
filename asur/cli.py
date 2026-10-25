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

from .core.gate import HOLD, SHIP
from .core.identity import get_identity
from .core.media_workspace import MediaWorkspace
from .core.workspace import Workspace, WorkspaceError
from .orchestrator import Orchestrator
from .script.audience import build_audience
from .script.hook_memory import HookMemory
from .script.hooks import build_hooks
from .script.idea import build_idea
from .script.quality_gate import build_qa_report
from .script.research import build_research
from .script.script_builder import build_script
from .script.strategy import build_strategy


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

    _emit("ASUR SCRIPT - Phase 1 (intelligence)")
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


def _run_render(args: argparse.Namespace) -> int:
    """Render an approved edit plan into a real, browsable, ready-to-upload package.

    Loads the latest edit_plan + viral_check artifacts, renders a real
    platform-sized MP4 (FFmpeg, the LOCKED renderer), assembles the publish
    package, and writes the DATA_MODELS file set into a browsable
    ``youtube/<project_id>/package/`` folder. It STOPS at the publish human
    gate (stage 25, ASUR-HUMAN-01): it produces files on disk, it never posts.
    Missing inputs or a missing FFmpeg binary fail closed to HOLD (ASUR-GATE-01).
    """
    # Imported here (not at module load) so the stdlib-only front door stays
    # importable without the generation media path on the import graph.
    from .generation.render import RenderError, build_final_render
    from .learning.publish_package import build_publish_package, materialize_package

    resolved = _resolve_project(args)
    if isinstance(resolved, int):
        return resolved
    project_root, project_id = resolved
    identity = get_identity()

    try:
        ws = Workspace(project_root, project_id).ensure()
    except WorkspaceError as exc:
        _emit(f"error: could not open workspace: {exc}")
        return 2

    edit_plan = ws.load_latest("edit_plan")
    viral_check = ws.load_latest("viral_check")

    _emit("ASUR RENDER - real local render + ready-to-upload package")
    _emit(f"  project  : {project_id}")
    _emit(f"  platform : {args.platform}")
    _emit(f"  creator  : {identity.principal()}")
    _emit()

    if edit_plan is None:
        _emit(f"  disposition : {HOLD} (NO_EDIT_PLAN)")
        _emit()
        _emit("No approved edit_plan artifact found in this project's workspace.")
        _emit("Build the pipeline through EDITING first; render fails closed.")
        return 1
    if viral_check is None:
        _emit(f"  disposition : {HOLD} (NO_VIRAL_CHECK)")
        _emit()
        _emit("No viral_check artifact found in this project's workspace.")
        _emit("The viral check must run before a package is assembled; fails closed.")
        return 1

    subject = str(edit_plan.body.get("subject", "") or project_id)
    render_dir = MediaWorkspace(project_root, project_id).ensure().base / "render"
    try:
        render = build_final_render(
            edit_plan,
            project_id,
            platform=args.platform,
            out_root=str(render_dir),
            identity=identity,
        )
        _emit_stage(ws, render, f"rendered real MP4 ({render.body['provenance']['resolution']})")

        publish = build_publish_package(
            edit_plan,
            viral_check,
            project_id,
            title=subject,
            caption=subject,
            platform=args.platform,
            identity=identity,
        )
        _emit_stage(ws, publish, "assembled publish package (metadata only)")

        package = materialize_package(
            publish,
            render,
            project_id,
            out_root=project_root,
            identity=identity,
        )
    except RenderError as exc:
        _emit()
        _emit(f"  disposition : {HOLD} (RENDER_UNAVAILABLE)")
        _emit(f"  reason      : {exc}")
        _emit()
        _emit("Render failed closed - no partial package was written.")
        return 1
    except WorkspaceError as exc:
        _emit()
        _emit(f"error: workspace refused a write (fail-closed): {exc}")
        return 2
    except ValueError as exc:
        _emit()
        _emit(f"error: a stage rejected its input: {exc}")
        return 2

    _emit()
    _emit("Ready-to-upload package written (browsable on disk):")
    _emit(f"  folder : {package['folder']}")
    for path in package["files"]:
        _emit(f"    - {path.name}")
    _emit()
    _emit("Result: files are ready. ASUR never posts - a human uploads them")
    _emit("(publish is human gate stage 25, ASUR-HUMAN-01).")
    return 0


def _run_explain(args: argparse.Namespace) -> int:
    """Print the explainable decision trail for a project's SCRIPT artifacts.

    Read-only (ASUR-EXPLAIN-01): it walks the versioned pipeline artifacts
    (SCRIPT through LEARNING) and surfaces, for each, its provenance (version,
    id, checksum, lineage) and the reasons it recorded. It never writes and is a
    human-facing view of the human's own workspace, not a cross-lane channel, so
    it is outside the GENERATION <-> VIRAL CHECK firewall (ASUR-HUMAN-01). Exit 0
    if the full chain is present, 1 if some stages are not produced yet (fail
    closed).
    """
    from .tools.explain import build_explanation

    resolved = _resolve_project(args)
    if isinstance(resolved, int):
        return resolved
    project_root, project_id = resolved

    try:
        ws = Workspace(project_root, project_id).ensure()
    except WorkspaceError as exc:
        _emit(f"error: could not open workspace: {exc}")
        return 2

    report = build_explanation(ws)

    _emit("ASUR EXPLAIN - why each SCRIPT decision was made (read-only)")
    _emit(f"  project : {project_id}")
    _emit(f"  root    : {project_root / '.script'}")
    _emit()

    if not report["entries"]:
        _emit("No SCRIPT artifacts found yet. Run `asur script --idea ...` first.")
        return 1

    for entry in report["entries"]:
        _emit(
            f"[{entry['version']:>2}] {entry['kind']:<9} {entry['artifact_id']}"
            f"  ({entry['status']})"
        )
        if entry["headline"]:
            _emit(f"     what : {entry['headline']}")
        if entry.get("selected_hook"):
            _emit(f"     hook : \"{entry['selected_hook']}\"")
        if entry["sources"]:
            _emit(f"     from : {', '.join(entry['sources'])}")
        _emit(f"     hash : {entry['checksum']}")
        for reason in entry["reasons"]:
            _emit(f"     why  : {reason}")
        _emit()

    if report["missing"]:
        _emit(f"Not produced yet: {', '.join(report['missing'])}")
        _emit("The trail is explainable as far as the pipeline has run (fail closed).")
        return 1

    _emit("Every SCRIPT stage is present and carries a recorded reason (ASUR-EXPLAIN-01).")
    return 0


def _run_verify_repro(args: argparse.Namespace) -> int:
    """Rebuild each stored SCRIPT stage and confirm byte-identical checksums.

    ASUR-VERSION-01 / ASUR-HONEST-01: proves "same inputs -> same checksums".
    Exit 0 only if every present stage reproduced; a mismatch fails closed
    (exit 1) because it means non-determinism or a tampered artifact.
    """
    from .tools.verify_repro import verify_reproducible

    resolved = _resolve_project(args)
    if isinstance(resolved, int):
        return resolved
    project_root, project_id = resolved

    try:
        ws = Workspace(project_root, project_id).ensure()
    except WorkspaceError as exc:
        _emit(f"error: could not open workspace: {exc}")
        return 2

    report = verify_reproducible(ws)

    _emit("ASUR VERIFY-REPRO - rebuild the SCRIPT chain, compare checksums")
    _emit(f"  project : {project_id}")
    _emit()

    if not report["stages"]:
        _emit("No SCRIPT artifacts found to verify. Run `asur script --idea ...` first.")
        return 1

    for stage in report["stages"]:
        if stage["match"] is None:
            mark = "skip"
        elif stage["match"]:
            mark = "ok  "
        else:
            mark = "DIFF"
        _emit(f"  [{mark}] {stage['kind']:<18} {stage['stored_checksum']}")
        if stage["match"] is None:
            _emit(f"         note    : {stage['note']}")
        elif not stage["match"]:
            _emit(f"         rebuilt -> {stage['rebuilt_checksum']}")
            _emit(f"         note    : {stage['note']}")

    _emit()
    if report["disposition"] == SHIP:
        _emit("Result: every stored SCRIPT stage reproduced byte-for-byte.")
        _emit("Same inputs produced the same checksums (ASUR-VERSION-01/HONEST-01).")
        return 0
    _emit(f"  disposition : {HOLD} (NOT_REPRODUCIBLE)")
    _emit("Result: at least one stage did not reproduce - fail closed. A mismatch")
    _emit("means the stage is non-deterministic or a stored artifact was altered.")
    return 1


def _run_insights(args: argparse.Namespace) -> int:
    """Show the learning loop made visible: what has worked for THIS creator.

    Read-only aggregation of the project's hook memory (ASUR-LOCAL-01). Every
    line is EMPIRICAL (this creator's own data) and there is no aggregate score
    or '% viral' (ASUR-HONEST-01). Exit 0 always (it is a report, not a gate);
    an empty memory is reported honestly, not as an error.
    """
    from .learning.insights import build_insights

    resolved = _resolve_project(args)
    if isinstance(resolved, int):
        return resolved
    project_root, project_id = resolved

    report = build_insights(project_root, project_id)
    totals = report["totals"]

    _emit("ASUR INSIGHTS - what has worked for you (EMPIRICAL, no score)")
    _emit(f"  project : {project_id}")
    _emit(
        f"  memory  : {totals['records']} hook record(s), "
        f"{totals['published']} published, "
        f"{totals['with_measured_performance']} with measured performance"
    )
    _emit()

    if report["by_direction"]:
        _emit("By hook direction:")
        for row in report["by_direction"]:
            avg = row["avg_completion"]
            avg_text = f"{avg}% avg completion" if avg is not None else "no measured result yet"
            _emit(
                f"  - {row['direction']:<14} seen {row['seen']}, "
                f"published {row['published']} ({avg_text})"
            )
        _emit()

    _emit("Learnings (this creator's own data):")
    for learning in report["learnings"]:
        _emit(f"  - {learning['text']}")
        if learning.get("basis"):
            _emit(f"      basis: {learning['basis']}")
    _emit()
    _emit(f"Next experiment: {report['next_experiment']}")
    return 0


def _run_ab_resolve(args: argparse.Namespace) -> int:
    """Resolve the hook A/B experiment from MEASURED performance (SPEC-GAP G2).

    Loads the latest hooks artifact + hook memory and declares a winner only
    when at least two variants carry a real measured result; otherwise it HOLDs
    (exit 1) rather than imply a winner it cannot measure (ASUR-HONEST-01).
    """
    from .learning.ab_resolution import resolve_ab_experiment
    from .script.hook_memory import HookMemory

    resolved = _resolve_project(args)
    if isinstance(resolved, int):
        return resolved
    project_root, project_id = resolved

    try:
        ws = Workspace(project_root, project_id).ensure()
    except WorkspaceError as exc:
        _emit(f"error: could not open workspace: {exc}")
        return 2

    hooks = ws.load_latest("hooks")
    if hooks is None:
        _emit(f"  disposition : {HOLD} (NO_HOOKS)")
        _emit("No hooks artifact found. Run `asur script --idea ...` first.")
        return 1

    report = resolve_ab_experiment(hooks, HookMemory(project_root).all_records())

    _emit("ASUR AB-RESOLVE - measured winner among hook variants")
    _emit(f"  project : {project_id}")
    _emit()
    for row in report["variants"]:
        comp = row["measured_completion"]
        comp_text = f"{comp}% completion" if comp is not None else "no measured result"
        _emit(f"  {row['variant']} ({row['direction']:<12}) {comp_text}")
        _emit(f"      \"{row['chosen_hook']}\"")
    _emit()

    if report["status"] == "resolved":
        win = report["winner"]
        _emit(
            f"Measured winner: variant {win['variant']} ({win['direction']}) "
            f"at {win['measured_completion']}% completion."
        )
        return 0
    _emit(f"  disposition : {HOLD} (INSUFFICIENT_DATA)")
    _emit(f"  reason      : {report['reason']}")
    return 1


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

    render_p = sub.add_parser(
        "render",
        help="Render an approved edit plan into a real MP4 + ready-to-upload package (local).",
    )
    render_p.add_argument("--project", default=".", help="Project directory. Default: current dir.")
    render_p.add_argument("--project-id", default=None, help="Explicit project id. Default: dir name.")
    render_p.add_argument(
        "--platform",
        default="instagram_reels",
        help="Target platform (instagram_reels|youtube_shorts|youtube_long). Default: instagram_reels.",
    )
    render_p.set_defaults(func=_run_render)

    explain_p = sub.add_parser(
        "explain",
        help="Show why each SCRIPT decision was made, with provenance (read-only).",
    )
    explain_p.add_argument("--project", default=".", help="Project directory. Default: current dir.")
    explain_p.add_argument("--project-id", default=None, help="Explicit project id. Default: dir name.")
    explain_p.set_defaults(func=_run_explain)

    verify_p = sub.add_parser(
        "verify-repro",
        help="Rebuild the SCRIPT chain and confirm byte-identical checksums (local).",
    )
    verify_p.add_argument("--project", default=".", help="Project directory. Default: current dir.")
    verify_p.add_argument("--project-id", default=None, help="Explicit project id. Default: dir name.")
    verify_p.set_defaults(func=_run_verify_repro)

    insights_p = sub.add_parser(
        "insights",
        help="Show what has worked for this creator from measured performance (read-only).",
    )
    insights_p.add_argument("--project", default=".", help="Project directory. Default: current dir.")
    insights_p.add_argument("--project-id", default=None, help="Explicit project id. Default: dir name.")
    insights_p.set_defaults(func=_run_insights)

    ab_p = sub.add_parser(
        "ab-resolve",
        help="Pick the measured-winner hook variant from real performance (local).",
    )
    ab_p.add_argument("--project", default=".", help="Project directory. Default: current dir.")
    ab_p.add_argument("--project-id", default=None, help="Explicit project id. Default: dir name.")
    ab_p.set_defaults(func=_run_ab_resolve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
