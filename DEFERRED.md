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
**real** video. But only one of the six generation adapters actually produces
media.

| Adapter | Status today | What would make it real |
| --- | --- | --- |
| `generation/adapters/ffmpeg.py` | **REAL.** Renders true 1080x1920 H.264 pixels from the timeline via the local `ffmpeg` binary (solid-colour procedural cards for now). No model, no GPU, no network. Returns provenance + license. | Nothing — it works. Richer visuals come from the image/audio adapters below feeding the same concat path. |
| `generation/adapters/sdxl.py` (images) | **STUB.** Raises `RuntimeError` ("needs the generation extra") then `NotImplementedError` ("human-run, local-only step"). | Add `torch`/`diffusers` to the generation extra; wire the lazy body; run locally on a machine with a GPU/MPS. Deliberately a human-run local step (G10: no GPU/no network in CI). |
| `generation/adapters/kokoro.py` (voice) | **STUB.** Same two-stage raise. | Add `kokoro` + `espeak-ng`; wire the lazy body; run locally. |
| `generation/adapters/stable_audio.py` (music) | **STUB.** Same. | Add `stable_audio_tools`; wire + run locally. |
| `generation/adapters/wan22.py` (AI video) | **STUB.** Same. | Add `torch`; needs a real GPU; run locally. |
| `generation/adapters/faster_whisper.py` (captions) | **STUB in this path.** (The standalone `edit_video.py` already uses faster-whisper directly.) | Wire the adapter body; `faster-whisper` is already in the extra. |
| `editing/adapters/otio.py` (timeline interchange) | **STUB.** `to_otio`/`from_otio` raise `NotImplementedError`. | Wire against `opentimelineio` (in the extra). Not needed for a render — FFmpeg renders straight from the timeline. |

So: **a full idea -> real .mp4 works offline today**, but the scenes are
procedural colour cards, not AI imagery/voice/music. Those are a deliberate,
honest, human-run local-only upgrade — not something CI pretends to do.

---

## 2. The generation extra is incomplete

`pyproject.toml` `[project.optional-dependencies].generation` lists only
`moviepy`, `faster-whisper`, `librosa`, `opentimelineio` (all unpinned).
Missing for the stubbed adapters above: `torch`, `diffusers`, `kokoro`,
`stable_audio_tools`. Needs: add them (pinned) in the same change that wires
the first real SDXL/Kokoro adapter.

---

## 3. Dispatcher prompt-sourcing is crude

`generation/dispatch.py` `run_job` passes the `timeline` to the FFmpeg adapter
(correct) but passes the **asset_ref string** as the prompt/text to every
other adapter. A real SDXL/Kokoro run needs the actual scene text (spoken
words, visual concept, hero words) from the visual screenplay, not the asset
id. Needs: thread the screenplay scene into the job and hand the real prompt
to the adapter when the image/voice adapters go live.

---

## 4. Enforcement that is partial or human-only

| Obligation | Stated in | Enforced today | Needs |
| --- | --- | --- | --- |
| Firewall holds on a **real** run (VIRAL_VIEW strips named targets) | ASUR-FIREWALL-01 | Unit tests + one integration test that greps the view's `repr` for forbidden tokens; CI greps source for the target names. | A structural (not repr-grep) conformance assertion over the exact projection the evaluator receives at render time. |
| Every asset carries complete provenance + license | ASUR-PROV-01 | The FFmpeg adapter returns a provenance+license dict; the license guard fails closed on trapped models. | Schema-validate that *every* produced asset (once real adapters land) carries the full block, not just the renderer's. |
| Two human gates (hero-proof stage 18, publish stage 25) | ASUR-HUMAN-01 | Honored in code paths via `approval_gate`. On a solo machine producer == approver, so it records `HOLD:SELF_APPROVED` (honest, not a fake pass). | A second real local identity to reach a true distinct-approver `SHIP`. Single-user self-approval is intended, not a bypass. |
| Type safety | — | `mypy asur` runs in CI but is **advisory** (`|| true`), not blocking. | Make mypy blocking once the codebase is clean. |

---

## 5. Known open SPEC-GAP

**G15** — `part1` / `part2` / `part3` at the parent directory are 0-byte files.
They are flagged and ignored; they are not inputs. Open only in the sense that
they have never been used. (All other gaps G1-G18 are resolved — see
`docs/build/OPEN_QUESTIONS.md`.)

---

*Keep this file honest. If you build the real thing, delete its row here in
the same change.*
