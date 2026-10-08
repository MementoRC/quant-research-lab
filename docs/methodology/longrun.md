# Long-run withdrawals: 30-year resampled paths

Status: spec written 2026-10-07, amended 2026-10-08 (`pixi run longrun`, writes
`research/longrun.md`). Owner-approved design 2026-10-07. Extends
[decision-helper.md](decision-helper.md).

## Purpose

The decision helper's withdrawal paths run at most 14 years (2005-2018), so
none of them deplete. A retirement can last 30 years. This report adds
30-year paths built by resampling 2005-2018 months. It compares; it selects
nothing and recommends nothing.

## Data

- Only data up to 2018-12-31 (the end of the research period) is read; validation and holdout stay sealed. CPI from before 2005 may be read for the January 2005 inflation figure.
- The same 12 portfolios as the decision helper (A-G, CASH, G-EW, AG,
  G-CASH, A-CASH), built by the decision helper's existing code
  (`decision.portfolio_returns` on `decision_config.load_decision_config`
  portfolios) at 5 bps per unit turnover. Research period only, nothing
  after 2018-12-31.
- Daily returns are compounded to calendar-month returns: 168 months,
  January 2005 to December 2018.
- Monthly inflation for month m = usable CPIAUCNS on the last calendar day of
  m / usable CPIAUCNS on the last calendar day of m-1, minus 1. "Usable" is
  the decision helper's availability-lagged rule (`decision_withdraw.usable_cpi`).
  A month's portfolio returns and its inflation are always kept together.
  - Amendment 2026-10-08 (owner-approved, before any result was seen): the CPI is read on the last calendar day of each month, not the last trading day. CPI for month M is usable from the last calendar day of M+1, so reading on the last trading day gave 0% inflation in months ending on a weekend and a double month after; block resampling can split that pair. Reading on the calendar month end gives each month one clean monthly figure and uses nothing not yet published.
- Extra row "CASH +1% real (assumption)": monthly return =
  (1 + inflation_m) x 1.01^(1/12) - 1, so its real return is exactly 1% a
  year on every path. It is printed directly under CASH and labelled an
  assumption, not history. Reason: SHY yields were near zero in 2009-2015,
  so resampled CASH looks worse than cash at today's rates. This row shows
  how much that one assumption matters.

## Resampling

- Circular block bootstrap: each path is 30 blocks of 12 consecutive months
  (360 months).
- A block's start month is drawn uniformly from all 168 months. A block that
  runs past December 2018 wraps to January 2005.
- 10,000 paths, numpy `default_rng` with the seed from `config/longrun.yaml`,
  so reruns are identical.
- Paired: every portfolio (and the assumption row) uses the same block
  starts, so differences between portfolios are not luck of the draw.

## Withdrawals

- Rates: 2%, 3.3%, 4% and 5% a year of the starting value (same as
  `decision.yaml`).
- Monthly: V_t = (V_{t-1} - w_t) x (1 + r_t), starting at V_0 = 1. The
  withdrawal is taken at the start of the month, then the month's return
  applies.
- w = rate / 12 in months 1-12. Every 12 months it is raised by the path's
  own inflation over the previous 12 months.
- At or below 1e-9 (of the starting value) the path is depleted in that month and stays 0. The small tolerance keeps floating-point rounding from leaving a path at a tiny positive value when it should be empty.
- Real value at month t = V_t / cumulative inflation index of the path
  (index 1 at the start).

## Outputs

Per withdrawal rate, one row per portfolio:

- chance of depletion by year 20, 25 and 30
- median depletion year among depleted paths (year = ceil(month / 12)); "-"
  if none depleted
- chance that the real value is ever below 50% of the start (the floor comes
  from the config)
- real value at year 30: median and 5th percentile (depleted paths count as
  0)

The report header lists: seed, path count, block length, horizon, sha256 of
`longrun.yaml` and `decision.yaml`, and these limits:

- one market era (2005-2018)
- one large crash (2008)
- falling interest rates that flatter bonds
- low inflation
- near-zero cash yields in 2009-2015

Resampling recombines these months. It cannot create a 1970s-style
inflation decade. Output is in percentages only; no dollar amounts anywhere.

## Configuration

`config/longrun.yaml`, pre-registered before any result is seen:

| key | value |
|---|---|
| version | 1 |
| decision_sha256 | pinned sha256 of `decision.yaml` |
| seed | fixed integer |
| n_paths | 10000 |
| block_months | 12 |
| horizon_years | 30 |
| real_floor | 0.5 |
| withdrawal_rates | [0.02, 0.033, 0.04, 0.05] |
| cash_real_yield | 0.01 |

It changes only through a dated amendment comment. `decision.yaml` is not
edited.

## Implementation

| file | role |
|---|---|
| `config/longrun.yaml` | pre-registered inputs; sha256-hashed |
| `src/qrl/longrun.py` | pure functions: `monthly_returns(daily)`, `monthly_inflation(cpi, month_ends)`, `block_starts(seed, n_paths, n_blocks, n_months)`, `run_paths(monthly_returns, monthly_inflation, starts, rate, block_months)`, `summarize(paths, ...)` |
| `src/qrl/longrun_report.py` | renders `research/longrun.md` |
| `scripts/longrun.py` | IO and wiring only; no thresholds or logic |
| `pixi.toml` | task `longrun` |

Reuse points: the decision helper's portfolio building and CPI loading. The
run reads, and never edits, `engine.py`, `metrics.py`, `periods.py` and
`checks.py`.

## Refusals

- `longrun.yaml` cannot be loaded or is missing a key (its sha256 is recorded in every report; after the first report it changes only through a dated amendment comment)
- `decision.yaml` sha256 does not match `decision_sha256`
- any data after 2018-12-31 would be used
- a month has no usable CPI
- any return is NaN

## Tests

Written first.

- zero returns, zero inflation, 5% rate: depletes in exactly month 240 (year 20), not month 239 or 241
- pairing: all portfolios get identical block starts
- the same seed gives identical output
- CASH +1% real row: real annual return is exactly 1%
- wrap-around: a block starting at December 2018 continues with January 2005
- a depleted path stays 0
- depletion by year N counts paths depleted in month 12 x N or earlier
- each refusal above raises

## Delivery

`research/longrun.md` is committed and added to the public GitHub Pages
dashboard like the other research pages (the site build reads committed
`research/*.md`).
