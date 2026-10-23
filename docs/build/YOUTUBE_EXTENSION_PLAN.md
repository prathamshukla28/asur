# ASUR — YouTube Extension Plan (P09 proposal)

> **Status: PLAN ONLY. No code written.** This is an architecture + implementation
> plan for extending ASUR to YouTube as a new output surface. It must be reviewed
> and approved by a human before any code is written (ASUR-HUMAN-01). It introduces
> one new SPEC-GAP (**G19**, below) because YouTube is *not* in the frozen spec,
> whose v1 target is explicitly an Instagram Reel (9:16). Per `AGENTS.md §7`, a new
> surface is logged, defaulted conservatively, and gated on a human — never invented
> silently.

---

## 0. Why this plan exists (context)

The master prompt (`../../../master/master.md`) describes the AI Content Creation OS.
**ASUR already implements it** — the full P00–P08 build is complete (227 tests pass),
paused only at HUMAN GATE #2 (publish). The master prompt's additions are all already
captured as resolved SPEC-GAPs (G1–G18): the Hinglish hook library, the anti-AI "Human
Pass Test" (G17), the 30–40s target band (G16), Sora removal (G8), license traps (G9).

So "running master.md into ASUR" is a no-op for the core product — it is already built.
The **only genuinely new work** implied by the request — *"if you are doing for youtube
make a separate folder and start building"* — is a **YouTube output surface**, which the
frozen spec does not cover (its v1 is Instagram Reels, 9:16). The 12 reference screenshots
under `master/` are all YouTube-channel growth material, confirming YouTube is the intent.

This plan adds YouTube as a **platform extension module**, reusing ASUR's engine and
obeying all 8 invariants and the GENERATION↔VIRAL CHECK firewall. It does **not** fork
or duplicate the core.

---

## 1. SPEC-GAP G19 (new — proposed)

| ID | Question | Conservative default (proposed, fail-closed) | Status |
|----|----------|----------------------------------------------|--------|
| **G19** | The frozen spec targets Instagram Reels 9:16 only. YouTube (long-form 16:9 + Shorts 9:16) is a new output surface with different formats, platform facts, publish metadata (title/thumbnail/description/tags/chapters), and ranking signals. How should ASUR support it? | Add a **platform registry** + a **YouTube platform pack** as an *additive* module. Instagram stays the locked default; YouTube is opt-in via `--platform youtube_long` / `youtube_shorts`. No platform may relax any invariant, the firewall, or the two human gates. Platform facts are **documented public signals only** (ASUR-HONEST-01) — no private algorithm claims, no "% viral". If a required YouTube platform fact or instrument is absent, the pipeline **HOLDs** (ASUR-GATE-01). No network publishing — the publish package is produced for a human to post (ASUR-HUMAN-01). | **open — awaiting human** |

Record in `docs/build/OPEN_QUESTIONS.md` on approval.

---

## 2. Design principle: platform packs, not a fork

ASUR's pipeline is platform-shaped in exactly three seams. YouTube support is delivered by
filling those three seams with a **platform pack**, leaving the engine untouched:

1. **Format facts** — aspect ratio, duration bands, caption safe-areas, resolution.
   (Today hard-coded to 9:16 / 1080×1920 in a few places — see §5 "Minimal core touch-ups".)
2. **VIRAL_VIEW `platform_facts`** — the documented public ranking/retention signals the
   evaluator may use, injected at the firewall seam
   (`asur/tools/projection.py::build_viral_view(platform_facts=...)`). The evaluator never
   sees quality/hardness targets; that is unchanged.
3. **Publish package** — platform-specific metadata fields, produced for a human
   (`asur/learning/publish_package.py::build_publish_package(platform=...)`).

A "platform pack" is a small, **stdlib-only, data-first** module that supplies those three
things plus a format spec. Instagram's current behavior becomes the first (default) pack;
YouTube adds two more. No instrument (SCRIPT / GENERATION / VIRAL CHECK) learns "which
platform" beyond the facts legitimately in its own view — the firewall is preserved.

---

## 3. Proposed folder (the "separate folder")

```
asur/asur/platforms/                     # NEW stdlib-only package (import-linted)
    __init__.py                          # PLATFORM_REGISTRY: {id -> PlatformPack}
    base.py                              # PlatformPack dataclass + FormatSpec dataclass
    instagram_reels.py                   # default pack (adopts today's 9:16 behavior)
    youtube_long.py                      # NEW — 16:9 long-form
    youtube_shorts.py                    # NEW — 9:16 Shorts (<=60s)
    _facts/                              # documented public signals, as data (no claims)
        youtube_long.json                # retention/CTR/chapter/search signals (public)
        youtube_shorts.json              # Shorts shelf / loop / hook signals (public)
        instagram_reels.json             # existing IG signals, extracted to data

asur/docs/platforms/YOUTUBE.md           # NEW design doc: formats, facts, provenance of each fact
```

`platforms/` goes under the **stdlib-only boundary** and is added to
`tests/test_boundary.py`'s import-linter. No media/third-party imports. Facts live in
`_facts/*.json` with a `source` + `as_of` field per signal so every fact is explainable
and citable (ASUR-EXPLAIN-01); nothing is a bare assertion.

---

## 4. What each YouTube pack carries

### 4.1 `FormatSpec` (per pack)
- `aspect_ratio`: `"16:9"` (long) / `"9:16"` (shorts)
- `resolution`: `1920x1080` (long) / `1080x1920` (shorts)
- `duration_band_s`: e.g. long `{min: 180, max: 1200, default: 480}`; shorts `{min: 15, max: 60, default: 45}` — carried as a **target band, not a hard overwrite** (same pattern as G16)
- `caption_safe_area`: platform-correct top/bottom/side bands (Shorts must dodge the right-hand action rail + bottom title; long-form must dodge the end-screen/last-20s zone and the progress bar)
- `fps`: 30 default (unchanged)

### 4.2 Publish-package fields (produced for a human, never posted)
- **Long-form:** `title` (<=100 chars, flagged if clickbait-without-payoff per hook quality gate), `description` (with `chapters[]` → timestamped sections), `tags[]`, `thumbnail_ref` (3 concepts + A/B per the existing hook A/B grouping), `category`, `end_screen_plan`, `cards_plan`.
- **Shorts:** `title`, `#Shorts`-aware `hashtags[]`, `caption`, `thumbnail_ref`, loop/hook note.
- All reuse the existing `make_artifact` envelope, `source_ref` lineage, and the publish **human gate** unchanged.

### 4.3 VIRAL_VIEW `platform_facts` (documented public signals only)
- **Long-form:** browse/suggested/search traffic behavior, CTR + average-view-duration interplay, the first-30s retention cliff, chapter/segment retention, end-screen/card click behavior — each tagged with an **evidence class** (VERIFIED / STRONG / EMPIRICAL / HYPOTHESIS) and a public source.
- **Shorts:** Shorts-shelf surfacing, loop/replay weight, swipe-away in first 1–3s, hook-to-payoff timing — same evidence tagging.
- **Hard rule:** these are *inputs the honest evaluator may weigh*, never a predicted outcome and never a single number. The 12-dimension honest report and PASS / PASS-WITH-CHANGES / REJECT verdict are unchanged. No private-algorithm claims (ASUR-HONEST-01).

---

## 5. Minimal core touch-ups (additive, invariant-preserving)

These are the only changes outside `platforms/`. Each is small, additive, and defaulted to
today's behavior so Instagram is byte-identical unless `--platform` is passed.

| File | Change | Default preserved |
|------|--------|-------------------|
| `asur/cli.py` | Add `--platform {instagram_reels,youtube_long,youtube_shorts}` to `generate`/`run`; default `instagram_reels` | yes |
| `asur/learning/publish_package.py` | Replace the hard-coded `metadata.aspect_ratio = "9:16"` and `_DEFAULT_PLATFORM` with values pulled from the chosen pack's `FormatSpec`; add optional `chapters`/`tags`/`description` fields when the pack declares them | IG pack returns 9:16 → identical output |
| `asur/generation/*` (creative_direction, visual_screenplay, asset_strategy, hero_proof, final_qa) | Read `aspect_ratio`/`resolution`/`duration_band`/`safe_area` from the pack instead of the 1080×1920 literal; the final-QA platform family reads the pack's duration band (reuses the G16 warning-not-fail pattern) | IG pack supplies 1080×1920 → identical |
| `asur/tools/projection.py` | No signature change. `build_viral_view` already takes `platform_facts`; the YouTube pack supplies that dict. Firewall strip unchanged | yes |
| `tests/test_boundary.py` | Add `platforms` to the stdlib-only import-linter allow-list | n/a |

**No change** to: the 8 invariants, the firewall projection logic, the hash-chained queue,
the state machine, the two human gates, the orchestrator control-token discipline, or the
`asur[generation]` boundary.

---

## 6. Firewall & invariant conformance (how this stays legal)

- **ASUR-FIREWALL-01:** YouTube facts enter only through `build_viral_view(platform_facts=)`.
  The generation side gets format facts (aspect/duration/safe-area) via GENERATION_VIEW's
  brief — those are *floors/format*, never viral pass criteria. The `conformance_scan`
  forbidden-name strip is unchanged and still fails closed. A YouTube pack cannot smuggle a
  target into VIRAL_VIEW because the named-forbidden set still applies.
- **ASUR-HONEST-01:** platform facts are documented, evidence-classed public signals; the
  output remains the 12-dimension report + verdict, never a "% viral" number.
- **ASUR-GATE-01:** if a pack or a required platform fact is missing →
  `HOLD:INSTRUMENT_NOT_AVAILABLE` / `HOLD`, never a silent pass. Unknown `--platform` value →
  fail closed (mirrors `dispatch.py`'s `DispatchError` pattern).
- **ASUR-PROV-01 / EXPLAIN-01:** every fact in `_facts/*.json` carries `source` + `as_of`;
  every publish field is traceable via `source_ref` lineage.
- **ASUR-VERSION-01 / HUMAN-01 / LOCAL-01:** artifacts stay versioned/append-only; publish
  stays a human gate; no network, no keys, FFmpeg/MoviePy render path unchanged.

---

## 7. Phasing (proposed P09, built the ASUR way)

Follows `AGENTS.md §6`: tests-first, parallel read-only review, independent verify, human gate, local commit.

- **P09a — Platform registry + IG adoption (refactor, zero behavior change).**
  Introduce `platforms/base.py` + `instagram_reels.py`; route the existing 9:16 literals
  through the IG pack. Exit gate: **all 227 existing tests still pass unchanged** (proves the
  refactor is behavior-neutral) + new unit tests for the registry.
- **P09b — YouTube Shorts pack (9:16, closest to today).** `youtube_shorts.py` + facts +
  publish fields + final-QA duration band. Tests: U (pack facts, duration band), G (missing
  fact → HOLD; unknown platform → fail closed), F (VIRAL_VIEW still strips targets with YT
  facts present), R (hero proof renders at 9:16 on fixtures, offline).
- **P09c — YouTube long-form pack (16:9).** `youtube_long.py` + chapters/description/tags/
  end-screen in the publish package + 16:9 safe areas + long-form retention facts. Tests:
  U (chapters/tags build, 16:9 safe area), I (screenplay→plan→publish lineage at 16:9), G
  (title clickbait-without-payoff flagged by existing hook quality gate), R (16:9 structural
  verify on fixtures), F (firewall conformance with long-form facts).
- **P09d — Repurpose bridge (optional, from the PNG "repurpose every video" idea).**
  One approved long-form script → derive a Shorts cut plan **as a new versioned artifact**
  (never silently mutating the source). Pure SCRIPT-side transform; no new firewall surface.

Each sub-phase independently green before the next; `docs/build/STATUS.md` + `CHANGELOG.md`
updated at each gate.

---

## 8. Out of scope (explicitly)

- **No automatic posting to YouTube.** No OAuth, no Data API upload, no keys — that would
  violate ASUR-LOCAL-01/HUMAN-01. ASUR produces the publish package; a human uploads.
- **No private-algorithm modeling** and **no "% viral"** — unchanged.
- **No channel-management / monetization automation** (the PNG prompts about niche picking,
  AdSense, sponsorships are creator *strategy* inspiration, not ASUR features). They can
  inform SCRIPT's research prompts later but are not built here.
- **No Sora**, ever (G8).

---

## 9. Decision requested

Approve, amend, or reject:

1. **Accept SPEC-GAP G19's default** (YouTube as an additive, opt-in platform pack; IG stays
   default; no network publish).
2. **Approve the folder** `asur/asur/platforms/` + `asur/docs/platforms/YOUTUBE.md`.
3. **Approve phasing P09a→P09d** (start with the behavior-neutral P09a refactor so the 227
   tests prove nothing regressed before any YouTube code lands).

On approval I will write P09a tests first (behavior-neutral refactor), then build — strictly
per `AGENTS.md`. Until then, **no code is written.**
