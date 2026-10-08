# ASUR — State Machine & Quality Gates

> ASUR is a **stage-gated** system. A project moves through explicit states. Invalid transitions are blocked.
> Gates are **real system states, not documentation** — if a gate fails, the system stops or holds; it never
> silently advances unproven work (ASUR-GATE-01, fail closed).

See `ARCHITECTURE.md` for invariants and `PIPELINE.md` for how the 26 generation stages map onto these states.

---

## 1. The project state machine

States are ordered. Each transition requires its gate to pass. A failed gate returns to the prior state (or holds).

```
DRAFT
  │  [gate: inputs inspected & understood]
  ▼
INPUTS_VERIFIED
  │  [gate: research complete, facts evidence-classed]
  ▼
RESEARCH_COMPLETE
  │  [gate: strategy approved]
  ▼
STRATEGY_APPROVED
  │  [gate: hook selected & approved]
  ▼
HOOK_APPROVED
  │  [gate: script passes script-quality gate]
  ▼
SCRIPT_APPROVED
  │  [gate: timing derived from real media + sync proof passes]
  ▼
TIMING_VERIFIED
  │  [gate: creative direction approved]
  ▼
CREATIVE_DIRECTION_APPROVED
  │  [gate: visual screenplay approved]
  ▼
SCREENPLAY_APPROVED
  │  [gate: hero proof rendered]
  ▼
HERO_PROOF_READY
  │  [gate: HUMAN approves hero proof]  ◄── human gate #1 (before expensive generation)
  ▼
HERO_PROOF_APPROVED
  │  [gate: full generation complete, no drift from approved direction]
  ▼
FULL_GENERATION
  │  [gate: all section QA + final QA pass]
  ▼
QA
  │  [gate: VIRAL CHECK disposition != BLOCK; VERDICT recorded]
  ▼
VIRAL_CHECK_APPROVED
  │  [gate: HUMAN approves final video for publish]  ◄── human gate #2
  ▼
PUBLISH_READY
  │  [human publishes to Instagram Reels]
  ▼
PUBLISHED
  │  [gate: real performance metrics captured]
  ▼
PERFORMANCE_CAPTURED
  │  [gate: learning fold computed & written to SCRIPT memory]
  ▼
LEARNED   ──────► feeds the next project
```

### Transition rules

- **Forward only, one step at a time.** You cannot jump from `DRAFT` to `FULL_GENERATION`.
- **Every forward transition is gated.** The gate name is on the arrow.
- **Failure routes.** A failed gate does **not** advance. It either:
  - returns to the **relevant prior state** for correction (e.g., sync proof fails → back to `SCRIPT_APPROVED` to fix timing), or
  - **holds** in place with a `HOLD` disposition and a recorded reason.
- **Regeneration is section-scoped.** In `FULL_GENERATION`/`QA`, a single failing section regenerates without resetting the whole project.
- **No silent overwrite.** Each transition writes a new artifact version; prior states/artifacts are retained (ASUR-VERSION-01).

---

## 2. Dispositions (closed vocabulary)

Every gate and every instrument emits exactly one disposition. Inherited from Trinity, simplified for the key-free world.

| Disposition | Meaning | Caused by |
|-------------|---------|-----------|
| **SHIP** | Release-ready. Advance. | All checks pass, evidence present, human approval where required. |
| **HOLD** | Wait. Something is missing but not broken. | Missing input, missing approval, incomplete evidence, single-user `self_approved` on a gate that wants a second human. |
| **BLOCK** | Refuse. A real defect exists. | Failed sync proof, failed QA, license violation, VIRAL CHECK finds a disqualifying risk, firewall leak detected. |

**Fail-closed default:** when evidence is missing or ambiguous, the gate defaults to **HOLD** (honest gap) or **BLOCK** (defect) — never SHIP.

Useful substates (optional, for clarity in reports):
- `HOLD:HUMAN_APPROVAL_REQUIRED` — waiting on a human gate.
- `HOLD:SELF_APPROVED` — single-user cleared their own gate; recorded honestly.
- `BLOCK:SYNC_FAILED`, `BLOCK:QA_FAILED`, `BLOCK:LICENSE_VIOLATION`, `BLOCK:FIREWALL_LEAK`.

---

## 3. The quality gates in detail

Each gate is a concrete check with a pass condition. Gates live in code (`asur/tools/`), not just prose.

| Gate | State guarded | Pass condition (fail → HOLD/BLOCK) |
|------|---------------|-------------------------------------|
| **Input inspection** | → INPUTS_VERIFIED | Every input has an `input_report` with type/duration/resolution/codec/language; no unresolved `technical_problems`. |
| **Research** | → RESEARCH_COMPLETE | Every claim in `research` carries an evidence class + source; risks listed. |
| **Strategy** | → STRATEGY_APPROVED | `strategy` has objective, audience, promise, value prop, narrative, CTA, success metric; a direction is chosen. |
| **Hook** | → HOOK_APPROVED | ≥20 hooks generated & scored (50+ for campaigns); one selected with a reason; `hook_fatigue_score` acceptable. |
| **Script quality** | → SCRIPT_APPROVED | Strong opening, clear audience, clear promise, coherent story, useful info, emotional engagement, credible claims, no needless repetition, strong payoff, appropriate CTA, platform suitability, originality, authenticity. Any fail → back to Script stage (no auto-proceed). |
| **Sync proof** | → TIMING_VERIFIED | `timing` derived from **actual media** (not estimated); `sync_proof` shows voice/subtitle/scene/visual alignment OK. Any false → **BLOCK:SYNC_FAILED**, stop, fix before continuing. |
| **Creative direction** | → CREATIVE_DIRECTION_APPROVED | Visual/emotional/motion language defined; motifs set. |
| **Screenplay** | → SCREENPLAY_APPROVED | Every scene has meaning + semantic visual concept (no generic B-roll/random zooms); generation method chosen per asset. |
| **Hero proof** | → HERO_PROOF_READY | A small representative render exists (5–15s simple / 20–40s complex) demonstrating quality, typography, motion, pacing, AI+original integration, audio, sync. **Reviewed as actual rendered output, not JSON** (ASUR stage 16). |
| **Hero-proof human approval** | → HERO_PROOF_APPROVED | A human sets `review.decision = approved`. **This is the gate before expensive full generation.** |
| **Full generation** | → FULL_GENERATION | All sections generated; continuity preserved; no drift from approved hero proof. |
| **QA** | → QA | Visual QA (no broken frames/artifacts/clipping/repetition), Audio QA (no clipping/overpowering music/sync issues), Text QA (spelling/readability/margins/contrast), Content QA (facts/script/CTA/brand), Platform QA (aspect/resolution/duration/captions/safe areas). |
| **Viral check** | → VIRAL_CHECK_APPROVED | VIRAL CHECK produces a VERDICT with disposition ≠ BLOCK. (PASS or PASS-WITH-CHANGES advances; REJECT holds.) |
| **Publish human approval** | → PUBLISH_READY | A human approves the final video. **Second human gate.** |
| **Performance capture** | → PERFORMANCE_CAPTURED | Real metrics recorded in a `performance` artifact. |
| **Learning fold** | → LEARNED | `learning` artifact compares prediction vs actual and is written to SCRIPT memory. |

---

## 4. Local gate separation (key-free producer ≠ approver)

Trinity used cryptographic signatures to prove *who* approved a gate. ASUR is **key-free** (ASUR-LOCAL-01), so it uses **local identity**:

- Each artifact records `creator.local_user` (and git name/email).
- Each approval records `review.reviewer.local_user`.
- **Rule:** for a human gate, the approver *should* differ from the creator.
- **Comparison is a pure string check** of local usernames — no keys, no remote lookup, no network.

### Single-user mode (the common case)

Most creators run ASUR solo. ASUR does **not** block this, but it is **honest about it**:

- If `reviewer.local_user == creator.local_user`, the approval is still accepted, but:
  - `review.self_approved = true` is written, and
  - the disposition is tagged `HOLD:SELF_APPROVED` in the report before the human explicitly confirms.
- The history therefore always shows *exactly* who created and who cleared each gate, and whether they were the same person.

> This preserves the one genuinely useful integrity property from Trinity (producer ≠ approver + HEAD/digest binding)
> as **pure local logic**, while fully satisfying the "no keys, no login" constraint. Nothing is faked, nothing is hidden.

### What was dropped from Trinity

- SSH signature verification on approvals → replaced by local-username comparison.
- `SAB_DISPOSITION_FORGED`, `RELEASE_DISPOSITION_INVALID`, `SAB_SENTINEL_CLEARANCE_UNSIGNED`, disposition-unbound
  (all "requires verified signature") → downgraded to **"requires a distinct-named non-producer approver via local identity"**,
  or (single-user) **"recorded as self-approved."**
- External signed pilot / independent publisher (which never existed in Trinity anyway) → **removed entirely**;
  ASUR's run is self-contained and actually delivers a finished video end-to-end.

---

## 5. HEAD / digest binding (kept, key-free)

To ensure a report describes the *actual* bytes it claims to:

- The bundle handed from GENERATION to VIRAL CHECK is **content-hashed** (SHA-256) when sealed.
- The VERDICT records the digest it evaluated.
- `place` (advancing the bundle) only succeeds if the **sealed digest, the verdict digest, and the on-disk digest all agree**.
- Mismatch → **BLOCK** (the report is talking about different bytes than exist). Pure hash comparison, no signing.
