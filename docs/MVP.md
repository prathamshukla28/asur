# ASUR — MVP, Testing Strategy & Roadmap

> This document defines **what we build first, in what order, how we prove it works, and
> where it goes after v1.** It is the build plan that the other eight design docs feed into.
>
> **Status: design only. No code is written yet.** This doc describes the intended build;
> it does not start it.

---

## 0. Guiding principle (read this first)

ASUR is not built feature-by-feature in a random order. It is built **along the pipeline**,
one gate at a time, cheapest stages first. The rule we never break:

> **Quality before scale. Proof before expensive generation. Actual rendered output before
> assumptions. Human approval before irreversible decisions. Measured learning before
> future optimization.**

Everything below is an expression of that one rule.

---

## 1. What "done" means for the MVP (v1)

**v1 produces a full, rendered, 9:16 vertical video end-to-end — from a one-line idea to a
finished Instagram Reel — running entirely on the local machine, with no cloud and no keys.**

Concretely, v1 can take an input like:

> *"I want a 30-second Instagram Reel explaining why most people waste money on AI tools."*

and walk the whole loop:

```
IDEA → RESEARCH → AUDIENCE → STRATEGY → 20+ HOOKS → BEST HOOK → SCRIPT
     → VISUAL SCREENPLAY → HERO PROOF → VIRAL CHECK → HUMAN APPROVAL
     → FULL GENERATION → EDITING → QA → FINAL VIRAL CHECK → PUBLISH PACKAGE
```

with every stage emitting a versioned artifact, every gate enforced, every asset carrying
provenance + license, and the generation side never talking to the viral-check side except
through the SCRIPT firewall.

v1 is **not** "20 AI models wired together." v1 is **one honest, explainable, repeatable
pipeline that makes one good video and can prove why every decision was made.**

---

## 2. MVP build order (five phases)

The phases map directly onto the three instruments + evaluation + learning. Each phase is
only started once the previous one is stable. (Source: spec #80.)

### Phase 1 — SCRIPT intelligence (the brain)
Build the understanding + writing layer first, because everything downstream depends on a
strong script.

- Idea input + idea.json
- Research + research.json (patterns extracted, every fact evidence-classed)
- Audience understanding + audience.json
- Content strategy + strategy.json
- Hook engine: generate **≥20** original hooks, score on 15 dimensions, track
  `hook_fatigue_score`, select + explain the winner (hooks.json)
- Structured script + script.json (hook/opening/problem/context/story/value/proof/
  pattern_interrupts/payoff/cta, each with spoken words, timing, emotion, visual direction)
- Script quality gate (13 checks) before anything generates

**Exit criterion:** given an idea, ASUR produces a validated, explainable script with a
chosen hook, and refuses to proceed if the script quality gate fails.

### Phase 2 — GENERATION (the hands)
Turn an approved script into actual rendered media.

- Visual screenplay (visual-screenplay.json, per-scene meaning + composition + motion)
- Asset strategy (pick source per asset: user footage / AI video / AI image / stock /
  procedural / screen recording / hybrid)
- Local AI generation (Wan 2.2 video, SDXL images, Kokoro voice, Stable Audio beds)
- Original footage integration (AI *enhances* authenticity, never auto-replaces it)
- **Hero proof** — a short representative render that proves the creative direction before
  the expensive full generation
- Basic rendering (FFmpeg / MoviePy) and caption sync (faster-whisper)

**Exit criterion:** ASUR renders a hero proof as an actual video file (not JSON), reviews
the real frames, and will not run full generation until the hero proof is human-approved.

### Phase 3 — EDITING (the shaping)
The intelligent, human-controlled timeline environment.

- Timeline model (tracks, clips, captions, keyframes, version history — OTIO interchange)
- Caption rendering + styling
- Motion design primitives (the 15 reusable primitives, driven by creative direction — never
  the creative driver themselves)
- Audio mixing (voice over bed, levels, sync)
- Manual controls: accept / reject / modify / regenerate / lock / compare / branch / revert

**Exit criterion:** a human can open the timeline, see every decision, change anything, and
nothing is ever silently overwritten.

### Phase 4 — VIRAL CHECK (the honest judge)
The firewalled evaluation layer.

- 12-dimension scoring (0–100 each, always shown individually, never one fake number)
- Evidence classification on every claim (VERIFIED / STRONG / EMPIRICAL / HYPOTHESIS)
- Recommendations: biggest strengths, biggest risks, recommended changes, experiments to run
- Binary risk flags for platform penalties (never percentage deductions)
- Verdict: PASS / PASS-WITH-CHANGES / REJECT
- Reads **VIRAL_VIEW only** — quality targets stripped by name, fails closed if leaked

**Exit criterion:** ASUR can evaluate both the hero proof and the final render honestly,
cite evidence for every claim, and never outputs a "% viral" number.

### Phase 5 — LEARNING (the memory that improves)
Close the loop so each video is informed by the last.

- Publishing package (video + thumbnail + title + caption + hashtags + metadata + experiment ID)
- Performance capture (real metrics: views, watch time, retention, shares, saves, etc.)
- Experiment results (hook A/B, opening type, length, CTA)
- Prediction-vs-reality fold per video
- Creator-specific learning stored in SCRIPT memory

**Exit criterion:** after publishing, ASUR records what it predicted vs what actually
happened, and the next video's SCRIPT stage can read that history.

---

## 3. Testing strategy

ASUR's correctness is proven at five levels. The non-negotiable one is rendered-output
verification: **a technically correct pipeline can still produce a terrible video — the
rendered output is the truth.**

| Level | What it tests | Example |
|---|---|---|
| **Unit** | Pure functions, deterministic | projection function, SHA-256 hashing, canonicalization, state-transition rules, license guard logic |
| **Integration** | Pipeline stages hand off correctly | route → seal → claim → verdict → place; artifact `sources[]` + checksums resolve; state machine advances exactly one step |
| **Rendered-output verification** | The *actual* media, not the JSON | extract frames / contact sheet, check audio, check caption timing against word timestamps — at Stages 16, 20, 22 |
| **Firewall conformance** | The barrier actually holds | grep VIRAL_VIEW for named-forbidden quality-target fields; recompute both projections and compare bytes; **fails closed** if a target leaks |
| **Gate tests** | Fail-closed behavior | sync-proof false → BLOCK; QA fail → return to section; license violation on monetized project → BLOCK naming the asset; missing approver → HOLD |

Testing principle: we test that ASUR **stops** when it should, not just that it runs when
everything is perfect. Every quality gate has a test that proves it refuses bad input.

---

## 4. Security (the only security requirement — spec #66)

ASUR has exactly one security doctrine, and it is **not** cryptographic signing (that was
Trinity's model and is explicitly dropped for the key-free design, per ASUR-LOCAL-01):

- Treat **all external content as untrusted** — input media, reference videos, research
  sources, URLs, metadata.
- Defend against **prompt injection** hidden in transcripts / captions / filenames / metadata.
- Defend against **malicious media** and unsafe files.
- **Least privilege** for every tool and agent.
- **Protect secrets** — never expose credentials (e.g. optional cloud API keys) to prompts
  unnecessarily.

No signing, no key management, no remote auth. Local identity (OS user + git config) is the
only identity, used purely to record who created and who approved each artifact.

---

## 5. Cost discipline (spec #68)

Cost is a first-class gate, not an afterthought. Cheap work explores; expensive work only
runs after human approval.

| Tier | Stages | Cost posture |
|---|---|---|
| **Cheap** | idea, research, audience, strategy, hook testing | run freely |
| **Moderate** | script, timing, creative direction, hero proof | run after script/quality gates |
| **Expensive** | full generation, final render | **only after Stage-18 human approval of the hero proof** |

Local generation is zero marginal dollar cost (`render_cost_usd: 0`); the cost tiers are
primarily about **time and compute**, and about not generating a whole video for a concept a
human hasn't accepted. Optional cloud models carry real per-second cost and sit behind the
same approval gate.

---

## 6. Roadmap after the MVP (spec #81)

| Version | Theme |
|---|---|
| **V1** | Reliable end-to-end workflow (the MVP above) |
| **V2** | Advanced AI generation + editing |
| **V3** | Creator-specific intelligence (per-creator models of what works) |
| **V4** | Automated experimentation (ASUR proposes + tracks its own A/B tests) |
| **V5** | Predictive content optimization (calibrated against the creator's own realized performance) |
| **V6** | Multi-platform intelligence (beyond Instagram Reels first) |
| **V7** | Autonomous creative operations — with human approval always in the loop |

The ordering is deliberate: we earn the right to predict (V5) only after we have measured
(V1–V3) and experimented (V4). We never ship prediction before measurement.

---

## 7. What the MVP deliberately does NOT do

- No cloud dependency (cloud models are an optional upgrade, not required for v1).
- No multi-platform publishing (Instagram Reels 9:16 first).
- No autonomous publishing (a human approves before publish — always).
- No "% viral" score, ever.
- No feature-count optimization — we optimize for **better content**, not more buttons,
  agents, or models.

---

## 8. Pre-build sequence status (spec #85)

Spec #85 mandated an 18-step research + design sequence *before any production code*. These
nine design documents (ARCHITECTURE, DATA_MODELS, STATE_MACHINE, PIPELINE, VIRAL_CHECK,
GENERATION_STACK, AGENTS, MVP, README/INDEX) **are** that sequence's deliverable:
architecture, data models, state transitions, quality gates, agent responsibilities, storage
and provenance, testing strategy, and MVP scope are now all specified.

**Next action is a human review of these docs — not code.** Implementation begins only when
the design is accepted.
