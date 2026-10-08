# ADR-0004: FFmpeg/MoviePy locked default renderer; Remotion optional; Sora removed

- Status: Accepted
- Date: 2026-10-07
- Deciders: local principals (project owner)
- Invariant(s) protected: ASUR-PROV-01, ASUR-HONEST-01

## Context

ASUR must render a 9:16 Instagram Reel end to end, locally and license-clean, at
zero marginal cost. Some renderers (Remotion) carry a real per-render cost;
OpenAI's Sora 2 API was sunset 2026-09-24 and is unavailable. See
`docs/GENERATION_STACK.md §5/§8` and SPEC-GAP G8.

## Decision

- **FFmpeg + MoviePy is the LOCKED default renderer** (`render_cost_usd: 0`).
- **Remotion is optional only**, and when used its real per-render cost is tracked
  in the provenance/cost record (never silently incurred).
- **Sora is removed entirely** — it must never appear in any option set, adapter,
  model table, doc example, or default. A grep test enforces its absence.
- Every rendered asset carries a provenance block (model, version, prompt, seed,
  inputs, transforms, editor, generated_at, generation_time_s, render_cost_usd)
  per ASUR-PROV-01; local renders record `render_cost_usd: 0` honestly.

## Consequences

- Positive: zero-cost, offline, deterministic default; honest cost accounting;
  no dependence on a sunset API.
- Negative: FFmpeg/MoviePy is lower-level than Remotion for complex motion; the
  15 motion primitives (EDITING, P05) must be built on it. Accepted.
- Follow-up: renderer adapters built in P04; Sora-absence grep test added. Closes
  the design side of SPEC-GAP G8.

## Alternatives considered

- Remotion as default: rejected — real per-render cost conflicts with the
  zero-cost local-first goal; kept as an optional upgrade.
- Cloud video (Veo/Runway) as default: rejected — paid + network; allowed later
  only as an explicit opt-in behind a human gate.
