# ASUR Build Phases (P00–P08)

Smallest-shippable phases that take ASUR from "Phase 1 SCRIPT done, 36 tests pass"
to an industry-grade, local-first, key-free product. Each phase lists **scope**,
**out-of-scope**, **mandatory tests**, and an **exit gate**. Phases are gated and
forward-only. A phase is done only when its exit gate is green and (where required)
a human gate is cleared.

Mapping: these phases implement the 5-phase MVP build order over the 26-stage
pipeline and the 18-state machine. Items already built are marked **[adopt/verify]**.

Legend for mandatory tests: **U** unit · **I** integration · **G** gate/fail-closed
· **F** firewall-conformance (greppable) · **R** rendered-output (tiny fixtures,
no GPU, no network).

---

## P00 — Foundations & ADRs
**Scope:** Freeze `docs/spec/SPEC.md`. Author the Phase-0 ADRs (`/architecture`).
Lock the stdlib-only core boundary. Add the `asur[generation]` optional extra to
`pyproject.toml` (empty/placeholder deps list is fine; nothing imports it yet). Add
CI that runs the suite with **no network, no GPU**, plus an import-linter that fails
if core/SCRIPT/VIRAL/ORCHESTRATOR/FIREWALL import any third-party/media module.
Scaffold `asur/tools/` and the `.script/ .generation/ .viral/ .asur/queue/`
workspaces (empty).
**Out-of-scope:** any feature code, any media dependency actually installed/used.
**Mandatory tests:** U (import-linter boundary test), G (CI fails on network/GPU
use). Confirm the existing **36 tests** still pass.
**Exit gate:** SPEC frozen; all Phase-0 ADRs Accepted and indexed; import-linter
green; scaffolding present; 36 tests pass.

## P01 — SCRIPT completion **[mostly adopt/verify]**
**Scope:** Adopt/verify the existing chain idea → research → audience → strategy →
hooks → script + the 13-check quality gate, evidence-classing, and hook
intelligence (15 dims + hook_fatigue + template_fatigue + originality + first-3s
blueprint + multilingual en/hi/hinglish/indian-en/mr). **ADD** two missing pieces:
(a) hook **A/B variant grouping** (data-only A/B/C/D; no live experimentation yet),
and (b) **hook memory persistence** (append-only store in the SCRIPT workspace so
originality compares against real prior hooks across runs).
**Out-of-scope:** any generation/render; live A/B experimentation (needs VIRAL
CHECK + LEARNING).
**Mandatory tests:** U (A/B grouping, hook-memory persistence), I (full chain +
lineage/checksums), G (quality gate HOLDs on degenerate script), F (script-side
bodies contain no forbidden target names).
**Exit gate:** one-line idea → validated, explainable script that **refuses to
proceed** when the gate fails; A/B grouping + hook memory present and tested;
determinism holds (same inputs → same checksums).

## P02 — State machine, Orchestrator & CLI surface
**Scope:** The 18-state project machine and 15 quality gates as **real runtime
states** (not just docs). The **ORCHESTRATOR** as a control-token router (carries
only state/gate/disposition/digest/residency — never findings/criteria/targets).
Full CLI surface: `asur script | generate | viral-check | run`. Append-only local
**observability** run-log (stdlib json lines) in `.asur/`. Per-stage **cost tiers**
(cheap 0–6 / moderate 7–16 / expensive 19–21) encoded as data, with the expensive
tier unreachable before the Stage-18 human approval.
**Out-of-scope:** actual generation/eval logic (later phases); any telemetry
leaving the machine.
**Mandatory tests:** U (transition legality, cost-tier gating), I (orchestrator
advances state only on gate pass), G (invalid transition / missing approval →
HOLD/BLOCK; expensive tier blocked pre-approval).
**Exit gate:** states + gates + orchestrator + 4 CLI verbs runnable; run-log
written; cost tiers enforced; two human gates (stage 18, stage 25) wired as real
blocking states with HOLD:SELF_APPROVED honesty.

## P03 — Firewall & hand-off queue
**Scope:** `asur/tools/projection.py` as a **pure function** computing
GENERATION_VIEW and VIRAL_VIEW from the canonical input closure; the **named-
forbidden stripper** + a **greppable conformance test**; a static cross-import check
(GENERATION ↔ VIRAL CHECK may not import each other). The **hash-chained hand-off
queue** `seal → claim → verdict → place` at `.asur/queue/<run_id>.jsonl`, with
`place` only on 3-way digest agreement (sealed = verdict = on-disk), atomic claim
(O_EXCL), bundles frozen on seal.
**Out-of-scope:** the content of generation/eval (later); any signing (de-keyed).
**Mandatory tests:** U (projection recompute determinism; digest agreement), G
(mismatched recompute / leaked forbidden name / digest disagreement → BLOCK), F
(forbidden names absent from both views; no cross-imports).
**Exit gate:** both views recompute identically; conformance grep green;
queue enforces 3-way digest + atomic claim + freeze-on-seal; fails closed on every
tamper case.

## P04 — GENERATION core + Hero Proof (HUMAN GATE #1)
**Scope:** Behind `asur[generation]`: visual direction, semantic visual screenplay,
asset strategy, the **LICENSE GUARD** (hard-coded trap list; monetized +
commercial_ok:false OR cap/territory violation fails closed naming the asset),
local adapters (ComfyUI/Wan 2.2 default, SDXL images, Kokoro voice, Stable Audio
bed, faster-whisper captions), **FFmpeg/MoviePy render**, and the **HERO PROOF**
(5–15s) with rendered-output verification. Ends at **HUMAN GATE #1** (hero-proof
approval) before any expensive full generation.
**Out-of-scope:** full-length generation (P06); Remotion as default; Sora (removed).
**Mandatory tests:** U (asset-strategy selection, license-guard trap list), I
(screenplay → asset plan → generation plan lineage), G (license violation fails
closed; expensive gen blocked before hero-proof approval), F (GENERATION reads only
GENERATION_VIEW; no VIRAL CHECK import), R (hero proof: 1080x1920, duration, frame
count, caption-timing JSON, contact-sheet — tiny fixtures, no GPU/network).
**Exit gate:** hero proof renders and verifies structurally offline; license guard
proven; **human approves the hero proof** before proceeding.

## P05 — EDITING environment
**Scope:** OTIO timeline model (1080x1920, 9:16, tracks/clips/markers/scenes), the
**15 motion primitives** as a component palette (never the creative driver),
caption styling (incl. Devanagari shaping for hi/hinglish/mr) + safe areas, audio
mix, and the human controls accept/reject/modify/regenerate/lock/compare/branch/
revert.
**Out-of-scope:** autonomous editing without human control.
**Mandatory tests:** U (primitive application, version_history integrity), I
(timeline round-trips via OTIO), G (every edit is a new version; nothing silently
overwritten; revert restores prior), R (a styled caption fixture renders with
correct timing/safe-area).
**Exit gate:** timeline + primitives + captions + audio mix + full manual control
set work; version history preserved and revertible.

## P06 — Full generation, section QA & final render
**Scope:** Lock the approved creative direction; generate remaining sections;
**section-by-section QA** (regenerate only the failing section); final render; the
**5-family FINAL QA** (visual / audio / text-typography / content / platform).
**Out-of-scope:** publishing; viral verdict (P07).
**Mandatory tests:** I (section generate→render→inspect→approve loop), G (one
failing section regenerates alone, not the whole video), R (final render:
dimensions/duration/caption timing on fixtures; 5-family QA checks run offline).
**Exit gate:** full video assembles from approved sections with no drift from the
hero proof; all 5 QA families pass on fixtures.

## P07 — VIRAL CHECK
**Scope:** The 12 scoring dimensions (each 0–100, shown individually), the 4
evidence classes, **binary risk flags** (never % deductions), and the verdict
**PASS / PASS-WITH-CHANGES / REJECT**. Reads **VIRAL_VIEW only**. **Never** emits a
single viral percentage.
**Out-of-scope:** seeing any quality/hardness TARGET; generating content.
**Mandatory tests:** U (dimension scoring, evidence-class tagging, risk-flag
logic), G (missing input / leaked forbidden target → cannot PASS), F (VIRAL_VIEW
carries no forbidden target names; no GENERATION import), and a test asserting the
output contains **no '%viral' number**.
**Exit gate:** honest 12-dim report + verdict produced from VIRAL_VIEW only;
no single viral number anywhere; fails closed on leak/missing input.

## P08 — LEARNING & Publish (HUMAN GATE #2)
**Scope:** Publish package; performance capture (real metrics, human-provided
files); prediction-vs-actual fold into SCRIPT memory; content/template fatigue;
creator-specific learning (EMPIRICAL OBSERVATION, not universal fact); content
knowledge graph. Ends at **HUMAN GATE #2** (publish approval). Never auto-publishes.
**Out-of-scope:** any automatic platform posting; network fetch of analytics by
default.
**Mandatory tests:** U (fatigue tracking, prediction-vs-actual diff, graph edges),
I (performance folds into SCRIPT memory and informs next-run hooks via hook
memory), G (publish blocked without human approval; no network in core path).
**Exit gate:** the loop closes — a published video's measured performance folds
back into SCRIPT memory and demonstrably informs the next idea; **human approves
publish**; nothing auto-posted.

---

### Notes
- Every phase: write tests **first** (qa-engineer), build, run code-reviewer +
  security-reviewer **in parallel**, fix affected tests, independent **verifier**
  re-runs the exit gate, then (if green and any human gate cleared) commit.
- Media work (P04–P06) is behind `asur[generation]`; CI tests the **harness**, not
  real models (no GPU, no network).
- Any underspecification → log a SPEC-GAP in `OPEN_QUESTIONS.md` with a conservative
  fail-closed default and STOP if it blocks. Never guess.
