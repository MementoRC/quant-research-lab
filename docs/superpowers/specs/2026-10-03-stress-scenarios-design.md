# Stress-scenario module — design

Date: 2026-10-03. Status: approved in conversation, pending written-spec review.

## Purpose

Diagnostic only. Answers: "if a shock like X happens, how much does the
portfolio lose, and does that breach the 35% max-drawdown cap
(`max_drawdown` in `config/profile.yaml`, the single source used for `breach`)?" It forecasts nothing, tunes nothing, and selects
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

Weights are built the same way the existing code builds them, not copied
from any report: the core with the same strategy-spec construction
`scripts/daily_check.py` uses for `config/portfolio.yaml` members; each
candidate with `qrl.paper.load_candidate` + `qrl.paper.candidate_weights`
(which applies `exit_before_delisting`).

Drawdown is always measured on an equity curve that starts at 1.0 on the
window's first day (a 0.0 return is prepended before calling
`qrl.metrics.drawdown`), so a loss on the window's first day counts.

- **Rule replay** (historical windows): price frames are truncated by index
  at the window end (no `slice_period`; no data after the window enters),
  start 2 calendar years before the window (warm-up for lookbacks: the longest is regime_pullback's 250 days; 3 years would precede GLD's 2004-11 launch for gfc_2008), run each
  strategy with `qrl.engine.run_backtest`, combine with `combine_portfolio`,
  and measure the worst drawdown inside the window only. Sleeve tickers not
  priced on every day of warm-up + window are dropped from that candidate's
  universe for that window; the report gives the count and share dropped.
  If the core's tickers are not fully priced, the cell is `unavailable`.
- **Frozen weights** (historical windows): take the latest weight row of
  each portfolio (built from data through today — the only use of
  post-window data in this module), buy at the window's first close, hold
  without rebalancing, and measure the worst drawdown inside the window.
  A ticker with no price at window start is replaced per class: `equity` →
  SPY, `gold` → cash (no gold series exists before GLD's 2004-11 launch).
  The report gives the proxied weight share per class.
- **Hypothetical**: loss = Σ class weight × class shock (single step).

No holdout-period *returns* are evaluated in any mode.

## Honesty labels and guards

- Every cell carries a label. Replay: `clean` (the core: a baseline, never
  searched), `in-sample` (a candidate in gfc_2008, inside its 2005-2018
  research period), `validation-seen` (a candidate in covid_2020 or
  inflation_2022), `out-of-sample` (a candidate in a window before its
  research period, e.g. dotcom_2000 if ever replayed). Frozen and hypothetical: `current-weights` (weights
  built from data through today, incl. post-research periods; the shock
  path itself is history or a stated judgment, not a test of selection).
- Guard: any historical window ending on/after the holdout start
  (`config/criteria.yaml`, 2023-01-01) is rejected at config load, and the
  module never calls `slice_period(..., unseal_holdout=True)`. Tested.

## Interfaces

- `src/qrl/stress.py` — pure functions: `load_stress_config(path, holdout_start)`,
  `replay_loss(...)`, `frozen_loss(...)`, `hypothetical_loss(...)`,
  `run_stress(...) -> list[Cell]` (the CLI assembles the report dict). No I/O except via injected loaders.
- `scripts/stress.py` — argparse CLI; prints a table; writes
  `reports/stress.json` (`--out` to override). Pixi task `stress`.
- `reports/stress.json` — per portfolio × scenario: mode, loss,
  `breach` (loss > `max_drawdown` from `config/profile.yaml`), label, proxied share; plus run timestamp
  and full sha256 of the raw bytes of `stress.yaml`, `portfolio.yaml`, `paper.yaml`, `profile.yaml`.

## Daily check

`scripts/daily_check.py` (not a locked file) reads `reports/stress.json`
(never recomputes) and reports stress findings on a separate warnings
channel, outside `HealthReport.checks`: printed after the health table and
written under a `stress_warnings` key in its JSON output.
- a **breach** warning listing every breaching portfolio × scenario;
- a **stale** warning if the report is missing, older than
  `max_report_age_days`, or any recorded config hash no longer matches.

These warnings never change `HealthReport.ok` or the exit status, and gate
nothing (no new pass rule).

## Errors

Missing price data for a whole window → that cell is reported as
`unavailable` with the reason, never silently dropped. A malformed config
fails loudly at load.

## Tests (`tests/test_stress.py`, new)

- Hand-computed losses on small hand-built frames for replay, frozen, and
  hypothetical modes.
- Per-class proxy substitution (equity → SPY, gold → cash) and proxied
  share per class; replay drops unpriced sleeve tickers and reports it.
- Drawdown counts a first-day loss (equity starts at 1.0).
- Replay frames contain no rows after the window end.
- Config rejects a window reaching the holdout, unknown classes, bad dates.
- Labels assigned correctly per portfolio and window.
- Daily check: breach, stale (age, hash) and missing-report warnings appear under `stress_warnings` and leave exit status unchanged.

## Out of scope

Forecasting, macro/news inputs, sector-level shocks (no sector data in the
repo), gating sleeve adoption, pre-1999 data.
