"""Withdrawal paths for the decision helper (spec:
docs/methodology/decision-helper.md, "Withdrawals"). Every value is a
fraction of the starting value (the report prints percentages only). `cpi`
is the CPIAUCNS series indexed by AVAILABILITY date (`qrl.macro`'s
`month_ends` lag: month M is usable from the last day of month M+1), so no
value is used before it was published.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

CPI_SERIES = "CPIAUCNS"
MAX_CPI_AGE = pd.Timedelta(days=45)  # monthly series: an older latest value means a gap


def usable_cpi(cpi: pd.Series, on: pd.Timestamp) -> float:
    """The latest CPI value usable on `on`. Raises ValueError ("missing CPI")
    if none is, or if the latest is older than MAX_CPI_AGE."""
    known = cpi.loc[:on].dropna()
    if known.empty or on - pd.Timestamp(known.index[-1]) > MAX_CPI_AGE:
        raise ValueError(f"missing CPI: no {CPI_SERIES} value usable on {on.date()}")
    return float(known.iloc[-1])


def monthly_withdrawals(
    rate: float, start_year: int, end_year: int, cpi: pd.Series
) -> dict[int, float]:
    """Monthly withdrawal per calendar year, as a fraction of the starting
    value: rate / 12 in the start year, then changed each January by the
    year-over-year change of the CPI usable on 1 January (vs 1 January of the
    year before)."""
    amounts = {start_year: rate / 12}
    for year in range(start_year + 1, end_year + 1):
        now = pd.Timestamp(year=year, month=1, day=1)
        before = pd.Timestamp(year=year - 1, month=1, day=1)
        change = usable_cpi(cpi, now) / usable_cpi(cpi, before) - 1
        amounts[year] = amounts[year - 1] * (1 + change)
    return amounts


@dataclass(frozen=True)
class WithdrawalPath:
    values: pd.Series  # value after each trading day, starting value = 1.0
    depleted: str | None  # "YYYY-MM" of depletion, or None


def withdrawal_path(returns: pd.Series, monthly: dict[int, float]) -> WithdrawalPath:
    """V(t) = V(t-1) x (1 + r(t)) from 1.0 before the first day. On the first
    trading day of each month, after that day's return, that year's monthly
    withdrawal is subtracted (proportionally from all holdings, no extra
    cost). At or below 0 the portfolio is depleted and stays at 0."""
    idx = pd.DatetimeIndex(returns.index)
    rets = returns.to_numpy(dtype=float)
    out = np.empty(len(rets))
    value = 1.0
    prev: tuple[int, int] | None = None
    depleted: str | None = None
    for i, ts in enumerate(idx):
        if np.isnan(rets[i]):
            raise ValueError(f"NaN return on {ts.date()}")
        month = (ts.year, ts.month)
        if value > 0:
            value *= 1.0 + rets[i]
            if month != prev:
                value -= monthly[ts.year]
            if value <= 0:
                value, depleted = 0.0, f"{ts:%Y-%m}"
        prev = month
        out[i] = value
    return WithdrawalPath(pd.Series(out, index=idx), depleted)


def _months(a: pd.Timestamp, b: pd.Timestamp) -> int:
    return (b.year - a.year) * 12 + b.month - a.month


def longest_below_peak(values: pd.Series) -> tuple[int, bool]:
    """Longest spell below a prior peak, in calendar months from the peak's
    month to the recovery month, and whether it recovered. The starting value
    1.0 is the first peak, dated the first day. A spell still open on the last
    date counts to that date and is reported as not recovered."""
    idx = pd.DatetimeIndex(values.index)
    peak, peak_at = 1.0, idx[0]
    best, recovered, under = 0, True, False
    for ts, v in zip(idx, values.to_numpy(dtype=float), strict=True):
        if v >= peak:
            if under and _months(peak_at, ts) > best:
                best, recovered = _months(peak_at, ts), True
            peak, peak_at, under = v, ts, False
        else:
            under = True
    if under and _months(peak_at, idx[-1]) >= best:
        best, recovered = _months(peak_at, idx[-1]), False
    return best, recovered


def path_metrics(path: WithdrawalPath, cpi: pd.Series) -> dict:
    """Ending value (nominal, and real: deflated by the CPI usable on the last
    day over the CPI usable on the first), lowest value, max drawdown of the
    value path (the starting 1.0 counts as a peak), longest time below a prior
    peak (with whether it recovered), whether the last value is below the
    running peak, and the depletion month."""
    values = path.values.to_numpy(dtype=float)
    idx = pd.DatetimeIndex(path.values.index)
    deflator = usable_cpi(cpi, idx[-1]) / usable_cpi(cpi, idx[0])
    peaks = np.maximum.accumulate(np.concatenate([[1.0], values]))[1:]
    months, recovered = longest_below_peak(path.values)
    return {
        "end_nominal": float(values[-1]),
        "end_real": float(values[-1]) / deflator,
        "lowest": float(values.min()),
        "max_drawdown": float((1.0 - values / peaks).max()),
        "below_peak_months": months,
        "recovered": recovered,
        "below_peak_at_end": bool(values[-1] < peaks[-1]),
        "depleted": path.depleted,
    }
