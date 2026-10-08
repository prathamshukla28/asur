"""ASUR core - the key-free foundation every instrument depends on.

Pure, dependency-free building blocks:
  identity   - local identity (OS user + git config), no network, no keys.
  canonical  - deterministic JSON canonicalization + SHA-256 content hashing.
  envelope   - the universal artifact envelope (versioned, checksummed).
  workspace  - on-disk artifact store (no silent overwrite, supersede chain).
  gate       - fail-closed disposition gate (producer != approver).

De-keying note (from Trinity analysis): we KEEP SHA-256 for byte-integrity
and lineage, and producer != approver separation by comparing local
usernames. We DROP all signing/attestation. "self_approved" is recorded
honestly when the creator is also the approver.
"""
