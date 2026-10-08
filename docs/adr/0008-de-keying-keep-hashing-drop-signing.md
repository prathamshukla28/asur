# ADR-0008: De-keying — KEEP SHA-256 for integrity/lineage + producer≠approver; DROP all SSH/DSSE/signing

- Status: Accepted
- Date: 2026-10-07
- Deciders: local principals (project owner)
- Invariant(s) protected: ASUR-LOCAL-01, ASUR-VERSION-01

## Context

Trinity's entire crypto surface funnels through one chokepoint (an SSH-signing
backend) plus DSSE/in-toto envelopes and an external trust root. ASUR must be
key-free (ADR-0001). But two different uses of SHA-256 must not be conflated:
**hashing for byte-integrity/lineage** (pure, no keys) versus **signing for
authorship proof** (key-bound). See `docs/ARCHITECTURE.md §key-free note` and
`SPEC.md §6`.

## Decision

**KEEP (pure, key-free):**
- SHA-256 content hashing for byte-integrity and lineage (checksum over the
  canonical artifact **body only**, so status/review changes don't change the
  content hash; identical bodies → identical `artifact_id` for lineage).
- The hash-chained hand-off queue (seal → claim → verdict → place) — ADR-0003.
- The pure projection function for the firewall — ADR-0003.
- `producer ≠ approver` separation, compared as local principals (ADR-0001).
- HEAD/digest binding (sealed == verdict == on-disk digest, else BLOCK).

**DROP (key-bound):**
- All SSH signing, DSSE / in-toto envelopes, external signers, trust-root
  authorization, crypto sentinel clearances, remote/submodule roster.
- Authorship-proof-by-signature → replaced with local-identity attribution.

## Consequences

- Positive: all genuinely useful integrity properties survive with zero keys and
  zero network (ASUR-LOCAL-01, ASUR-VERSION-01); nothing is silently overwritten.
- Negative: ASUR cannot cryptographically prove *who* authored a bundle to a
  third party — acceptable for a local single-creator tool; attribution is
  honest, not provable.
- Follow-up: already reflected in `core/canonical.py`, `core/envelope.py`,
  `core/workspace.py`, `core/gate.py`; queue + projection land in P03.

## Alternatives considered

- Keep signing for "just authorship": rejected — reintroduces keys and a trust
  root, violating ASUR-LOCAL-01.
- Drop hashing too: rejected — integrity/lineage hashing is pure and is the
  backbone of versioning (ASUR-VERSION-01) and the firewall queue.
