"""Daily-bar backtest engine.

Timing contract (the most important rule in this project):
    target_weights.loc[t] may use information up to and including the CLOSE of day t.
    The engine executes those weights at the OPEN of day t+1.

A day's portfolio return is built in two legs:
    1. Overnight gap (close t-1 -> open t) earned on the weights held overnight.
    2. Rebalance at the open, paying costs on turnover.
    3. Session (open t -> close t) earned on the newly executed weights.

Simplifications, documented on purpose:
    * Weights are treated as rebalanced to target daily (drift is ignored).
    * Uninvested cash earns 0%.
    * Long-only, no leverage (sum of weights <= 1). Phase 3 adds leverage.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

_EPS = 1e-9


@dataclass
class BacktestResult:
    returns: pd.Series  # daily net portfolio returns, starting on first execution day
    executed: pd.DataFrame  # weights held during each day's session
    turnover: pd.Series
    costs: pd.Series
    target: pd.DataFrame  # the strategy's raw target weights (last row = next open)

    @property
    def equity(self) -> pd.Series:
        return (1 + self.returns).cumprod()

    @property
    def trade_days(self) -> int:
        return int((self.turnover > _EPS).sum())


def run_backtest(
    open_: pd.DataFrame,
    close: pd.DataFrame,
    target_weights: pd.DataFrame,
    cost_bps: float = 5.0,
) -> BacktestResult:
    cols = list(target_weights.columns)
    idx = target_weights.index
    open_ = open_.reindex(index=idx, columns=cols)
    close = close.reindex(index=idx, columns=cols)

    valid_rows = target_weights.notna().all(axis=1)
    if not valid_rows.any():
        raise ValueError("Strategy produced no valid target weights.")
    first_signal = valid_rows.idxmax()

    tw = target_weights.fillna(0.0)
    if (tw < -_EPS).any().any():
        raise ValueError("Negative weights (shorting) are not supported yet.")
    if (tw.sum(axis=1) > 1 + _EPS).any():
        raise ValueError("Weights sum above 1 (leverage) are not supported yet.")

    executed = tw.shift(1).fillna(0.0)  # held during day t's session
    overnight = executed.shift(1).fillna(0.0)  # held from close t-1 into open t

    gap = open_ / close.shift(1) - 1
    session = close / open_ - 1

    # Refuse to silently treat missing prices as zero returns on held positions.
    held_gap = (overnight > _EPS) & gap.isna()
    held_session = (executed > _EPS) & session.isna()
    held_gap.iloc[0] = False
    if held_gap.any().any() or held_session.any().any():
        bad: pd.Series = (held_gap | held_session).stack()  # type: ignore[assignment]
        first_bad = bad[bad].index[0]
        raise ValueError(f"Missing price for a held position at {first_bad}.")

    gap = gap.fillna(0.0)
    session = session.fillna(0.0)

    turnover = (executed - overnight).abs().sum(axis=1)
    costs = turnover * cost_bps / 10_000.0
    growth = (
        (1 + (overnight * gap).sum(axis=1)) * (1 - costs) * (1 + (executed * session).sum(axis=1))
    )
    returns = growth - 1

    # Results start on the first day a position could be executed.
    pos: int = idx.get_loc(first_signal)  # type: ignore[assignment]
    if pos + 1 >= len(idx):
        raise ValueError("Not enough data after the warm-up period.")
    start = idx[pos + 1]

    return BacktestResult(
        returns=returns.loc[start:],
        executed=executed.loc[start:],
        turnover=turnover.loc[start:],
        costs=costs.loc[start:],
        target=target_weights,
    )
