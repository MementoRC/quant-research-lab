# Income explorer: a what-if panel on the dashboard

Status: Draft (2026-10-26). Owner approved the design in conversation on 2026-10-26.
Extends [decision-helper.md](decision-helper.md),
[withdrawal-rules.md](withdrawal-rules.md) and
[staged-entry.md](staged-entry.md).

## Goal

An interactive dashboard section for looking up, for one portfolio, withdrawal
rate and choice, what the committed withdrawal-rules and staged-entry reports
say, next to its baseline. It is the "exploratory what-if panel" deferred in
decision-helper.md.

It is a lookup over published results. It computes no new result, selects
nothing and recommends nothing. Public site: research and exploration output,
as the other report sections are.

## Sources

`research/withdrawal_rules.md` and `research/staged_entry.md`, as already
parsed by site_core (`build_withdrawal_rules`, `build_staged_entry`). The data
cutoff is 2018-12-31, taken from the reports' "data:" header bullet. Nothing is
recomputed from prices.

## Modes

Two modes. There is no rule x entry combination; the combined grid stays
deferred, as in staged-entry.md.

1. Withdrawal rule. All money is invested at the start (lump sum).
   - Pick: portfolio (A-G, CASH), rate (2%, 3.3%, 4%, 5%), rule
     (skip_raise_after_loss, guardrails, pct_of_balance, floor_ceiling).
   - Baseline: the fixed rule, same portfolio and rate.
2. Entry speed. Fixed CPI-indexed withdrawal.
   - Pick: portfolio (A-G; the staged report has no CASH), rate, entry
     (6 months, 12 months, 24 months), and cash variant. SHY is waiting cash in
     SHY at actual prices. CPI+1% is waiting cash at inflation + 1% real, an
     assumption.
   - Baseline: lump sum, same portfolio, rate and variant.

## What is shown

Two cards side by side, Historical and Long run, each a small table.

- Rule mode: the rows are all the report's value columns for that view (every
  column after "portfolio" and "rule"), in report order, with the column name
  as the row label: 14 rows for historical, 12 for long run. Worst start year
  is a row with an empty difference. There are three value columns: the chosen
  rule, fixed, and the difference.
- Entry mode: the chosen entry row next to the lump-sum row, for the chosen
  cash variant, with the "SHY: " / "CPI+1%: " prefix dropped from the column
  names. The gap and above-lump figures are the report's own staged-minus-lump
  columns. No difference column is added.
- Every figure is the report's string, unchanged. Each card links to its full
  report.

Defaults: rule mode, portfolio G, 4%, guardrails. A default is a starting
point, not a recommendation; the section note says so.

Section note: "Looks up results already in the withdrawal-rules and
staged-entry reports. A comparison only: it selects nothing and recommends
nothing. Data up to 2018-12-31 only."

Placement: right after the staged-entry section, as
`<section id="explorer-section" hidden>`. Child ids are prefixed `explorer-`.
It stays hidden, like the other report sections, when the block is absent.

Controls: native `<select>` elements, each with a `<label>` (keyboard and
phone friendly, no new library). The cash-variant select shows only in entry
mode, and CASH shows only in rule mode.

## Differences

Rule mode only. Computed in Python at build time, not in the browser.

- A cell is a single percentage if it fully matches `^-?\d+(\.\d+)?%$`. The
  difference is computed only when both the rule cell and the fixed cell
  match.
- Otherwise the difference is "": for example "-", a year like "2014",
  "median (worst, best)" cells, or "0.0%" against "-".
- Total real income cells such as "1400.0%" are single percentages and get a
  difference such as "+157.3 pp". This is intended: they are percentages of
  the starting income.
- The difference is in percentage points, with a sign, rounded like the
  reports (one decimal, never "-0.0"), shown as e.g. "+1.2 pp".
- Every other cell gets an empty difference.

## Data block

`results.json` key `income_explorer`. Built by a new pure function
`build_income_explorer(withdrawal_block, staged_block)` in a new module
`src/qrl/site_explorer.py`. It returns None if either block is None.
`scripts/build_site.py` adds it to the payload next to the existing report
blocks.

Shape:

- `sources`: both report paths.
- `data_end`: "2018-12-31". Each report's "data:" bullet is matched with
  `up to (\d{4}-\d{2}-\d{2})`. Both must match and be equal, else ValueError.
- `portfolios`: one shared `{id: description}` dict covering all 8 ids. Each
  report's "portfolios:" header bullet is one "; "-joined string whose items
  are "ID (description)". withdrawal_rules.md has A-G plus CASH;
  staged_entry.md has A-G. The A-G descriptions must be identical across the
  two reports, else ValueError.
- `rates`: ["2%", "3.3%", "4%", "5%"]. Titles are normalised: 2.0% and 2% map
  to "2%"; 3.3% to "3.3%"; 4.0% and 4% to "4%"; 5.0% and 5% to "5%".
- Expected sections and table titles, matched exactly. Anything else is a
  ValueError.
  - Withdrawal sections: "Historical view: start years 2005 to 2014, each to
    2018-12-31" and "Long-run view: 30-year resampled paths". Table titles:
    "Withdrawal rate 2.0% per year", "Withdrawal rate 3.3% per year",
    "Withdrawal rate 4.0% per year", "Withdrawal rate 5.0% per year".
  - Staged sections: "Historical starts" and "Long run". Table titles:
    "Withdrawal rate 2%", "Withdrawal rate 3.3%", "Withdrawal rate 4%",
    "Withdrawal rate 5%".
  - A view section is found by its exact title. Historical sections are
    matched by exact title, so a change to the start years in a regenerated
    report fails the build on purpose.
- `rule`:
  - `portfolios`: [A..G, CASH].
  - `columns`: `{historical: [...], long_run: [...]}`, excluding "portfolio"
    and "rule".
  - `rows`: `{"<portfolio>|<rate>|<rule>": {historical: [cells], long_run: [cells]}}`.
    The fixed rows are included as rows so the page can show the baseline.
  - `diff`: the same keys, `{historical: [...], long_run: [...]}`.
- `entry`:
  - `portfolios`: [A..G].
  - `variants`: ["SHY", "CPI+1%"].
  - `columns`: `{historical: [...], long_run: [...]}`, excluding "Portfolio"
    and "Entry", per variant with the prefixes removed. The SHY and CPI+1%
    column lists must be equal after stripping, else ValueError.
  - `rows`: `{"<portfolio>|<rate>|<entry>|<variant>": {historical: [...], long_run: [...]}}`.
    The lump-sum rows are included.

Each row's cell list aligns 1:1 with its columns. The size of the block is
measured at build time.

## Failure

Fails loudly. `build_income_explorer` raises ValueError, which fails the site
build and so the Pages deploy, if:

- a table title, rate or column header is not the expected one;
- any portfolio x rate x rule (8x4x5) or portfolio x rate x entry x variant
  (7x4x4x2) combination is missing or duplicated;
- the two reports' data cutoffs differ.

It never guesses or skips. If a key is somehow missing in the browser, the card
shows "No result for this combination".

## Tests

New `tests/test_site_explorer.py`.

- On small hand-made blocks: the shape, rate normalisation, prefix stripping,
  difference maths and rounding including the empty cases and no negative
  zero, and each failure case raising.
- On the committed reports: every combination resolves, the row counts are 160
  rule rows per view and 224 entry rows, and spot checks equal exact cells from
  the report text.

New string checks in the style of `tests/test_site_safety.py`: `index.html`
contains the explorer's "selects nothing and recommends nothing" note and its
data-cutoff wording. Existing tests are not changed.

`pixi run build-site --refresh` shows the block and its size.

## Rejected alternatives

- Parsing the report tables in the browser: fragile, since a layout change
  would silently break it, and it cannot be tested in pytest.
- JSON written by the report scripts: it touches the report writers and their
  regen specs for the same result.
- A mix explorer (blending portfolios in the browser): mixes involving
  switching cores would only be approximate; whatif-mix stays a local command.
- Preset shocks: out of scope here.
- Choosing a rule and an entry speed together: that needs the deferred rule x
  entry grid.

## Out of scope

Any new computation, any change to the two reports or their writers, and the
history-grounded scenarios (a separate spec).

## Open questions

None outstanding. All design questions were answered by the owner on
2026-10-26.
