# Deferred register

ASUR's founding promise is honesty: no black box, and never a claim the
machine cannot back up (ASUR-HONEST-01, ASUR-EXPLAIN-01). This register
applies that promise to ASUR itself.

Every row below is an obligation the design states and that nothing (or only
a human) currently enforces. The rules are not wrong and they are not
abandoned. They are written here so anyone can tell, without reading the
whole spec, which of ASUR's refusals and capabilities are **real today** and
which are **intentions wearing the grammar of a requirement**.

A rule leaves this register in exactly one direction: something is built that
actually enforces or performs it, and the row is deleted in the same change
that lands the real thing. A rule may not leave by being reworded.

The pattern is borrowed from the sibling Trinity project's `DEFERRED.md`.

---

## 1. Generation adapters (real pixels vs. stubs)

ASUR plans the whole video (idea -> script -> creative direction -> visual
screenplay -> asset plan -> generation plan -> timeline) and now renders a
**real** video, compositing produced AI backgrounds and muxing produced audio.
Five of the six generation adapters carry real, wired bodies and are composited
into the render; only AI video (Wan 2.2) and the OTIO interchange remain stubs.

| Adapter | Status today | What remains |
| --- | --- | --- |
| `generation/adapters/ffmpeg.py` | **REAL.** Renders true H.264 pixels from the timeline via the local `ffmpeg` binary at the pack resolution: produced AI background images are composited (scale-to-cover + centre-crop), with solid-colour cards as the fallback for scenes with no image, plus burned-in captions and optional audio mux. No model, no GPU, no network. Returns provenance + license. | Nothing — it works. |
| `generation/adapters/sdxl.py` (images) | **REAL (human-run local-only).** Lazy-imports `torch`/`diffusers`/`PIL`; generates a 1080x1920 portrait PNG on MPS/CUDA/CPU; returns provenance + license. Fails closed with `RuntimeError` if the generation extra is absent. Real-run lines are `# pragma: no cover` (G10: no GPU/no network in CI). Produced by `produce_assets` and composited into the render (P11b). | Nothing — deps pinned in the extra (P11c, G28). |
| `generation/adapters/kokoro.py` (voice) | **REAL (human-run local-only).** Lazy-imports `kokoro`/`numpy`/`soundfile`; synthesises a 24 kHz WAV; returns provenance + license. Fails closed without the extra. `# pragma: no cover`. Produced by `produce_assets` and muxed into the render (P11b). | Nothing — deps pinned in the extra (P11c, G28). |
| `generation/adapters/stable_audio.py` (music) | **REAL (human-run local-only).** Lazy-imports `torch`/`torchaudio`/`stable_audio_tools`; generates a 44.1 kHz stereo WAV; returns provenance + license. Fails closed without the extra. `# pragma: no cover`. Produced by `produce_assets`; the renderer now mixes voice over ducked music when both are present (two-track mix landed). | Nothing — two-track voice-over-ducked-music mix landed in the renderer. |
| `generation/adapters/faster_whisper.py` (captions) | **REAL (human-run local-only).** Lazy-imports `faster_whisper`; transcribes an input audio file with deterministic greedy decoding + word timestamps; returns provenance + license. Fails closed without the extra. `# pragma: no cover`. The dispatcher now feeds it the produced voice WAV via `params['audio_path']` (P11b). | Deps: `faster-whisper` is already in the extra. |
| `generation/adapters/wan22.py` (AI video) | **STUB.** Lazy-imports `torch` then raises `NotImplementedError` ("human-run, local-only GPU step"). | Add `torch`; needs a real GPU; run locally. Deferred past P11 (SPEC-GAP G29). |
| `editing/adapters/otio.py` (timeline interchange) | **REAL (human-run local-only).** Lazy-imports `opentimelineio`; `to_otio` builds a standard OTIO track/clip structure and `from_otio` reads back a lossless ASUR Timeline dict (stashed as a JSON string in OTIO metadata, since OTIO's `AnyDictionary` coerces nested containers). Fails closed without the extra and `from_otio` fails closed if the OTIO object carries no ASUR metadata. `# pragma: no cover` on the extra-only paths. | Nothing — `opentimelineio` is already pinned in the extra. |

So: **a full idea -> real .mp4 works offline today** — procedural colour cards
when run stdlib-only, or real AI backgrounds + voice/music when the
`asur[generation]` extra is installed and `produce_assets` runs first. The AI
adapters are a deliberate, honest, human-run local-only upgrade (they fail closed
without the extra and never run in CI) — not something CI pretends to do.

---

## 2. Enforcement that is partial or human-only

| Obligation | Stated in | Enforced today | Needs |
| --- | --- | --- | --- |
| Two human gates (hero-proof stage 18, publish stage 25) | ASUR-HUMAN-01 | Honored in code paths via `approval_gate`. On a solo machine producer == approver, so it records `HOLD:SELF_APPROVED` (honest, not a fake pass). | A second real local identity to reach a true distinct-approver `SHIP`. Single-user self-approval is intended, not a bypass. |
| Life Mentor encryption at rest | Life Mentor CHARTER §3 (SPEC-GAP LM-G1) | macOS FileVault + 0700/0600 permissions + refusal of loose/symlinked store roots. Data files themselves are plaintext JSON. | An optional `cryptography` extra (authenticated encryption of `~/.life_mentor`) — new dependency, needs a human gate. |
| Weekly Tracker calendar **network sync** | User request "weekly calendar" (SPEC-GAP WT-G8) | Local `.ics` export now ships (`weekly-tracker plan ics`, stdlib `weekly_tracker/ics.py`); the planner also still writes Markdown. No Google/Outlook network sync. | Opt-in two-way network sync behind a human gate (network, accounts) — deliberately not built; the local `.ics` file is imported by hand. |
| Life Mentor wearable / health-platform import | LM10 brief (Apple Health, Google Fit, wearables) | Nothing imported; health metrics are entered by hand or via the metric log. | Opt-in local-export parsers behind a human gate; no account linking. |
| Life Mentor bank / account-aggregator APIs | LM10 brief | Only user-downloaded CSV statements are imported (`life-mentor import bank-csv`). | Network + credentials: needs a human gate and a security review; not planned without one. |
| Life Mentor rule-value refresh | Life Mentor CHARTER §2 LM-RULE (SPEC-GAP LM-G4) | RulePacks are edited by hand; `rules_gate` HOLDs stale values and flags unverified ones. Nothing fetches updates. | An explicit, human-run network refresh CLI (never implicit, never in tests); MoSPI CPI needs a token so stays manual. |

---

## 3. Known open SPEC-GAP

**G15** — `part1` / `part2` / `part3` at the parent directory are 0-byte files.
They are flagged and ignored; they are not inputs. Open only in the sense that
they have never been used. (All other gaps G1-G18 are resolved — see
`docs/build/OPEN_QUESTIONS.md`.)

---

*Keep this file honest. If you build the real thing, delete its row here in
the same change.*
