# ASUR Build Status

_Live build dashboard. Update at every phase gate._

| Field | Value |
|---|---|
| Current phase | **Integrity + loop-visibility build — six additive features, three of which delete/narrow `DEFERRED.md` rows.** (1) Provenance+license schema guard (`generation/provenance.py::validate_produced_assets`) wired into `produce_assets`: every produced asset must carry a complete, structurally-valid provenance+license block or production fails closed (ASUR-PROV-01 made real for every asset, not just the renderer's — deletes a DEFERRED row). (2) Structural firewall conformance (`tools/projection.py::assert_view_clean`) walks the exact view a lane receives — every key/string at any depth — selecting the forbidden set by view tag; the render-pipeline integration test now uses it instead of grepping `repr()` (ASUR-FIREWALL-01 — deletes a DEFERRED row). (3) Stdlib RFC 5545 `.ics` export (`life_mentor/ics.py`), local-only no-network: `weekly-tracker plan ics` (WT-G8) + `life-mentor habits ics` (LM-G54 resolved, WT-G8 narrowed to network sync only). (4) `asur insights` — read-only EMPIRICAL aggregation of this creator's hook memory (best-measured direction, pattern fatigue, next experiment), no aggregate score/`%` (ASUR-HONEST-01). (5) `asur ab-resolve` — declares an A/B winner only from measured performance on ≥2 variants, HOLDs otherwise (closes the live half of SPEC-GAP G2). (6) `asur explain` now walks the full pipeline lineage (SCRIPT→LEARNING, a human-facing read of the owner's own workspace, outside the GENERATION↔VIRAL firewall per ASUR-HUMAN-01) and `asur verify-repro` extends byte-identical-checksum rebuilds across the deterministic GENERATION/EDITING planning stages (creative_direction→edit_plan), honestly skipping non-deterministic/media/human-input stages. +46 tests; stdlib-only boundary + firewall conformance stay green; mypy clean (77 files). Prior: **Tooling built — `asur explain` + `asur verify-repro` (two read-only, stdlib-only front doors over the SCRIPT workspace).** `asur/tools/explain.py::build_explanation` walks the versioned SCRIPT chain (idea → research → audience → strategy → hooks → script → qa_report) and surfaces, per stage, its provenance (version, id, checksum, lineage edges) and the reasons it recorded (`selection_reason`/`method`/nested `how_derived`/gate reasons) — reading only what the stages wrote (never invents an explanation) and only SCRIPT-side artifacts (cannot leak across the firewall — ASUR-EXPLAIN-01/FIREWALL-01). `asur/tools/verify_repro.py::verify_reproducible` rebuilds each stored stage from its on-disk upstream artifact(s), recomputes the body checksum, and compares to disk; a mismatch (non-determinism or a tampered body — proven by a re-stamped-checksum tamper test) fails closed to `HOLD:NOT_REPRODUCIBLE` (ASUR-VERSION-01/HONEST-01/GATE-01); hooks carry an honest caveat because their `prior_hooks` input is not captured in the body. Both wired into `cli.py` (`asur explain` / `asur verify-repro`), never write an artifact, no network. Also strengthened the closed-loop test: a published hook folded into memory with its measured result demonstrably shifts the next run's evaluation of that same hook (fatigue 12→80, originality → derivative) — proof LEARNING learns, not just stores. +13 tests; stdlib-only boundary + firewall conformance stay green. Prior: **V1b built — human-gated collector for the viral-check correlation study (SPEC-GAP G30).** `studio/validation/collect.py` (outside `asur/`, never imported by core, never in pytest) turns a human-prepared JSON clip list into the exact V1a sealed dataset: `clip_meta.json` (observable metadata only), `views.sealed.json` (public view counts, written last), empty blind-rating stubs under `ratings/`, and a `clips/` drop folder. Loud banner; never logs in / calls a platform API / downloads / scores (ASUR-LOCAL-01/HONEST-01); refuses to overwrite a study and rejects clips with no observed integer public view count (ASUR-VERSION-01/GATE-01). V1c (real 200–500-clip study) is human-driven and remains. Prior: **V1a built — blind-correlation validation spine for the viral checker (SPEC-GAP G30).** New stdlib-only `asur/viral_check/validation/` package (`derive.py` builds observable `platform_facts` + blind human-rater judgment calls, omitting absent facts never inventing; `score_blind.py::score_study` scores every clip through the real `build_viral_view → build_viral_check` path and **never opens the sealed view counts**; `correlate.py` computes per-dimension **Spearman rank correlation** vs public views and writes an honest `report.json`/`report.md` with **no `%` and no aggregate score** — ASUR-HONEST-01). 12 tests-first + `tests/fixtures/viral_validation/demo-study/`; viral_check stays stdlib-only. V1b (human-gated collector, outside pytest/stdlib-core) + V1c (real 200–500-clip study) remain. Prior: P11b built — produce real AI assets + composite them into the render. `generation/produce.py::produce_assets` walks a generation plan's jobs in dependency order, runs each AI job through the dispatcher, and groups the produced files by role (`{backgrounds, voice, music, assets, skipped}`); FFmpeg on-screen-text and user-camera footage jobs are skipped+recorded; fails closed when an adapter raises or claims a file not on disk (ASUR-GATE-01); dispatcher/ffmpeg imports are lazy so the module stays stdlib-only. The FFmpeg adapter `render(..., backgrounds=)` composites a produced image per scene (`-loop 1 -i <png>`, scale-to-cover + centre-crop) with the solid-colour card as fallback — `backgrounds=None` byte-identical to P10 (ASUR-VERSION-01); a missing referenced image fails closed; provenance gains `backgrounds_used`. `build_final_render(..., assets=)` composites backgrounds + muxes voice/music (voice preferred, no fabricated audio — ASUR-HONEST-01) and records wired roles; `assets=None` byte-identical. The dispatcher captions branch now feeds faster-whisper the produced voice WAV. SPEC-GAP **G27** resolved; pinned deps (**G28**, P11c) remain; Wan 2.2 AI video (**G29**) stays deferred. Prior: P11a threaded real screenplay prompts into generation jobs + landed the real Kokoro/Stable Audio/faster-whisper adapters (SPEC-GAP **G26**). Prior phases: Full P00–P08 complete; P09a/b/c added the opt-in YouTube platform packs + long-form hero proof + long-form publish fields; P10a landed the render kind + browsable `MediaWorkspace` + G24 chapters fix; P10b makes the FFmpeg adapter render at the platform pack's resolution (9:16 Instagram byte-identical default, 16:9 youtube_long), adds `generation/render.py::build_final_render`, and fixes `verify_render` to accept a named `max_duration_s` ceiling; P10b-captions threads authored `onscreen_text` onto text-clip overlays, burns it via `drawtext` in the safe area (only authored text ever burned — ASUR-HONEST-01/§7; clean card byte-identical when none), and adds optional audio mux; **P10c** adds `learning/publish_package.py::materialize_package` (writes the `DATA_MODELS.md` L132 authoritative 7-file ready-to-upload set into `youtube/<project_id>/package/` via the O_EXCL versioned `MediaWorkspace`), `adapters/ffmpeg.py::grab_thumbnail` (FFmpeg frame-grab → `thumbnail.jpg`, zero new deps, provenance `origin: ffmpeg-framegrab` + license), an honest `content-report.json` (lineage ids+checksums, viral verdict as recorded never %, render provenance/resolution, `content_category`, `experiment_id` null — no invented metrics), and the `asur render --project <id> [--platform ...]` CLI that renders → assembles → materializes and **stops at the publish human gate (never posts)**. SPEC-GAPs **G20/G21/G22/G23/G24/G25 all landed**; only AI-generated pixels/voice (SDXL/Kokoro/Stable Audio/Wan) remain deferred to P11 by user decision. Fails closed on empty scenes / absent ffmpeg / verify-`fail` / missing render video / no edit plan / no viral check. Awaiting HUMAN GATE #2 (publish, stage 25) |
| State-machine position | 18-state machine **runtime** live; orchestrator carries control tokens only; hero proof approved; editing + QA + honest viral check built; learning & publish built, paused at the publish gate. P09a/P09b are additive — IG Reels stays the byte-identical default, no state-machine change |
| Tests | **1069 unit tests** (`python3 -m pytest -q` from `asur/`) + **10 opt-in integration tests** (`pytest -m integration`, needs `ffmpeg`). Count is derived, not hand-typed: `python3 -m asur.tools.status`. Covers SCRIPT + orchestrator + firewall + generation + editing + P06 QA + P07 viral check + P08 learning/publish + **P09a platform registry + P09b platform-pack wiring + P09c long-form hero proof & publish fields + P10a media workspace + render kind + chapters fix + P10b platform-aware FFmpeg render + build_final_render + P10b-captions burned-in captions & optional audio mux + P10c ready-to-upload package + thumbnail + asur render CLI + P11a screenplay-prompt threading into generation jobs + P11b produce_assets + background compositing + voice/music mux + captions-dispatch fix** + file-based learning ingest + real-render pipeline (now covers build_final_render at 9:16 + 16:9) + boundary-lint (OTIO round-trip skips when the `generation` extra is absent) + **`asur explain` full-pipeline decision trail + `asur verify-repro` reproducibility guard (SCRIPT + planning stages) incl. tamper detection + strengthened closed-loop learning proof + provenance schema guard + structural firewall conformance + stdlib `.ics` export (planner + habits) + `asur insights` + `asur ab-resolve`** (+46 tests across `test_provenance`, `test_ics`, `test_insights`, extended `test_firewall`/`test_explain`/`test_verify_repro`/`test_learning`). Count is derived, not hand-typed: `python3 -m asur.tools.status`. |
| Last commit | _none yet — repo not initialized (no git commit requested)_ |
| Next human gate | **HERE: HUMAN GATE #2 (publish, stage 25).** A human must approve the publish package before anything posts; ASUR never auto-publishes (ASUR-HUMAN-01) |

## What exists today (verified)
- Stdlib-only core: `identity`, `canonical`, `envelope`, `workspace`, `gate`.
- SCRIPT chain: `idea → research → audience → strategy → hooks → script` + 13-check
  `quality_gate`, with evidence-classing and hook intelligence (15 dims, fatigue,
  originality, first-3s, multilingual).
- CLI: `asur script` / `run` / `generate` / `viral-check` / `render`, plus the
  read-only tools `asur explain` (full-pipeline decision trail with provenance,
  ASUR-EXPLAIN-01), `asur verify-repro` (rebuilds the SCRIPT + GENERATION/EDITING
  planning stages and confirms byte-identical checksums, fails closed on any
  mismatch, ASUR-VERSION-01), `asur insights` (EMPIRICAL learning-loop view, no
  score, ASUR-HONEST-01), and `asur ab-resolve` (measured A/B winner or HOLD,
  SPEC-GAP G2). All stdlib-only and none write an artifact.
- Local `.ics` calendar export (stdlib RFC 5545, no network): `weekly-tracker
  plan ics` (planner) and `life-mentor habits ics` (active habits), built on the
  shared `products/life_mentor/ics.py` writer.
- **P00 done:** 8 ADRs (`docs/adr/0001–0008`, all Accepted); `asur[generation]`
  optional extra declared in `pyproject.toml`; `tests/test_boundary.py` import-linter
  enforces stdlib-only core/script (closes SPEC-GAP G7 for those layers).
- **P01 done:** hook A/B variant grouping (data-only A/B/C/D, SPEC-GAP G2) in
  `hooks.py`; append-only hook memory (`script/hook_memory.py`, SPEC-GAP G3) at
  `.script/memory/hooks.jsonl`, wired into the CLI so each run compares against and
  records remembered hooks (cross-run originality).
- **P02 done:** 18-state machine runtime + forward-only gated transitions
  (`orchestrator/states.py`); orchestrator carrying control tokens only
  (`orchestrator/orchestrator.py`); append-only run-log at `.asur/runs/<run_id>.jsonl`
  with a control-token-only allow-list (`orchestrator/observability.py`, SPEC-GAP G12);
  cost tiers with expensive work unreachable before stage-18 (SPEC-GAP G13); the two
  human gates wired as real blocking states (`HOLD:SELF_APPROVED`, SPEC-GAP G11);
  CLI verbs `run` (drives SCRIPT states, fails closed) / `generate` / `viral-check`
  (honest `HOLD:INSTRUMENT_NOT_AVAILABLE`, no faked work).
- **P03 done:** pure projection function with two views
  (`asur/tools/projection.py`) — `GENERATION_VIEW` (brief + hooks + quality floors)
  and `VIRAL_VIEW` (bundle hashes + provenance + platform facts); named-forbidden
  strip + greppable `conformance_scan` that fails closed (`FirewallLeak`) if a
  forbidden name leaks (SPEC-GAP G4); a static cross-import check
  (`tests/test_firewall.py`) asserting GENERATION and VIRAL CHECK code never import
  each other (ASUR-FIREWALL-01); hash-chained hand-off queue
  (`asur/tools/queue.py`) `seal → claim → verdict → place` at
  `.asur/queue/<run_id>.jsonl` with 3-way digest agreement (SPEC-GAP G5); `tools`
  added to the boundary import-linter (stays stdlib-only).
- **P04 built (awaiting human gate):** GENERATION control logic behind the
  `asur[generation]` extra — `creative_direction` → `visual_screenplay`
  (one scene per script section) → `asset_strategy` (locked-stack defaults:
  SDXL / Wan 2.2 / Kokoro-82M / Stable Audio 3.0 / FFmpeg, all `render_cost_usd:0`)
  → `generation_plan` → `hero_proof` manifest. License guard
  (`generation/license_guard.py`) holds the hard-coded trap list and fails closed
  **naming the offending asset** when a monetized project would use a trapped model
  (SPEC-GAP G9). `hero_proof.verify_render()` is an offline structural harness
  (1080×1920, duration, caption-timing, contact-sheet) that **degrades to
  `skipped`** when `ffprobe`/GPU/network are absent — never a real model in CI
  (SPEC-GAP G10). Six media adapter shells (`generation/adapters/`) sit behind the
  extra, import heavy deps lazily, and are never on the stdlib control path or in
  tests. Sora appears nowhere as an option (SPEC-GAP G8). `generation` added to the
  boundary import-linter (control modules stay stdlib-only; `adapters/` excluded).
- **P05 done:** EDITING environment (stdlib control path). OTIO timeline model
  (`editing/timeline.py`): 1080×1920 @ 30fps, versioned `Clip`/`Track`/`Timeline`
  with `version_history`, `build_timeline_from_generation_plan` + `build_edit_plan`
  (`kind=edit_plan`). The 15 motion primitives as a palette
  (`editing/primitives.py`) — `apply_primitive` records a prior version and never
  drives the creative concept. Caption styling + safe areas
  (`editing/captions.py`): Devanagari shaping flag for hi/hinglish/mr, timing and
  12% top/bottom safe-band checks that fail closed. Audio mix
  (`editing/audio_mix.py`): voice/music/sfx + ducking; fails closed if music buries
  narration. Full manual control set (`editing/controls.py`):
  accept/reject/modify/regenerate/lock/unlock/compare/branch/revert — each produces
  a new version; `revert` restores the prior state exactly; locked clips refuse
  edits. OTIO interchange shell (`editing/adapters/otio.py`) behind the
  `asur[generation]` extra, imported lazily, never on the control path or in CI.
  `editing` added to the boundary import-linter (`adapters/` excluded).
- **P06 done:** section-by-section QA (`generation/section_qa.py`) that
  regenerates **only** the failing section and fails closed when a section has no
  rendered asset; the 5-family final QA (`generation/final_qa.py` —
  visual / audio / text-typography / content / platform). The **visual family**
  carries the ideas-3 anti-AI **Human Pass Test** (human_pass_test, natural_motion,
  skin_texture, lighting_shadow_continuity, physics_continuity, color_grading) as
  **manual-review flags** that HOLD until a human records a decision on the actual
  rendered output — ASUR never auto-certifies photorealism (SPEC-GAP G17). The
  **platform family** flags duration outside a declared target band (e.g. 30–40s)
  as a **warning, not a hard fail**; the 60s default is kept, not overwritten
  (SPEC-GAP G16). Dimensions (1080×1920) and the final-render structural verify
  reuse the offline harness (degrades to `skipped` with no GPU/network).
- **P07 done:** honest VIRAL CHECK (`viral_check/`). 12 scoring dimensions each
  0–100 shown individually — **never a single "% viral" number** (ASUR-HONEST-01);
  4 evidence classes; binary risk flags (never % deductions); verdict
  PASS / PASS-WITH-CHANGES / REJECT (any hard flag → REJECT, soft flag or weak
  dimension → PASS-WITH-CHANGES). Reads **VIRAL_VIEW only** and fails closed
  (`FirewallLeak`) if a quality target leaks; never imports GENERATION. `viral_check`
  added to the boundary import-linter.
- **P08 built (awaiting human gate):** LEARNING & publish (`learning/`, stdlib
  control path). `publish_package.build_publish_package` assembles the publish
  package from the edit plan + viral check (its own `source_ref`, no cross-import).
  `performance.build_performance` captures **human-provided** metrics — **no network
  fetch** (ASUR-LOCAL-01). `learning.build_learning` folds prediction-vs-actual
  (diff direction), tracks template/content fatigue, records creator-specific
  learnings as **EMPIRICAL** (not universal), and emits `knowledge_graph_edges`
  (`predicted_then_measured`). `learning.fold_hook_into_memory` records the published
  hook to hook memory so the **next run is informed — the loop closes.**
  `publish_gate` is the real HUMAN GATE #2 via `approval_gate`: no approver →
  `HOLD:HUMAN_APPROVAL_REQUIRED` (never auto-publishes), self → `HOLD:SELF_APPROVED`,
  distinct approver → SHIP. `learning` added to the boundary import-linter.
- **P09a done (behaviour-neutral):** YouTube extension scaffolding (SPEC-GAP G19).
  New stdlib-only `asur/asur/platforms/` package — `FormatSpec` + `PlatformPack`
  frozen dataclasses (`platforms/base.py`) and a 3-pack registry
  (`platforms/__init__.py`, `DEFAULT_PLATFORM='instagram_reels'`, fail-closed
  `UnknownPlatform`): `instagram_reels` (9:16 / 1080×1920 / 30fps / 60s default /
  no band — **reproduces today's numbers exactly**), `youtube_shorts`
  (9:16 / 1080×1920 / 45s default / 15–60s band), `youtube_long`
  (16:9 / 1920×1080 / 480s default / 180–1200s band, chapters/tags/description
  publish fields). Each pack exposes evidence-classed `platform_facts()` ready to
  feed the firewall's VIRAL_VIEW. **No generation/publish rewiring yet** (that is
  P09b/c), so all prior behaviour is byte-identical. `platforms` added to the
  boundary import-linter. 19 tests in `tests/test_platforms.py`.
- **P09b done (platform-pack wiring):** the two hard-coded 9:16 seams now read the
  selected pack. `generation/final_qa.py` — `platform_family` /
  `run_final_qa` / `build_final_qa_report` take an optional `platform=` id;
  dimensions are checked against the pack's `FormatSpec.width/height` and the
  duration band defaults to the pack's `duration_band_s` (youtube_long 1920×1080
  PASSES under its pack but FAILS under the IG default; youtube_shorts applies the
  15–60s band as a **warning, not a hard fail**, keeping the G16 pattern). An
  explicit `target_band_s` still overrides. `learning/publish_package.py` —
  `metadata.aspect_ratio` is now sourced from
  `get_platform(platform).format_spec.aspect_ratio` (IG `9:16`, youtube_long
  `16:9`) instead of a hard-coded literal; `_DEFAULT_PLATFORM` imports from the
  registry. Both default to `instagram_reels`, so with no `platform=` argument the
  output is **byte-identical** to P09a; an unknown platform id **fails closed**
  (`UnknownPlatform`, ASUR-GATE-01). No cross-import added — ASUR-FIREWALL-01
  intact. 17 tests in `tests/test_platforms_wiring.py`. `hero_proof.py` is
  intentionally **unchanged** (Shorts is also 9:16/1080×1920; long-form 16:9 hero
  proof is a P09c concern per the plan's prove-small rule).
- **P09c done (long-form 16:9 hero proof + long-form publish fields):** the last two
  hard-coded 9:16 seams now read the selected pack. `generation/hero_proof.py` —
  `build_hero_proof` and `verify_render` take an optional `platform=` id; the emitted
  `target_spec` (width/height/aspect_ratio/max_duration_s) and the render verifier's
  dimension/duration checks are sourced from `get_platform(platform).format_spec`
  instead of the 1080×1920/15s literals (youtube_long → 1920×1080/`16:9`). The
  long-form hero `max_duration_s` is sourced from the pack's already-declared
  `duration_band_s` upper bound (youtube_long → 1200.0); Instagram declares no band,
  so it falls back to `MAX_HERO_DURATION_S` (15.0) — **no long-form cap is invented**
  (§7), and the default call stays byte-identical. `learning/publish_package.py` —
  when `pack.publish_fields` declares the long-form set, the package emits
  `description` (with timestamped **chapters** derived honestly from the edit plan's
  recorded clips — no invented metrics, no "%viral"), `chapters`, `tags`, and the
  human-owned placeholders `category`, `end_screen`, `cards`; the Instagram default
  declares none, so its body is byte-identical. Unknown platform id **fails closed**
  (`UnknownPlatform`) at both seams, even when `ffprobe` is absent. No cross-import —
  ASUR-FIREWALL-01 intact. 8 tests in `tests/test_platforms_p09c.py`.
- 272 unit tests pass + 6 opt-in integration tests; count derived via `python3 -m asur.tools.status`, never hand-typed.

## Not yet built
- The remaining YouTube rewire phase from `docs/build/YOUTUBE_EXTENSION_PLAN.md`:
  **P09d** (long→shorts repurpose). **P09a/P09b/P09c are done** (platform registry,
  final-QA + publish aspect-ratio wiring, and long-form hero proof + long-form publish
  fields). These are opt-in; IG Reels stays the byte-identical default.
- The remaining P00–P08 steps are human/manual by design: the **publish approval**
  (HUMAN GATE #2; the hero-proof approval at P04 is already done) and the real
  **local-GPU render** behind `asur[generation]`. **No network publish** is planned
  for YouTube either — publish stays a human-gated package (ASUR-LOCAL-01).

## Where we are (Leg C)
Leg A (P00–P03) done. Leg B (P04) hero proof **approved**. Leg C (P05–P08)
**complete**: editing, full generation + section QA + final 5-family QA, the honest
viral check, and learning & publish are all built. The entire 9-phase build is done
and every test passes; the build is **paused at HUMAN GATE #2 (publish, stage 25)** —
nothing posts without a human.

## How to read this
Phases and exit gates are defined in `PHASES.md`. Open design questions and their
conservative defaults are in `OPEN_QUESTIONS.md`. Nothing here is auto-updated —
the build commands update it at each gate.
