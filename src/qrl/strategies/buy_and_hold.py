import pandas as pd


def buy_and_hold(close: pd.DataFrame, ticker: str) -> pd.DataFrame:
    w = pd.DataFrame({ticker: 1.0}, index=close.index)
    w[close[ticker].isna()] = float("nan")
    return w
