# ADR-0002: Stdlib-only core; media behind the `asur[generation]` optional extra

- Status: Accepted
- Date: 2026-10-07
- Deciders: local principals (project owner)
- Invariant(s) protected: ASUR-LOCAL-01

## Context

ASUR must run 100% locally and key-free. The intelligence/evaluation half of the
system (SCRIPT, VIRAL CHECK, ORCHESTRATOR, FIREWALL, core) should install and run
with **zero third-party packages** so it is trivially portable, offline, and
auditable. But the GENERATION/EDITING half genuinely needs heavy media libraries
(FFmpeg/MoviePy, ComfyUI, Wan 2.2, SDXL, Kokoro, Stable Audio, faster-whisper,
librosa, OTIO). These must not contaminate the stdlib-only half. See `AGENTS.md
§4`, `SPEC.md §8`, and SPEC-GAP G7.

## Decision

The core / SCRIPT / VIRAL CHECK / ORCHESTRATOR / FIREWALL layers import **only the
Python standard library**. This matches `pyproject.toml` (`dependencies = []`).

All media dependencies live behind the optional extra **`asur[generation]`**
(declared in `[project.optional-dependencies]`) and are **never imported by the
stdlib core**. A stdlib-only install must run SCRIPT + VIRAL CHECK + orchestration
end to end.

A boundary (import-linter) test asserts that no module under `asur/asur/core/` or
`asur/asur/script/` imports a non-stdlib or media module, and that none of them
import networking in a way that performs I/O. The check fails the build if
violated (fail closed).

## Consequences

- Positive: the intelligence half is portable, offline, dependency-free, and
  CI-testable with no GPU and no network (ASUR-LOCAL-01).
- Negative: GENERATION code must be carefully segregated; engineers cannot
  casually `import` a media helper into a core module. The boundary test makes
  this explicit.
- Follow-up: P00 adds the `[project.optional-dependencies] generation` slot and
  `tests/test_boundary.py`. Closes SPEC-GAP G7 for the core/script layers.

## Alternatives considered

- One flat dependency list: rejected — would force media installs on users who
  only want SCRIPT/VIRAL CHECK and break offline/portable guarantees.
- Separate packages/repos: rejected for now as premature; a single package with
  an optional extra is simpler and still enforces the boundary via the test.
