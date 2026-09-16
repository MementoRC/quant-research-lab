"""Price data: Yahoo Finance daily bars with a local CSV cache, plus a synthetic
generator for offline development and tests."""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd

CACHE_DIR = Path("data/cache")


def _download_one(ticker: str, start: str, retries: int = 3) -> pd.DataFrame:
    import yfinance as yf

    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            df = yf.download(ticker, start=start, auto_adjust=True, progress=False,
                             threads=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if df.empty:
                raise RuntimeError(f"No rows returned for {ticker}")
            df = df[["Open", "High", "Low", "Close", "Volume"]]
            df.index = pd.to_datetime(df.index).tz_localize(None)
            return df.dropna(subset=["Open", "Close"])
        except Exception as err:  # network hiccups and rate limits are common in CI
            last_err = err
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Failed to download {ticker}: {last_err}")


def load_prices(tickers: list[str], start: str = "1999-01-01", refresh: bool = False,
                cache_dir: Path = CACHE_DIR) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (open, close) DataFrames with one column per ticker."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    frames = {}
    for t in sorted(set(tickers)):
        path = cache_dir / f"{t}.csv"
        if path.exists() and not refresh:
            df = pd.read_csv(path, index_col=0, parse_dates=True)
        else:
            df = _download_one(t, start)
            df.to_csv(path)
        frames[t] = df
    open_ = pd.DataFrame({t: f["Open"] for t, f in frames.items()}).sort_index()
    close = pd.DataFrame({t: f["Close"] for t, f in frames.items()}).sort_index()
    return open_, close


def synthetic_prices(tickers: list[str], start: str = "2003-01-01", end: str | None = None,
                     seed: int = 7) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Random-walk OHLC for offline work. Not market data; never trade on it."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, end or pd.Timestamp.today().normalize())
    drift = {"QQQ": 0.0006, "SPY": 0.0004, "GLD": 0.0003}
    vol = {"QQQ": 0.015, "SPY": 0.011, "GLD": 0.010}
    opens, closes = {}, {}
    for t in tickers:
        r = rng.normal(drift.get(t, 0.0003), vol.get(t, 0.012), len(idx))
        c = 100 * np.exp(np.cumsum(r))
        gap = rng.normal(0, vol.get(t, 0.012) / 3, len(idx))
        o = np.concatenate([[100.0], c[:-1]]) * np.exp(gap)
        closes[t], opens[t] = c, o
    return pd.DataFrame(opens, index=idx), pd.DataFrame(closes, index=idx)
