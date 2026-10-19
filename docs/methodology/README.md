# Methodology

These documents fix each study's rules before any results are seen. Each one
records the question, the pre-registered inputs and the pass or reporting
rules; later changes are made only as dated amendments recorded in the
document itself.

- [core-comparison.md](core-comparison.md) — exploration-only comparison of
  seven pre-registered, more resilient cores against the current core, on
  past shocks and research-period return.
- [core-reveal.md](core-reveal.md) — the single, one-time look at the
  validation-period stress windows for the owner's shortlisted cores.
- [stress-scenarios.md](stress-scenarios.md) — diagnostic stress scenarios
  showing how much the portfolio would lose in a shock and whether that
  breaches the max-drawdown cap.
- [fragility-screen.md](fragility-screen.md) — balance-sheet screen that flags
  listed US companies that look fragile if borrowing stays expensive.
- [decision-helper.md](decision-helper.md) — decision aid comparing a fixed
  set of portfolios under historical crashes, judgement-based shocks and
  inflation-indexed withdrawals.
- [longrun.md](longrun.md) — 30-year withdrawal paths built by resampling
  2005-2018 months, comparing the decision-helper portfolios on depletion
  chance and real value.
- [rsp-sleeve.md](rsp-sleeve.md) — one fixed, pre-registered test of whether a
  20% RSP (equal-weight S&P 500) sleeve beats the core alone, with no search.
- [defensive-sleeve.md](defensive-sleeve.md) — decision-aid comparison of the
  core with a 20% cash, bond or RSP sleeve on drawdowns, stress losses,
  withdrawal survival and lost return.
- [true-cash-sleeve.md](true-cash-sleeve.md) — one assumption row, 80% of
  the core plus 20% cash at +1% real, showing how much SHY's near-zero
  2009-2015 yields weigh on the cash-sleeve baseline.
- [true-cash-all-cores.md](true-cash-all-cores.md) — true cash and SHY 80/20
  rows for every core A-G (owner-approved 2026-10-12; implemented and run 2026-10-12).
- [withdrawal-edge-cases.md](withdrawal-edge-cases.md) — one withdrawal order
  and one depletion threshold for the decision helper and the long run; also
  the RSP sleeve written-spec review (spec written 2026-10-15).
- [whatif-mix.md](whatif-mix.md) — local command that builds your own mix of the
  decision-report portfolios (plus true cash) and runs it through the report's
  tables, privately (owner-approved 2026-10-17; implemented in PR #64).
- [whatif-shock.md](whatif-shock.md) — local command that runs the decision-report
  portfolios (and an optional mix) with withdrawals through a multi-year bad
  stretch you define, then real history, privately (spec written 2026-10-18,
  awaiting owner review).
- [macro-overlay.md](macro-overlay.md) — one fixed, pre-registered test of a
  slow de-risk-only macro overlay (trend, volatility, inflation) on core G.
  Research passed; validation and holdout failed; track closed
  (`research/overlay.md`).
- [report-wording.md](report-wording.md) — wording fixes in reports: cost,
  drawdown, true cash, start years, PLAN summary, proxied note (implemented in
  PR #60).
- [audit-remaining.md](audit-remaining.md) — closes the 2026-10-12 audit:
  deflated-Sharpe counting, paper.yaml pin, docs drift (implemented in PR #61).
- [code-audit.md](code-audit.md) — October 2026 code audit: research-integrity
  fixes, test gaps, duplication and QA strictness, in four PRs (draft, awaiting
  owner review).
- [site-safety.md](site-safety.md) — Site safety: survivorship label and holdout
  cut-off on the public dashboard (owner-approved; implemented).

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
