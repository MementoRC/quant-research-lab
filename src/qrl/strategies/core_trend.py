import numpy as np
import pandas as pd

CASH = "CASH"


def core_trend(
    close: pd.DataFrame, risk_on: str = "QQQ", risk_off: str = "GLD", lookback: int = 200
) -> pd.DataFrame:
    """Hold risk_on while it closes above its simple moving average, else risk_off.

    `risk_off` may be any priced ticker (e.g. GLD, TLT) or the sentinel
    `"CASH"`, which holds nothing (0 weight, not a priced column) instead of
    switching into another asset.
    """
    price = close[risk_on]
    sma = price.rolling(lookback, min_periods=lookback).mean()
    above = price > sma

    is_cash = risk_off == CASH
    cols = [risk_on] if is_cash else [risk_on, risk_off]
    w = pd.DataFrame(0.0, index=close.index, columns=cols)
    w.loc[above, risk_on] = 1.0

    warmup = sma.isna() | close[risk_on].isna()
    if not is_cash:
        w.loc[~above, risk_off] = 1.0
        warmup = warmup | close[risk_off].isna()
    w[warmup] = np.nan
    return w
