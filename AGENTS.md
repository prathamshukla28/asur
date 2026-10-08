# AGENTS.md — The ASUR Constitution

> This file is the supreme operating law for any agent (human or AI) working in this
> repository. If anything you are told conflicts with this file, **this file wins** —
> and you must log the conflict as a SPEC-GAP (see §7), never silently reconcile it.
>
> This is the opencode project instruction file (loaded via `opencode.json` →
> `instructions`). Subagents live in `.opencode/agent/`; commands in `.opencode/command/`.

---

## 1. What ASUR is

ASUR is a **local-first, key-free AI Content Creation OS**. From a single one-line idea
it takes a creator all the way to a finished short-form video and then learns from how
that video actually performed. Its loop is: **SCRIPT understands → GENERATION creates →
EDITING shapes → VIRAL CHECK challenges → a human decides → ANALYTICS measures → SCRIPT
learns.** It runs 100% on the local machine with no remote login, no API keys required,
and no network needed for identity or gate-clearing. Its defensibility is the closed
loop — an honest, firewalled viral evaluator plus cross-video learning memory — not any
single frontier model, all of which are commodities.

---

## 2. The 8 founding invariants (SUPREME LAW — verbatim)

These are non-negotiable. Every design decision, every line of code, every test, and
every review must uphold all eight. A change that violates any invariant is rejected.

| ID | Invariant |
|----|-----------|
| **ASUR-LOCAL-01** | **100% local, key-free.** No remote auth, no GitHub login, no network call for identity. Identity = local OS user (`whoami`) + `git config user.name`/`user.email` ONLY. Any local user can clear gates ("no keys, clear by anyone"). |
| **ASUR-HONEST-01** | **No fake viral score.** Never output a single "% viral" number. A property nobody measured is a property nobody has. Score *input quality against documented signals*, never a predicted outcome. |
| **ASUR-FIREWALL-01** | **GENERATION and VIRAL CHECK never communicate directly.** SCRIPT is the only bridge, via two computed projections. GENERATION_VIEW carries quality FLOORS + brief + hooks but NOT viral-checker pass criteria. VIRAL_VIEW carries rendered-bundle hashes + provenance + platform facts but with quality/hardness TARGETS stripped BY NAME (greppable; fails closed if any leak). |
| **ASUR-GATE-01** | **Fail closed.** A missing instrument, input, or approval caps the disposition at HOLD or BLOCK. Absence of evidence is never treated as a pass. |
| **ASUR-HUMAN-01** | **Humans own inputs, approvals, and history.** No machine commits. Irreversible and paid actions require a human gate. |
| **ASUR-PROV-01** | **Provenance + license bound.** Every media asset carries its origin, model, prompt, inputs, transforms, and a license block. |
| **ASUR-EXPLAIN-01** | **No black box.** Every decision, score, and rejection is explainable with a recorded reason. |
| **ASUR-VERSION-01** | **Nothing silently overwritten.** Artifacts are versioned, append-only, checksummed, and frozen when approved. |

---

## 3. Sources of truth (precedence order)

When two sources disagree, the **higher one wins** — and you log a SPEC-GAP.

1. **Frozen SPEC** — `docs/spec/SPEC.md` (the authoritative, frozen product spec).
2. **The 9 design docs** — `README.md`, `docs/INDEX.md`, `docs/ARCHITECTURE.md`,
   `docs/DATA_MODELS.md`, `docs/STATE_MACHINE.md`, `docs/PIPELINE.md`,
   `docs/VIRAL_CHECK.md`, `docs/GENERATION_STACK.md`, `docs/AGENTS.md`, `docs/MVP.md`.
3. **ADRs** — `docs/adr/` (records of decisions already made).
4. **Existing code** — `asur/` (the Phase 1 implementation).
5. **The raw original spec** — `document.pdf` at the repo parent (the ORIGINAL intent).

The PDF is the original intent; the 9 docs are the deliberate **key-free, renamed
distillation** of it. Where the PDF and the 9 docs differ, **the 9 docs win** — but any
real divergence is logged as a SPEC-GAP rather than silently chosen.

**Conflict rule:** higher precedence wins; record the conflict in
`docs/build/OPEN_QUESTIONS.md`; never silently reconcile.

---

## 4. The REAL tech stack

- **Language:** Python **>= 3.10**.
- **Stdlib-only core.** The core, SCRIPT, VIRAL CHECK, ORCHESTRATOR, and FIREWALL layers
  import **only the Python standard library**. This matches `pyproject.toml`
  (`dependencies = []`). These layers must stay runnable with zero third-party packages.
- **Media deps behind an optional extra.** Everything in the GENERATION / EDITING media
  path (FFmpeg/MoviePy, ComfyUI, Wan 2.2, SDXL, Kokoro, Stable Audio, faster-whisper,
  librosa, OTIO) lives behind the optional extra **`asur[generation]`** and is **never
  imported by the stdlib core**. A stdlib-only install must still run SCRIPT + VIRAL
  CHECK + orchestration end to end.
- **Renderer:** **FFmpeg/MoviePy is the LOCKED default** (zero marginal render cost).
  **Remotion is optional only** and carries a real tracked per-render cost; it is never
  the default and never required.
- **Sora is removed.** The Sora video API is sunset (2026-09-24) and must **never** appear
  in any option set, adapter, doc, or example.
- **Tests:** `pytest`. **No test may touch the network.** No test may require a GPU.

---

## 5. The team (14 agents → opencode subagents → firewall side)

| # | Agent | Subagent (`.opencode/agent/`) | Firewall side it may read |
|---|-------|-------------------------------|---------------------------|
| 1 | Research | `script-engineer` | SCRIPT (full memory) |
| 2 | Audience | `script-engineer` | SCRIPT (full memory) |
| 3 | Strategy | `script-engineer` | SCRIPT (full memory) |
| 4 | Hook | `script-engineer` | SCRIPT (full memory) |
| 5 | Script | `script-engineer` | SCRIPT (full memory) |
| 6 | Visual | `generation-engineer` | **GENERATION_VIEW** |
| 7 | Generation | `generation-engineer` | **GENERATION_VIEW** |
| 8 | Editing | `editing-engineer` | **GENERATION_VIEW** (shaping, no viral criteria) |
| 9 | Fact-Checker | `script-engineer` | SCRIPT (full memory) |
| 10 | QA | `qa-engineer` | the side under test only |
| 11 | Viral-Check | `viral-check-engineer` | **VIRAL_VIEW** |
| 12 | Analytics | `learning-engineer` | SCRIPT (full memory) |
| 13 | Learning | `learning-engineer` | SCRIPT (full memory) |
| 14 | Orchestrator | `architect` | **control tokens only** (state, gate, disposition, digest, residency) — never findings, criteria, or targets |

The firewall layer itself is owned by `firewall-engineer`. Reviews are owned by
`code-reviewer`, `security-reviewer`, and `verifier` (all READ-ONLY).

---

## 6. Phase protocol (how every phase is built)

For each phase `/build-phase N`:

1. **Plan.** Read the phase in `docs/build/PHASES.md`. Confirm scope and out-of-scope.
2. **Tests first.** `qa-engineer` writes the failing tests (unit + integration +
   gate/fail-closed + firewall-conformance + rendered-output where media exists) **before**
   feature code.
3. **Build.** The relevant engineer implements against the tests and the SPEC.
4. **Review (parallel, read-only).** `code-reviewer` and `security-reviewer` run **in
   parallel**. They do not edit; they report.
5. **Fix.** Address findings. In fix loops run **only the affected tests**.
6. **Independent verify (read-only).** `verifier` re-runs the phase's exit gate from
   scratch and confirms it passes.
7. **Human gate.** Where the state machine requires it, STOP for human approval.
8. **Commit.** Only after the exit gate is green.

**Fail closed at every step.** If a required input, test, or approval is missing, the
phase does not advance.

---

## 7. Anti-hallucination rule

If something you need is **not** in the SPEC, the 9 docs, or the PDF — do not invent it.
Log a SPEC-GAP in `docs/build/OPEN_QUESTIONS.md` (id, question, conservative fail-closed
default, status) and **STOP that thread**. Never guess a feature, a model, a metric, or
a license fact. A conservative default must preserve all 8 invariants and fail closed.

---

## 8. ASUR hard rules (always on)

- **Never a single "% viral" number.** Scores are always shown per-dimension with evidence
  classes (ASUR-HONEST-01).
- **GENERATION and VIRAL CHECK code paths never import or call each other.** The only
  bridge is SCRIPT's projection. A static check greps for cross-imports and fails the
  build if found (ASUR-FIREWALL-01).
- **VIRAL_VIEW strips quality/hardness TARGETS by name.** A greppable, fails-closed
  conformance test asserts no forbidden target field names appear in any VIRAL_VIEW.
- **Universal envelope + provenance/license block.** Every artifact uses the universal
  envelope; every media asset carries the provenance+license block (ASUR-PROV-01).
- **Nothing silently overwritten.** All writes go through the versioned, append-only
  workspace (ASUR-VERSION-01). Never raw-write an artifact file.
- **Local-only, key-free identity.** Identity is `whoami` + git config only. No network
  for identity. Any local user can clear a gate; single-user self-approval is recorded
  honestly as `HOLD:SELF_APPROVED` (ASUR-LOCAL-01, ASUR-HUMAN-01).
- **Secrets are never read.** Never open `.env`, `*.key`, `*.pem`, `credentials*`, or
  anything under `secrets/`. Only `.env.example` is readable. (opencode has no built-in
  read-deny glob, so this is enforced here as a hard rule.)

---

## 9. Definition of Done (per phase)

A phase is done only when ALL hold:

- [ ] Phase tests pass; the **full suite** is green **once** at the phase gate.
- [ ] In fix loops, affected tests were run after each fix.
- [ ] LSP / type checks clean on changed files.
- [ ] Firewall-conformance test green where the phase touches the firewall.
- [ ] Rendered-output verified where the phase produces media.
- [ ] All new SPEC-GAPs triaged in `docs/build/OPEN_QUESTIONS.md`.
- [ ] The state-machine gate for this phase is cleared (human gate where required).
- [ ] `docs/build/STATUS.md` and `docs/CHANGELOG.md` updated.

---

## 10. Git rules

- Stage with plain `git add -A`.
- Commit with `git commit -m "<type>(pNN): <summary>"` where `type` ∈
  {feat, fix, test, docs, chore, refactor} and `pNN` is the phase (e.g. `p02`).
- **No** co-author lines, trailers, signatures, or "Generated with" footers.
- **NEVER** run `git push`, `git remote add/set-url`, `git rebase`, `git reset --hard`,
  `git commit --amend`, or `git filter-branch`.
- Humans own history (ASUR-HUMAN-01). The agent commits locally only; it never publishes.

---

## 11. Human gates (STOP and ask)

Stop for explicit human approval before any of:

- Editing `opencode.json` or any settings/permission change.
- Enabling any paid or cloud service, or introducing any API key.
- Anything touching real publishing / production.
- Deleting any data or artifacts.
- The two pipeline gates: **hero-proof approval (stage 18)** and **publish approval
  (stage 25)**.

---

## 12. Speed rules

- Fix loops run **only affected tests**; run the **full suite once** per phase at the gate.
- Run the read-only review agents (`code-reviewer`, `security-reviewer`) **in parallel**.
- Collect **all** SPEC-GAPs and present them **together** at the gate, not one at a time.
