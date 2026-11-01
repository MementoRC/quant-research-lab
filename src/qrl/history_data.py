"""Stand-in data for the history-grounded scenarios (spec:
docs/methodology/history-scenarios.md, "Stand-in data"). Pure builders and a
panel assembler, plus thin loaders at the end of the file. Every series is cut
at the research end (2018-12-31) right after loading."""

from __future__ import annotations

import numpy as np
import pandas as pd

DIVIDEND_DAYS = 252  # trading days a year: the daily dividend accrual is yield / 252


def _require_increasing(index: pd.Index, name: str) -> None:
    if not index.is_monotonic_increasing or index.has_duplicates:
        raise ValueError(f"{name} index must be strictly increasing (sorted, no duplicates)")


def interpolate_monthly(monthly: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    """Each monthly figure placed on its month's last trading day in `index`,
    the days between filled at a constant daily rate (geometric interpolation),
    so each month end equals that month's figure. NaN before the first and
    after the last month end. `monthly` is indexed by any date in the month.

    Each figure is a monthly average placed on the month end, and the days
    before it are interpolated toward that NEXT month-end anchor: an accepted
    lookahead for a stand-in (see the methodology caveat). If `index` ends
    mid-month, the last month's figure lands on the last day of `index`, which
    is not its real month end. A month missing from `monthly` is bridged
    geometrically between its neighbours. Raises ValueError on a non-positive
    figure or an unsorted or duplicated `index`."""
    _require_increasing(index, "index")
    if (monthly <= 0).any():
        raise ValueError("monthly figures must be positive (geometric interpolation)")
    figure = pd.Series(
        monthly.to_numpy(dtype=float), index=pd.PeriodIndex(monthly.index, freq="M")
    )
    figure = figure[~figure.index.duplicated(keep="last")]
    last_day = pd.Series(index, index=index.to_period("M")).groupby(level=0).max()
    anchors = figure.reindex(last_day.index).dropna()
    logs = pd.Series(np.nan, index=index)
    logs.loc[last_day.loc[anchors.index].to_numpy()] = np.log(anchors.to_numpy())
    filled = logs.interpolate(method="linear", limit_area="inside")
    return pd.Series(np.exp(filled.to_numpy(dtype=float)), index=index)


def sp_with_dividends(price: pd.Series, annual_yield: pd.Series) -> pd.Series:
    """The S&P 500 price plus its dividend yield accrued daily: daily return =
    price return + yield / 252, starting at 1.0. `annual_yield` is the monthly
    series (any date in the month, fraction a year); each day uses the previous
    month's value, known at the start of its month. Raises ValueError on a
    empty, unsorted or duplicated price, a missing price or yield, or two
    yield figures in one month."""
    _require_increasing(price.index, "price")
    if len(price) == 0:
        raise ValueError("the S&P 500 price is empty")
    if price.isna().any():
        raise ValueError("the S&P 500 price has missing days")
    by_month = pd.Series(
        annual_yield.to_numpy(dtype=float), index=pd.PeriodIndex(annual_yield.index, freq="M")
    )
    if by_month.index.has_duplicates:
        raise ValueError("dividend yield has more than one figure in a month")
    previous = pd.DatetimeIndex(price.index).to_period("M") - 1
    daily = pd.Series(by_month.reindex(previous).to_numpy(), index=price.index)
    if daily.isna().any():
        raise ValueError(f"dividend yield missing on {int(daily.isna().sum())} days")
    returns = price.pct_change(fill_method=None) + daily / DIVIDEND_DAYS
    returns.iloc[0] = 0.0
    return (1.0 + returns).cumprod()
