"""True-cash assumption row (spec: docs/methodology/true-cash-sleeve.md): a
cash leg earning each month's CPI inflation plus a fixed real yield, mixed
daily with a base portfolio's returns. An assumption, not a fund. Pure
functions; callers cut every price and CPI frame at the research end first.
"""

from __future__ import annotations

import pandas as pd

from .decision_withdraw import monthly_inflation


def _month_end(p: pd.Period) -> pd.Timestamp:
    return p.to_timestamp(how="end").normalize()


def strict_monthly_inflation(cpi: pd.Series, months: pd.PeriodIndex) -> pd.Series:
    """`monthly_inflation`, after refusing any month m whose own or previous
    calendar month end has no CPI value dated exactly on it (spec "Missing
    CPI: refuse, never fill"), so no month reuses a stale value."""
    known = pd.DatetimeIndex(cpi.dropna().index)
    for m in months:
        for p in (m - 1, m):
            if _month_end(p) not in known:
                raise ValueError(
                    f"missing CPI for month {m}: no value dated {_month_end(p).date()}"
                )
    return monthly_inflation(cpi, months)


def cash_leg_returns(
    days: pd.DatetimeIndex, trading_days: pd.DatetimeIndex, cpi: pd.Series, real_yield: float
) -> pd.Series:
    """Daily cash return on each of `days`: month m's growth (1 + inflation_m)
    x (1 + real_yield)^(1/12), split evenly (geometrically) over the n_m
    trading days of m in `trading_days`, so a whole month compounds to
    exactly that growth."""
    months = pd.DatetimeIndex(days).to_period("M")
    unique = pd.PeriodIndex(months.unique())
    counts = pd.DatetimeIndex(trading_days).to_period("M").value_counts().reindex(unique)
    if counts.isna().any():
        raise ValueError("cash leg: a month of `days` has no trading day in `trading_days`")
    growth = (1.0 + strict_monthly_inflation(cpi, unique)) * (1.0 + real_yield) ** (1 / 12)
    per_day = growth.to_numpy() ** (1.0 / counts.to_numpy(dtype=float)) - 1.0
    by_month = pd.Series(per_day, index=unique)
    return pd.Series(by_month.reindex(months).to_numpy(), index=days, dtype=float)


def nominal_loss_stats(series: pd.Series) -> dict:
    """Months in which the cash leg lost money in nominal terms. `series` holds
    returns, daily (DatetimeIndex, compounded to calendar months) or monthly
    (PeriodIndex). `n` months are negative of `N`; `worst` is the largest
    peak-to-trough nominal decline (positive fraction) of the cumulative
    monthly value, the starting value 1.0 counting as a peak. `start` is the
    first month of that decline (the month after its peak), `end` the trough
    month (YYYY-MM). No negative month gives worst 0.0 and start/end None."""
    if isinstance(series.index, pd.DatetimeIndex):
        series = (1.0 + series).groupby(series.index.to_period("M")).prod() - 1.0
    values = series.to_numpy(dtype=float)
    months = [str(p) for p in series.index]
    worst, start, end = 0.0, None, None
    value, peak, first = 1.0, 1.0, 0
    for i, v in enumerate(values):
        value *= 1.0 + v
        if value >= peak:
            peak, first = value, i + 1
        elif 1.0 - value / peak > worst:
            worst, start, end = 1.0 - value / peak, months[first], months[i]
    return {
        "n": int((values < 0).sum()),
        "N": len(values),
        "worst": worst,
        "start": start,
        "end": end,
    }


def mix_returns(base: pd.Series, cash: pd.Series, share: float) -> pd.Series:
    """(1 - share) x base + share x cash, day by day: the two legs rebalanced
    to their shares every day, the rebalancing at no cost (spec, disclosed)."""
    if not base.index.equals(cash.index):
        raise ValueError("base and cash returns must share one index")
    return (1.0 - share) * base + share * cash
