# ADR-0006: Honest viral evaluation — 12 dimensions, 4 evidence classes, binary risk flags, never a single %viral number

- Status: Accepted
- Date: 2026-10-07
- Deciders: local principals (project owner)
- Invariant(s) protected: ASUR-HONEST-01

## Context

Platform ranking functions are private and change constantly. A single "93%
viral" number is misleading and unfalsifiable. Everything a platform "says it
uses" is a VERIFIED FACT about the *statement*, not proof of live weighting. See
`docs/VIRAL_CHECK.md` and `SPEC.md §7`.

## Decision

VIRAL CHECK never outputs a single %viral number. Instead:

1. **12 scoring dimensions**, each 0-100, always shown **individually** (never
   collapsed): Attention, Retention, Satisfaction, Value, Shareability,
   Saveability, Replayability, Originality, Authenticity, Visual Quality,
   Audience Fit, Platform Fit.
2. **4 evidence classes** tag every claim: VERIFIED FACT / STRONG EVIDENCE /
   EMPIRICAL OBSERVATION (this creator's own data) / HYPOTHESIS.
3. Every prediction = **Prediction + Confidence + Evidence + Uncertainty**.
4. Penalties are **binary risk flags**, never percentage deductions.
5. Verdict is **PASS / PASS-WITH-CHANGES / REJECT** — a disposition, not a score.
6. Separate "signal exists" (VERIFIED) from "weight known" (UNKNOWN everywhere).

## Consequences

- Positive: honest, falsifiable, actionable; no false certainty (ASUR-HONEST-01);
  evaluates input quality against documented signals, not a fabricated outcome.
- Negative: users expecting one magic number must read a richer report; this is a
  deliberate product stance and the core differentiator.
- Follow-up: implemented in P07; a test asserts no single %viral number is ever
  emitted. Reinforces (does not close) ongoing honesty discipline.

## Alternatives considered

- Single composite viral score (OpusClip-style): rejected — misleading,
  uncalibrated, and the exact anti-pattern ASUR exists to replace.
