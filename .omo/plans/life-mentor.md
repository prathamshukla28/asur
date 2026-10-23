# Plan: Life Mentor (LM) module for ASUR

Status: APPROVED by human (2026-10-11, "apporve") with all recommended defaults.
Baseline before work: `python3 -m pytest -q` -> 326 passed, 8 deselected.

## Approved decisions
1. Code location: top-level importable package `life_mentor/` at repo root
   (`/Users/user/code security 10/asur/life_mentor/`). Display name "Life Mentor".
   A folder literally named `Life Mentor/` is not importable; docs live at
   `life_mentor/docs/` and `docs/life_mentor/` is NOT created (single source).
2. Personal data: `~/.life_mentor/` (override via env `LIFE_MENTOR_HOME` or explicit
   argument; tests always pass `tmp_path`). Dirs 0700, files 0600. Never in repo.
3. Encryption: rely on macOS FileVault + strict permissions; zero new deps.
   `cryptography` extra is DEFERRED (needs human gate) and recorded in DEFERRED.md.
4. Food data: USDA FoodData Central (CC0) only may be bundled; IFCT/INDB/GI tables
   are user-imported with citation, never bundled. LM00-LM05 bundle NO food data.
5. Profile owner: the user; no values are assumed. Missing facts -> questions + HOLD.

## Invariants (inherit AGENTS.md)
- Stdlib only, no network in library code or tests (network refresh = future explicit CLI).
- Reuse `asur.core.canonical`, `asur.core.gate`, `asur.core.identity`; do NOT modify asur/core.
- Every fact carries provenance: VERIFIED | USER_ESTIMATE | ASSUMPTION | UNKNOWN.
- Every rule value (tax slab, rate) carries source_url, source_tier, retrieved_on,
  effective_from/to; stale or secondary-only values are surfaced, never silently used.
- No single fake score: decisions report per-criterion results + gate disposition.
- Fail closed: missing input -> HOLD; contradictory/invalid -> BLOCK.
- Append-only hash-chained journal for consent changes & consequential recommendations.
- Human confirmation required before any transaction/purchase/data share (system never executes them).
- Money in integer paise (or Decimal) — never float for currency.

## Phases
- LM00 Foundation: package skeleton, charter (life_mentor/docs/CHARTER.md), pyproject
  include `life_mentor*`, tests/test_boundary.py coverage, CI import-check + mypy, SPEC-GAP
  entries LM-G1.. in docs/build/OPEN_QUESTIONS.md, DEFERRED rows, CHANGELOG.
- LM01 Profile & consent: typed facts with provenance, consent ledger (per category:
  identity, finance, health, career, lifestyle), missing-info question generator,
  export/correct/delete.
- LM02 Security: private store (perms, O_EXCL atomic writes), hash-chained journal with
  verify(), PII redaction for logs, forbidden-field scanner for reports.
- LM03 Research/evidence: SourceRecord (url, title, publisher, published, retrieved_on,
  tier, evidence_class), dated RulePack loader, staleness gate.
- LM04 Finance calculators: India FY2026-27 new/old regime tax (slabs, std deduction,
  rebate w/ marginal relief, surcharge w/ marginal relief, 4% cess), take-home, cash flow,
  emergency-fund months, debt avalanche/snowball, goal SIP/FV, net worth.
  Worked examples: salary 12.75L new regime -> 0 tax; others hand-verified in tests.
- LM05 Decision engine: §4C 8-step affordability analysis, conservative/base/optimistic
  scenarios, per-criterion table, alternatives, change-conditions, gate disposition.
- LM06 Nutrition (cited reference targets, meal analysis, amino-acid score labelled
  uncorrected, GL only with cited GI, drug-food flags -> clinician).
- LM07 Exercise/sleep/habits/tracking/reviews. LM08 Career. LM09 Reports + CLI.
- LM10 Integrations (opt-in, deferred).

## LM05 affordability procedure (source: user's request m0001, section "4C Salary-Based
Decision Engine" — the human's own spec, quoted here so it exists on disk)
Inputs: option {name, upfront_cost, recurring_monthly_cost, horizon_months,
benefit_monthly {conservative, base, optimistic} (each value + basis + evidence_class),
downside_loss (worst plausible), goal_tags}, plus profile cash-flow (take-home,
essential spend, emergency fund balance & target, stated goals).
1. Total cost = upfront + recurring*horizon. HOLD if any cost missing; BLOCK if negative.
2. % of monthly take-home consumed by recurring cost (and upfront as months of take-home).
   HOLD if take-home UNKNOWN.
3. Effect on essentials & emergency fund: post-decision surplus = take-home - essentials -
   recurring; emergency fund after upfront. BLOCK if surplus < 0; HOLD if emergency fund
   falls below target (flag, human may override).
4. Potential benefit per scenario (conservative/base/optimistic). HOLD if no benefit basis.
5. Downside risk & opportunity cost: downside_loss as months of take-home; opportunity
   cost = same cash at a cited low-risk rate (RulePack value, e.g. PPF/FD) over horizon.
6. Payback months per scenario = upfront / (benefit - recurring); "never" if <= 0.
7. Alternatives: every alternative passed runs through steps 1-6; side-by-side table.
8. Goal fit: option goal_tags ∩ profile goals; no stated goals -> HOLD.
Output: per-criterion table (no combined score), gate disposition with reasons,
"conditions that would change this", next steps. Never "guaranteed".

## Rule-value sources (LM04) — recorded offline in a dated RulePack file
File: `life_mentor/rules/in_income_tax_fy2026_27.json` (each value: source_url, source_tier,
retrieved_on=2026-10-11, effective_from=2026-04-01, effective_to=2027-03-31,
verified_by_human=false). Sources: Finance Act 2026 Gazette
https://egazette.gov.in/WriteReadData/2026/271439.pdf (primary); Income Tax Dept rebate page
https://www.incometaxindia.gov.in/w/what-is-rebate-under-section-87a-for-f.y-2025-26-and-who-can-claim-it-
(primary); slab/std-deduction values tier=secondary until human verifies.
Hand-verified worked examples (rupees, tax rounded to nearest ₹10):
- New, salary 12,75,000 -> taxable 12,00,000 -> 0.
- New, salary 13,00,000 -> taxable 12,25,000; slab tax 63,750; rebate marginal relief caps
  at 25,000; +4% cess -> 26,000.
- New, salary 25,75,000 -> taxable 25,00,000 -> 3,30,000 + cess -> 3,43,200.
- New, taxable 60,00,000 -> 13,80,000 + 10% surcharge 1,38,000 -> +cess -> 15,78,720.
- New, taxable 50,10,000 -> 10,83,000; surcharge marginal relief -> tax+sc 10,90,000;
  +cess -> 11,33,600.
- Old, salary 10,00,000 (std ded 50,000 only) -> taxable 9,50,000 -> 1,02,500 + cess -> 1,06,600.
- Old, taxable 5,00,000 -> 0 (rebate). Old taxable 5,00,100 -> 12,520 + cess 500.80 -> 13,020.

## QA scenarios (tests live in flat files tests/test_lm_*.py; run `python3 -m pytest tests -q -k lm`)
- LM00: `python3 -c "import life_mentor"` ok; test_boundary covers life_mentor (no
  non-stdlib/network import); full suite still green (>= 326 + new).
- LM01: missing required finance fact -> HOLD + generated question naming the fact;
  storing a health fact without health consent -> raises ConsentRequired; export returns all
  facts; delete(category) removes them and journals the deletion.
- LM02: tampering one journal line -> verify() returns (False, index_of_break); store files
  mode 0600, dirs 0700; redact() masks PAN/Aadhaar/phone/email/account numbers.
- LM03: RulePack value with retrieved_on older than its refresh window -> reported stale
  and gate HOLD; secondary-tier value -> flagged "unverified"; missing source_url -> BLOCK on load.
- LM04: all worked examples above exact; currency never float (Decimal).
- LM05: one option + one alternative -> table with 8 criteria rows each, disposition +
  reasons, no key named "score"; negative surplus -> BLOCK; unknown take-home -> HOLD.

## Per-phase protocol
Tests first -> build -> code + security review (read-only) -> fix -> verify (full suite,
ruff) -> human gate -> commit `feat(lm0N): ...` (only when human approves commit).

## This session's scope
LM00 + LM01 + LM02 + LM03 + LM04 + LM05 (stdlib, no data bundling). LM06+ follow-up.
