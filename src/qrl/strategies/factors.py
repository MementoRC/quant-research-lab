"""Long-only factor families over the point-in-time universe (Phase 4, milestone 3).

    value_ey        score = NetIncome TTM / market cap (fund_shares x close at t);
                    names with NI TTM <= 0 are excluded; higher is better.
    profitability   score = OperatingIncomeLoss TTM / Assets; higher is better
                    (operating income, not gross profit, for coverage; owner 2026-10-02).
    low_investment  score = Assets / Assets one year earlier - 1; LOWER is better;
                    both Assets values must be present.

Frames arrive in the order of the spec's `fields` (see `qrl.factor_data`): close,
pit_member, then the fundamentals. All fundamentals follow the filed < t rule, so
weights at t use only data up to the close of t.

Common rules
- Eligible at t: a current pit member, with a close at t and a non-NaN score.
- On each rebalance day hold the best `n_hold` eligible names, 1/n_hold each. With
  fewer eligible names, hold those at 1/n_hold each and keep the rest in cash.
- Rebalance days: the first trading day of each month ("monthly") or of
  Jan/Apr/Jul/Oct ("quarterly"). Weights are constant in between. A held name that
  leaves membership or loses its price keeps its weight until the next rebalance,
  where it is simply not reselected (its weight goes to cash there); no intra-period
  adjustment (price loss at delisting is handled downstream by
  `qrl.tradability.exit_before_delisting`). With monthly rebalancing membership is
  re-evaluated the same day, so non-members are never held.
- `trend_filter`: when the equal-weight index of current members (daily mean of
  members' returns, compounded) is below its 200-day moving average at t, hold cash
  that day (weights are restored when it recovers); NaN moving average (warm-up) is
  treated as cash.
- Rows before the first rebalance day are NaN (warm-up); afterwards always numeric.
- Ties in score are broken by ticker name.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

REBALANCE_MODES = ("monthly", "quarterly")
QUARTER_MONTHS = (1, 4, 7, 10)
TREND_WINDOW = 200


def rebalance_flags(index: pd.DatetimeIndex, rebalance: str) -> np.ndarray:
    """Bool array: True on the first trading day of each month (or of Jan/Apr/Jul/Oct)."""
    if rebalance not in REBALANCE_MODES:
        raise ValueError(f"rebalance must be one of {REBALANCE_MODES}, got {rebalance!r}")
    month = np.asarray(index.year * 12 + index.month)
    first = np.concatenate([[False], month[1:] != month[:-1]])
    if rebalance == "quarterly":
        first &= np.isin(np.asarray(index.month), QUARTER_MONTHS)
    return first


def _trend_on(close: pd.DataFrame, member: pd.DataFrame) -> np.ndarray:
    """Bool per row: the equal-weight member index is at or above its 200-day average."""
    ret = close.pct_change(fill_method=None).where(member)
    level = (1.0 + ret.mean(axis=1).fillna(0.0)).cumprod()
    ma = level.rolling(TREND_WINDOW, min_periods=TREND_WINDOW).mean()
    return (level >= ma).to_numpy()


def factor_weights(
    close: pd.DataFrame,
    member: pd.DataFrame,
    score: pd.DataFrame,
    *,
    n_hold: int,
    rebalance: str,
    trend_filter: bool,
    higher_is_better: bool = True,
) -> pd.DataFrame:
    """Rank `score` among eligible names and hold the best `n_hold` (module docstring)."""
    if n_hold < 1:
        raise ValueError("n_hold must be >= 1")
    flags = rebalance_flags(pd.DatetimeIndex(close.index), rebalance)
    member_b = member.reindex_like(close).fillna(False).astype(bool)
    eligible = (member_b & close.notna() & score.reindex_like(close).notna()).to_numpy()
    sc = score.reindex_like(close).to_numpy(dtype=float)
    sign = -1.0 if higher_is_better else 1.0
    cols = list(close.columns)

    out = np.zeros(close.shape)
    current = np.zeros(close.shape[1])
    for i in np.flatnonzero(flags):
        idx = np.flatnonzero(eligible[i])
        ranked = sorted(idx, key=lambda j: (sign * sc[i, j], cols[j]))[:n_hold]
        current = np.zeros(close.shape[1])
        current[ranked] = 1.0 / n_hold
        out[i] = current
        nxt = i + 1
        while nxt < len(out) and not flags[nxt]:
            out[nxt] = current
            nxt += 1

    if trend_filter:
        out = out * _trend_on(close, member_b)[:, None]
    weights = pd.DataFrame(out, index=close.index, columns=close.columns)
    if flags.any():
        weights.iloc[: int(np.flatnonzero(flags)[0])] = np.nan
    else:
        weights[:] = np.nan
    return weights


def value_ey(
    close: pd.DataFrame,
    member: pd.DataFrame,
    ni_ttm: pd.DataFrame,
    shares: pd.DataFrame,
    *,
    n_hold: int = 30,
    rebalance: str = "monthly",
    trend_filter: bool = False,
) -> pd.DataFrame:
    cap = shares.reindex_like(close) * close
    score = (ni_ttm.reindex_like(close) / cap.where(cap > 0)).where(ni_ttm.reindex_like(close) > 0)
    return factor_weights(
        close, member, score, n_hold=n_hold, rebalance=rebalance, trend_filter=trend_filter
    )


def profitability(
    close: pd.DataFrame,
    member: pd.DataFrame,
    opinc_ttm: pd.DataFrame,
    assets: pd.DataFrame,
    *,
    n_hold: int = 30,
    rebalance: str = "monthly",
    trend_filter: bool = False,
) -> pd.DataFrame:
    a = assets.reindex_like(close)
    score = opinc_ttm.reindex_like(close) / a.where(a > 0)
    return factor_weights(
        close, member, score, n_hold=n_hold, rebalance=rebalance, trend_filter=trend_filter
    )


def low_investment(
    close: pd.DataFrame,
    member: pd.DataFrame,
    assets: pd.DataFrame,
    assets_lag1y: pd.DataFrame,
    *,
    n_hold: int = 30,
    rebalance: str = "monthly",
    trend_filter: bool = False,
) -> pd.DataFrame:
    lag = assets_lag1y.reindex_like(close)
    score = assets.reindex_like(close) / lag.where(lag > 0) - 1.0
    return factor_weights(
        close,
        member,
        score,
        n_hold=n_hold,
        rebalance=rebalance,
        trend_filter=trend_filter,
        higher_is_better=False,
    )
