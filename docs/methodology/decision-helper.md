# Decision helper: portfolios, scenarios and withdrawals

Status: implemented 2026-10-06 (`pixi run decision`, writes
`research/decision.md`). Owner-approved design.

## Purpose

The research pipeline is complete. This report supports a different
question: how to deploy savings while withdrawing for income. This
report is a decision aid: it compares a fixed set of portfolios under
historical crashes, judgement-based shocks and inflation-indexed
withdrawals. It selects nothing and recommends nothing. It replaces the
earlier idea of a PLAN.md amendment to switch the core.

## Data rules

- Only data up to 2018-12-31 (the end of the research period) is read.
  Validation (2019-2022) and holdout (2023 on) stay sealed. A single
  unseal for the owner's eventual shortlist is a separate, later decision.
- Every price and macro frame is cut at 2018-12-31 (as `core_compare`
  does), and the config loader refuses any window, start year or
  scenario date past 2018-12-31.
- Data before 2005 is not sealed and may be used (dot-com window; later,
  history-grounded scenarios).

## Portfolios

Every portfolio is 100% of capital (no 80/20 core/sleeve split; the sleeve
is empty). Weights are rebalanced daily with the engine's normal costs, as
in the core comparison; real rebalancing would be less frequent, so blends
look slightly smoother than practice. The report says so.

- **A-G**: read from `config/core_candidates.yaml` unchanged. Its sha256 is
  checked and recorded; the file is never edited (it is bound to
  `core_shortlist.yaml` and the core-reveal record).
- New, defined in `config/decision.yaml`:

| id | definition |
|---|---|
| CASH | 100% SHY |
| G-EW | 25% each RSP / TLT / GLD / SHY |
| AG | 1/2 A + 1/2 G |
| G-CASH | 1/2 G + 1/2 CASH |
| A-CASH | 1/2 A + 1/2 CASH |

A blend's daily target weights are the weighted sum of its components'
daily target weights; a switching component (A) keeps switching inside the
blend.

The report states the cumulative number of portfolios compared (7 in the
core comparison, 12 here) as a multiple-comparison disclosure.

## Scenarios

### Historical windows

`dotcom_2000` (frozen mode only; `config/stress.yaml` sets `replay: false`)
and `gfc_2008` (replay and frozen) from `config/stress.yaml`, read and not
edited. In `dotcom_2000`, which starts before the 2002 inception of SHY,
IEF and TLT and before GLD (2004) and RSP (2003), the stress module's
existing rule applies: unpriced equity is proxied by SPY, and unpriced bond
and gold funds by cash. This heavily distorts the window: CASH is entirely
cash there (0% loss by construction), and G, G-EW, G-CASH and A-CASH are
mostly proxied. The report shows each portfolio's proxied share per class
for every frozen cell (from the existing `proxied_share` detail), and marks
any cell more than 25% proxied as "mostly proxied, indicative only".

### Judgement-based shocks (v1)

Each scenario gives a one-year total return for EVERY fund held by any
portfolio (SPY, QQQ, RSP, SHY, IEF, TLT, GLD) plus one-year inflation. The
loader refuses a scenario missing any held fund (no default asset class).
Each shock must be > -1. Losses are reported nominal and real:
real = (1 + nominal) / (1 + inflation) - 1.

Switching portfolios (A, B, C, F, AG, A-CASH) are evaluated in both states
(risk-on and risk-off weights) because their current state would require
sealed data; the report shows both and the worse.

All scenarios are labelled "judgement-based, v1".

| scenario | SPY | QQQ | RSP | SHY | IEF | TLT | GLD | inflation |
|---|---|---|---|---|---|---|---|---|
| treasury_dollar_crisis | -25% | -30% | -22% | +1% | -12% | -30% | +25% | 8% |
| trade_oil_shock | -20% | -25% | -18% | +2% | -6% | -15% | +10% | 7% |
| ai_megacap_crash | -30% | -45% | -15% | +3% | +6% | +12% | +5% | 2% |

The four existing class-based hypotheticals in `config/stress.yaml`
(no_safe_haven, stagflation, energy_shock_severe, tech_crash) are carried
over by a fixed translation: the equity value applies to SPY, QQQ and RSP;
the bonds value to IEF and TLT; the gold value to GLD; SHY gets 0% (it is
treated as cash-like, so CASH stays cash, unlike `stress.yaml`, which
shocks SHY as a bond). `stress.yaml` has no inflation, so the owner sets
each carried-over scenario's inflation. The translated rows are shown to
the owner for approval before `decision.yaml` is first hashed; until then
only the three v1 scenarios run.

Known gap: no portfolio holds an asset that gains from a falling dollar
other than gold. The report states this.

## Withdrawals

- Each portfolio's daily return path comes from the engine at 100% of
  capital with the normal `cost_bps` from `criteria.yaml`. Weights are
  built from the earliest available data (for warm-up) and must be free
  of NaN from the start date on; the run refuses otherwise. A NaN is never
  silently turned into cash.
- Value path: V(t) = V(t-1) x (1 + r(t)). On the first trading day of each
  month, after that day's return, the monthly withdrawal is subtracted,
  taken proportionally from all holdings, with no extra trading cost (a
  stated simplification). If V reaches 0 the portfolio is depleted: value
  stays 0 and the depletion month is reported.
- The withdrawal is the annual rate / 12 times the starting value, raised
  each January by the year-over-year change in the latest CPI usable on
  1 January under the publication lag below.
- CPI: FRED `CPIAUCNSA` (not seasonally adjusted; unlike CPIAUCSL it is not
  revised, so the downloaded values are the first-release values). Added
  as a new entry in `config/macro.yaml` with a lag: month M's index is
  usable from the last day of month M+1 (it is published mid-month M+1).
  The decision code cuts the series at 2018-12-31.
- Rates: 2%, 3.3%, 4%, 5% per year.
- Start dates: each January 2005 through 2014, every path ending
  2018-12-31.
- Reported per portfolio and rate:
  - real ending value (start-2005 path)
  - lowest value
  - maximum drawdown of the value path
  - longest time below a prior peak, in months, on the value path (what
    the owner would see on a statement); a drawdown unrecovered at
    2018-12-31 is reported as "at least N months, not recovered"
  - worst start year, by real ending value
- Year-one scenario hit: for each judgement-based scenario, value after
  one year = (1 + scenario return) minus the year's withdrawals at that
  rate, nominal and real.
- Not included: separating dividend and interest income from sales
  (prices are dividend-adjusted, so totals are correct).
- Output is in percentages only; no dollar amounts anywhere.

## Implementation

| file | role |
|---|---|
| `config/decision.yaml` | portfolios, blends, scenarios, rates, start years; sha256-hashed |
| `src/qrl/decision*.py` | all logic, split into focused modules (config, weights/scenarios, withdrawals, report): `decision_config.py`, `decision.py`, `decision_withdraw.py`, `decision_report.py` |
| `scripts/decision.py` | IO, wiring, formatting only; no thresholds or logic |
| `research/decision.md` | committed report |
| `pixi.toml` | task `decision` |

Reuse points: `core_compare.candidate_weights` builds A-G, and
`combine_portfolio` with a split of {core: 1.0, sleeve: 0.0} gives 100%
of capital (as `benchmark_metrics` already does). `core_compare.branch_mixes`
gives the risk-on and risk-off weights of switching cores from params
alone. Blends containing a switching core take that core's two branches
combined with the other component's fixed weights (AG and A-CASH each
have exactly two states, since only A switches). The stress module's
`run_stress`, `replay_loss` and `frozen_loss` accept any weight builder.
Stress cells use the stress module unchanged; its replay calls the engine
without an explicit `cost_bps`, so the engine's default 5 bps applies,
while withdrawal paths use `criteria.yaml`'s `cost_bps`. The report states
both. RSP is added to the price cache, and
CPIAUCNSA to `config/macro.yaml` (neither file is locked or hash-bound).
No locked file (`engine.py`, `metrics.py`, `periods.py`, `checks.py`,
`criteria.yaml`, `combined*.yaml`, `paper.yaml`, `factor.yaml`) and no
hash-bound config (`core_candidates.yaml`, `core_shortlist.yaml`,
`stress.yaml`, `fragility.yaml`) is edited.

## Refusals

- scenario missing a held fund
- held fund without a price at a start date (except the labelled dot-com
  proxies)
- missing CPI
- `core_candidates.yaml` sha256 mismatch
- a configured window or start year past 2018-12-31
- NaN weights on or after a start date

## Tests

- scenario arithmetic, hand-checked on a two-fund portfolio
- blend weights equal the weighted sum of components
- both states produced for switching portfolios
- withdrawal path matches a closed form on a constant-return series
- sealing: altering prices after 2018-12-31 leaves the report unchanged
- each refusal above
- the report contains no dollar amounts
- a blend with a switching component yields exactly two states
- withdrawal mechanics: depletion stops at 0; an unrecovered drawdown is reported as not recovered
- CPI lag: a month's index is not used before the last day of the next month
- dot-com cells report proxied shares, and cells above 25% carry the indicative flag

## Delivery

1. This spec: the report (portfolios, scenarios, withdrawals).
2. Next PR: a dashboard section parsed from `research/decision.md`, like
   the core comparison.
3. Later, separate specs: an exploratory what-if panel on the dashboard,
   and history-grounded scenarios (trigger-defined episodes, pre-2005 data
   included, reporting the typical and worst outcome per fund).
