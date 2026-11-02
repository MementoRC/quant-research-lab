# History-grounded scenarios: every large fall since 1971

Status: Implemented (2026-11-01). Owner answered the design questions in
conversation on 2026-10-30 and 2026-10-31.
Extends [decision-helper.md](decision-helper.md) (Delivery, item 3) and
[income-explorer.md](income-explorer.md) (Out of scope).

## Goal

A report that shows, for each portfolio in the decision helper, what happened
in every large stock-market fall since 1971: how far it fell, how long it took
to get back, and what a fixed inflation-indexed withdrawal from the peak left
after 5 and 10 years. It gives the typical (median) and the worst outcome, and
every episode on its own row.

The existing reports test two hand-picked windows (`dotcom_2000`,
`gfc_2008`). This report lets a rule pick the episodes instead, and reaches
back before the funds existed using stand-in data.

It is a decision aid. It selects nothing and recommends nothing.

## Data rules

- Only data up to 2018-12-31 (the end of the research period, from
  `decision.data_end`) is read. Every series, including the non-FRED ones, is
  cut there, in src/qrl/history_data.py, right after loading
  (`data.load_prices` has no end date). Validation and holdout stay sealed.
- Data before 2005 is not sealed and may be used (decision-helper.md, Data
  rules).
- The portfolio price panel starts on the first trading day on which every
  stand-in has a price (expected 1971-02-05, the first Nasdaq Composite close;
  the data probe pins the date in config/history.yaml). The S&P 500 index used
  to date episodes is read from its full history (see Episodes).
- CPI is FRED CPIAUCNS, loaded with `macro.load_macro` as the withdrawal
  reports do, from 1970 so the first yearly raise has a value.

## Episodes

- Found on the S&P 500 price index (`^GSPC`, without dividends, the usual way
  bear markets are dated), daily closes, over its full history up to
  2018-12-31, so a "peak" is a true all-time high and not just the highest
  close since 1971.
- An episode starts at a peak: a close higher than every earlier close. It
  counts if a later close is 15% or more below that peak before the index
  closes at or above the peak again. Exactly 15% counts; 14.9% does not.
- The trough is the lowest close between peak and recovery. Depth is
  peak-to-trough. The recovery date is the first close at or above the peak.
  A second dip before recovery is part of the same episode. Length is peak to
  recovery, in calendar months.
- An episode not recovered by 2018-12-31 is kept: recovery "not recovered by
  2018", length "-". A fall that would reach 15% only after 2018-12-31 cannot
  be seen and is not an episode.
- Only episodes whose peak is on or after 1971-01-01 are reported.
- The episode list is computed from the index alone, before any portfolio
  result.
- The threshold (15%) and start date are fixed in the config. They were chosen
  from the expected number of episodes (about 10 at 15%, about 5 at 20%), not
  from any outcome. The actual count comes from the data.

## Portfolios

The 12 portfolios of the decision helper: A-G, CASH, G-EW, AG, G-CASH, A-CASH.
Definitions are read from `config/core_candidates.yaml` and
`config/decision.yaml`, unchanged; their sha256 values are recorded.

Returns: `decision.portfolio_returns` is called once per portfolio over the
whole panel, with the engine unchanged, its normal 5 bps cost per unit of
turnover, and daily rebalancing. Its start is the first trading day on which
every weight is defined (after the 200-day warm-up of the switching rules;
the panel start for static portfolios). Each episode then reads that one
daily return series from its peak. Switching portfolios (A, B, C, F, and A
inside blends) keep their daily 200-day rule. If an episode's peak is before
a portfolio's start, its cells are "no signal yet". Nothing is filled in.

## Stand-in data

Each fund's own prices are used from its first trading day. Before that a
stand-in is used, joined without a jump by `international.splice`. On every
stand-in day the open is the previous close (no overnight gap), the
convention of `international.build_panel`; the rule is applied in
src/qrl/history_data.py (build_panel itself is not called, and yfinance's
old index opens are not used). So the engine's open and close frames are
both defined on every day.

| Fund | Stand-in before the fund existed |
|---|---|
| SPY | `^SP500TR` from its first close in 1988. Before that: `^GSPC` plus the Shiller monthly dividend yield, accrued daily (yield / 252 per trading day). |
| QQQ | Nasdaq Composite (`^IXIC`). |
| SHY | Total return from FRED DGS2 by `international.yield_proxy_close`, from its first value (1976-06-01). Before that, DGS1, joined without a jump. Both use SHY's duration. |
| IEF | Same, from FRED DGS7. |
| TLT | Same, from FRED DGS20, except 1987-01-01 to 1993-09-30 when DGS20 was not published: there DGS30 is used, joined without a jump. Each maturity has its own duration. |
| GLD | Before 2000: World Bank (Pink Sheet) monthly gold price. From the first `GC=F` close in 2000: gold futures. From GLD's first trading day (2004-11-18): GLD. Spliced in that order. |
| RSP | The SPY stand-in. An approximation, labelled. |

- The World Bank figure is a monthly average. It is placed on each month's last
  trading day and the days between are filled at a constant daily rate
  (geometric interpolation), so each month-end equals that month's figure.
  Because the figure is an average, this makes gold smoother than it was; the
  report says so.
- Exact series ids, yield maturities, durations and lags (for
  `international.yield_proxy_close`), source URLs and switch-over dates are
  pinned in the new config, config/history.yaml.
- Every stand-in must cover the panel start to its fund's first day. Interior
  gaps of at most 1 trading day are forward-filled, the same rule as
  `international.fill_proxy_gaps`; a longer gap is an error.
- Downloads are cached in their own directory, data/cache/history, and not
  committed. The loader checks each series' first date and raises if a cached
  series starts later than needed (the shared cache may hold series fetched
  from 1999). The report records
  the sha256 of each raw series. Only openly available sources are fetched;
  nothing is redistributed in the repo.

### Stand-in checks

Where a stand-in and the next series overlap, the correlation of their returns
must be at least 0.95, the bar of the international test
([international-test.md](international-test.md)).

- SPY, QQQ: daily returns, stand-in against fund, over the whole overlap to
  2018-12-31.
- SHY, IEF, TLT: monthly returns (month-end to month-end), stand-in against
  fund, over the whole overlap to 2018-12-31. Each yield is used on its own date
  (lag 0). A yield proxy is a fitted curve at one maturity, rounded to 0.01
  point, while a fund holds a range of maturities; for short bonds that
  difference is large next to one day's move. Daily checks were measured first,
  by the data probe: at lag 0, SHY 0.70, IEF 0.948, TLT 0.949; at lag 1 (a day
  off), about -0.04. Monthly returns measure the price path, as for gold. SHY is
  checked on its DGS2 proxy. On monthly returns at lag 0, the DGS1 proxy gave
  SHY 0.855, below the bar, and the DGS2 proxy 0.981 (IEF 0.978, TLT 0.978).
  The DGS1 part (1971 to 1976) ends before SHY existed and cannot be checked
  against it.
- Gold: monthly returns, because daily gold futures and GLD close at
  different times (the international test measured their daily correlation
  at 0.934). Two checks: World Bank against the monthly average of `GC=F`;
  month-end `GC=F` against month-end GLD.
- RSP has no check: its stand-in is a stated approximation.

The report shows each check: series, stand-in, overlap, frequency,
correlation.

## Measures

Each portfolio, in each episode, has value 1 at the close of the peak date;
its daily returns apply from the next trading day. The measure window for
worst loss runs from the peak to the earlier of 10 years later or 2018-12-31;
the episode table shows each window's end.

1. **Worst loss.** 1 minus the lowest value in the window. A portfolio that
   never goes below 1 shows 0.0%. Nominal, like the stress tables
   (`src/qrl/stress.py`).
2. **Months to recover.** Calendar months from the peak to the first close at
   or above 1 after its low, looking as far as 2018-12-31 (not capped at 10
   years). Only the month arithmetic of `decision_withdraw` is reused;
   `decision_withdraw.longest_below_peak` measures a different thing (the
   longest spell below any running peak). 0 if it never goes below 1. If none
   by 2018-12-31: "not recovered by 2018".
3. **Income path.** A fixed CPI-indexed withdrawal at 2%, 3.3%, 4% and 5% a
   year, using `decision_withdraw.monthly_withdrawals` and
   `decision_withdraw.withdrawal_path` unchanged. The path starts on the first
   trading day after the peak, and the first withdrawal is taken on that day
   (`withdrawal_path` withdraws on its first row). `monthly_withdrawals` gets
   that day's year as start year and an end year 11 years later, capped at
   2018, so a 120-month horizon is always covered. As in those functions, the
   amount is raised each January by the usable CPI (so a September peak gets
   its first raise four months later). Reported: the real balance 60 and 120
   months after the peak, as a % of the start, deflated as
   `decision_withdraw.path_metrics` does, or "depleted" with the month it ran
   out.

Edge cases:

- An income horizon that ends after 2018-12-31 is "n/a (data ends)". So the
  5-year and 10-year columns have different counts.
- Medians and worst cases skip "n/a" and "no signal yet" cells, and each
  summary cell states its count (e.g. "median of 9").

## Labels

Set per cell, over that cell's window: the measure window for worst loss; peak
to recovery (or 2018-12-31) for months to recover; peak to horizon for an
income cell:

- † if any fund the portfolio can hold (both branches of a switching rule,
  and every part of a blend) uses stand-in data on any day of the window.
- ‡ if the portfolio can hold GLD and the window includes any day before the
  first `GC=F` close (interpolated gold).
- A cell can carry both.

## Report

research/history_scenarios.md, in this order:

1. Header bullets: data cutoff; threshold; config sha256 values, each as a
   line `- config/NAME.yaml sha256: `<hex>`` (the format
   `tests/test_docs_freshness.py` checks); raw stand-in sha256 values; the
   number of portfolios compared (12), with the same multiple-comparison
   disclosure as `research/decision.md`.
2. Episodes: peak, trough, recovery date, S&P depth, length, measure-window
   end.
3. Stand-in checks.
4. Falls summary: per portfolio, median worst loss, deepest loss (with
   episode), median months to recover, longest recovery (with episode).
5. Income summary: one table per withdrawal rate; per portfolio, median and
   worst real balance at 5 and 10 years, each with its count.
6. Per-episode detail: portfolio x episode tables for worst loss, months to
   recover, and real balance after 10 years at each rate.
7. Label legend for † and ‡.
8. Caveats, in plain words: few episodes (about 10); stand-ins are not the
   funds; interpolated monthly-average gold is smoother than gold was; RSP is
   approximated by the S&P 500; daily rebalancing; the report selects nothing
   and recommends nothing.

No existing report or number changes.

## Code

| File | Role |
|---|---|
| config/history.yaml | Threshold, start date, portfolio ids, rates, horizons, correlation bar, stand-in sources (ids, maturities, durations, lags, URLs, switch-over dates). |
| src/qrl/history_data.py | Builds the daily open/close panel. Reuses `international.yield_proxy_close`, `international.splice`, `macro.fetch_series` and the yfinance loader in `src/qrl/data.py`. New loaders, cached in data/cache/history and cut at 2018-12-31: fetch_shiller_dividend_yield, fetch_worldbank_gold. New: S&P plus dividends, gold interpolation, the previous-close open rule,
the cut at 2018-12-31, the first-date check, the stand-in checks. |
| src/qrl/history.py | Pure functions: find_episodes, episode_measures, cell_labels, summarize. No I/O. |
| src/qrl/history_report.py | Renders the markdown. |
| scripts/history_scenarios.py | Command line; pixi task history-scenarios. |

## Failure

Fails loudly: raises, and writes no report, if

- a stand-in check is below 0.95;
- a series has an interior gap longer than 1 trading day, or does not reach
  back to the panel start;
- a download fails;
- any data after 2018-12-31 would be read;
- no episode is found.

A partial report is never written.

## Tests

Offline, on small hand-built series, in the style of the existing tests.

- find_episodes: a 15.0% fall counts and 14.9% does not; two dips without a
  new high are one episode; recovery is at or above the peak; an episode
  unrecovered at the end is kept; a peak before the start date is dropped
  even if its fall is after it.
- Measures: hand-computed worst loss and months to recover; 0.0% and 0 months
  for a path that never falls; "not recovered by 2018"; "n/a (data ends)" and
  the counts in summaries; the depletion month; "no signal yet" for a peak
  before a portfolio's start.
- Labels: † and ‡ set by the window rule, both on one cell.
- Gold interpolation puts each monthly figure exactly on its month-end.
- A stand-in below the correlation bar raises; a 2-day gap raises.
- The report contains the † and ‡ legend, the caveats and "selects nothing
  and recommends nothing", and its config hash lines pass
  `tests/test_docs_freshness.py`.

Existing tests are not changed.

## Delivery

1. This spec (feature branch, PR to development).
2. Implementation PR.
3. Run; commit the report.
4. Later, separate: a dashboard section.

## Rejected alternatives

- Macro triggers (inflation, hikes, curve inversion): more thresholds to pick,
  easier to cherry-pick.
- A 20% threshold: about 5 episodes, too few for a median.
- Measuring from the trigger day: misses the first 15% of the fall.
- All-monthly data: the switching rules would need a monthly version and would
  no longer be the rules compared elsewhere.
- Starting in 2000 (daily gold futures only): about 5 episodes, drops the
  1970s and 1980s.
- Fund prices only: most pre-2002 cells would be "not priced".
- Daily gold correlation checks: futures and GLD close at different times, so
  a daily check measures timing, not the price.
- Daily bond correlation checks: they measure one-day noise between a fitted
  yield and the fund, not the price path (SHY 0.70 daily).
- A lower bar for bonds, or dropping the bond stand-ins: the first changes the
  international test's rule, the second loses every year before 2002.
- DGS1 alone for SHY: its monthly correlation with SHY was 0.855, below the
  bar. A one-year yield rounded to 0.01 point is too coarse for a 1-3 year
  fund.

## Out of scope

Macro-triggered episodes, other withdrawal rules or staged entry, international
markets, data after 2018-12-31, and any change to existing reports.

## Open questions

None outstanding. Exact series ids, durations and lags are settled in the
plan and pinned in config/history.yaml.

Amended 2026-10-31 before implementation: the panel starts when every
stand-in has a price, because the Nasdaq Composite starts on 1971-02-05
(owner decision).

Amended 2026-11-01 before implementation: the bond stand-in checks use
monthly returns, with each yield on its own date (lag 0) (owner decision).
The daily figures quoted in Stand-in checks were seen before this change was
made; no portfolio result had been computed.

Amended again 2026-11-01 before implementation: SHY's stand-in is DGS2, with
DGS1 before 1976 (owner decision). The owner chose this rule, and that it
must pass the same monthly 0.95 bar, after seeing the DGS1 figure (0.855)
and before the DGS2 figure was measured.
