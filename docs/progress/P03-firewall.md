# P03 — The Firewall  ✅ DONE

## What this phase is for

This is the piece that makes ASUR trustworthy: the part that **makes** the video
and the part that **judges** whether it will perform must never talk directly. If
they could, the maker would just build whatever the judge rubber-stamps. P03 builds
that wall.

## What P03 added

- **A projection function** — the single, local, key-free bridge. It computes two
  separate views:
  - The **maker's view**: the brief, hooks, and quality *floors* — but never the
    judge's pass criteria.
  - The **judge's view**: the finished-bundle fingerprints, provenance, and platform
    facts — but the quality/difficulty *targets* are stripped out by name.
- **A name-strip + grep check** — an automatic test that fails loudly if a secret
  target ever leaks into the judge's view.
- **A cross-import check** — fails the build if the maker code ever imports the judge
  code, or vice-versa.
- **A safe hand-off queue** — a tamper-evident log: seal → claim → verdict → place.
  Something only moves forward when three fingerprints agree, otherwise it's blocked.

## Safety promises kept

- Leak = blocked, automatically.
- All based on plain fingerprints (SHA-256), no keys, 100% local.

## Status

**Done.** 106 tests pass. This was the last step of Leg A — stopping here for you
before any video work begins.
