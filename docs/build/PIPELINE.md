# ASUR Build Pipeline (Automation Runbook)

> **What this is.** A single runbook so you don't have to drive every phase by hand.
> It chains the build phases **P00 → P08** in order, runs the full tests at the end,
> fixes what's broken, and verifies — **but it stops automatically at every point that
> needs you** (a human). You run **one** command (`/all-phases`) and watch; it pauses
> and asks only when it must.
>
> **Not to be confused with** `docs/PIPELINE.md`, which is the 26-stage *content*
> pipeline (idea → rendered video). **This** file is the *developer build* pipeline
> (how the software itself gets built, phase by phase).

---

## 0. The one rule that makes "automatic" safe

Automatic does **not** mean unattended-irreversible. The 8 invariants still rule.
The runbook may chain as much as it likes, but it **must stop and wait for a human**
whenever it hits any of these (this is `ASUR-HUMAN-01` + `ASUR-GATE-01`):

- A **human gate** in the state machine — **hero-proof approval (stage 18)** and
  **publish approval (stage 25)**. These are never self-cleared.
- Any **BLOCK** or **HOLD** disposition from a gate (tests red, firewall leak,
  license violation, missing input). Fail closed: stop, don't push past it.
- Any **open SPEC-GAP** that blocks the current phase.
- Any **settings change, paid/cloud service, API key, publishing, or data deletion**.

Everywhere else, it keeps going on its own.

---

## 1. The order (developer-first, then test-fix-verify)

You asked for: **build all phases first, then test, fix, and verify — optimized.**
Here is how that maps to ASUR safely. Each phase still writes its *own* tests first
(that's non-negotiable — it's how we know a phase works), but the **heavy full-suite
verification and cross-phase fix pass happens once at the end**, so you're not
blocked between phases.

```
   BUILD PASS (phases, in order)              VERIFY PASS (once, at the end)
   ──────────────────────────────            ──────────────────────────────
   P00  Foundations & ADRs                    1. Full test suite (all phases)
   P01  SCRIPT completion                     2. Firewall conformance (grep)
   P02  State machine + orchestrator + CLI    3. Fix any failures (affected tests
   P03  Firewall + hand-off queue                in the loop, full suite once more)
   P04  GENERATION + HERO PROOF  ⟵ HUMAN #1    4. Independent verifier re-runs
   P05  EDITING                                  every phase's exit gate
   P06  Full generation + QA                   5. /report — the final dashboard
   P07  VIRAL CHECK
   P08  LEARNING + PUBLISH       ⟵ HUMAN #2
```

Within each phase the micro-order is still the AGENTS.md protocol
(**plan → tests-first → build → parallel review → fix affected → verify → gate →
commit**). The optimization is: between phases we only run the **affected** tests to
stay fast; the **full** suite + firewall grep + independent re-verify is the big
pass that runs **once** after the build reaches its first human gate (P04) and again
at the end (P08).

### Two natural stopping points
The chain can't actually run unattended all the way to P08, because **P04 and P08
require a human**. So in practice `/all-phases` runs in **three legs**:

| Leg | Phases | Ends at |
|-----|--------|---------|
| **Leg A** | P00 → P03 | fully automatic; stops only on BLOCK/HOLD/SPEC-GAP |
| **Leg B** | P04 | stops at **HUMAN GATE #1** (hero-proof) — you approve the rendered proof |
| **Leg C** | P05 → P08 | automatic to **HUMAN GATE #2** (publish) — you approve publishing |

You re-run `/all-phases` after each human approval and it picks up where it left off.

---

## 2. How to run it

```
/all-phases          # drive the whole chain from the current phase, stop at gates
/status              # quick: where are we, tests green?, next gate   (read-only)
/report              # deep: full dashboard + per-phase + SPEC-GAPs   (read-only)
/build-phase 3       # build just one phase by hand (P03)
/verify-phase 3      # re-verify one phase's exit gate, read-only
/fix-bug <desc>      # test-first fix of a single bug
```

Normal use is just: **`/all-phases`**, then answer when it stops, then `/all-phases`
again. Call **`/status`** anytime for a one-line health check, or **`/report`** when
you want the full picture.

---

## 3. What `/all-phases` does, step by step

1. **Read state.** Current phase + state from `docs/build/STATUS.md`; open SPEC-GAPs
   from `docs/build/OPEN_QUESTIONS.md`.
2. **Pre-flight (fail closed).** If a blocking SPEC-GAP is open, **stop** and list it.
   If the tree is dirty in a way that would be overwritten, **stop** (ASUR-VERSION-01).
3. **For each phase from here up to the next human gate:** run `/build-phase N`
   (the full protocol). After each phase, run **only the affected tests**.
4. **At a human gate (P04 hero-proof, P08 publish):** STOP. Print exactly what needs
   approval and how to see it (the rendered proof path). Do **not** self-approve.
5. **At any BLOCK/HOLD:** STOP. Print the disposition, the reason, and the smallest
   next action. Never advance.
6. **End-of-leg verify pass:** run the **full suite once**, the firewall-conformance
   grep, and the `verifier` on each phase's exit gate.
7. **Record.** Update `docs/build/STATUS.md` and `docs/CHANGELOG.md`. Commit per the
   git rules (`<type>(pNN): ...`, no trailers, never push). Then print a short recap
   and the next action.

---

## 4. Optimization rules (so it's fast, not wasteful)

- **Affected tests between phases; full suite once per leg.** Don't re-run 36+ tests
  after every tiny change — only at the leg's verify pass.
- **Parallel read-only review.** `code-reviewer` and `security-reviewer` run at the
  same time, never one-after-another.
- **Batch SPEC-GAPs.** Collect them and present together at the gate, not one by one.
- **Regenerate only the failing piece.** A failing section/stage is rebuilt alone, not
  the whole video or the whole phase.
- **Cheap work early, expensive work gated.** Idea/research/hooks/script are cheap and
  run freely; GPU/render/cloud work stays behind the stage-18 human gate (cost
  discipline — see `docs/PIPELINE.md §cost`).

---

## 5. If something goes wrong

- **Tests red →** the phase does not advance. `/fix-bug` (test-first), then re-run.
- **Firewall leak (forbidden target field in VIRAL_VIEW) →** hard BLOCK. Fix the
  projection; the greppable conformance test must go green before anything proceeds.
- **3 failed fix attempts →** stop, revert to last green, write down what was tried,
  and escalate to the human. Never shotgun-patch.
- **A failed artifact →** it is kept with `status: rejected` (never deleted); retry
  only the failing stage (ASUR-VERSION-01, reproducibility).

---

## 6. Quick reference

| You want… | Command |
|-----------|---------|
| Build everything, stopping only when you're needed | `/all-phases` |
| A one-line "are we healthy?" | `/status` |
| The full dashboard with per-phase detail + SPEC-GAPs | `/report` |
| Build exactly one phase | `/build-phase N` |
| Re-check one phase without changing anything | `/verify-phase N` |
| Fix one specific bug, test-first | `/fix-bug <description>` |

Phases and their exit gates are defined in `docs/build/PHASES.md`. The supreme rules
are in `AGENTS.md`. This runbook only *orchestrates* them — it never overrides a gate.
