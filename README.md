# ASUR

[![CI](https://github.com/prathamshukla28/asur/actions/workflows/ci.yml/badge.svg)](https://github.com/prathamshukla28/asur/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

**A local-first content pipeline: one-line idea → scored script → rendered MP4 →
a viral check measured from the rendered file → a fail-closed publish gate.**

The core is Python standard library only. Rendering uses the `ffmpeg` binary.
Narration uses your OS speech engine (macOS `say` or `espeak-ng`) when one is
installed. Drafting with an LLM is optional (a local Ollama server or the
Anthropic API). Without one, deterministic templates are used, and every
artifact records which generator produced it.

---

## Demo: one command

Needs Python 3.10+ and `ffmpeg`/`ffprobe` on PATH (`brew install ffmpeg` /
`apt install ffmpeg`).

```bash
pip install -e .
mkdir -p /tmp/asur-demo
asur run --project /tmp/asur-demo \
  --idea "why most people waste money on AI tools" \
  --takeaway "list every AI subscription you pay for and cancel the ones that run the same underlying model" \
  --self-approve
```

What you get in `/tmp/asur-demo`:

| Path | What it is |
|---|---|
| `youtube/asur-demo/render/final-video.mp4` | The rendered 1080x1920 video (FFmpeg colour cards + system-voice narration) |
| `youtube/asur-demo/render/hero-proof.mp4` | The hook scene, rendered and ffprobe-verified before the full render |
| `youtube/asur-demo/package/` | Ready-to-upload set: video, thumbnail, title, description, tags, metadata, content report |
| `.script/artifacts/<kind>/` | The artifact trail (15 kinds): idea → research → audience → strategy → hooks → script → qa_report → plans → edit_plan → render → viral_check → publish_package. Every artifact is versioned and checksummed, with lineage. |
| `.asur/runs/run-1.jsonl` | The state-machine log (every gate, disposition and approval) |

Real result on the author's machine (macOS, Homebrew ffmpeg 9.0.2 built without
libfreetype, template generator, about 2.5 minutes, exit code 1 = held):

```
[->] SCRIPT_APPROVED              13-check script quality gate
[->] HERO_PROOF_READY             hero proof (hook scene rendered + ffprobe-verified)
[->] FULL_GENERATION              full render 1080x1920 53.6s audio=True
      note: ffmpeg build lacks the drawtext filter (libfreetype); 9 caption card(s) rendered clean
[->] QA                           QA on the rendered file
  verdict  : PASS-WITH-CHANGES  (verdict covers the 4 measured dimension(s) and risk flags only)
    Attention            27   Retention             7   Visual Quality       97   Platform Fit   93
    Satisfaction, Value, Shareability, Saveability, Replayability, Originality,
    Authenticity, Audience Fit: unknown (not measurable from a file)
    soft  RISK: 2.7s silent gap -> dead air invites a swipe
    soft  RISK: no cut or motion in the first 3s -> weak scroll-stop
    soft  RISK: 1.00 of the runtime is frozen frames (static cards)
    soft  RISK: captions were authored but are not on screen (ffmpeg build lacks drawtext)
[->] VIRAL_CHECK_APPROVED         viral check over the rendered bytes
[HOLD] PUBLISH_READY              HUMAN gate #2: publish checks
        [HOLD] viral_check_completed: viral check PASS-WITH-CHANGES: fix [...] before publishing
```

So the run **holds at the publish gate**, which is the correct outcome. The
default renderer makes static colour cards, so the measured Attention and
Retention scores are low. On this machine's ffmpeg build the captions could not
be burned in. The checker says so, using numbers taken from the file. With an
ffmpeg build that includes `drawtext`, the captions render. Real motion
(SDXL/Wan backgrounds via `asur[generation]`) moves those scores.

Without `--self-approve`, the run stops at the first human gate
(`HERO_PROOF_APPROVED`). You watch `hero-proof.mp4` first, then approve.

---

## What is real, what is template, what is LLM

| Stage | Default (offline) | With `--llm` / `ASUR_LLM` | Recorded as |
|---|---|---|---|
| idea parsing, strategy | deterministic rules | same | `generator: template` |
| research, audience | f-string templates | LLM-drafted JSON, schema-validated; every claim tagged `HYPOTHESIS` | `template` or `llm:<provider>/<model>` |
| hooks | 21 template hooks | template hooks plus up to 8 LLM hooks, all scored by the same model | per-hook `metadata.generator` |
| script spoken lines | templates + your `--takeaway` | LLM-drafted lines, anchored to the selected hook | `generator`, `value_source` |
| hook scoring | 14 measured text features × documented weights (`asur/script/hooks.py`) | same | `features`, `scoring_model` |
| render | FFmpeg colour cards + system-TTS narration | same | render `provenance` + `license` |
| viral check | ffprobe/ffmpeg measurements of the MP4 | same | per-dimension `components` |

Invalid LLM output, or an unreachable server, falls back to the template. The
artifact records the failure (`llm_fallback`). `asur verify-repro` rebuilds
template stages byte-for-byte. LLM-drafted stages are reported as skipped,
because they cannot be rebuilt deterministically.

LLM setup:

```bash
ollama pull llama3.1 && ASUR_LLM=ollama:llama3.1 asur script --idea "..."   # local, no key
pip install -e ".[llm]" && export ANTHROPIC_API_KEY=... && asur script --idea "..." --llm anthropic
```

`anthropic` defaults to the model `claude-sonnet-5-5`. You can choose another
with `--llm anthropic:<model>`.

---

## The viral check: measured, not asserted

`asur viral-check <video.mp4> --platform instagram_reels|youtube_shorts|youtube_long`
runs three local passes over the file: `ffprobe` (duration, resolution, fps,
streams); `ebur128` + `volumedetect` + `silencedetect` (loudness, level, silent
gaps); and `scdet` + `blackdetect` + `freezedetect` (cuts, black frames, frozen
frames). It combines these with the plan's caption track and whether the render
actually burned it in.

- **Scored** (each one is a weighted mean of named, measured components): Attention,
  Retention, Visual Quality, Platform Fit. Formulas are in
  [`asur/viral_check/dimensions.py`](asur/viral_check/dimensions.py).
- **Unknown, with a reason** (never a made-up number): Value, Shareability,
  Saveability, Replayability, Authenticity, Audience Fit, plus Satisfaction and
  Originality unless a human rating is supplied.
- **Risk flags** are binary and record the measured value:
  - Hard: wrong aspect ratio, below 720p, over the upload ceiling.
  - Soft: muted, loudness off -14 LUFS, silent gaps, static opening, mostly
    frozen, captions missing, text too dense.
- There is no single "% viral" number anywhere. The artifact is bound to the
  file's sha256. The publish gate refuses (BLOCK) if the file on disk is not the
  file that was measured.

## The gates

- **Script quality gate (13 checks)**, which checks content rather than whether
  sections exist:
  - hook is 4–14 words and clears the hook-score floor
  - a concrete takeaway is present (a generic template value line HOLDs)
  - no unsourced statistics and no invented first-person anecdotes
  - no near-duplicate lines and no mechanical repetition of the subject
  - a real CTA verb
  - contiguous timings
  - estimated speech duration fits the platform band
- **18-state machine** (`asur run`): every transition runs real checks.
  - Artifact checksums, hook pool, the 13 checks, timing vs platform.
  - Hero proof rendered and verified.
  - Human gate #1.
  - Full render with file/duration/checksum QA.
  - Measured viral check (REJECT holds).
  - Human gate #2, publish checks: file present, sha256 matches the viral
    check, viral verdict PASS, audio present, duration within platform bounds,
    package written, licenses recorded.
- ASUR never uploads. A human does that.

---

## Commands

```bash
asur script       --idea "..." [--takeaway "..."] [--llm ...] [--platform ...]
asur generate     [--project P] [--platform ...] [--no-voice] [--force]   # plan + render latest approved script
asur viral-check  path/to/video.mp4 [--platform ...]                       # measure any MP4
asur run          --idea "..." [--takeaway "..."] [--self-approve]         # everything, gated
asur render       # package an existing edit_plan + viral_check into youtube/<project>/package
asur explain | verify-repro | insights | ab-resolve
```

Exit codes: `0` means the gate cleared, `1` means HELD (the reasons are
printed), `2` means a usage error.

## Development

```bash
pip install -e ".[dev]"
python3 -m pytest -q                 # unit suite (ffmpeg-backed tests skip without ffmpeg)
python3 -m pytest -q -m integration  # real renders; the SDXL test self-skips without asur[generation]
ruff check .
mypy asur
```

CI also asserts that importing the core pulls in no heavy or network
dependency. Test counts are not hard-coded here; run the suite.

Layout: `asur/core` (artifacts, gates, identity), `asur/script` (SCRIPT
stages), `asur/llm` (provider interface; the network adapters are in
`asur/llm/adapters`), `asur/generation` (planning, render, adapters),
`asur/editing`, `asur/viral_check` (probe, facts, dimensions, verdict),
`asur/orchestrator`, `asur/learning`, `asur/platforms`, `asur/tools` (pipeline,
firewall projection, verify-repro). Design docs are in [`docs/`](docs/INDEX.md).
Those are the original design and are aspirational where they disagree with
this README.

## Known limitations

- The default visuals are solid colour cards. Real AI backgrounds, video, voice
  and music adapters (SDXL, Wan 2.2, Kokoro, Stable Audio) live behind
  `pip install -e ".[generation]"` and multi-GB local weights.
- macOS `say` voices are licensed for personal, non-commercial use. The publish
  gate lists this. Use espeak-ng or Kokoro for commercial posting.
- Template copy is generic, because the subject phrase is inserted verbatim. Use
  `--takeaway` and/or an LLM for real content.
- Only 4 of the 12 viral-check dimensions are measurable from a file. The rest
  need real audience data (`asur insights` / `ab-resolve` once performance is
  recorded).

## Related

Life OS (Life Mentor + Weekly Tracker), formerly in this repo, now lives at https://github.com/prathamshukla28/life-os
