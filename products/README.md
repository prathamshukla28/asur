# products/ — separate products hosted in this repo

These are **not part of ASUR** (the content-creation pipeline). They are
stand-alone local-first products that live here because they reuse a handful of
ASUR's stdlib-only core primitives (`asur.core.gate`, `asur.core.canonical`,
`asur.core.envelope`, `asur.script.evidence`) and share its constitution
(`AGENTS.md`) and CI.

| Product | Package | CLI | What it is |
|---|---|---|---|
| **Life Mentor** | `products/life_mentor/` (imported as `life_mentor`) | `life-mentor` | Local-first personal mentor: finances, health, career, lifestyle decisions — explainable, consent-gated, never an oracle. See its [README](life_mentor/README.md) and [CHARTER](life_mentor/docs/CHARTER.md). |
| **Weekly Tracker** | `products/weekly_tracker/` (imported as `weekly_tracker`) | `weekly-tracker` | ISO-week planner and weekly review (planner + git activity + Life Mentor aggregates), one Markdown file per week, local `.ics` export. See its [README](weekly_tracker/README.md). |

## Dependency direction (one-way, enforced)

```
asur  <--  life_mentor  <--  weekly_tracker
```

- `asur` never imports either product.
- `life_mentor` imports only the four ASUR core primitives listed above.
- `weekly_tracker` builds on `life_mentor` (security store, journal, ics, tracking).

All three stay stdlib-only; `tests/test_boundary.py` lints every module in all
three packages for non-stdlib/network imports.

## Tests

```bash
python3 -m pytest -q tests/lifeos            # these products only
python3 -m pytest -q --ignore=tests/lifeos   # ASUR only
```

CI runs both lanes separately (see `.github/workflows/ci.yml`), so a failure
here is visibly not an ASUR failure, and vice versa.

## Future split

If either product needs its own public life (independent versioning, releases,
contributors), the extraction path is: new repo, vendor the four ASUR core
primitives, carry history with `git filter-repo`. Until then this layout keeps
one CI, one install, and zero duplicated code.
