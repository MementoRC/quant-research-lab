# Core comparison — design

Date: 2026-10-03. Status: approved in conversation (owner, 2026-10-03), pending written-spec review.

## Purpose

EXPLORATION ONLY. Answers: "would a more resilient (less equity-heavy) core
than the current QQQ/GLD 200-day trend rule have lost less in past shocks
without giving up too much research-period return?" It compares a fixed list
of seven pre-registered cores and selects nothing.

It changes nothing in `config/portfolio.yaml`, `config/combined.yaml`,
`config/combined_null.yaml`, `config/paper.yaml`, `config/criteria.yaml`,
`config/profile.yaml` or `config/factor.yaml`, and does not touch
`src/qrl/engine.py`, `metrics.py`, `periods.py`, `checks.py` or any existing
test. (It adds one entry to `EXAMPLE_PARAMS` in `tests/test_strategies.py`,
which AGENTS.md requires for every new strategy; adding an entry does not
weaken a test. It also updates the predecessor's new `tests/test_stress.py`
tests for the new required `bonds` class, without weakening them.)

Out of scope: actually switching the core. The core is bound into runs 4/5
through `combined_config_hash` (`combined.yaml` raw bytes + `capital_split` +
core spec), and the paper-track candidates were selected against QQQ/GLD.
Switching it would need a dated PLAN.md amendment and a new run, decided by
the owner after reading this report.

## Candidates — `config/core_candidates.yaml`

Fixed before any result is seen (header comment says so; after the first
report, changes only via a dated amendment comment). Every report records the
file's full sha256 and the trial count (7). Each is evaluated as a core-only
portfolio: `qrl.portfolio.combine_portfolio(core_weights, [], capital_split)`
with the profile's `capital_split` (core 0.80, sleeve empty, so 20% is cash).

| id | rule |
|---|---|
| A | `core_trend` risk_on QQQ, risk_off GLD, lookback 200 (the current core) |
| B | `core_trend` risk_on SPY, risk_off GLD, lookback 200 |
| C | `core_trend` risk_on SPY, risk_off IEF, lookback 200 |
| D | `core_mix` static SPY 0.6 / IEF 0.4 |
| E | `core_mix` static SPY 0.6 / IEF 0.2 / GLD 0.2 |
| F | `core_mix` risk_on {SPY 0.6, IEF 0.4}, risk_off {IEF 0.5, GLD 0.5}, signal SPY, lookback 200 |
| G | `core_mix` static SPY 0.25 / TLT 0.25 / GLD 0.25 / SHY 0.25 |

C is expressed with `core_trend`: its `risk_off` accepts any priced ticker
(only the sentinel `"CASH"` is special), so IEF needs no `core_mix`.

## New strategy family `core_mix`

`src/qrl/strategies/core_mix.py`, registered in `REGISTRY` (and so in
`EXAMPLE_PARAMS`). Params:

- `risk_on`: dict ticker -> weight (non-negative, sum <= 1; required).
- `risk_off`: dict ticker -> weight (non-negative, sum <= 1; optional). Omitted
  means a static mix with no switch.
- `signal`: ticker for the trend test; `lookback`: int. Both required when
  `risk_off` is given, and rejected when it is not.

Rule, mirroring `core_trend`: at the close of day t, `signal` close above its
simple moving average (`rolling(lookback, min_periods=lookback).mean()`) holds
the `risk_on` weights, otherwise the `risk_off` weights. Rows are NaN while the
average is not yet defined or when any ticker the rule can hold, or the
signal, has no price (`core_trend` NaNs on a missing `risk_off` price the same
way). A static mix is NaN only on days a held ticker is unpriced. Day-t weights
use data up to the close of day t. The engine rebalances to target daily
(drift ignored), so a static mix pays a small amount of rebalancing turnover;
that is accepted.

`StrategySpec.tickers` is the union of `risk_on` and `risk_off` keys, plus
`signal` when `risk_off` is given. The signal must be in `tickers` because
`scripts/stress.py`-style callers build `data[f][spec.tickers(params)]` and
pass that frame to the weights function, so a signal that is not held (e.g.
QQQ signalling a SPY mix) would otherwise be missing. The weights frame's
columns are only the tickers the rule can hold, so the signal is not an
engine column unless held. `space` is empty: the family is not searched.

## Stress: `bonds` class

In `src/qrl/stress.py`:

- `asset_class` maps `IEF`, `TLT`, `SHY`, `AGG` to `"bonds"` (GLD stays
  `"gold"`, everything else `"equity"`).
- `SHOCK_CLASSES = ("equity", "gold", "bonds")`; the loader requires all three
  in every hypothetical (unknown or missing class is still a load error).
- `frozen_loss`: a bond ticker with no price at the window's first day is
  replaced by cash, like gold, and the weight is reported under
  `proxied_share["bonds"]`.

`config/stress.yaml` gets a DATED AMENDMENT comment (2026-10-03, owner
approval) adding `bonds` to each hypothetical: `no_safe_haven` -0.15,
`stagflation` -0.20, `energy_shock_severe` -0.10, `tech_crash` +0.05. Its
sha256 changes, so the daily check will flag an existing `reports/stress.json`
as stale until `pixi run stress` is re-run; the chosen core holds no bonds, so
the chosen portfolio's own stress losses do not change.

## Measures — `scripts/core_compare.py`

Data: `qrl.data.load_ohlcv(tickers, refresh=True)`, as `scripts/stress.py`
does. Tickers: every candidate's `tickers` plus `EQUITY_PROXY` (SPY). A ticker
the loader dropped (no data) fails the run loudly.

(a) Research-period metrics, per candidate. Frames are truncated by index at
the research end (`period_bounds(criteria, "research")`) BEFORE weights are
built; warm-up rows before the research start are allowed. The weights go
through `combine_portfolio`, `qrl.engine.run_backtest` (cost from
`criteria["costs"]["bps_per_unit_turnover"]`), then the returns are cut to the
research period with `slice_period(..., "research")` and passed to
`qrl.metrics.compute_metrics`: CAGR, Sharpe, max drawdown, plus turnover per
year. A candidate whose core weights are not yet valid at the research start
is recorded as an error (not silently shortened). The validation and holdout
periods are never used in any computation (prices are downloaded in full;
every computation is cut at the research end), and `unseal_holdout=True` is
never passed.

(b) Stress cells, via `qrl.stress.run_stress` with `PortfolioDef`s, on frames
truncated at the research end:

- Only windows that do not overlap the validation period (nor holdout) are
  evaluated: with today's `stress.yaml` that is `dotcom_2000` (frozen only) and
  `gfc_2008` (replay + frozen), plus every hypothetical. `covid_2020` and
  `inflation_2022` are computed NOWHERE in this tool. A later, separate step
  may show them once the owner has picked.
- Frozen and hypothetical cells need a weight row. A switching rule (A, B, C,
  F) has a state-dependent latest row (as of the research end it would show
  whichever branch happened to be live), which would flatter or penalise it
  arbitrarily. So a switching candidate X is stressed as three portfolios:
  `X` (rule replay cells only), `X[risk_on]` and `X[risk_off]` (static branch
  mixes; frozen and hypothetical cells only). A static candidate is the single
  portfolio `X` with all modes.
- Frozen cells in `dotcom_2000` see no bond/gold ETF price at the window
  start, so those weights are proxied to cash and reported in
  `proxied_share`. The markdown stress table shows them in a "proxied to cash"
  column (per-class shares from `detail["proxied_share"]`, e.g. "bonds 40%,
  gold 20%"; blank if none), with a footnote that bonds/gold treated as cash
  before their ETFs existed understate their cushion in `dotcom_2000`.
- After loading, every candidate ticker (signal tickers included) must be
  priced on the last row at or before the research end, else the run fails
  loudly (as `scripts/stress.py` does for its core).

Breaches: a stress cell breaches when its loss exceeds the profile's
`max_drawdown` (0.35, `config/profile.yaml`); the research period breaches
when its max drawdown does. Per candidate the report gives
`breach_count` (research breach + breaching stress cells), plus the number of
unavailable cells.

## Output

- Printed table (the markdown below).
- `research/core_compare.md`: deterministic (no timestamp) so a re-run on the
  same data is diffable. The owner decides to keep it; the plan's final task
  commits the first generated version.
- `reports/core_compare.json` (gitignored): generated_at, candidates file
  sha256, trial count, stress.yaml sha256, research period, cap, capital
  split, excluded windows, and per candidate: params, research metrics,
  breach counts, every cell.

Every candidate tested appears in the output, with the candidates-file hash
and the trial count (AGENTS.md: record every variant).

## Guardrails

- Validation and holdout data never enter any computation: research frames and
  stress frames are cut at the research end before use; windows ending on/after
  the validation start are dropped before `run_stress`.
- `config/core_candidates.yaml` is pre-registered; its hash is in every report.
- The tool selects nothing and writes no config.
- The loader rejects: a missing/empty candidates list, wrong version, duplicate
  ids, an id containing `[` or other non `[A-Za-z0-9_-]` characters, an `fn`
  other than `core_trend`/`core_mix`, a `risk_off` of `"CASH"` (no priced
  branch to stress), and params the strategy rejects.

## Interfaces

- `src/qrl/strategies/core_mix.py` — `core_mix(close, risk_on, risk_off=None,
  signal=None, lookback=None)`, `core_mix_tickers(params)`.
- `src/qrl/core_compare.py` — pure functions: `load_core_candidates(path) ->
  (list[Candidate], sha256)`, `candidate_weights`, `split_windows`,
  `research_metrics`, `stress_portfolios`, `run_core_compare`,
  `render_markdown` (stress table has a "proxied to cash" column and a
  dotcom footnote). No I/O except `load_core_candidates` reading its file;
  malformed YAML and non-mapping `params` raise `ValueError`.
- `scripts/core_compare.py` — argparse CLI (`--out-json`, `--out-md`); pixi
  task `core-compare`.

## Errors

A candidate whose research run raises `ValueError` (e.g. weights not valid at
the research start) is recorded with `research: {"error": ...}` and still
appears in the table. A stress cell with missing data is `unavailable` with
the reason, never dropped (existing `qrl.stress` behaviour). A malformed
candidates file, or a ticker the loader could not fetch, fails loudly.

## Tests

- `tests/test_core_mix.py` (new): static weights, NaN until priced, switch on
  and off on a hand-built series, equality with `core_trend` for a
  one-ticker-each mix, causality, validation errors, `tickers`/columns.
  `tests/test_strategies.py`: `core_mix` entry in `EXAMPLE_PARAMS` (feeds the
  existing look-ahead test).
- `tests/test_stress.py`: `bonds` class mapping, hypothetical loss, frozen
  proxy to cash, loader requires the class, shipped config bonds values;
  existing two-class assertions updated for the third class.
- `tests/test_core_compare.py` (new): candidate loader validation; window
  split drops validation/holdout overlap; research metrics ignore later data
  and never end after the research end; unwarmed candidate rejected; no
  validation window is evaluated and no frame row after the research end
  reaches `run_stress`; every candidate recorded; branch-state portfolios;
  markdown content (incl. proxied-to-cash column); loader rejects malformed
  YAML and non-mapping params; CLI writes outputs and fails loudly on a
  missing or unpriced ticker.

## Out of scope

Changing the core, any PLAN.md amendment or new run, ranking or selecting a
winner, showing validation-window cells (a later separate step), sleeve
interaction (the sleeve is empty here), leverage, forecasting.

## Amendment 2026-10-05: benchmark rows

After the first report, two plain buy-and-hold rows for the criteria benchmark
ticker (QQQ) were added to the report: one at the core share of the capital
split (rest cash) and one at 100%. They are reference-only, research period
only, select nothing, and are not candidates: `config/core_candidates.yaml` and
the trial count (7) are unchanged.
