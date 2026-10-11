# True-cash sleeve: 80% A + 20% cash at an assumed +1% real

Status: spec written 2026-10-11, owner-approved design 2026-10-11. Not yet implemented.
Extends [defensive-sleeve.md](defensive-sleeve.md), [decision-helper.md](decision-helper.md)
and [longrun.md](longrun.md).

## Question

The defensive-sleeve report warns that its cash baseline, A80-CASH20, holds
SHY, and that SHY's near-zero 2009-2015 yields make it look worse than cash
at today's rates. How much does that one fact matter? This spec adds one
row, A80-TCASH20: 80% A (`core_trend`, QQQ/GLD, 200-day) plus 20% true cash
earning each month's inflation plus 1% a year. It is the same assumption as
the long-run report's existing "CASH +1% real (assumption)" row.

## An assumption row, not a fund, and not a test

- Historical Treasury bills also paid about 0% in 2009-2015, so no price
  series gives "cash at today's rates" for that era. An assumption is the
  only way to show it. The row is labelled as such everywhere.
- It is a sensitivity row next to A80-CASH20, not a candidate. It is a
  comparison, not a pass/fail test: no criteria, combined or validation rule
  is applied to it. It adds no trials to any search run.
- Research period (2005-2018) only. Validation (2019-2022) and the holdout
  (2023 on) stay sealed.

## Configuration

`config/decision.yaml` gets a dated amendment and one new, optional
top-level key:

```yaml
# Amendment 2026-10-11 (owner-approved design, spec
# docs/methodology/true-cash-sleeve.md): optional cash_assumption row
# A80-TCASH20 added. It is not a portfolio: it never enters the windows,
# scenarios or year-one tables. Existing entries unchanged; candidates_sha256
# unchanged.
cash_assumption:
  id: A80-TCASH20
  label: "80% A + 20% cash at +1% real (assumption)"
  base: A
  cash_share: 0.2
  real_yield: 0.01
```

Loader (`src/qrl/decision_config.py`, `load_decision_config`):

- The key is optional. Absent: no row anywhere, and every existing fixture
  (`GOOD`, `GOOD_SLEEVE` in `tests/decision_helpers.py`) loads exactly as
  today.
- Present, it must be a mapping with `id`, `label`, `base`, `cash_share` and
  `real_yield`. The loader refuses (ValueError):
  1. not a mapping, or a missing key;
  2. an `id` that does not match the existing id pattern `[A-Za-z0-9_-]+`;
  3. an `id` equal to any portfolio id (A-G, statics, blends);
  4. a `base` that is not an existing portfolio id;
  5. a `cash_share` not strictly between 0 and 1 (NaN is refused too);
  6. a `real_yield` that is not finite or lies outside -0.05 to 0.05
     (inclusive).
- The result is a new frozen record `CashAssumption(id, label, base,
  cash_share, real_yield)` stored in a new field
  `DecisionConfig.cash_assumption`, default `None`, placed last so existing
  code that builds a `DecisionConfig` is unaffected.
- The row is not added to `DecisionConfig.portfolios`. Everything that loops
  over portfolios (historical windows, scenarios, year-one, held-fund checks)
  therefore cannot see it.

Bookkeeping:

- `decision.yaml`'s sha256 changes. `config/longrun.yaml`'s
  `decision_sha256` is re-pinned with the comment: "Amendment 2026-10-11:
  decision_sha256 re-pinned after the true-cash assumption row was added
  (docs/methodology/true-cash-sleeve.md). No other key changed."
- `candidates_sha256`, every existing portfolio, scenario, window, rate and
  start year are unchanged.

## Consistency with the long-run report

The row and the long-run "CASH +1% real" row must use the same real yield.
The long-run run refuses (ValueError) if `decision.yaml`'s
`cash_assumption.real_yield` differs from `longrun.yaml`'s
`cash_real_yield` (exact equality; both are read from YAML text).

Where the check lives. `load_longrun_config(path, decision_sha256)` sees only
the decision file's hash, not its contents, so it cannot make the check
without a new argument. Smallest testable change: a new pure function in
`src/qrl/longrun.py`, `check_cash_assumption(lcfg, dcfg)`, which does nothing
when `dcfg.cash_assumption` is None and raises otherwise on a mismatch. It
is called

- by `scripts/longrun.py` immediately after `load_longrun_config`, before
  any price or CPI data is loaded (the same "check the config before the
  data" order the decision-hash pin already follows), and
- as the first statement of `run_longrun`, so any direct caller is also
  protected.

`load_longrun_config`'s signature and behaviour are unchanged.

## Computation

New code only. `engine.py`, `metrics.py`, `periods.py` and `checks.py` are
imported, never edited. Price and CPI frames are cut at the data end
(2018-12-31) before any use, exactly as the existing decision and long-run
functions do.

Cash leg, daily return on trading day d of calendar month m:

    r_cash(d) = ((1 + infl_m) x (1 + y)^(1/12))^(1/n_m) - 1

- y = `real_yield` (0.01).
- n_m = the number of trading days of month m in the cut price index
  (`data["close"]` after the cut). Every trading day of a month earns the
  same rate, and a whole month compounds to exactly
  (1 + infl_m) x (1 + y)^(1/12), the long-run row's monthly return. All
  current paths start on the first trading day of a January and end on
  2018-12-31, so every month they cover is whole.
- infl_m = the long-run report's monthly inflation: CPIAUCNS usable on m's
  last calendar day divided by CPIAUCNS usable on (m-1)'s last calendar day,
  minus 1, with the decision helper's availability rule (month M's value is
  usable from the last calendar day of M+1). So infl_m is month m-1's
  published change, which first becomes usable on m's last calendar day.
- Timing, a known simplification. infl_m accrues on every trading day of
  m, including the days before it is published at the end of m. This is
  deliberate: it keeps the cash leg at exactly +1% a year real against the
  decision helper's own deflator (see the check below). It is not a trading
  look-ahead: the row's returns never feed any weight, signal or choice;
  they only fill report cells. It is a simplification inside an assumption
  that is already labelled as one. Alternative rejected: lagging the figure
  one more month (month m earns infl_(m-1)). It removes the timing issue but
  breaks the exact deflator identity, so the row would no longer be exactly
  +1% real over a path.
- First month. For a path starting in January of year Y, the first figure
  reads the values available on 31 December of Y-1 (November's CPI) and
  31 January of Y (December's CPI). For 2005 this reads one pre-2005 value,
  as the long-run report already does. The last month, December 2018, reads
  values available on 30 November and 31 December 2018, both on or before
  the data end.
- Missing CPI: refuse, never fill. The existing `monthly_inflation` accepts
  any value up to 45 days old (`MAX_CPI_AGE`), so a single missing month
  would silently give that month 0% inflation and the next month a double
  figure. The new code adds a stricter check first: the CPI series must
  hold a non-missing value dated exactly on the last calendar day of every
  month it reads (m and m-1, for every m used). Otherwise it raises "missing
  CPI for month m". When the check passes, `monthly_inflation` returns
  exactly those values, so the long-run report's monthly inflation and this
  row's agree month for month.

The row:

    r_row(d) = (1 - s) x r_base(d) + s x r_cash(d)

- s = `cash_share` (0.2). r_base = `decision.portfolio_returns(base, ...)`,
  unchanged: same start day, same cost (`criteria` cost_bps, 5 bps per unit
  of turnover), same refusals.
- This equals 80% A and 20% cash rebalanced back to 80/20 every day, the
  same daily rebalancing every other portfolio in the report has.
- Disclosed differences from A80-CASH20: the cash leg pays no trading cost,
  and the daily trades that bring the two legs back to 80/20 pay no cost
  either. A80-CASH20 runs through the engine and pays 5 bps on its daily
  drift rebalancing. The difference is small but favours the assumption row.
- Check on the inflation figures: for a path from the first trading day of
  January Y to 2018-12-31, the cash leg grows by exactly CPI(Nov 2018) /
  CPI(Nov Y-1) x 1.01^(2019 - Y). The decision helper's own real deflator
  for that path is the CPI usable on 2018-12-31 over the CPI usable on the
  start day, i.e. the same CPI(Nov 2018) / CPI(Nov Y-1) (December's value is
  only usable from 31 January). So in the withdrawal tables the cash leg
  alone, with no withdrawals, ends at exactly 1.01^(2019 - Y) in real terms:
  +1% a year, as intended.

Code placement. `decision.py` must compute the row, but `longrun.py`
imports `decision.py`, so `decision.py` cannot import `longrun.py` (circular
import). Therefore:

- `monthly_inflation` moves, body unchanged, from `longrun.py` to
  `src/qrl/decision_withdraw.py` (beside `usable_cpi`, its only dependency).
  `longrun.py` imports it from there, so `qrl.longrun.monthly_inflation`
  stays importable and `tests/test_longrun.py` is unaffected. Its
  `from .decision_withdraw import usable_cpi` import, used only inside
  `monthly_inflation`, becomes unused and is replaced by
  `from .decision_withdraw import monthly_inflation`.
- New module `src/qrl/true_cash.py`, pure functions:
  `cash_leg_returns(days, trading_days, cpi, real_yield)` (the strict CPI
  check, then r_cash on `days`) and `mix_returns(base, cash, share)`.
- `src/qrl/decision.py`: new `assumption_returns(cfg, data, cpi, start,
  cost_bps)` returning the row's daily series (or None without a
  `cash_assumption`). It appends the row after all portfolio rows, so it is
  the last row of each table:
  - `return_rows(cfg, data, criteria, cpi=None)`: the new `cpi` argument
    is optional. It raises ValueError when `cfg.cash_assumption` is set and
    `cpi` is None. `run_decision` passes its `cpi`. The six existing calls
    in `tests/test_defensive_sleeve.py` (lines 109, 133, 147, 152, 161,
    167) pass three positional arguments; they are unchanged and still pass,
    because their fixture (`GOOD_SLEEVE`) has no `cash_assumption`.
  - `withdrawal_rows`: building the paths stays in the caller, because
    `portfolio_returns` needs a `Portfolio` (`decision.py:234`). For each
    portfolio the loop builds `paths` (start year to daily returns) with
    `portfolio_returns` as today; for the row it builds them with
    `assumption_returns` at each start day. Only the per-rate block (the
    metrics per start year, first and worst year, and the row dict;
    `decision.py:235-253`) is extracted, unchanged, into a helper
    `_withdrawal_rows_for(pid, paths, cfg, cpi)`, called once per portfolio
    and once for the row. Without a `cash_assumption` the output is
    byte-identical to today's.
  - `run_decision` adds one key, `cash_assumption` (the five config fields
    as a dict, or None).
- `src/qrl/longrun.py`: `run_longrun` compounds the same daily series to
  months with `monthly_returns` and appends the row after all portfolio
  rows, on the same block draws (paired). Its report dict gains three keys
  from the decision config: `cash_assumption_id` (the id, or None),
  `cash_assumption_base` (the base portfolio id, or None) and
  `cash_assumption_share` (the cash share, or None).

## Where the row is shown

Decision report (`research/decision.md`):

- "Research-period return (2005-2018, no withdrawals)": CAGR, max drawdown
  and CAGR given up vs A, from `qrl.metrics.compute_metrics`, as for every
  portfolio.
- "Withdrawals": every rate table (2%, 3.3%, 4%, 5%), every start year
  2005-2014 (first-year columns and worst start year), as for every
  portfolio.
- Not in "Portfolios", "Historical windows", "Judgement-based scenarios" or
  "Year-one scenario hit".

Long-run report (`research/longrun.md`): every withdrawal-rate table, as the
last row, alongside A80-CASH20 and "CASH +1% real (assumption)".

Rows are named by the id, A80-TCASH20, in both reports; the notes give the
label.

### Why it is left out of the windows, scenarios and year-one tables

Those sections do not treat SHY as true cash, and they have no cash return
to give the row. Exactly:

- Historical windows (`qrl.stress`). In `dotcom_2000` SHY did not yet trade,
  so it is already replaced by cash at 0%: the row's frozen cell would equal
  A80-CASH20's. In `gfc_2008` SHY is priced, so A80-CASH20's cells use SHY's
  actual 2007-2009 prices. The stress module only models cash at 0%; it has
  no CPI-linked cash, so the row would need a new window-specific
  assumption.
- Judgement-based scenarios. SHY has owner-set one-year returns (+1%, +2%,
  +3% in the three shocks); no cash return is set. "Inflation +1%" would
  give cash +9.1%, +8.1% and +3.0%, far above SHY; whether cash keeps pace
  with an 8% inflation shock within one year is a new judgement this design
  does not make.
- Year-one is built from the scenarios, so the same applies.

The decision report's Notes section gets one conditional bullet saying this
in plain words (present only when the row is).

### Header and notes

Decision report (`decision_report.py`). Everywhere below, a missing
`report["cash_assumption"]` key is treated the same as None (no row): the
hand-built `_hand_report` in `tests/test_decision_report.py` has no such
key, and its rendered text stays byte-for-byte as today.

- `_header`: the multiple-comparison count includes the row: "7 in the core
  comparison, 22 here (A-G again plus 15 new)". The count is
  `len(report["portfolios"])` plus one when `cash_assumption` is present;
  without it the line is unchanged.
- One new header bullet, after the existing sleeve note and present only
  with the row. For the shipped config it renders as: "- A80-TCASH20 (80%
  A + 20% cash at +1% real (assumption)) is an assumption row, not a fund:
  20.0% cash earning each month's inflation plus 1.0% a year, the long-run
  report's CASH +1% real assumption, shown to answer the SHY caveat above.
  It is comparison 22 but not one of the 21 portfolios. Its cash leg and
  its daily return to 80/20 pay no trading cost, while A80-CASH20 pays 5 bps
  per unit of turnover on its rebalancing, a small difference in the
  assumption row's favour."
  Template: with N = `len(report["portfolios"])` (computed, never
  hard-coded), the id, label, cash share and real yield come from
  `report["cash_assumption"]` (share and yield via `_pct`), "comparison 22"
  is N + 1, "the 21 portfolios" is N, and "5 bps" is
  `{report['cost_bps']:g} bps`, as in the existing cost note
  (`decision_report.py:86`).
- `_sleeve_note` needs no change. It counts ids in `report["portfolios"]`,
  which never contains the row, so it still reads "of the 21 portfolios
  here, 4 are by-product rows ...; only the 5 A80 rows ... answer the
  defensive-sleeve question". The "A80-" prefix of the new id cannot be
  miscounted there.

Long-run report (`longrun_report.py`):

- `_sleeve_note` counts names in the rows by the "A80-" prefix, so it would
  count the assumption row as a sixth A80 fund row and still say the rows
  include only one assumption row. Handling: when `cash_assumption_id` is
  present, it is left out of the A80 count and named as an assumption row:
  "- 23 rows per withdrawal rate, including the CASH +1% real (assumption)
  row, the A80-TCASH20 assumption row and 4 by-product rows (IEF, TLT, RSP,
  BONDS); only the 5 A80 rows answer the defensive-sleeve question
  (docs/methodology/defensive-sleeve.md)". When it is absent (or the key is
  missing from the report dict) the line is byte-for-byte as today.
- One new note, present only with the row. For the shipped config it
  renders as: "- A80-TCASH20: an assumption, not history. 80.0% A plus 20.0%
  cash earning each month's inflation plus 1.0% a year, rebalanced daily;
  its real yield is checked equal to the CASH +1% real row's. The cash leg
  and the daily return to 80/20 pay no trading cost, while A80-CASH20 pays
  5 bps per unit traded on its rebalancing, a small difference in the
  assumption row's favour."
  Template: the id is `r["cash_assumption_id"]`; "80.0%" is
  `_pct(1 - r["cash_assumption_share"])` and "A" is
  `r["cash_assumption_base"]`; "20.0%" is `_pct(r["cash_assumption_share"])`;
  "1.0%" is `_pct(r["cash_real_yield"])` (already checked equal to the
  decision config's yield); "5 bps" is `{r['cost_bps']:g} bps`.

## Outputs

- Regenerate `research/decision.md` (`pixi run decision`) and
  `research/longrun.md` (`pixi run longrun`). No new report file; no new
  section titles, so the public dashboard and its section-title tests are
  unaffected.
- The PR description gives a short summary: A80-TCASH20 against A80-CASH20
  on CAGR, max drawdown, withdrawal survival and long-run depletion.

## Tests

New file `tests/test_true_cash.py`, offline (synthetic prices and CPI from
`tests/decision_helpers.py`):

- loader: the shipped `decision.yaml` loads with the exact
  `CashAssumption` above; each of the six refusals raises; an absent key
  gives `cash_assumption is None` and the same portfolio list.
- the row is not in `cfg.portfolios` and so not in the windows, scenario
  rows or year-one rows of `run_decision`.
- long-run: `check_cash_assumption` raises on a real-yield mismatch, passes
  on equality and without the key; `run_longrun` raises before reading any
  data; `scripts/longrun.py` refuses before loading prices or CPI.
- every exactness test below uses a CPI with uneven monthly changes (as
  `tests/test_longrun.py`'s `_cpi_by_availability(levels=...)` does), not
  the constant-growth `decision_helpers.cpi()`, which cannot catch a
  one-month misalignment.
- `return_rows` refuses a `cash_assumption` without `cpi`.
- cash leg: deflated by the CPI, each whole month earns exactly
  (1.01)^(1/12) real, and over 2005-2018 the leg divided by the decision
  helper's own deflator is 1.01^14 (relative tolerance 1e-12).
- each trading day of a month earns the same rate; months with different
  trading-day counts still compound to the same monthly figure.
- missing CPI: a single missing month (which `monthly_inflation` alone
  would pass) is refused, as is a NaN value.
- the row equals (1 - s) x `portfolio_returns(A, ...)` + s x cash leg, day
  by day.
- sealing: poisoning prices and CPI after 2018-12-31 changes nothing.
- reports: the row is the last row of the return table and of every
  withdrawal table; the header count is 22 and the assumption bullet and the
  Notes bullet appear; without the key the rendered decision report is
  identical to today's; the long-run sleeve note reads as above with the id
  and unchanged without it.

### Existing test edits (requires owner approval before implementation)

Only one existing assertion breaks. Every other existing test either uses
fixtures without the new key (`GOOD`, `GOOD_SLEEVE`, hand-built reports),
or checks things the row does not touch (portfolio ids and count, section
titles, table counts, the longrun pin values).

1. `tests/test_decision_cli.py::test_decision_shipped_config_matches_test_fixture`.
   The shipped config now carries `cash_assumption`, the fixture does not,
   so the two `DecisionConfig`s differ in the new field.
   - before: `assert replace(_shipped(), sha256="") == replace(load(tmp_path, GOOD_SLEEVE), sha256="")`
   - after: `assert replace(_shipped(), sha256="") == replace(load(tmp_path, GOOD_TCASH), sha256="")`
   - with a new constant in `tests/decision_helpers.py`: `GOOD_TCASH` =
     `GOOD_SLEEVE` plus the five-line `cash_assumption` block above, with
     its dated comment. `GOOD` and `GOOD_SLEEVE` are not changed, so every
     fixture-driven test (including `tests/test_defensive_sleeve.py`'s
     `small` fixture and its return-row tests) is unchanged. Exact equality
     is kept.

Checked and not affected: `test_decision_shipped_config_loads` (portfolio
ids unchanged), `test_shipped_decision_config_counts_21_portfolios_with_five_a80_rows`
(the row is not a portfolio), the six `return_rows` calls in
`tests/test_defensive_sleeve.py` (the new `cpi` argument is optional and
their fixture has no `cash_assumption`), `test_shipped_longrun_pin_matches_shipped_decision_config`
(passes once the pin is re-pinned), `test_header_sleeve_note_counts_by_products_and_a80_rows`
and `test_longrun_header_sleeve_note_counts_22_rows` (hand-built reports
without the new keys), `test_decision_report_sections_in_order` and the
`test_site_core.py` committed-report tests (no new section), and every
`tests/test_longrun.py` / `tests/test_longrun_run.py` test (`GOOD` has no
key; `monthly_inflation` stays importable from `qrl.longrun`).

Full suite run in the background before the PR.

## Rejected alternatives

- A synthetic price column (a fake "CASH1R" ticker in the price data).
  It would leak into every section: `qrl.stress` classes an unknown ticker as
  equity, so in `dotcom_2000` it would be proxied by SPY; every scenario
  would need a return for it; and fake data would sit beside market prices.
- A fixed nominal yield (e.g. 4% a year). It ignores inflation, which is
  what a retiree's withdrawals follow, and would differ from the long-run
  report's assumption.
- Inflation lagged one more month (month m earns infl_(m-1)), so no day
  earns a figure before its publication. Rejected because it breaks the
  exact +1% real identity against the decision helper's deflator; see
  "Timing, a known simplification" under Computation.
- A 0% / +1% real bracket (two rows). The 0% end is close to what SHY
  already shows, so it adds a row and a comparison for little information.
- Showing the row in every section. Windows and scenarios would need new
  cash judgements (see "Why it is left out" above); it would also add 3
  scenario and 3 year-one rows of pure assumption.

## Not changed

AGENTS.md-protected files (`criteria.yaml`, `combined.yaml`,
`combined_null.yaml`, `paper.yaml`, `factor.yaml`, `engine.py`,
`metrics.py`, `periods.py`, `checks.py`), `profile.yaml`'s `capital_split`,
`portfolio.yaml`'s core, `core_candidates.yaml`, `stress.yaml`, every
existing portfolio, scenario, window, rate and start year in
`decision.yaml`, every `longrun.yaml` key except `decision_sha256`, and
every existing test assertion except the one listed above. No search run,
ledger or trial count is touched.
