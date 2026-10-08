# ASUR — The 26-Stage Generation Pipeline & Firewall Mechanics

> This is the operational heart of ASUR: the exact, ordered path from inputs to a finished, evaluated video.
> It is **stage-gated** (each stage must pass before the next runs) and it is where the **firewall**
> (GENERATION_VIEW / VIRAL_VIEW) physically operates.

See `STATE_MACHINE.md` for how these stages map to project states, and `ARCHITECTURE.md` §3 for firewall intent.

---

## 1. The full pipeline (never skip critical gates for speed)

```
 0. INPUTS                     — gather everything the user provides
 1. INPUT INSPECTION           — understand every input file  → input_report.json
 2. SOURCE-OF-TRUTH ID         — declare canonical source for script/timing/facts/brand/perf
 3. CONTENT UNDERSTANDING      — extract topic/audience/arc/claims/beats/CTA
 4. RESEARCH                   — topic/audience/competitor/trends, evidence-classed
 5. CONTENT STRATEGY           — objective/promise/value/narrative/CTA/metric
 6. HOOK GENERATION            — ≥20 hooks, scored & ranked (Hook Engine)
 7. SCRIPT GENERATION          — full production script w/ visual+audio direction
 8. TIMING ANALYSIS            — word/scene timestamps from ACTUAL media
 9. SYNCHRONIZATION PROOF      — prove voice/subtitle/scene sync BEFORE effects  ◄ hard gate
10. FREEZE APPROVED DATA       — immutable approved artifacts (version+checksum)
11. CREATIVE / CINEMATIC DIR   — visual/emotional/motion language
12. VISUAL SCREENPLAY          — per-scene semantic blueprint → visual_screenplay.json
13. ASSET STRATEGY             — choose source per asset (original/AI/procedural/stock)
14. AI + ORIGINAL FOOTAGE PLAN — combine real + AI, preserve authenticity
15. MOTION DESIGN PLAN         — motion primitives chosen by creative direction
16. SMALL HERO PROOF           — render a representative slice (truth = rendered output)
17. VIRAL CHECK (hero proof)   — blind evaluation of the proof  ◄ firewall active
18. HUMAN APPROVAL             — human approves proof  ◄ human gate #1 (before big spend)
19. FULL GENERATION            — generate all sections, no drift from approved direction
20. SECTION-BY-SECTION QA      — GENERATE→RENDER→INSPECT→QA→APPROVE per section
21. FINAL RENDER               — assemble final 9:16 video
22. FINAL QA                   — visual/audio/text/content/platform QA
23. FINAL VIRAL CHECK          — blind evaluation of the FINAL video  ◄ firewall active
24. PUBLISHING PACKAGE         — video + thumbnail + title + caption + hashtags + metadata
25. PUBLISH                    — human publishes to Instagram Reels
26. PERFORMANCE → LEARNING     — capture metrics, fold into SCRIPT memory
```

> Stages **0–15** are SCRIPT + GENERATION authoring. Stages **17 & 23** are VIRAL CHECK. Stage **26** is the learning loop.
> **17 and 23 are where the firewall is enforced** — VIRAL CHECK receives only the VIRAL_VIEW.

---

## 2. Stage notes (the parts that most affect design)

- **Stage 1 — Input inspection.** Do not begin production before understanding inputs. Missing/broken inputs → fail closed.
- **Stage 2 — Source of truth.** Explicitly pin: script→approved script; timing→actual audio/video timing; facts→verified research; brand→approved guidelines; performance→platform analytics. Generated assumptions must never silently replace source data.
- **Stage 9 — Sync proof.** No artistic complexity until basic sync is proven. If sync is wrong, **STOP** (`BLOCK:SYNC_FAILED`). This prevents building beautiful effects on a broken foundation.
- **Stage 10 — Freeze.** Approved artifacts become immutable (version, timestamp, checksum, source, approver, status). Downstream reads the frozen version.
- **Stage 13–14 — Asset strategy & AI+original.** AI should *enhance* authenticity, not auto-replace it. Preserve original footage where it adds trust/personality/proof/emotion/creator identity. Each asset's source is a deliberate choice, not "AI because AI."
- **Stage 16 — Hero proof.** Prove the creative direction on a small slice *before* generating the whole video. Cheap insurance against expensive mistakes.
- **Stage 16/20/22 — Review actual rendered output.** Never judge only code/config/JSON/timeline metadata. Extract frames, contact sheets, audio, captions. A technically correct pipeline can still produce a bad video. **Rendered output is truth.**
- **Stage (pre-17) — Self-critique.** Before VIRAL CHECK, GENERATION asks itself: does it look generic / bad-AI / boringly paced / repetitive / over-transitioned? Does the visual communicate the script? Does the first frame stop the scroll? Regenerate weak sections *before* handing off.
- **Stage 19–20 — Full gen + section QA.** Lock creative direction, visual language, timing, approved assets. Generate remaining sections preserving continuity. A failing section regenerates **alone**.

---

## 3. Cost discipline across the pipeline

Cheap methods for exploration; expensive generation only after quality gates (research flag: local = zero marginal render cost, cloud/Remotion = real cost).

| Phase | Cost tier | What runs |
|-------|-----------|-----------|
| Stages 0–6 (ideation, hooks) | **Cheap** | Text generation, scoring. Explore many options freely. |
| Stages 7–16 (script, screenplay, hero proof) | **Moderate** | One representative render, limited model calls. |
| Stages 19–21 (full generation + final render) | **Expensive** | Full video generation. **Gated behind human approval of the hero proof (stage 18).** |

This is why the human approval gate sits at stage 18 — it caps spend on any concept the human hasn't accepted.

---

## 4. The firewall in motion (GENERATION_VIEW / VIRAL_VIEW)

The firewall is a **pure projection function** (`asur/tools/projection.py`). It is the only thing that stands between
the two instruments, and it runs at the hand-off into stages 17 and 23.

### 4.1 Hand-off is the only channel

GENERATION never calls VIRAL CHECK directly. Instead:

```
GENERATION  ──seal bundle──>  [hash-chained local queue]  ──claim──>  VIRAL CHECK
```

- **seal:** GENERATION writes the rendered bundle + its SHA-256 digest to a local hash-chained queue
  (`.asur/queue/<run_id>.jsonl`). Once sealed, the bundle is **frozen** — GENERATION can write nothing more under it.
- **claim:** VIRAL CHECK atomically claims the sealed bundle (O_EXCL). It evaluates at the sealed digest.
- **verdict → place:** advancing only succeeds if sealed digest = verdict digest = on-disk digest (§5 of `STATE_MACHINE.md`).

This is Trinity's `route → seal → claim → verdict → place → reconcile` pipeline, **kept intact and key-free** —
it needs only SHA-256 hashing and atomic file ops, no signing.

### 4.2 What each side receives

The projector computes two views from the canonical input closure (SCRIPT memory + pinned inputs + one declared
evaluation instant). Each view is recomputable and **fails closed** if bytes differ or the projector is absent.

**GENERATION_VIEW** (built for stages 6–19):
```
✓ creative brief, audience, platform, promise
✓ hook direction + strategic angles
✓ quality / hardness FLOORS (minimum bar)
✓ per-category quality targets, lever direction
✓ cost/budget envelope, asset-license policy
✗ VIRAL CHECK pass criteria            (stripped)
✗ gate thresholds                       (stripped)
✗ finding text / weakness reasoning     (stripped)
```

**VIRAL_VIEW** (built for stages 17 & 23):
```
✓ rendered-bundle content hashes + claimed scope
✓ provenance manifests + per-asset license facts
✓ platform / brand facts + constraints
✓ checker rubric metadata (which lane, binding identity)
✗ quality / hardness TARGETS            (stripped BY NAME — greppable)
✗ "what good was defined as"            (stripped BY NAME)
✗ per-dimension target values           (stripped BY NAME)
```

### 4.3 Why targets are stripped from VIRAL_VIEW

> *An evaluator holding the author's playbook grades the intent instead of the bytes.*

If VIRAL CHECK could see the quality targets GENERATION aimed for, it would (consciously or not) grade toward those
targets and rubber-stamp. By withholding them, VIRAL CHECK must judge the **actual rendered video on its own merits**
against documented platform signals — which is exactly the honest evaluation the market lacks (see `VIRAL_CHECK.md`).

### 4.4 Three enforcement mechanisms (all local, all key-free)

1. **Pure projection function.** Each view is recomputed from canonical inputs; any byte mismatch → fail closed.
2. **Named-forbidden strip + grep.** Forbidden fields are removed by name; a conformance check greps the produced
   views and **fails closed** if a forbidden field name leaks through.
3. **Local layout check.** `.script/`, `.generation/`, `.viral/` are separate local directories; the gate refuses any
   VIRAL CHECK evidence file whose path/content cites the quality-target files. No submodules, no remotes — a plain
   local path + content scan.

---

## 5. Pipeline integrity summary (kept vs dropped)

| Mechanism | Status in ASUR | How |
|-----------|----------------|-----|
| Hash-chained hand-off queue | **KEPT** | SHA-256 + atomic file ops |
| Bundle freeze on seal | **KEPT** | content hash; producer can't mutate after seal |
| Projection firewall (2 views) | **KEPT** | pure function, fails closed |
| Producer ≠ approver | **KEPT** | compare local usernames |
| HEAD/digest binding | **KEPT** | three-way digest agreement |
| Task-collision refusal | **KEPT** | same task under different bytes → refuse (pure hash) |
| SSH-signed envelopes | **DROPPED** | replaced by local identity |
| External signed pilot | **DROPPED** | run is self-contained; delivers finished video |
| Independent publisher authority | **DROPPED** | human publishes locally |
| Crypto sentinel clearances | **DROPPED** | not needed without keys |

---

## 6. Real-world validation — *PYAAR?* by Naam Sujal

This pipeline is not theoretical. A full Hindi rap lyric video (*PYAAR?* by Naam
Sujal) was built end-to-end, **locally**, by a coding agent (Claude Code +
Remotion) following exactly this stage-gated flow. It is proof the process works
on real content in a real language — Hindi / Hinglish / Marathi with Devanagari
script.

### What it proved — three rules that map straight to ASUR invariants

1. **Freeze approved files, then never change them.**
   Once a stage was approved its files were frozen and their checksums recorded;
   every later stage *read* them but never *rewrote* them.
   → ASUR-VERSION-01 + Stage-10 FREEZE APPROVED DATA.

2. **Review a picture, not code.**
   Every stage ended in *something you watch*, never just JSON or config — a
   sync-test video, a contact sheet of frames, a short proof render. The agent
   inspected the rendered frames itself and fixed problems *before* showing the
   human.
   → Stage-16 "rendered output is truth" + Stage-17 self-critique.

3. **Prove quality on a small piece first.**
   A 5–15s hero proof set the quality bar before scaling to the full render.
   Mid-project the ask *"can we make a small section quickly"* cut scope to a
   single 5-second moustache moment — and a short polished proof got a decision
   far faster than a long unfinished one would have.
   → Stage-15 hero proof + Stage-18 human approval.

### Concrete artifacts it produced (good examples to imitate)

`word-timestamps.json` · `phrases.json` · `beat-map.json` (123 BPM, with
downbeats / kicks / snares / energy / section boundaries via **librosa**) ·
`sync-test.mp4` · `hero-proof.mp4` · `visual-screenplay.json` ·
`creative-direction.md` · `implementation-notes.md`.

### Local stack the case study happened to use

| Job | Tools |
|-----|-------|
| Timing | **Demucs** (vocal isolation) + **torchaudio MMS** forced-alignment + **Whisper** cross-check |
| Beat map | **librosa** |
| Render | **Remotion** (React/TypeScript) + **HarfBuzz / libraqm** (Devanagari shaping) + **FFmpeg** |

> **Caveat — not a mandate.** This case study used Remotion, but ASUR's *locked
> default* render stack remains **FFmpeg / MoviePy** (zero marginal cost).
> Remotion is **optional** only (see `GENERATION_STACK.md §5 / §8`). The *process*
> is what's validated here, not any one renderer.
