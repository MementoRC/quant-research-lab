# Staged entry: all at once or in monthly tranches, while drawing income

Status: Spec written 2026-10-23, owner-approved design 2026-10-23. Not yet implemented.
Extends [decision-helper.md](decision-helper.md), [longrun.md](longrun.md) and
[true-cash-all-cores.md](true-cash-all-cores.md). It ships after
[withdrawal-rules.md](withdrawal-rules.md) for review load, not because of any
code dependency.

## Question

The owner holds cash and will invest it while also withdrawing income. Is it
better to invest everything at once (lump sum), or to move the cash in equal
monthly tranches over 6, 12 or 24 months? Does the wait help or hurt, and does
it limit the damage if the market falls right after the start?

## Not a test

Comparison only. No pass/fail rule, no trials added to any search run, nothing
selected or recommended. Research period (2005-2018) only: data are cut at
2018-12-31; validation (2019-2022) and holdout (2023 on) stay sealed. The
"inflation + 1% real" cash row is a labelled assumption, as in the true-cash
reports.

## Design

- Portfolios: cores A-G. CASH is excluded: staging into cash is a lump sum.
- Staging periods: 0 (lump sum), 6, 12 and 24 months. A period of N months
  means N equal tranches (1/N of the starting value each), the first on the
  start day and then on the first trading day of each following month.
- Waiting cash earns, in two variants shown side by side:
  - SHY: actual SHY prices (the CASH static in `decision.yaml`).
  - inflation + 1% real: the cash leg of the true-cash rows, each month's
    inflation plus the `real_yield` in `decision.yaml`'s `cash_assumptions`
    (`true_cash.cash_leg_returns`, strict CPI check).
  The lump sum (period 0) never holds cash, so it is the same in both
  variants.
- Withdrawals: the fixed CPI-indexed rule only, at all four rates in
  `decision.yaml`. Each month's withdrawal is taken from waiting cash first.
  Once the cash is 0, withdrawals come from the invested part, proportionally
  across the tranches already bought, at no extra cost. Cash at or below
  `DEPLETED` (1e-9) counts as 0.
- Raises. Historical: the monthly amount is raised on each 12-month
  anniversary of the start month, by the CPI usable on the anniversary's first
  trading day over the CPI usable on the previous anniversary's first trading
  day (the start date's for the first raise). For January start months this is
  identical to `monthly_withdrawals(rate, start_year, ...)`: the CPI usable on
  1 January equals the CPI usable on the first trading day of January, because
  of the availability lag (month M is usable from the last day of month M+1,
  so December's CPI is not usable before 31 January). Long run: raised every
  12 months by the path's inflation over the previous 12 months, as `run_paths`.
- Tranche size is fixed at starting value / N. If the cash holds less than a
  tranche, all remaining cash is invested and later tranches are zero. The last
  tranche invests all remaining cash, including what it earned.
- Order on a day that has a withdrawal and a tranche: withdraw, then move the
  tranche, then apply the day's returns.
- Flexible rules together with staging are deferred. They would multiply the
  table size by five, and the question is the entry, not the rule.

## Configuration

New `config/staged_entry.yaml`, pre-registered with this spec and fixed before
any result is seen. Every report records its sha256. After the first report,
change it only by a dated amendment comment.

```yaml
version: 1
decision_sha256: "<sha256 of config/decision.yaml>"
longrun_sha256: "<sha256 of config/longrun.yaml>"
periods_months: [0, 6, 12, 24]
cash_variants: [shy, real_plus_1]
portfolios: [A, B, C, D, E, F, G]
```

Loader raises ValueError on: an unreadable file, an unknown or missing key, a
version other than 1, periods that are not a list of distinct non-negative
integers that starts with 0, an unknown cash variant, a portfolio id not in
`decision.yaml` or equal to a static (CASH), an empty or duplicated list, and
either hash that does not match the current file. `real_plus_1` needs a
`cash_assumptions` row in `decision.yaml`, and its `real_yield` must equal
`longrun.yaml`'s `cash_real_yield` (existing `check_cash_assumption`).

Read from existing files, never copied: rates and the cash yield from
`decision.yaml`; seed, n_paths (10,000), block_months (12) and horizon_years
(30) from `longrun.yaml`; 5 bps from `criteria.yaml`. `decision.yaml` is not
edited, so no pin is re-set.

## Computation

New `src/qrl/decision_staged.py`.

- Tranche returns, historical. Each tranche is a fresh purchase of the core on
  its own date: a fresh `decision.portfolio_returns` run started on that date,
  unchanged, with the engine's 5 bps entry cost inside it. Period 0 is then
  the existing lump-sum path. Returns are cached per core and date.
- Tranche cost, long run. No tranche cost is charged (`run_paths` charges no
  entry cost either), so period 0 equals `run_paths` exactly. This biases the
  result in staging's favour by at most 5 bps of starting value in total,
  which is negligible.
- Cash leg. SHY variant: the daily SHY return. Real + 1% variant:
  `true_cash.cash_leg_returns` over the same days. Cash is held between
  tranches and earns that leg daily.
- Value path. Daily state: cash balance and one value per bought tranche.
  `decision_staged.py` has its own path runner (cash leg and tranche state,
  cash-first withdrawals, tranche schedule). The total value is cash plus
  tranches. Depletion uses `DEPLETED` (1e-9 of the starting value) on the
  total, as in withdrawal-edge-cases.md.
- Historical starts: the first trading day of every month from 2005-01 to
  2014-12 (120 starts), each ending 2018-12-31. Fixed horizon for the primary
  measure: the value on the last trading day of the 48th month counting the
  start month as the first (start 2005-01 gives 2008-12-31, ..., start 2014-12
  gives 2018-11-30), deflated by the CPI usable on that day relative to the CPI
  usable on the start date. Value at the data end (2018-12-31), deflated the
  same way, is a secondary measure (paths of different length).
- Long run: the same resampled paths as longrun.md (same seed, `block_starts`,
  `month_indices`, 10,000 paths, 12-month blocks), with staging applied at the
  path start in monthly steps. Monthly cash: SHY from the CASH row's monthly
  returns; real + 1% from `longrun.cash_assumption_returns` (which keeps the
  long run's 45-day CPI tolerance, as in the existing CASH +1% real row).
  Tranches are bought at the start of each month; each tranche's monthly
  return is the core's monthly return, with 5 bps charged on the amount
  moved only in the historical view (see Tranche cost, long run).

## Measures

Historical, per portfolio x period x cash variant x rate (periods 6, 12, 24
against lump sum):

- Share of the 120 starts where staging ended above lump sum at 4 years, in
  real ending value.
- Median, best and worst gap in real ending value at 4 years, in percentage
  points of starting value (staged minus lump sum).
- Max drawdown of the total value path (starting value counts as a peak):
  the worst staged value and the worst lump-sum value across the 120 starts,
  and the worst per-start difference (staged minus lump sum).
- Worst start month for each (lowest real value at 4 years).
- Secondary: the same gaps at the data end.

Long run, per portfolio x period x cash variant x rate:

- Share of paths depleted by year 30.
- Median real ending value at year 30.
- Median real value at year 5.

## Report layout

`research/staged_entry.md`: a historical section and a long-run section; per
rate, a table with a row per portfolio x period, one column group per cash
variant. Lump sum first, then 6, 12, 24. Portfolios in A-G order. Nothing is
sorted by result. Row counts are computed, not hard-coded.

## Header and notes

Header, in the format `tests/test_docs_freshness.py` checks:

- `- staged_entry.yaml sha256: \`hex\``
- `- decision.yaml sha256: \`hex\``
- `- longrun.yaml sha256: \`hex\``

Plus data end, the 120 historical starts, the 4-year horizon, the long-run
seed, path count, block length and horizon, and the cost. Notes state: a
comparison, nothing recommended; the 120 starts overlap heavily, so they are
not 120 independent tests; the real + 1% cash is an assumption, and SHY's
2009-2015 yields were near zero, so SHY understates today's rates; each
historical tranche pays 5 bps (none in the long run, at most 5 bps in
staging's favour); flexible rules with staging are deferred; and the
historical period had a long rising market, which favours the lump sum.

## Outputs

- `src/qrl/decision_staged.py`, `src/qrl/staged_entry_report.py` (renders; no
  IO) and `scripts/staged_entry.py` (IO only).
- pixi task `staged-entry`.
- `research/staged_entry.md`, added to `regen.SPECS`.

## Tests

New `tests/test_decision_staged.py`, offline, synthetic prices.

- Hand-computed staging: tranche dates and sizes; cash earning daily between
  tranches under each variant; withdrawals taken from cash first and from
  the invested part only after the cash is gone; the withdraw-then-tranche
  order; the 5 bps on each tranche, in the historical view only.
- Period 0 equals the existing lump-sum path (`withdrawal_path` with
  `portfolio_returns`, historical, January start months only; `run_paths`,
  long run) exactly, in both cash variants.
- Depletion with staged cash.
- Withdrawals exhaust the cash before the last tranche: all remaining cash is
  invested, later tranches are zero, and withdrawals then come from the
  invested part.
- Sealing: changing prices after 2018-12-31 does not change the report.
- Config refusals: each ValueError case above and both hash mismatches.
- Regen and freshness: the report is in `regen.SPECS`; hash lines match.

## Rejected alternatives

- Proportional withdrawals: they would sell the invested part while the
  same month buys it.
- January-only starts: 10 points are too few for a timing question; all 120
  months are used.
- No-withdrawal comparison: it ignores the owner's income need.
- SHY-only cash: it understates today's rates, so the second variant is
  shown beside it.
- Flexible rules x staging now: five times the table size; deferred.

## Not changed

AGENTS.md-protected files (`criteria.yaml`, `combined.yaml`,
`combined_null.yaml`, `paper.yaml`, `factor.yaml`, `engine.py`, `metrics.py`,
`periods.py`, `checks.py`), `decision.yaml`, `longrun.yaml`, `true_cash.py`,
`decision_withdraw.py`, `longrun.py`, `profile.yaml`, `portfolio.yaml`, every
existing test and report number. Existing reports and their generators are
not changed. No search run, ledger or trial count is
touched.
