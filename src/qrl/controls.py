"""Null-sleeve controls: deliberately dumb sleeves used as a diagnostic.

A combined-rule run can pass many candidates simply because the universe
(e.g. today's large caps) drifted up. A null sleeve has no entry skill; if it
also passes the combined rule, the rule cannot separate strategy from
universe. These are controls, never candidates: callers must not record them
as ledger tests (they would inflate the deflated-Sharpe trial count).

Weights on day t use only data up to the close of day t.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

NULL_KINDS = ("equal_weight", "equal_weight_trend")
TREND_WINDOW = 200


def _equal_weight_of(held: pd.DataFrame) -> pd.DataFrame:
    """Equal weight across the True cells of each row; all-False rows are cash."""
    flags = held.astype(float)
    count = flags.sum(axis=1).replace(0.0, float("nan"))
    return flags.div(count, axis=0).fillna(0.0)


def null_sleeve_weights(close: pd.DataFrame, tickers: Sequence[str], kind: str) -> pd.DataFrame:
    """Target weights (long-only, rows sum to <= 1) for a null sleeve.

    `equal_weight`: equal weight across the tickers priced on each day.
    `equal_weight_trend`: equal weight across the tickers whose close is above
    their 200-day simple moving average, else cash (no weight before 200 days
    of history).
    """
    if kind not in NULL_KINDS:
        raise ValueError(f"unknown null sleeve kind {kind!r}; expected one of {NULL_KINDS}")
    prices = close[list(tickers)]
    if kind == "equal_weight":
        return _equal_weight_of(prices.notna())
    sma = prices.rolling(TREND_WINDOW, min_periods=TREND_WINDOW).mean()
    return _equal_weight_of(prices > sma)
