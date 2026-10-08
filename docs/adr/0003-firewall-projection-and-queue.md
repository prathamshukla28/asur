# ADR-0003: Firewall as a pure projection function + named-forbidden strip + greppable conformance + hash-chained hand-off queue

- Status: Accepted
- Date: 2026-10-07
- Deciders: local principals (project owner)
- Invariant(s) protected: ASUR-FIREWALL-01, ASUR-GATE-01

## Context

GENERATION (the creator) and VIRAL CHECK (the evaluator) must never communicate
directly. If they shared a channel, the generator could tune content to whatever
the evaluator rubber-stamps (reward hacking). Trinity solved this with a pure
projection function (not crypto); ASUR keeps that mechanism key-free. See
`docs/ARCHITECTURE.md §3`, `SPEC.md §3`, and SPEC-GAPs G4 and G5.

## Decision

1. **Pure projection function** (`asur/tools/projection.py`, built in P03): SCRIPT
   is the only bridge. From the canonical input closure it recomputes two views
   and refuses any view whose bytes differ (fails closed on mismatch/absence):
   - `GENERATION_VIEW` = brief + hooks + quality **floors**. It never carries the
     viral-checker pass criteria / gate thresholds.
   - `VIRAL_VIEW` = rendered-bundle hashes + provenance + platform facts. The
     quality/hardness **targets are stripped by name** (greppable), so the
     evaluator never sees what "good" was defined as.
2. **Named-forbidden strip + greppable conformance test**: forbidden target field
   names are stripped by name and a conformance test greps the produced
   `VIRAL_VIEW` for them; if any leaks, the test fails closed.
3. **Static cross-import check**: GENERATION code may never import/call VIRAL
   CHECK code or vice-versa; a grep/AST check fails the build if it happens.
4. **Hash-chained hand-off queue** (`.asur/queue/<run_id>.jsonl`, built in P03):
   the only producer→consumer channel. Flow `seal → claim → verdict → place`.
   SHA-256 integrity only (no signing). `claim` is atomic (`O_EXCL`); a bundle is
   frozen on seal; `place` happens only when sealed digest == verdict digest ==
   on-disk digest (3-way agreement) else BLOCK.

## Consequences

- Positive: structural anti-reward-hacking; the moat (honest firewalled
  evaluator) is enforced by code, not discipline. 100% local, key-free.
- Negative: more moving parts than a direct call; the projection must be a true
  pure function with a conformance test or the guarantee is hollow.
- Follow-up: implemented in P03; until then GENERATION/VIRAL CHECK phases are
  BLOCKED. Closes the design side of SPEC-GAPs G4 and G5 (implementation in P03).

## Alternatives considered

- Direct GENERATION↔VIRAL CHECK call: rejected — enables reward hacking.
- Crypto-signed envelopes (Trinity): rejected — needs keys (ADR-0001/0008).
