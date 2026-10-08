# ADR-0001: Key-free local identity

- Status: Accepted
- Date: 2026-10-07
- Deciders: local principals (project owner)
- Invariant(s) protected: ASUR-LOCAL-01, ASUR-HUMAN-01

## Context

The reference architecture (Trinity) proved authorship and gate-clearing with
cryptographic signatures (SSH / DSSE / in-toto, an external trust root). The ASUR
owner required the opposite: the system must run 100% locally with **no remote
login, no GitHub auth, no API keys, and no network call for identity**, and any
local user must be able to clear a gate ("no keys, clear by anyone"). See
`docs/ARCHITECTURE.md §local gate separation` and `SPEC.md §1`.

## Decision

Identity is derived **only** from the local machine: the OS user (`whoami` /
`getpass.getuser()`) plus `git config user.name` and `git config user.email`.
Identity resolution never touches the network and never raises — on any failure
it returns empty strings, and the gate layer (not the identity layer) decides
policy. A principal is `git_email` → `git_name` → `local_user` (first non-empty).

Gate separation is enforced by comparing local principals as plain strings:
producer ≠ approver. A single-user machine may still clear a gate, but when
creator == approver it is recorded honestly as `self_approved = true` and the
disposition is capped at `HOLD:SELF_APPROVED` (never silently promoted to SHIP
unless self-approval is explicitly allowed).

## Consequences

- Positive: zero infrastructure, no secrets to leak, works fully offline,
  satisfies ASUR-LOCAL-01 and ASUR-HUMAN-01.
- Negative: identity is only as trustworthy as the local machine; this is
  accepted because ASUR is a single-creator local tool, not a multi-tenant
  service. "Trust" here means honest attribution, not cryptographic proof.
- Follow-up: the producer≠approver comparison and `HOLD:SELF_APPROVED` honesty
  are implemented in `asur/asur/core/gate.py` (`approval_gate`). No SPEC-GAP.

## Alternatives considered

- SSH / DSSE signing (Trinity's approach): rejected — requires keys and a trust
  root, violating ASUR-LOCAL-01.
- No identity at all: rejected — producer≠approver separation is a genuinely
  useful, key-free integrity property worth keeping (ADR-0008).
