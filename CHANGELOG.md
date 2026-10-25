# Changelog

All notable changes to ASUR are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Provenance+license schema guard (`asur/generation/provenance.py`), wired into
  `produce_assets`: every produced asset must carry a complete, structurally
  valid provenance+license block or production fails closed — making ASUR-PROV-01
  real for *every* asset, not just the renderer's. Deletes a `DEFERRED.md` row.
- Structural firewall conformance (`assert_view_clean` in
  `asur/tools/projection.py`): walks the exact view a lane receives (every key
  and string value, at any depth) instead of grepping `repr()`, selecting the
  forbidden set from the view tag; the render-pipeline integration test now uses
  it (ASUR-FIREWALL-01). Deletes a `DEFERRED.md` row.
- Stdlib iCalendar (`.ics`) export, local-only, no network or accounts:
  `weekly-tracker plan ics` for the planner (WT-G8) and `life-mentor habits ics`
  for the active habit schedule (LM-G54), built on a shared RFC 5545 writer
  (`life_mentor/ics.py`). Resolves the LM-G54 row and narrows WT-G8 to network
  sync only.
- `asur insights` — the learning loop made visible: a read-only, EMPIRICAL
  aggregation of a creator's own hook memory (which directions have measured
  better, which patterns are fatiguing, the next experiment), with no aggregate
  score or "% viral" (`asur/learning/insights.py`).
- `asur ab-resolve` — resolves a hook A/B experiment from *measured* performance,
  declaring a winner only when ≥2 variants carry real results and failing closed
  otherwise (`asur/learning/ab_resolution.py`, closes the live half of SPEC-GAP G2).
- `asur explain` and `asur verify-repro` now cover the full pipeline lineage
  (SCRIPT through LEARNING for explain; SCRIPT + the deterministic
  GENERATION/EDITING planning stages for verify-repro, with non-deterministic
  stages honestly skipped).
- `asur explain` — a read-only decision trail over the SCRIPT workspace. Walks
  the versioned chain (idea → research → audience → strategy → hooks → script →
  qa_report) and surfaces, per stage, its provenance (version, id, checksum,
  lineage) and the reason it recorded. Reads only what the stages wrote and only
  SCRIPT-side artifacts, so it never invents an explanation and cannot leak
  across the firewall (ASUR-EXPLAIN-01, ASUR-FIREWALL-01). New module
  `asur/tools/explain.py`; stdlib-only.
- `asur verify-repro` — rebuilds each stored SCRIPT stage from its on-disk
  upstream artifacts and confirms byte-identical checksums, turning the
  "same inputs → same checksums" claim into a checkable guarantee. A mismatch
  (non-determinism or a tampered artifact) fails closed (ASUR-VERSION-01,
  ASUR-HONEST-01, ASUR-GATE-01). New module `asur/tools/verify_repro.py`;
  stdlib-only, never writes a new artifact.
- Stronger closed-loop proof: a test that a published hook, once folded into
  SCRIPT memory with its measured result, demonstrably shifts the next run's
  evaluation of that same hook (fatigue rises, originality drops to derivative)
  — evidence that LEARNING actually learns, not just that the hook is stored.
- Project governance and community files: `LICENSE` (MIT), `CONTRIBUTING.md`,
  `CODE_OF_CONDUCT.md`, `SECURITY.md`, and this changelog.
- GitHub issue and pull request templates.

## [0.1.0] - 2026-10-09

Phase 1 initial public release.

### Added
- Local-first, key-free content-creation core with a stdlib-only runtime
  (invariant ASUR-LOCAL-01).
- Core pipeline: SCRIPT → GENERATION → EDITING → VIRAL CHECK → PUBLISH →
  PERFORMANCE → LEARNING.
- GENERATION ↔ VIRAL CHECK firewall with greppable, fail-closed enforcement
  (invariant ASUR-FIREWALL-01).
- Honest viral assessment that never emits a single "percent viral" number
  (invariant ASUR-HONEST-01).
- Provenance and license metadata on every asset (invariant ASUR-PROV-01).
- Versioned, append-only, checksummed artifact storage with atomic writes
  (invariant ASUR-VERSION-01).
- Optional `[generation]` extra for media backends (MoviePy/FFmpeg, with
  additional ML adapters behind clearly marked stubs).
- `asur` command-line entry point (`asur.cli:main`).
- Unit test suite (221 passing, 1 skipped) plus integration tests, runnable
  without network access or a GPU.
- Continuous integration with a stdlib/firewall guard job and a
  lint/type/test job.

[Unreleased]: https://github.com/prathamshukla28/asur/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/prathamshukla28/asur/releases/tag/v0.1.0
