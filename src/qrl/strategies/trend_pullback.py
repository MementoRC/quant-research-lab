"""Buy dips in stocks still in a long-term uptrend.

Eligible when the close is above its `trend_lookback`-day moving average.
Entry fires on `pullback_days` consecutive down closes, or a close at least
`pullback_pct` below the `short_ma`-day moving average. Exit after
`exit_days` bars held, or on a close back above the short moving average,
whichever comes first.
"""

from __future__ import annotations

import pandas as pd

from ._cross_section import build_weights, consecutive_true


def trend_pullback(
    close: pd.DataFrame,
    *,
    trend_lookback: int = 200,
    short_ma: int = 10,
    pullback_days: int = 3,
    pullback_pct: float = 0.0,
    exit_days: int = 5,
    max_positions: int = 10,
    capital: float = 1.0,
) -> pd.DataFrame:
    sma_trend = close.rolling(trend_lookback, min_periods=trend_lookback).mean()
    sma_short = close.rolling(short_ma, min_periods=short_ma).mean()

    uptrend = close > sma_trend
    down_streak = consecutive_true(close.diff() < 0)
    below_short = close <= sma_short * (1 - pullback_pct)

    entry = uptrend & ((down_streak >= pullback_days) | below_short)
    exit_signal = close > sma_short
    # Rank deeper pullbacks (further below the short average) first.
    score = (sma_short - close) / sma_short
    warmup = sma_trend.isna() | sma_short.isna() | close.isna()

    return build_weights(
        entry=entry.fillna(False),
        exit_signal=exit_signal.fillna(True),
        score=score.fillna(-1e18),
        warmup=warmup,
        max_positions=max_positions,
        capital=capital,
        exit_days=exit_days,
    )
