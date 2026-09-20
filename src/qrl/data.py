"""Price data: Yahoo Finance daily bars with a local Parquet cache, plus a
synthetic generator for offline development and tests, and a per-ticker
coverage report for universes too large to eyeball."""

from __future__ import annotations

import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

CACHE_DIR = Path("data/cache")
CHUNK_SIZE = 50
_BARS = ["Open", "High", "Low", "Close", "Volume"]
_FIELD_COLUMNS = {
    "open": "Open",
    "high": "High",
    "low": "Low",
    "close": "Close",
    "volume": "Volume",
}


def _tidy(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[_BARS]
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df.dropna(subset=["Open", "Close"])


def _download_one(ticker: str, start: str, retries: int = 3) -> pd.DataFrame:
    import yfinance as yf

    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            df: pd.DataFrame = yf.download(
                ticker, start=start, auto_adjust=True, progress=False, threads=False
            )
            if df.empty:
                raise RuntimeError(f"No rows returned for {ticker}")
            return _tidy(df)
        except Exception as err:  # network hiccups and rate limits are common in CI
            last_err = err
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Failed to download {ticker}: {last_err}")


def _download_chunk(tickers: list[str], start: str, retries: int = 3) -> dict[str, pd.DataFrame]:
    """Download several tickers in one request. Tickers with no rows are simply
    absent from the result rather than raising; the caller falls back to
    per-ticker downloads for anything missing."""
    import yfinance as yf

    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            raw: pd.DataFrame = yf.download(
                tickers,
                start=start,
                auto_adjust=True,
                progress=False,
                threads=False,
                group_by="ticker",
            )
            if raw.empty:
                raise RuntimeError(f"No rows returned for chunk {tickers}")
            frames: dict[str, pd.DataFrame] = {}
            for t in tickers:
                try:
                    sub = raw[t] if isinstance(raw.columns, pd.MultiIndex) else raw
                except KeyError:
                    continue
                tidy = _tidy(pd.DataFrame(sub))
                if not tidy.empty:
                    frames[t] = tidy
            return frames
        except Exception as err:  # network hiccups and rate limits are common in CI
            last_err = err
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Failed to download chunk {tickers}: {last_err}")


def _cache_path(cache_dir: Path, ticker: str) -> Path:
    return cache_dir / f"{ticker}.parquet"


def _load_cached(cache_dir: Path, ticker: str) -> pd.DataFrame | None:
    """Read a ticker's cache, migrating a legacy CSV to Parquet in place."""
    parquet_path = _cache_path(cache_dir, ticker)
    if parquet_path.exists():
        return pd.read_parquet(parquet_path)
    csv_path = cache_dir / f"{ticker}.csv"
    if csv_path.exists():
        df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
        df.to_parquet(parquet_path)
        return df
    return None


def _has_columns(df: pd.DataFrame, columns: list[str]) -> bool:
    return all(c in df.columns for c in columns)


def _load_frames(
    tickers: list[str],
    start: str,
    refresh: bool,
    cache_dir: Path,
    columns: list[str],
) -> dict[str, pd.DataFrame]:
    """Shared loader behind `load_prices`/`load_ohlcv`: per-ticker tidy bars
    satisfying `columns`.

    A cached ticker missing one of `columns` (e.g. a legacy open/close-only
    parquet asked for High/Low/Volume) is treated exactly like an uncached
    ticker and refetched. Tickers with no data anywhere (after that refetch)
    are dropped and reported with a warning, not a crash.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    tickers = sorted(set(tickers))
    frames: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    stale: list[str] = []

    to_fetch = []
    for t in tickers:
        cached = None if refresh else _load_cached(cache_dir, t)
        if cached is None:
            to_fetch.append(t)
        elif _has_columns(cached, columns):
            frames[t] = cached
        else:
            stale.append(t)
            to_fetch.append(t)

    for i in range(0, len(to_fetch), CHUNK_SIZE):
        chunk = to_fetch[i : i + CHUNK_SIZE]
        try:
            downloaded = _download_chunk(chunk, start)
        except RuntimeError:
            downloaded = {}
        for t in chunk:
            if t in downloaded:
                continue
            try:
                downloaded[t] = _download_one(t, start)
            except RuntimeError as err:
                missing.append(t)
                warnings.warn(str(err), stacklevel=2)
        for t, df in downloaded.items():
            df.to_parquet(_cache_path(cache_dir, t))
            frames[t] = df

    if stale:
        warnings.warn(
            f"Refreshing {len(stale)} ticker(s) whose cache was missing requested "
            f"field(s) {columns}: {sorted(stale)}",
            stacklevel=2,
        )
    if missing:
        warnings.warn(
            f"No data for {len(missing)} ticker(s), dropped from the universe: {sorted(missing)}",
            stacklevel=2,
        )

    return frames


def load_prices(
    tickers: list[str],
    start: str = "1999-01-01",
    refresh: bool = False,
    cache_dir: Path = CACHE_DIR,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (open, close) DataFrames with one column per ticker.

    Uncached tickers are downloaded in chunks (`CHUNK_SIZE` per request); a
    chunk that fails outright, or a ticker missing from an otherwise-successful
    chunk, falls back to a per-ticker download. Tickers with no data anywhere
    are dropped and reported with a warning, not a crash.
    """
    frames = _load_frames(tickers, start, refresh, cache_dir, ["Open", "Close"])
    open_ = pd.DataFrame({t: f["Open"] for t, f in frames.items()}).sort_index()
    close = pd.DataFrame({t: f["Close"] for t, f in frames.items()}).sort_index()
    return open_, close


def load_ohlcv(
    tickers: list[str],
    start: str = "1999-01-01",
    refresh: bool = False,
    cache_dir: Path = CACHE_DIR,
) -> dict[str, pd.DataFrame]:
    """Return {"open", "high", "low", "close", "volume"} DataFrames, one
    column per ticker, for strategy families that need more than open/close
    (e.g. `low_range_close` needs high/low, `quiet_pullback` needs volume).

    Uses the same chunked-download-with-fallback cache as `load_prices`; a
    cache written before this field was needed is treated as needing a
    refetch rather than crashing (see `_load_frames`).
    """
    frames = _load_frames(tickers, start, refresh, cache_dir, _BARS)
    return {
        key: pd.DataFrame({t: f[col] for t, f in frames.items()}).sort_index()
        for key, col in _FIELD_COLUMNS.items()
    }


def coverage_report(
    open_: pd.DataFrame,
    close: pd.DataFrame,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Per-ticker data-quality summary, indexed by ticker.

    Columns: `first_date`/`last_date` (first and last bar with a valid close),
    `n_bars` (valid close count), `missing_pct` (share of the calendar between
    a ticker's first and last date with no close -- the calendar is the union
    index of `close`, restricted to [start, end] if given), `gaps` (number of
    separate NaN runs inside the ticker's life), and `ended_early` (its last
    date is before the frame's last date, a hint it may have been delisted or
    acquired -- see `qrl.tradability.exit_before_delisting`).
    """
    idx = close.index
    if start is not None or end is not None:
        lo = pd.Timestamp(start) if start is not None else idx[0]
        hi = pd.Timestamp(end) if end is not None else idx[-1]
        idx = idx[(idx >= lo) & (idx <= hi)]
    close_w = close.reindex(idx)
    frame_end = idx[-1]

    rows: dict[str, dict[str, object]] = {}
    for t in close_w.columns:
        valid = close_w[t].dropna()
        if valid.empty:
            rows[t] = {
                "first_date": pd.NaT,
                "last_date": pd.NaT,
                "n_bars": 0,
                "missing_pct": 1.0,
                "gaps": 0,
                "ended_early": True,
            }
            continue
        first, last = valid.index[0], valid.index[-1]
        life_is_nan = close_w[t].loc[first:last].isna()
        gaps = int((life_is_nan & ~life_is_nan.shift(1, fill_value=False)).sum())
        rows[t] = {
            "first_date": first,
            "last_date": last,
            "n_bars": int(valid.shape[0]),
            "missing_pct": float(life_is_nan.mean()),
            "gaps": gaps,
            "ended_early": bool(last < frame_end),
        }
    return pd.DataFrame.from_dict(rows, orient="index")


def synthetic_prices(
    tickers: list[str], start: str = "2003-01-01", end: str | None = None, seed: int = 7
) -> tuple[pd.DataFrame, pd.DataFrame]:
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


def synthetic_ohlcv(
    tickers: list[str], start: str = "2003-01-01", end: str | None = None, seed: int = 7
) -> dict[str, pd.DataFrame]:
    """Random-walk OHLCV for offline work, built on `synthetic_prices`.

    High/low are the open/close range stretched by a small random extension,
    so high >= max(open, close) >= min(open, close) >= low always holds;
    volume is a positive series loosely scaled to the day's absolute move.
    Not market data; never trade on it.
    """
    open_, close = synthetic_prices(tickers, start=start, end=end, seed=seed)
    rng = np.random.default_rng(seed + 1)
    shape = close.shape
    hi_ext = pd.DataFrame(rng.uniform(0.0, 0.01, shape), index=close.index, columns=close.columns)
    lo_ext = pd.DataFrame(rng.uniform(0.0, 0.01, shape), index=close.index, columns=close.columns)

    upper = open_.combine(close, np.maximum)
    lower = open_.combine(close, np.minimum)
    high = upper * (1 + hi_ext)
    low = lower * (1 - lo_ext)

    move = close.pct_change().abs().fillna(0.0)
    volume = pd.DataFrame(
        1_000_000 * (1 + 20 * move) * rng.uniform(0.8, 1.2, shape),
        index=close.index,
        columns=close.columns,
    ).round()

    return {"open": open_, "high": high, "low": low, "close": close, "volume": volume}
