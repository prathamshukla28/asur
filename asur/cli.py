"""asur - local command-line front door.

    asur script      --idea "..." [--takeaway "..."] [--llm ollama:llama3.1]
    asur generate    render the latest approved script to an MP4 (FFmpeg + system voice)
    asur viral-check <video.mp4> [--platform ...]   measure a rendered file
    asur run         --idea "..." --self-approve    script -> plan -> render -> measure
                     -> viral check -> publish gate, driving the 18-state machine

Every stage writes a versioned, checksummed artifact into ``<project>/.script/``
(ASUR-VERSION-01) with lineage back to its inputs (ASUR-PROV-01). Gates fail
closed: exit 0 means the step cleared its gate, 1 means HELD (with reasons),
2 means a usage/input error.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core.envelope import verify_checksum
from .core.gate import HOLD, SHIP, Check
from .core.identity import get_identity
from .core.media_workspace import MediaWorkspace
from .core.workspace import Workspace, WorkspaceError
from .llm import LLMProvider, provider_from_spec
from .orchestrator import Orchestrator
from .platforms import get_platform
from .tools import pipeline


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


def _provider(args: argparse.Namespace) -> LLMProvider | None | int:
    """Resolve --llm / $ASUR_LLM; exit code 2 on an unknown provider name."""
    try:
        return provider_from_spec(getattr(args, "llm", None))
    except ValueError as exc:
        _emit(f"error: {exc}")
        return 2


def _print_gate(result, indent: str = "  ") -> None:
    _emit(f"{indent}disposition : {result.disposition}"
          + (f" ({result.substate})" if result.substate else ""))
    for reason in result.reasons:
        mark = "ok  " if reason["disposition"] == SHIP else reason["disposition"]
        _emit(f"{indent}  [{mark}] {reason['check']}: {reason['reason']}")


def _script_stage(ws: Workspace, args: argparse.Namespace, generator, identity):
    """Run SCRIPT, print each artifact, return the ScriptResult."""
    result = pipeline.build_script_chain(
        ws, args.idea.strip(), platform=args.platform, language=getattr(args, "language", "en"),
        takeaway=getattr(args, "takeaway", None), generator=generator, identity=identity,
    )
    for kind, art in result.artifacts.items():
        gen = (art.body or {}).get("generator", "")
        _emit(f"  {kind:<10} {art.artifact_id}  [{gen}]" if gen else f"  {kind:<10} {art.artifact_id}")
    for note in result.notes:
        _emit(f"  {note}")
    return result


def _run_script(args: argparse.Namespace) -> int:
    if not (args.idea or "").strip():
        _emit("error: --idea must not be empty")
        return 2
    resolved = _resolve_project(args)
    if isinstance(resolved, int):
        return resolved
    project_root, project_id = resolved
    generator = _provider(args)
    if isinstance(generator, int):
        return generator
    identity = get_identity()
    try:
        ws = Workspace(project_root, project_id).ensure()
    except WorkspaceError as exc:
        _emit(f"error: could not open workspace: {exc}")
        return 2

    _emit("ASUR SCRIPT")
    _emit(f"  project   : {project_id}  ({project_root / '.script'})")
    _emit(f"  generator : {generator.label if generator else 'template (offline)'}")
    _emit()
    try:
        result = _script_stage(ws, args, generator, identity)
    except (WorkspaceError, ValueError) as exc:
        _emit(f"error: {exc}")
        return 2
    _emit()
    _emit("13-check script quality gate:")
    _print_gate(result.gate)
    _emit()
    if result.gate.disposition == SHIP:
        _emit("Result: script cleared the quality floor. Next: asur generate")
        return 0
    _emit("Result: HELD for revision (nothing overwritten; re-run creates a new version).")
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


def _render_dir(project_root: Path, project_id: str) -> Path:
    return MediaWorkspace(project_root, project_id).ensure().base / "render"


def _print_viral(viral) -> None:
    body = viral.body or {}
    _emit(f"  verdict  : {body.get('verdict')}  ({body.get('verdict_scope', '')})")
    for d in body.get("dimensions", []):
        score = "unknown" if d["score"] is None else f"{d['score']:>3}"
        _emit(f"    {d['dimension']:<15} {score:>7}  {d['note']}")
    for f in body.get("risk_flags", []):
        _emit(f"    {'HARD' if f['hard'] else 'soft'}  {f['flag']}")


def _run_generate(args: argparse.Namespace) -> int:
    """Plan + render the latest script artifact into a real MP4 (FFmpeg)."""
    from .generation.render import RenderError

    resolved = _resolve_project(args)
    if isinstance(resolved, int):
        return resolved
    project_root, project_id = resolved
    identity = get_identity()
    ws = Workspace(project_root, project_id).ensure()
    strategy, script, qa = (ws.load_latest(k) for k in ("strategy", "script", "qa_report"))
    _emit("ASUR GENERATE - plan + FFmpeg render")
    if strategy is None or script is None:
        _emit(f"  disposition : {HOLD} (NO_SCRIPT)  run `asur script --idea ...` first")
        return 1
    if (qa is None or (qa.body or {}).get("disposition") != SHIP) and not args.force:
        _emit(f"  disposition : {HOLD} (SCRIPT_NOT_APPROVED)")
        _emit("  the latest script did not clear the quality gate; fix it or pass --force")
        return 1
    plan = pipeline.build_plan(ws, strategy, script, identity=identity)
    for kind, art in plan.items():
        _emit(f"  {kind:<18} {art.artifact_id}")
    try:
        render, note = pipeline.render_final(
            ws, plan["edit_plan"], plan["visual_screenplay"], platform=args.platform,
            out_dir=_render_dir(project_root, project_id), voice=not args.no_voice,
            identity=identity,
        )
    except RenderError as exc:
        _emit(f"  disposition : {HOLD} (RENDER_UNAVAILABLE) {exc}")
        return 1
    prov = render.body["provenance"]
    _emit(f"  render             {render.artifact_id}")
    _emit(f"  video : {render.body['final_video']}")
    _emit(f"          {prov['resolution']}, {prov['duration_s']}s, audio={prov['audio_present']}, "
          f"captions_burned_in={prov['captions_burned_in']}")
    if prov.get("captions_skipped_reason"):
        _emit(f"          note: {prov['captions_skipped_reason']}")
    if note:
        _emit(f"          note: {note}")
    _emit("Next: asur viral-check " + render.body["final_video"])
    return 0


def _run_viral_check(args: argparse.Namespace) -> int:
    """Measure a rendered MP4 and report the twelve dimensions + risk flags."""
    from .viral_check.check import check_video
    from .viral_check.facts import plan_facts
    from .viral_check.probe import ProbeUnavailable

    resolved = _resolve_project(args)
    if isinstance(resolved, int):
        return resolved
    project_root, project_id = resolved
    video = Path(args.video).expanduser().resolve()
    _emit("ASUR VIRAL CHECK - measured from the rendered file")
    _emit(f"  file     : {video}")
    _emit(f"  platform : {args.platform}")
    ws = Workspace(project_root, project_id).ensure()
    edit_plan, render = ws.load_latest("edit_plan"), ws.load_latest("render")
    if render is not None and Path(str(render.body.get("final_video", ""))).resolve() != video:
        edit_plan = render = None  # project artifacts describe a different file
    try:
        if edit_plan is not None or render is not None:
            viral = pipeline.viral_check_render(ws, video, platform=args.platform,
                                                edit_plan=edit_plan, render=render)
        else:
            viral = check_video(video, project_id, platform=args.platform,
                                plan=plan_facts(None, None))
            ws.save_artifact(viral)
    except ProbeUnavailable as exc:
        _emit(f"  disposition : {HOLD} (NOT_MEASURABLE) {exc}")
        return 1
    _print_viral(viral)
    _emit(f"  saved    : viral_check {viral.artifact_id} (v{viral.version})")
    return 0 if viral.body.get("verdict") == "PASS" else 1


def _run_run(args: argparse.Namespace) -> int:
    """Drive the 18-state machine end to end with real gate checks.

    DRAFT .. SCRIPT_APPROVED   SCRIPT stages + the 13-check quality gate
    .. SCREENPLAY_APPROVED     deterministic planning, checked for consistency
    HERO_PROOF_READY           the hook scene is actually rendered + ffprobe-verified
    HERO_PROOF_APPROVED        HUMAN gate #1 (--self-approve records you as approver)
    FULL_GENERATION .. QA      narration + full render; file/duration/checksum checks
    VIRAL_CHECK_APPROVED       measured viral check; REJECT holds the run
    PUBLISH_READY              HUMAN gate #2 + publish checks over the real bytes
    ASUR never uploads: the run stops at PUBLISH_READY with a package on disk.
    """
    from .generation.render import RenderError
    from .learning.publish_package import build_publish_package, materialize_package
    from .viral_check.probe import ProbeUnavailable

    if not (args.idea or "").strip():
        _emit("error: --idea must not be empty")
        return 2
    resolved = _resolve_project(args)
    if isinstance(resolved, int):
        return resolved
    project_root, project_id = resolved
    generator = _provider(args)
    if isinstance(generator, int):
        return generator
    identity = get_identity()
    try:
        ws = Workspace(project_root, project_id).ensure()
        orch = Orchestrator(project_root, args.run_id, identity=identity)
    except (WorkspaceError, ValueError) as exc:
        _emit(f"error: could not start run: {exc}")
        return 2
    approver = identity if args.self_approve else None
    render_dir = _render_dir(project_root, project_id)

    _emit("ASUR RUN - idea -> script -> render -> viral check -> publish gate")
    _emit(f"  project   : {project_id}  ({project_root})")
    _emit(f"  platform  : {args.platform}")
    _emit(f"  generator : {generator.label if generator else 'template (offline)'}")
    _emit()

    def step(checks: list[Check], label: str) -> bool:
        res = orch.step(checks=checks, approver=approver,
                        allow_self_approval=args.self_approve)
        mark = "->" if res.advanced else "HOLD"
        _emit(f"[{mark}] {res.to_state or res.from_state:<28} {label}")
        if not res.advanced:
            _print_gate(res.result, indent="      ")
            _emit()
            _emit(f"Result: HELD at {res.to_state}. Run log: .asur/runs/{args.run_id}.jsonl")
        return res.advanced

    def ok(cond: bool, good: str, bad: str) -> tuple[str, str]:
        return (SHIP, good) if cond else (HOLD, bad)

    _emit("SCRIPT")
    try:
        sres = _script_stage(ws, args, generator, identity)
    except (WorkspaceError, ValueError) as exc:
        _emit(f"error: {exc}")
        return 2
    a = sres.artifacts
    if not step([Check("idea_checksum", lambda: ok(verify_checksum(a["idea"]), "idea verified", "idea checksum mismatch")),
                 Check("idea_text", lambda: ok(bool(a["idea"].body.get("one_line")), "idea present", "empty idea"))],
                "idea recorded"):
        return 1
    if not step([Check("research_angles", lambda: ok(len(a["research"].body.get("angles", [])) >= 3,
                                                     "research has >=3 angles", "fewer than 3 angles"))],
                f"research [{a['research'].body.get('generator')}]"):
        return 1
    if not step([Check("strategy_promise", lambda: ok(bool(a["strategy"].body.get("core_promise")),
                                                      "single promise defined", "no core promise"))],
                "strategy"):
        return 1
    if not step([Check("hook_pool", lambda: ok(pipeline.min_hooks_ok(a["hooks"]), "hook pool >= 20",
                                               "too few hooks")),
                 Check("hook_selected", lambda: ok(bool(a["hooks"].body.get("selected_hook_id")),
                                                   "best hook selected", "no hook selected"))],
                "hooks"):
        return 1
    def _replay(reason: dict) -> Check:
        result: tuple[str, str] = (str(reason["disposition"]), str(reason["reason"]))
        return Check(str(reason["check"]), lambda: result)

    if not step([_replay(r) for r in sres.gate.reasons], "13-check script quality gate"):
        return 1
    script = a["script"]
    plat = get_platform(args.platform)
    timings_total = script.body.get("estimated_duration_s", 0)
    if not step([Check("timing_fits_platform", lambda: ok(
            timings_total > 0 and (plat.format_spec.duration_band_s is None
                                   or plat.format_spec.duration_band_s[0] <= timings_total
                                   <= plat.format_spec.duration_band_s[1]),
            f"{timings_total}s fits {args.platform}", f"{timings_total}s does not fit {args.platform}"))],
                f"timing ({timings_total}s)"):
        return 1

    _emit("PLAN")
    plan = pipeline.build_plan(ws, a["strategy"], script, identity=identity)
    if not step([Check("direction_checksum", lambda: ok(verify_checksum(plan["creative_direction"]),
                                                        "verified", "checksum mismatch"))],
                "creative direction"):
        return 1
    scenes = plan["visual_screenplay"].body.get("scenes", [])
    if not step([Check("screenplay_scenes", lambda: ok(
            bool(scenes) and all(s["end"] > s["start"] for s in scenes),
            f"{len(scenes)} timed scenes", "screenplay has untimed scenes"))],
                "screenplay"):
        return 1
    try:
        hero = pipeline.render_hero_proof(plan["edit_plan"], platform=args.platform, out_dir=render_dir)
    except RenderError as exc:
        hero = {"path": "", "verify": {"status": "fail", "reasons": [str(exc)]}}
    if not step([Check("hero_proof_rendered", lambda: ok(
            hero["verify"].get("status") == "pass", f"hero proof verified: {hero['path']}",
            f"hero proof not verified: {hero['verify'].get('reasons')}"))],
                "hero proof (hook scene rendered + ffprobe-verified)"):
        return 1
    if not step([], "HUMAN gate #1: approve hero proof"):
        _emit("Pass --self-approve to record yourself as the approver, after watching")
        _emit(f"  {hero['path']}")
        return 1

    _emit("RENDER")
    try:
        render, note = pipeline.render_final(ws, plan["edit_plan"], plan["visual_screenplay"],
                                             platform=args.platform, out_dir=render_dir,
                                             voice=not args.no_voice, identity=identity)
    except RenderError as exc:
        render, note = None, str(exc)
    if render is None:
        step([Check("render", lambda: (HOLD, f"render failed: {note}"))], "full render")
        return 1
    prov = render.body["provenance"]
    if not step([Check("render_verified", lambda: ok(render.body["verify"].get("status") == "pass",
                                                     "render verified", "render not verified"))],
                f"full render {prov['resolution']} {prov['duration_s']}s audio={prov['audio_present']}"):
        return 1
    if note:
        _emit(f"      note: {note}")
    if prov.get("captions_skipped_reason"):
        _emit(f"      note: {prov['captions_skipped_reason']}")
    if not step(pipeline.qa_checks(render, platform=args.platform), "QA on the rendered file"):
        return 1

    _emit("VIRAL CHECK")
    video = render.body["final_video"]
    try:
        viral = pipeline.viral_check_render(ws, video, platform=args.platform,
                                            edit_plan=plan["edit_plan"], render=render,
                                            identity=identity)
    except ProbeUnavailable as exc:
        reason = f"not measurable: {exc}"
        step([Check("viral_check", lambda: (HOLD, reason))], "viral check")
        return 1
    _print_viral(viral)
    vb = viral.body
    if not step([Check("viral_not_rejected", lambda: ok(vb["verdict"] != "REJECT",
                                                        f"verdict {vb['verdict']}",
                                                        "REJECT: hard risk flag measured")),
                 Check("measured_coverage", lambda: ok(vb["coverage"]["scored"] >= 4,
                                                       f"{vb['coverage']['scored']} dimensions measured",
                                                       "fewer than 4 dimensions measured"))],
                "viral check over the rendered bytes"):
        return 1

    _emit("PUBLISH")
    subject = str(script.body.get("subject") or project_id)
    publish = build_publish_package(plan["edit_plan"], viral, project_id, title=subject,
                                    caption=subject, platform=args.platform, identity=identity)
    ws.save_artifact(publish)
    try:
        package = materialize_package(publish, render, project_id, out_root=project_root,
                                      identity=identity)
        folder: Path | None = Path(package["folder"])
    except RenderError:
        folder = None
    if not step(pipeline.publish_checks(render, viral, platform=args.platform, package_folder=folder),
                "HUMAN gate #2: publish checks"):
        return 1
    _emit()
    _emit(f"Result: PUBLISH_READY. Upload the files in {folder} yourself;")
    _emit("ASUR never posts (ASUR-HUMAN-01).")
    return 0


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
        description="ASUR - local-first content pipeline: idea -> script -> render -> "
        "measured viral check -> publish gate.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    platforms = "instagram_reels|youtube_shorts|youtube_long"

    def common(p: argparse.ArgumentParser, *, platform: bool = True) -> None:
        p.add_argument("--project", default=".", help="Project directory. Default: current dir.")
        p.add_argument("--project-id", default=None, help="Explicit project id. Default: dir name.")
        if platform:
            p.add_argument("--platform", default="instagram_reels",
                           help=f"Target platform ({platforms}). Default: instagram_reels.")

    def script_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--idea", required=True,
                       help="One-line content idea, e.g. 'why most people waste money on AI tools'.")
        p.add_argument("--takeaway", default=None,
                       help="Your concrete point for the value section (templates cannot invent it).")
        p.add_argument("--language", default="en",
                       help="Hook/script language (en|hi|hinglish|indian-en|mr). Default: en.")
        p.add_argument("--llm", default=None,
                       help="LLM drafter: ollama[:model] | anthropic[:model] | none. "
                            "Default: $ASUR_LLM, else templates (offline).")

    script_p = sub.add_parser("script", help="Idea -> scored, structured script + 13-check gate.")
    script_args(script_p)
    common(script_p)
    script_p.set_defaults(func=_run_script)

    run_p = sub.add_parser(
        "run",
        help="End to end: script -> plan -> render -> viral check -> publish gate (18 states).",
    )
    script_args(run_p)
    common(run_p)
    run_p.add_argument("--run-id", default="run-1", help="Run identifier for the run log.")
    run_p.add_argument("--self-approve", action="store_true",
                       help="Record yourself as approver at the two human gates (recorded as "
                            "self_approved in the run log).")
    run_p.add_argument("--no-voice", action="store_true", help="Render without system-TTS narration.")
    run_p.set_defaults(func=_run_run)

    gen_p = sub.add_parser("generate", help="Plan + render the latest approved script to an MP4.")
    common(gen_p)
    gen_p.add_argument("--no-voice", action="store_true", help="Render without system-TTS narration.")
    gen_p.add_argument("--force", action="store_true",
                       help="Render even if the latest script did not clear the quality gate.")
    gen_p.set_defaults(func=_run_generate)

    vc_p = sub.add_parser("viral-check", help="Measure a rendered video file (ffprobe/ffmpeg).")
    vc_p.add_argument("video", help="Path to the rendered MP4.")
    common(vc_p)
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
