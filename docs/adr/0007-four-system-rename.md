# ADR-0007: 4-system rename (Trinity lineage → ASUR); EDITING is a shared human-controlled env

- Status: Accepted
- Date: 2026-10-07
- Deciders: local principals (project owner)
- Invariant(s) protected: — (naming/architecture clarity)

## Context

ASUR adapts Trinity's architecture (phases, gates, firewall, learning) but is not
a code copy and serves a different purpose (viral content creation vs adversarial
eval authoring). The vocabulary must be ASUR-native so the codebase, docs, and
agents speak one language. See `docs/ARCHITECTURE.md` and `SPEC.md §2`.

## Decision

Authoritative, locked rename map:

| Trinity (ancestor) | ASUR | Workspace | Root report |
|---|---|---|---|
| Trinity (whole) | **ASUR** | — | — |
| ENGRAM (memory) | **SCRIPT** | `.script/` | DIRECTIVE.md |
| FORGE (author) | **GENERATION** | `.generation/` | EDICT.md |
| CRUCIBLE (inspector) | **VIRAL CHECK** | `.viral/` | VERDICT.md |
| MAESTRO (conductor) | **ORCHESTRATOR** | — | — |

**EDITING** is a shared, human-controlled editing environment — **not a 4th
instrument**. SCRIPT is the only firewall bridge between GENERATION and VIRAL
CHECK.

Trinity/ENGRAM/FORGE/CRUCIBLE/MAESTRO names may appear in docs **only** as clearly
labelled "ancestor" provenance notes. The document.pdf's stray "Trinity→Editing"
line is **superseded** by this map. Code contains none of the legacy names.

## Consequences

- Positive: one consistent vocabulary across code, docs, agents, CLI.
- Negative: readers who know Trinity must learn the mapping; the ancestor labels
  in docs ease that (SPEC-GAP G1 default: keep as provenance notes).
- Follow-up: none; rename already honored in code (grep-verified clean).

## Alternatives considered

- Keep Trinity names: rejected — wrong domain, confusing for a content product.
- Make EDITING a 4th instrument: rejected — editing is where the human shapes
  output; promoting it to an instrument would blur the firewall and human
  ownership (ASUR-HUMAN-01).
