import numpy as np
import pandas as pd


def core_trend(
    close: pd.DataFrame, risk_on: str = "QQQ", risk_off: str = "GLD", lookback: int = 200
) -> pd.DataFrame:
    """Hold risk_on while it closes above its simple moving average, else risk_off."""
    price = close[risk_on]
    sma = price.rolling(lookback, min_periods=lookback).mean()
    above = price > sma

    w = pd.DataFrame(0.0, index=close.index, columns=[risk_on, risk_off])
    w.loc[above, risk_on] = 1.0
    w.loc[~above, risk_off] = 1.0

    warmup = sma.isna() | close[risk_on].isna() | close[risk_off].isna()
    w[warmup] = np.nan
    return w
