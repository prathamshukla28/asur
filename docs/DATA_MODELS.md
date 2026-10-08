# ASUR — Data Models

> Every stage of ASUR produces a **versioned artifact** on local disk. Artifacts are the memory of the system:
> they are how one stage talks to the next, how the firewall computes its views, how history is preserved,
> and how learning happens. This document defines every entity and every field.

See `ARCHITECTURE.md` for the invariants these models serve — especially **ASUR-PROV-01** (everything provenance-bound),
**ASUR-VERSION-01** (nothing silently overwritten), and **ASUR-LOCAL-01** (identity = local git/OS user, no keys).

---

## 1. Core principles for all data

1. **Artifact-first.** Every meaningful decision is written to disk as a structured JSON artifact before the next stage runs.
2. **Versioned, never overwritten.** A change creates a new version; the old one stays. You can compare, branch, revert.
3. **Content-hashed.** Every artifact and asset carries a SHA-256 checksum over its canonical bytes (integrity + lineage, *not* signing).
4. **Provenance-bound.** Every artifact records who/what made it and from which source artifacts.
5. **Local identity.** `creator` / `reviewer` / `approver` are local git/OS usernames (`whoami`, `git config user.name`). No remote accounts, no keys.
6. **Honest status.** Status is explicit (`draft`, `ready`, `approved`, `rejected`, `superseded`). Nothing is implied.

---

## 2. The universal artifact envelope

Every artifact JSON file shares this envelope. Stage-specific fields live under `body`.

```jsonc
{
  "artifact_id": "hooks-7f3a9c2e",          // stable id: "<kind>-<short-hash>"
  "kind": "hooks",                           // one of the artifact kinds in §4
  "version": 3,                              // integer, increments; previous versions retained
  "schema_version": "asur.artifact/v1",      // envelope schema version
  "project_id": "proj-20261007-ab12",        // owning project
  "created_at": "2026-10-07T09:14:33Z",      // UTC
  "creator": {                               // local identity, NO keys
    "agent": "hook-agent",                   // which ASUR agent produced it (or "human")
    "local_user": "ravi",                    // whoami
    "git_name": "Ravi K",                    // git config user.name
    "git_email": "ravi@local"                // git config user.email
  },
  "sources": [                               // artifact lineage: what this was derived from
    { "artifact_id": "strategy-1a2b", "version": 2, "checksum": "sha256:..." },
    { "artifact_id": "audience-9d8c", "version": 1, "checksum": "sha256:..." }
  ],
  "status": "ready",                         // draft | ready | approved | rejected | superseded
  "review": {                                // null until reviewed
    "reviewer": { "local_user": "ravi", "git_name": "Ravi K" },
    "decision": "approved",                  // approved | rejected | changes_requested
    "reason": "Hook #4 chosen; strongest curiosity + payoff fit.",
    "reviewed_at": "2026-10-07T09:20:01Z",
    "self_approved": false                   // true if creator==approver (single-user mode) — recorded honestly
  },
  "checksum": "sha256:9a1f...",              // over canonical body bytes
  "supersedes": "hooks-7f3a9c2e@2",          // previous version this replaces, or null
  "body": { /* stage-specific, see §4 */ }
}
```

> **`self_approved`** is the key-free analogue of Trinity's producer≠approver separation. If the local user who created the
> artifact is the same as the one approving it, ASUR does not pretend otherwise — it sets `self_approved: true` so the gap is
> visible in history (ASUR-HONEST-01).

---

## 3. Provenance & license (first-class, per asset)

Research flagged **license as a first-class provenance field** (FLUX-dev, XTTS-v2, MusicGen, HunyuanVideo, Suno/Udio are traps).
Every *generated or sourced media asset* carries this block, separate from the artifact envelope:

```jsonc
{
  "asset_id": "asset-c4d5e6",
  "media_type": "video",                     // video | image | audio_voice | audio_music | audio_sfx | footage | graphic | screen_recording
  "origin": "ai_generated",                  // user_original | ai_generated | procedural | licensed_stock | screen_recording | hybrid
  "provenance": {
    "model": "Wan2.2-TI2V-5B",               // tool/model that made it
    "model_version": "2.2",
    "prompt": "slow push-in on a cracked phone screen, moody light",
    "seed": 184422,
    "input_assets": ["asset-aa11", "asset-bb22"],   // for I2V / composites
    "transforms": [                           // ordered edit operations applied
      { "op": "color_grade", "params": { "lut": "teal_orange" } },
      { "op": "speed_ramp",  "params": { "from": 1.0, "to": 0.5 } }
    ],
    "editor": { "agent": "generation-agent", "local_user": "ravi" },
    "generated_at": "2026-10-07T10:02:11Z",
    "generation_time_s": 540,                 // for cost/observability
    "render_cost_usd": 0.0                     // 0 for local models; >0 for cloud/Remotion
  },
  "license": {                                // THE guard rails
    "name": "Apache-2.0",                     // e.g. Apache-2.0, OpenRAIL++-M, CPML, CC-BY-NC-4.0, StabilityAI-Community
    "commercial_ok": true,                    // hard gate for monetized output
    "revenue_cap_usd": null,                  // e.g. 1000000 for Stable Audio community; null = none
    "territory_exclusions": [],               // e.g. ["EU","UK","KR"] for HunyuanVideo
    "training_data_provenance": "undisclosed",// disclosed | undisclosed | proprietary
    "source_url": "https://huggingface.co/...",
    "notes": "Unconditional commercial use."
  },
  "checksum": "sha256:...",                    // over the asset bytes
  "file_path": ".generation/assets/asset-c4d5e6.mp4"
}
```

**License guard rule (enforced at asset-strategy + QA gates):** if the project is monetized and any asset has
`commercial_ok: false` (FLUX-dev output, XTTS-v2 voice, MusicGen track) or violates `revenue_cap_usd` /
`territory_exclusions`, the gate **fails closed** (ASUR-GATE-01) and names the offending asset + license.

---

## 4. The artifact catalog (one per lifecycle stage)

Each entry lists `kind` and the notable `body` fields. All share the §2 envelope.

| kind | Produced by | Key `body` fields |
|------|-------------|-------------------|
| `idea` | human / research-agent | `statement`, `what_communicated`, `who_for`, `why_matters`, `problem_solved`, `target_emotion`, `desired_action`, `platform`, `duration_target_s` |
| `input_report` | generation (stage 0) | per input file: `file_type`, `duration`, `resolution`, `aspect_ratio`, `fps`, `codec`, `audio_props`, `language`, `transcript_available`, `visual_characteristics`, `scene_structure`, `missing_info[]`, `technical_problems[]`, `copyright_provenance` |
| `research` | research-agent | `topic_findings[]`, `audience_findings[]`, `competitor_findings[]`, `trends[]`, `supporting_facts[]` (each w/ evidence class + source), `counterarguments[]`, `risks[]` |
| `audience` | audience-agent | `demographics`, `interests[]`, `pain_points[]`, `desires[]`, `fears[]`, `objections[]`, `awareness_level`, `language`, `content_preferences[]` |
| `strategy` | strategy-agent | `objective`, `audience_ref`, `format`, `platform`, `target_emotion`, `core_promise`, `value_prop`, `narrative_structure`, `cta`, `success_metric`, `directions[]` (educational/controversial/story/curiosity/…), `direction_scores{}` |
| `hooks` | hook-agent | `hooks[]` (each: `text`, `direction`, `first_frame_concept`, `first_motion_concept`, `scores{15 dims}`, `rank`, `reason`, **+ hook-intelligence metadata — see §4.1**), `hook_fatigue_score`, `template_fatigue_score`, `selected_hook_id` |
| `script` | script-agent | `language`, + structured sections: `hook`, `opening`, `problem`, `context`, `story`, `value`, `proof`, `pattern_interrupts[]`, `payoff`, `cta` — each section: `spoken_words`, `timing`, `emotion`, `intended_reaction`, `visual_direction`, `onscreen_text`, `broll_requirements`, `transition_requirements`, `audio_direction` |
| `timing` | timing-agent | `word_timestamps[]`, `phrase_timestamps[]`, `sentence_timestamps[]`, `scene_timestamps[]`, `beat_map`, `pause_map`, `emphasis_map` (derived from actual media, not estimated) |
| `sync_proof` | generation (stage 6) | `voice_sync_ok`, `subtitle_timing_ok`, `scene_timing_ok`, `visual_alignment_ok`, `discrepancies[]` — gate fails closed if any false |
| `creative_direction` | visual-agent | `visual_language{color,composition,texture,lighting,typography,framing,camera}`, `emotional_language{}`, `motion_language{}`, `recurring_motifs[]` |
| `visual_screenplay` | visual-agent | `scenes[]` (each: `scene_id`, `start`, `end`, `spoken_content`, `meaning`, `hero_words[]`, `visual_concept`, `semantic_metaphor`, `composition`, `typography{}`, `camera{}`, `background{}`, `graphics{}`, `motion{}`, `transition{}`, `intensity`, `assets[]`, `generation_method`) |
| `asset_plan` | generation-agent | per asset: `asset_ref`, `source_strategy` (user_original/ai_video/ai_image/procedural/licensed_stock/screen_recording/existing/hybrid), `rationale`, `model_choice`, `estimated_cost`, `license_precheck` |
| `generation_plan` | generation-agent | ordered generation jobs: `job_id`, `target_asset`, `model`, `params`, `depends_on[]`, `cost_estimate`, `cloud_or_local` |
| `edit_plan` | editing-agent | timeline composition (see §5 Timeline), chosen editing primitives per section + rationale |
| `qa_report` | qa-agent | `visual_qa{}`, `audio_qa{}`, `text_qa{}`, `content_qa{}`, `platform_qa{}` — each a list of checks w/ pass/fail + evidence (frame refs, waveform refs) |
| `viral_check` | viral-check-agent | see `VIRAL_CHECK.md` — 12 dimension scores, evidence class per claim, risk flags, confidence, recommendations. **Never a single % number.** |
| `publish_package` | generation-agent | `final_video_ref`, `thumbnail_ref`, `title`, `caption`, `hashtags[]`, `cta`, `platform_metadata{}`, `content_category`, `experiment_id` |
| `performance` | analytics-agent | `views`, `reach`, `watch_time`, `avg_watch_time`, `retention_curve[]`, `completion_rate`, `replays`, `shares`, `saves`, `comments`, `likes`, `follows`, `profile_visits`, `conversions`, `captured_at` |
| `learning` | learning-agent | `prediction{}`, `actual{}`, `difference{}`, `what_worked[]`, `what_failed[]`, `surprises[]`, `drop_off_points[]`, `next_experiment{}` → folded into SCRIPT memory |

---

## 4.1 Hook intelligence (the deep hook layer)

A hook is not a line of text — it is a **psychological object paired with a
visual opening**, and ASUR treats it as first-class. The hook-agent attaches this
metadata to every hook in `hooks[]`:

```jsonc
{
  "hook": "Teen baar fail hua... phir ye trick chali.",   // the actual hook (any language)
  "language": "hinglish",                 // en | hi | hinglish | indian-en | mr | ...
  "category": "experience",               // experience | tip | howto | story | contrarian | authority | data | ...
  "pattern": "multiple_attempts_then_winner",
  "psychology": ["curiosity", "proof", "comparison"],
  "emotion": "determination",
  "promise": "a trick that finally works after repeated failure",
  "audience_stage": "beginner",           // beginner | intermediate | advanced
  "content_types": ["educational", "storytelling", "review"],
  "strength": "high",                     // high | medium | low
  "originality": { "verdict": "fresh_execution", "nearest_prior": "...", "distance": 0.0 }
}
```

**First-3-seconds blueprint** — the opening is designed as a timed unit, not a
sentence (adapt the exact split to the real format/pacing):

| time | element |
|------|---------|
| 0.0–0.5s | visual pattern interrupt (first frame stops the scroll) |
| 0.5–1.5s | core hook (the spoken/on-screen hook line) |
| 1.5–2.5s | curiosity / promise (why keep watching) |
| 2.5–3.0s | transition into value (deliver, don't stall) |

**Hook + visual = one unit.** A hook is always evaluated as
`hook + first_frame + first_motion + audio + onscreen_text` together — never the
words alone. This is the STAGE-12 "first three seconds" creative unit.

**Hook A/B testing** (feeds the experimentation engine, see `VIRAL_CHECK.md §8`):
same video, variants A/B/C/D each with a *different hook* (e.g. Curiosity /
Contrarian / Story / Data), the rest of the video held constant where sensible.
Track which hook wins on retention, watch-time, completion, shares, saves,
comments, follows → fold the result into SCRIPT hook memory.

**Hook memory** (persistent, in SCRIPT — see §7): every hook generated / used /
rejected / published, with its metadata (category, audience, topic, platform,
language) and its *prediction-vs-actual* performance. Over time this learns
**which hook structures work for which audience/topic/creator** — e.g. for
Creator X: "Contrarian +24% retention, Story +12%, generic list −8%". These are
**EMPIRICAL OBSERVATIONS** from that creator's own data (see evidence classes in
`VIRAL_CHECK.md`), never universal claims.

**Originality engine.** Each new hook is compared against (a) the creator's
previous hooks, (b) common templates, (c) recent viral hooks, (d) known pattern
library — to distinguish *familiar structure + fresh execution* (fine) from
*generic copy* (flagged). Output lands in the `originality` field above.

**Template fatigue.** Overused templates ("3 things you need to know", "Nobody
tells you…", "Here's the secret…", "Stop doing this") are tracked in
`template_fatigue_score`; ASUR will not keep producing the same opening structure
unless it is genuinely the right call.

**Hook principle (what we optimize).** The hook exists to maximize
**Attention → Retention → Satisfaction → Value → Shareability → long-term
audience trust** — *not* raw clicks. A hook that grabs attention but disappoints
the payoff earns a **low viral-check score**. ASUR explicitly learns the
difference between clickbait and curiosity-with-payoff.

### 4.1.1 Multilingual hooks & scripts (first-class)

`language` is a first-class field on **both hooks and scripts** — not just
captions. ASUR must produce natural **Hindi, Hinglish, English, Indian-English,
and Marathi** hooks and spoken scripts (regional-language expansion is a planned
roadmap item).

**Rule: never literal translation.** A hook/script is adapted by preserving its
**psychological intent** (curiosity, promise, emotion, pattern) while rewriting
the wording into how people *actually speak* that language — code-switching,
slang, and rhythm included. A word-for-word translation that sounds unnatural is
a failure, even if "correct". (The real-world validation video in `PIPELINE.md`
is a Hindi/Hinglish/Marathi rap, which exercises exactly this.)

---

## 5. Timeline model (EDITING environment)

The timeline is a first-class versioned entity. Every object has a **stable identity + version history** (ASUR-VERSION-01).

```jsonc
{
  "timeline_id": "tl-55aa",
  "version": 4,
  "project_id": "proj-20261007-ab12",
  "fps": 30,
  "resolution": { "w": 1080, "h": 1920 },      // 9:16 Reels
  "duration_s": 30.0,
  "tracks": [
    {
      "track_id": "trk-video-1", "type": "video",
      "clips": [
        {
          "clip_id": "clip-01", "asset_ref": "asset-c4d5e6",
          "in": 0.0, "out": 3.2, "timeline_start": 0.0,
          "keyframes": { "scale": [...], "position": [...], "opacity": [...] },
          "speed": 1.0, "crop": {...}, "masks": [...], "overlays": [...],
          "primitive": "CameraPush",            // optional editing primitive applied
          "version_history": [ /* prior states */ ]
        }
      ]
    },
    { "track_id": "trk-audio-voice", "type": "audio", "clips": [ ... ] },
    { "track_id": "trk-captions",    "type": "text",  "clips": [ ... ] },
    { "track_id": "trk-graphics",    "type": "graphic", "clips": [ ... ] }
  ],
  "markers": [ { "t": 1.0, "label": "beat" } ],
  "scenes": [ { "scene_id": "sc-1", "start": 0.0, "end": 5.0 } ]
}
```

- Track/clip types: **video, audio, text (captions), graphics, effects, transitions.**
- Per-clip editable: in/out, timeline position, scale, crop, position, opacity, speed, masks, overlays, keyframes.
- **Editing primitives** (reusable, but never the creative driver — the creative concept decides usage):
  `TextReveal, WordPunch, CameraPush, CameraPull, BlurTransition, CutOnBeat, HighlightWord, SubtitleEmphasis,
  ImageParallax, MotionBackground, ShapeReveal, ScreenShake, SpeedRamp, MaskReveal, TrackingText`.
- **Timeline interchange** uses OpenTimelineIO (OTIO, Apache-2.0) so the model can hand off cleanly between tools and renderers.

---

## 6. Persistent memory entities (SCRIPT)

These are long-lived, cross-project, versioned stores — the system's accumulating intelligence.

| Entity | Holds |
|--------|-------|
| **Creator** | identity, niche, expertise, tone, vocabulary, personality, preferred formats/platforms, visual identity, audience, goals |
| **Brand** | positioning, values, colors, typography, language, forbidden claims, compliance rules, products, services, brand voice |
| **Audience** | demographics, interests, pain points, desires, fears, objections, awareness level, language, content preferences |
| **Content memory** | previous ideas/scripts, published videos, hooks used, formats used, topics covered, performance, failed/successful experiments |
| **Knowledge** | research, verified facts, sources, claims, citations, expert info, market info, platform info — **each fact tagged with an evidence class** (see `VIRAL_CHECK.md`) |
| **Content knowledge graph** | relationships between creators ↔ topics ↔ audiences ↔ hooks ↔ scripts ↔ videos ↔ assets ↔ formats ↔ experiments ↔ performance |

---

## 7. Top-level entity relationships

```
User ──owns──> Creator ──has──> Brand
Creator ──runs──> Project
Project ──> Idea ──> Research ──> Audience ──> Strategy ──> Hooks ──> Script
Script ──> Timing ──> CreativeDirection ──> VisualScreenplay ──> AssetPlan ──> GenerationPlan
GenerationPlan ──produces──> Asset[] ──composed into──> Timeline ──rendered to──> Video
Video ──> QAReport ──> ViralCheck ──> PublishPackage ──> Publication
Publication ──> Performance ──> Learning ──folds into──> SCRIPT memory (Creator/Content/Knowledge/Graph)
Experiment ──links──> Hooks/Script/Strategy choices ──measured by──> Performance
```

Every entity in this diagram is **versioned** (ASUR-VERSION-01) and **provenance-bound** (ASUR-PROV-01).
