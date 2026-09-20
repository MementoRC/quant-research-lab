"""Buy a pullback, in an uptrend, that is happening on unusually low volume
(a "quiet" pullback -- no one is selling in size, unlike a real breakdown).

Eligible when the close is above its `trend_lookback`-day moving average and
has pulled back below its `short_ma`-day moving average, while `vol_lookback`
-day volume is below `quiet_ratio` times its own `vol_lookback`-day average.
Exit after `exit_days` bars held, or on a close back above the short moving
average, whichever comes first.

Judgment call: the plan says "below-average volatility or volume"; since
this family's signature takes `volume` (not just `close`), it is defined
here purely on relative volume, matching its declared data field.
"""

from __future__ import annotations

import pandas as pd

from ._cross_section import build_weights


def quiet_pullback(
    close: pd.DataFrame,
    volume: pd.DataFrame,
    *,
    trend_lookback: int = 200,
    short_ma: int = 10,
    vol_lookback: int = 20,
    quiet_ratio: float = 0.8,
    exit_days: int = 5,
    max_positions: int = 10,
    capital: float = 1.0,
) -> pd.DataFrame:
    sma_trend = close.rolling(trend_lookback, min_periods=trend_lookback).mean()
    sma_short = close.rolling(short_ma, min_periods=short_ma).mean()
    avg_volume = volume.rolling(vol_lookback, min_periods=vol_lookback).mean()

    uptrend = close > sma_trend
    pullback = close <= sma_short
    quiet = volume <= quiet_ratio * avg_volume
    vol_ratio = volume / avg_volume

    entry = uptrend & pullback & quiet
    exit_signal = close > sma_short
    # Rank the quietest (lowest relative volume) pullbacks first.
    score = -vol_ratio
    warmup = sma_trend.isna() | sma_short.isna() | avg_volume.isna() | close.isna() | volume.isna()

    return build_weights(
        entry=entry.fillna(False),
        exit_signal=exit_signal.fillna(True),
        score=score.fillna(-1e18),
        warmup=warmup,
        max_positions=max_positions,
        capital=capital,
        exit_days=exit_days,
    )
