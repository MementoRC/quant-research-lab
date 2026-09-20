"""Buy a pullback, in an uptrend, that is happening on unusually low volume
or unusually low realized volatility (a "quiet" pullback -- no one is
selling in size, or the tape simply isn't moving much, unlike a real
breakdown).

Eligible when the close is above its `trend_lookback`-day moving average and
has pulled back below its `short_ma`-day moving average, while the chosen
`quiet_by` measure is below `quiet_ratio` times its own reference average:

* `quiet_by="volume"` (default, preserves original behaviour): `vol_lookback`
  -day volume at or below `quiet_ratio` times its own `vol_lookback`-day
  average volume.
* `quiet_by="volatility"`: realized volatility -- the rolling standard
  deviation of daily close-to-close returns over `vol_lookback` days -- at
  or below `quiet_ratio` times the rolling `vol_lookback`-day *average of
  that same volatility series*. Using the same window length for both the
  volatility estimate and its own reference average keeps the family's
  existing "value vs. its own trailing average, both over vol_lookback"
  shape (as already used for volume) rather than introducing a second,
  unrelated lookback parameter; the reference average effectively spans a
  longer, overlapping window of returns, so a genuine calm patch inside a
  choppier recent history reads as "quiet" relative to it.

Exit after `exit_days` bars held, or on a close back above the short moving
average, whichever comes first.

Both variants take the same (close, volume) signature so they share a
single registry entry; `quiet_by="volatility"` simply ignores `volume`.
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
    quiet_by: str = "volume",
    exit_days: int = 5,
    max_positions: int = 10,
    capital: float = 1.0,
) -> pd.DataFrame:
    if quiet_by not in ("volume", "volatility"):
        raise ValueError(f"quiet_by must be 'volume' or 'volatility', got {quiet_by!r}")

    sma_trend = close.rolling(trend_lookback, min_periods=trend_lookback).mean()
    sma_short = close.rolling(short_ma, min_periods=short_ma).mean()
    base_warmup = sma_trend.isna() | sma_short.isna() | close.isna()

    if quiet_by == "volume":
        level = volume
        avg_level = volume.rolling(vol_lookback, min_periods=vol_lookback).mean()
        warmup = base_warmup | volume.isna() | avg_level.isna()
    else:
        realized_vol = close.pct_change().rolling(vol_lookback, min_periods=vol_lookback).std()
        level = realized_vol
        avg_level = realized_vol.rolling(vol_lookback, min_periods=vol_lookback).mean()
        warmup = base_warmup | avg_level.isna()

    uptrend = close > sma_trend
    pullback = close <= sma_short
    quiet = level <= quiet_ratio * avg_level
    relative_level = level / avg_level

    entry = uptrend & pullback & quiet
    exit_signal = close > sma_short
    # Rank the quietest (lowest relative volume/volatility) pullbacks first.
    score = -relative_level

    return build_weights(
        entry=entry.fillna(False),
        exit_signal=exit_signal.fillna(True),
        score=score.fillna(-1e18),
        warmup=warmup,
        max_positions=max_positions,
        capital=capital,
        exit_days=exit_days,
    )
