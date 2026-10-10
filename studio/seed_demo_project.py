"""Seed one real ASUR project so `asur render` can fill the youtube/ folder.

Runs the whole local chain for one idea:

    idea -> research -> audience -> strategy -> hooks -> script
         -> creative direction -> screenplay -> asset plan -> generation plan
         -> timeline -> edit plan -> viral check

and saves every artifact into the versioned workspace at
`<asur root>/.script/<project-id>/`. After this, the render command can run:

    python3 studio/seed_demo_project.py --idea "why most people waste money on AI tools"
    python3 -m asur.cli render --project . --project-id demo --platform youtube_shorts

which writes the browsable folder `youtube/<project-id>/{render,package,_work}/`
and stops at the publish human gate (nothing is uploaded).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from asur.core.identity import get_identity
from asur.core.workspace import Workspace
from asur.editing.timeline import build_edit_plan, build_timeline_from_generation_plan
from asur.generation.asset_strategy import build_asset_plan
from asur.generation.creative_direction import build_creative_direction
from asur.generation.generation_plan import build_generation_plan
from asur.generation.visual_screenplay import build_visual_screenplay
from asur.script.audience import build_audience
from asur.script.hooks import build_hooks
from asur.script.idea import build_idea
from asur.script.research import build_research
from asur.script.script_builder import build_script
from asur.script.strategy import build_strategy
from asur.tools.projection import build_viral_view
from asur.viral_check.evaluate import build_viral_check

ASUR_ROOT = Path(__file__).resolve().parent.parent


def seed(idea_text: str, project_id: str, root: Path) -> list[Path]:
    ident = get_identity()
    idea = build_idea(idea_text, project_id, identity=ident)
    research = build_research(idea, project_id, identity=ident)
    audience = build_audience(idea, research, project_id, identity=ident)
    strategy = build_strategy(idea, audience, project_id, identity=ident)
    hooks = build_hooks(strategy, project_id, identity=ident)
    script = build_script(strategy, hooks, project_id, identity=ident)
    direction = build_creative_direction(strategy, script, project_id, identity=ident)
    screenplay = build_visual_screenplay(direction, script, project_id, identity=ident)
    asset_plan = build_asset_plan(screenplay, project_id, identity=ident)
    gen_plan = build_generation_plan(asset_plan, project_id, identity=ident)
    timeline = build_timeline_from_generation_plan(gen_plan, screenplay, project_id)
    edit_plan = build_edit_plan(timeline, gen_plan, project_id, identity=ident)

    # The viral check only ever sees the firewall projection (ASUR-FIREWALL-01).
    view = build_viral_view(
        bundle_hashes={"edit_plan": edit_plan.checksum},
        provenance={"renderer": "FFmpeg", "render_cost_usd": 0},
        platform_facts={
            "aspect_ratio": "9:16",
            "strong_first_three_seconds": True,
            "captions_present": True,
            "delivers_promise": True,
        },
        rubric_metadata={"lane": "viral-check", "binding": project_id},
    )
    viral = build_viral_check(view, project_id, identity=ident)

    ws = Workspace(root, project_id).ensure()
    artifacts = [
        idea, research, audience, strategy, hooks, script, direction,
        screenplay, asset_plan, gen_plan, edit_plan, viral,
    ]
    return [ws.save_artifact(a) for a in artifacts]


def main() -> int:
    ap = argparse.ArgumentParser(prog="studio/seed_demo_project.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--idea", default="why most people waste money on AI tools")
    ap.add_argument("--project-id", default="demo")
    ap.add_argument("--root", default=str(ASUR_ROOT), help="project root (default: asur root)")
    args = ap.parse_args()

    paths = seed(args.idea, args.project_id, Path(args.root))
    for p in paths:
        print(f"saved {p}")
    print(f"\nnext: python3 -m asur.cli render --project {args.root} "
          f"--project-id {args.project_id} --platform youtube_shorts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
