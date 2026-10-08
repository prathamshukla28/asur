# ASUR — AGENTS (Roster & Orchestration)

> ASUR behaves like an intelligent creative **team**, not a pile of disconnected
> AI tools. This document defines the specialized agents, what each owns, how the
> ORCHESTRATOR sequences them, and how every agent binds to the firewall.
>
> An "agent" here is a role with a single responsibility, a defined input
> artifact set, and a defined output artifact (see `DATA_MODELS.md`). Agents never
> reach across the firewall; they operate inside one instrument
> (SCRIPT / GENERATION / VIRAL CHECK) or they are the ORCHESTRATOR.

---

## 1. Engineering architecture (service view)

```
            ┌──────────────────────────── UI ────────────────────────────┐
            │              (local CLI: asur script|generate|               │
            │               viral-check|run  + optional dashboard)        │
            └───────────────────────────┬─────────────────────────────────┘
                                         │
                                 ┌───────▼────────┐
                                 │  ORCHESTRATOR  │   (carries only control tokens:
                                 │  (Maestro)     │    state, gate, disposition, digest)
                                 └───┬───────┬───┬┘
             GENERATION_VIEW ◄───────┘       │   └───────► VIRAL_VIEW
                                     ┌───────▼────────┐
                 ┌───────────────────┤     SCRIPT     ├───────────────────┐
                 │  (the only bridge; owns memory, projections, learning) │
                 └───────────────────┬────────────────┬──────────────────┘
                                     │                 │
                           ┌─────────▼──────┐  ┌───────▼────────┐
                           │  GENERATION    │  │  VIRAL CHECK   │
                           │  (+ EDITING    │  │  (evaluation)  │
                           │     env)       │  │                │
                           └────────────────┘  └────────────────┘
                                     │
                               ┌─────▼──────┐
                               │ ANALYTICS  │ → feeds → SCRIPT LEARNING
                               └────────────┘
```

Service flow: **UI → ORCHESTRATOR → [SCRIPT, GENERATION, EDITING] → ANALYTICS →
SCRIPT LEARNING.** GENERATION and VIRAL CHECK never share a channel; SCRIPT
bridges them via the two computed projections.

---

## 2. Agent roster (14)

| # | Agent | Instrument | Owns / produces | Key inputs |
|---|---|---|---|---|
| 1 | **Research** | SCRIPT | `research.json` — topic, audience, competitors, existing content, trends, supporting facts, counterarguments, risks (patterns, not copies) | idea.json |
| 2 | **Audience** | SCRIPT | `audience.json` — demographics, interests, pains, desires, fears, objections, awareness level, language, content prefs | research.json, SCRIPT memory |
| 3 | **Strategy** | SCRIPT | `strategy.json` — objective, audience, format, platform, emotion, core promise, value prop, narrative structure, CTA, success metric | audience.json, research.json |
| 4 | **Hook** | SCRIPT | `hooks.json` — ≥20 original hooks (50+ for campaigns), each scored on 15 dimensions + `hook_fatigue_score`; selects best | strategy.json, SCRIPT memory |
| 5 | **Script** | SCRIPT | `script.json` — full structured script (hook/opening/problem/context/story/value/proof/pattern_interrupts/payoff/cta), each section with spoken words, timing, emotion, visual/audio direction | hooks.json, strategy.json |
| 6 | **Visual** | GENERATION | `creative_direction.json` + `visual_screenplay.json` — visual/emotional/motion language, per-scene blueprint | frozen script.json, GENERATION_VIEW |
| 7 | **Generation** | GENERATION | `asset_plan.json`, `generation_plan.json`, generated assets (video/image/audio) with full provenance + license | visual_screenplay.json, stack defaults |
| 8 | **Editing** | GENERATION (EDITING env) | timeline, `edit_plan.json`, rendered sections — assembles assets + original footage per creative direction | generated assets, OTIO timeline |
| 9 | **Fact-Checker** | SCRIPT | verified claims + citations into Knowledge memory; flags unverifiable claims | research.json, script.json |
| 10 | **QA** | GENERATION | `qa_report.json` — visual/audio/text/content/platform QA on **actual rendered output** | rendered sections/frames |
| 11 | **Viral-Check** | VIRAL CHECK | `viral_check.json` + VERDICT (PASS / PASS-WITH-CHANGES / REJECT), 12 dims, evidence-tagged | **VIRAL_VIEW only** |
| 12 | **Analytics** | (post-publish) | `performance.json` — real metrics capture (views, watch time, retention, shares, saves, etc.) | published video metrics |
| 13 | **Learning** | SCRIPT | `learning.json` — prediction vs reality, what worked/failed, next experiment; folds into SCRIPT memory | performance.json, viral_check.json |
| 14 | **Orchestrator** | (cross-cutting) | project state transitions, control tokens | all root reports |

---

## 3. The Orchestrator (not blind execution)

The ORCHESTRATOR is the conductor. It never does creative work and never carries
creative content across the firewall. Its responsibilities:

1. **Understand project state** — read the current state from the state machine.
2. **Inspect dependencies** — confirm the required upstream artifacts exist,
   are `approved`, and match their checksums.
3. **Call the correct agent** — route the lane to the right instrument/agent.
4. **Validate output** — confirm the agent produced the expected artifact and it
   passes its gate.
5. **Move state forward** — apply exactly one forward transition.
6. **Stop when a quality gate fails** — never push past a failed gate; route to
   hold or back to the prior stage.
7. **Request human approval** where the state machine requires it (Stage-18 hero
   proof, Stage-25 publish).
8. **Maintain provenance** — ensure every asset carries its provenance + license.
9. **Maintain cost controls** — keep expensive generation behind the approval
   gates.
10. **Record decisions** — append to the run record; nothing silent.

**The Orchestrator carries only control tokens** — state, gate name,
disposition, digest, residency count. It **never** carries findings, pass
criteria, hardness/quality targets, or evidence bytes between lanes. This is the
same firewall binding as Trinity's Maestro: the conductor cannot become the
back-channel that lets GENERATION tune to what VIRAL CHECK rubber-stamps.

---

## 4. Firewall binding per agent

| Agent group | Projection it reads | Never sees |
|---|---|---|
| Visual, Generation, Editing (GENERATION) | **GENERATION_VIEW** — creative brief, hooks direction, quality **floors** | VIRAL CHECK's pass criteria / gate thresholds / finding text |
| Viral-Check (VIRAL CHECK) | **VIRAL_VIEW** — rendered-bundle hashes, provenance, platform/brand facts | quality/hardness **targets** (stripped by name; fails closed if leaked) |
| Research, Audience, Strategy, Hook, Script, Fact-Checker, Learning (SCRIPT) | full SCRIPT memory (SCRIPT is the bridge; it computes both projections) | — |
| Orchestrator | control tokens only | all creative/evidence content |

Enforcement (per `ARCHITECTURE.md §3`): a pure projection function recomputes
each view from canonical inputs; forbidden fields are stripped **by name** and
are greppable; conformance fails closed if any forbidden field appears where it
must not.

---

## 5. Why agents, not one model

Each agent is a narrow role so that:

- every decision is **explainable** (ASUR-EXPLAIN-01) — the Hook agent explains
  *why* a hook was selected (audience, mechanism, promise, emotion, retention
  rationale), not just "here's a hook";
- outputs are **versioned artifacts** (ASUR-VERSION-01), not ephemeral chat;
- the firewall can bind cleanly to agent boundaries;
- a failing stage regenerates only the responsible agent's output, not the whole
  video.
