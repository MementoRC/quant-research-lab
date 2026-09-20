"""Buy stocks, still in an uptrend, that close near the low of their own
day's high-low range (a one-day capitulation / reversal setup).

Eligible when the close is above its `trend_lookback`-day moving average and
today's close sits in the bottom `range_pct` of today's high-low range. Exit
on a close above the *prior* day's high, or after `exit_days` bars held,
whichever comes first.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ._cross_section import build_weights


def low_range_close(
    close: pd.DataFrame,
    high: pd.DataFrame,
    low: pd.DataFrame,
    *,
    trend_lookback: int = 200,
    range_pct: float = 0.25,
    exit_days: int = 5,
    max_positions: int = 10,
    capital: float = 1.0,
) -> pd.DataFrame:
    sma_trend = close.rolling(trend_lookback, min_periods=trend_lookback).mean()
    uptrend = close > sma_trend

    day_range = (high - low).replace(0.0, np.nan)
    close_pos = (close - low) / day_range  # 0 = at the low, 1 = at the high

    entry = uptrend & (close_pos <= range_pct)
    exit_signal = close > high.shift(1)
    # Rank the closes nearest the low of their range first.
    score = -close_pos
    warmup = sma_trend.isna() | close.isna() | high.isna() | low.isna() | close_pos.isna()

    return build_weights(
        entry=entry.fillna(False),
        exit_signal=exit_signal.fillna(True),
        score=score.fillna(-1e18),
        warmup=warmup,
        max_positions=max_positions,
        capital=capital,
        exit_days=exit_days,
    )
