"""ASUR - a local-first, key-free AI Content Creation OS.

Phase 1 implements the SCRIPT intelligence instrument: it turns a one-line
idea into a researched, audience-aware, strategy-backed, hook-scored,
fully structured script - with every stage emitting a versioned, checksummed,
provenance-bound artifact.

Founding invariants enforced throughout (see asur/README.md):
  ASUR-LOCAL-01   100% local; identity = OS user + git config only; no network.
  ASUR-HONEST-01  never a single fake "%viral" number.
  ASUR-FIREWALL-01 GENERATION and VIRAL CHECK never talk; SCRIPT bridges.
  ASUR-GATE-01    fail closed (missing input/approval caps HOLD or BLOCK).
  ASUR-HUMAN-01   humans own inputs, approvals, history.
  ASUR-PROV-01    every artifact/asset is provenance-bound.
  ASUR-EXPLAIN-01 no black box; every decision is explainable.
  ASUR-VERSION-01 nothing is silently overwritten.
"""

__version__ = "0.1.0"
SCHEMA_VERSION = "asur.artifact/v1"
