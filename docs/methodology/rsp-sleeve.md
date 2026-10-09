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
2. Seed a new run (the next number after the highest in the ledger) with
   `search seed --fixed --pass-rule combined --combined-config
   config/combined_fixed.yaml --families buy_and_hold`. `--fixed` marks the
   run as a fixed-candidate run and lets its one declared family through
   `_validate_seed`, even though `buy_and_hold` is not in `SEARCHABLE_SPACES`.
   It stays out of `SEARCHABLE_SPACES` (that dict feeds `propose_batch`). The
   flag is stored so existing runs are unaffected: they read as not fixed.
3. Run `search fixed --run ID --family buy_and_hold --params '{"ticker":"RSP"}'`.
   It skips `propose_batch`, reuses `_batch_setup` (config-hash and
   data-source guards) and `_test_one_candidate`, and adds the candidate's own
   tickers (`spec.tickers(params)`, here RSP) to the `needed` price set.
   Today `_run_batch` loads only the universe, defaults, benchmarks and core,
   so RSP would be missing.
4. Guards. `batch` refuses on a fixed run; `fixed` refuses on a non-fixed run.
   `fixed` also refuses if `ledger.list_tests(run)` is non-empty: one attempt.
5. Preflight, before anything is recorded: every needed ticker must have
   prices covering the research period (2005-01-01 to 2018-12-31). If not,
   nothing is recorded and no performance is computed; fix the data and rerun.
6. If evaluation itself errors after preflight, it is recorded as a failed
   test (AGENTS.md: every attempt logged) and the run is closed. A retry needs
   a new dated amendment approved by the owner, never a silent rerun.
7. Only if it passes, `validate` once on 2019-2022. `scripts/validate.py`
   builds `needed` the same way as `_run_batch` (about :153-156), so it gets
   the same generic fix: add each validated candidate's own tickers
   (`spec.tickers(params)`) to `needed`. It is not a protected file, and
   existing runs are unaffected since their tickers are already loaded.
8. The holdout (2023 onward) stays sealed.
9. Nothing is tuned or rerun. The result is written up, pass or fail, in
   `research/rsp_sleeve.md`, with one line on the dashboard.

## Validation gates (unchanged, part of the bar)

`validate` applies its existing gates to this candidate:

- Neighbourhood check: trivially passed. `buy_and_hold` has no space, so
  `spaces.get(family, {})` is empty and there are no neighbours.
- Deflated Sharpe: the trial count is 1, so SR0 = 0 (fewer than 2 trials
  gives no multiple-testing penalty). The candidate must still reach
  DSR >= 0.95 (`config/validation.yaml`, `min_deflated_sharpe`) on the
  improvement Sharpe. This is a real pass/fail gate, the same one every prior
  run faces.

## Risk limit note

`profile.yaml`'s `max_loss_per_trade` (0.04) is a per-position weight cap on
the sleeve (`src/qrl/risk.py`). No evaluation path passes limits today.
Owner decision 2026-10-09: the cap applies per individual stock. A diversified
fund like RSP (about 500 stocks, about 0.2% each) is exempt. A dated
`profile.yaml` amendment is needed only at adoption, not for this test.

## Tests

- `combined_fixed.yaml` loads, and the run hash check works (a changed file
  makes `search batch` and `validate` refuse).
- Minimum trades: `combined_checks` is called with both configs on the same
  inputs (a sleeve with too few trades). It passes under `combined_fixed` and
  fails under `combined`.
- `seed --fixed` then `fixed` records exactly one test; a second `fixed` call
  is refused.
- `batch` refuses on a fixed run; `fixed` refuses on a non-fixed run.
- A preflight failure (a needed ticker lacks research-period prices) records
  nothing.
- `validate` loads the candidate's own tickers (RSP) into `needed`.
- Existing tests are unchanged.

## Untouched

`config/criteria.yaml`, `config/combined.yaml`, `config/combined_null.yaml`,
`config/paper.yaml`, `config/factor.yaml`, `src/qrl/engine.py`, `metrics.py`,
`periods.py`, `checks.py`, existing tests, the core and `capital_split`.

## Adoption (out of scope)

Adopting RSP would need a dated PLAN.md amendment and a sleeve entry in
`config/portfolio.yaml`. This document does not do either.
