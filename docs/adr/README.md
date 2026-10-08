# Architecture Decision Records (ADRs)

ADRs capture **why** a decision was made, so it is not silently reversed later. In
ASUR, changing anything in the frozen `docs/spec/SPEC.md` requires a new ADR plus a
logged SPEC-GAP. Higher-precedence sources win (SPEC > 9 design docs > ADRs > code
> `document.pdf`); an ADR records a decision consistent with that order.

## Template

```
# ADR-NNNN: <short title>

- Status: Proposed | Accepted | Superseded by ADR-MMMM
- Date: YYYY-MM-DD
- Deciders: <local principals>
- Invariant(s) protected: <ASUR-...>

## Context
What problem/force prompted this decision. Reference the spec/doc section.

## Decision
The decision, stated plainly.

## Consequences
Positive, negative, and follow-ups (incl. any SPEC-GAP opened/closed).

## Alternatives considered
What else, and why not.
```

## Index (seed ADRs — author in P00 via `/architecture`)

These record decisions already made and locked. Author each as `ADR-0001`.. under
this folder with status **Accepted**.

| ADR | Title | Invariant(s) |
|---|---|---|
| 0001 | Key-free local identity (whoami + git config; any local user clears gates; no remote auth) | ASUR-LOCAL-01, ASUR-HUMAN-01 |
| 0002 | Stdlib-only core; media behind the `asur[generation]` optional extra (import-linter enforced) | ASUR-LOCAL-01 |
| 0003 | Firewall as a pure projection function + named-forbidden strip + greppable conformance + hash-chained seal→claim→verdict→place queue | ASUR-FIREWALL-01, ASUR-GATE-01 |
| 0004 | FFmpeg/MoviePy locked default renderer (cost 0); Remotion optional; **Sora removed** (sunset 2026-09-24) | ASUR-PROV-01, ASUR-HONEST-01 |
| 0005 | License as a first-class provenance field with a hard-coded trap list; monetized + commercial_ok:false (or cap/territory) fails closed naming the asset | ASUR-PROV-01, ASUR-GATE-01 |
| 0006 | Honest viral evaluation: 12 individual dimensions, 4 evidence classes, binary risk flags, verdict PASS/PASS-WITH-CHANGES/REJECT; **never a single %viral number** | ASUR-HONEST-01 |
| 0007 | 4-system rename Trinity→ASUR, ENGRAM→SCRIPT, FORGE→GENERATION, CRUCIBLE→VIRAL CHECK, MAESTRO→ORCHESTRATOR; EDITING = shared human-controlled env (not a 4th instrument) | — |
| 0008 | De-keying: KEEP SHA-256 for byte-integrity/lineage + producer≠approver by local principal; DROP all SSH/DSSE/signing | ASUR-LOCAL-01, ASUR-VERSION-01 |

Each ADR is immutable once Accepted; revise by writing a new ADR that supersedes it.
