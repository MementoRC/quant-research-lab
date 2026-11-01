"""History-grounded scenarios (spec: docs/methodology/history-scenarios.md):
pure functions, no I/O. Episodes are found on the S&P 500 price index alone,
before any portfolio result. A decision aid: it selects nothing and recommends
nothing. Only data up to the research end (2018-12-31) is ever passed in."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .decision_withdraw import _months

EPS = 1e-12  # float slack so a fall of exactly 15% counts


@dataclass(frozen=True)
class Episode:
    """A peak, its lowest close before recovery, and the first close at or
    above the peak (None: not recovered by the data end)."""

    peak: pd.Timestamp
    trough: pd.Timestamp
    recovery: pd.Timestamp | None
    depth: float  # peak-to-trough, positive
    months: int | None  # calendar months peak to recovery
    window_end: pd.Timestamp  # earlier of peak + horizon years and the data end


def _episode(
    peak: pd.Timestamp,
    trough: pd.Timestamp,
    depth: float,
    recovery: pd.Timestamp | None,
    horizon_years: int,
    end: pd.Timestamp,
) -> Episode:
    months = None if recovery is None else _months(peak, recovery)
    window_end = min(pd.Timestamp(peak + pd.DateOffset(years=horizon_years)), end)
    return Episode(peak, trough, recovery, depth, months, window_end)


def find_episodes(
    close: pd.Series,
    threshold: float,
    start: pd.Timestamp,
    horizon_years: int,
    data_end: pd.Timestamp,
) -> list[Episode]:
    """Episodes of the index `close` (full history, cut at `data_end`): a peak
    is a close higher than every earlier close; it counts if a later close is
    `threshold` or more below it before the index closes at or above it again
    (exactly `threshold` counts). The trough is the lowest close before
    recovery, the recovery the first close at or above the peak. A tie with the
    peak ends the episode but is not a new peak: a later fall from it is an
    episode only after a strictly higher close. Raises ValueError on an
    unsorted or duplicated index. Only peaks on or after
    `start` are returned, in date order."""
    if not close.index.is_monotonic_increasing or close.index.has_duplicates:
        raise ValueError("close index must be strictly increasing (sorted, no duplicates)")
    series = close.dropna().loc[:data_end]
    values = series.to_numpy(dtype=float)
    dates = pd.DatetimeIndex(series.index)
    found: list[Episode] = []
    if len(values) == 0:
        return found
    peak_i = trough_i = 0
    flagged = False
    armed = True  # False after a tie with the high, until a strictly higher close
    for i in range(1, len(values)):
        if values[i] >= values[peak_i]:
            if flagged:
                depth = 1.0 - values[trough_i] / values[peak_i]
                found.append(
                    _episode(
                        dates[peak_i], dates[trough_i], depth, dates[i], horizon_years, data_end
                    )
                )
            if values[i] > values[peak_i]:
                peak_i, armed = i, True
            else:
                armed = False
            trough_i, flagged = peak_i, False
            continue
        if values[i] < values[trough_i]:
            trough_i = i
        if armed and 1.0 - values[trough_i] / values[peak_i] >= threshold - EPS:
            flagged = True
    if flagged:
        depth = 1.0 - values[trough_i] / values[peak_i]
        found.append(_episode(dates[peak_i], dates[trough_i], depth, None, horizon_years, data_end))
    return [ep for ep in found if ep.peak >= start]
