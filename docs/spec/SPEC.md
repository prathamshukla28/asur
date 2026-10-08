# ASUR — Frozen Product Specification

> **FROZEN.** This document is the single highest source of truth for what ASUR is.
> Changes require a new ADR (`docs/adr/`) **and** a logged SPEC-GAP
> (`docs/build/OPEN_QUESTIONS.md`). It is composed only from the 9 design docs +
> README; it invents no features, models, metrics, or license facts. Where the
> original `document.pdf` and the 9 docs diverge, the 9 docs win and the divergence
> is a SPEC-GAP (never silently reconciled).

ASUR is a **local-first, key-free AI Content Creation OS**. From a one-line idea it
produces a full, rendered 9:16 vertical Instagram Reel, end to end, 100% locally,
then learns from real performance so each video is informed by the measured
performance of the last. Its defensibility is the **closed loop** — an honest,
firewalled viral evaluator plus cross-video learning memory.

---

## 1. The 8 founding invariants (supreme law)

1. **ASUR-LOCAL-01** — 100% local, key-free. No remote auth, no GitHub login, no
   network for identity. Identity = local OS user (`whoami`) + git config
   `user.name`/`user.email` only. **Any local user can clear gates.**
2. **ASUR-HONEST-01** — never a single fake "%viral" number.
3. **ASUR-FIREWALL-01** — GENERATION and VIRAL CHECK never communicate directly;
   SCRIPT bridges them via two computed projections. GENERATION_VIEW gets quality
   **floors** + brief + hooks but **not** the viral-checker's pass criteria;
   VIRAL_VIEW gets rendered-bundle hashes + provenance + platform facts but the
   quality/hardness **targets are stripped by name** (greppable; fails closed if
   leaked).
4. **ASUR-GATE-01** — fail closed. A missing instrument/input/approval caps the
   disposition at HOLD or BLOCK.
5. **ASUR-HUMAN-01** — humans own inputs, approvals, and history. No machine
   commits.
6. **ASUR-PROV-01** — every asset is provenance- and license-bound.
7. **ASUR-EXPLAIN-01** — no black box; every decision is explainable.
8. **ASUR-VERSION-01** — nothing is silently overwritten (versioned artifacts +
   freeze + checksum).

## 2. Instruments, editing env, orchestrator

| System | Ancestor | Workspace | Root report | Role |
|---|---|---|---|---|
| **SCRIPT** | ENGRAM | `.script/` | `DIRECTIVE.md` | Intelligence + memory + learning. The **only** firewall bridge; computes both projections. |
| **GENERATION** | FORGE | `.generation/` | `EDICT.md` | Creation/production. Reads GENERATION_VIEW only. |
| **VIRAL CHECK** | CRUCIBLE | `.viral/` | `VERDICT.md` | Evaluation. Reads VIRAL_VIEW only. |
| **EDITING** | — | shared | — | Shared, **human-controlled editing env — NOT a 4th instrument**. |
| **ORCHESTRATOR** | MAESTRO | — | — | Sequences lanes; carries only control tokens (state/gate/disposition/digest/residency); never findings/criteria/targets. |

## 3. The firewall and its two views

- **GENERATION_VIEW**: creative brief + selected hooks + quality **floors**. Never
  the viral-checker pass criteria, gate thresholds, or finding text.
- **VIRAL_VIEW**: rendered-bundle hashes + provenance + platform facts. The
  quality/hardness **targets are stripped by name** (a fixed, greppable list).
- **Three enforcement mechanisms**: (1) a **pure projection function** that
  recomputes both views and fails closed on mismatch; (2) a **named-forbidden
  strip + grep** conformance test; (3) a **local layout / static cross-import
  check** (GENERATION and VIRAL CHECK code may not import each other).
- Rationale: "an evaluator holding the author's playbook grades the intent, not the
  bytes." This structural separation is the moat — no competitor has it.

## 4. The 26-stage pipeline

0 INPUTS · 1 INPUT INSPECTION · 2 SOURCE-OF-TRUTH · 3 CONTENT UNDERSTANDING ·
4 RESEARCH · 5 STRATEGY · 6 HOOK GEN · 7 SCRIPT GEN · 8 TIMING · **9 SYNC PROOF
(hard gate — STOP if wrong)** · **10 FREEZE (immutable + checksum)** · 11 CREATIVE
DIRECTION · 12 VISUAL SCREENPLAY · 13 ASSET STRATEGY · 14 AI+ORIGINAL FOOTAGE PLAN ·
**15 HERO PROOF** · 16 RENDER/REVIEW ACTUAL OUTPUT · 17 SELF-CRITIQUE + VIRAL CHECK
(hero proof; firewall active) · **18 HUMAN APPROVAL (gate #1)** · 19 FULL
GENERATION · 20 SECTION-BY-SECTION QA · 21 FINAL RENDER · 22 FINAL QA · 23 FINAL
VIRAL CHECK · 24 PUBLISH PACKAGE · **25 PUBLISH (human gate #2)** ·
26 PERFORMANCE → LEARNING.

- "Rendered output is truth" at stages 16 / 20 / 22 — evaluate the actual video,
  not JSON.
- Cost discipline: cheap 0–6, moderate 7–16, expensive 19–21 (behind stage-18
  approval). Local render cost = 0.
- Firewall in motion: `seal → claim → verdict → place` (SHA-256 + atomic O_EXCL;
  bundle frozen on seal).
- Real-world validation: **PYAAR? by Naam Sujal** (Hindi rap lyric video built
  end-to-end locally) proved three rules — freeze + checksums, review a picture not
  code, prove quality on a small 5–15s piece first. (ASUR default render remains
  FFmpeg/MoviePy; the case study used Remotion, which is optional only.)

## 5. The 18-state project machine + 15 quality gates

DRAFT → INPUTS_VERIFIED → RESEARCH_COMPLETE → STRATEGY_APPROVED → HOOK_APPROVED →
SCRIPT_APPROVED → TIMING_VERIFIED → CREATIVE_DIRECTION_APPROVED → SCREENPLAY_APPROVED
→ HERO_PROOF_READY → **HERO_PROOF_APPROVED (human gate #1)** → FULL_GENERATION → QA →
VIRAL_CHECK_APPROVED → **PUBLISH_READY (human gate #2)** → PUBLISHED →
PERFORMANCE_CAPTURED → LEARNED.

- Forward-only, one-step, gated transitions.
- Dispositions **SHIP / HOLD / BLOCK** with substates (HOLD:HUMAN_APPROVAL_REQUIRED,
  HOLD:SELF_APPROVED, BLOCK:SYNC_FAILED, BLOCK:QA_FAILED, BLOCK:LICENSE_VIOLATION,
  BLOCK:FIREWALL_LEAK).
- 15 quality gates across the pipeline.
- **Local gate separation**: producer ≠ approver by comparing local principals
  (pure string compare, no keys/network). Single-user is allowed but recorded
  honestly as HOLD:SELF_APPROVED.
- HEAD/digest binding: sealed digest = verdict digest = on-disk digest, else BLOCK.

## 6. Data models

- **Universal artifact envelope**: `artifact_id` (`<kind>-<shorthash>`), `kind`,
  `version` (int), `schema_version` (`asur.artifact/v1`), `project_id`,
  `created_at` (UTC), `creator` {agent, local_user, git_name, git_email},
  `sources[]` {artifact_id, version, checksum}, `status`
  (draft|ready|approved|rejected|superseded), `review` {reviewer, decision, reason,
  reviewed_at, self_approved}, `checksum` (SHA-256 over the **canonical body
  only**), `supersedes`, `body`.
- **Per-asset provenance + license block**: `asset_id`, `media_type`, `origin`
  (user_original|ai_generated|procedural|licensed_stock|screen_recording|hybrid),
  `provenance` {model, model_version, prompt, seed, input_assets[], transforms[],
  editor, generated_at, generation_time_s, render_cost_usd (0 for local)},
  `license` {name, commercial_ok, revenue_cap_usd, territory_exclusions[],
  training_data_provenance, source_url, notes}, `checksum`, `file_path`.
- **License guard**: monetized + commercial_ok:false, OR a revenue-cap/territory
  violation → gate fails closed, naming the offending asset.
- **17 artifact kinds**: idea, input_report, research, audience, strategy, hooks,
  script, timing, sync_proof, creative_direction, visual_screenplay, asset_plan,
  generation_plan, edit_plan, qa_report, viral_check, publish_package, performance,
  learning.
- **script.json** sections: hook, opening, problem, context, story, value, proof,
  pattern_interrupts[], payoff, cta — each with spoken_words, timing, emotion,
  intended_reaction, visual_direction, onscreen_text, broll_requirements,
  transition_requirements, audio_direction.
- **Hook intelligence** (per hook): metadata {hook, language
  (en|hi|hinglish|indian-en|mr), category, pattern, psychology[], emotion, promise,
  audience_stage, content_types[], strength, originality{verdict, nearest_prior,
  distance}}, 15 score dimensions, hook_fatigue_score, template_fatigue_score,
  first-3-seconds blueprint (0.0–0.5 pattern interrupt / 0.5–1.5 core hook /
  1.5–2.5 curiosity-promise / 2.5–3.0 transition), A/B variants, persistent hook
  memory. Principle: optimize Attention → Retention → Satisfaction → Value →
  Shareability → long-term trust, **not** clicks.
- **Multilingual**: language is first-class on hooks and scripts. Natural Hindi /
  Hinglish / English / Indian-English / Marathi — never literal translation;
  preserve psychological intent.
- **Timeline model**: id, version, fps, resolution 1080x1920 (9:16), tracks
  (video/audio/text/graphics/effects/transitions), clips, markers, scenes, OTIO
  (Apache-2.0) interchange, 15 editing primitives ("never the creative driver").
- **SCRIPT memory entities**: Creator, Brand, Audience, Content memory, Knowledge
  (evidence-classed), Content knowledge graph. All versioned and provenance-bound.

## 7. VIRAL CHECK — 12 dimensions, 4 evidence classes, 3 honesty rules

- **12 dimensions**, each 0–100, always shown individually: Attention, Retention,
  Satisfaction, Value, Shareability, Saveability, Replayability, Originality,
  Authenticity, Visual Quality, Audience Fit, Platform Fit.
- **4 evidence classes** on every claim: VERIFIED FACT, STRONG EVIDENCE, EMPIRICAL
  OBSERVATION (this creator's own data), HYPOTHESIS. Every prediction = Prediction +
  Confidence + Evidence + Uncertainty.
- **3 honesty rules**: (1) never a single "%viral" number — score input quality
  against documented signals; (2) separate "signal exists" (VERIFIED) from "weight
  known" (UNKNOWN); (3) penalties are binary risk flags, not % deductions.
- Verdict: **PASS / PASS-WITH-CHANGES / REJECT**.
- Platform signal KB (Oct 2026 baseline, data not weighting): IG Reels top-3 =
  watch time, likes, sends; demotes low-res/watermarked/muted/bordered/
  majority-text/reposted; 10+ copies/30 days ineligible. TikTok completion >
  engagement. YT Shorts % chose-to-view. Treated as VERIFIED about the *statement*,
  not about live weighting.

## 8. Locked generation stack

- **Video**: Wan 2.2 TI2V-5B (Apache, default), via ComfyUI headless.
- **Images**: SDXL (OpenRAIL++, default local B-roll). Trap: FLUX dev
  (non-commercial).
- **Voice**: Kokoro-82M (Apache, default). Trap: XTTS v2 (CPML, non-commercial).
- **Music/SFX**: Stable Audio 3.0. Trap: MusicGen (CC-BY-NC). Avoid: Suno/Udio.
- **Render**: FFmpeg + MoviePy + OTIO (**locked default, cost 0**). Remotion
  optional (per-render cost).
- **Captions**: faster-whisper (MIT, word-level timestamps).
- **Cloud (optional, later)**: Veo 3.1 Fast / Runway Gen-4 Turbo (clips ≤ ~20s →
  sectioned generation + stitch; persist expiring URLs immediately).
- **Sora is removed** (API sunset 2026-09-24) and must never appear in any option
  set.
- License is a first-class provenance field; the trap list is hard-coded and
  enforced by the license guard.

## 9. MVP, security, roadmap

- **v1 "done"**: a full rendered 9:16 Instagram Reel from a one-line idea, 100%
  local, every stage a versioned/checksummed/explainable artifact behind gates.
- **5-phase MVP build order**: SCRIPT → GENERATION → EDITING → VIRAL CHECK →
  LEARNING (implemented over P00–P08; see `docs/build/PHASES.md`).
- **Guiding principle**: quality before scale; proof before expensive generation;
  actual rendered output before assumptions; human approval before irreversible
  action; measured learning before optimization.
- **Security (spec #66 — the ONLY security requirement, and it is NOT crypto
  signing)**: treat all external content as untrusted; defend against prompt
  injection (in transcripts/filenames/metadata) and malicious media; least
  privilege; protect secrets.
- **Testing (5 levels)**: unit (pure funcs) · integration (pipeline hand-off) ·
  rendered-output verification (actual frames/audio/captions on tiny fixtures) ·
  firewall conformance (greppable, fails closed) · gate fail-closed.
- **Roadmap V1–V7**: V1 reliable end-to-end → V2 advanced gen/edit → V3
  creator-specific intelligence → V4 automated experimentation → V5 predictive
  optimization (calibrated vs own realized performance) → V6 multi-platform → V7
  autonomous operations with human approval.

---

_End of frozen spec. To change anything here: open an ADR + a SPEC-GAP._
