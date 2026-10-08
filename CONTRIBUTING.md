# Contributing to ASUR

Thank you for your interest in contributing to ASUR. This document describes how to
set up a development environment, run the test suite, and submit changes that respect
the project's governing constraints.

> **Read `AGENTS.md` first.** It is the ASUR Constitution and the supreme law of this
> repository. Every contribution must respect its eight invariants. Where this guide
> and `AGENTS.md` appear to disagree, `AGENTS.md` wins.

## Table of Contents

- [Core Principles](#core-principles)
- [Development Setup](#development-setup)
- [Running Tests](#running-tests)
- [Linting and Type Checking](#linting-and-type-checking)
- [Commit Conventions](#commit-conventions)
- [Pull Requests](#pull-requests)
- [What You Must Not Do](#what-you-must-not-do)

## Core Principles

ASUR is a **local-first, key-free** AI content-creation OS. Before writing code, keep
these invariants (from `AGENTS.md`) in mind:

- **ASUR-LOCAL-01** — The core runs 100% locally with no network calls and no API keys.
  The core package depends on the Python standard library only. Heavy media dependencies
  live behind the optional `[generation]` extra.
- **ASUR-FIREWALL-01** — GENERATION and VIRAL CHECK never communicate except through
  SCRIPT projections. The firewall is enforced and greppable; it fails closed.
- **ASUR-HONEST-01** — Never emit a single "percent viral" number.
- **ASUR-HUMAN-01** — Humans own all inputs, approvals, and history. No machine commits.
- **ASUR-PROV-01**, **ASUR-GATE-01**, **ASUR-EXPLAIN-01**, **ASUR-VERSION-01** — see
  `AGENTS.md` for full definitions.

## Development Setup

ASUR targets **Python 3.10+**.

```bash
# Clone and enter the repository
git clone https://github.com/prathamshukla28/asur.git
cd asur

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # On Windows: .venv\Scripts\activate

# Install the package in editable mode (stdlib-only core)
pip install -e .

# Optional: install the media-generation extra for integration work
pip install -e ".[generation]"

# Developer tooling
pip install ruff mypy pytest
```

The core install pulls **no third-party runtime dependencies**. If `pip install -e .`
starts downloading packages, something has violated ASUR-LOCAL-01 — stop and investigate.

## Running Tests

The unit suite runs with no network access and no GPU.

```bash
# Run the unit suite (integration tests are excluded by default)
pytest -q

# Run everything including integration tests
pytest -q -m "integration or not integration"

# Run a single test file
pytest tests/path/to/test_file.py -q
```

`pyproject.toml` sets `addopts = "-m 'not integration'"`, so plain `pytest` skips
integration tests. Integration tests are marked with `@pytest.mark.integration`.

## Linting and Type Checking

```bash
# Lint
ruff check .

# Auto-fix what can be fixed safely
ruff check . --fix

# Type check
mypy asur
```

CI runs `ruff check .` as a hard gate and `mypy asur` in advisory mode. Please keep new
code type-clean regardless.

## Commit Conventions

ASUR uses a phase-scoped conventional commit style (see `AGENTS.md` §10):

```
<type>(pNN): <summary>
```

- **type** — one of `feat`, `fix`, `test`, `docs`, `chore`, `refactor`.
- **pNN** — the phase number the change belongs to (e.g. `p01`).
- **summary** — concise, imperative mood, lower case, no trailing period.

Examples:

```
feat(p02): add atomic version writer for rendered assets
fix(p01): close firewall leak in viral_check projection
docs(p01): document the eight invariants in the README
```

**Do not** add co-author trailers, signatures, "Generated with" footers, or any other
automated attribution to commit messages.

## Pull Requests

1. Fork the repository and create a topic branch from `main`.
2. Make focused changes. Keep each PR scoped to one logical concern.
3. Ensure `ruff check .` passes and `pytest -q` is green.
4. Fill out the pull request template honestly, including how you tested.
5. Confirm your change preserves every invariant in `AGENTS.md`.

All PRs run through CI (`stdlib-firewall` and `lint-type-test` jobs). Both must pass
before review.

## What You Must Not Do

Per `AGENTS.md`, contributions must never:

- Add network calls, API keys, or cloud/paid services to the core.
- Introduce third-party runtime dependencies into the stdlib-only core.
- Break the GENERATION ↔ VIRAL CHECK firewall or leak target names across it.
- Emit a single "percent viral" score.
- Reintroduce removed integrations (e.g. Sora must never appear).
- Perform machine commits on behalf of a human, or rewrite shared history.

When in doubt, open an issue and ask before writing code.
