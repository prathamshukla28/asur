"""Seed one real ASUR project so `asur render` can fill the youtube/ folder.

Runs the local chain for one idea and saves every artifact into
`<root>/.script/<project-id>/`:

    idea -> research -> audience -> strategy -> hooks -> script
         -> creative direction -> screenplay -> asset plan -> generation plan
         -> edit plan -> FFmpeg render -> MEASURED viral check (ffprobe/ffmpeg)

The viral check measures the rendered MP4; nothing is hard-coded. Prefer
`asur run` (which also drives the gates); this script is kept for the
`asur render` packaging flow:

    python3 studio/seed_demo_project.py --idea "..." --takeaway "..."
    python3 -m asur.cli render --project . --project-id demo --platform youtube_shorts
"""

from __future__ import annotations

import argparse
from pathlib import Path

from asur.core.identity import get_identity
from asur.core.media_workspace import MediaWorkspace
from asur.core.workspace import Workspace
from asur.tools import pipeline

ASUR_ROOT = Path(__file__).resolve().parent.parent


def seed(idea_text: str, project_id: str, root: Path, *, takeaway: str | None = None,
         platform: str = "instagram_reels") -> list[str]:
    ident = get_identity()
    ws = Workspace(root, project_id).ensure()
    script = pipeline.build_script_chain(ws, idea_text, platform=platform,
                                         takeaway=takeaway, identity=ident)
    arts = script.artifacts
    plan = pipeline.build_plan(ws, arts["strategy"], arts["script"], identity=ident)
    out_dir = MediaWorkspace(root, project_id).ensure().base / "render"
    render, _note = pipeline.render_final(ws, plan["edit_plan"], plan["visual_screenplay"],
                                          platform=platform, out_dir=out_dir, identity=ident)
    viral = pipeline.viral_check_render(ws, render.body["final_video"], platform=platform,
                                        edit_plan=plan["edit_plan"], render=render,
                                        identity=ident)
    return [a.artifact_id for a in [*arts.values(), *plan.values(), render, viral]]


def main() -> int:
    ap = argparse.ArgumentParser(prog="studio/seed_demo_project.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--idea", default="why most people waste money on AI tools")
    ap.add_argument("--takeaway", default=None)
    ap.add_argument("--project-id", default="demo")
    ap.add_argument("--root", default=str(ASUR_ROOT), help="project root (default: asur root)")
    args = ap.parse_args()

    ids = seed(args.idea, args.project_id, Path(args.root), takeaway=args.takeaway)
    for artifact_id in ids:
        print(f"saved {artifact_id}")
    print(f"\nnext: python3 -m asur.cli render --project {args.root} "
          f"--project-id {args.project_id} --platform youtube_shorts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
