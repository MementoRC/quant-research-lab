# Macro overlay on core G (design, pre-registered 2026-10-07)

## Purpose

The owner wants a portfolio that adapts to macro conditions. The approach: keep
static G (25% each SPY, TLT, GLD, SHY; `config/core_candidates.yaml` id `G`) as
the base. Add a slow, de-risk-only overlay of three signals. Test honestly
whether it beats static G.

One fixed spec, one trial, no tuning.

## The rule

Fixed before any result is seen.

- Signals are evaluated at the close of the last trading day of each month.
- Weights are held constant until the next month-end. The engine's existing
  1-day shift handles execution.
- Cost is 5 bps on turnover (the engine default).
- All moves go to SHY only. The overlay never adds risk and never uses leverage.

| Signal | Trigger | Move | Basis |
|---|---|---|---|
| Trend | For each of SPY, TLT, GLD: close < its 210-trading-day SMA | 20/3 percentage points (about 6.67; one third of the 20-point cap) of that asset to SHY | Faber 2007 |
| Volatility | SPY 63-day realized vol (annualized std of daily returns) > 1.5x its trailing 1260-day median of that same vol series | 5 points SPY to SHY | Volatility clustering; Moreira and Muir 2017 |
| Inflation | CPI-U YoY (FRED `CPIAUCNS`, using the 2-month-end availability lag in `config/macro.yaml`) > 4% and above its value 3 months earlier | 5 points TLT to SHY | Long-bond losses in the 1970s |

Cap: total moved weight is at most 20 points. If triggered moves sum above 20
(the maximum possible is 30), scale every move by 20/sum.

Missing inputs or warm-up (for example, the 1260-day median needs history from
about 2000): that signal is off.

Gold is deliberately not tilted up for inflation. Shortening duration is the
more robust pre-2019 response, and a gold tilt would partly encode what the
2022 window showed.

## Pass rule

Research period 2005-01-01 to 2018-12-31 (`criteria.yaml` periods).

Overlay-G passes only if all of these hold versus static G:

- Sharpe >= G Sharpe + 0.05.
- Max drawdown no worse than G's.
- CAGR >= G CAGR - 0.01.
- The Sharpe improvement (overlay minus G) exceeds the 95th percentile of a
  random-signal null.

Null: for each signal, shuffle its on/off spells into random order. Keep the
fraction of time on and the spell lengths, so turnover is roughly matched.
1000 draws, fixed seed (recorded in `config/overlay.yaml`). Same cap and
month-end logic. The 95th percentile is taken by linear interpolation (numpy
default).

`combined_null.yaml` is not used. It grades sleeves added to a fixed core, not
changes to the core.

## Evidence and sealing

- The 2020 and 2022 validation windows were already seen once
  (`research/core_reveal.md`, ledger event 1), including G's 2022 loss. So every
  signal is justified by pre-2019 evidence only. The 2019-2022 run is stamped
  VALIDATION-SEEN and treated as weak evidence.
- The decisive test is a one-time unseal of the holdout (2023-01-01 to latest
  data) with the same three thresholds vs static G (no null). It spends the
  holdout for every future idea and reveals static G's 2023+ results too. It
  requires a pass on research, an explicit `--unseal-holdout-once` flag, and a
  fresh owner go-ahead at that time. A second holdout run is refused.
- The paper track (forward from 2026-10-02) is unaffected.

## Components

- `config/overlay.yaml`: the spec, pass rule, null settings, holdout plan. Its
  sha256 is recorded in the ledger at seed; later steps refuse if it changed.
- `src/qrl/overlay.py`: pure functions, signals to on/off series to capped
  month-end weights held daily. Inputs: close frame and CPI series. No data
  loading.
- `src/qrl/overlay_null.py`: spell shuffle and null distribution.
- `scripts/overlay.py` (pixi task `overlay`): subcommands `research`,
  `validate`, `holdout`. Uses `qrl.data.load_prices`, `qrl.macro.load_macro`
  and the unchanged engine.
- `research/overlay.md`: report. Dashboard wiring is a separate later PR.
- Not a `REGISTRY` strategy: the strategy contract passes prices only, and the
  overlay needs CPI.
- No changes to locked files (engine, metrics, periods, checks, locked YAMLs,
  `core_candidates.yaml`, existing tests).

## Run sequence

1. `research`: one trial vs static G plus null. A fail ends the overlay track
   (no retries, no tweaks).
2. `validate`: only after a pass. 2019-2022. VALIDATION-SEEN. Reported, not
   decisive.
3. `holdout`: only after a pass, with the flag and owner go-ahead. Decisive.

Every step is recorded in the ledger, passes and failures alike.

## Tests (new only)

- No lookahead: truncating future data leaves earlier weights unchanged.
- The cap always holds.
- Weights sum to 1, none negative.
- Weights are constant within a month.
- CPI lag is applied.
- The null preserves on-fraction and spell lengths.
- Hash-change refusal.
- Second-holdout refusal.
