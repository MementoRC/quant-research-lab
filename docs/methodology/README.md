# Methodology

These documents fix each study's rules before any results are seen. Each one
records the question, the pre-registered inputs and the pass or reporting
rules; later changes are made only as dated amendments recorded in the
document itself.

Each entry ends with the document's status keyword (Draft, Approved,
Implemented or Closed), matching its `Status:` line.

- [core-comparison.md](core-comparison.md) — exploration-only comparison of
  seven pre-registered, more resilient cores against the current core, on
  past shocks and research-period return (implemented).
- [core-reveal.md](core-reveal.md) — the single, one-time look at the
  validation-period stress windows for the owner's shortlisted cores
  (implemented).
- [stress-scenarios.md](stress-scenarios.md) — diagnostic stress scenarios
  showing how much the portfolio would lose in a shock and whether that
  breaches the max-drawdown cap (implemented).
- [fragility-screen.md](fragility-screen.md) — balance-sheet screen that flags
  listed US companies that look fragile if borrowing stays expensive
  (implemented).
- [decision-helper.md](decision-helper.md) — decision aid comparing a fixed
  set of portfolios under historical crashes, judgement-based shocks and
  inflation-indexed withdrawals (implemented).
- [longrun.md](longrun.md) — 30-year withdrawal paths built by resampling
  2005-2018 months, comparing the decision-helper portfolios on depletion
  chance and real value (implemented).
- [rsp-sleeve.md](rsp-sleeve.md) — one fixed, pre-registered test of whether a
  20% RSP (equal-weight S&P 500) sleeve beats the core alone, with no search
  (closed: research passed; validation failed; not adopted).
- [defensive-sleeve.md](defensive-sleeve.md) — decision-aid comparison of the
  core with a 20% cash, bond or RSP sleeve on drawdowns, stress losses,
  withdrawal survival and lost return (implemented).
- [true-cash-sleeve.md](true-cash-sleeve.md) — one assumption row, 80% of
  the core plus 20% cash at +1% real, showing how much SHY's near-zero
  2009-2015 yields weigh on the cash-sleeve baseline (implemented).
- [true-cash-all-cores.md](true-cash-all-cores.md) — true cash and SHY 80/20
  rows for every core A-G (implemented: owner-approved 2026-10-12; run
  2026-10-12).
- [withdrawal-edge-cases.md](withdrawal-edge-cases.md) — one withdrawal order
  and one depletion threshold for the decision helper and the long run; also
  the RSP sleeve written-spec review (implemented 2026-10-15).
- [withdrawal-rules.md](withdrawal-rules.md) — the fixed CPI-indexed withdrawal
  against four flexible rules (skip the raise after a loss, guardrails, percent
  of balance, floor and ceiling), historical and long run; compares, recommends
  nothing (implemented 2026-10-24; `pixi run withdrawal-rules`).
- [staged-entry.md](staged-entry.md) — staged entry from cash: lump sum against
  equal monthly tranches over 6, 12 and 24 months while drawing income, cores
  A-G, waiting cash in SHY or at inflation + 1% (implemented 2026-10-25;
  `pixi run staged-entry`).
- [income-explorer.md](income-explorer.md) — dashboard what-if panel that looks
  up the committed withdrawal-rules and staged-entry results for one portfolio,
  rate and choice next to its baseline; computes and recommends nothing (draft
  2026-10-26).
- [whatif-mix.md](whatif-mix.md) — local command that builds your own mix of the
  decision-report portfolios (plus true cash) and runs it through the report's
  tables, privately (implemented in PR #64; owner-approved 2026-10-17).
- [whatif-shock.md](whatif-shock.md) — local command that runs the decision-report
  portfolios (and an optional mix) with withdrawals through a multi-year bad
  stretch you define, then real history, privately (implemented in PR #65,
  2026-10-18).
- [macro-overlay.md](macro-overlay.md) — one fixed, pre-registered test of a
  slow de-risk-only macro overlay (trend, volatility, inflation) on core G
  (closed: research passed; validation and holdout failed; track closed;
  `research/overlay.md`).
- [report-wording.md](report-wording.md) — wording fixes in reports: cost,
  drawdown, true cash, start years, PLAN summary, proxied note (implemented in
  PR #60).
- [audit-remaining.md](audit-remaining.md) — closes the 2026-10-12 audit:
  deflated-Sharpe counting, paper.yaml pin, docs drift (implemented in PR #61).
- [site-safety.md](site-safety.md) — Site safety: survivorship label and holdout
  cut-off on the public dashboard (implemented in PR #59; owner-approved).
- [international-test.md](international-test.md) — final test of an accepted
  index-level rule on non-US markets, replacing the spent 2023+ holdout
  (implemented 2026-10-22; owner-approved 2026-10-21; not run).

## Former paths

Config files whose sha256 is recorded in reports (`config/fragility.yaml`,
`config/stress.yaml`, `config/core_candidates.yaml`,
`config/core_shortlist.yaml`) still cite the old paths in their header
comments. They are left unchanged so their hashes stay valid.

| Old path | New file |
|---|---|
| `docs/superpowers/specs/2026-10-03-core-compare-design.md` | `core-comparison.md` |
| `docs/superpowers/specs/2026-10-03-stress-scenarios-design.md` | `stress-scenarios.md` |
| `docs/superpowers/specs/2026-10-04-core-reveal-design.md` | `core-reveal.md` |
| `docs/superpowers/specs/2026-10-05-fragility-screen-design.md` | `fragility-screen.md` |
