# Viral check report: README demo

This is the real viral-check output for [`demo.mp4`](demo.mp4) (the same file
that [`demo.gif`](demo.gif) is cut from). Nothing below was edited by hand: the
numbers are copied from the `viral_check` artifact that `asur run` wrote.

- **File:** `final-video.mp4`, 1080x1920, 30 fps, 53.6 s, H.264 + AAC, 5,052,562 bytes
- **sha256:** `2a9c7b9accd7b4a4b0f32fc131ba04db660d89b61c7ca0308608c7d3c4af8317`
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
  Its paths are shown as `<project>` below.
- **Render and measure:** ffmpeg 7.1 static build from `imageio-ffmpeg==0.6.0`
  (wheel sha256 checked against PyPI, has `drawtext`), set with
  `ASUR_FFMPEG`. Homebrew ffprobe 9.0.2. Generator: offline templates.
- **Narration:** macOS `say` (system voice). Those voices are licensed for
  personal, non-commercial use, so the publish gate records the voice as
  non-commercial. espeak-ng was not installed.
- **Run time:** about 41 s wall clock on an Apple-silicon Mac. Exit code 1
  (HELD).

## Verdict: PASS-WITH-CHANGES, so the gate holds

The verdict covers only the 4 measured dimensions and the risk flags. The other
8 dimensions are `unknown` because a file probe cannot measure them.

| Dimension | Score | Components (value x weight, source: measured input) |
|---|---:|---|
| Attention | **77** | opening_change 0.60 x 0.5 (measured: 0 cuts in the first 3 s, 0.0 s frozen); opening_not_black 1.00 x 0.2 (measured: 0.0 s black at start); hook_length 0.917 x 0.3 (plan: 13-word hook) |
| Retention | **87** | captions 1.00 x 0.3 (plan: authored, and burned in); pacing 1.00 x 0.3 (measured: 7.84 scene changes/min); motion 1.00 x 0.2 (measured: frozen_ratio 0.0); speech_continuity 0.371 x 0.2 (measured: 16.85 s of silence) |
| Visual Quality | **100** | resolution 1.00 x 0.5 (1080x1920); fps 1.00 x 0.2 (30); not_black 1.00 x 0.3 (0.0 s black) |
| Platform Fit | **93** | aspect 1.00 x 0.35 (9:16); duration 1.00 x 0.25 (53.6 s, ceiling 180 s); audio 1.00 x 0.2 (mean -20.9 dB); loudness 0.65 x 0.2 (-19.5 LUFS against a -14 target) |
| Satisfaction, Value, Shareability, Saveability, Replayability, Originality, Authenticity, Audience Fit | unknown | Not measurable from a file. They need human ratings or real audience data. |

Risk flags:

- soft `long_silence`: "RISK: 2.7s silent gap -> dead air invites a swipe"
  (measured 2.726 s)

Publish gate (human gate #2):

```
[HOLD] PUBLISH_READY                HUMAN gate #2: publish checks
      disposition : HOLD (CONTENT_HOLD)
        [ok  ] final_file_present: <project>/youtube/asur-demo/render/final-video.mp4 present
        [ok  ] checksum_matches_viral_check: file sha256 matches the measured bundle (sha256:2a9c7b9accd7...)
        [HOLD] viral_check_completed: viral check PASS-WITH-CHANGES: fix ['long_silence'] before publishing
        [ok  ] audio_present: audio track muxed
        [ok  ] duration_within_platform_bounds: 53.6s within upload bounds
        [ok  ] package_materialized: package at <project>/youtube/asur-demo/package
        [ok  ] asset_licenses_recorded: licenses recorded; personal/non-commercial only: ['macOS system voice']
        [ok  ] approval: self-approval explicitly permitted

Result: HELD at PUBLISH_READY. Run log: .asur/runs/run-1.jsonl
```

The remaining hold is real. The template script's spoken lines are shorter than
their scenes, so the narration leaves a 2.7 s gap. The fix belongs in the
script and its timing, not in the checker.

## Before and after: same script, same checker

"Before" is the previous run of the same command. It used Homebrew ffmpeg 9.0.2,
which has no `drawtext`, and the old renderer, which drew static solid-colour
cards (sha256 `beef7559bfa7...`).

| | Before | After |
|---|---:|---:|
| Attention | 27 | **77** |
| Retention | 7 | **87** |
| Visual Quality | 97 | **100** |
| Platform Fit | 93 | 93 |
| frozen_ratio (freezedetect) | 1.00 | **0.00** |
| scene changes/min (scdet) | 0.0 | **7.84** (7 of the 8 scene boundaries detected) |
| black at start (blackdetect) | 4.8 s (the dark first card read as black) | **0.0 s** |
| captions burned in | no (no drawtext) | **yes** |
| soft risk flags | long_silence, static_opening, mostly_static, captions_missing | long_silence |
| verdict / gate | PASS-WITH-CHANGES / HOLD | PASS-WITH-CHANGES / HOLD |

Re-measuring both files with both ffmpeg builds (9.0.2 and 7.1) gives
identical probe numbers. The improvement comes from the pixels, not from a
different measuring tool.

What changed in the render (all pure ffmpeg filters, deterministic: two runs
produced byte-identical MP4s):

- the background is a slowly rotating two-colour gradient (`gradients`), with
  cards alternating dark and bright so each scene change is a real visual change
- a progress bar fills across the whole video (`overlay` with a time expression)
- authored captions are word-wrapped, and each line fades and slides in on a
  0.22 s stagger (`drawtext` alpha/y expressions)
- a 0.12 s `xfade` slide-up connects consecutive scenes
- produced background images (SDXL) get a slow Ken Burns zoom (`zoompan`)
