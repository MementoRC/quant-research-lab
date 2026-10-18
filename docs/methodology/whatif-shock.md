# What-if shock: your own bad stretch, then real history

Status: spec written 2026-10-18; design approved by the owner 2026-10-17/18
(decisions listed at the end). Awaiting owner review of this written spec.
Related: [decision-helper.md](decision-helper.md), [whatif-mix.md](whatif-mix.md).
This is part 2 of 2: the owner's own shock. Part 1 (your own mix) is
implemented; this spec reuses its `parse_mix`, `parse_rate`, `mix_portfolio`,
`mix_cash_row` and `merge_rate` (`whatif.py:45`, `:66`, `:101`, `:124`, `:159`).

Rule for the whole spec: **no new maths and no locked file changes**
(`config/criteria.yaml`, `combined.yaml`, `combined_null.yaml`, `paper.yaml`,
`factor.yaml`, `src/qrl/engine.py`, `metrics.py`, `periods.py`, `checks.py`).
`config/decision.yaml` is read, never edited. The only new calculation is the
made-up stretch (fixed weights times yearly numbers); everything after it is
the report's own code.

## Question

How do the decision report's portfolios (and an optional mix of them), with
withdrawals, hold up through a bad stretch of several years that you define,
followed by real history?

## Input

```
pixi run whatif-shock --shock <file> [--mix "..."] [--rate R]
```

The pixi task `whatif-shock = "python scripts/whatif_shock.py"` is added to
`pixi.toml` beside `whatif` (`pixi.toml:25`).

**Shock file** (YAML, read-only; the script never writes it):

```yaml
name: stagflation-5y          # letters, digits, - or _
years:                        # 1 to 10 entries, in order
  - {stocks: -0.30, gold: 0.20, long_bonds: -0.15, short_bonds: 0.01, inflation: 0.09}
  - {stocks: -0.10, gold: 0.10, long_bonds: -0.10, short_bonds: 0.02, inflation: 0.08}
```

Rules, each a refusal (`load_shock` raises ValueError):

- The file is a mapping with exactly the keys `name` and `years`. Unknown or
  missing keys are refused. Invalid YAML is refused.
- `name` matches `[A-Za-z0-9_-]+` (the loader's own `_ID`,
  `decision_config.py:29`).
- `years` is a list of 1 to 10 entries. Each entry is a mapping with exactly
  `stocks`, `gold`, `long_bonds`, `short_bonds`, `inflation`. Unknown or missing
  keys are refused.
- Every value is a finite number (a boolean or a string is refused).
- Each return (`stocks`, `gold`, `long_bonds`, `short_bonds`) is above -1 and at
  most 2 (+200%).
- `inflation` is in [-0.10, 0.30].

`--mix` and `--rate` follow part 1's rules, by calling `parse_mix` and
`parse_rate` (`whatif.py:45`, `:66`): `--mix` is optional here (without it
only the report's portfolios run); names are those of `valid_names(cfg)`
(`whatif.py:154`); `--rate` is in (0, 0.10] and is added to the report's rates
(`decision.yaml:98`) by `merge_rate`.

## The fund map

Each held fund takes the yearly return of one group (`FUND_GROUP`):

| Fund | Group |
|---|---|
| SPY, QQQ, RSP | `stocks` |
| GLD | `gold` |
| TLT | `long_bonds` |
| SHY | `short_bonds` |
| IEF | midpoint of the `long_bonds` and `short_bonds` returns of that year (their arithmetic mean) |

These are all seven tickers the report's portfolios hold: A-G are SPY, QQQ,
GLD, IEF, TLT, SHY (`core_candidates.yaml:11-24`), and the statics add RSP
(`decision.yaml:19-25`). A held ticker not in the map is refused (this keeps
the tool honest if a fund is added to the config later). Signal-only tickers
need no group: the stretch uses fixed weights, not signals.

**Flagged caveat:** QQQ is treated like SPY, so core A (QQQ risk-on) looks less
exposed than it is to a tech-led fall. IEF at the midpoint is a rough duration
guess, not data.

## The stretch

For real start year Y (each of `start_years`, `decision.yaml:101`) and a
shock of N years, the made-up stretch covers calendar years Y-N to Y-1. It
comes before the real history that starts in Y, so each start year has its own
stretch dates (and its own CPI splice, below).

- **Days.** Weekdays (Monday to Friday, holidays included) from 2 January of
  Y-N to 31 December of Y-1. 1 January is skipped so the first day matches a
  real path's first trading day, which is never 1 January.
- **Daily returns.** A group's yearly return r is spread evenly and
  geometrically over that calendar year's n days: each day earns
  (1 + r)^(1/n) - 1. A year compounds to exactly 1 + r. This is the
  convention of `cash_leg_returns` (`true_cash.py:32`, month by month there,
  year by year here).
- **Portfolios.** Each state holds the fixed weights of `portfolio_states`
  (`decision_config.py:99`), rebalanced daily, with no costs. The portfolio's
  daily return is the weighted sum of its funds' daily returns. These are the
  fixed weights of the scenario tables (`scenario_return`, `decision.py:60`).
  Because of the daily rebalancing, a year does not compound to the weighted
  sum of the yearly returns (it would with a yearly rebalance); the header says
  so.
- **Switching portfolios** (A, B, C, F and every blend or mix containing one)
  run once per state. States differ only in the stretch: after it, the real part
  is the live rule and is the same for both. The worse state is headlined, and
  both are shown.
- **Which is "worse".** Per row and rate, the state with the lower real ending
  value of the first start year's path (the report's headline withdrawal
  column, `decision_report.py:447`). A tie goes to the state with the greater
  name, the tie rule of `worst_state` (`decision.py:70-74`, which takes the
  `max` of `(loss, name)`). The headlined state supplies every column of that
  row at that rate; the other state's headline value is shown beside it.
- **TCASH rows.** Every `cash_assumptions` row (`decision.yaml:56-70`) plus
  `MIX-TCASH`: in the stretch, `(1 - share) x base state + share x cash`, daily
  (the same `mix_returns` rule, `true_cash.py:79`), with the cash leg earning
  the `short_bonds` daily return. After the stretch the cash leg earns CPI plus
  the real yield, as in the report (`cash_leg_returns`).

## After the stretch

From the real start day of Y, the report's own daily returns, unchanged:
`portfolio_returns` (`decision.py:191`: the live rule, with costs) for
portfolios, and `all_assumption_returns` (`decision.py:263`) for the TCASH rows,
on the same prices cut at `data_end` (`decision.py:32`). The stretch's
series and the real series are concatenated; the stretch ends before the real
start, so the dates are increasing.

The join charges no extra cost. The real series carries the cost it always
has: `portfolio_returns` buys the portfolio fresh on the start day, and the
engine charges that purchase (5 bps of turnover, `criteria.yaml:22`,
`engine.py:66-67`, `:84-85`) and has no overnight gap on that day. This is the
report's own day one and is kept, not removed. The withdrawal level carries
over: it is one path.

## CPI and withdrawals

Withdrawals use `monthly_withdrawals`, `withdrawal_path` and `path_metrics`
unchanged (`decision_withdraw.py:43`, `:65`, `:118`) on the spliced dates and
spliced CPI. Withdrawals start at the stretch start at rate/12 of the starting
value and step up each January by the year-over-year change of the CPI usable
on 1 January (`decision_withdraw.py:43-56`). During the stretch that is the
shock's inflation.

**Dating.** The real series is dated by availability: FRED's value for month M
is dated the 1st of M and `month_ends` 2 moves it to the last day of M+1
(`config/macro.yaml:57-62`, `macro.py:81-82`). `usable_cpi` takes the latest
value dated on or before the day, and refuses one older than 45 days
(`decision_withdraw.py:17`, `:21-27`). So the CPI usable on 1 January Y is the
value of October Y-1, dated 30 November.

**Synthetic series (`stretch_cpi`).** One value dated the last day of each month
M+1, in the same way as the real series:

- Base: level 100 for October Y-N-1, dated 30 November Y-N-1.
- Then 12 values per shock year k: month by month, each multiplies the level by
  (1 + inflation_k)^(1/12). Year k's 12 values are the observations for
  November of the year before to October of the stretch year, dated 31 December
  to 30 November. That is exactly the window between "usable on 1 January" of
  that year and of the next, so the CPI usable on 1 January of year k+1 over the
  CPI usable on 1 January of year k equals 1 + inflation_k exactly, and the
  January step-up is the shock's inflation.
- The last value, the October Y-1 observation dated 30 November Y-1, is the
  stretch's end level.

**Splice (`shocked_path`).** The real series (cut at `data_end`, as
`withdrawal_rows` does, `decision.py:339-343`) is multiplied by one factor
f = (stretch end level) / (real value usable on 1 January Y), so its value
usable on 1 January Y equals the end level, with no jump. The spliced series is
the synthetic values (dated up to 30 November Y-1) followed by the real values
dated after 30 November Y-1, times f. Only ratios of the real series are ever
used, so f does not change anything after the join: from January Y+1 the
step-ups are the real ones. In January Y the step-up is the last shock
year's inflation, and the real part's deflator is the real one. The TCASH rows'
cash legs use the unscaled real CPI (`cash_leg_returns` uses ratios only).

## Rows and columns

Rows: every portfolio in `config/decision.yaml` (27), every `cash_assumptions`
row (7), plus `MIX` and `MIX-TCASH` when `--mix` is given. `MIX` and
`MIX-TCASH` are built on the full config with `mix_portfolio` and
`mix_cash_row` (`whatif.py:101`, `:124`), not with `mix_config` (which keeps only
A and CASH). With no non-cash part, the base is `CASH`, as in part 1.

Columns, per rate, are the report's withdrawal columns
(`decision_report.py:447-461`): real ending value (first start year), lowest
value, max drawdown, longest below a prior peak, depleted, worst start year
(real ending value to `data_end`), and the equal-horizon worst start year. The
report's "below peak at end" column is left out. Each cell shows the shocked
figure, with the same figure without the shock beside it.

**No-shock figures.** They come from the report's own `withdrawal_rows`
(`decision.py:331`), called on the decision config extended with `MIX`,
`MIX-TCASH` and the merged rates (`dataclasses.replace`). The report's rows
only cover `decision.yaml`'s rates and portfolios, so this call is the only
way to have the no-shock figure for `MIX` and for `--rate`; for the rest it
gives the report's published numbers exactly (a test checks it).

**Start years and paths.** A shocked path for start year Y begins on 2 January
of Y-N, so it is N years longer than the report's. The shocked path is keyed by
Y-N when `monthly_withdrawals` is called (the start year there is the first
withdrawal year). The table shows Y, with the horizon in years including the
stretch.

**Equal horizon.** The report's rule is kept: the horizon H is the last path's
end year minus the last start year plus one, and every path is cut to its first
H calendar years (`_withdrawal_rows_for`, `decision.py:285-287`, `_first_years`
`:323`). With keys Y-N, H becomes H0 + N (H0 = 5, the report's, for start year
2014 to 2018), and a path starting in Y-N is cut at the end of the year Y+H0-1.
So every path is compared on the N stretch years plus H0 real years from its own
start year.

**Why the report's helper is not called.** `_withdrawal_rows_for`
(`decision.py:275`) takes one CPI for all start years. Each start year here has
its own splice, so `shock.py` repeats its short per-year step and the
worst-start and equal-horizon choices (smallest real value, ties to the lowest
year, as `decision.py:303-304`). It uses the public alias `first_years` of
`_first_years`, added to `decision.py` the same way part 1 added aliases
(`decision_config.py:376-380`): the private name and its behaviour stay. A
parity test (below) feeds this step the unshocked paths and real CPI and
requires the report's numbers back.

## Output

`ROOT/reports/whatif-shock-<name>.md`, written with `report_path(REPORTS,
"shock-<name>")` (`whatif_report.py:43`), which resolves the path and refuses
anything outside `ROOT/reports`. The name pattern cannot traverse. An existing
file is overwritten. `reports/` is gitignored (`.gitignore:23`), so the file is
private. Nothing is written under `research/` or `site/`.

The header prints:

- the shock table (every year's five numbers) and N;
- that the shock came from a file, not from `decision.yaml`, and the mix if given
  (as part 1's header);
- data end, the `decision.yaml`, `core_candidates.yaml` and `stress.yaml`
  sha256 (as `render_whatif`, `whatif_report.py:77-100`);
- the assumptions: QQQ treated as SPY; IEF at the midpoint of long and short
  bonds; fixed weights, rebalanced daily, no costs in the stretch; TCASH earns
  `short_bonds` in the stretch and CPI plus 1% after; the stretch dates are
  made up and come before each real start year; the stretch's CPI is built from
  your inflation and the real CPI is rescaled to join it; the first real day
  pays the report's purchase cost.

Then, per rate, a table with one row per portfolio (the headlined state shown
as `A (risk_off)`, as `decision_report.py:494`) and, for switching rows, a short
second table with both states' headline value. The report's own caveats about
costs, CASH being SHY and daily rebalancing are repeated.

A short terminal summary is printed: the shock name and N, the output path, and
for `MIX`, `MIX-TCASH`, A and CASH the first start year's real ending value,
shocked and not shocked, at every rate. It does not print the whole report.

## Data and sealing

- The same `data_end` (2018-12-31) and the same functions. Prices and CPI are
  cut at it exactly as `withdrawal_rows` does (`decision.py:339-343`) before
  anything is computed. The stretch dates are before every start year, so they
  are not data.
- Never unseals: no `slice_period(..., "holdout", unseal_holdout=True)`.
- `config/decision.yaml` and the shock file are read-only. The decision.yaml
  sha256 is pinned by `longrun.yaml` (`config/longrun.yaml:16`) and stays
  unchanged.
- Prices and CPI are loaded as `scripts/whatif.py:52-65` does (`refresh=False`,
  the shared cache), for the tickers of all portfolios plus `EQUITY_PROXY`.

## Refusals

Each is printed as `refused: <reason>` with exit code 1, as
`scripts/whatif.py:68-70`. Nothing is written.

- every shock-file refusal above, and a shock file that is missing or unreadable
- `--shock` missing
- a held ticker not in the fund map
- every `--mix` and `--rate` refusal of part 1
- `cash_assumptions` rows with different real yields (`whatif.py:115-121`)
- a real CPI value not usable on 1 January Y (`usable_cpi`, "missing CPI")
- every refusal the report already makes: a held fund unpriced at a start date,
  NaN weights, missing CPI (decision-helper.md "Refusals")

## Tests

New files `tests/test_shock.py` and `tests/test_whatif_shock.py`, using the fake
price and macro helpers of `tests/test_decision_cli.py` (`_fake_ohlcv` `:121`,
`_fake_macro` `:132`). Existing tests are unchanged.

- `load_shock`: each refusal above, and one valid load.
- The stretch compounds exactly to each fund's yearly input, per fund and year.
- IEF's yearly return is the midpoint of long and short bonds.
- The synthetic CPI: usable on 1 January of year k+1 over usable on 1 January of
  year k equals 1 + inflation_k; after the splice there is no jump (the value
  usable on 1 January Y equals the end level, and no step is added at the join).
- A hand-checked CASH path through a one-year stretch, in closed form (monthly
  withdrawals and the geometric daily return).
- After the join, the returns equal `portfolio_returns` for that start year
  exactly (and the TCASH rows' report returns).
- Switching: two states with the worse headlined by the rule above (a hand case
  with a known worse state, and a tie); static: one state.
- TCASH follows `short_bonds` in the stretch and CPI plus the real yield after.
- The no-shock columns equal the report's withdrawal rows exactly (the
  parity test above, also on `MIX`).
- Equal horizon: H = H0 + N and the cut dates, on a small case.
- Sealing: prices after 2018-12-31 altered leave the output unchanged.
- `config/decision.yaml` and the shock file bytes are unchanged after a run.
- Output only under `ROOT/reports/` (the resolved path is asserted).
- `--mix` adds `MIX` (and `MIX-TCASH`) rows; with TCASH=1 only `MIX-TCASH`.
- The pixi task `whatif-shock` exists (as `test_decision_pixi_task`,
  `tests/test_decision_cli.py:106`).
- Mutation check, done by hand before the work is called complete: each of a
  wrong group map (for example IEF as `long_bonds`), no CPI rescale, and the
  wrong state headlined must turn at least one test red.

Implementation step: regenerate `research/decision.md` in place and check
`git diff --exit-code research/decision.md`. Any diff stops the work; restore
the file with `git checkout research/decision.md` and report.

## Code

- `src/qrl/shock.py`: `load_shock`, `FUND_GROUP`, `stretch_returns`,
  `stretch_cpi`, `shocked_path`. Pure functions.
- `src/qrl/shock_report.py`: the markdown and the terminal summary. A pure
  renderer, deterministic, no timestamp.
- `scripts/whatif_shock.py`: IO and wiring only, as `scripts/whatif.py`.
- `pixi.toml`: the task `whatif-shock`.
- `src/qrl/decision.py`: one public alias, `first_years = _first_years`.

## Untouched

- The locked files named in AGENTS.md.
- `config/decision.yaml` and `config/longrun.yaml`.
- `research/decision.md` (byte-identical) and the site.
- Existing tests, and the private names in `decision.py`.

## Out of scope

- A one-time drop at the start (a shock is a stretch of years).
- The live rule inside the stretch (fixed state weights only).
- Long-run resampling.
- A dashboard panel.
- Saved shock presets.

## Owner decisions (2026-10-17/18)

- The shock is a stretch over time, not a one-off drop.
- The numbers are yearly, per group (stocks, gold, long bonds, short bonds,
  inflation).
- Fixed state weights in the stretch; the worse state is headlined.
- History resumes from each start year.
- True cash follows short bonds during the stretch.
- A simple fund map, with the QQQ caveat.
- All the report's portfolios, plus an optional mix.
- Output is private.
