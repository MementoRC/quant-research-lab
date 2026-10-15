# True cash for every core: 80% core + 20% cash, SHY and +1% real

Status: spec written 2026-10-12, owner-approved design and spec 2026-10-12. Revised 2026-10-14 (report wording): see report-wording.md.
Owner choices
(2026-10-12): every core B-G, each with a SHY pair, 20% share, +1% real.
Extends [true-cash-sleeve.md](true-cash-sleeve.md) and
[defensive-sleeve.md](defensive-sleeve.md). Run 2026-10-12 (branch feature/true-cash-all-cores): results in research/decision.md and research/longrun.md.

## Question

A80-TCASH20 answered the SHY caveat for core A only. The owner wants every
core kept comparable. This spec adds, for each core X in B-G:

- X80-CASH20, a real portfolio: 80% X + 20% CASH (SHY), like A80-CASH20.
- X80-TCASH20, an assumption row: 80% X + 20% cash earning each month's
  inflation plus 1% a year, exactly as A80-TCASH20. It follows unadjusted CPI
  (CPIAUCNS) with no floor, so it loses money in nominal terms in deflation
  months; the reports give the count and the worst decline.

So each of the seven cores gets the same three rows: X, X80-CASH20 and
X80-TCASH20.

## Not a test

As in the true-cash spec: comparison only, no pass/fail rule, no trials added
to any search run, research period (2005-2018) only; validation (2019-2022)
and holdout (2023 on) stay sealed. The X80-CASH20 rows are ordinary
portfolios; the X80-TCASH20 rows are labelled assumptions everywhere.

## Configuration

`config/decision.yaml`, one dated amendment:

```yaml
# Amendment 2026-10-12 (owner-approved design, spec
# docs/methodology/true-cash-all-cores.md): blends B80-CASH20 ... G80-CASH20
# added; cash_assumption replaced by the list cash_assumptions, whose first
# entry is the former A80-TCASH20 row unchanged plus its pair. Existing
# portfolios unchanged; candidates_sha256 unchanged.
```

- `blends:` gains six entries, appended after the existing ones in B-G order,
  same shape as A80-CASH20:
  `- {id: B80-CASH20, label: "80% B + 20% CASH", parts: {B: 0.8, CASH: 0.2}}`
  and likewise C, D, E, F, G.
- The singular `cash_assumption:` key is replaced by `cash_assumptions:`, a
  list of seven mappings in A-G order. Each has the five existing fields plus
  one new field, `pair`:

```yaml
cash_assumptions:
  - {id: A80-TCASH20, label: "80% A + 20% cash at +1% real (assumption)",
     base: A, cash_share: 0.2, real_yield: 0.01, pair: A80-CASH20}
  - {id: B80-TCASH20, label: "80% B + 20% cash at +1% real (assumption)",
     base: B, cash_share: 0.2, real_yield: 0.01, pair: B80-CASH20}
  # ... C, D, E, F, G the same way
```

Loader (`src/qrl/decision_config.py`):

- `DecisionConfig` gets a new last field `cash_assumptions:
  tuple[CashAssumption, ...] = ()`. The existing field `cash_assumption`
  stays and holds the first row (or None), so code and tests that read it
  for a one-row config are unaffected.
- The singular key stays accepted (one mapping, read exactly as today, a
  one-element tuple). Both keys at once is refused. Every existing fixture
  (`GOOD`, `GOOD_SLEEVE`, `GOOD_TCASH`) therefore loads exactly as today.
- `CashAssumption` gets an optional last field `pair: str | None = None`.
- Per entry, the six existing refusals apply. New refusals (ValueError):
  1. the list key is not a non-empty list;
  2. two entries share an id, or share a base;
  3. a `pair` that is not a blend whose parts are exactly
     `{base: 1 - cash_share, CASH: cash_share}`.
- Bookkeeping: decision.yaml's sha256 changes; `config/longrun.yaml`'s
  `decision_sha256` is re-pinned with a dated comment, no other key changed.

## Consistency with the long-run report

`check_cash_assumption(lcfg, dcfg)` checks every row: each `real_yield` must
equal `longrun.yaml`'s `cash_real_yield` exactly. Same call sites as today
(`scripts/longrun.py` before any data, first statement of `run_longrun`).

## Computation

Unchanged per row. `assumption_returns` is applied once per entry, with that
entry's base; the cash leg (`qrl.true_cash`, strict CPI check, exact +1% real
against the decision helper's deflator) is shared. `engine.py`, `metrics.py`,
`periods.py`, `checks.py` imported, never edited. Data cut at 2018-12-31.

The X80-CASH20 blends need no new code: they run through the existing blend
path, pay 5 bps per unit of turnover, and enter every section (portfolios,
historical windows, scenarios, year-one, returns, withdrawals) like
A80-CASH20.

## Where the rows are shown, and in what order

- Portfolios: the six new blends after the existing rows, in B-G order, in
  every table that lists portfolios.
- Assumption rows: after all portfolio rows, in A-G order, in the return
  table, every withdrawal table and every long-run rate table, as A80-TCASH20
  is today. Not in windows, scenarios or year-one (reasons unchanged from the
  true-cash spec).
- Counts with the shipped config: 27 portfolios (21 + 6) and 7 assumption
  rows, 34 comparisons. Header line: "7 in the core comparison, 34 here (A-G
  again plus 27 new)". All counts computed, never hard-coded.

## Historical windows: what the new blends inherit

- dotcom_2000: SHY did not trade, so each X80-CASH20's SHY leg is cash at 0%
  (existing proxy rule). D80-CASH20, E80-CASH20 and G80-CASH20 have more than
  0.25 of capital proxied (0.32, 0.32, 0.60) and are flagged mostly proxied,
  indicative only, by the existing `proxied_threshold` rule.
- Switching blends: B80-CASH20, C80-CASH20 and F80-CASH20 hold switching cores
  and get frozen-by-state and replay cells like A80-CASH20.
- The report texts that name portfolios by hand are generated from the config
  instead, so the new rows are named: decision_report.py's "Switching
  portfolios (A, B, C, F and blends holding A)" (a blend holding any
  switching core), "G, G-EW, G-CASH and A-CASH are mostly proxied" (the
  flagged rows), and "RSP, GLD and bonds are proxied". `DOTCOM_SLEEVE` (the
  five A80 rows being equal in dotcom) is unchanged.

## Header and notes

Decision report. Every text below is unchanged byte for byte when the config
has at most one assumption row and no `pair` (fixtures, hand-built reports).
With more than one row:

- One header bullet replaces the single-row bullet: "- A80-TCASH20 to
  G80-TCASH20 are 7 assumption rows, not funds: for each core, 20.0% cash
  earning each month's inflation plus 1.0% a year, the long-run report's CASH
  +1% real assumption, shown next to that core's SHY pair (A80-CASH20 to
  G80-CASH20) to answer the SHY caveat. They are comparisons 28-34 but not
  among the 27 portfolios. Both they and each SHY pair pay no
  trading cost for the rebalancing, because the engine charges only
  target-to-target turnover, so rebalancing a constant mix is free in both
  rows; drift is never charged, so real periodic rebalancing costs are
  slightly understated."
- The Notes scope bullet names the pairs generally ("would equal its SHY
  pair in dotcom_2000") instead of A80-CASH20.
- A note for G: G already holds 25% SHY, so G80-CASH20 holds 40% SHY in all
  and G80-TCASH20 swaps only the added 20%.
- `_sleeve_note` keeps "only the 5 A80 rows answer the defensive-sleeve
  question" and adds: "the 7 X80-CASH20 rows and the 7 assumption rows answer
  the true-cash question (docs/methodology/true-cash-all-cores.md)".

Long-run report. Report dict gains `cash_assumptions`: a list of
`{id, base, share, pair}`. The scalar keys `cash_assumption_id/base/share`
keep today's meaning when there is exactly one row and are None otherwise.
`_sleeve_note` leaves every assumption id out of the A80 count; with the
shipped config it reads: "- 35 rows per withdrawal rate, including the CASH
+1% real (assumption) row, 7 assumption rows (A80-TCASH20 to G80-TCASH20) and
4 by-product rows (IEF, TLT, RSP, BONDS); only the 5 A80 rows answer the
defensive-sleeve question; the 7 X80-CASH20 rows and the 7 assumption rows
answer the true-cash question" (counts computed). The per-row assumption
note becomes one note covering all rows, naming each row's pair from `pair`.

## Outputs

Regenerate `research/decision.md` (`pixi run decision`) and
`research/longrun.md` (`pixi run longrun`). No new section titles. PR
description: per core, X vs X80-CASH20 vs X80-TCASH20 on CAGR, max drawdown,
worst-start 4% withdrawal and long-run 4% typical real value at year 30.

## Tests

New file `tests/test_true_cash_all_cores.py`, offline, with a new fixture
`GOOD_TCASH_ALL` in `tests/decision_helpers.py` (= `GOOD_SLEEVE` plus the six
blends and the `cash_assumptions` list). Covers: the loader (list and
singular forms, both-keys refusal, the three new refusals, `pair` check);
each row equals (1 - s) x that base's returns + s x cash leg; every row's
yield checked against longrun; row order in every table; header count 34 and
the multi-row bullet; long-run sleeve note; byte-identical output for a
one-row config; sealing (poisoned data after 2018-12-31 changes nothing).

### Existing test edits (owner-approved 2026-10-12)

Exact-equality tripwires on the shipped config that must change; no
assertion is weakened, each is replaced by its new exact value:

1. `tests/test_defensive_sleeve.py:79` `len(ids) == 21` -> 27.
2. `tests/test_decision_cli.py:34-50` the shipped ordered id list gains the
   six blends at the end.
3. `tests/test_decision_cli.py:97` compares the shipped config with
   `GOOD_TCASH_ALL` instead of `GOOD_TCASH`.
4. `tests/test_true_cash.py:83-88` (shipped config): `cfg.cash_assumption ==
   TCASH` stays true only if `TCASH` gains `pair="A80-CASH20"`; the edit is
   `cfg.cash_assumptions[0] == replace(TCASH, pair="A80-CASH20")` and
   `len(ids) == 27`.

Any other existing assertion found to break during implementation stops the
work for owner approval. Fixture-driven tests (singular key, no `pair`) are
expected unchanged.

## Rejected alternatives

- Only the true-cash rows, no SHY pairs: the SHY-vs-true-cash gap could only
  be read for A (owner chose pairs).
- Keeping the singular key and adding a second list key for B-G: two places
  for the same kind of row.
- Placing each assumption row next to its pair: assumption rows would sit
  among real portfolios; keeping them last keeps "last rows are assumptions".

## Not changed

AGENTS.md-protected files, `profile.yaml`'s `capital_split`,
`portfolio.yaml`'s core, `core_candidates.yaml`, `stress.yaml`, every existing
portfolio, scenario, window, rate and start year, every `longrun.yaml` key
except `decision_sha256`, `qrl.true_cash`'s cash leg, and every existing test
assertion except the four above. No search run, ledger or trial count is
touched.
