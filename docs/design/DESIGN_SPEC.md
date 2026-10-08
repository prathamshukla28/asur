# ASUR — Design Spec (UX & Rendered-Output Design System)

> ASUR's "UI" is two things: (a) the **local CLI** (and an optional dashboard), and
> (b) **the rendered 9:16 Reel itself** — the real output a viewer sees. This doc
> governs both. It invents no features beyond the 9 design docs + SPEC; anything
> missing is a SPEC-GAP with a conservative default.

---

## Part A — The tool's interface (CLI + optional dashboard)

### A1. Command grammar

Four front-door verbs (see SPEC §2 / ADR-0003/CLI contracts):

```
asur script       --idea "<one line>" [--project DIR] [--project-id ID]
                  [--language en|hi|hinglish|indian-en|mr] [--platform instagram_reels]
asur generate     --project DIR [--stage N] [--hero-proof]
asur viral-check  --project DIR [--on hero-proof|final]
asur run          --project DIR        # orchestrated end-to-end, stopping at human gates
```

Principles: one idea in, artifacts out; every verb is resumable; every verb writes
only through the versioned workspace; `run` stops (never pushes past) a human gate.

### A2. Honest status vocabulary

The only disposition words shown to the user are **SHIP**, **HOLD**, **BLOCK** (with
substates like HOLD:SELF_APPROVED, BLOCK:LICENSE_VIOLATION). Never a "%viral"
number, never "this will go viral." Progress is shown via the versioned artifact
list, not a spinner that hides work.

### A3. Verdict & gate terminal formatting

- Each stage prints one explainable line: `[vNN] <kind> <artifact_id> — <what it
  did>`.
- A gate prints its disposition, whether it passed, and the **reasons** list (every
  failed check named). A SPEC-GAP encountered mid-run prints the gap id + the
  conservative default taken, and (if blocking) STOPS.
- Viral-check output is a **table of the 12 dimensions** (each 0–100 with its
  evidence class), then the verdict PASS / PASS-WITH-CHANGES / REJECT — never a
  single aggregate number.

### A4. Dashboards (optional, spec §72–73)

- **Project dashboard**: Project (name, status, platform, duration, creator) ·
  Pipeline (SCRIPT / GENERATION / EDITING / VIRAL CHECK / PUBLISH / LEARNING with
  state markers) · Current gate (what was evaluated, passed, failed).
- **Viral-check dashboard**: per-dimension scores + overall assessment +
  confidence, then Biggest strengths · Biggest risks · Recommended changes ·
  Evidence · Experiments to run. Weaknesses are never hidden behind one number.

---

## Part B — The rendered 9:16 Reel design system

This is the design system for the **actual video**. It is the real product surface;
"rendered output is truth."

### B1. Canvas & safe areas
- Resolution **1080×1920 (9:16)**, vertical. Respect Instagram Reels UI safe zones:
  keep essential text/subjects clear of the top status area and the bottom
  caption/CTA/▸ action rail. Define explicit top/bottom/side safe-margin tokens.

### B2. Typography (incl. Devanagari)
- Latin and **Devanagari** scripts for hi / hinglish / mr must shape correctly —
  use **HarfBuzz / libraqm** at render time (correct conjuncts, matras, kerning).
- Type scale tokens (display / headline / caption / emphasis word). Captions sized
  for mobile legibility; emphasis words (WordPunch/HighlightWord) use a distinct
  weight/color, not random styling.

### B3. Color & motion tokens
- A small token set: background, surface, primary text, caption text, emphasis
  accent, risk/флаг accent. Contrast must meet readability on mobile over moving
  video.
- Motion tokens: enter/exit durations, easing, beat-sync tolerance. Motion serves
  meaning (SPEC §9 semantic visual design) — never decorative.

### B4. The 15 motion primitives as a component library
TextReveal, WordPunch, CameraPush, CameraPull, BlurTransition, CutOnBeat,
HighlightWord, SubtitleEmphasis, ImageParallax, MotionBackground, ShapeReveal,
ScreenShake, SpeedRamp, MaskReveal, TrackingText. Each is a reusable component with
typed params and version history. **The creative concept decides which primitive and
why — primitives are never the creative driver.** The same primitive yields many
outcomes.

### B5. First-3-seconds blueprint (the hook as a visual unit)
Treat 0–3s as one creative unit: 0.0–0.5s visual pattern interrupt · 0.5–1.5s core
hook (spoken + first frame + first motion) · 1.5–2.5s curiosity-promise · 2.5–3.0s
transition into value. Hook text, first frame, first motion, audio, and on-screen
text are designed together.

### B6. Platform-fit rules (design-level)
Avoid everything IG demotes: low-res, visible watermarks, muted/no-audio, letterbox
borders, majority-text frames, reposted/unoriginal. These are **binary design
checks**, surfaced as risk flags — not score deductions.

### B7. Accessibility
Caption contrast and size for mobile; keep captions and key subjects inside safe
margins; avoid text that flashes faster than it can be read; ensure emphasis relies
on more than color alone where feasible.

---

## Design-level SPEC-GAPs
Any concrete value not fixed by the 9 docs (exact margin px, exact type scale, exact
token hex, exact easing curves) is a **SPEC-GAP** — pick a conservative,
mobile-legible, platform-safe default and record it in `OPEN_QUESTIONS.md` rather
than inventing a "brand." The creator's Brand entity (SPEC §6) overrides defaults
once provided.
