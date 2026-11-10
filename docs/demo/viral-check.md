# Viral check report: README demo

This is the real viral-check output for [`demo.mp4`](demo.mp4) (the same file
that [`demo.gif`](demo.gif) is cut from). Nothing below was edited by hand: the
numbers are copied from the `viral_check` and `edit_plan` artifacts that
`asur run` wrote.

- **File:** `final-video.mp4`, 1080x1920, 30 fps, 40.7 s, H.264 + AAC, 4,007,900 bytes
- **sha256:** `fb717f6a9e827555b48dbf870ece83ba2a75450fea035ea3da36dec5db83db9f`
  (`shasum -a 256 docs/demo/demo.mp4` gives the same hash, so this is the file
  that was measured)
- **Command:**
  ```bash
  export ASUR_FFMPEG="$(python -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')"
  asur run --project /tmp/asur-demo \
    --idea "why most people waste money on AI tools" \
    --takeaway "list every AI subscription you pay for and cancel the ones that run the same underlying model" \
    --self-approve
  ```
  The recorded run used a scratch directory named `asur-demo` as `--project`.
- **Render and measure:** ffmpeg 7.1 static build from `imageio-ffmpeg==0.6.0`
  (wheel sha256 checked against PyPI, has `drawtext`), set with
  `ASUR_FFMPEG`. Homebrew ffprobe 9.0.2. Generator: offline templates.
- **Narration:** macOS `say` (system voice). Those voices are licensed for
  personal, non-commercial use, so the publish gate records the voice as
  non-commercial. espeak-ng was not installed.
- **Run time:** about 30 s wall clock on an Apple-silicon Mac. Exit code 0.
- **`asur verify-repro`:** every stored planning stage, including the timed
  `edit_plan`, rebuilt byte-for-byte.

## Verdict: PASS, so the gate ships

The verdict covers only the 4 measured dimensions and the risk flags. The other
8 dimensions are `unknown` because a file probe cannot measure them.

| Dimension | Score | Components (value x weight, source: measured input) |
|---|---:|---|
| Attention | **77** | opening_change 0.60 x 0.5 (measured: 0 cuts in the first 3 s, 0.0 s frozen); opening_not_black 1.00 x 0.2 (measured: 0.0 s black at start); hook_length 0.917 x 0.3 (plan: 13-word hook) |
| Retention | **99** | captions 1.00 x 0.3 (plan: authored, and burned in); pacing 1.00 x 0.3 (measured: 8.85 scene changes/min); motion 1.00 x 0.2 (measured: frozen_ratio 0.0); speech_continuity 0.928 x 0.2 (measured: 1.475 s of silence) |
| Visual Quality | **100** | resolution 1.00 x 0.5 (1080x1920); fps 1.00 x 0.2 (30); not_black 1.00 x 0.3 (0.0 s black) |
| Platform Fit | **93** | aspect 1.00 x 0.35 (9:16); duration 1.00 x 0.25 (40.7 s, ceiling 180 s); audio 1.00 x 0.2 (mean -19.7 dB); loudness 0.64 x 0.2 (-19.6 LUFS against a -14 target) |
| Satisfaction, Value, Shareability, Saveability, Replayability, Originality, Authenticity, Audience Fit | unknown | Not measurable from a file. They need human ratings or real audience data. |

Risk flags: none. The longest silent gap is 1.475 s, under the 2.0 s
`long_silence` threshold. The densest caption runs at 3.27 words/s, under the
3.5 limit. Loudness is -19.6 LUFS, inside the 6 LU tolerance; it still costs
Platform Fit points.

Run output:

```
  narration timing: scenes fitted to measured speech (53.6s planned -> 40.7s)
[->] HERO_PROOF_READY             hero proof (hook scene rendered + ffprobe-verified)
[->] HERO_PROOF_APPROVED          HUMAN gate #1: approve hero proof
[->] FULL_GENERATION              full render 1080x1920 40.7s audio=True
[->] QA                           QA on the rendered file
  verdict  : PASS  (verdict covers the 4 measured dimension(s) and risk flags only)
[->] VIRAL_CHECK_APPROVED         viral check over the rendered bytes
[->] PUBLISH_READY                HUMAN gate #2: publish checks

Result: PUBLISH_READY. Upload the files in <project>/youtube/asur-demo/package yourself;
ASUR never posts (ASUR-HUMAN-01).
```

PUBLISH_READY means the gate checks passed. ASUR never uploads anything. The
voice licence is recorded as personal and non-commercial only, so this file is
fine as a portfolio demo but not for commercial posting.

## Scene timing: measured speech instead of an estimate

The script planner sizes scenes at 2.5 words/s. macOS `say` speaks faster than
that, and the narration used to be padded out to each planned scene. That left
dead air at the end of every scene: 16.85 s of silence in all, the longest gap
2.73 s, which set the `long_silence` flag.

Now each spoken line is synthesized first, trimmed of the engine's own
leading and trailing silence, and measured with ffprobe. Each scene then lasts
as long as its line plus a 0.3 s pad. Two floors apply: the time needed to read
the scene's on-screen caption at 3.3 words/s, and a 1.0 s minimum. A scene with
no narration is capped at 1.5 s.

| Scene | Speech (s) | Planned (s) | Timed (s) |
|---|---:|---:|---:|
| hook | 3.895 | 4.8 | 4.2 |
| opening | 2.809 | 4.4 | 3.2 |
| problem | 4.362 | 6.4 | 4.7 |
| context | 2.594 | 3.6 | 2.9 |
| story | 5.723 | 7.6 | 6.1 |
| value | 7.138 | 9.6 | 7.5 |
| proof | 3.836 | 6.0 | 4.2 |
| payoff | 4.033 | 6.4 | 5.5 (the 18-word caption's reading floor) |
| cta | 2.035 | 4.8 | 2.4 |

The one remaining 1.475 s silence is the payoff scene. It is held a little
longer than its spoken line so its 18-word caption stays readable.

## Before and after: same script, same checker

| | Static cards (first run) | Animated, planned timing | Animated, measured timing (this file) |
|---|---:|---:|---:|
| Attention | 27 | 77 | **77** |
| Retention | 7 | 87 | **99** |
| Visual Quality | 97 | 100 | **100** |
| Platform Fit | 93 | 93 | **93** |
| duration | 53.6 s | 53.6 s | **40.7 s** |
| silence total / longest gap | 16.85 s / 2.73 s | 16.85 s / 2.73 s | **1.48 s / 1.48 s** |
| frozen_ratio | 1.00 | 0.00 | **0.00** |
| captions burned in | no | yes | **yes** |
| risk flags | long_silence, static_opening, mostly_static, captions_missing | long_silence | **none** |
| verdict / gate | PASS-WITH-CHANGES / HOLD | PASS-WITH-CHANGES / HOLD | **PASS / SHIP** |

What the render does (all pure ffmpeg filters, deterministic):

- the background is a slowly rotating two-colour gradient (`gradients`), with
  cards alternating dark and bright so each scene change is a real visual change
- a progress bar fills across the whole video (`overlay` with a time expression)
- authored captions are word-wrapped, and each line fades and slides in on a
  0.22 s stagger (`drawtext` alpha/y expressions)
- a 0.12 s `xfade` slide-up connects consecutive scenes
- produced background images (SDXL) get a slow Ken Burns zoom (`zoompan`)
