# ASUR — VIRAL CHECK (Evaluation Doctrine)

> VIRAL CHECK is the **evaluation / challenge** instrument (Trinity's CRUCIBLE ancestor).
> Workbench `.viral/`. Root report `VERDICT.md`.
> It answers one honest question: **"Does this video have a realistic chance of
> performing exceptionally well?"** — never "this will go viral."
>
> VIRAL CHECK is **structurally independent** from GENERATION. They never talk.
> SCRIPT is the only bridge, and it hands VIRAL CHECK a `VIRAL_VIEW` that has had
> all quality/hardness **targets stripped by name** — so the evaluator grades the
> actual bytes of the video, not the author's intent. See `ARCHITECTURE.md §3`
> and `PIPELINE.md §4`.

---

## 1. The three honesty rules (non-negotiable)

These three rules are the whole reason VIRAL CHECK exists. Violating any one of
them turns ASUR into exactly the thing the market already has and distrusts.

1. **NEVER output a single "% viral" number.** No platform publishes the
   probability that a given video succeeds; reach is partly serendipitous even at
   a fixed ranking. ASUR scores **input quality against documented signals**, not
   a predicted outcome. A score of `Shareability: 82` means "this has strong
   properties on a signal platforms say they use," *not* "82% chance of going
   viral."

2. **Separate "signal exists" from "weight known."** That a platform *uses* watch
   time is a **VERIFIED FACT**. *How much* watch time is weighted relative to
   likes is **UNKNOWN** — on every platform. Every claim must say which half it
   is standing on.

3. **Penalties are BINARY RISK FLAGS, never percentage deductions.** No platform
   publishes "a watermark costs you 12% reach." ASUR raises a flag
   (`RISK: visible watermark → reposted-content suppression on Instagram`) and
   never invents a deduction number.

---

## 2. Evidence classification (tag every claim)

Every statement VIRAL CHECK makes carries exactly one tag. Categories are never
mixed inside one claim.

| Tag | Meaning | Example |
|---|---|---|
| **VERIFIED FACT** | Platform has publicly stated it, or it is directly observable. Note: a platform statement is a verified fact *about the statement*, not proof of live weighting. | "Instagram lists watch time, likes, and sends as top signals (Mosseri, Oct 2025)." |
| **STRONG EVIDENCE** | Backed by a credible study, but with a transfer caveat (e.g. ad-recall studies applied to organic feed by analogy). | "First ~3 seconds are disproportionately important (Nielsen, 173 Facebook studies — advertising-recall caveat)." |
| **EMPIRICAL OBSERVATION** | Measured from *this creator's own* published videos in SCRIPT memory. | "This creator's curiosity-hook reels retained 18% longer than their list hooks (n=11 of their videos)." |
| **HYPOTHESIS** | Creator folklore or plausible mechanism with no rigorous causal study. | "Open loops improve retention (HYPOTHESIS — widely believed, no controlled study)." |

Every **prediction** additionally carries four parts:

```
Prediction:  <what we expect>
Confidence:  low | moderate | high
Evidence:    <the evidence class + source backing it>
Uncertainty: <what we explicitly do not know>
```

---

## 3. The 12 scoring dimensions

Each dimension is scored **0–100 on its own**. There is an overall assessment,
but the individual scores are **always shown** — weaknesses are never hidden
behind one number (rule 1).

| # | Dimension | What it measures | Dominant evidence class |
|---|---|---|---|
| 1 | **Attention** | First frame, first motion, first words; contrast, curiosity, novelty, clarity | STRONG (ad-derived) + VERIFIED (platforms endorse hooks) |
| 2 | **Retention** | Opening strength, pacing, info density, pattern interrupts, open loops, payoff timing, dead moments | VERIFIED (watch time is a named signal) |
| 3 | **Satisfaction** | Delivers on the promise; meaningful payoff; viewer rewarded; satisfying ending | VERIFIED (post-watch surveys used) |
| 4 | **Value** | Educational / entertainment / emotional / practical / inspirational payload | STRONG |
| 5 | **Shareability** | Would a viewer send this to someone? Usefulness, relatability, identity, emotion, surprise | VERIFIED (IG: *sends* top-3, slightly stronger for unconnected reach) |
| 6 | **Saveability** | Would a viewer return to it? Tutorials, checklists, frameworks, references | VERIFIED signal exists; weight UNKNOWN |
| 7 | **Replayability** | Dense info, hidden details, loopable structure, fast value | VERIFIED proxy / HYPOTHESIS as a distinct lever |
| 8 | **Originality** | Generic-AI look, copied formats, overused hooks, template fatigue, derivative concepts | VERIFIED (penalty exists) / HYPOTHESIS (detection specifics) |
| 9 | **Authenticity** | Feels human, sounds like the creator, AI not overused, real personality | STRONG |
| 10 | **Visual Quality** | Resolution, artifacts, composition, consistency | VERIFIED (IG demotes low-res) / HYPOTHESIS (TikTok specifics) |
| 11 | **Audience Fit** | Match to the creator's actual audience and interests | VERIFIED (personalization + collaborative filtering) |
| 12 | **Platform Fit** | Aspect ratio, duration, captions, safe areas, per-platform rules | VERIFIED (per-platform published rules) |

---

## 4. Platform signal knowledge base (Oct 2026)

> **Framing:** exact ranking functions are **private and change constantly**.
> Everything a platform "says it uses" is a **VERIFIED FACT about the public
> statement**, not proof of current live weighting. Treat all weights as a
> **moving target**, never fixed numbers.

### Instagram Reels (first platform — ASUR's v1 target)
- **VERIFIED:** Top predictions = likelihood to **reshare / send**, **watch all
  the way through / watch time**, **like**, and go to the audio page.
- **VERIFIED:** Mosseri (Oct 2025) — for **both connected and unconnected
  reach**, the top three are **WATCH TIME, LIKES, SENDS**. Likes weigh slightly
  more for connected reach; sends slightly more for unconnected reach. Watch:
  average watch time, likes per reach, sends per reach.
- **VERIFIED:** April 2024 update names watch time, retention, shares, likes,
  comments, plus audience-matching.
- **VERIFIED signal order:** your activity > your history with the poster >
  info about the reel (audio / visuals / popularity) > info about the poster.
- **VERIFIED — what hurts reach (→ BINARY RISK FLAGS):** low-res, visible
  watermark, muted/no audio, bordered, majority on-screen text, already-posted
  elsewhere. Originality: no visible watermarks; identical copies are replaced by
  the original; posting 10+ copies of others' content in 30 days → ineligible for
  recommendation.
- **Emphasis has shifted over time** (2021 watch-through → 2023 reshare →
  2024–25 watch time/likes/sends). Encode as moving target.

### TikTok For You (future platform)
- **VERIFIED:** Inputs = user interactions, video info (captions/sounds/hashtags),
  device/account settings (explicitly **lower** weight). Finishing a longer video
  beginning-to-end is weighted more than a weak indicator.
- **VERIFIED:** Neither follower count nor past high-performing videos are
  **direct** factors. Pipeline: Selecting → Predicting → Ranking → Similarity
  check → Recommendation rules. Uses collaborative filtering.
- **VERIFIED:** FYF-ineligible = reused/unoriginal without creative edits,
  someone else's watermark/logo, low-quality/minimally-edited, GIF-only.
  Consequence is **suppression, not removal** (stays on profile, drops out of the
  For You feed). Captions over someone else's audio = insufficient originality.

### YouTube Shorts (future platform)
- **VERIFIED:** Signals = % of viewers who **chose to view** + average view
  duration + average % viewed, then likes + post-watch survey. "Viewed vs swiped
  away." A view encodes **intent**, not a flip-through. Shorts performance cannot
  hurt long-form (separate watch histories). No minimum posting cadence.

### Cross-platform synthesis (VERIFIED)
All three converge on the same ladder:

```
watch-through / completion / "chose to view"
        >  active engagement (shares, likes, comments)
        >  metadata / audio
        >  account / device
```

**Follower count is de-emphasized everywhere.**

---

## 5. Retention principles

- **STRONG (ad-study caveat):** The first ~3 seconds are disproportionately
  important. Nielsen (173 Facebook studies): 0–3s drove +47% ad-recall lift,
  +32% brand awareness, +44% purchase intent. TikTok Creative guidance: 90% of
  ad recall lands in the first 6s. Meta exposes "3-Second Video Plays" / "hook
  rate" as native metrics. **Caveat:** these are advertising-recall studies, not
  organic-feed studies; the transfer to organic is by analogy.
- **STRONG:** Curiosity hooks outperformed direct-informational hooks by ~6.25%
  engagement (TikTok study, n=80, p=0.004, R²=0.28 — single-niche caveat).
- **STRONG:** Captions increase watch-to-end by ~80% (Verizon/Publicis, 5,616
  adults, 2019).
- **HYPOTHESIS:** Pattern interrupts, open loops, and "retention editing" are
  creator folklore — partially echoed by platform guidance, but no rigorous
  causal study. Always tagged HYPOTHESIS.
- **STRONG counter-folklore:** Interacting with a video does **not** immediately
  reshape the next recommendations; recently *viewed* content influences whether
  you like/share (arXiv 2503.20030, p<0.001). Guards against "engagement-bait
  instantly changes your feed" myths.

---

## 6. The hard unknowns (encode as honest uncertainty)

VIRAL CHECK must *state these out loud* rather than paper over them:

1. **Signal weights** are not published anywhere.
2. **View / engagement thresholds** that flip reach are unknown.
3. **How the models change** over time, across A/B tests, and by region is
   unknown.
4. **Per-video outcome** is probabilistic and partly serendipitous even at fixed
   ranking.
5. **Originality / watermark detection reliability** is not disclosed; platforms
   say they "build classifiers to predict" it, with no certainty.

"Shadowban" is **CONTESTED**: visibility *reduction* is real and documented
(e.g. For-You ineligibility); a secret punitive shadowban is **not confirmed**.
ASUR reports the documented mechanism, never the folklore.

---

## 7. Verdict output

VIRAL CHECK emits a `viral_check.json` artifact and a human-readable verdict.

**Disposition (one of three):**
- **PASS** — strong against documented signals; no blocking risk flags.
- **PASS WITH CHANGES** — viable, but named weaknesses/risks should be fixed
  first; each change is actionable.
- **REJECT** — a blocking risk flag (e.g. originality ineligibility, license
  violation surfaced during evaluation) or a dimension floor failure.

**The verdict never maps to a single viral percentage.** Disposition +
per-dimension scores + confidence, nothing collapsed.

### Verdict dashboard layout
```
Per-dimension scores (12, each 0–100)   ← always visible
Overall assessment + Confidence          ← qualitative, never a % of success
Biggest strengths                        ← evidence-tagged
Biggest risks                            ← binary risk flags
Recommended changes                      ← actionable, prioritized
Evidence                                 ← every claim tagged (§2)
Experiments to run                       ← hooks/opening/length/CTA, feeds §8
```

---

## 8. Experimentation engine

VIRAL CHECK recommends controlled experiments and stores their results in SCRIPT
memory, so each verdict is informed by the creator's own measured history
(EMPIRICAL OBSERVATION class):

- **Hook A/B:** curiosity vs authority vs story.
- **Opening type:** talking-head vs visual-action vs text-first vs unexpected
  image.
- **Length:** short vs medium vs long.
- **CTA:** comment vs save vs follow vs none.

Each published video records a **prediction-vs-reality** record:

```json
{
  "prediction": { "...": "VIRAL CHECK's scored expectation" },
  "actual":     { "...": "real metrics from Performance capture" },
  "difference": { "...": "where we were right / wrong" },
  "learning":   [ "..." ],
  "next_experiment": { "..." }
}
```

This closes the loop into the SCRIPT learning layer — the single property no
competitor has: a video that is informed by the **measured performance** of the
last one. See `AGENTS.md` (Analytics + Learning agents) and `MVP.md` (Phase 5).

---

## 9. Firewall binding

- VIRAL CHECK reads only the **VIRAL_VIEW** projection from SCRIPT:
  rendered-bundle hashes, provenance, platform/brand facts.
- The **quality / hardness targets are stripped by name** before VIRAL CHECK
  ever sees them (greppable; conformance fails closed if a forbidden field
  leaks). Rationale: *"an evaluator holding the author's playbook grades the
  intent instead of the bytes."*
- VIRAL CHECK never receives the creative brief's "what good looks like," never
  talks to GENERATION, and never has its pass criteria exposed back to
  GENERATION.

See `ARCHITECTURE.md §3` and `STATE_MACHINE.md §4` for enforcement details.
