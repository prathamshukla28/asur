# P00 — Foundations & Rulebook  ✅ DONE

## What this phase is for

Before building any more features, lock down the rules and the safety guards so
everything built later stays honest and 100% local. No video features here — just
the foundation.

## What got done

1. **8 decision records (ADRs) written and accepted** — the permanent "why we
   decided this" notes, in `docs/adr/`:
   - 0001 — Identity is just your computer login + git name/email. No passwords, no logins.
   - 0002 — The core stays pure Python standard library (nothing extra to install, nothing phones home).
   - 0003 — The firewall between "maker" and "judge", and the safe hand-off queue.
   - 0004 — FFmpeg is the default (free) video renderer; the old "Sora" option is gone for good.
   - 0005 — Every asset carries its licence; risky licences are blocked by name.
   - 0006 — The honest viral check: 12 separate scores, never one fake "%".
   - 0007 — The renaming map (the four parts of ASUR and what they do).
   - 0008 — We keep secure "fingerprints" of files, but dropped all the heavy signing keys.

2. **A place to declare video tools later** — added an optional `asur[generation]`
   install group in `pyproject.toml`. The core never touches it; it's only pulled in
   when you actually make video.

3. **A guard test** — `tests/test_boundary.py` automatically fails the build if the
   core ever tries to import something non-local (internet or heavy media libraries).
   This is what keeps the "100% local" promise honest forever.

## Proof it works

- `python3 -m pytest -q` → **52 passed** (23 core + 13 pipeline + 16 guard checks).

## Status

**Done.** Moving on to P01.
