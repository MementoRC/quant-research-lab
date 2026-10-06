"""Withdrawal paths for the decision helper (spec:
docs/methodology/decision-helper.md, "Withdrawals"). `cpi` is the CPIAUCNSA
series indexed by AVAILABILITY date (`qrl.macro`'s `month_ends` lag: month M
is usable from the last day of month M+1), so no value is used before it was
published.
"""

from __future__ import annotations

import pandas as pd

CPI_SERIES = "CPIAUCNSA"
MAX_CPI_AGE = pd.Timedelta(days=45)  # monthly series: an older latest value means a gap


def usable_cpi(cpi: pd.Series, on: pd.Timestamp) -> float:
    """The latest CPI value usable on `on`. Raises ValueError ("missing CPI")
    if none is, or if the latest is older than MAX_CPI_AGE."""
    known = cpi.loc[:on].dropna()
    if known.empty or on - pd.Timestamp(known.index[-1]) > MAX_CPI_AGE:
        raise ValueError(f"missing CPI: no {CPI_SERIES} value usable on {on.date()}")
    return float(known.iloc[-1])
