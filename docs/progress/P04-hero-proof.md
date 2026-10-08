# P04 — First Video Proof (hero proof)  🛠️ BUILT · 🛑 STOPS FOR YOU (now)

## What this phase is for

Before spending time and compute making a whole video, ASUR makes one tiny
**proof** — a 5–15 second sample — so you can check the look, typography, motion,
pacing, voice, and captions. If the sample is wrong, we fix it cheaply before
scaling up.

## What P04 added

- The video tools, pulled in only now via `asur[generation]` (FFmpeg/MoviePy default,
  free; Wan 2.2, SDXL, Kokoro voice, Stable Audio, faster-whisper captions) — as thin
  shells that only load the heavy libraries when you actually run them.
- Visual direction + a semantic screenplay (every visual means something), one scene
  per script section.
- An asset plan with a **licence guard** — risky licences get blocked **by name** before
  anything is made.
- A hero-proof plan (which 5–15s slice to prove) plus a checker for the **actual rendered
  output**, not just the plan on paper.

## 🛑 The human gate

This phase **stops and asks you**. You watch the sample clip and say go / no-go.
Nothing expensive happens until you approve.

## Safety promises kept

- In the automated test runs there is **no GPU and no internet** — tests check the
  machinery on tiny stand-in files, never a real heavy model.
- Every asset carries its licence and origin.

## Status

**Built — waiting for you.** 138 tests pass. The machinery (visual direction →
screenplay → asset plan + licence guard → generation plan → hero-proof plan + checker)
is done, but it produced the **plan and the checker only** — it has **not** rendered a
real video (that's a local step on your machine with the video tools installed). This is
the start of Leg B, and it is the first place the build stops for your approval. Say go
to continue into P05 (the editing room), or stop to review first.
