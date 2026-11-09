"""End-to-end pipeline steps shared by ``asur script|generate|viral-check|run``.

    script  : idea -> research -> audience -> strategy -> hooks -> script -> 13-check gate
    plan    : creative direction -> screenplay -> asset plan -> generation plan -> edit plan
    render  : (optional) system-TTS narration + FFmpeg render of the edit plan
    measure : VIRAL CHECK over the rendered MP4 (ffprobe/ffmpeg measurements)
    publish : publish package + real gate checks over the rendered bytes

Each step saves versioned, checksummed artifacts through the Workspace. The
heavy media path (``asur.generation.adapters``) is imported lazily inside the
functions that need it, so importing this module stays stdlib-only. VIRAL CHECK
and GENERATION never import each other; this orchestration layer is the only
place that hands the render's facts (as plain data) to the evaluator.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core.envelope import Artifact, verify_checksum
from ..core.gate import HOLD, SHIP, Check, GateResult
from ..core.identity import Identity
from ..core.workspace import Workspace
from ..llm import LLMProvider
from ..platforms import get_platform
from ..script.audience import build_audience
from ..script.hook_memory import HookMemory
from ..script.hooks import MIN_HOOKS, build_hooks
from ..script.idea import build_idea
from ..script.quality_gate import build_qa_report
from ..script.research import build_research
from ..script.script_builder import build_script
from ..script.strategy import build_strategy

__all__ = [
    "ScriptResult",
    "build_plan",
    "build_script_chain",
    "file_sha256",
    "publish_checks",
    "qa_checks",
    "render_hero_proof",
    "render_final",
    "viral_check_render",
]


@dataclass
class ScriptResult:
    artifacts: dict[str, Artifact]
    gate: GateResult
    notes: list[str] = field(default_factory=list)


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def build_script_chain(
    ws: Workspace,
    idea_text: str,
    *,
    platform: str,
    language: str = "en",
    takeaway: str | None = None,
    generator: LLMProvider | None = None,
    identity: Identity | None = None,
) -> ScriptResult:
    """Run the SCRIPT stages, save every artifact, and return them + the gate result."""
    pid = ws.project_id
    idea = build_idea(idea_text, pid, platform=platform, language=language,
                      takeaway=takeaway, identity=identity)
    research = build_research(idea, pid, identity=identity, generator=generator)
    audience = build_audience(idea, research, pid, identity=identity, generator=generator)
    strategy = build_strategy(idea, audience, pid, identity=identity)
    memory = HookMemory(ws.project_root).ensure()
    prior = memory.prior_hook_texts()
    hooks = build_hooks(strategy, pid, identity=identity, prior_hooks=prior, generator=generator)
    script = build_script(strategy, hooks, pid, identity=identity, generator=generator)
    qa, result = build_qa_report(script, pid, hooks_artifact=hooks,
                                 strategy_artifact=strategy, identity=identity)
    artifacts = {"idea": idea, "research": research, "audience": audience,
                 "strategy": strategy, "hooks": hooks, "script": script, "qa_report": qa}
    for art in artifacts.values():
        ws.save_artifact(art)
    recorded = memory.record_many(hooks.body.get("hooks", []), event="generated",
                                  project_id=pid, identity=identity)
    notes = [f"hook memory: compared against {len(prior)} remembered, recorded {recorded}"]
    return ScriptResult(artifacts=artifacts, gate=result, notes=notes)


def build_plan(
    ws: Workspace, strategy: Artifact, script: Artifact, *, identity: Identity | None = None
) -> dict[str, Artifact]:
    """Deterministic GENERATION/EDITING planning from an approved script."""
    from ..editing.timeline import build_edit_plan, build_timeline_from_generation_plan
    from ..generation.asset_strategy import build_asset_plan
    from ..generation.creative_direction import build_creative_direction
    from ..generation.generation_plan import build_generation_plan
    from ..generation.visual_screenplay import build_visual_screenplay

    pid = ws.project_id
    direction = build_creative_direction(strategy, script, pid, identity=identity)
    screenplay = build_visual_screenplay(direction, script, pid, identity=identity)
    asset_plan = build_asset_plan(screenplay, pid, identity=identity)
    gen_plan = build_generation_plan(asset_plan, pid, visual_screenplay_artifact=screenplay,
                                     identity=identity)
    timeline = build_timeline_from_generation_plan(gen_plan, screenplay, pid)
    edit_plan = build_edit_plan(timeline, gen_plan, pid, identity=identity)
    plan = {"creative_direction": direction, "visual_screenplay": screenplay,
            "asset_plan": asset_plan, "generation_plan": gen_plan, "edit_plan": edit_plan}
    for art in plan.values():
        ws.save_artifact(art)
    return plan


def _narration_segments(screenplay: Artifact) -> list[dict[str, Any]]:
    return [
        {"start": s.get("start", 0.0), "end": s.get("end", 0.0), "text": s.get("spoken_content", "")}
        for s in (screenplay.body or {}).get("scenes", [])
    ]


def render_hero_proof(edit_plan: Artifact, *, platform: str, out_dir: Path) -> dict[str, Any]:
    """Render ONLY the hook scene and structurally verify it (hero proof, stage 16)."""
    from ..generation.adapters import ffmpeg
    from ..generation.hero_proof import verify_render

    timeline = dict((edit_plan.body or {}).get("timeline") or {})
    scenes = list(timeline.get("scenes") or [])[:1]
    hero_tl = {**timeline, "scenes": scenes}
    out = out_dir / "hero-proof.mp4"
    out_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg.render(hero_tl, str(out), platform=platform)
    return {"path": str(out), "verify": verify_render(out, platform=platform)}


def render_final(
    ws: Workspace,
    edit_plan: Artifact,
    screenplay: Artifact,
    *,
    platform: str,
    out_dir: Path,
    voice: bool = True,
    identity: Identity | None = None,
) -> tuple[Artifact, str | None]:
    """Narrate (if a system voice exists) and render the full edit plan.

    Returns ``(render_artifact, voice_note)``; voice_note explains a silent render.
    """
    from ..generation.adapters.system_tts import TTSUnavailable, synthesize_narration
    from ..generation.render import build_final_render

    narration: dict[str, Any] | None = None
    note: str | None = None
    if voice:
        try:
            narration = synthesize_narration(_narration_segments(screenplay),
                                             out_dir / "narration.wav")
        except TTSUnavailable as exc:
            note = f"silent render: {exc}"
    else:
        note = "silent render: voice disabled (--no-voice)"
    render = build_final_render(
        edit_plan, ws.project_id, platform=platform, out_root=str(out_dir),
        assets={"voice": narration["file_path"]} if narration else None,
        narration=narration, identity=identity,
    )
    ws.save_artifact(render)
    return render, note


def viral_check_render(
    ws: Workspace,
    video: str | Path,
    *,
    platform: str,
    edit_plan: Artifact | None = None,
    render: Artifact | None = None,
    identity: Identity | None = None,
) -> Artifact:
    """Measure the rendered file and save a ``viral_check`` artifact."""
    from ..viral_check.check import check_video
    from ..viral_check.facts import plan_facts

    plan = plan_facts(edit_plan.body if edit_plan else None, render.body if render else None)
    provenance = dict((render.body or {}).get("provenance") or {}) if render else None
    sources = [a for a in (edit_plan, render) if a is not None]
    viral = check_video(video, ws.project_id, platform=platform, plan=plan,
                        render_provenance=provenance, source_artifacts=sources,
                        identity=identity)
    ws.save_artifact(viral)
    return viral


def _duration_bounds(platform: str) -> tuple[float, float]:
    from ..viral_check.facts import PLATFORM_MAX_S

    ceiling = PLATFORM_MAX_S.get(get_platform(platform).platform_id)
    return 1.0, float(ceiling) if ceiling else float("inf")


def qa_checks(render: Artifact, *, platform: str) -> list[Check]:
    """Gate checks for entering QA: the render is a real, well-formed file."""
    body = render.body or {}
    video = Path(str(body.get("final_video", "")))
    verify = body.get("verify") or {}
    lo, hi = _duration_bounds(platform)

    def exists() -> tuple[str, str]:
        if not video.is_file() or video.stat().st_size == 0:
            return HOLD, f"rendered file missing or empty: {video}"
        return SHIP, f"{video.name} exists ({video.stat().st_size} bytes)"

    def structural() -> tuple[str, str]:
        status = verify.get("status")
        if status != "pass":
            return HOLD, f"ffprobe structural verify is {status!r}, not 'pass'"
        return SHIP, "ffprobe verified dimensions and duration"

    def duration() -> tuple[str, str]:
        d = float((body.get("provenance") or {}).get("duration_s") or 0.0)
        if not lo <= d <= hi:
            return HOLD, f"duration {d:.1f}s outside {lo:g}-{hi:g}s for {platform}"
        return SHIP, f"duration {d:.1f}s within {lo:g}-{hi:g}s"

    def artifact_checksum() -> tuple[str, str]:
        return (SHIP, "render artifact checksum verified") if verify_checksum(render) \
            else ("BLOCK", "render artifact checksum mismatch")

    return [Check("render_file_exists", exists), Check("render_structural_verify", structural),
            Check("render_duration_in_bounds", duration),
            Check("render_artifact_checksum", artifact_checksum)]


def publish_checks(
    render: Artifact, viral: Artifact | None, *, platform: str, package_folder: Path | None
) -> list[Check]:
    """Real publish-gate checks over the bytes that would actually be uploaded."""
    body = render.body or {}
    video = Path(str(body.get("final_video", "")))

    def file_present() -> tuple[str, str]:
        return (SHIP, f"{video} present") if video.is_file() else (HOLD, f"missing {video}")

    def bytes_match_viral_check() -> tuple[str, str]:
        if viral is None or not video.is_file():
            return HOLD, "no viral check or no file to compare"
        recorded = set((viral.body or {}).get("bundle_hashes", {}).values())
        actual = file_sha256(video)
        if actual not in recorded:
            return "BLOCK", "the file on disk is not the file the viral check measured"
        return SHIP, f"file sha256 matches the measured bundle ({actual[:19]}...)"

    def viral_completed() -> tuple[str, str]:
        if viral is None:
            return HOLD, "viral check has not run"
        vb = viral.body or {}
        verdict = vb.get("verdict")
        if verdict == "REJECT":
            hard = [f["flag"] for f in vb.get("risk_flags", []) if f.get("hard")]
            return HOLD, f"viral check REJECT: {'; '.join(hard)}"
        if verdict != "PASS":
            soft = [f["code"] for f in vb.get("risk_flags", [])]
            weak = vb.get("weak_dimensions", [])
            return HOLD, f"viral check {verdict}: fix {soft + weak} before publishing"
        return SHIP, "viral check PASS on measured dimensions"

    def audio_present() -> tuple[str, str]:
        prov = body.get("provenance") or {}
        return (SHIP, "audio track muxed") if prov.get("audio_present") \
            else (HOLD, "render has no audio track")

    def duration_ok() -> tuple[str, str]:
        lo, hi = _duration_bounds(platform)
        d = float((body.get("provenance") or {}).get("duration_s") or 0.0)
        return (SHIP, f"{d:.1f}s within upload bounds") if lo <= d <= hi \
            else (HOLD, f"{d:.1f}s outside {lo:g}-{hi:g}s")

    def package_written() -> tuple[str, str]:
        if package_folder is None or not package_folder.is_dir():
            return HOLD, "ready-to-upload package folder not written"
        return SHIP, f"package at {package_folder}"

    def licenses_recorded() -> tuple[str, str]:
        blocks = [body.get("license") or {}]
        narration = body.get("narration")
        if narration:
            blocks.append(narration.get("license") or {})
        if any(not b.get("name") for b in blocks):
            return HOLD, "an asset in the render has no license block"
        personal = [b["name"] for b in blocks if b.get("commercial_ok") is False]
        if personal:
            return SHIP, f"licenses recorded; personal/non-commercial only: {personal}"
        return SHIP, "licenses recorded; all commercial-OK"

    return [Check("final_file_present", file_present),
            Check("checksum_matches_viral_check", bytes_match_viral_check),
            Check("viral_check_completed", viral_completed),
            Check("audio_present", audio_present),
            Check("duration_within_platform_bounds", duration_ok),
            Check("package_materialized", package_written),
            Check("asset_licenses_recorded", licenses_recorded)]


def min_hooks_ok(hooks: Artifact) -> bool:
    return len((hooks.body or {}).get("hooks", [])) >= MIN_HOOKS
