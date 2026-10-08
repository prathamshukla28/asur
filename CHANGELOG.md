# Changelog

All notable changes to ASUR are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
