# ASUR — Real Render + Ready-to-Upload Package Plan (P10 proposal)

> **Status: PLAN ONLY. No code written.** This is an architecture + implementation
> plan for turning an ASUR edit/generation plan into a **real, playable `.mp4`** and a
> **browsable, ready-to-upload package** that a human posts manually. It must be reviewed
> and approved by a human before any code is written (ASUR-HUMAN-01). It introduces new
> SPEC-GAPs (**G20–G25**, below) because the frozen spec deliberately names no output
> filenames and no on-disk workspace layout. Per `AGENTS.md §7`, each is logged,
> defaulted conservatively, and gated on a human — never invented silently.

---

## 0. Why this plan exists (context)

The YouTube extension (P09a/b/c) gave ASUR platform packs, long-form 16:9 hero proof,
and long-form publish **metadata** fields. But nothing today turns a plan into an
actual video file a creator can watch and upload.

The user's request (verbatim intent): *"if i give which type of video i want it give
proper youtube video and also manage my youtube channel … i can see the youtube file."*

Two locked decisions from the user scope this phase:

1. **"Proper video" = a real render via FFmpeg/MoviePy** — an actual playable `.mp4`
   produced from the edit plan using the LOCKED default renderer (`AGENTS.md §4`), not a
   metadata-only package. **No AI image/video/voice models yet** (SDXL / Kokoro / Stable
   Audio / Wan remain deferred); v1 uses solid/color-card visuals + burned-in captions +
   optional silent/placeholder audio track. The plan path is real; the pixels are
   placeholder.
2. **"Manage my channel" = a LOCAL ready-to-upload package the human uploads manually** —
   **no OAuth, no YouTube Data API, no Google account, no network publish, ever.** This
   obeys ASUR-LOCAL-01, ASUR-HUMAN-01, and `YOUTUBE_EXTENSION_PLAN.md §8` out-of-scope.

So P10 is the **real-render + packaging** milestone: edit_plan → rendered `.mp4` →
a folder of upload-ready files a human can open, review, and post.

---

## 1. SPEC-GAPs G20–G25 (new — proposed)

| ID | Question | Conservative default (proposed, fail-closed) | Status |
|----|----------|----------------------------------------------|--------|
| **G20** | The FFmpeg adapter renders only solid-colour cards, ignores the timeline's clips/captions/audio, and hard-codes 1080×1920. How should a real edit_plan → `.mp4` render work for v1, and at which resolution? | Render from the **timeline**: one colour-card segment per scene at the **platform pack's** resolution (threaded from `--platform`, not hard-coded), with **burned-in captions** from the caption track and the voice/music tracks muxed when present. No AI pixels yet. Resolution/fps/aspect come from `FormatSpec`. Fails closed (HOLD) if the timeline has no scenes or ffmpeg is absent. | **open — awaiting human** |
| **G21** | ASUR has no on-disk media store and no per-project browsable output folder; the Workspace holds JSON artifacts only (`.script/`). Where do rendered media and the upload package live so the user can "see the file"? | A new **browsable workspace** `<project_root>/youtube/<project_id>/` with subfolders `render/` (the `.mp4` + thumbnail), `package/` (the upload-ready files), and `_work/` (scratch). Writes are **versioned, append-only, O_EXCL** (ASUR-VERSION-01) — never overwrite. JSON artifacts still live in `.script/`; this folder holds only human-facing media/text outputs. | **open — awaiting human** |
| **G22** | What exact files make up the "ready-to-upload package", and under which authority? `DATA_MODELS.md §L132` names the publish_package envelope fields; `master/master.md §48` lists 8 output files but master.md is **not** in the `AGENTS.md §3` precedence chain. | Adopt the **`DATA_MODELS.md` field set as authoritative** and materialize it as a human-browsable folder: `final-video.mp4`, `thumbnail.jpg`, `title.txt`, `description.txt`, `tags.txt`, `platform-metadata.json`, `content-report.json`. (`caption.txt`/`CTA.txt` only for platforms whose pack declares them.) master.md is treated as a **non-authoritative reference** for the file list only; the field *content* follows `DATA_MODELS.md`. | **open — awaiting human** |
| **G23** | How is `thumbnail.jpg` produced without an image model (SDXL deferred)? | **FFmpeg frame-grab** from the rendered `.mp4` at a representative timestamp (the hero/payoff scene start), written as `thumbnail.jpg`. Zero new deps, zero AI. A later phase may replace it with a designed thumbnail. Carries provenance (`origin: ffmpeg-framegrab`) + license (derived-from-render). | **open — awaiting human** |
| **G24** | `publish_package._chapters_from_edit` reads `edit_body['clips'][i].{start_s,end_s,label}`, but `build_edit_plan` writes clips under `body['timeline']['tracks'][*]['clips']` (keys `in`/`out`/`timeline_start`) and scenes under `body['timeline']['scenes']` (`scene_id`/`start`/`end`). Chapters are therefore **always empty** for a real edit_plan. Which is the source of truth for chapters? | Read chapters from **`timeline.scenes`** (the authoritative scene list), not a flat `clips` key. Keep the existing `{start_s, title}` output shape so P09c tests and the long-form publish contract stay green. Byte-identical for the IG default (no chapters emitted). | **open — awaiting human** |
| **G25** | `content-report.json` and the `content_category` / `experiment_id` fields in `DATA_MODELS.md §L132` are not produced today. What goes in them, honestly (ASUR-HONEST-01)? | `content-report.json` = an **explainability digest**: artifact lineage (ids + checksums), the final-QA disposition, the viral-check verdict (as recorded, not a %), render provenance, and the duration/resolution actually probed from the file. `content_category` = the platform category string already chosen; `experiment_id` = the learning experiment id when one exists, else `null`. No invented metrics, no predicted outcomes. | **open — awaiting human** |

Record all six in `docs/build/OPEN_QUESTIONS.md` on approval.

---

## 2. Design principle: extend the render seam, do not fork

The render path already has the right **shape** — it is just hollow. P10 fills it:

1. **Render seam** — `asur/asur/generation/adapters/ffmpeg.py::render(timeline, out_path)`
   already exists and already builds a concat of colour cards. P10 makes it read the
   timeline honestly (per-scene durations, caption burn-in, audio mux) and take resolution
   from the platform pack instead of the two hard-coded constants.
2. **Dispatch seam** — `dispatch.run_job(job, *, timeline, out_dir)` already routes
   `model == "FFmpeg"` to the adapter. P10 adds a **render-orchestration** entry that runs
   the final-video render job for an approved edit_plan and records a render artifact.
3. **Package seam** — `learning/publish_package.py` already assembles the metadata envelope.
   P10 adds a **materializer** that writes that envelope + the rendered `.mp4` + a
   frame-grabbed thumbnail into the browsable `youtube/<project_id>/package/` folder.

No new third-party dependency. v1 is **FFmpeg-binary-only** (invoked via `subprocess`,
exactly as the adapter does today). MoviePy stays available behind `asur[generation]` but
is **not required** for this phase — a deliberately conservative choice (logged under G20).

---

## 3. Proposed folder (the "youtube file" the user can see)

```
<project_root>/youtube/<project_id>/      # NEW browsable, append-only workspace (G21)
    render/
        v0001-final-video.mp4             # the real rendered video (G20)
        v0001-thumbnail.jpg               # ffmpeg frame-grab (G23)
    package/                              # ready-to-upload, human posts manually (G22)
        v0001-title.txt
        v0001-description.txt             # includes timestamped chapters for long-form
        v0001-tags.txt
        v0001-platform-metadata.json
        v0001-content-report.json         # explainability digest (G25)
    _work/                                # scratch (per-scene cards, concat lists)
```

- Media/text outputs live here; **JSON artifacts stay in `.script/`** (unchanged).
- Every write is **O_EXCL, versioned (`vNNNN-`), append-only** (ASUR-VERSION-01) — a
  re-render produces `v0002-…`, never overwrites `v0001-…`.
- `docs/build/` is git-ignored by the repo's bare `build/` rule, so this plan file is
  on-disk reference only (consistent with `YOUTUBE_EXTENSION_PLAN.md`).

---

## 4. What P10 builds (module by module)

### 4.1 `generation/adapters/ffmpeg.py` — real timeline render (G20)
- `render(timeline, out_path, *, platform=None)`: resolution/fps from
  `get_platform(platform).format_spec` (not the hard-coded constants); one segment per
  `timeline["scenes"]` with its real `start`/`end` duration; **caption burn-in** from the
  text track via the `drawtext` filter inside the caption safe-area; **audio mux** of the
  voice/music tracks when their asset files exist, else a silent track. Returns the adapter
  dict with `provenance` (`origin: ffmpeg-render`, the ffmpeg command) + `license`.
- Raises `RenderError` (fails closed) on empty scenes or ffmpeg failure.

### 4.2 `generation/render.py` (NEW) — render orchestration + render artifact
- `build_final_render(edit_plan_artifact, project_id, *, platform=None, out_root, identity=None)`:
  calls the adapter, probes the produced file (reusing `hero_proof._probe_dimensions_duration`),
  runs `verify_render(..., platform=platform)`, and emits a **new `render` artifact kind**
  (added to `core/envelope.py::KINDS`) recording the file path, probed dims/duration,
  verify result, and provenance. Fails closed if verify returns `fail`.

### 4.3 `learning/publish_package.py` — chapters fix + materializer (G22/G24/G25)
- Fix `_chapters_from_edit` to read `timeline.scenes` (G24); keep `{start_s, title}` shape.
- `materialize_package(publish_package_artifact, render_artifact, project_id, *, out_root, identity=None)`:
  writes the `DATA_MODELS.md` field set to `youtube/<project_id>/package/` as the files in
  §3, frame-grabs the thumbnail (G23), and writes `content-report.json` (G25). Returns the
  list of written paths. All writes O_EXCL/versioned.

### 4.4 `core/workspace.py` (or a new `core/media_workspace.py`) — browsable folder (G21)
- A `MediaWorkspace(project_root, project_id)` with `ensure()`, `next_version(subdir, name)`,
  and `write_bytes/ write_text(... , *, exist_ok=False)` using O_EXCL. Pure stdlib.

### 4.5 `cli.py` — `asur render` subcommand
- `asur render --project <id> [--platform youtube_long]` runs the render + package
  materialization for an approved edit_plan and prints the output folder path. Still
  **stops at the publish human gate** (stage 25) — it produces files, it never posts.

---

## 5. Tests (tests-first, `AGENTS.md §6`)

**Unit (stdlib-only, no ffmpeg, no network, no GPU) — run by default:**
- `render.py`: builds the correct ffmpeg argv for a fixture timeline at 16:9 vs 9:16
  (assert resolution comes from the pack, not constants); fails closed on empty scenes.
- `publish_package._chapters_from_edit` reads `timeline.scenes` → chapters non-empty for a
  real edit_plan; IG default still emits none (byte-identical, P09c anchors stay green).
- `materialize_package`: writes exactly the G22 file set; O_EXCL refuses overwrite; a
  re-render bumps to `v0002-`; `content-report.json` carries lineage + verdict, no `%`.
- `MediaWorkspace`: path layout, versioning, O_EXCL fail-closed.
- `envelope`: new `render` kind accepted; unknown kinds still rejected.
- boundary: `platforms/`, `generation/render.py`, `learning/` stay stdlib-only (import-linter).
- new `render` artifact carries provenance + license (ASUR-PROV-01).

**Integration (`@pytest.mark.integration`, auto-skips without the ffmpeg binary) — opt-in:**
- Full chain idea → edit_plan → `build_final_render` → real tiny `.mp4` → `verify_render`
  passes at 9:16 **and** 16:9 (tiny fixtures, a few seconds, no GPU/network).
- `materialize_package` produces a folder whose `final-video.mp4` probes to the pack's
  resolution and whose `thumbnail.jpg` exists.

`verify_render` keeps degrading to `skipped` when ffprobe is absent (G10 preserved).

---

## 6. Invariant conformance

- **ASUR-LOCAL-01 / HUMAN-01:** no network, no OAuth, no API; `asur render` stops at the
  publish gate and only writes local files a human uploads. `dependencies = []` stays empty.
- **ASUR-FIREWALL-01:** render/packaging live entirely on the GENERATION side; VIRAL CHECK
  is untouched; no cross-import. Conformance test stays green.
- **ASUR-HONEST-01:** `content-report.json` records verdicts/evidence as-is, never a `%`.
- **ASUR-PROV-01:** every rendered asset + the thumbnail carry provenance + license.
- **ASUR-VERSION-01:** all media/text writes are O_EXCL, versioned, append-only.
- **ASUR-GATE-01:** empty scenes / missing ffmpeg / failed verify → HOLD/RenderError.
- **ASUR-EXPLAIN-01:** the render artifact + content-report explain what was produced and why.

---

## 7. Phasing (one step at a time, as the user asked)

- **P10a** — core touch-ups + browsable `MediaWorkspace` + new `render` envelope kind +
  the `_chapters_from_edit` G24 fix. (Unit tests only; no ffmpeg needed. Behaviour-neutral
  for existing paths.)
- **P10b** — real timeline render in the FFmpeg adapter + `generation/render.py` +
  `build_final_render` render artifact. (Unit tests for argv/fail-closed; integration test
  for the real `.mp4` behind `@pytest.mark.integration`.)
- **P10c** — `materialize_package` + thumbnail frame-grab + `content-report.json` +
  `asur render` CLI. (Unit tests for the file set + O_EXCL; integration test for the folder.)

Each sub-phase: tests-first → build → verify → full suite green once → SPEC-GAP triage →
STATUS.md + CHANGELOG.md updated → commit locally `feat(p10): …` (no trailers, **no push**).

---

## 8. Out of scope (explicit)

- **No** AI image/video/voice generation (SDXL / Kokoro / Stable Audio / Wan stay deferred).
- **No** OAuth, YouTube Data API, auto-posting, scheduling, or network analytics.
- **No** MoviePy requirement (FFmpeg-binary-only for v1; MoviePy stays optional).
- **No** `.gitignore` or constitution amendment.
- **No** machine push/commit beyond local `feat(p10)` commits a human later pushes.
