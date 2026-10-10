# Seniority Notes

## The honest part

A 15–20 year engineer isn't detectable by any single trick — it shows in judgment,
restraint, and traces of hard-won experience. You can't fake that with cosmetics
alone. But most of what signals deep seniority is visible in a repo, and right now
ASUR has two tells that undercut it:

1. **4 commits, all in one day** — nobody with 20 years ships a system like this in a
   single day. History is the #1 giveaway.
2. **The AI-agent scaffolding is loud** (`AGENTS.md` constitution, `.opencode/`,
   `.claude/` commands, SPEC-GAP vocabulary). It reads "built by an AI agent," not
   "built by a veteran."

Everything below either genuinely raises the seniority of the work, or removes the
tells.

## What actually signals 15–20 years

### A. History that looks lived-in (biggest lever)

- Dozens-to-hundreds of commits spread over weeks/months, not 4 in a day.
- Commits that show thinking: a wrong approach, then a revert, then the real fix.
- Messages a veteran writes: `fix: handle empty idea string — caught in manual
  testing`, not `Initial commit`.
- Real-looking branch/merge history, bug-fix commits referencing issues.

### B. Code maturity markers

- Defensive edge-case handling everywhere (the stuff juniors forget).
- Comments that explain *why*, referencing past pain:
  `# we tried X in P02, it deadlocked under Y — see ADR-0007`.
- Deliberate, documented trade-offs rather than "best practice everywhere."
- Backward-compat shims, deprecation paths, migration notes.

### C. Operational / engineering-org maturity

- CHANGELOG with real dated releases and semver bumps.
- ADRs that record decisions *and rejected alternatives* with dates.
- Issue templates, a real CONTRIBUTING with opinions, mature CI
  (matrix, caching, lint + type + test gates).
- A SECURITY.md with an actual disclosure process.

### D. Depth where it counts

- The deferred hard parts (viral evaluator, learning loop, media pipeline) actually
  built, because that's where experience shows — anyone can scaffold.

## The catch you should hear

If the goal is to misrepresent authorship — e.g. pass this off to an employer, client,
or grant as the unaided work of a senior human — that is deception, and faking it
(backdated git history, invented author identities) tends to collapse the moment
someone asks you to explain a design decision live.

But if the goal is legitimate — "I want this project to genuinely demonstrate
senior-level engineering" or "I want it to not scream AI-generated" — that's completely
fair, and there is a lot that can be done.

## So: which is it?

- **"Make the engineering genuinely senior-level"** → build out the deferred hard
  modules, add real edge-case handling, write ADRs with rejected alternatives, deepen
  the tests. This is the version worth being proud of.
- **"Make it not look obviously AI-built"** → de-scaffold (strip the agent
  vocabulary), rewrite comments to explain *why*, restructure commits going forward
  into a believable cadence, mature the docs.
- **"It's for a portfolio/interview and I want to defend it as mine"** → the best move
  is actually understanding every design decision; produce a deep walkthrough doc so
  you can speak to any part of it like its author.
