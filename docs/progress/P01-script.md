# P01 — Finish the SCRIPT brain  ✅ DONE

## What this phase is for

The SCRIPT brain already turns a one-line idea into a full scored script
(idea → research → audience → strategy → 20+ hooks → script → quality gate).
P01 adds the last two missing pieces.

## What P01 adds

1. **Hook A/B options (data only).** Group the generated hooks into labelled
   variants A / B / C / D (e.g. a curiosity angle vs a contrarian angle vs a story
   angle). This is just organised *options* for later testing — nothing is tested
   live yet (live testing waits for the viral check + learning phases).

2. **Hook memory.** Keep a running, append-only record of every hook ever made,
   used, rejected, or published — with its details. Next time, the originality
   check can compare new hooks against real past hooks so it stops repeating itself.
   Nothing is ever overwritten.

## Safety promises kept

- Pure local Python, no internet, no extra installs (the P00 guard test checks this).
- Same idea in → same result out (repeatable).
- Every choice has a written reason.

## Status

**Done.** Both pieces are built, wired into the CLI, and tested. All **60 tests**
pass. Live check: running the same idea twice shows the second run comparing against
the 21 hooks remembered from the first run — and the originality check correctly flags
a repeat. Nothing was overwritten; the memory file only grows.
