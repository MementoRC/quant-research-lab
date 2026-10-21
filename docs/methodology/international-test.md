# International final test (approved 2026-10-21)

Status: Approved by the owner on 2026-10-21 (gold source amended the same
day, before any run). Not implemented. No market in any set has been run.
Files named below without backticks (config/international.yaml,
src/qrl/international.py, scripts/international.py) do not exist yet.

## Purpose

The 2023+ holdout is spent: the macro overlay used its one unseal on
2026-10-18 (`macro-overlay.md`). Its results are committed and published, so
2023+ US data is no longer unseen. A future accepted rule needs a final test on
data nobody has looked at.

This test runs an accepted rule, unchanged, once on non-US stock markets it was
never tuned on. It replaces the holdout as the final test in milestone 2.6. The
paper track (forward from 2026-10-02) stays as supporting evidence. A forced
second unseal of 2023+ US data (`qrl.holdout.unseal(..., force=True)`) is a
labeled last resort only.

## Scope

Covered: index- and ETF-level rules with exactly one timed equity leg (core
variants such as a trend switch, overlays, ETF sleeves of that shape).

Not covered: single-stock sleeves. A point-in-time foreign stock universe needs
historical index membership and delisted prices that free data does not have.
Rules built on US-only inputs that cannot be swapped (EDGAR fundamentals) are
not covered either. Rules with more than one equity leg are not covered. An
uncovered rule falls back to the paper track or a labeled forced unseal.

## Market sets

Fixed before any result is seen. Each set is used once, in this order, for
successive accepted rules.

| Set | Markets (iShares country ETFs, USD) | Data from |
|---|---|---|
| main | EWJ Japan, EWU UK, EWG Germany, EWC Canada, EWA Australia, EWL Switzerland, EWQ France | 1996-03 |
| reserve_1 | EWN Netherlands, EWD Sweden, EWP Spain, EWI Italy, EWH Hong Kong, EWS Singapore | 1996-03 |
| reserve_2 (emerging) | EWZ Brazil, EWT Taiwan, EWY South Korea, EEM emerging markets | 2000-2003 |

- A pass or fail on a set is final for that rule. A reserve set is never used
  to rescue or retry a rule. It is the unseen test for the next accepted rule,
  because the earlier set's results have then been seen.
- The reserve sets do not overlap the main set (a regional fund such as EFA
  would mostly repeat it).
- reserve_2 is reported as its own group: a fail there can come from
  emerging-market specifics (currency crises, commodity swings) rather than the
  rule. Its early window is short (2001-2004; EEM 2004 only).

## Windows

Only years the rule never touched, in each market:

- Early: 1997-01-01 to 2004-12-31. Before the US research period (2005-2018);
  includes the dot-com bust, the 1997 Asian crisis and 1998.
- Late: 2023-01-01 to the frozen data end (see Sealing).
- 2005-2022 is excluded from scoring: it overlaps the US research and
  validation periods, and markets crash together (2008), so a US-tuned rule
  would be partly re-checked on events it was fitted to.

Warm-up: the backtest runs on each market's continuous series from its first
date. Scoring in a market starts at the later of the window start and the first
day all of the rule's lookbacks are filled. So a long lookback, or a fund that
started late (reserve_2: EWZ, EWT, EWY 2000; EEM 2003-04), shortens or empties
that market's early window; it is never filled in from elsewhere.

Minimum data: a market needs at least 500 scored trading days across both
windows. A market below that counts as not passed (the count's denominator
stays 7, 6 or 4).

Scoring: the rule's daily returns (net of costs) from the two windows are
joined end to end, in order, and metrics are computed once on that joined
series with `qrl.metrics` (252-day annualization). The excluded years never
enter, and drawdown is measured on the joined curve, so no drawdown spans the
gap. Buy-and-hold is scored the same way. Per-window figures are reported for
information only; the verdict uses the joined series.

Costs: the engine default (5 bps on turnover), applied during the continuous
backtest.

## Translation

One mechanical translation, fixed here, no per-market choices:

- The rule's config must name its timed equity leg (`equity_leg`, for example
  SPY or QQQ). Every other ticker in the rule must be on the defensive list in
  config/international.yaml: GLD, IEF, TLT, SHY, cash. A rule with no
  `equity_leg`, or with any other ticker, is refused as not covered.
- The equity leg is replaced by the market's ETF. Every parameter stays as
  accepted.
- Defensive legs stay the US-dollar investor's assets.
- Macro signals, if any, stay US signals, with the lags already in
  `config/macro.yaml`.

The question this answers: does the timing logic work on other stock markets,
for a US-dollar investor?

Defensive-leg proxies, used only before each fund's first date and spliced at
that date (so the price series has no jump):

| Leg | Fund start | Proxy before it (FRED) | Duration used |
|---|---|---|---|
| SHY | 2002-07 | DGS2 | 1.9 |
| IEF | 2002-07 | DGS10 | 7.5 |
| TLT | 2002-07 | DGS20 | 17.0 |
| cash | none | DTB3 | 0 |

Daily proxy return = previous yield / 252 - duration x (yield change), yields
in decimals, each yield lagged one business day (FRED publishes H.15 rates the
next day), so the proxy uses nothing not known at the close.

Gold: GLD from 2004-11-18. Before that: Yahoo `GC=F` (COMEX front-month
gold futures, unadjusted continuous series, from 2000-08-30), lagged one
business day and spliced to GLD at GLD's first date. It is a futures price,
not the London fix (the LBMA fix is no longer freely available), so a roll
can add a small jump. `check-data` reports the daily-return correlation of
`GC=F` against GLD over 2004-11-18 to 2006-12-31; this compares gold data
only, never a rule result. If it is below 0.95, a rule that can hold gold is
scored on the late window only, and its report says so. There is no gold
data before 2000-08-30: a gold-holding rule's early window starts once
`GC=F` covers its warm-up (about mid-2001 for a 200-day lookback).

The engine is unchanged: translation and proxies only build the price frame it
receives.

## Pass rule

Per market: the translated rule versus buy-and-hold of that market's ETF,
both scored on the joined windows. One threshold set for every covered rule
kind:

- Sharpe >= buy-and-hold Sharpe + 0.05.
- Max drawdown no worse than buy-and-hold's.
- CAGR >= buy-and-hold CAGR - 0.01.

Across the set, both must hold:

- Count: at least 5 of 7 markets pass (main), 4 of 6 (reserve_1), 3 of 4
  (reserve_2).
- Average: the mean Sharpe improvement (rule minus buy-and-hold) across all of
  the set's markets with enough data is above 0.

Markets are correlated (daily correlation with the US of about 0.7-0.9), so
the count alone is weaker evidence than independent tests; the average guards
against a narrow count hiding large losses.

## Sealing

The market sets are sealed like the holdout:

- No rule is run on any set before a rule is accepted. The tool is built and
  tested on synthetic data only.
- `check-data` may download and report coverage (first date, gaps, proxy
  coverage per window). It never prints or stores returns or metrics.
- A run needs a rule that passed validation, `--confirm`, and a fresh owner
  go-ahead.
- Sets are used in order: main, then reserve_1, then reserve_2. A run on a
  later set is refused while an earlier one is unused.
- Before anything is scored, the run writes an `international_events` row:
  set, rule id, rule config sha256, `international.yaml` sha256, git commit,
  data end date (the last complete trading day before the run), a sha256 of the
  frozen price and proxy data, reason, time, status `started`. Data after the
  recorded end date is dropped.
- A set with an event is used. There is no force option.
- If a run fails after its event, it may only be re-run with the same rule
  hash, config hash and data hash (a deterministic recompute, not a retry with
  new data). The row moves to status `completed` with the report path when the
  report is written.

## Components

- config/international.yaml: sets, windows, warm-up start, pass rule,
  proxies. Its sha256 is recorded with each event; a run refuses if it changed
  since the spec commit.
- src/qrl/international.py: pure functions. Translate a rule (swap the
  equity ticker, parameters unchanged), score windows, per-market verdict, set
  verdict. No data loading.
- `qrl.ledger`: new `international_events` table and its check.
- scripts/international.py (pixi task `international`): subcommands
  `check-data --set <set>` and `run --set <set> --rule <id> --confirm`.
- `research/international_<set>.md`: written once per run. Per-market table,
  count, average, verdict.
- No changes to locked files (engine, metrics, periods, checks, locked YAMLs,
  existing tests).

## Tests (new only)

- A second run on a used set is refused; nothing is recorded without
  `--confirm`.
- Verdict logic: 5 of 7 with a negative average fails; 6 of 7 with a positive
  average passes; 4 of 7 fails.
- Dates 2005-01-01 to 2022-12-31 never enter scoring.
- Translation changes only the equity ticker, never a parameter.
- `check-data` output contains no return or metric figures.
- Hash-change refusal.
- scripts/international.py never sets `unseal_holdout=True` (covered by
  `tests/test_holdout.py`'s scripts guard).
