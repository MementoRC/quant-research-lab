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
   `search seed --lane B --fixed --params '{"ticker":"RSP"}' --pass-rule
   combined --combined-config config/combined_fixed.yaml --families
   buy_and_hold` (`--lane` is required; `--params` is what the stored marker
   holds). `--fixed` marks the
   run as a fixed-candidate run and lets its one declared family through
   `_validate_seed`, even though `buy_and_hold` is not in `SEARCHABLE_SPACES`.
   It stays out of `SEARCHABLE_SPACES` (that dict feeds `propose_batch`).
   Storage: the flag lives in the run's `seed_description`, next to the
   families. `_encode_seed_description` (`scripts/search.py` ~:97) today dumps
   JSON `{"description", "families"}` and `_decode_seed_description` (~:101)
   reads it back, falling back to `(raw, [])` for non-JSON text. A fixed run
   adds a `"fixed"` key holding a marker plus the declared family and its
   params (`buy_and_hold`, `{"ticker":"RSP"}`); the decoder returns that too,
   and a missing key means not fixed. No ledger schema change. Runs seeded
   before this change have no such key (or plain-text descriptions), so they
   decode as not fixed and are unaffected.
3. Run `search fixed --run ID --family buy_and_hold --params '{"ticker":"RSP"}'
   --combined-config config/combined_fixed.yaml`.
   It skips `propose_batch` and reuses `_batch_setup` (config-hash and
   data-source guards) and `_test_one_candidate`. `fixed` loads only the
   core's, the benchmarks', the defaults' and the candidate's own tickers
   (`spec.tickers(params)`, here RSP). The universe is excluded: it is only
   used by the `null_equal_weight` baseline, which `combined_fixed.yaml` does
   not have, and a preflight over the present-day universe would always fail
   (its members often lack 2005 history).
4. Guards. `batch` refuses on a fixed run; `fixed` refuses on a non-fixed run.
   `fixed` also refuses if `ledger.list_tests(run)` is non-empty: one attempt.
5. Preflight, before anything is recorded: every ticker in that same set
   (core, benchmarks, defaults, candidate; not the universe) must have
   prices covering the research period (2005-01-01 to 2018-12-31). If not,
   nothing is recorded and no performance is computed; fix the data and rerun.
6. If evaluation itself errors after preflight, it is recorded as a failed
   test (AGENTS.md: every attempt logged) and the run is closed. A retry needs
   a new dated amendment approved by the owner, never a silent rerun.
7. Only if it passes, `validate` once on 2019-2022, with `--combined-config
   config/combined_fixed.yaml`. `scripts/validate.py`
   builds `needed` (~:153-158) before any candidate is selected, from the
   universe, defaults, benchmarks and core. So the extra tickers come from the
   run's recorded tests: for each test in `ledger.list_tests(run)`, add
   `qrl.search._spec_for(family).tickers(params)` to `needed`, and skip a
   family that `_spec_for` cannot resolve (it raises `KeyError`). It is not a
   protected file, and existing runs are unaffected since their tickers are
   already loaded.
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
- `validate` loads the recorded tests' own tickers (RSP) into `needed`, and
  skips a family `_spec_for` cannot resolve.
- A pre-change `seed_description` (JSON without the fixed key, and plain text)
  decodes as not fixed.
- A fixed run's description round-trips: encode then decode returns the fixed
  marker, family and params.
- Existing tests are unchanged.

## Untouched

`config/criteria.yaml`, `config/combined.yaml`, `config/combined_null.yaml`,
`config/paper.yaml`, `config/factor.yaml`, `src/qrl/engine.py`, `metrics.py`,
`periods.py`, `checks.py`, existing tests, the core and `capital_split`.

## Adoption (out of scope)

Adopting RSP would need a dated PLAN.md amendment and a sleeve entry in
`config/portfolio.yaml`. This document does not do either.
