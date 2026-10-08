<!--
Thank you for contributing to ASUR. Please read AGENTS.md (the ASUR Constitution)
and CONTRIBUTING.md before opening this PR.
-->

## Summary

<!-- What does this change do, and why? -->

## Related issues

<!-- e.g. Closes #123 -->

## Type of change

- [ ] `feat` — new functionality
- [ ] `fix` — bug fix
- [ ] `test` — tests only
- [ ] `docs` — documentation only
- [ ] `chore` — tooling / maintenance
- [ ] `refactor` — no behavior change

## How was this tested?

<!-- Commands run and their results. -->

```
# e.g.
ruff check .
pytest -q
```

## Invariant checklist (see AGENTS.md)

- [ ] Core remains local-first and key-free; no network calls or API keys added (ASUR-LOCAL-01).
- [ ] No third-party runtime dependency added to the stdlib-only core.
- [ ] GENERATION ↔ VIRAL CHECK firewall intact; no target-name leakage (ASUR-FIREWALL-01).
- [ ] No single "percent viral" number is emitted (ASUR-HONEST-01).
- [ ] Assets carry provenance + license metadata (ASUR-PROV-01).
- [ ] Nothing is silently overwritten; writes stay versioned/append-only/checksummed (ASUR-VERSION-01).
- [ ] No removed integrations reintroduced (e.g. Sora).

## Commit hygiene

- [ ] Commits follow `<type>(pNN): <summary>` (CONTRIBUTING.md / AGENTS.md §10).
- [ ] No co-author trailers, signatures, or "Generated with" footers.
- [ ] `ruff check .` passes and `pytest -q` is green.
