# Changelog

All notable changes to ASUR are recorded here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow
[Semantic Versioning](https://semver.org/).

Human-authored; no machine commits. Each phase (P00–P08) adds an entry at its exit
gate.

## [Unreleased]

### Added — V1b (human-gated collector for the viral-check correlation study, G30)
- **Collector CLI** (`studio/validation/collect.py`, SPEC-GAP **G30 V1b**): turns a
  human-prepared JSON clip list into the exact sealed dataset the V1a blind scorer
  and offline correlator already consume (`clip_meta.json` with observable metadata
  only, `views.sealed.json` written last with public view counts, empty blind-rating
  stubs under `ratings/`, and a `clips/` drop folder).
- **Human-gated, never networked in code** (ASUR-LOCAL-01 / ASUR-HUMAN-01): the tool
  prints a loud banner, never logs in, never calls a platform API, and never downloads
  — the creator gathers public clips and public view counts with their own browser.
  It lives **outside** `asur/` (exempt from the stdlib-only boundary linter) and is
  **never imported by the core or run by pytest**.
- **Fail-closed and honest**: refuses to overwrite an existing study (ASUR-VERSION-01),
  rejects any clip missing an integer public view count, writes view counts only into
  the sealed file, and leaves judgment booleans empty for a blind rater (nothing invented).

### Added — V1a (blind-correlation validation spine for the viral checker, G30)
- **Validation package** (`asur/viral_check/validation/`, stdlib-only, SPEC-GAP **G30**):
  a three-stage spine that measures whether the viral checker's per-dimension
  *input-quality* score correlates with real-world performance — **without ever
  emitting a predicted-outcome or "% viral" number** (ASUR-HONEST-01).
- **`derive.py`** — `derive_platform_facts()` builds a plain-observable
  `platform_facts` dict: machine-observable facts (aspect ratio, resolution,
  audio presence) come from an injected `probe`; the judgment calls
  (`strong_first_three_seconds`, `delivers_promise`) come only from a **blind human
  rater** and are **omitted when absent** — never invented (§7). Captions presence
  is `'unknown'` when the model/extra is absent rather than guessed. Real-run
  `probe_clip`/`captions_probe` helpers (ffprobe via stdlib subprocess; lazy
  `faster_whisper` adapter) are `# pragma: no cover` — no network/GPU in tests.
- **`score_blind.py`** — `score_study()` scores every clip through the real
  `build_viral_view` → `build_viral_check` path (firewall fails closed on any
  leaked target name) and writes `scores/<clip>.json`. **Hard invariant: the
  scorer never opens `views.sealed.json`** — view counts stay sealed during
  scoring (blind study).
- **`correlate.py`** — `correlate()` unseals the view counts, computes the
  **Spearman rank correlation per dimension** (`spearman()` with average-rank tie
  handling) against public views, buckets verdicts vs median views, and writes an
  honest `report.json` + `report.md` with recorded caveats (correlation is not
  causation; reach is probabilistic and partly serendipitous; public-views-only).
  The report carries **no `%` and no aggregate/overall score** (guarded).
- **Tests-first:** `tests/test_viral_validation_v1a.py` (12 tests) + fixtures under
  `tests/fixtures/viral_validation/demo-study/`; validation stays stdlib-only
  (import-linter green); full suite green.

### Added — P11c (pin the generation extra, G28)
- **Pinned `asur[generation]`** (`pyproject.toml`, SPEC-GAP **G28**): every dependency
  in the optional `generation` extra is now pinned to a known-good version for a
  reproducible opt-in install, replacing the previous unpinned list.
- **Added the five P11b audio/caption deps** that the now-real adapters need:
  `kokoro`, `soundfile`, `numpy`, `stable-audio-tools`, `torchaudio` (each with its
  license + purpose noted inline alongside the existing ten).
- **`[project].dependencies` stays `[]`** (ASUR-LOCAL-01): the stdlib core still
  installs and runs SCRIPT + VIRAL CHECK + orchestration with zero third-party
  packages. Enabling the extra pulls `torch` + multi-GB weights and is a human-gated,
  opt-in action (ASUR-HUMAN-01); the core never imports any of these.
- **Tests first** (`tests/test_generation_extra_p11c.py`): asserts the extra lists
  every real-adapter dependency, that every entry carries a `==` pin, and that
  `[project].dependencies` remains empty. Reads `pyproject.toml` only (stdlib
  `tomllib`, `importorskip` on 3.10); never imports `torch` or any heavy dep.

### Added — P11b (produce real AI assets + composite them into the render)
- **`produce_assets`** (`asur/asur/generation/produce.py`, SPEC-GAP **G27**): walks a
  generation plan's jobs in dependency order, runs each AI job through the dispatcher,
  and groups the produced files by role — `{backgrounds: {scene_id: png}, voice: wav|None,
  music: wav|None, assets: [provenance...], skipped: [job_id...]}`. On-screen-text
  (model `FFmpeg`, burned in at render time) and user-original footage (model
  `user-camera`, creator-owned) jobs are **skipped and recorded**, never silently dropped.
  Fails closed (ASUR-GATE-01): a raising adapter (missing `asur[generation]` extra)
  propagates, and an adapter that claims a file not on disk raises `RenderError`. The
  dispatcher + the ffmpeg import are lazy, so the module stays stdlib-only and the
  boundary import-linter stays green.
- **Background compositing** (`asur/asur/generation/adapters/ffmpeg.py`, SPEC-GAP **G27**):
  `render(timeline, out_path, *, backgrounds=None, ...)`. A scene with a produced image
  is composited (`-loop 1 … -i <png>`, scale-to-cover + centre-crop to the pack
  resolution) instead of a solid colour card; any burned-in caption joins the same
  `-vf` chain and the drawtext fallback keeps the background. Scenes with no produced
  image stay solid cards, so `backgrounds=None` is byte-identical to the P10 render
  (ASUR-VERSION-01). A referenced background file that is absent fails closed
  (`RenderError`). Provenance gains `backgrounds_used` (0 when none).
- **Asset wiring in `build_final_render`** (`asur/asur/generation/render.py`): gains an
  optional `assets=` (the `produce_assets` result). When supplied, its backgrounds are
  composited and its voice/music are muxed (voice preferred — the information-carrying
  track; no fabricated audio, ASUR-HONEST-01), and the render body records which asset
  roles were wired. `assets=None` forwards nothing and stays byte-identical to P10.
- **Captions dispatch fix** (`asur/asur/generation/dispatch.py`): the `captions` branch
  now feeds faster-whisper the real produced voice WAV via `params['audio_path']`
  (falling back to the ref string only when no audio was wired), and `captions` jobs
  get a `.json` output extension. faster-whisper transcribes an *input* audio file, not
  an `out_path`.
- **Tests** (`tests/test_produce_p11b.py`, 9 tests, tests-first/RED-confirmed): produce
  groups backgrounds/voice/music; FFmpeg + user-camera jobs are skipped; fail-closed on a
  raising adapter and on a missing output file; a background PNG is composited via
  `-loop 1 -i <png>` + scale/crop while other scenes stay colour cards; no-background
  render is byte-identical (no new used-count); a missing background file fails closed;
  compositing still renders at the pack resolution; `build_final_render(assets=None)` is
  byte-identical. Full suite **326 passed, 8 deselected**.

### Added — P11a (real screenplay prompts into generation jobs + AI adapter baseline)
- **Prompt threading** (SPEC-GAP **G26**): `build_generation_plan`
  (`asur/asur/generation/generation_plan.py`) gains an optional keyword-only
  `visual_screenplay_artifact=`. When supplied, each AI job carries a real prompt
  derived **only from authored screenplay fields** (never invented, §7): image
  backgrounds use `visual_concept + semantic_metaphor + composition`, the voice track
  uses the joined `spoken_content`, the music bed uses `audio_direction`. On-screen-text
  jobs get no AI prompt. Omitting the screenplay produces byte-identical output
  (ASUR-VERSION-01) — all existing callers are unaffected.
- **Dispatcher wiring** (SPEC-GAP **G26**): `dispatch.run_job`
  (`asur/asur/generation/dispatch.py`) now hands `params['prompt']` to the SDXL / Kokoro /
  Stable Audio adapters instead of the raw asset-ref string; the asset-ref fallback is
  preserved when no prompt is present. The FFmpeg and captions branches are unchanged.
- **Real AI adapters landed as baseline**: the Kokoro voice (`adapters/kokoro.py`),
  Stable Audio music (`adapters/stable_audio.py`), and faster-whisper caption
  (`adapters/faster_whisper.py`) adapters are real, lazy-import, fail-closed
  implementations (they `RuntimeError` without the `asur[generation]` extra and their
  real-run lines are `# pragma: no cover`). `DEFERRED.md` corrected: the crude-prompt row
  removed, the stub rows for SDXL/Kokoro/Stable Audio/faster-whisper corrected to REAL
  (only Wan 2.2 AI video and the OTIO interchange remain stubs).
- **Tests** (`tests/test_generation_prompt_p11.py`, 7 tests, tests-first/RED-confirmed):
  plan without screenplay is byte-identical; image job prompt is real screenplay intent
  (not the asset ref); voice prompt is spoken content; music prompt is audio direction;
  on-screen-text jobs have no AI prompt; `run_job` passes the real prompt to the adapter
  and falls back to the asset ref without one. Full suite **316 passed, 8 deselected**.

### Added — P10c (ready-to-upload package + thumbnail + `asur render` CLI)
- **`materialize_package`** (`asur/asur/learning/publish_package.py`): writes the
  ready-to-upload file set into the browsable per-project media workspace
  (`<root>/youtube/<project_id>/package/`) via `MediaWorkspace` (O_EXCL, append-only,
  versioned `vNNNN-` filenames — re-running never overwrites, ASUR-VERSION-01). The
  file set adopts `docs/spec/DATA_MODELS.md` L132 as authoritative (SPEC-GAP **G22**):
  `final-video.mp4`, `thumbnail.jpg`, `title.txt`, `description.txt`, `tags.txt`,
  `platform-metadata.json`, `content-report.json`. Fails closed (`RenderError`) when the
  render artifact has no real video on disk (ASUR-GATE-01).
- **Thumbnail frame-grab** (`asur/asur/generation/adapters/ffmpeg.py`): new
  `grab_thumbnail(video_path, out_path, *, timestamp_s=0.0)` extracts a single frame from
  the real render with FFmpeg (zero new dependencies, no AI model, SPEC-GAP **G23**) and
  carries provenance `origin: ffmpeg-framegrab` + a license block (ASUR-PROV-01).
- **`content-report.json`** (SPEC-GAP **G25**): an honest explainability digest —
  artifact lineage (ids + checksums for the publish and render artifacts), the
  viral-check verdict **as recorded** (a label, never a "%" score, ASUR-HONEST-01), the
  render provenance and probed resolution, `content_category`, and `experiment_id`
  (null when no learning experiment). No invented metrics; verified to contain no "%"
  character anywhere.
- **`asur render` CLI** (`asur/asur/cli.py`): new `asur render --project <id>
  [--platform instagram_reels|youtube_shorts|youtube_long]` renders the latest approved
  edit plan into a real MP4, assembles the publish package, materializes the upload
  folder, and prints its path. Fails closed with `HOLD` when no edit plan or viral check
  exists. **It stops at the publish human gate (stage 25) and never posts** — a human
  uploads the files (ASUR-HUMAN-01).
- **Tests** (`tests/test_materialize_p10c.py`, 8 tests, tests-first/RED-confirmed): exact
  authoritative file set; files live in the browsable youtube folder; thumbnail is an
  FFmpeg frame-grab; content report is honest and contains no "%"; metadata carries
  platform + title; re-run appends a new version rather than overwriting; fails closed
  without a real video; long-form description carries chapters. Full suite
  **309 passed, 8 deselected**.

### Added — P10b-captions (burned-in captions + optional audio mux)
- **Caption burn-in** (`asur/asur/editing/timeline.py` +
  `asur/asur/generation/adapters/ffmpeg.py`): the authored on-screen text from the
  visual screenplay (`scenes[].graphics.onscreen_text`) is threaded onto the matching
  text-track clip's `overlays` in `build_timeline_from_generation_plan`, then burned
  into the render via an FFmpeg `drawtext` filter positioned in the caption safe area
  (y-fraction 0.78, matching `editing/captions.py`). **Only authored text is ever
  burned** — never a section label or invented string (ASUR-HONEST-01, §7
  anti-hallucination). Scenes with no authored caption render as clean cards,
  byte-identical to the pre-caption output (ASUR-VERSION-01).
- **Optional audio mux** (same adapter): `render(..., audio_path=None)` muxes a voice
  or music track into the output **only when a real audio file exists on disk**; absent
  or missing file ⇒ a silent render with no fabricated track (user decision: placeholder
  audio only, real AI voice/music via Kokoro/Stable Audio deferred to P11).
- **Provenance booleans** (same adapter): the render provenance now records
  `captions_burned_in` and `audio_present` so each rendered asset honestly states what
  was composited (ASUR-PROV-01, ASUR-EXPLAIN-01).
- **Tests** (`tests/test_render_captions_p10.py`, 8 tests, tests-first/RED-confirmed):
  overlays carry only real on-screen text with safe-area timing; render burns the real
  caption text; no overlays ⇒ no `drawtext`; resolution unchanged with captions; audio
  muxed only when a real file exists. Full suite **301 passed, 8 deselected**.

### Added — P10b (real timeline render — platform-aware FFmpeg adapter + build_final_render)
- **Platform-aware render** (`asur/asur/generation/adapters/ffmpeg.py`):
  `render(timeline, out_path, *, platform=None)` now reads resolution and fps from
  the chosen platform pack's `FormatSpec` instead of the hard-coded 1080×1920
  literal (SPEC-GAP **G20**). `platform=None` resolves to Instagram Reels and stays
  **byte-identical** at 1080×1920 (ASUR-VERSION-01); `youtube_long` renders 16:9
  1920×1080. An unknown platform id fails closed via `get_platform`
  (`UnknownPlatform`) before any work, and the provenance `resolution` string is
  pack-derived. The solid-colour card scope is unchanged (no AI models yet — those
  are deferred to P11).
- **Fail-closed on empty scenes** (same file): a timeline that declares an
  *explicit* empty `scenes: []` list now raises `RenderError` — an edit plan with
  nothing to render is a fail, never a silent default card (ASUR-GATE-01). A bare
  `{}` timeline still falls back to a single default card (it is a minimal valid
  timeline, not an authored-empty one).
- **New final-render orchestrator** (`asur/asur/generation/render.py`, stdlib
  control shell, lazy adapter import keeps the §4 boundary + import-linter green):
  `build_final_render(edit_plan_artifact, project_id, *, platform=None, out_root,
  identity=None)` renders the edit plan's timeline through the FFmpeg adapter,
  structurally verifies the output with the **same** platform, and emits a
  first-class `render` artifact carrying the adapter's provenance + license block
  (ASUR-PROV-01) and the verification report (ASUR-EXPLAIN-01). It **fails closed**
  (`RenderError`) if structural verification reports `fail` (ASUR-GATE-01).
- **`verify_render` final-render ceiling** (`asur/asur/generation/hero_proof.py`):
  added an explicit, named `max_duration_s` parameter. The default (`None`) keeps
  the existing **hero-proof** behaviour (ceiling = hero cap, 5–15s for Instagram),
  so all P04/P09c callers stay byte-identical. A caller verifying a **full final
  render** passes the final ceiling explicitly (the platform band's upper bound, or
  `float('inf')` for an undeclared band) so a legitimately long final video is not
  failed by the short hero-proof cap. The ceiling is always a named input, never a
  silently skipped check (ASUR-EXPLAIN-01). This fixes a real bug surfaced by the
  integration run: a full 60s Instagram render was being failed by the 15s hero cap.
- **Tests**: `tests/test_render_p10b.py` (8 new unit tests, tests-first /
  RED-confirmed before code; stdlib-only, no ffmpeg — `subprocess.run` + `ffprobe`
  monkeypatched): default `platform=None` byte-identical 1080×1920; `youtube_long`
  16:9; unknown platform fails closed; explicit empty scenes fail closed; no-ffmpeg
  fails closed; `build_final_render` emits a `render` artifact with provenance +
  license; youtube_long verifies landscape; verify-`fail` fails closed. Integration
  (`tests/integration/test_render_pipeline.py`, `pytest -m integration`, opt-in,
  needs the real ffmpeg binary): `build_final_render` writes a real 1080×1920 .mp4
  (verify `pass`) and a real 1920×1080 youtube_long .mp4 (dimensions `pass`). Full
  default suite green once: **293 passed, 8 deselected** (integration, need `ffmpeg`).

### Added — P10a (real-render groundwork — media workspace + render kind + chapters fix)
- **New `render` artifact kind** (`asur/asur/core/envelope.py`): added `render` to
  the universal-envelope `KINDS` set so a rendered-output artifact can be created
  through `make_artifact` like any other stage artifact (checksummed, versioned).
  Unknown kinds still fail closed with `ValueError` (ASUR-GATE-01).
- **New browsable media workspace** (`asur/asur/core/media_workspace.py`, pure
  stdlib): `MediaWorkspace(project_root, project_id)` manages a human-browsable
  `youtube/<project_id>/{render,package,_work}/` tree separate from the JSON
  artifact store (`.script/`). Writes are **O_EXCL append-only** — `write_text` /
  `write_bytes` refuse to overwrite an existing file (`MediaWorkspaceError`), and
  `next_version(subdir, name)` yields `vNNNN-<name>` so nothing is silently
  overwritten (ASUR-VERSION-01). Only the three known subdirs are writable; any
  other target fails closed (ASUR-GATE-01). No third-party imports — the stdlib-only
  core boundary (§4, import-linter) stays intact.
- **Fixed G24 — long-form chapters were always empty**
  (`asur/asur/learning/publish_package.py`): `_chapters_from_edit` previously read
  `edit_body['clips']`, a key `build_edit_plan` never writes, so a real edit plan
  produced zero chapters. It now reads `edit_body['timeline']['scenes']` (the shape
  `Timeline.to_dict()` actually emits) and derives each chapter title honestly from
  the `scene_id` token (no invented labels — §7). Chapter shape `{start_s, title}`
  is unchanged. The Instagram default pack declares no `description` field, so
  `_longform_fields` (and thus this helper) is never invoked for Instagram — its
  package body stays **byte-identical** (ASUR-VERSION-01).
- **Tests** (`tests/test_render_p10a.py`, 11 new, tests-first / RED-confirmed before
  code): render kind accepted + unknown rejected; `MediaWorkspace` layout, text/bytes
  round-trip, overwrite refusal, version bumping, unknown-subdir rejection; chapters
  populated from a real timeline (9 scenes, sorted, first at 0.0), description embeds
  `Chapters:`/`00:00`, and Instagram stays byte-identical even with a real timeline.
  Full suite green once: **284 passed, 6 deselected** (integration, need `ffmpeg`).

### Added — P09c (YouTube extension — long-form hero proof + long-form publish fields)
- **Hero proof reads the selected pack** (`asur/asur/generation/hero_proof.py`):
  `build_hero_proof` and `verify_render` now take an optional `platform=` id. The
  emitted `target_spec` (width / height / aspect_ratio / max_duration_s) and the
  render verifier's dimension/duration checks are sourced from
  `get_platform(platform).format_spec` instead of the hard-coded 1080×1920 / 15s
  literals (the former `1080x1920` reason string is now derived from the pack). So
  `youtube_long` yields a 1920×1080 / `16:9` hero spec while Instagram stays
  1080×1920 / `9:16`.
- **Long-form hero duration sourced from the pack band, not invented** (§7
  anti-hallucination): the hero-proof `max_duration_s` is the pack's already-declared
  `duration_band_s` upper bound (`youtube_long` → 1200.0). Instagram declares no band,
  so the cap falls back to the module default `MAX_HERO_DURATION_S` (15.0) — the
  default call stays **byte-identical** (ASUR-VERSION-01 / G19). No long-form cap is
  guessed; the value is read from authorized pack data.
- **Publish package emits long-form fields when the pack declares them**
  (`asur/asur/learning/publish_package.py`): when `pack.publish_fields` includes the
  long-form set, the package now carries `description` (with timestamped **chapters**
  derived honestly from the edit plan's recorded clips — no invented metrics, no
  "%viral"), `chapters`, `tags`, and the human-owned placeholders `category`,
  `end_screen`, `cards`. The Instagram default pack declares none of these, so its
  body emits **no** extra keys and stays byte-identical.
- **Byte-identical default, fail-closed otherwise**: with no `platform=` argument
  every P00–P09b behaviour and artifact checksum is unchanged (the P04 vertical-reel
  anchor test still passes); an unknown platform id **fails closed** with
  `UnknownPlatform` at both the hero-proof and publish seams (ASUR-GATE-01), even when
  `ffprobe` is absent. No cross-import added — ASUR-FIREWALL-01 intact; honest
  per-dimension scoring untouched (ASUR-HONEST-01). **No network publish** is
  introduced (ASUR-LOCAL-01 / ASUR-HUMAN-01).
- **8 tests** in `tests/test_platforms_p09c.py` (hero-proof default-still-vertical
  anchor, youtube_long landscape spec + 1200.0 cap, unknown-platform fail-closed,
  `verify_render` platform routing + ffprobe-absent `skipped` degrade,
  unknown-platform fail-closed, publish default has no long-form keys, publish
  youtube_long emits long-form fields, publish unknown fail-closed). Full suite
  **272 passed, 6 deselected** (264 prior unit tests unchanged + 8 new P09c tests).

### Added — P09b (YouTube extension — platform pack wiring)
- **Final QA reads the selected pack** (`asur/asur/generation/final_qa.py`):
  `platform_family`, `run_final_qa`, and `build_final_qa_report` now take an
  optional `platform=` id. Dimensions are checked against the pack's
  `FormatSpec.width/height` (not a hard-coded 1080×1920), and when no explicit
  `target_band_s` is given the duration band defaults to the pack's
  `duration_band_s`. So `youtube_long` (1920×1080) **PASSES** dimensions under its
  own pack while still **FAILING** under the Instagram default, and `youtube_shorts`
  applies its 15–60s band as a **warning, not a hard fail** (the G16 pattern is
  preserved — a 90s Shorts WARNs, it does not escalate the family to fail). An
  explicit `target_band_s` still overrides the pack band.
- **Publish package sources aspect ratio from the pack**
  (`asur/asur/learning/publish_package.py`): `metadata.aspect_ratio` is now
  `get_platform(platform).format_spec.aspect_ratio` instead of a hard-coded `"9:16"`
  (IG → `9:16`, `youtube_long` → `16:9`), and `_DEFAULT_PLATFORM` is imported from
  the registry rather than re-declared. The `platform` string is still carried in
  the body unchanged; `publish_gate` (HUMAN GATE #2) is untouched.
- **Byte-identical default, fail-closed otherwise**: both entry points default to
  `instagram_reels`, so with no `platform=` argument every P00–P09a behaviour and
  artifact checksum is unchanged; an unknown platform id **fails closed** with
  `UnknownPlatform` (ASUR-GATE-01). `generation/final_qa.py` imports the stdlib
  `platforms` layer only — **no GENERATION↔VIRAL CHECK cross-import** is introduced
  (ASUR-FIREWALL-01; firewall/conformance subset still green).
- **`hero_proof.py` deliberately unchanged**: Shorts is also 9:16/1080×1920, so it
  needs no edit; long-form 16:9 hero proof is a P09c concern (plan's prove-small
  rule). **No network publish** is introduced or planned for YouTube
  (ASUR-LOCAL-01 / ASUR-HUMAN-01).
- **17 tests** in `tests/test_platforms_wiring.py`. Full suite **264 passed, 6
  deselected** (247 prior unit tests unchanged + 17 new wiring tests).

### Added — P09a (YouTube extension — platform registry, behaviour-neutral)
- **Platform pack layer** (`asur/asur/platforms/`, stdlib-only): new `FormatSpec`
  and `PlatformPack` frozen dataclasses (`platforms/base.py`) that model a target
  surface as **data** — aspect ratio, resolution, fps, default duration, optional
  duration band, safe area, publish field set, and evidence-classed platform facts.
  Resolves **SPEC-GAP G19** (ASUR v1 hard-coded Instagram Reels 9:16; YouTube is new
  scope). Plan: `docs/build/YOUTUBE_EXTENSION_PLAN.md`.
- **Three packs + fail-closed registry** (`platforms/__init__.py`): `instagram_reels`
  (9:16 / 1080×1920 / 30fps / 60s default / no band — **reproduces today's numbers
  byte-for-byte**), `youtube_shorts` (9:16 / 1080×1920 / 45s default / 15–60s band),
  `youtube_long` (16:9 / 1920×1080 / 480s default / 180–1200s band, with
  chapters/tags/description publish fields). `DEFAULT_PLATFORM='instagram_reels'`;
  `get_platform(id)` fails closed with `UnknownPlatform` on any unknown id (never a
  silent default, ASUR-GATE-01).
- **Firewall-ready facts**: `PlatformPack.platform_facts()` returns
  `{platform_id, signals:[…]}` as documented, evidence-classed signals — the exact
  shape `tools/projection.build_viral_view(platform_facts=…)` already accepts, so a
  pack can feed VIRAL_VIEW without leaking any quality/hardness target
  (ASUR-FIREWALL-01, ASUR-HONEST-01).
- **No behaviour change**: this phase adds the registry only; generation/publish are
  **not** rewired to read it yet (that is P09b/c). All P00–P08 behaviour and artifact
  checksums are unchanged. **No network publish** is introduced or planned for
  YouTube (ASUR-LOCAL-01 / ASUR-HUMAN-01).
- `platforms` added to the stdlib boundary import-linter; **19 tests** in
  `tests/test_platforms.py`. Full suite **247 passed, 6 deselected** (223 prior unit
  tests unchanged + 19 platform + 5 new boundary cases for the 5 new modules).

### Added — Road to 10/10 (real render, honest CI, closed loop)
- **Real FFmpeg render adapter** (`asur/asur/generation/adapters/ffmpeg.py`): the
  stub is now a real renderer. It drives the `ffmpeg` binary via `subprocess`
  (stdlib-only at module level, fails closed with `RenderError` if `ffmpeg` is
  absent), writes a true 1080×1920 H.264 `yuv420p` MP4 from the timeline's scenes
  (procedural colour cards — no AI model, GPU, or network), and returns a
  provenance + license dict (`model: FFmpeg`, `render_cost_usd: 0`,
  `resolution: 1080x1920`). An idea → real `.mp4` now runs fully offline.
- **Model → adapter dispatcher** (`asur/asur/generation/dispatch.py`): new
  stdlib-only router (`_ROUTES`, lazy `importlib`) mapping each model name
  (`FFmpeg`, `SDXL`, `Kokoro-82M`, `Stable Audio 3.0`, `Wan 2.2 TI2V-5B`,
  `faster-whisper`) to its adapter function. `run_job(...)` routes a generation
  job to the right adapter; `DispatchError` fails closed on an unknown model.
  Closes **SPEC-GAP G18** (no dispatcher existed; jobs carried the model as a
  bare string).
- **Opt-in integration test tier** (`tests/integration/`): new `integration`
  pytest marker + `addopts = "-m 'not integration'"` so the default run stays
  unit-only. `test_render_pipeline.py` builds the full SCRIPT → GENERATION →
  EDITING chain and renders a real MP4 (5 tests: 9-scene screenplay, valid
  vertical MP4 + `verify_render`, provenance/license, dispatcher route, firewall
  holds on a real run). `conftest.py` auto-skips when `ffmpeg` is absent.
- **GitHub Actions CI** (`.github/workflows/ci.yml`): `stdlib-firewall` job
  (`pip install .` with **no extras**, then a `sys.modules` snapshot that fails if
  any media/network dep leaked into the core import, plus a greppable firewall
  guard for forbidden target field names) and a `lint-type-test` job
  (`ruff` + `mypy` advisory + `pytest`).
- **Derived test-count status tool** (`asur/asur/tools/status.py`, stdlib-only):
  the single source of truth for the test count, read from `pytest --collect-only`.
  Kills the README (36) / STATUS (214) / reality drift — counts are now derived,
  not hand-typed. Run `python3 -m asur.tools.status`.
- **Honest gap register** (`DEFERRED.md` at repo root): names exactly what is real
  vs stubbed (FFmpeg adapter real; SDXL/Kokoro/Stable Audio/Wan 2.2/faster-whisper
  adapters + OTIO still human-run local-only stubs), the incomplete `generation`
  extra, crude dispatch prompt-sourcing, and which invariants are enforced only
  partially (mypy advisory, solo-machine `HOLD:SELF_APPROVED`).
- **File-based PERFORMANCE → LEARNING ingest** (`asur/asur/learning/metrics_ingest.py`,
  stdlib-only, no pandas, no network): `read_metrics_file` reads a `.json`/`.csv`
  metrics file from disk (fails closed with `MetricsFileError`);
  `build_performance_from_file` feeds it to `build_performance`. The learn-from-
  performance loop now closes on disk, not just in memory.

### Added — P08 (LEARNING & Publish)
- **Publish package** (`asur/learning/publish_package.py`): `build_publish_package`
  assembles the publish bundle (title, caption, hashtags, CTA, platform, final-video
  ref, thumbnail ref, carried viral verdict) from the edit plan + viral check, using
  LEARNING's own `source_ref` for both — no cross-import of GENERATION or VIRAL CHECK code.
- **Performance capture** (`asur/learning/performance.py`): `build_performance` records
  **human-provided** metrics (views / watch time / retention / completion / shares / saves /
  comments / likes / follows), normalised against `METRIC_KEYS`, extra keys kept.
  **No network fetch** (ASUR-LOCAL-01) — the source string says so.
- **Learning fold** (`asur/learning/learning.py`): `build_learning` computes
  prediction-vs-actual (diff direction), tracks template/content fatigue, records
  creator-specific learnings as **EMPIRICAL** (this creator's measured performance, not a
  universal rule), and emits `knowledge_graph_edges` (`predicted_then_measured`).
- **The loop closes**: `fold_hook_into_memory` records the published hook to
  `HookMemory` (`event='published'`) so a subsequent `build_hooks(prior_hooks=...)` sees it —
  a published video's measured performance informs the next idea.
- **Publish is a real human gate** (ASUR-HUMAN-01): `publish_gate` wraps `approval_gate` —
  no approver → `HOLD:HUMAN_APPROVAL_REQUIRED` (never auto-publishes); self-approval →
  `HOLD:SELF_APPROVED`; a distinct approver → SHIP.
- `learning` added to the stdlib boundary import-linter; 15 tests in
  `tests/test_learning.py`. **214 passed, 1 skipped.** This completes the P00–P08 build.

### Added — P07 (VIRAL CHECK)
- **Twelve scoring dimensions** (`asur/viral_check/dimensions.py`): Attention, Retention,
  Satisfaction, Value, Shareability, Saveability, Replayability, Originality,
  Authenticity, Visual Quality, Audience Fit, Platform Fit — each scored 0-100 on its own.
  There is **never a single "%viral" number** (ASUR-HONEST-01); scores rate input quality
  against documented platform signals, not a predicted outcome.
- **Four evidence classes** carried per dimension (VERIFIED_FACT / STRONG_EVIDENCE /
  EMPIRICAL / HYPOTHESIS), reused from `asur/script/evidence.py` — "signal exists" is kept
  separate from "weight known" (unknown on every platform).
- **Binary risk flags** (`asur/viral_check/evaluate.py`): watermark / reposted / low-res /
  muted / bordered / majority-text are flagged as messages, never as percentage deductions.
- **Verdict** PASS / PASS-WITH-CHANGES / REJECT: any hard risk flag → REJECT; any soft flag
  or weak dimension → PASS-WITH-CHANGES; otherwise PASS. No aggregate score is summed.
- **Firewall-bound** (ASUR-FIREWALL-01): reads only the VIRAL_VIEW projection; a leaked
  quality/hardness target fails closed at projection time (`FirewallLeak`). `viral_check`
  never imports a GENERATION path (static cross-import check in `tests/test_firewall.py`).
- `build_viral_check(...)` emits a versioned `viral_check` artifact; 17 tests in
  `tests/test_viral_check.py` (incl. an assertion that no aggregate viral number appears);
  `viral_check` added to the stdlib boundary linter. **199 passed, 1 skipped.**

### Added — P06 (full generation, section QA & final render)
- **Section-by-section QA** (`asur/generation/section_qa.py`): each rendered section is
  checked; a failing or rejected section is the **only** one marked to regenerate
  (`sections_to_regenerate`), and expected sections not produced are flagged as failures.
  Fails closed — a section with no rendered asset does not pass.
- **5-family final QA** (`asur/generation/final_qa.py`): visual / audio / text-typography /
  content / platform. `run_final_qa` blocks on any family failure, HOLDs when a required
  manual review is unrecorded, and ships only when all are clear.
- **Anti-AI "Human Pass Test"** (ideas-3 brief, SPEC-GAP G17): the visual family carries six
  named checks — `human_pass_test`, `natural_motion`, `skin_texture`,
  `lighting_shadow_continuity`, `physics_continuity`, `color_grading` — as **manual-review
  flags on the actual rendered output**. ASUR cannot auto-certify photorealism
  (ASUR-HONEST-01), so an unrecorded review fails closed to HOLD.
- **Duration target band** (ideas-3 brief, SPEC-GAP G16): the platform family warns when the
  final duration falls outside a declared band (e.g. 30–40s) but **does not hard-fail**; with
  no band declared it passes (60s platform-neutral default kept, not overwritten).
- **Creative-quality note** added to `docs/GENERATION_STACK.md` §10 (context-aware color
  grading + the Human Pass Test).
- **13 new tests** in `tests/test_p06.py`; full suite **182 passed, 1 skipped** (OTIO).

### Added — P05 (EDITING)
- **OTIO timeline model** (`asur/editing/timeline.py`): 1080×1920 @ 30fps, versioned
  `Clip` / `Track` / `Timeline` with `version_history` on every clip;
  `build_timeline_from_generation_plan` assembles tracks from the generation plan and
  `build_edit_plan` emits a versioned `edit_plan` artifact.
- **15 motion primitives as a palette** (`asur/editing/primitives.py`): `apply_primitive`
  records the prior clip state before every change and is never the creative driver.
- **Caption styling + safe areas** (`asur/editing/captions.py`): Devanagari shaping flag
  for hi/hinglish/mr, with timing and 12% top/bottom safe-band checks that **fail closed**.
- **Audio mix** (`asur/editing/audio_mix.py`): voice/music/sfx + ducking; **fails closed**
  if the music bed would bury the narration.
- **Full manual control set** (`asur/editing/controls.py`): accept / reject / modify /
  regenerate / lock / unlock / compare / branch / revert — each produces a **new version**;
  revert restores the prior state exactly; locked clips refuse edits (ASUR-VERSION-01,
  ASUR-HUMAN-01).
- **OTIO interchange shell** (`asur/editing/adapters/otio.py`): behind `asur[generation]`,
  lazy import, never on the stdlib control path or in CI.
- `editing` added to the boundary import-linter (`adapters/` excluded).
- **29 new tests** in `tests/test_editing.py`. **167 pass (1 skipped — OTIO round-trip
  when the generation extra is absent, by design).**

### Added — P04 (GENERATION + Hero Proof)
- **GENERATION control logic** (stdlib-only, behind no imports; media stays in
  `asur[generation]`): `creative_direction` → `visual_screenplay` (one scene per
  script section) → `asset_strategy` → `generation_plan` → `hero_proof` manifest.
  Asset strategy defaults to the locked stack (SDXL / Wan 2.2 TI2V-5B / Kokoro-82M /
  Stable Audio 3.0 / FFmpeg), all `render_cost_usd:0`.
- **License guard** (`asur/generation/license_guard.py`): hard-coded trap list
  (FLUX-dev / XTTS-v2 / MusicGen / Coqui = non-commercial; HunyuanVideo EU/UK/KR +
  100M MAU cap; CogVideoX-5B 1M-visits/mo cap; Suno / Udio / Sora = avoid). A
  monetized project with a trapped asset (or `commercial_ok:false` / cap / territory
  violation) **fails closed naming the offending asset** (→ `BLOCK:LICENSE_VIOLATION`,
  SPEC-GAP G9, ADR-0005).
- **Offline render-verification harness** (`hero_proof.verify_render`): checks
  structural properties (file exists, 1080×1920, duration ≤ 15s, caption-timing JSON,
  contact-sheet) and **degrades to `skipped`** when `ffprobe`/GPU/network is absent —
  never calls a real model in tests (SPEC-GAP G10). `file_exists` still fails closed on
  a missing file.
- **6 media adapter shells** (`asur/generation/adapters/`: `wan22`, `sdxl`, `kokoro`,
  `stable_audio`, `ffmpeg`, `faster_whisper`), each module-level stdlib-only with the
  heavy dep imported **lazily inside the call** behind `asur[generation]`; never on the
  stdlib control path, never called in tests, excluded from the boundary linter.
- **Sora absent** everywhere as an option/model/adapter (SPEC-GAP G8, ADR-0004); the
  only mention is the forbidden-marker entry in the license trap list.
- **32 new tests** (`tests/test_generation.py`): locked-stack defaults, parametrized
  license-trap firing, lineage + checksums, one-scene-per-section, per-asset
  provenance+license, fail-closed on a trapped asset, expensive-gen blocked before the
  hero-proof gate, vertical-reel spec, `verify_render` missing-file fail + ffprobe-absent
  skip, no adapter offers Sora. **138 tests pass.** `generation` added to the boundary
  import-linter (`adapters/` excluded).
- GENERATION produced the hero-proof **plan + verifier only** — it did **not** render a
  real video (a local GPU step behind the extra). Per ASUR-HUMAN-01 the build stops at
  **HUMAN GATE #1** for a human to approve the actual hero proof before expensive full
  generation.

### Added — P03 (Firewall)
- **Pure projection function** (`asur/tools/projection.py`): `build_generation_view`
  returns `GENERATION_VIEW` (brief + hooks + quality **floors** + cost policy);
  `build_viral_view` returns `VIRAL_VIEW` (rendered-bundle hashes + provenance +
  platform facts + rubric metadata). Pure, deterministic, recomputable
  (ASUR-FIREWALL-01).
- **Named-forbidden strip + greppable conformance** (`conformance_scan`): recursively
  scans every key and string value of a produced view; raises `FirewallLeak`
  (→ `BLOCK:FIREWALL_LEAK`) if any forbidden name appears. `GENERATION_FORBIDDEN`
  blocks viral pass-criteria / gate thresholds / finding text; `VIRAL_FORBIDDEN`
  blocks quality/hardness targets. Fails closed.
- **Static cross-import check** (`tests/test_firewall.py`): asserts no GENERATION
  code path imports a VIRAL CHECK code path and vice-versa. Passes vacuously now
  (neither package exists) and fails the build the moment a cross-import is
  introduced (ASUR-FIREWALL-01).
- **Hash-chained hand-off queue** (`asur/tools/queue.py`) at
  `.asur/queue/<run_id>.jsonl`: `seal → claim → verdict → place`. SHA-256 only;
  bundle frozen on seal (re-seal with different bytes → task-collision `QueueError`);
  atomic single-claimant via `O_EXCL`; `place` succeeds only when sealed digest ==
  verdict digest == on-disk digest (3-way HEAD/digest binding), else `BLOCK`
  (SPEC-GAP G5, ADR-0003).
- **22 new tests** (`tests/test_firewall.py`): projection happy paths + determinism,
  fail-closed on forbidden names in keys and string values, queue happy path, task
  collision, double-claim, verdict-before-claim, 3-way digest mismatch, append-only
  persistence. **106 tests pass.** `tools` added to the boundary import-linter
  (stays stdlib-only).

### Added — P02 (Controller)
- **18-state machine runtime** (`asur/orchestrator/states.py`): ordered `STATES`,
  forward-only one-step `TRANSITIONS`, `HUMAN_GATE_STATES`
  (`HERO_PROOF_APPROVED`, `PUBLISH_READY`), and cost tiers
  (`cheap` stages 0–6, `moderate` 7–18, `expensive` 19+) so expensive work is
  unreachable before the stage-18 hero-proof gate (SPEC-GAP G13).
- **Orchestrator carrying control tokens only** (`asur/orchestrator/orchestrator.py`):
  `ControlToken`/`StepResult` expose state, gate, disposition, digest, residency —
  never findings, criteria, or targets (ASUR-FIREWALL-01). `step()` advances on SHIP,
  holds on HOLD, refuses expensive targets before the hero-proof gate, and routes the
  two human-gate states through `approval_gate` (`HOLD:SELF_APPROVED` for single-user,
  SPEC-GAP G11).
- **Append-only run-log** (`asur/orchestrator/observability.py`) at
  `.asur/runs/<run_id>.jsonl` with a control-token-only key allow-list; rejects any
  out-of-vocab token key (fails closed). No network, no telemetry (SPEC-GAP G12).
- **CLI verbs** `run` / `generate` / `viral-check`: `run` drives the SCRIPT states
  and fails closed at the first ungated step (`HOLD:NO_CHECKS`); `generate` and
  `viral-check` honestly report `HOLD:INSTRUMENT_NOT_AVAILABLE` rather than faking
  work (anti-hallucination §7).
- **New tests** (`tests/test_orchestrator.py`): forward-only transitions, cost-tier
  boundaries, expensive-blocked-before-hero-proof, step advance/hold/block/terminal,
  human-gate approver / self-approval / distinct-approver, run-log append-only
  roundtrip + control-token allow-list. **84 tests pass.** `orchestrator` added to the
  boundary import-linter (stays stdlib-only).

### Added — P01 (SCRIPT completion)
- **Hook A/B variant grouping** (SPEC-GAP G2) in `asur/script/hooks.py`: generated
  hooks are grouped into labelled variants A/B/C/D by strategic direction
  (curiosity / contrarian / story / authority). **Data-only** — no live experiment,
  no winner declared (live A/B waits for VIRAL CHECK + LEARNING, which own real
  performance data). Honors ASUR-HONEST-01 and ASUR-FIREWALL-01.
- **Append-only hook memory** (SPEC-GAP G3): new `asur/script/hook_memory.py` keeps
  an append-only event log at `.script/memory/hooks.jsonl` (events: generated /
  used / rejected / published), one canonical-JSON record per line, never edited or
  deleted (ASUR-VERSION-01). The CLI now reads remembered hooks and feeds them to the
  originality engine, then records newly generated hooks — so repetition is caught
  across runs.
- **7 new tests** (A/B data-only + no-winner, hook-memory append-only roundtrip,
  distinct first-seen order, fail-closed on unknown event, record_many count,
  prior-hooks feed originality across runs). **60 tests pass** (23 core + 13
  integration + 7 P01 + 16 boundary-lint).

### Added — P00 (Foundations & ADRs)
- 8 Architecture Decision Records (`docs/adr/0001–0008`, all **Accepted**):
  key-free local identity; stdlib-only core; firewall projection + queue; FFmpeg
  default renderer + Sora removed; license as a first-class field + trap list;
  honest viral evaluation; the 4-system rename; de-keying (keep hashing, drop
  signing).
- `asur[generation]` optional extra declared in `pyproject.toml` (media deps:
  `moviepy`, `faster-whisper`, `librosa`, `opentimelineio`; never imported by the
  stdlib-only core).
- `tests/test_boundary.py` import-linter enforcing stdlib-only `core`/`script`
  (closes SPEC-GAP G7 for those layers).
- **52 tests pass** (23 core + 13 integration + 16 boundary-lint).

### Added — build kit (governance, no feature code)
- **opencode build kit**: `AGENTS.md` constitution, `opencode.json`, 11 subagent
  definitions under `.opencode/agent/`, slash commands under `.opencode/command/`
  (`/architecture`, `/build-phase`, `/verify-phase`, `/fix-bug`, `/status`,
  `/report`, `/all-phases`), and the `docs/build/`, `docs/spec/`, `docs/adr/`,
  `docs/design/` document sets. (Converted from an earlier Claude-Code kit;
  the `.claude/` files were removed.)
- Automation runbook (`docs/build/PIPELINE.md`) chaining P00→P08 while stopping
  at every human gate / BLOCK / HOLD.
- Phase plan P00–P08 (`docs/build/PHASES.md`) with per-phase scope, mandatory
  tests, and exit gates.
- Frozen product spec (`docs/spec/SPEC.md`) and the open-questions register
  (`docs/build/OPEN_QUESTIONS.md`, seeded with SPEC-GAPs G1–G15).

### Existing (pre-kit, verified)
- Phase 1 SCRIPT intelligence: stdlib-only core (`identity`, `canonical`,
  `envelope`, `workspace`, `gate`) and the SCRIPT chain `idea → research →
  audience → strategy → hooks → script` + 13-check quality gate, with
  evidence-classing and hook intelligence (15 dims, fatigue, originality, first-3s,
  multilingual). CLI `asur script`.

### Notes
- Nothing published or generated yet. Media stack is deferred behind the
  `asur[generation]` optional extra.
