# ASUR

[![CI](https://github.com/prathamshukla28/asur/actions/workflows/ci.yml/badge.svg)](https://github.com/prathamshukla28/asur/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

**A local-first, key-free AI Content Creation OS.**

You give it an idea. It researches, writes a strong script, generates and edits
the video (combining AI-generated media with your own footage), honestly checks
whether the video has a real chance of performing well, you approve it, it
publishes, it measures the real-world result, and it learns — so the next video
is better than the last.

ASUR is **not** another AI video generator. It is a content creation, editing,
evaluation, and **learning** system that behaves like an intelligent creative
team, not a pile of disconnected AI tools.

---

## The core loop

```
SCRIPT  ->  GENERATION  ->  EDITING  ->  VIRAL CHECK  ->  PUBLISH  ->  PERFORMANCE
  ^                                                                        |
  +------------------------------ LEARNING <-------------------------------+
```

- **SCRIPT** understands the idea and remembers everything (intelligence + memory + learning).
- **GENERATION** creates the media (AI video, AI images, voice, music, plus your own footage).
- **EDITING** is a human-controlled timeline where AI accelerates but never takes ownership.
- **VIRAL CHECK** honestly evaluates the finished video — it never fakes a score.
- **PUBLISH / PERFORMANCE / LEARNING** capture the real result and feed it back into SCRIPT.

Each stage produces a versioned artifact with full provenance. Nothing is a black
box. Nothing is silently overwritten.

---

## The 8 founding invariants

| ID | Rule |
|----|------|
| **ASUR-LOCAL-01** | Runs 100% locally. No remote login, no GitHub, no keys, no network for identity. Identity = your local OS user + git config only. |
| **ASUR-HONEST-01** | Never a fake "93% viral" number. Score input quality against documented signals; separate what is known from what is unknown. |
| **ASUR-FIREWALL-01** | GENERATION and VIRAL CHECK never talk to each other. SCRIPT is the only bridge. The generator cannot tune content to whatever the checker rubber-stamps. |
| **ASUR-GATE-01** | Fail closed. A missing input, failed check, or leaked target blocks the pipeline — it never passes by default. |
| **ASUR-HUMAN-01** | Humans own all inputs, all approvals, and all history. The machine never self-approves silently. |
| **ASUR-PROV-01** | Every asset carries its source, model, prompt, inputs, transforms, editor, version, and license. |
| **ASUR-EXPLAIN-01** | Every important decision (why this hook, why this cut, why this verdict) is explainable. |
| **ASUR-VERSION-01** | Nothing is ever silently overwritten. Every artifact is versioned; history is preserved. |

---

## What ASUR is NOT

- Not a cloud service — it works offline, on your machine.
- Not a key-signing / crypto-attestation system — local identity only.
- Not a fake-confidence "viral score" generator.
- Not a tool where the thing that makes the video also grades it.
- Not optimized for feature count — optimized for **better content over time**.

---

## Why ASUR (differentiation)

AI generation and editing are now **commodities** — nearly every tool resells the
same frontier models (Veo, Kling, Runway, etc.). The open space is elsewhere:

- **Idea / script origination** for video — thin.
- **Honest pre-publish viral evaluation** — nearly empty. The one tool that ships
  a virality score (OpusClip) is uncalibrated and grades the same vendor's own
  output — a fox guarding the henhouse.
- **A creation ↔ performance learning loop for creators** — empty. A generated
  video today has no memory of how the last one actually performed.
- **The firewall** (generator structurally independent from evaluator) — nobody has it.

> **Competitors optimize one stage and resell the same frontier models; ASUR's
> defensibility is the closed loop — an honest, firewalled viral evaluator plus
> cross-video learning memory that makes each video informed by the measured
> performance of the last.**

---

## Status

- **Design:** complete — 9 documents, see [`docs/INDEX.md`](docs/INDEX.md), frozen
  into [`docs/spec/SPEC.md`](docs/spec/SPEC.md).
- **Phase 1 (SCRIPT intelligence):** **built and passing** — one-line idea →
  research → audience → strategy → 20+ scored hooks → structured script →
  13-check quality gate, all local, versioned, checksummed, explainable.
  **222 unit tests** pass (`python3 -m pytest -q`), plus **5 opt-in integration tests** (`pytest -m integration`, needs the `ffmpeg` binary) — 227 collected. Counts are derived, not hand-typed: run `python3 -m asur.tools.status`.
- **Build kit:** in place — constitution ([`CLAUDE.md`](CLAUDE.md)), subagents
  (`.claude/agents/`), commands (`.claude/commands/`), phase plan
  ([`docs/build/PHASES.md`](docs/build/PHASES.md)), and open questions
  ([`docs/build/OPEN_QUESTIONS.md`](docs/build/OPEN_QUESTIONS.md)).
- **Next:** answer the open SPEC-GAPs, then run `/architecture` (P00) and proceed
  phase by phase.

v1 target: a full rendered 9:16 vertical **Instagram Reel**, end-to-end from a
one-line idea, generated entirely locally.

Default local stack: **Wan 2.2** (video) + **SDXL** (images) + **Kokoro** (voice)
+ **Stable Audio** (music/SFX) + **FFmpeg / MoviePy** (render) + **faster-whisper**
(captions).

---

## Documentation

Start at [`docs/INDEX.md`](docs/INDEX.md) for the full map. In reading order:

1. [ARCHITECTURE](docs/ARCHITECTURE.md)
2. [DATA_MODELS](docs/DATA_MODELS.md)
3. [STATE_MACHINE](docs/STATE_MACHINE.md)
4. [PIPELINE](docs/PIPELINE.md)
5. [VIRAL_CHECK](docs/VIRAL_CHECK.md)
6. [GENERATION_STACK](docs/GENERATION_STACK.md)
7. [AGENTS](docs/AGENTS.md)
8. [MVP](docs/MVP.md)

Build/governance docs:

- [`docs/spec/SPEC.md`](docs/spec/SPEC.md) — the frozen product spec (authoritative).
- [`docs/build/PHASES.md`](docs/build/PHASES.md) — phases P00–P08 with exit gates.
- [`docs/build/STATUS.md`](docs/build/STATUS.md) — live build status.
- [`docs/build/OPEN_QUESTIONS.md`](docs/build/OPEN_QUESTIONS.md) — SPEC-GAPs + defaults.
- [`docs/adr/README.md`](docs/adr/README.md) — architecture decision records.
- [`docs/design/DESIGN_SPEC.md`](docs/design/DESIGN_SPEC.md) — CLI UX + rendered-video design system.

---

## Setup

ASUR's core is **stdlib-only** — no third-party packages needed to run SCRIPT.

```bash
# from the asur/ directory
python3 -m venv .venv
source .venv/bin/activate

# install the stdlib-only core (editable)
pip install -e .

# optional: media stack for GENERATION/EDITING (FFmpeg/MoviePy, etc.) — later phases
pip install -e ".[generation]"
```

Run the tests (no network, no GPU required):

```bash
python3 -m pytest -q        # from the asur/ directory
```

Try Phase 1 end-to-end:

```bash
asur script --idea "why most people waste money on AI tools" --project ./demo
# or: python3 -m asur.cli script --idea "..." --project ./demo
```

---

## Build order (for Claude Code)

The build is driven by slash commands defined in `.claude/commands/`, governed by
[`CLAUDE.md`](CLAUDE.md):

```
/architecture          # P00 — ADRs + scaffolding (no feature code)
/build-phase 1         # then verify
/verify-phase 1
/build-phase 2
/verify-phase 2
...
/build-phase 8
/verify-phase 8
```

Use `/status` any time to see the current phase, test counts, open SPEC-GAPs, and
the next human gate. Every phase writes tests first, builds, runs read-only code +
security review in parallel, fixes, independently verifies the exit gate, stops at
any human gate, then commits locally.
