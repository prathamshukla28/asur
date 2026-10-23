# ASUR — Viral-Check Empirical Validation Plan (V1 proposal)

> **Status: PLAN ONLY. No code written.** This is an architecture + implementation
> plan for the user's #1 "worth real money" ask: **prove the viral-check score predicts
> real-world performance** by scoring 200–500 real Reels/Shorts *before* seeing their
> views, then showing the relationship. It must be reviewed and approved by a human
> before any code is written (ASUR-HUMAN-01 §11). It introduces one new SPEC-GAP
> (**G30**, logged in `OPEN_QUESTIONS.md`). Per `AGENTS.md §7`, it is logged, defaulted
> conservatively, and gated on a human — never invented silently.

---

## 0. Why this plan exists (context)

The user's exact ask (priority #1):

> "Prove the viral check: score 200–500 real Reels or Shorts before looking at their
> views, then show the score predicts performance. This is the single thing that turns
> your claim into an asset." + "do this testing".

This is the defensibility claim from `AGENTS.md §1` ("an honest, firewalled viral
evaluator plus cross-video learning memory"). Right now that claim is **unproven**. A
measured correlation between the score and real performance is what converts it from a
claim into an asset.

### The constitutional tension (drives the whole design)

The viral checker **scores input quality against documented signals** and, by
**ASUR-HONEST-01**, must **never emit a single "% viral" / predicted-views number**.
`tests/test_viral_check.py::test_no_single_viral_percentage_anywhere` already walks the
whole `viral_check` body and fails if any aggregate/percentage key appears. So
"prove the score predicts performance" **cannot** mean "turn it into a predictor." It
can only mean a **correlation measured after the fact**: score blind, then reveal the
views, then compute how well the per-dimension scores and the verdict rank-order the
real outcomes.

Two more invariants shape it:

- **§4 / ASUR-LOCAL-01** — no test may touch the network; the core is stdlib-only and
  key-free. Fetching real clips + view counts needs the network and the user's own
  platform credentials.
- **§11 / ASUR-HUMAN-01** — anything touching paid/cloud/API or real platform data is a
  **human-gated** action the user runs themselves.

Therefore the data collection **cannot** live in the stdlib core or the pytest suite. It
is a separate, human-run, opt-in tool.

### User decisions already locked (m0513)

1. **Validation framing = blind correlation study.** Score 200–500 clips blind, then
   reveal views, measure **Spearman rank correlation** per dimension + verdict-vs-
   performance. Never a %viral predictor. The honest correlation result is the asset.
2. **Judgment-call facts = blind human rater pass.** The machine auto-derives only the
   **observable** facts (aspect ratio, resolution, captions-present, audio-present,
   watermark). The **judgment** booleans (`delivers_promise`, `strong_first_three_seconds`)
   are tagged by a **human rater who watches each clip without seeing its view count**
   (never invented, §7).

---

## 1. SPEC-GAP G30 (new — proposed, status: open — awaiting human)

| ID | Question | Conservative default (proposed, fail-closed) | Status |
|----|----------|-----------------------------------------------|--------|
| **G30** | Can we empirically prove the viral-check score predicts real-world performance, given ASUR-HONEST-01 forbids a predicted-views/%viral number and §4/§11 forbid network + credentials inside the stdlib core / pytest? | **Blind correlation study, three separated pieces, never a predictor.** (1) Human-gated **collector** outside `asur/` + outside pytest; user runs it with their own credentials; writes a dataset dir with **view counts sealed** in a separate file. (2) **Blind-scoring** harness (stdlib): auto-derive observable `platform_facts` (aspect/resolution/captions/audio/watermark) + ingest a **blind human rater's** judgment booleans; `build_viral_view → score_all + decide_verdict` per clip with views **still sealed**. (3) **Offline correlation report** (stdlib, no network): unseal views, compute **Spearman** per dimension + verdict-vs-performance, with honest caveats. Never a %viral number (ASUR-HONEST-01 + the existing guard). | open — awaiting human |

---

## 2. Design principle — measure, never predict; collect human-gated, score blind, correlate offline

The viral checker is untouched. We add a **study pipeline around it** with a strict
blind boundary: the view counts are sealed from the moment they are collected until the
moment the correlation is computed, so the scoring step **cannot** be tuned to the
outcome (the same spirit as the firewall). Three cleanly separated pieces:

1. **Collect (human-gated, outside core/pytest):** the user pulls real clips + views
   with their own credentials; views land **sealed**.
2. **Score (stdlib, blind):** derive observable facts + ingest blind human judgments →
   run the real evaluator → write per-clip scores, views never read.
3. **Correlate (stdlib, offline):** unseal views, compute Spearman + verdict buckets,
   write an honest report. No %viral.

---

## 3. What lands (and what does not)

**Lands (code, stdlib-only, tests-first):**

- `studio/validation/` (OUTSIDE `asur/` — never imported by the stdlib core): the
  human-gated **collector** CLI + the **dataset schema** writer. It is opt-in, manual,
  and never runs in pytest.
- `asur/asur/viral_check/validation/` — **stdlib-only** blind-scoring harness +
  Spearman correlation report. This is pure, offline, deterministic, and fully tested on
  fixtures (no network, no GPU, no real clip).
- Tests under `tests/` for the harness + correlation math (fixtures only).

**Does not land (human-run, out of scope for code):**

- The actual 200–500-clip collection run (user-driven, their credentials).
- Any network client, OAuth, or platform API inside the repo's importable code. The
  collector shells out / uses the user's own already-installed tooling; it is a thin,
  clearly-marked, human-gated script.

---

## 4. Module-by-module

### 4.1 Dataset schema (the sealed contract)

A dataset is a directory `validation/<study_id>/` with:

- `clips/<clip_id>.mp4` — the downloaded clip (gitignored; large; never committed).
- `clip_meta.json` — per clip: `clip_id`, `platform`, `source_url`, `collected_at`,
  and **observable-only** metadata. **No view counts here.**
- `views.sealed.json` — `{clip_id: observed_views, ...}` + `watch_time`/`shares`/`saves`
  if available. **This file is the sealed outcome.** The scoring step must not read it
  (enforced by a test: the scorer never opens `views.sealed.json`).
- `ratings/<clip_id>.json` — the **blind human rater's** judgment booleans
  (`delivers_promise`, `strong_first_three_seconds`), each with the rater id + timestamp.
  Written by a human who has **not** seen `views.sealed.json`.
- `scores/<clip_id>.json` — written by the blind-scoring harness (the real
  `viral_check` body: 12 dims + verdict + flags). Produced with views sealed.
- `report.json` + `report.md` — the offline correlation output.

### 4.2 `studio/validation/collect.py` — human-gated collector (OUTSIDE core/pytest)

A manual CLI the user runs themselves. Pulls N clips + metadata + view counts with the
user's own credentials, writes `clips/`, `clip_meta.json`, and `views.sealed.json`. It
is **never imported by `asur/`**, **never run in pytest**, and prints a clear banner that
it touches the network with the user's credentials (ASUR-HUMAN-01). It does **not** score
anything.

### 4.3 `asur/asur/viral_check/validation/derive.py` — observable-fact derivation (stdlib)

`derive_platform_facts(clip_path, *, ratings)` builds the `platform_facts` dict the
evaluator consumes:

- **Machine-observable** (via ffprobe, already used in `hero_proof`): `aspect_ratio`,
  `low_resolution`, `audio` present → (and its absence → `muted`). `captions_present`
  via the existing faster-whisper adapter **only when the extra is installed** (else the
  fact is recorded as `unknown` and that dimension stays at baseline — fail-open to
  baseline, never guessed true/false).
- **Blind human judgments** (from `ratings/<clip_id>.json`): `delivers_promise`,
  `strong_first_three_seconds`. If a rating is missing, the fact is **omitted** (the
  dimension stays at baseline) — never invented (§7).

Everything flows through `build_viral_view(...)` so the firewall conformance scan still
fails closed on any leaked target name.

### 4.4 `asur/asur/viral_check/validation/score_blind.py` — blind scorer (stdlib)

Iterates `clip_meta.json`, calls `derive_platform_facts`, runs the **real**
`build_viral_view → score_all → risk_flags → decide_verdict`, writes `scores/<clip_id>.json`.
**Hard invariant (tested): it never opens `views.sealed.json`.**

### 4.5 `asur/asur/viral_check/validation/correlate.py` — offline correlation (stdlib)

`correlate(study_dir)` unseals `views.sealed.json`, joins to `scores/`, and computes,
with **pure-stdlib math only**:

- **Spearman rank correlation** per dimension (dimension score vs observed views) + a
  two-sided p-value approximation; and the verdict buckets (PASS / PASS-WITH-CHANGES /
  REJECT) vs median views (are PASS clips actually higher-ranked?).
- Honest caveats: sample size, that correlation ≠ causation, that per-video reach is
  partly serendipitous (the evaluator's own `evidence_notes` line), and the evidence
  class of each dimension.
- Writes `report.json` + `report.md`. **No %viral / predicted-views number anywhere**
  (a test asserts the forbidden aggregate keys never appear, mirroring the evaluator's
  own guard).

---

## 5. Tests-first (stdlib-only, no network, no GPU)

- **Fixture dataset** (tiny, committed under `tests/fixtures/validation/`): ~5 clips with
  hand-written `clip_meta.json`, `ratings/`, and `views.sealed.json` — **no real mp4**
  (derivation is monkeypatched / fed pre-derived facts so no ffprobe/model is needed).
- `score_blind` produces 12-dim + verdict per clip and **never reads the sealed file**
  (assert via a monkeypatched `open` guard or a path-access spy).
- `correlate` computes a known Spearman value on a hand-built rank pair (deterministic),
  emits `report.json` with **no forbidden aggregate key** and no "%".
- `derive_platform_facts`: missing rating → fact omitted (baseline), `captions_present`
  → `unknown` when the extra is absent (never guessed).
- Firewall: a view built from a dataset still fails closed if a target-ish fact name is
  injected (reuse the `FirewallLeak` path).
- The collector is **not** importable by `asur/` (boundary test) and has **no** pytest.

---

## 6. Invariant conformance

- **LOCAL-01 / §4:** core + harness are stdlib-only; `[project].dependencies = []`
  stays empty; no test touches the network; the collector lives outside `asur/` and
  outside pytest.
- **HONEST-01:** the output is a **correlation**, never a predicted-views/%viral number;
  the forbidden-aggregate-key guard is reused in the report tests.
- **FIREWALL-01:** facts flow through `build_viral_view`; the conformance scan still
  fails closed.
- **GATE-01:** missing ffprobe / missing extra / missing rating → the fact is
  `unknown`/omitted and the dimension stays at baseline (never a guessed pass); the
  scorer refuses to read the sealed file.
- **HUMAN-01 / §11:** collection is human-run with the user's own credentials; the agent
  never runs it, never posts, never fetches.
- **PROV-01 / VERSION-01:** every derived fact records its source (ffprobe / faster-
  whisper / blind-rater id); dataset files are append-only, checksummed, never
  overwritten.

---

## 7. Phasing

- **V1a — schema + blind scorer + correlation math (tests-first, fixtures only).**
  stdlib-only; no network; no real clips. This is the whole provable spine and it can be
  committed and green before a single real clip exists.
- **V1b — human-gated collector CLI (manual, no pytest).** The thin, clearly-marked,
  human-run data puller. Lands with a loud banner + docs; never in CI.
- **V1c — run the real 200–500-clip study (human-driven).** The user collects, a blind
  rater tags, the harness scores, the report correlates. Output is the honest asset.

Each sub-phase: tests-first → build → verify → full-suite-green-once → SPEC-GAP triage →
`STATUS.md` + `docs/CHANGELOG.md` → commit local `feat(vNN)` selective-add, no trailers,
NO push.

---

## 8. Out of scope

- Any %viral / predicted-views number (ASUR-HONEST-01).
- Any network client, OAuth, or platform API inside importable repo code.
- Tuning the evaluator to the outcome (that would defeat the blind study; the evaluator
  is untouched).
- Auto-collection in CI / pytest.
- The three non-#1 asks (get users / charge / relicense) — separate work.
