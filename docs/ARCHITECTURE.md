# ASUR — Architecture

> **ASUR** is a local-first, key-free AI Content Creation Operating System.
> It takes an idea and delivers a finished, platform-ready short video — then learns from how it performs.
>
> Inspired by Trinity's architecture (phases, gates, firewall, learning loop).
> **Not** a copy of Trinity's implementation. No cryptographic signing. No remote login. Runs 100% locally.

---

## 0. One-sentence version

ASUR understands what you want to say, discovers the strongest way to say it, generates and edits the video, honestly challenges whether it is good enough to perform, and learns from every result so the next video is better.

---

## 1. Founding invariants (non-negotiable)

These are the rules the whole system is built around. Everything else serves them.

| # | Invariant | What it means in practice |
|---|-----------|---------------------------|
| **ASUR-LOCAL-01** | **Local-only, key-free.** | No GitHub login, no `GITHUB_ACTOR`, no remote auth, no network call for identity or gate-clearing. Identity = local OS user + local git config (`whoami`, `git config user.name/user.email`) only. |
| **ASUR-HONEST-01** | **No fake viral score.** | Never output "93% viral". A property nobody measured is a property nobody has. Score *input quality against documented signals*, never predicted outcome. (Trinity's "measured, never claimed".) |
| **ASUR-FIREWALL-01** | **Generator and evaluator never talk.** | GENERATION and VIRAL CHECK share no channel. SCRIPT is the only bridge, via two computed projections. Prevents the author tuning content to whatever the checker rubber-stamps. |
| **ASUR-GATE-01** | **Fail closed.** | Missing input, failed sync, failed QA → the system *stops or holds*. It never silently passes unproven work to the next stage. |
| **ASUR-HUMAN-01** | **Humans own inputs, approvals, and history.** | Agents never edit human-written requirements, never auto-approve a gate, never commit on their own. Expensive/irreversible steps require a human. |
| **ASUR-PROV-01** | **Everything is provenance-bound.** | Every artifact and asset records where it came from: source, model, prompt, inputs, transforms, license, version, checksum. Answerable: "Where did this come from?" |
| **ASUR-EXPLAIN-01** | **No black box.** | Every important decision (hook choice, rejection, asset choice) carries a human-readable reason. |
| **ASUR-VERSION-01** | **Nothing is silently overwritten.** | Every artifact is versioned. History is preserved. You can compare, branch, revert. |

> **Key-free design note.** Trinity enforced integrity with SSH signatures (`ssh-keygen -Y sign/verify`). ASUR replaces *authorship proof* with *local identity* (git/OS user) and keeps only the parts that need no keys:
> - **KEEP (pure, key-free):** SHA-256 content hashing for byte-integrity & lineage; the hash-chained hand-off queue; the firewall projection function; producer≠approver separation (compare local usernames); HEAD/digest binding.
> - **DROP (key-bound):** SSH signing, DSSE/in-toto attestation envelopes, external signers, trust-root authorization, cryptographic sentinel clearances, remote submodule roster.
>
> Two uses of SHA-256 must never be conflated: **hashing for integrity (kept)** vs **signing for authorship (dropped)**.

---

## 2. The three instruments + the editing environment

ASUR splits the job across three deliberately separated instruments, plus one shared editing surface.

| Instrument | Trinity ancestor | Role | Workspace | Root report |
|------------|------------------|------|-----------|-------------|
| **SCRIPT** | ENGRAM (memory) | Intelligence, memory & learning. Ideas, research, audience, strategy, hooks, scripts, structure, CTAs, captions, content memory, performance learnings. **The only bridge between GENERATION and VIRAL CHECK.** | `.script/` | `DIRECTIVE.md` |
| **GENERATION** | FORGE (writer) | Creation & production. Visual concepts, storyboards, AI video/images, original footage, B-roll, motion graphics, audio, voice, music, compositing, rendering, final video. | `.generation/` | `EDICT.md` |
| **VIRAL CHECK** | CRUCIBLE (inspector) | Evaluation & challenge. "Does this video have a realistic chance of performing exceptionally well?" Honest, evidence-classed, never claims certainty. | `.viral/` | `VERDICT.md` |

**EDITING** is not a fourth instrument — it is the intelligent, human-controlled editing environment (timeline, clips, captions, effects, motion, versioning) that GENERATION produces into and the human steers. It serves whichever instrument needs it.

**ORCHESTRATOR** (Trinity's MAESTRO) sequences SCRIPT → GENERATION → VIRAL CHECK as isolated lanes. It owns no workspace, no memory, no report. It carries only control tokens (state, gate names, dispositions, digests) between lanes — never findings, never evaluation criteria, never creative targets. It binds to the same firewall.

```
                         ┌─────────────────────────────┐
                         │        ORCHESTRATOR         │
                         │  (sequences lanes, carries  │
                         │   only control tokens)      │
                         └──────────────┬──────────────┘
                                        │
            ┌───────────────────────────┼───────────────────────────┐
            │                           │                           │
            ▼                           ▼                           ▼
     ┌─────────────┐             ┌─────────────┐             ┌─────────────┐
     │   SCRIPT    │             │ GENERATION  │             │ VIRAL CHECK │
     │  (memory +  │             │  (produces  │             │  (evaluates │
     │ intelligence)│            │   video)    │             │   blind)    │
     └──────┬──────┘             └──────┬──────┘             └──────┬──────┘
            │                           │                           │
            │  GENERATION_VIEW          │                           │  VIRAL_VIEW
            │  (brief + hooks +         │                           │  (bundle hashes +
            │   quality floors,         │                           │   provenance + platform
            │   NO checker criteria)    │                           │   facts, NO quality targets)
            └──────────┐                │                ┌──────────┘
                       ▼                ▼                ▼
                 ┌──────────────────────────────────────────┐
                 │   THE FIREWALL (pure projection function)  │
                 │   computes both views from SCRIPT memory   │
                 │   — GENERATION & VIRAL CHECK never talk     │
                 └──────────────────────────────────────────┘
```

---

## 3. The firewall (ASUR's defensible core)

**This is the single most important architectural idea, and the market's biggest white space** — no competitor (OpusClip, Later, Sprout, etc.) separates the generator from the evaluator. OpusClip is "the fox guarding the henhouse": the same vendor generates *and* scores.

### 3.1 Why it exists

If GENERATION could see exactly what VIRAL CHECK accepts, it would stop making genuinely strong content and start making content tuned to pass the checker — reward hacking. So:

- GENERATION and VIRAL CHECK **never share a channel**.
- SCRIPT is the **only bridge**.
- SCRIPT exposes direction through **two computed projections**, each a *pure function* of (SCRIPT memory, pinned inputs, one declared evaluation instant). Recomputable; fails closed if bytes differ or the projector is absent.

### 3.2 The two views

**GENERATION_VIEW** (what the generator is allowed to see):
- Creative brief, audience, platform, promise
- Hook direction and strategic angles
- Quality / hardness **floors** (minimum bar to clear)
- Lever direction (which techniques to apply), per-category quality targets
- Cost/budget envelope, asset-license policy
- **NEVER:** VIRAL CHECK's pass criteria, gate thresholds, finding text, exploit/weakness reasoning

**VIRAL_VIEW** (what the evaluator is allowed to see):
- Rendered-bundle content hashes + claimed scope
- Provenance manifests + asset license facts
- Platform/brand facts and constraints
- Checker metadata (which rubric lane, binding identity — not fixtures)
- **NEVER (stripped by name, greppable, fails closed if leaked):** the quality/hardness **targets** — no per-dimension target, no "what good was defined as". *An evaluator holding the author's playbook grades the intent instead of the bytes.*

### 3.3 How it is enforced (key-free)

1. **Projection is a pure function** (`asur/tools/projection.py`): recomputes each view from the canonical input closure; refuses any view whose bytes don't match; fails closed if the projector is missing.
2. **Named-forbidden strip:** the projector removes target fields *by name*; a conformance check greps the produced views and fails closed if a forbidden field leaks.
3. **Local layout check:** `.script/`, `.generation/`, `.viral/` are separate workspaces; the gate refuses any VIRAL CHECK evidence file that cites the quality-target files (`.script/hardness.yaml` equivalent). No submodules, no remotes — just local directory ownership + a path/content scan.

---

## 4. The four layers

Trinity had 5 layers (the 5th was external signing authorities that mostly don't exist). ASUR collapses to **four, all local**:

| Layer | What it is | ASUR contents |
|-------|-----------|---------------|
| **L1 — Contracts / brain** | The instruction logic each instrument follows. | SCRIPT / GENERATION / VIRAL CHECK behavior specs + the orchestrator. Can be realized as agent prompts *and/or* code — ASUR ships as a running local app, not paste-in contracts. |
| **L2 — Front doors** | How a human or agent invokes a lane. | Local CLI (`asur script`, `asur generate`, `asur viral-check`, `asur run`) + optional UI dashboard. No per-runtime door files, no installed commands in external tools. |
| **L3 — Tooling** | The deterministic engine. | Python tooling: pipeline (hash-chained queue), projection (firewall), hashing/lineage, state machine, generation adapters (ComfyUI/FFmpeg/Kokoro/…), viral-check rubric engine, learning folds, provenance ledger. |
| **L4 — Workspaces & artifacts** | Local on-disk state. | `.script/ .generation/ .viral/`, artifact store, asset store, project state, version history, local git for history. **Plain local directories — no submodules, no remotes.** |

---

## 5. The run lifecycle

```
IDEA
  │
  ▼
SCRIPT lane  ──────────── research → audience → strategy → hooks → script → script-quality gate
  │  (emits GENERATION_VIEW via firewall)
  ▼
GENERATION lane ───────── creative direction → visual screenplay → asset strategy →
  │                        HERO PROOF → [human approval gate] → full generation →
  │                        section QA → final render → final QA
  │  (bundle sealed into hand-off queue; frozen)
  ▼
VIRAL CHECK lane ──────── claims sealed bundle → evaluates blind (VIRAL_VIEW) → VERDICT
  │  (SHIP / HOLD / BLOCK + per-dimension honest assessment)
  ▼
[human approval gate] → PUBLISH PACKAGE → (human publishes)
  │
  ▼
PERFORMANCE captured → LEARNING fold → SCRIPT memory updated → better next video
```

- **Gates** bracket each lane. Two require a human: **hero-proof approval** (before expensive full generation) and **final publish approval**.
- **Hand-off** between GENERATION and VIRAL CHECK is the *only* producer→consumer channel, implemented as a local hash-chained queue (see `PIPELINE.md`). The bundle is frozen (content-hashed) when sealed; GENERATION can no longer touch it.
- **Dispositions** (closed vocabulary, all instruments): **SHIP** (release-ready), **HOLD** (wait — something missing), **BLOCK** (refuse — real defect). Fail closed → default to HOLD/BLOCK when evidence is missing.
- **Local gate separation:** the local user who *produced* a stage must differ from the local user who *approves* it (compared by local git/OS username). Single-user mode is allowed but records `self-approved` explicitly in provenance (honest about the gap, never hidden).

---

## 6. What ASUR deliberately is NOT

- Not a black box that spits out a video and a vanity score.
- Not "AI because AI" — it picks the *best* source method (original footage, AI, procedural, stock) per creative need.
- Not a single-stage point tool — the **integrated loop** (idea→…→learn) is the moat.
- Not a certainty machine — it speaks in probability, evidence, and uncertainty.
- Not cloud-locked — it runs fully offline on local models; cloud is an optional upgrade.

---

## 7. Document map

| Doc | Covers |
|-----|--------|
| `ARCHITECTURE.md` (this) | Invariants, instruments, firewall, layers, lifecycle |
| `DATA_MODELS.md` | Every artifact schema, versioned entities, provenance & license fields |
| `STATE_MACHINE.md` | Project states, transitions, quality gates, local gate separation |
| `PIPELINE.md` | The 26-stage generation pipeline + firewall projection mechanics |
| `VIRAL_CHECK.md` | 12-dimension evidence framework, evidence classes, honesty rules, IG signals |
| `GENERATION_STACK.md` | Local-first model stack, license guards, cost model, asset strategy |
| `AGENTS.md` | Agent roster + orchestrator responsibilities |
| `MVP.md` | Build order, testing strategy, roadmap |
