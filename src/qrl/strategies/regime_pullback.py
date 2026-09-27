"""trend_pullback's entry logic gated by a universe-breadth regime filter.

Same pullback-in-an-uptrend entry/exit signals as `trend_pullback` (buy a
down-streak or a close well below the short moving average while still above
the long-term trend average, rank deeper pullbacks first), but exposure is
flattened entirely on any day the sleeve's own universe breadth falls below
`breadth_min`. Breadth is the fraction of tickers in the sleeve's own
universe trading above their own `breadth_ma`-day moving average, using data
through that day only -- reusing the sleeve's own tickers needs no extra
ticker and no new data plumbing (no new `fields`).

Motivation: across roughly 1100 search trials, the existing sleeves
(trend_pullback, low_range_close, quiet_pullback) fail the max_drawdown
criterion in about 89pct of cases, and none of them has any defensive
mechanism, while `core_trend` (in `REGISTRY`) does have a risk-on/risk-off
switch. This family gives the cross-sectional sleeves a comparable safety
valve.

On a bad-regime day, held positions are force-exited (not merely hidden from
the output) and no new entries are taken, so a name re-entering once the
regime recovers must clear the normal pullback entry bar again rather than
silently resuming its old weight.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ._cross_section import build_weights, consecutive_true


def regime_pullback(
    close: pd.DataFrame,
    *,
    trend_lookback: int = 200,
    short_ma: int = 10,
    pullback_days: int = 3,
    pullback_pct: float = 0.0,
    exit_days: int = 5,
    max_positions: int = 10,
    capital: float = 1.0,
    breadth_ma: int = 200,
    breadth_min: float = 0.4,
) -> pd.DataFrame:
    sma_trend = close.rolling(trend_lookback, min_periods=trend_lookback).mean()
    sma_short = close.rolling(short_ma, min_periods=short_ma).mean()

    uptrend = close > sma_trend
    down_streak = consecutive_true(close.diff() < 0)
    below_short = close <= sma_short * (1 - pullback_pct)

    raw_entry = uptrend & ((down_streak >= pullback_days) | below_short)
    raw_exit = close > sma_short
    # Rank deeper pullbacks (further below the short average) first.
    score = (sma_short - close) / sma_short
    warmup = sma_trend.isna() | sma_short.isna() | close.isna()

    # Universe breadth: fraction of the sleeve's own tickers trading above
    # their own `breadth_ma`-day trailing moving average, using data through
    # day t only. A ticker whose own breadth average is not yet available
    # compares False (a comparison against NaN is never True), so it simply
    # counts against the fraction instead of needing its own warm-up
    # bookkeeping -- the same "earliest-ready ticker drives the start"
    # convention `_cross_section` already relies on for entry/exit.
    sma_breadth = close.rolling(breadth_ma, min_periods=breadth_ma).mean()
    above_breadth_ma = close > sma_breadth
    breadth = above_breadth_ma.mean(axis=1)
    regime_on = breadth >= breadth_min
    regime_on_frame = pd.DataFrame(
        np.tile(regime_on.to_numpy()[:, None], (1, close.shape[1])),
        index=close.index,
        columns=close.columns,
    )

    entry = raw_entry.fillna(False) & regime_on_frame
    # Bad-regime days force an exit for every held name (not merely hide the
    # weight), so a name is never left silently "paused" at its old weight.
    exit_signal = raw_exit.fillna(True) | ~regime_on_frame

    return build_weights(
        entry=entry,
        exit_signal=exit_signal,
        score=score.fillna(-1e18),
        warmup=warmup,
        max_positions=max_positions,
        capital=capital,
        exit_days=exit_days,
    )
