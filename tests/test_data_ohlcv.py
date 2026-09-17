"""Tests for milestone 2.2's OHLCV data support: `load_ohlcv`, migration of
a legacy open/close-only Parquet cache when High/Low/Volume are requested,
and the `synthetic_ohlcv` generator's price invariants."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qrl import data as qdata


def _fake_ohlcv_df(n: int = 6, start: str = "2020-01-01") -> pd.DataFrame:
    idx = pd.bdate_range(start, periods=n)
    return pd.DataFrame(
        {
            "Open": np.linspace(10, 10 + n, n),
            "High": np.linspace(11, 11 + n, n),
            "Low": np.linspace(9, 9 + n, n),
            "Close": np.linspace(10.5, 10.5 + n, n),
            "Volume": np.full(n, 1000.0),
        },
        index=idx,
    )


def test_load_ohlcv_returns_all_five_frames(tmp_path, monkeypatch):
    def fake_chunk(tickers, start, retries=3):
        return {t: _fake_ohlcv_df() for t in tickers}

    monkeypatch.setattr(qdata, "_download_chunk", fake_chunk)
    frames = qdata.load_ohlcv(["AAA"], cache_dir=tmp_path)

    assert set(frames) == {"open", "high", "low", "close", "volume"}
    for key in frames:
        assert list(frames[key].columns) == ["AAA"]
    assert (frames["high"]["AAA"] >= frames["close"]["AAA"]).all()
    assert (frames["low"]["AAA"] <= frames["close"]["AAA"]).all()


def test_load_ohlcv_refetches_legacy_open_close_only_cache(tmp_path, monkeypatch):
    legacy = pd.DataFrame(
        {"Open": [10.0, 11.0, 12.0], "Close": [10.5, 11.5, 12.5]},
        index=pd.bdate_range("2020-01-01", periods=3),
    )
    legacy.to_parquet(tmp_path / "BBB.parquet")

    def fake_chunk(tickers, start, retries=3):
        return {t: _fake_ohlcv_df() for t in tickers}

    monkeypatch.setattr(qdata, "_download_chunk", fake_chunk)
    with pytest.warns(UserWarning, match="Refreshing"):
        frames = qdata.load_ohlcv(["BBB"], cache_dir=tmp_path)

    assert "BBB" in frames["high"].columns
    assert frames["high"]["BBB"].notna().any()


def test_load_prices_ignores_legacy_open_close_only_cache(tmp_path, monkeypatch):
    """load_prices only ever asks for Open/Close, so a cache that already has
    exactly those fields must not be treated as stale and refetched."""
    legacy = pd.DataFrame(
        {"Open": [10.0, 11.0], "Close": [10.5, 11.5]},
        index=pd.bdate_range("2020-01-01", periods=2),
    )
    legacy.to_parquet(tmp_path / "CCC.parquet")

    def boom(*args, **kwargs):
        raise AssertionError("load_prices must not refetch an open/close-only cache")

    monkeypatch.setattr(qdata, "_download_chunk", boom)
    monkeypatch.setattr(qdata, "_download_one", boom)

    _, close = qdata.load_prices(["CCC"], cache_dir=tmp_path)
    assert close["CCC"].iloc[0] == pytest.approx(10.5)


def test_synthetic_ohlcv_respects_high_low_bounds():
    frames = qdata.synthetic_ohlcv(["QQQ", "GLD"], start="2020-01-01", end="2020-06-30")
    o, h, lo, c, v = (frames[k] for k in ("open", "high", "low", "close", "volume"))

    upper = np.maximum(o, c)
    lower = np.minimum(o, c)
    assert (h >= upper - 1e-9).all().all()
    assert (upper >= lower - 1e-9).all().all()
    assert (lower >= lo - 1e-9).all().all()
    assert (v > 0).all().all()
