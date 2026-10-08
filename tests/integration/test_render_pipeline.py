"""ASUR-INTEG-01..05: real end-to-end render (opt-in, needs the ffmpeg binary).

Builds the full SCRIPT -> GENERATION -> EDITING chain from one idea, renders a
real procedural MP4 through the FFmpeg adapter + dispatcher, and asserts the
output is a valid 1080x1920 file carrying provenance+license (ASUR-PROV-01),
while a real-run VIRAL_VIEW still strips quality TARGETS by name
(ASUR-FIREWALL-01). Run with `pytest -m integration`.
"""

import pytest

from asur.core.identity import get_identity
from asur.editing.timeline import build_timeline_from_generation_plan
from asur.generation.adapters import ffmpeg
from asur.generation.asset_strategy import build_asset_plan
from asur.generation.creative_direction import build_creative_direction
from asur.generation.dispatch import run_job
from asur.generation.generation_plan import build_generation_plan
from asur.generation.hero_proof import verify_render
from asur.generation.visual_screenplay import build_visual_screenplay
from asur.script.audience import build_audience
from asur.script.hooks import build_hooks
from asur.script.idea import build_idea
from asur.script.research import build_research
from asur.script.script_builder import build_script
from asur.script.strategy import build_strategy
from asur.tools.projection import VIRAL_FORBIDDEN, build_viral_view

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
    return {
        "screenplay": screenplay,
        "gen_plan": gen_plan,
        "timeline": timeline,
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


def test_firewall_holds_on_a_real_run(chain):
    view = build_viral_view(
        bundle_hashes={"reel.mp4": "sha256:deadbeef"},
        provenance={"model": "FFmpeg", "render_cost_usd": 0},
        platform_facts={"aspect_ratio": "9:16", "has_captions": True},
        rubric_metadata={"lane": "viral", "binding": "run-x"},
    )
    blob = repr(view).casefold()
    for forbidden in VIRAL_FORBIDDEN:
        assert forbidden.casefold() not in blob
