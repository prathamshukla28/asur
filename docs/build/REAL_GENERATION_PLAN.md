# ASUR — Real AI Generation Plan (P11 proposal)

> **Status: PLAN ONLY. No code written.** This is an architecture + implementation
> plan for turning the placeholder color-card render into a **real AI-generated video**:
> SDXL background images, Kokoro voiceover, and Stable Audio music composited by the
> LOCKED FFmpeg/MoviePy renderer. It must be reviewed and approved by a human before any
> code is written (ASUR-HUMAN-01 §11). It introduces new SPEC-GAPs (**G26–G29**, below).
> Per `AGENTS.md §7`, each is logged, defaulted conservatively, and gated on a human —
> never invented silently. All AI model work stays behind the `asur[generation]` extra
> and is never imported by the stdlib core (`AGENTS.md §4`).

---

## 0. Why this plan exists (context)

P10 made the pipeline render a **real playable `.mp4`** — but the pixels are placeholder
solid color-cards with burned-in captions. The user's two locked decisions deferred the
AI pixels/voice to "P11":

1. **"Proper video" = real render via FFmpeg/MoviePy** (DONE in P10) — *AI image/video/
   voice deferred to P11.*
2. **"Manage channel" = local ready-to-upload package** (DONE in P10) — no OAuth/API/
   network publish, ever.

The user (m0330) then approved: *"Scope P11 — real AI-generated visuals/voice (FFmpeg/
MoviePy still the locked compositor), tests-first."*

**Surprising discovery while scoping (must be stated honestly):** the generation adapters
are **not stubs**. Four of them (`sdxl.py`, `kokoro.py`, `stable_audio.py`,
`faster_whisper.py`) already carry **real, fully-written implementations** — `sdxl.py` is
committed; the other three are uncommitted working-tree diffs (+75/+91/+88 lines). Only
`wan22.py` (AI video) is still a true stub. **So P11 is NOT "write the AI adapters."**
The adapters exist. The gap is **wiring**: nothing threads real prompts into the jobs, and
nothing composites the generated assets into the render. `DEFERRED.md` is stale and must
be corrected in the same change.

---

## 1. SPEC-GAPs G26–G29 (new — proposed, status: open — awaiting human)

| ID | Question | Conservative default (proposed, fail-closed) | Status |
|----|----------|-----------------------------------------------|--------|
| **G26** | How is a real prompt sourced for each generation job? The screenplay has the intent (`visual_concept`, `semantic_metaphor`, `background.value`, `spoken_content`, `hero_words`) but the `generation_plan` job carries only `target_asset` (an asset_ref string) + `model`. Today `dispatch.run_job` passes the asset_ref string itself as the prompt (crude-prompt gap). | Thread the **already-authored** screenplay scene fields into each job's `params` at `build_generation_plan` time (no new text invented, §7): image jobs get `visual_concept`/`semantic_metaphor`/`composition`; voice jobs get the scene `spoken_content`; music jobs get `audio_direction`. Adapters receive real text, never an asset_ref. If a field is absent, fall back to the asset_ref (current behavior) — never fabricate. | open — awaiting human |
| **G27** | How are generated assets composited into the final render? `ffmpeg.render` draws color-cards and never consumes an SDXL PNG, a Kokoro WAV, or a Stable Audio bed. | A new orchestration step runs `run_job` across the generation plan into the media workspace `_work/` **before** rendering, producing a per-scene asset map `{scene_id: {background_png, ...}}` + `voice_wav` + `music_wav`. `ffmpeg.render` gains optional `backgrounds: dict[int,str]` and keeps its existing `audio_path`. When a background PNG is present for a scene it is used as the card's `-i` input (scaled/cropped to pack resolution) instead of the solid `lavfi color=`; when absent it falls back to the color-card (byte-identical to P10). Captions still burn over it. Fail-closed: a referenced asset file that does not exist => `RenderError` (never a silent blank). | open — awaiting human |
| **G28** | Which generation deps go in `asur[generation]`, and are they pinned? `DEFERRED.md §2` says the extra lists only `moviepy/faster-whisper/librosa/opentimelineio` (unpinned) and is **missing** `torch/diffusers/kokoro/stable_audio_tools`. | Add the missing deps to `[project.optional-dependencies].generation` **pinned** to known-good versions (ADR-worthy; `AGENTS.md §4` — media behind the extra). Keep `[project].dependencies = []` empty (ASUR-LOCAL-01). Stdlib core + tests still install and pass with zero third-party packages. | open — awaiting human |
| **G29** | Does P11 wire AI video (Wan 2.2)? | **No.** `wan22.py` stays a stub this phase (needs a real local GPU + large weights; `user_original`/`ai_image` cover v1 backgrounds). Leave the `DEFERRED.md §1` wan22 row intact; only its sibling rows (sdxl/kokoro/stable_audio/faster_whisper) graduate. | open — awaiting human |

---

## 2. Design principle — wire what exists, do not rebuild

The adapters are real and already correct: lazy-import the heavy dep inside the function
(fail-closed `RuntimeError` when `asur[generation]` is absent), run on MPS/CUDA/CPU,
return the universal `{media_type, origin, file_path, provenance, license}` block
(ASUR-PROV-01), and mark every real-run line `# pragma: no cover` (G10 — never CI, no GPU,
no network, no 7 GB download in tests). P11 does **not** touch adapter internals except to
accept the real prompt text. P11 is three seams:

1. **Prompt seam (G26):** `generation_plan` carries real scene text; `dispatch` passes it.
2. **Produce seam (G27):** an orchestration step runs the plan into `_work/`.
3. **Composite seam (G27):** `ffmpeg.render` uses the produced backgrounds + audio.

FFmpeg/MoviePy remains the LOCKED compositor (`AGENTS.md §4`); AI only *supplies pixels and
audio*, it never becomes the renderer. Sora stays removed.

---

## 3. What lands (and what is committed)

- **Baseline commit (honest):** the 3 uncommitted real adapters (`kokoro.py`,
  `stable_audio.py`, `faster_whisper.py`) + the `dispatch.py` diff are committed as the
  P11 adapter baseline (they are real work, just uncommitted). `sdxl.py` is already
  committed. `lyric_video/timing.py`, `.serena/`, `user.name`, `user.email` stay excluded.
- **Prompt threading** in `generation_plan.py` + `dispatch.py` (G26).
- **Produce-and-composite** path: new `generation/produce.py` (orchestration) + `ffmpeg.py`
  background input (G27).
- **Pinned deps** added to the `generation` extra (G28).
- **DEFERRED.md** §1 rows for sdxl/kokoro/stable_audio/faster_whisper **deleted** (the real
  thing now exists); §2 updated (deps added); §3 crude-prompt row **deleted** (closed by
  G26); wan22 §1 row **kept** (G29).

---

## 4. Module-by-module

- **4.1 `generation/visual_screenplay.py`** — unchanged (already emits `visual_concept`,
  `semantic_metaphor`, `composition`, `background.value`, `spoken_content`, `hero_words`,
  `audio_direction` per scene). These are the honest prompt sources.
- **4.2 `generation/asset_strategy.py`** — unchanged (already assigns SDXL/Kokoro/Stable
  Audio/FFmpeg per asset with license precheck).
- **4.3 `generation/generation_plan.py` (G26)** — `_job_for_asset` adds a `prompt` into
  `params`, sourced from the owning screenplay scene: for `media_type=='image'` →
  `f"{visual_concept}. {semantic_metaphor}. {composition}"`; for `audio_voice` → the
  scene/section `spoken_content`; for `audio_music` → `audio_direction`. `build_generation_plan`
  must therefore also receive the screenplay (add `visual_screenplay_artifact` param) so it
  can map `asset_ref` → scene. No field invented; absent field → omit → dispatch falls back.
- **4.4 `generation/dispatch.py` (G26)** — `run_job` passes `params['prompt']` (when present)
  to SDXL/Kokoro/Stable Audio instead of the `target_asset` string. Fallback to `target_asset`
  preserved. Routing/ext map unchanged. Still lazy-imports adapters (boundary stays green).
- **4.5 NEW `generation/produce.py` (G27)** — `produce_assets(generation_plan_artifact, *,
  out_dir, screenplay=None) -> dict`: iterates jobs in dependency order, calls `run_job` for
  each into `out_dir` (the media workspace `_work/`), returns `{backgrounds: {scene_index:
  png_path}, voice: wav_path|None, music: wav_path|None, assets: [result dicts]}`. Lazy, media
  side only (never imported by core). Fail-closed: adapter `RuntimeError` (extra absent) or a
  missing output file propagates — never a silent skip.
- **4.6 `generation/adapters/ffmpeg.py` (G27)** — `render(timeline, out_path, *, platform=None,
  audio_path=None, backgrounds=None, **params)`: `backgrounds: dict[int,str]` keyed by scene
  index. `_render_card(index, ..., background=None)`: when a background path is given, input is
  `-i <png>` scaled/cropped (`scale=...:force_original_aspect_ratio=increase,crop=WxH`) to pack
  resolution instead of `lavfi color=`; captions `drawtext` still overlay. Absent → color-card
  (byte-identical to P10). Missing referenced file → `RenderError` (fail-closed). Provenance
  gains `backgrounds_used: int`.
- **4.7 `generation/render.py` (G27)** — `build_final_render` gains optional `assets=None`
  (the `produce_assets` result) and forwards `backgrounds=`/`audio_path=` into `ffmpeg.render`.
  When `assets is None` → exact P10 behavior (color-cards). Render artifact provenance records
  which scenes used AI backgrounds + whether voice/music were AI.
- **4.8 `pyproject.toml` (G28)** — add pinned `torch`, `diffusers`, `transformers`,
  `accelerate`, `safetensors`, `Pillow`, `kokoro`, `soundfile`, `numpy`, `stable-audio-tools`,
  `torchaudio` to `[project.optional-dependencies].generation`. `[project].dependencies` stays `[]`.
- **4.9 `DEFERRED.md`** — delete the four graduated §1 rows + the §3 crude-prompt row; update §2.

---

## 5. Tests-first (§6)

**UNIT (stdlib-only, no ffmpeg/GPU/network, run by default):**
- `generation_plan` now threads a real prompt into image/voice/music job params, sourced
  from the screenplay scene (assert the prompt equals the scene's `visual_concept`-derived
  string, never the asset_ref); absent field → asset_ref fallback.
- `dispatch.run_job` passes `params['prompt']` to a **monkeypatched** adapter (assert the
  adapter received the real prompt, not the asset_ref). Adapters themselves never run.
- `produce_assets` iterates jobs in dependency order and returns the `{backgrounds, voice,
  music}` map (adapters monkeypatched to touch fake files); fail-closed when an adapter
  raises or an output file is missing.
- `ffmpeg.render` builds an `-i <png>` + `scale/crop` argv for a scene with a background
  (via the `_install_fake_ffmpeg` subprocess monkeypatch harness from P10b/P10c); builds the
  `lavfi color=` card when no background (byte-identical P10); `RenderError` when a referenced
  background file is absent. Resolution tokens unchanged.
- `build_final_render(assets=None)` is byte-identical to P10 (color-cards).
- Boundary import-linter (`tests/test_boundary.py`) stays green — all media imports lazy.

**INTEGRATION (`@pytest.mark.integration` + `importorskip`, opt-in, double-gated like
`tests/integration/test_sdxl_image.py`):** real SDXL background → real FFmpeg composite →
`verify_render` passes at 9:16; skipped automatically without the extra/weights/ffmpeg.
No AI integration test is expected to run in CI (no GPU, no 7 GB download).

---

## 6. Invariant conformance

- **ASUR-LOCAL-01:** `[project].dependencies=[]` stays empty; AI deps only in the extra;
  stdlib core still runs SCRIPT + VIRAL CHECK end-to-end. No network for identity/gates.
- **ASUR-FIREWALL-01:** all P11 code is GENERATION-side only; no VIRAL CHECK import/call.
- **ASUR-GATE-01:** missing extra → adapter `RuntimeError`; missing asset file → `RenderError`;
  empty plan → fail closed. Absence never passes.
- **ASUR-PROV-01:** every produced asset already carries provenance+license; the render
  artifact + content-report record which pixels/audio were AI-generated and under what license.
- **ASUR-VERSION-01:** assets land in the append-only MediaWorkspace `_work/`; nothing
  overwritten.
- **ASUR-HUMAN-01:** machine commits locally only; still stops at publish gate stage 25;
  never posts. Enabling the paid/large-download `asur[generation]` extra is a human action.
- **ASUR-EXPLAIN-01:** provenance names the model, prompt, seed, device for every asset.

---

## 7. Phasing

- **P11a — baseline + prompt seam (G26):** commit the 3 real adapters + dispatch diff;
  thread real screenplay prompts into `generation_plan` + `dispatch`; update `DEFERRED.md §3`.
  Unit tests only (no ffmpeg/GPU). Behaviour-neutral for the render path.
- **P11b — produce + composite (G27):** `generation/produce.py` + `ffmpeg.render` background
  input + `build_final_render(assets=)`. Unit (argv/fallback/fail-closed) + integration
  (real SDXL→composite, opt-in).
- **P11c — deps + docs (G28):** pin the generation extra; update `DEFERRED.md §1/§2`,
  `STATUS.md`, `CHANGELOG.md`.

Each sub-phase: tests-first → build → verify → full suite green once → SPEC-GAP triage →
STATUS/CHANGELOG → commit local `feat(p11)` selective-add, no trailers, **no push**.

## 8. Out of scope

- **No AI video (Wan 2.2)** — `wan22.py` stays a stub (G29); v1 backgrounds are SDXL images
  or `user_original` footage.
- **No OAuth / Data API / auto-post / network analytics** (unchanged from P10).
- **No Remotion** (FFmpeg/MoviePy LOCKED); **no Sora** (removed).
- **No `[project].dependencies`** growth — AI deps only in the optional extra.
- **No `.gitignore` or constitution amendment; no machine push.**
