# Stress-scenario module — design

Date: 2026-10-03. Status: approved in conversation, pending written-spec review.

## Purpose

Diagnostic only. Answers: "if a shock like X happens, how much does the
portfolio lose, and does that breach the 35% max-drawdown cap
(`config/profile.yaml`)?" It forecasts nothing, tunes nothing, and selects
nothing. It does not modify `engine.py`, `metrics.py`, `periods.py`,
`checks.py`, or any locked config (AGENTS.md).

## Portfolios tested

Built with `qrl.portfolio.combine_portfolio` and the profile's
`capital_split` (core 0.80 / sleeve 0.20):

1. `chosen` — `config/portfolio.yaml` as it stands. Today: core
   `core_trend` (QQQ/GLD), empty sleeve, so the 20% is cash.
2. `core+<candidate>` — the core plus one paper-track candidate
   (`config/paper.yaml`) as the whole 20% sleeve, once per candidate.

## Scenarios — `config/stress.yaml`

Fixed before any results are seen. Each report records the file's sha256.
Changes after the first report are made only by a dated amendment comment
in the file, as with the other locked configs.

Historical windows (start, end inclusive):

| name | start | end | modes |
|---|---|---|---|
| dotcom_2000 | 2000-03-24 | 2002-10-09 | frozen only (GLD absent before 2004-11) |
| gfc_2008 | 2007-10-09 | 2009-03-09 | replay + frozen |
| covid_2020 | 2020-02-19 | 2020-04-30 | replay + frozen |
| inflation_2022 | 2022-01-03 | 2022-10-31 | replay + frozen |

Hypothetical shocks (instantaneous, applied per asset class to frozen
weights; classes: `gold` = GLD, `cash` = unallocated weight, `equity` =
every other ticker):

| name | equity | gold | meaning |
|---|---|---|---|
| no_safe_haven | -50% | -20% | stocks and gold fall together |
| stagflation | -45% | +10% | 1973-74-style real-asset rotation |
| energy_shock_severe | -40% | -10% | a fuel/diesel shock worse than 2022 |
| tech_crash | -60% | 0% | a 2000-02-scale equity collapse |

Also: `max_report_age_days: 30` (see Daily check).

## Loss measures

- **Rule replay** (historical windows): run each portfolio's strategies
  with `qrl.engine.run_backtest` from 3 calendar years before the window
  start (warm-up for lookbacks), combine with `combine_portfolio`, then
  measure the worst peak-to-trough drawdown of portfolio returns *inside the
  window only* (peak reset at window start; `qrl.metrics.drawdown`).
- **Frozen weights** (historical windows): take the latest weight row of
  each portfolio (the same weights `daily_check` reports today), buy at the
  window's first close, hold without rebalancing, and measure the worst
  drawdown of that path inside the window. Tickers with no price at window
  start are replaced by SPY; the report gives the proxied weight share.
- **Hypothetical**: loss = Σ class weight × class shock (single step).

Using the latest weight row reads current data the same way the paper track
and `daily_check` already do; no holdout-period *returns* are evaluated.

## Honesty labels and guards

- Each replay result carries a label: `clean` (the core: a baseline, never
  searched), `in-sample` (a candidate in a window overlapping its research
  period, i.e. gfc_2008), `validation-seen` (a candidate in covid_2020 or
  inflation_2022).
- Guard: any historical window ending on/after the holdout start
  (`config/criteria.yaml`, 2023-01-01) is rejected at config load, and the
  module never calls `slice_period(..., unseal_holdout=True)`. Tested.

## Interfaces

- `src/qrl/stress.py` — pure functions: `load_stress_config(path)`,
  `replay_loss(...)`, `frozen_loss(...)`, `hypothetical_loss(...)`,
  `run_stress(...) -> StressReport`. No I/O except via injected loaders.
- `scripts/stress.py` — argparse CLI; prints a table; writes
  `reports/stress.json` (`--out` to override). Pixi task `stress`.
- `reports/stress.json` — per portfolio × scenario: mode, loss,
  `breach` (loss > max_drawdown), label, proxied share; plus run timestamp
  and sha256 of `stress.yaml`, `portfolio.yaml`, `paper.yaml`, `profile.yaml`.

## Daily check

`scripts/daily_check.py` reads `reports/stress.json` (never recomputes) and
adds to its output:
- a standing **warning** listing every breaching portfolio × scenario;
- a **stale** warning if the report is missing, older than
  `max_report_age_days`, or any recorded config hash no longer matches.

Warnings do not change exit status or gate anything (no new pass rule).

## Errors

Missing price data for a whole window → that cell is reported as
`unavailable` with the reason, never silently dropped. A malformed config
fails loudly at load.

## Tests (`tests/test_stress.py`, new)

- Hand-computed losses on `synthetic_prices` for replay, frozen, and
  hypothetical modes.
- SPY proxy substitution and proxied-share figure.
- Config rejects a window reaching the holdout, unknown classes, bad dates.
- Labels assigned correctly per portfolio and window.
- Daily check: breach warning, stale (age and hash) warning, missing report.

## Out of scope

Forecasting, macro/news inputs, sector-level shocks (no sector data in the
repo), gating sleeve adoption, pre-1999 data.
