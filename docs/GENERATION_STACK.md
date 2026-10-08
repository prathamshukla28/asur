# ASUR — GENERATION STACK (Local-First Model & Tooling Spec)

> This document pins the concrete models and tools GENERATION uses to turn an
> approved screenplay into a finished 9:16 Instagram Reel.
>
> **Founding constraint (ASUR-LOCAL-01):** ASUR runs 100% locally by default.
> Cloud generators are an **optional upgrade, never a requirement**. Every stage
> of the stage-gated loop (generate → render → inspect → QA) is realizable fully
> offline.
>
> **Research currency:** Oct 2026. The single most important freshness fact:
> **OpenAI Sora 2 API was sunset Sep 24 2026 — it is DEAD and removed from every
> option set in ASUR.**

---

## 0. The locked default stack (user decision)

For v1 (Instagram Reels, 9:16 vertical, full rendered video end-to-end):

| Role | Default (local, license-clean) |
|---|---|
| Video | **Wan 2.2 TI2V-5B** (Apache-2.0) |
| Images / B-roll | **SDXL** (OpenRAIL++-M) |
| Voice / narration | **Kokoro-82M** (Apache-2.0) |
| Music / SFX bed | **Stable Audio 3.0** (Community, free <$1M rev) |
| Render / composite | **FFmpeg** (+ MoviePy MIT) |
| Captions / timing | **faster-whisper** (MIT, word-level) |

Everything below is the full menu behind those defaults, with the license traps
that force the choices.

---

## 1. Video generation

### Local (open-weights) — default path
| Model | License | Notes |
|---|---|---|
| **Wan 2.2 TI2V-5B** | Apache-2.0 (unconditional) | **CLEAN DEFAULT.** T2V + I2V, ~8GB via ComfyUI offload, 720p / 24fps / 5s, ~9 min/clip on a 4090. |
| Wan 2.2 A14B | Apache-2.0 | Best open quality (VBench ~86%); heavier. |
| LTX-2 / LTX-Video | LTX Community (free <$10M rev) | **Fastest**; LTX-2 adds synced audio; 10–16GB. |
| HunyuanVideo / 1.5 | Restricted | Top quality **but NOT licensed in EU / UK / South Korea + 100M MAU cap** → hard territory guard. |
| Mochi 1 | Apache-2.0 | ~20GB, 480p. |
| CogVideoX 2B | Apache-2.0 | Runs in 8GB. |
| CogVideoX 5B | bespoke (<1M visits/mo) | Revenue/traffic cap → guard. |
| SVD | legacy | img2vid, superseded. |

### Cloud (optional upgrade)
| Model | Price | Notes |
|---|---|---|
| **Veo 3.1 Fast** | $0.10/s | 720p + audio — **recommended cloud default**. |
| **Runway Gen-4 Turbo** | $0.05/s | 5–10s, 9:16, cheap I2V iteration. |
| Veo 3.1 | $0.40/s | Native audio + lipsync + C2PA, up to 4K. |
| Runway Gen-4.5 | $0.12/s | Leaderboard leader, ~16s. |
| Kling 3.0 / Omni | broker only | Best multi-shot/narrative, **no first-party Western API** → via fal.ai / PiAPI; flag in provenance. |
| Pika 2.5 | ~$0.04/s (fal) | |
| Luma Ray3 | — | No native audio. |
| MiniMax Hailuo 2.3 | $0.045–0.08/s | Cheapest. |

> **Wrinkle (cloud only):** jobs take **minutes** and return **expiring URLs**.
> ASUR must persist outputs to its own storage immediately and model job-state
> durability. All cloud clips are short (≤~20s native) → **sectioned generation +
> stitching is mandatory** regardless of provider.

---

## 2. Image generation (B-roll, stills, first frames)

| Model | License | Notes |
|---|---|---|
| **SDXL** | OpenRAIL++-M (commercial OK, **no revenue cap**) | **DEFAULT local B-roll.** 6–8GB, biggest LoRA/ControlNet ecosystem. |
| FLUX.1 schnell | Apache-2.0 | **Only** license-clean FLUX; 4-step fast. |
| FLUX.2 klein 4B | Apache-2.0 | ~13GB. |
| Qwen-Image | Apache-2.0 | Best in-image text, multilingual. |
| **FLUX.1 dev / FLUX.2 dev** | **NON-COMMERCIAL** | **TRAP** — needs a paid BFL license to sell output. Hard guard against monetized use. |
| GPT Image / Imagen4 / Nano Banana / FLUX Pro | cloud | Optional. |
| Midjourney | no public API | Unusable for an autonomous agent. |

---

## 3. Voice (TTS)

| Model | License | Notes |
|---|---|---|
| **Kokoro-82M** | Apache-2.0 | **Narration default.** CPU-capable (2–3GB), 54 preset voices, **no cloning** — best quality/compute locally. |
| Chatterbox / Resemble | MIT | Cloning from 7–10s + emotion, ~6GB; **best commercial-clean cloning**; batch (no streaming is fine). |
| Qwen3-TTS | Apache-2.0 | Cloning from 3s, lowest WER. |
| Piper | MIT | Edge / Raspberry Pi. |
| F5-TTS | MIT | Cloning. |
| **XTTS v2 / Coqui** | **CPML NON-COMMERCIAL** | **TRAP** — guard behind NC flag. |
| ElevenLabs | cloud, $0.08/1K chars | Best cloning, word timestamps via Scribe. |
| OpenAI tts | cloud, $15/1M | |

---

## 4. Music & SFX

| Model | License | Notes |
|---|---|---|
| **Stable Audio 3.0** | Community (free <$1M rev) | **Local bed default.** Instrumental / SFX / loops, **no vocals**. |
| YuE / ACE-Step | Apache / open | Full song + vocals, 16–24GB. |
| **MusicGen / AudioCraft** | **CC-BY-NC-4.0 NON-COMMERCIAL** | **TRAP** — guard behind NC flag. 30s. |
| ElevenLabs Music / SFX | cloud, $0.15/min / $0.12/min | Self-serve license excludes film/TV/games. |
| **Suno v6** | **AVOID** | Download caps (Sep 3 2026) + Sony/Universal lawsuits. |
| **Udio** | **AVOID** | Downloads disabled since Oct 2025 — unusable. |

---

## 5. Editing / compositing / rendering

| Tool | License | Notes |
|---|---|---|
| **FFmpeg** | LGPL/GPL (codec patents are your problem) | **THE substrate.** Deterministic CLI, ideal for agent control. |
| **MoviePy** | MIT | Python over FFmpeg; MCP wrappers exist. |
| **OpenTimelineIO (OTIO)** | Apache-2.0 (ASWF) | Timeline **interchange**, not a renderer — ASUR's timeline model/handoff format. |
| Remotion | source-available | Best agentic renderer (`renderMedia()`) **but** Free ≤3-person org; "Automators" = **$0.01/render, $100/mo minimum** — a real per-render cost to budget. |
| Motion Canvas | MIT | No official CLI export (UI-driven). |
| Revideo | MIT | Motion Canvas fork with headless render API — **prefer over Motion Canvas** for headless. |

### Captions
| Tool | License | Notes |
|---|---|---|
| **faster-whisper / CTranslate2** | MIT | **Standard local caption timing.** 4× faster, word-level timestamps. |
| whisper.cpp | MIT | CPU / Metal / CUDA, word timestamps. |
| WhisperX | BSD | Alignment + diarization for karaoke captions. |

---

## 6. The offline stage-gated loop

The entire `generate → render → inspect → QA` loop runs **locally, offline**:

```
ComfyUI JSON workflows (headless)      → generate video + images
FFmpeg / MoviePy                       → render / composite
Kokoro / Chatterbox / Stable Audio     → audio (in-process)
faster-whisper                         → caption QA + sync verification
OTIO                                   → timeline handoff between stages
vision model on FFmpeg-extracted frames→ QA gate (see PIPELINE.md stages 16/20/22)
```

Cloud generators, if enabled, fit the **same async submit → poll → download**
pattern, with the expiring-URL handling from §1.

---

## 7. License as a first-class provenance field

Per `DATA_MODELS.md`, **every asset** carries a `license{}` block. The license is
not a footnote — it is a gated field. The **monetization gate** fails closed and
**names the offending asset** when:

- `commercial_ok: false` and the project is monetized, **or**
- a `revenue_cap_usd` would be exceeded, **or**
- a `territory_exclusion` applies to the creator's region.

### Hard-guard trap list (never silently used for monetized output)
| Asset source | Trap |
|---|---|
| FLUX.1 dev / FLUX.2 dev | Non-commercial without paid BFL license |
| XTTS v2 / Coqui | CPML non-commercial |
| MusicGen / AudioCraft | CC-BY-NC non-commercial |
| HunyuanVideo | Not licensed EU / UK / South Korea + 100M MAU cap |
| CogVideoX-5B | <1M visits/mo cap |
| LTX / Stable Audio / SD3.5 | Revenue caps (free below threshold) |
| Suno / Udio | Download disabled / active litigation — avoid entirely |

---

## 8. Cost model

Cost discipline mirrors the pipeline's gate structure (`PIPELINE.md §cost`):

- **Local renderers are zero marginal cost** (FFmpeg, MoviePy, Revideo, Motion
  Canvas — all MIT/LGPL). `render_cost_usd: 0`.
- **Remotion is the exception** among "local" renderers — it carries a real
  $0.01/render, $100/mo-minimum cost that the cost model must track separately.
- **Cloud generation is the expensive tier** and is only reachable **after the
  Stage-18 human approval gate** — exploration and hero-proof happen on the cheap
  local stack first.

Cost intelligence: cheap methods for exploration/ideation/hook-testing; moderate
for script/hero-proof; expensive full generation only after quality gates pass.

---

## 9. Design flags (carry into implementation)

1. **Local-first is viable end-to-end**; cloud is an optional upgrade, not a
   dependency.
2. **License is a first-class provenance field** (§7) — encode `commercial_ok`,
   `revenue_cap_usd`, `territory_exclusions`, `training_data_provenance`.
3. **Sora is gone** (removed everywhere).
4. **Remotion has a real per-render cost** — the cost model must distinguish it
   from zero-marginal local renderers.
5. **Cloud video is short + async + expiring-URL** — sectioned generation,
   stitching, and durable storage of outputs are mandatory.

---

## 10. Creative-quality guidance (ideas-3 brief)

Carried into the final QA (P06), not auto-certified by the machine:

- **Context-aware color grading** — cinematic grading that matches mood
  (warm/vibrant for uplifting beats, moody/filmic for dramatic ones). Avoid flat,
  over-saturated, generic AI palettes.
- **Anti-AI "Human Pass Test"** — the rendered output should read as real,
  human-created live-action: natural micro-expressions, eye blinking, hair sway,
  real skin texture (no plastic smoothing); consistent lighting, shadows, physics,
  and continuity across cuts; zero morphing, warping, glitching hands, or floating
  objects.

ASUR cannot auto-certify photorealism (ASUR-HONEST-01), so each of these is a
**named manual-review flag** a human records on the actual rendered output in the
P06 visual-QA family. If the review is not recorded, visual QA **fails closed to
HOLD**.
