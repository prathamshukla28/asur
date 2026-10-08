# ADR-0005: License as a first-class provenance field with a hard-coded trap list

- Status: Accepted
- Date: 2026-10-07
- Deciders: local principals (project owner)
- Invariant(s) protected: ASUR-PROV-01, ASUR-GATE-01

## Context

ASUR mixes AI-generated, procedural, licensed-stock, and original assets. Some
otherwise-attractive models carry license terms that forbid commercial/monetized
use or restrict territory/revenue (e.g. FLUX dev non-commercial, XTTS v2 CPML
non-commercial, MusicGen CC-BY-NC, HunyuanVideo EU/UK/KR + MAU cap, CogVideoX-5B
traffic cap, Suno/Udio avoid). A creator who monetizes must not unknowingly ship
an asset that forbids it. See `docs/GENERATION_STACK.md §7` and SPEC-GAP G9.

## Decision

Every asset carries a first-class `license` block:
`{name, commercial_ok, revenue_cap_usd, territory_exclusions[],
training_data_provenance, source_url, notes}`.

A license guard (built in P04) holds a **hard-coded trap list** of known
non-commercial / capped / restricted models. The guard **fails closed, naming the
offending asset**, when a project is monetized and any asset has
`commercial_ok: false`, OR a revenue cap / territory exclusion is violated. The
gate disposition is `BLOCK:LICENSE_VIOLATION`.

## Consequences

- Positive: a creator cannot silently ship a license-incompatible asset;
  violations name the exact asset (ASUR-EXPLAIN-01) and block (ASUR-GATE-01).
- Negative: the trap list must be maintained as model licenses change; it is
  explicitly a point-in-time snapshot recorded in `GENERATION_STACK.md`.
- Follow-up: license guard module + trap list + test built in P04. Closes the
  design side of SPEC-GAP G9.

## Alternatives considered

- Trust the model's default license silently: rejected — violates ASUR-PROV-01
  and risks the creator's revenue.
- Allow-list only (no trap list): rejected — an allow-list grows stale and would
  block legitimate new clean models; a fail-closed trap list on monetized use is
  the conservative default.
