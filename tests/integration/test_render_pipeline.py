"""ASUR-INTEG-01..05: real end-to-end render (opt-in, needs the ffmpeg binary).

Builds the full SCRIPT -> GENERATION -> EDITING chain from one idea, renders a
real procedural MP4 through the FFmpeg adapter + dispatcher, and asserts the
output is a valid 1080x1920 file carrying provenance+license (ASUR-PROV-01),
while a real-run VIRAL_VIEW still strips quality TARGETS by name
(ASUR-FIREWALL-01). Run with `pytest -m integration`.
"""

import pytest

from asur.core.identity import get_identity
from asur.editing.timeline import build_edit_plan, build_timeline_from_generation_plan
from asur.generation.adapters import ffmpeg
from asur.generation.asset_strategy import build_asset_plan
from asur.generation.creative_direction import build_creative_direction
from asur.generation.dispatch import run_job
from asur.generation.generation_plan import build_generation_plan
from asur.generation.hero_proof import verify_render
from asur.generation.render import build_final_render
from asur.generation.visual_screenplay import build_visual_screenplay
from asur.script.audience import build_audience
from asur.script.hooks import build_hooks
from asur.script.idea import build_idea
from asur.script.research import build_research
from asur.script.script_builder import build_script
from asur.script.strategy import build_strategy
from asur.tools.projection import VIRAL_FORBIDDEN, FirewallLeak, build_viral_view

pytestmark = pytest.mark.integration

PROJECT_ID = "integ-render"
IDEA = "why most people waste money on AI tools"


@pytest.fixture(scope="module")
def chain():
    ident = get_identity()
    idea = build_idea(IDEA, PROJECT_ID, identity=ident)
    research = build_research(idea, PROJECT_ID, identity=ident)
    audience = build_audience(idea, research, PROJECT_ID, identity=ident)
    strategy = build_strategy(idea, audience, PROJECT_ID, identity=ident)
    hooks = build_hooks(strategy, PROJECT_ID, identity=ident)
    script = build_script(strategy, hooks, PROJECT_ID, identity=ident)
    direction = build_creative_direction(strategy, script, PROJECT_ID, identity=ident)
    screenplay = build_visual_screenplay(direction, script, PROJECT_ID, identity=ident)
    asset_plan = build_asset_plan(screenplay, PROJECT_ID, identity=ident)
    gen_plan = build_generation_plan(asset_plan, PROJECT_ID, identity=ident)
    timeline = build_timeline_from_generation_plan(gen_plan, screenplay, PROJECT_ID)
    edit_plan = build_edit_plan(timeline, gen_plan, PROJECT_ID, identity=ident)
    return {
        "screenplay": screenplay,
        "gen_plan": gen_plan,
        "timeline": timeline,
        "edit_plan": edit_plan,
    }


def test_chain_builds_a_nine_scene_screenplay(chain):
    assert chain["screenplay"].body["scene_count"] == 9


def test_ffmpeg_render_writes_a_valid_vertical_mp4(chain, tmp_path):
    out = tmp_path / "reel.mp4"
    result = ffmpeg.render(chain["timeline"], str(out))

    assert out.exists() and out.stat().st_size > 0
    report = verify_render(str(out))
    checks = {c["check"]: c["result"] for c in report["checks"]}
    assert checks["file_exists"] == "pass"
    assert checks["dimensions"] == "pass"
    assert result["media_type"] == "video"


def test_render_output_carries_provenance_and_license(chain, tmp_path):
    out = tmp_path / "reel.mp4"
    result = ffmpeg.render(chain["timeline"], str(out))

    prov = result["provenance"]
    assert prov["model"] == "FFmpeg"
    assert prov["render_cost_usd"] == 0
    assert prov["resolution"] == "1080x1920"
    assert result["license"]["name"]
    assert result["license"]["commercial_ok"] is True


def test_dispatcher_routes_ffmpeg_job_to_a_real_render(chain, tmp_path):
    job = {
        "job_id": "job-00-reel",
        "target_asset": "reel",
        "model": "FFmpeg",
        "params": {"media_type": "video"},
    }
    result = run_job(job, timeline=chain["timeline"], out_dir=str(tmp_path))

    produced = tmp_path / "reel.mp4"
    assert produced.exists() and produced.stat().st_size > 0
    assert result["job_id"] == "job-00-reel"
    assert verify_render(str(produced))["checks"][0]["result"] == "pass"


def test_build_final_render_writes_a_real_vertical_mp4(chain, tmp_path):
    art = build_final_render(
        chain["edit_plan"], PROJECT_ID, out_root=str(tmp_path)
    )

    produced = tmp_path / "final-video.mp4"
    assert produced.exists() and produced.stat().st_size > 0
    assert art.kind == "render"
    assert art.body["verify"]["status"] == "pass"
    assert art.body["provenance"]["resolution"] == "1080x1920"
    assert art.body["license"]["commercial_ok"] is True


def test_build_final_render_youtube_long_is_landscape(chain, tmp_path):
    art = build_final_render(
        chain["edit_plan"], PROJECT_ID, platform="youtube_long", out_root=str(tmp_path)
    )

    produced = tmp_path / "final-video.mp4"
    assert produced.exists() and produced.stat().st_size > 0
    assert art.body["provenance"]["resolution"] == "1920x1080"
    report = verify_render(str(produced), platform="youtube_long")
    checks = {c["check"]: c["result"] for c in report["checks"]}
    assert checks["dimensions"] == "pass"


def _synth_wav(path, *, freq, seconds=2.0):
    """Synthesize a tiny real WAV with the ffmpeg binary (no third-party deps)."""
    import subprocess

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={freq}:duration={seconds:.2f}",
            "-ac",
            "1",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )


def test_two_track_mix_muxes_voice_over_ducked_music(chain, tmp_path):
    """Both a voice track and a music bed produce a single mixed audio stream.

    Synthesizes two real WAVs, renders with assets={'voice', 'music'}, and
    confirms the output carries one audio stream and provenance records two
    source tracks (two-track voice-over-ducked-music mix).
    """
    import subprocess

    voice = tmp_path / "voice.wav"
    music = tmp_path / "music.wav"
    _synth_wav(voice, freq=220)
    _synth_wav(music, freq=440)

    out_root = tmp_path / "render"
    art = build_final_render(
        chain["edit_plan"],
        PROJECT_ID,
        out_root=str(out_root),
        assets={"voice": str(voice), "music": str(music)},
    )

    produced = out_root / "final-video.mp4"
    assert produced.exists() and produced.stat().st_size > 0
    assert art.body["provenance"]["audio_tracks"] == 2
    assert art.body["provenance"]["audio_present"] is True

    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            str(produced),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    assert probe.stdout.strip().splitlines() == ["audio"]


def test_firewall_holds_on_a_real_render_artifact(chain, tmp_path):
    """A real rendered bundle's VIRAL_VIEW carries no quality/hardness TARGET.

    The render artifact's own provenance (not a hand-written literal) is fed
    through ``build_viral_view``; its conformance scan runs for real and the
    resulting view is asserted clean of every VIRAL_FORBIDDEN name
    (ASUR-FIREWALL-01). This exercises the actual projection path on real output
    rather than re-checking a fixture dict.
    """
    art = build_final_render(chain["edit_plan"], PROJECT_ID, out_root=str(tmp_path))

    view = build_viral_view(
        bundle_hashes={"final-video.mp4": "sha256:deadbeef"},
        provenance=art.body["provenance"],
        platform_facts={"aspect_ratio": "9:16", "has_captions": True},
        rubric_metadata={"lane": "viral", "binding": "run-x"},
    )
    blob = repr(view).casefold()
    for forbidden in VIRAL_FORBIDDEN:
        assert forbidden.casefold() not in blob


def test_firewall_fails_closed_if_a_target_leaks_into_provenance(chain, tmp_path):
    """A leaked TARGET name in the render provenance fails the projection closed.

    If a quality/hardness target ever leaked into a render artifact's
    provenance, feeding it through ``build_viral_view`` must raise
    ``FirewallLeak`` rather than pass it to the evaluator (ASUR-FIREWALL-01,
    fails closed).
    """
    art = build_final_render(chain["edit_plan"], PROJECT_ID, out_root=str(tmp_path))
    poisoned = dict(art.body["provenance"])
    poisoned["target_score"] = 90

    with pytest.raises(FirewallLeak):
        build_viral_view(
            bundle_hashes={"final-video.mp4": "sha256:deadbeef"},
            provenance=poisoned,
            platform_facts={"aspect_ratio": "9:16"},
            rubric_metadata={"lane": "viral", "binding": "run-x"},
        )
