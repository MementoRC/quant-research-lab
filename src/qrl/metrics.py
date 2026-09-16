"""Performance metrics computed from daily returns."""
from __future__ import annotations

import math

import pandas as pd

TRADING_DAYS = 252


def drawdown(returns: pd.Series) -> pd.Series:
    equity = (1 + returns).cumprod()
    return equity / equity.cummax() - 1


def compute_metrics(returns: pd.Series, turnover: pd.Series | None = None,
                    executed: pd.DataFrame | None = None) -> dict:
    returns = returns.dropna()
    n = len(returns)
    if n < 2:
        return {"days": n}
    equity = (1 + returns).cumprod()
    years = n / TRADING_DAYS
    std = returns.std()
    out = {
        "start": returns.index[0].strftime("%Y-%m-%d"),
        "end": returns.index[-1].strftime("%Y-%m-%d"),
        "days": n,
        "total_return": float(equity.iloc[-1] - 1),
        "cagr": float(equity.iloc[-1] ** (1 / years) - 1) if equity.iloc[-1] > 0 else -1.0,
        "volatility": float(std * math.sqrt(TRADING_DAYS)),
        "sharpe": float(returns.mean() / std * math.sqrt(TRADING_DAYS)) if std > 0 else 0.0,
        "max_drawdown": float(-drawdown(returns).min()),
    }
    out["calmar"] = out["cagr"] / out["max_drawdown"] if out["max_drawdown"] > 0 else None
    if turnover is not None:
        t = turnover.reindex(returns.index).fillna(0.0)
        out["trades"] = int((t > 1e-9).sum())
        out["turnover_per_year"] = float(t.sum() / years)
    if executed is not None:
        e = executed.reindex(returns.index).fillna(0.0)
        out["exposure"] = float((e.sum(axis=1) > 1e-9).mean())
    return out
