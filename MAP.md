# ASUR map

One page that shows where everything lives and what it does.
The full illustrated version is `guides/ASUR-Complete-Guide.pdf`.

## The flow

```
idea -> research -> audience -> strategy -> hooks -> script -> quality gate
     -> creative direction -> screenplay -> asset plan -> generation plan
     -> GATE 1 (hero proof, human)  -> full generation -> editing / timeline
     -> render (ffmpeg) -> viral check (12 dimensions)
     -> GATE 2 (publish, human)     -> publish package -> performance -> learning
```

Nothing is published automatically. ASUR stops at gate 2 and a human decides.

## Folders

| Folder | What it is | Tracked in git |
|---|---|---|
| `asur/` | The Python package (the actual product) | yes |
| `asur/core/` | Artifacts, checksums, gates, identity, workspaces | yes |
| `asur/script/` | Stages 1-7: idea, research, audience, strategy, hooks, script, quality gate | yes |
| `asur/generation/` | Stages 8-21: direction, screenplay, assets, plans, hero proof, QA, render, model adapters | yes |
| `asur/editing/` | Timeline, 15 edit primitives, captions, audio mix, edit controls | yes |
| `asur/viral_check/` | 12-dimension honest viral evaluation, PASS / CHANGES / REJECT | yes |
| `asur/learning/` | Publish package, metrics ingest, performance, learning memory | yes |
| `asur/orchestrator/` | 18-state machine, control tokens, run log | yes |
| `asur/platforms/` | Instagram Reels, YouTube Shorts, YouTube Long format packs | yes |
| `asur/tools/` | Firewall projection, hash-chained queue, status, daily driver | yes |
| `tests/` | Test suite (`python3 -m pytest -q`) | yes |
| `docs/` | Spec, architecture, ADRs, build plans, progress | yes |
| `guides/` | PDF guides and the scripts that generate them | yes |
| `studio/` | Hands-on tools: render demo, edit video, lyric video, demo seeder | yes (media ignored) |
| `scripts/` | macOS launchd template for the daily driver | yes |
| `archive/` | Kept-not-deleted files (`SENIORITY_NOTES.md`, stray git config files) | partly |
| `outputs/` | Videos made by studio tools (`edit_out/`, `render_out/`) | no |
| `youtube/` | Output of `asur render`: `youtube/<project>/{render,package,_work}` | no |
| `.script/` | Versioned artifact store used by the pipeline | no |

## Commands

```bash
# Script from an idea (stages 1-7)
python3 -m asur.cli script --idea "your idea" --project . --project-id myvid

# Seed a full demo project, then render it into youtube/demo/package/
python3 studio/seed_demo_project.py --project-id demo
python3 -m asur.cli render --project . --project-id demo --platform youtube_shorts

# Studio tools
python3 studio/render_demo.py --idea "your idea"      # -> outputs/render_out/asur_reel.mp4
python3 studio/edit_video.py --input clip.mp4         # -> outputs/edit_out/variant_*.mp4
python3 studio/lyric_video/ingest.py --help           # lyric video pipeline

# Rebuild the guides
python3 guides/make_brand_guide.py                    # -> guides/ASUR-Complete-Guide.pdf
python3 guides/make_guide.py                          # -> guides/ASUR-Lyric-Video-Guide.pdf

# Health
python3 -m pytest -q
ruff check asur studio guides
```

## Status in one line

Real today: the scripting pipeline, planning, gates, editing plans, ffmpeg render,
viral check, publish package, learning memory. Stubs or in progress: the AI model
adapters (SDXL, Kokoro, Stable Audio, faster-whisper, Wan 2.2). See `DEFERRED.md`.
