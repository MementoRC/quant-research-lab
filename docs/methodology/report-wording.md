# Report wording: cost, drawdown, true cash, start years, PLAN summary, proxied note

Status: spec written 2026-10-13; owner decisions taken 2026-10-13 (listed at
the end). Awaiting implementation.
Source: the read-only audit of 2026-10-12 (workflow wf_78e2e1c3-596),
findings 3, 4, 5, 6, 7 and 14, all rated low. Each was re-checked against
HEAD 805daae (after PR #58) and still holds. Two corrections to the audit
are noted under 3 and 7. No other audit finding is in scope here.

## Problem

3. **A cost difference that does not exist.** The engine charges turnover
   target to target (`src/qrl/engine.py:84-85`, `executed - overnight`) and
   never charges drift, so rebalancing a constant mix is free. TCASH rows
   and their SHY pairs therefore pay the same cost: none for the
   rebalancing. Yet the reports say each SHY pair "pays 5 bps per unit of
   turnover on its rebalancing, a small difference in the assumption rows'
   favour":
   - `research/decision.md:12`, from `src/qrl/decision_report.py:84-88`
     (several assumption rows) and `:131-132` (one row);
   - `research/longrun.md:34`, from `src/qrl/longrun_report.py:71-74` and
     `:91-93`;
   - `docs/methodology/true-cash-sleeve.md:161-164, 274-275, 304-305` and
     `docs/methodology/true-cash-all-cores.md:132-133`. (The audit says
     "three specs"; only these two files carry the claim, the first in
     three places.)

   The flip side is not disclosed either: because drift is never charged,
   periodic rebalancing costs are slightly understated for every blend.
   `engine.py` is locked, so the engine stays as it is.

4. **Two drawdown definitions under one name.** `qrl.metrics.drawdown`
   (`src/qrl/metrics.py:12-14`) does not count the starting value as a
   peak. `decision_withdraw.py:123` and `stress.py:109-114` do, on purpose:
   `tests/test_stress.py:146` (`test_window_drawdown_counts_first_day_loss`)
   pins that a -10% first day is a 10% loss. In `research/decision.md` the
   research-period return table (`:77`, "Max drawdown") uses the first
   rule and the withdrawal and window tables (`:374` ff., `:116`) the
   second, under the same name and with no note. For A the gap is 31.17%
   vs 32.21% on the same returns (audit), about 1 point.

5. **True cash can lose money in nominal terms, and nothing says so.**
   `src/qrl/true_cash.py:44` grows the cash leg by unadjusted CPI
   (CPIAUCNS) plus 1% real, with no floor. In deflation months it falls:
   40 of 168 months, about -3% from 2008-09 to 2009-03 (audit). That is
   the approved design, but `research/longrun.md:33-34`,
   `research/decision.md:12` and both true-cash specs describe it only as
   "inflation plus 1.0% a year". A reader assumes cash never falls, and
   the crash windows quietly lean against true cash.

6. **"Worst start year" compares unequal horizons.** `src/qrl/decision.py:285-292`
   takes the minimum real ending value over start years 2005-2014, but
   every path ends 2018-12-31 (`decision.md:370`), so a 2005 start runs
   14 years and a 2014 start 5. The column ("worst start year (real ending
   value)", `decision_report.py:404`, cell at `:415`) shows the year and
   value but not the horizon. At 2% the worst year for A and B is 2014,
   the shortest path: the column mostly finds short paths, not bad
   sequences of returns.

7. **The PLAN.md summary leaves out where true cash wins.** `PLAN.md:44-47`
   (local, untracked) says the 20% cash leg "cuts max drawdown by 3-10
   points for 0.7-1.1 points of CAGR" and that "every 80/20 row trails its
   100% core on 4% withdrawals and on long-run value at year 30". The
   reports say otherwise in two places:
   - Drawdown cut, core minus 80/20 row (`decision.md:79-112`):
     X80-CASH20 3.0-8.2 points, X80-TCASH20 3.4-7.6. Never 10.
   - Money ran out by year 30 at 4% (`longrun.md:124-130, 152-158`),
     core vs X80-TCASH20: A 14.8 vs 12.3, B 9.5 vs 7.8, C 13.1 vs 12.1,
     D 5.0 vs 4.5, E 3.3 vs 2.9, F 1.8 vs 1.6, G 0.6 vs 0.6. True cash
     runs out less often for A-F and ties on G. (The audit says "every
     row"; G is a tie.) Typical real value at year 30 is lower for every
     cash row (X80-CASH20, X80-TCASH20), but not for the A80-TLT20 and A80-RSP20 sleeve rows, so that half of the sentence is right only for the cash rows.

   For an owner who needs income, depletion is the figure that matters
   most, and the summary omits it.

14. **A hand-written "mostly proxied" list.** `_mostly_proxied`
    (`src/qrl/decision_report.py:225-236`) returns the fixed string
    "G, G-EW, G-CASH and A-CASH" when there are 0 or 1 assumption rows,
    or when the computed list is empty. Before PR #58 it contradicted its
    own table in every report. `tests/test_defensive_sleeve.py:250` pins
    the fixed text, so the bug would come back silently the next time a
    report has one or no assumption rows. `_switching_label` (`:217-222`)
    has the same shape ("A, B, C, F and blends holding A" when not
    `_multi`); the audit did not flag it, and it is fixed here too.

## Not a test

Report generators, report text and specs only. No strategy, criteria,
period or ledger rule changes, and no locked file is edited (`engine.py`,
`metrics.py`, `periods.py`, `checks.py`, the locked configs). Two kinds of
figure in `research/decision.md` do change, by owner decision: the return
table's max drawdown (one rule, below) and a new equal-horizon worst case.

## Design

One rule for every new sentence: **a number in report text is computed by
the generator from the same data as the tables, never typed in.** Finding
14 is what a typed-in list does once the data moves.
### 3. Cost sentence

- Replace the claim in all four generator branches with:
  "The cash leg and the daily return to 80/20 pay no trading cost, and
  neither do their SHY pairs: the engine charges only target-to-target
  turnover, so rebalancing a constant mix is free in both rows."
- Add one line to the Notes of `decision.md` and `longrun.md`:
  "The engine never charges for drift, so the cost of real periodic
  rebalancing is slightly understated for every blend."
- Specs are corrected in place: the wrong sentences in
  `true-cash-sleeve.md` and `true-cash-all-cores.md` are replaced with the
  sentence above, and each status line gains "Revised 2026-10-13 (cost
  and true-cash wording): see report-wording.md".

### 4. One drawdown rule in the decision report: from the start

- Every drawdown in `research/decision.md` counts the starting value as a
  peak, so it measures loss from the money put in. The withdrawal and
  window tables already do (`decision_withdraw.py:123`,
  `stress.window_drawdown`); they and their tests stay as they are.
- The research-period return table switches: its "Max drawdown" is
  computed from the same daily returns with `stress.window_drawdown`
  (start counts as a peak) instead of the `qrl.metrics` value read at
  `decision.py:375`. `metrics.py` is not touched. For A the figure goes
  from 31.2% to 32.2%; the drawdown-cut figures in finding 7 are
  recomputed from the new values.
- Headers say "max drawdown (from start)" in every decision table. One
  Notes line: "Drawdowns here count the starting value as a peak. The
  criteria and the research dashboard use `qrl.metrics`, which does not,
  so their figures can be lower by up to about a point."
- `core_compare.md`, `overlay.md`, `rsp_sleeve.md` and the dashboard keep
  `qrl.metrics`, because there the figure is the criteria measure (the
  35% max-drawdown limit is checked with it). Their drawdown headers gain
  "(criteria rule)" so the difference is visible.

### 5. True-cash disclosure

- Wherever the true-cash leg is described (`longrun_report.py:144`
  `CASH_ASSUMPTION`, `_assumption_note` / `_multi_assumption_note`, and
  the matching `decision_report.py` branches), add:
  "It follows unadjusted CPI, so it loses money in deflation months:
  {n} of {N} months here, worst {d}% from {start} to {end}. A 0% floor
  would make true cash look better in the crash windows."
- `n`, `N`, `d`, `start` and `end` are computed from the cash leg's own
  series by a new pure helper in `qrl.true_cash`
  (`nominal_loss_stats(series)`), not typed.
- Both true-cash specs get the same sentence, without figures, in place.

### 6. Start years: horizon shown, and an equal-horizon worst case

- The existing column stays, relabelled "worst start year to
  {end} (real ending value; horizons differ)", end date from the data,
  and each cell shows its horizon: `2014, 5 y (138.1%)`.
- New column "worst 5-year start (real value after 5 years)". For each
  start year 2005-2014 the path is cut at 60 months (`withdrawal_path` on
  the first five years of returns, same monthly withdrawals) and
  `path_metrics` gives its real value. The column shows the worst start
  year and that value. Five years is the longest horizon every start
  year allows before the 2018-12-31 end; the generator derives it as
  `end year - last start year + 1` rather than typing 5.
- `decision.py` adds `worst5_year` and `worst5_end_real` to each row
  beside `worst_year` / `worst_end_real`.
- `decision-helper.md:122-131` is edited in place to describe both
  columns.

### 7. PLAN.md summary

PLAN.md is local and untracked, so this is a hand edit outside git, done
after the reports are regenerated. The replacement for `:44-47`, every
figure read from the regenerated reports at edit time:

"For every core, a 20% cash leg cuts max drawdown by {s1}-{s2} points
(SHY) or {t1}-{t2} (true cash) for {a}-{b} points of CAGR against the same
core. True cash beats SHY by about 0.2 points of CAGR. At 4% withdrawals,
X80-TCASH20 runs out of money by year 30 less often than its 100% core
for A-F (A: 12.3% vs 14.8%) and ties on G (0.6%), but every X80-CASH20 and X80-TCASH20 row
ends year 30 with a lower typical real value than its core (the A80 bond and RSP sleeve rows do not: A80-TLT20 181.0% and A80-RSP20 200.4% against A's 156.4% at 4%). Lowest drawdown of any
core-based row: G80-TCASH20, {g}%."

The drawdown figures change with section 4 (today 3.0-8.2 and 3.4-7.6).
Measured against each row's own core in the regenerated report, the CAGR given up is 0.7-1.1 points for the SHY rows (so PLAN.md's figure was right for them) and 0.5-0.9 for the true-cash rows; true cash beats SHY by 0.2 points for every core.

### 14. Computed lists only

- `_mostly_proxied` always computes the list from the `dotcom_2000`
  window rows (`indicative and not unavailable`), whatever the number of
  assumption rows. If the list is empty, the sentence is left out; there
  is no fallback string.
- `_switching_label` likewise computes from `report["portfolios"]`
  (states > 1) in every case, and leaves the sentence out when the list
  is empty.

## Tests

The owner approved (2026-10-13) changing the existing assertions that pin
wrong text. Each is **replaced by an assertion of the correct text**: same
test, same strength, nothing deleted.

- `tests/test_true_cash.py:439-441, 555-556`: assert the new cost sentence
  and that "pays 5 bps" is absent.
- `tests/test_true_cash_all_cores.py:367-368`: same. `:378` ("each row
  would equal its SHY pair there") is still true and stays.
- `tests/test_defensive_sleeve.py:250`: the hand report has no
  `dotcom_2000` rows, so the sentence is left out and the assertion
  becomes `"mostly proxied" not in md`.
- `tests/test_stress.py:146-154` and the drawdown tests in
  `tests/test_decision_withdraw.py` are untouched: the from-start rule
  they pin is the one kept.
- Any existing test that pins the "worst start year (real ending value)"
  header or the old cell format is updated to the new header and cell
  the same way (new text asserted, nothing removed).

New tests, all with synthetic data:

1. Single-row and multi-row reports: no "pays 5 bps" in either
   generator's output; the drift note is present.
2. A return series whose first day is a loss: the decision return table's
   max drawdown counts it (equals `stress.window_drawdown`), and differs
   from `qrl.metrics`' value.
3. Every drawdown header in `decision.md` says "(from start)"; the
   core-compare, overlay and rsp-sleeve headers say "(criteria rule)".
4. `nominal_loss_stats` on a synthetic cash series with three negative
   months gives `n == 3` and the right worst run; the disclosure sentence
   carries those figures.
5. A cash series with no negative month: the sentence still states the
   design and gives `0 of N months`.
6. Withdrawal paths that all end on one date: each old-column cell shows
   its horizon in years, and the header names the end date.
7. Equal-horizon worst case: with synthetic paths where the longest path
   has the lowest 5-year value but not the lowest full-length value,
   `worst5_year` picks it, and every path is cut at the same length.
8. The horizon is derived from the data: ending the paths a year later
   gives 6-year paths.
9. `_mostly_proxied` with one assumption row and flagged `dotcom_2000`
   rows returns exactly the flagged portfolios; with no flagged rows the
   sentence is absent.
10. The same two cases for `_switching_label`.

## Effect on the reports

- `pixi run decision` and `pixi run longrun` regenerate `research/decision.md`
  and `research/longrun.md`. In `decision.md` the return-table drawdowns
  rise by up to about a point, a 5-year worst-case column appears, and
  the notes change as above. `longrun.md` changes in text only.
- `core_compare.md`, `overlay.md` and `rsp_sleeve.md` change in their
  drawdown headers only.
- The dashboard picks up any of this it shows on the next Pages build.
- The two true-cash specs and `decision-helper.md` are corrected in
  place; PLAN.md is edited by hand.

## Owner decisions (2026-10-13)

1. **Pinned tests:** approved, replace wrong-text assertions with the
   correct text.
2. **Drawdown:** one rule in the decision report, counting from the start
   (loss from the money put in). The criteria measure stays `qrl.metrics`
   and is labelled where it is shown. (Chosen over moving the withdrawal
   and stress tables to `qrl.metrics`, which would drop first-day losses
   and read crash windows lower.)
3. **Start year:** add an equal-horizon worst case, keeping the existing
   column with its horizon shown.
4. **Specs:** edit in place, with a revision note on the status line.
5. **`_switching_label`:** fixed with finding 14.

## Out of scope

Every other audit finding (deflated-Sharpe counting, `paper.yaml` pin,
docs drift). Changing the engine to charge drift. Changing either
drawdown definition in `metrics.py`, or the drawdown used by the criteria,
the research reports or the dashboard.
