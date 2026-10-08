# P02 — The Controller  ✅ DONE

## What this phase is for

Right now the SCRIPT steps run one after another. P02 builds the real **controller**
that knows the full project state and runs stages in the correct order — and
**refuses to skip a safety check**.

## What P02 added

- **State machine** — the 18 official project states (from DRAFT all the way to
  LEARNED). You can only move forward one safe step at a time; a failed gate holds
  in place or sends you back, never skips ahead.
- **Orchestrator** — the conductor. It only carries small control tokens (which
  state, which gate, pass/hold/block). It never carries the actual findings or
  secret targets between the maker and the judge.
- **More commands** — `asur run`, `asur generate`, `asur viral-check` (on top of
  `asur script`). `run` drives the SCRIPT steps and stops safely at the first gate
  that isn't wired yet. `generate` and `viral-check` exist but say honestly
  "not built yet" instead of faking work — those instruments arrive in later phases.
- **A plain activity log** — a simple local record of what ran, written one line at
  a time to `.asur/runs/<run-id>.jsonl`. It only ever records the small control
  tokens, nothing secret, and never phones home.
- **Cost tiers** — cheap steps run freely; expensive steps are locked until the
  human hero-proof approval (stage 18).

## Safety promises kept

- Fails safe: a missing input or approval means HOLD or BLOCK, never "just proceed".
- The two human gates can't be auto-skipped (single-user approval is recorded
  honestly as "self-approved").
- Expensive work literally can't start before you approve the hero proof.

## Status

**Done.** 84 tests pass (`python3 -m pytest -q` from `asur/`).
