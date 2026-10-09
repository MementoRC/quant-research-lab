# RSP sleeve: a fixed equal-weight S&P 500 sleeve

Status: spec written 2026-10-09, owner-approved design 2026-10-09. Not yet
run. Related: PLAN.md section 2.5 (amendments 2026-10-01 and 2026-10-02).

## Question

Does 80% core + 20% RSP beat 100% core? The sleeve is one fixed candidate:
`buy_and_hold`, ticker `RSP`. The core and the capital split do not change:
`config/portfolio.yaml`'s core (`core_trend`, QQQ/GLD, 200-day) at 80% and
`config/profile.yaml`'s `capital_split` (core 0.80, sleeve 0.20).

## Why RSP

RSP is a real equal-weight S&P 500 fund with its own price history (from
2003-05). It has no survivorship bias. The `combined_null` null does: it is
equal-weight over a present-day large-cap universe.

This is one fixed candidate and no search. There is nothing to pick the best
of, so no multiple-comparison or luck correction is needed. The attempt count
is 1.

## Pass rule

A new pre-registered file, `config/combined_fixed.yaml`. It copies
`config/combined.yaml`'s thresholds exactly, except that the sleeve
minimum-trades check is off. Buy-and-hold makes about one trade by
construction, so that check could never be met.

```yaml
version: 1
sleeve_min_trades: 0            # combined.yaml: 10. Off: buy-and-hold trades ~once.
min_sharpe_improvement: 0.05
max_drawdown: 0.35
drawdown_no_worse_than_core: true
max_cagr_shortfall: 0.01
rank_by: improvement_sharpe
```

- The baseline is the core alone at 100% of capital (no `baseline` key), the
  same as `combined.yaml`.
- Costs, periods and benchmarks come from `criteria.yaml`.
- How the check goes off: `qrl.combined.combined_checks` tests
  `sleeve_trades >= cfg["sleeve_min_trades"]`, and `load_combined_config`
  requires the key to be present. So `0` needs no code change in the rule
  logic: the check stays in the list and always passes. `combined.yaml` still
  says 10, so every other combined run is unaffected.
- The file is selected with `search seed --pass-rule combined --combined-config
  config/combined_fixed.yaml`. It has no `baseline` key, so it matches the
  `combined` rule. The hash (`load_combined_config`: the file's bytes plus the
  capital split and core) is stored at seed time. `search batch` and
  `validate` refuse if the file, `capital_split` or the core changed.

## Procedure

1. Commit this spec and `config/combined_fixed.yaml` before any result.
2. Record the single candidate in the ledger as a new run (the next run
   number after the highest in the ledger). A small new path in
   `scripts/search.py` takes a fixed candidate: no proposal, no search. It
   refuses to test a second candidate, or the same one twice.
3. Research period, 2005-01-01 to 2018-12-31, once.
4. Only if it passes, `validate` once on 2019-2022.
5. The holdout (2023 onward) stays sealed.
6. Nothing is tuned or rerun. The result is written up, pass or fail, in
   `research/rsp_sleeve.md`, with one line on the dashboard.

## Risk limit note

`profile.yaml`'s `max_loss_per_trade` (0.04) is a per-position weight cap on
the sleeve (`src/qrl/risk.py`). No evaluation path passes limits today.
Owner decision 2026-10-09: the cap applies per individual stock. A diversified
fund like RSP (about 500 stocks, about 0.2% each) is exempt. A dated
`profile.yaml` amendment is needed only at adoption, not for this test.

## Tests

- `combined_fixed.yaml` loads, and the run hash check works (a changed file
  makes `search batch` and `validate` refuse).
- The minimum-trades check always passes under `combined_fixed.yaml` and still
  fails a sleeve with too few trades under `combined.yaml`.
- The fixed candidate is recorded exactly once; a second attempt is refused.
- Existing tests are unchanged.

## Untouched

`config/criteria.yaml`, `config/combined.yaml`, `config/combined_null.yaml`,
`config/paper.yaml`, `config/factor.yaml`, `src/qrl/engine.py`, `metrics.py`,
`periods.py`, `checks.py`, existing tests, the core and `capital_split`.

## Adoption (out of scope)

Adopting RSP would need a dated PLAN.md amendment and a sleeve entry in
`config/portfolio.yaml`. This document does not do either.
