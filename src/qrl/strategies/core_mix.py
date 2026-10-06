"""Static or trend-switched fixed-weight core mix.

risk_on / risk_off map ticker -> weight (non-negative, sum <= 1). With
`risk_off` omitted the mix is static. With it, the rule mirrors `core_trend`:
hold `risk_on` while `signal` closes above its simple moving average over
`lookback` days, else `risk_off`. Rows are NaN during warm-up and whenever a
ticker the rule can hold (or the signal) has no price. Row t uses data up to
the close of day t. Spec: docs/methodology/core-comparison.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

_EPS = 1e-9


def _validated(name: str, mix: dict[str, float]) -> None:
    if not mix:
        raise ValueError(f"{name} must be a non-empty ticker -> weight mapping")
    if any(w < 0 for w in mix.values()):
        raise ValueError(f"{name} has a negative weight; long-only required")
    total = sum(mix.values())
    if total > 1 + _EPS:
        raise ValueError(f"{name} weights sum to {total:.3f}, above 1")


def core_mix(
    close: pd.DataFrame,
    risk_on: dict[str, float],
    risk_off: dict[str, float] | None = None,
    signal: str | None = None,
    lookback: int | None = None,
) -> pd.DataFrame:
    _validated("risk_on", risk_on)
    if risk_off is None:
        if signal is not None or lookback is not None:
            raise ValueError(
                "signal and lookback apply only with risk_off: a static mix never switches"
            )
        cols = list(risk_on)
        static = pd.DataFrame({t: float(x) for t, x in risk_on.items()}, index=close.index)
        static[close[cols].isna().any(axis=1)] = np.nan
        return static

    _validated("risk_off", risk_off)
    if signal is None or lookback is None:
        raise ValueError("risk_off requires both signal and lookback")
    price = close[signal]
    sma = price.rolling(lookback, min_periods=lookback).mean()
    above = (price > sma).to_numpy()

    cols = list(dict.fromkeys([*risk_on, *risk_off]))
    w = pd.DataFrame(0.0, index=close.index, columns=cols)
    for ticker, weight in risk_on.items():
        w[ticker] = w[ticker] + np.where(above, weight, 0.0)
    for ticker, weight in risk_off.items():
        w[ticker] = w[ticker] + np.where(above, 0.0, weight)

    warmup = sma.isna() | price.isna() | close[cols].isna().any(axis=1)
    w[warmup] = np.nan
    return w


def core_mix_tickers(params: dict) -> list[str]:
    """Every ticker whose prices the rule needs: the held tickers, plus the
    signal when the mix switches (callers load `data[f][tickers]`)."""
    names = [*params["risk_on"], *(params.get("risk_off") or {})]
    if params.get("risk_off") is not None and params.get("signal"):
        names.append(params["signal"])
    return list(dict.fromkeys(names))
