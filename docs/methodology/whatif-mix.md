# What-if mix: your own blend of the report's portfolios

Status: spec written 2026-10-17; design approved 2026-10-16; written spec
owner-approved 2026-10-17. Awaiting implementation.
(Owner decisions are listed at the end.)
Related: [decision-helper.md](decision-helper.md), "Delivery" item 3 (the
what-if panel). This is part 1 of 2: build-your-own mix. Part 2 (your own
shock) is a separate, later spec.

Rule for the whole spec: **no new maths and no locked file changes**
(`config/criteria.yaml`, `combined.yaml`, `combined_null.yaml`, `paper.yaml`,
`factor.yaml`, `src/qrl/engine.py`, `metrics.py`, `periods.py`, `checks.py`).
`config/decision.yaml` is read, never edited.

## Question

What does a mix of the report's portfolios, chosen by the owner, look like
under the decision report's own tables?

## Input

```
pixi run whatif --mix "G=0.5,A=0.3,TCASH=0.2" [--rate R]
```

The pixi task `whatif = "python scripts/whatif.py"` is added to `pixi.toml`
beside `decision` (`pixi.toml:24`).

Ingredients are names, each with a share:

- Any portfolio id in `config/decision.yaml` after loading, as
  `load_decision_config` returns them (`decision_config.py:332`):
  - A-G, from `config/core_candidates.yaml`.
  - The statics (`decision.yaml:19-25`): CASH, G-EW, IEF, TLT, RSP, BONDS.
  - The existing blends (`decision.yaml:29-43`): AG, G-CASH, A-CASH,
    A80-CASH20, A80-IEF20, A80-TLT20, A80-BONDS20, A80-RSP20, B80-CASH20,
    C80-CASH20, D80-CASH20, E80-CASH20, F80-CASH20, G80-CASH20.
  - A blend ingredient is flattened into its parts, the way `_blend` does
    it (`decision_config.py:173-175`): each part's share is multiplied by the
    ingredient's share. So `AG=1.0` is the same as `A=0.5,G=0.5`.
- `TCASH`: true cash, earning each month's CPI inflation plus the real yield
  in `decision.yaml`. It is the cash leg of the cash-assumption rows
  (`cash_leg_returns`, `true_cash.py:32`). The yield is read from the
  `cash_assumptions` rows (`decision.yaml:56-70`, all +1%), not typed on the
  command line.

Rules:

- Every share is a finite number >= 0.
- The shares sum to 1 within 1e-9 (the loader's own `_EPS`,
  `decision_config.py:30`). This input check, made by whatif, is the
  authoritative one. The shares are then renormalised exactly (see
  Construction) before the `Portfolio` is built, so `_check_full`
  (`decision_config.py:185-189`) passes.
- No name appears twice. An unknown name is refused. A name with share 0 is
  checked like the others and then dropped.
- `--rate R` is optional: one extra annual withdrawal rate, in (0, 0.10]. It
  is added to the report's rates (`cfg.rates`, `decision.yaml:98`). If it
  equals a rate already there, nothing is added.

## Construction

**No new maths.** The mix is built by the same code that builds the report.

- **Non-cash ingredients** become one `Portfolio` with id `MIX`, built exactly
  as `_blend` builds blends: shares scaled, parts concatenated
  (`decision_config.py:173-176`). Ingredients are taken in the order given
  (so `A=0.8,CASH=0.2` has parts A then CASH, as `A80-CASH20` does, and float
  sums depend on part order). After flattening, parts with the same candidate
  id are merged by summing their shares, keeping first-appearance order.
  Without this, `A=0.3,AG=0.4` would hold A twice and `portfolio_states`
  would build impossible states pairing A risk-on with A risk-off. Its daily target weights come from
  `portfolio_weights` (`decision.py:47`): the share-weighted sum of the
  parts' weights, rebalanced daily, costs on turnover from `criteria.yaml`
  (`portfolio_returns`, `decision.py:191`). A switching part (A, B, C, F)
  keeps switching inside the mix, so two switching ingredients give four
  states (`portfolio_states`, `decision_config.py:99`).
- **If TCASH > 0:** the non-cash part is renormalised to 100% and is `MIX`:
  each non-cash share is divided by the sum of the non-cash shares (exactly
  1.0 for `A=0.8,TCASH=0.2`). With TCASH = 0 the same division makes the
  shares sum to exactly 1.
  One `CashAssumption` row is added (`decision_config.py:66`): id
  `MIX-TCASH`, base `MIX`, `cash_share` = the TCASH share, `real_yield` from
  `decision.yaml`, no `pair`. This is the same mechanism as `A80-TCASH20`:
  `_row_returns` mixes the base's `portfolio_returns` with
  `cash_leg_returns` through `mix_returns` (`decision.py:245-260`,
  `true_cash.py:79`). The cash leg and the daily rebalancing to the split
  pay no trading cost. Like those rows it appears in the returns and
  withdrawals tables only, never in windows, scenarios or year one.
- **TCASH = 1:** allowed. There is no non-cash part, so there is no `MIX`
  portfolio. The row is `MIX-TCASH` with base `CASH` (irrelevant at 100%
  cash) and `cash_share` 1. The loader still refuses `cash_share` 1 in
  `decision.yaml` (`decision_config.py:233`, unchanged): whatif builds the
  `CashAssumption` directly, after its own checks, so this holds for whatif
  only.
- **The config.** An in-memory `DecisionConfig` built with
  `dataclasses.replace(cfg, ...)` holds the portfolios A, CASH and MIX (in
  that order; MIX only if there is a non-cash part) and the cash row, if any.
  A and CASH are there for reference. A also makes the "CAGR given up vs A"
  column work (`return_rows`, `decision.py:396`). The rates are the report's
  plus `--rate`. Windows, scenarios, start years, thresholds and hashes are
  kept from the loaded config. Then the existing `run_decision`
  (`decision.py:445`) runs on it.

**Checks.** The mix bypasses the loader. For the portfolio, whatif reuses the
loader's own functions, not copies. They exist but are private:
`_blend`, `_check_full` (100% of capital in every state,
`decision_config.py:185`). Every existing private name keeps its name and
behaviour; the implementation adds public names that point to the same
objects, and no existing import changes (for example
`tests/test_true_cash_all_cores.py:411` imports `_window_section`). The
loader (`_ID`, `_entry`, `_cash_row`) is not changed.

The cash row does not go through `_cash_row`. whatif builds the
`CashAssumption` directly and applies the `_cash_row` checks itself
(`decision_config.py:224-239`, without the `cash_share` (0,1) and id-pattern
rules): the base is a portfolio id in the in-memory config, the row id
`MIX-TCASH` is not a portfolio id, and the real yield is finite and within
`MAX_REAL_YIELD` (`:45`).

`real_yield` comes from the first `cash_assumptions` row in `decision.yaml`.
whatif refuses if the rows' yields differ, as `_cash_nominal_loss` does
(`decision.py:495-496`).

## Output

Per-portfolio sections of the decision report, for `MIX` (and `MIX-TCASH`
where it applies), with A and CASH for reference:

- states and weights (`_portfolio_section`, `decision_report.py:298`; MIX and
  the references only, the cash row is not a portfolio)
- research-period returns (`_return_section`, `:311`; includes `MIX-TCASH`)
- historical windows (`_window_section`, `:346`)
- judgement-based scenarios (`_scenario_section`, `:382`)
- withdrawals (`_withdrawal_section`, `:415`; includes `MIX-TCASH`)
- year-one scenario hit (`_year_one_section`, `:462`)

The file is always `ROOT/reports/whatif-<slug>.md`; there is no `--out-md`
option. Only `reports/` is created (mkdir). `reports/` is gitignored
(`.gitignore:23`), so the file is private. The output is never written under
`research/` or `site/`. Ids are restricted to `[A-Za-z0-9_-]` (`_ID`,
`decision_config.py:29`), so the slug cannot traverse; whatif still asserts
the resolved path is under `ROOT/reports`.

The slug is the ingredients in input order, joined with `__`, each written
`<id>.<percent>`: the percent to at most 2 decimals, trailing zeros dropped,
`.` written as `p` (33.33 becomes `33p33`). Zero-share ingredients are
dropped before the slug is built, so they do not appear in the filename. Ids cannot contain `.` and none
contains `__`, so the slug is unambiguous. Example:
`whatif-G.50__A.30__TCASH.20.md`. An existing file for the same mix is
overwritten (the same input gives the same content).

The header says the mix came from the command line, not from `decision.yaml`,
and prints the mix (names and shares as given, the renormalised MIX shares, and
the TCASH share). When TCASH > 0 it also says that the `MIX` rows in the
windows, scenarios and year-one tables are the non-cash part at 100%, and that
the full mix appears only as `MIX-TCASH`, in the returns and withdrawals
tables. It also carries what `render_markdown` already prints:
data end, the `decision.yaml`, `core_candidates.yaml` and `stress.yaml` sha256,
and the daily-rebalancing and cost notes.

A short terminal summary is printed: the mix, the output path, and for each of
MIX, MIX-TCASH, A and CASH its research-period CAGR and max drawdown. Only
rows that exist are printed: no MIX row when TCASH=1, no MIX-TCASH row when
TCASH=0. It does
not print the whole report (unlike `scripts/decision.py:73`).

## Data and sealing

- Same `data_end` (2018-12-31, `data_end`, `decision.py:32`) and the same
  functions, which cut every price and CPI frame at that date
  (`stress_rows` `:166`, `withdrawal_rows` `:340-341`, `return_rows` `:389`).
  The cut is inherited, so nothing new can read sealed data.
- Never unseals: no `slice_period(..., "holdout", unseal_holdout=True)`.
- `config/decision.yaml` is read-only. Its sha256 is pinned by
  `longrun.yaml`'s `decision_sha256` (`config/longrun.yaml:16`) and stays
  unchanged.
- Prices and CPI are loaded as `scripts/decision.py:51` and `:59-64` do
  (`refresh=False`, the shared cache), for the tickers of A, CASH and MIX
  plus `EQUITY_PROXY`.

## Refusals

Each is printed as `refused: <reason>` with exit code 1, following
`scripts/decision.py:55`, `:66-68`. Nothing is written.

- `--mix` missing, empty, or an item that is not `NAME=SHARE`
- a share that is not a number, not finite, or negative
- a duplicate name
- an unknown name (the message lists the valid ones)
- shares that do not sum to 1 within 1e-9
- `--rate` not a number or outside (0, 0.10]
- `cash_assumptions` rows in `decision.yaml` with different real yields
- every refusal `run_decision` already makes: a held fund with no price at a
  start date, missing CPI, NaN weights (decision-helper.md "Refusals"), and a
  failed `config/decision.yaml` load

## Tests

New file `tests/test_whatif.py`, using the fake price and macro helpers of
`tests/test_decision_cli.py` (`_fake_ohlcv`, `_fake_macro`). Existing tests
are unchanged.

- Parity: `A=0.8,CASH=0.2` (ingredients in the order A, CASH) gives the same
  returns and withdrawals numbers as the report's `A80-CASH20`.
  `A=0.8,TCASH=0.2` gives the same numbers as `A80-TCASH20` (same inputs).
  The tests compare numbers only, ignoring the row id and label column.
- Two switching portfolios (for example `A=0.5,B=0.5`) give four states.
- Duplicate parts: `A=0.3,AG=0.4` has the same states as the mix of A and G
  alone, and no state pairs A with itself.
- `TCASH=1` works in whatif. A `decision.yaml`-style config with
  `cash_share` 1 is still refused by the loader.
- Sealing: altering prices after 2018-12-31 leaves the output unchanged.
- `config/decision.yaml` bytes (and sha256) are unchanged after a run.
- Output is written only under `ROOT/reports/` (the resolved path is
  asserted), and the slug follows the rule above.
- Each refusal above.
- The pixi task `whatif` exists (as `test_decision_pixi_task`,
  `tests/test_decision_cli.py:106`).
- TCASH = 1 runs and gives only a `MIX-TCASH` row, with no `MIX`.

## Notes for the implementer

Places where the code is stricter than this spec, found while checking it
against the code:

- `_cash_row` refuses `cash_share` 1 (`decision_config.py:233`) and `_entry`
  limits ids to `[A-Za-z0-9_-]` (`:146`). Neither is changed. whatif builds
  the `CashAssumption` directly after its own checks.
- `render_markdown` cannot be reused unchanged. Its header "multiple
  comparisons" line assumes the full report (`decision_report.py:231`), and its
  single-row cash notes name `A80-CASH20` and "the SHY caveat above"
  (`:149-157`, `:178-183`). For `MIX-TCASH` those would be wrong. So whatif
  writes its own header and notes and reuses the section builders listed under
  Output, through new public names that point to the same objects. Implementation
  step: regenerate `research/decision.md` in place and check
  `git diff --exit-code research/decision.md`. Any diff stops the work; restore
  the file with `git checkout research/decision.md` and report.
- `_rates` accepts (0, 1) (`decision_config.py:317`); the (0, 0.10] bound is
  whatif's own, applied to `--rate` only.

## Untouched

- The locked files named in AGENTS.md.
- `config/decision.yaml` and `config/longrun.yaml`, so the `decision_sha256`
  pin stays valid.
- `research/decision.md` (regenerated only to check it is byte-identical) and
  the site.
- Existing tests.

## Out of scope

- Your own shock (part 2).
- A dashboard panel.
- Mixing individual funds.
- Saved named mixes.

## Owner decisions (2026-10-16)

- The mix and the shock are two specs; the mix comes first.
- Ingredients are the report's portfolios, plus true cash.
- A local command first; the dashboard later.
- Output is private.
