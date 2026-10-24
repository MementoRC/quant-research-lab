# Withdrawal rules: fixed against four flexible rules

Status: Spec written 2026-10-23, owner-approved design 2026-10-23. Not yet implemented.
Extends [decision-helper.md](decision-helper.md) (Withdrawals) and
[longrun.md](longrun.md). Order and depletion threshold follow
[withdrawal-edge-cases.md](withdrawal-edge-cases.md).

## Question

The owner withdraws for income. Today every report uses one rule: a fixed
amount raised by CPI each year. How do flexible rules compare with it? A
flexible rule can cut income after a bad year. That should lower the chance of
running out of money. The cost is lower or less steady income. This spec
measures both sides, per portfolio, rule and rate.

## Not a test

Comparison only. It has no pass/fail rule, adds no trials to any search run,
selects nothing and recommends nothing. Research period (2005-2018) only: data
are cut at 2018-12-31; validation (2019-2022) and holdout (2023 on) stay
sealed. The rules are published or textbook rules with fixed parameters, not
fitted to these data.

## Rules

Every rule starts at the same monthly amount: rate x starting value / 12.
A decision is made once a year. In the historical view that is each January,
on the first trading day of January. The long run has no calendar January
(bootstrapped paths start in any month, as in
[withdrawal-edge-cases.md](withdrawal-edge-cases.md) section c), so there the
decision is made every 12 months, at months 13, 25 and so on. The first year
has no decision. In the text below "January" means that decision point.

Let `prev` be last year's monthly amount as actually paid, `cpi` the CPI ratio
over the last year (the same ratio the fixed rule uses), and `V` the portfolio
value at the decision point, before that month's withdrawal.

| id | monthly amount from this January |
|---|---|
| fixed | `prev x cpi`. Same as the existing `monthly_withdrawals`. |
| skip_raise_after_loss | As fixed, but if the portfolio's return over the prior calendar year was negative, `prev` (no CPI raise). The rule applies from the first decision, using the first year's portfolio return (the return before withdrawals). |
| guardrails | Take the fixed amount. Let `q` = 12 x amount / `V`. If `q` > 1.2 x rate, cut the amount by 10%. If `q` < 0.8 x rate, raise it by 10%. Otherwise keep it. |
| pct_of_balance | 12 x amount = rate x `V`. |
| floor_ceiling | Start from rate x `V` / 12, then clamp so the real change against `prev` (after CPI) is within -2.5% and +5%: the amount stays in [`prev x cpi x 0.975`, `prev x cpi x 1.05`]. |

Details.

- "Prior calendar-year return" is the portfolio's own compounded return over
  the 12 months before the decision point, before any withdrawal. In the
  historical view that is the prior calendar year. In the long run it is the
  previous 12-month step of the path.
- The guardrails rule is Guyton-Klinger's capital preservation and
  prosperity rules, with one deviation: there is no 15-year exception (the
  original stops the cut late in life). Its 20% bands and 10% adjustments are
  the published ones. Their inflation rule is replaced by the fixed rule's
  CPI step; the "skip the raise" part is the separate rule above.
- floor_ceiling uses Vanguard's published bands (-2.5% and +5% real). They
  are not fitted.
- All parameters are the same at every rate. A rule never looks ahead and uses
  only values known at the decision point.
- Order within a month and depletion follow withdrawal-edge-cases.md: the
  month's withdrawal is taken first, then the day's (or month's) return. A
  value at or below `DEPLETED` (1e-9 of the starting value, defined in
  `decision_withdraw.py`) after the withdrawal is depleted that month, and
  no return is applied to it. A value at or below `DEPLETED` after the day's
  (or month's) return also depletes the path that month, as in
  `withdrawal_path` and `run_paths`. Once depleted, a path stays at 0 and pays
  nothing. In a month depleted by the withdrawal, the income received is the
  remaining balance, not the full amount. In a month depleted by the return,
  the withdrawal was not short, so the income is the full amount paid. The test that the fixed rule equals
  `withdrawal_path` / `run_paths` compares the value series and the
  depletion month only, not income on the depletion month.
- CPI ratio, historical view: all rules use the ratio `monthly_withdrawals`
  uses, the CPI usable on 1 January over the CPI usable on the previous
  1 January (`usable_cpi`, `decision_withdraw.py`).

## Configuration

New `config/withdrawal_rules.yaml`, pre-registered with this spec and fixed
before any result is seen. Every report records its sha256. After the first
report, change it only by a dated amendment comment.

```yaml
version: 1
decision_sha256: "<sha256 of config/decision.yaml>"
longrun_sha256: "<sha256 of config/longrun.yaml>"
rules:
  fixed: {}
  skip_raise_after_loss: {}
  guardrails: {upper: 1.2, lower: 0.8, cut: 0.10, raise: 0.10}
  pct_of_balance: {}
  floor_ceiling: {max_real_cut: 0.025, max_real_raise: 0.05}
income_lines: [0.9, 0.8, 0.7]
portfolios: [A, B, C, D, E, F, G, CASH]
```

Loader (`src/qrl/decision_rules.py`, or a small loader beside it) raises
ValueError on: an unreadable file, any unknown key, any missing key, a
version other than 1, an unknown rule id or a rule with a wrong parameter set,
a parameter outside its range (upper <= 1, lower >= 1, cut or raise outside
(0, 1), bands negative), an empty or duplicated list, an income line outside
(0, 1), a portfolio id that is not a portfolio in `decision.yaml`, and either
hash that does not match the current file.

Read from the existing files, never copied here: withdrawal rates and start
years from `decision.yaml`; seed, n_paths (10,000), block_months (12) and
horizon_years (30) from `longrun.yaml`; the cost per unit of turnover from
`criteria.yaml` (5 bps, unchanged). `decision.yaml` is not edited, so
`longrun.yaml`'s `decision_sha256` pin and every other pin stay valid.

## Computation

New `src/qrl/decision_rules.py`.

- One vectorised January function per rule, on numpy arrays across paths
  (inputs: `prev`, `cpi`, `V`, prior-year return, rate; output: the new
  monthly amount). The scalar case is a length-1 array.
- One path runner, used by both views. It steps through a return series, takes
  the month's withdrawal at the first step of each month, applies the
  decision at each January, applies the step's return, and checks depletion.
  A step is a trading day in the historical view and a calendar month in the
  long run. It records the amount paid in each month.
- Historical view: for each portfolio and start year, daily returns from
  `decision.portfolio_returns` (unchanged, 5 bps), CPI usable on each date as
  in `decision_withdraw.py`. Paths start on the first trading day of January
  of each `start_years` entry and end 2018-12-31.
- Long-run view: the same monthly returns and inflation as `longrun.py`
  (`monthly_returns`, `monthly_inflation`) and the same paths: same seed,
  `block_starts`, `month_indices`, 10,000 paths, 12-month blocks, 30 years.
  The CPI ratio of a year is the product of the path's 12 monthly
  inflations, as in `run_paths`.
- Existing code is untouched: `withdrawal_path`, `monthly_withdrawals`,
  `run_paths` and everything that calls them keep their numbers. The fixed
  rule here is an independent re-implementation that must match them exactly
  (see Tests).

## Measures

Per portfolio x rule x rate:

- Existing: depleted (month, or none), real ending value, lowest value.
- Lowest yearly real income, as a percentage of starting income. Starting
  income is rate x starting value. Yearly real income is the sum of the
  year's payments, each deflated to starting-date money. Historical: a
  calendar year's withdrawals are deflated by the CPI usable on 1 January of
  that year relative to the CPI usable on the start date. Long run: each
  12-month period's payments are deflated by the path's cumulative inflation
  at the start of that period. A depleted path counts 0 for the years after
  depletion; in the depletion year it counts what was received.
- Share of years with real income below 90%, 80% and 70% of starting income
  (`income_lines`). Historical: pooled over all start-year-years, each
  calendar year of each start year's path to 2018-12-31 counting once; a
  depleted year counts as below every line. Long run: the share of paths
  whose real income is ever below each line in any year of the 30; depleted
  paths count as below.
- Total real income received over the whole path, as a percentage of starting
  income.
- Long run also: share of paths depleted by year 30.

Historical figures are given for the first start year (2005) and for the worst
start year by real ending value, as in decision.md, and the share of years
is pooled over all start years. Long-run figures are over the 10,000 paths
(lowest income and total income: median and 5th percentile).

## Report layout

`research/withdrawal_rules.md`, one section per view (historical, long run),
then per rate a table with a row per portfolio x rule, grouped by portfolio,
rules in the config order, `fixed` first. Rows are never sorted by result. The
columns are the Measures above. Portfolios and rates print in config order.
Counts (8 portfolios, 5 rules, 4 rates, 160 rows per view) are computed, not
hard-coded.

## Header and notes

Header lists, one per line and in this format (`tests/test_docs_freshness.py`
checks it):

- `- withdrawal_rules.yaml sha256: \`hex\``
- `- decision.yaml sha256: \`hex\``
- `- longrun.yaml sha256: \`hex\``

Plus: data end 2018-12-31; the long-run seed, path count, block length and
horizon; the cost in bps. Notes state, in plain words:

- this is a comparison and recommends nothing;
- the rules and their parameters, with the guardrails deviation (no 15-year
  exception) and that the bands are published, not fitted;
- the long-run decision point is every 12 months, not January;
- income is real, a depleted path counts 0;
- the historical view has 10 overlapping start years, so it is 10 related
  paths, not 10 independent tests;
- the withdrawal is taken proportionally from all holdings at no extra cost,
  as in the decision helper.

## Outputs

- `src/qrl/decision_rules.py` (rules, runner, loader, both views).
- `src/qrl/withdrawal_rules_report.py` (renders; no IO).
- `scripts/withdrawal_rules.py` (IO only: read configs, data and CPI; write
  the report).
- pixi task `withdrawal-rules`.
- `research/withdrawal_rules.md`, added to `regen.SPECS` so `regen` and the
  freshness test cover it.

## Tests

New `tests/test_decision_rules.py`, offline, synthetic series.

- Hand-computed amounts for each rule over a few Januaries, including a
  guardrail cut, a guardrail raise, the floor_ceiling lower clamp and the
  upper clamp, and a skip after a loss and a normal raise after a gain.
- The fixed rule equals `withdrawal_path` (historical, same returns and
  CPI) and `run_paths` (long run, same indices) exactly: same values, same
  depletion month.
- One path through the vectorised code equals the scalar run, for every
  rule.
- Depletion: the 1e-9 threshold, depletion by the withdrawal itself, depletion
  by the return (full income that month), nothing paid afterwards.
- Sealing: changing prices after 2018-12-31 does not change the report.
- Config refusals: each ValueError case above, and both hash mismatches.
- Regen and freshness: the report is in `regen.SPECS`; the header hash lines
  match the files.

## Rejected alternatives

- Rewriting the existing withdrawal code to be rule-based: it could move
  published numbers that `shock.py` and the true-cash reports use.
- Separate implementations in each report: they would drift apart. One
  runner serves both views.
- Adding the rules to `decision.yaml`: it would force re-pins of
  `longrun.yaml` and every pin that follows.
- All 27 portfolios: 27 x 5 x 4 rows per view is unreadable. Cores A-G and
  CASH are the owner's comparison set.

## Not changed

AGENTS.md-protected files (`criteria.yaml`, `combined.yaml`,
`combined_null.yaml`, `paper.yaml`, `factor.yaml`, `engine.py`, `metrics.py`,
`periods.py`, `checks.py`), `decision.yaml`, `longrun.yaml`, `profile.yaml`,
`portfolio.yaml`, `withdrawal_path`, `monthly_withdrawals`, `run_paths`, every
existing test, every existing report number. Existing reports and their
generators are not changed. No search run, ledger or trial
count is touched.
