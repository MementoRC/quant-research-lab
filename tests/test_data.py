import numpy as np
import pandas as pd
import pytest

from qrl import data as qdata


def _fake_df(n=5, start="2020-01-01"):
    idx = pd.bdate_range(start, periods=n)
    return pd.DataFrame(
        {
            "Open": np.linspace(10, 10 + n, n),
            "High": np.linspace(11, 11 + n, n),
            "Low": np.linspace(9, 9 + n, n),
            "Close": np.linspace(10.5, 10.5 + n, n),
            "Volume": np.full(n, 1000),
        },
        index=idx,
    )


def test_load_prices_writes_and_reuses_parquet_cache(tmp_path, monkeypatch):
    calls = []

    def fake_chunk(tickers, start, retries=3):
        calls.append(list(tickers))
        return {t: _fake_df() for t in tickers}

    monkeypatch.setattr(qdata, "_download_chunk", fake_chunk)
    open_, close = qdata.load_prices(["AAA"], cache_dir=tmp_path)
    assert (tmp_path / "AAA.parquet").exists()
    assert list(open_.columns) == ["AAA"]
    assert len(calls) == 1

    # Second call must not hit the network again: cache is reused.
    _, close2 = qdata.load_prices(["AAA"], cache_dir=tmp_path)
    assert len(calls) == 1
    # Parquet round-trips values exactly but drops the DatetimeIndex freq tag.
    pd.testing.assert_frame_equal(close, close2, check_freq=False)


def test_load_prices_migrates_legacy_csv_without_refetching(tmp_path, monkeypatch):
    df = _fake_df()
    df.to_csv(tmp_path / "BBB.csv")

    def boom(*args, **kwargs):
        raise AssertionError("should not fetch when a legacy CSV cache exists")

    monkeypatch.setattr(qdata, "_download_chunk", boom)
    monkeypatch.setattr(qdata, "_download_one", boom)

    _, close = qdata.load_prices(["BBB"], cache_dir=tmp_path)
    assert (tmp_path / "BBB.parquet").exists()
    assert close["BBB"].iloc[0] == pytest.approx(df["Close"].iloc[0])


def test_load_prices_falls_back_to_per_ticker_on_chunk_failure(tmp_path, monkeypatch):
    def failing_chunk(tickers, start, retries=3):
        raise RuntimeError("simulated network failure")

    def fake_one(ticker, start, retries=3):
        return _fake_df()

    monkeypatch.setattr(qdata, "_download_chunk", failing_chunk)
    monkeypatch.setattr(qdata, "_download_one", fake_one)

    _, close = qdata.load_prices(["CCC"], cache_dir=tmp_path)
    assert list(close.columns) == ["CCC"]
    assert (tmp_path / "CCC.parquet").exists()


def test_load_prices_reports_missing_tickers_without_crashing(tmp_path, monkeypatch):
    def partial_chunk(tickers, start, retries=3):
        return {t: _fake_df() for t in tickers if t != "DEAD"}

    def fake_one(ticker, start, retries=3):
        if ticker == "DEAD":
            raise RuntimeError(f"No rows returned for {ticker}")
        return _fake_df()

    monkeypatch.setattr(qdata, "_download_chunk", partial_chunk)
    monkeypatch.setattr(qdata, "_download_one", fake_one)

    with pytest.warns(UserWarning, match="No data for"):
        _, close = qdata.load_prices(["OK", "DEAD"], cache_dir=tmp_path)
    assert list(close.columns) == ["OK"]
    assert not (tmp_path / "DEAD.parquet").exists()


def test_coverage_report_hand_checked():
    idx = pd.bdate_range("2024-01-01", periods=6)
    close = pd.DataFrame(
        {
            "FULL": [10, 11, 12, 13, 14, 15],
            "TRUNC": [20, 21, np.nan, 22, np.nan, np.nan],
        },
        index=idx,
    )
    open_ = close.copy()

    cov = qdata.coverage_report(open_, close)

    assert cov.loc["FULL", "n_bars"] == 6
    assert cov.loc["FULL", "missing_pct"] == 0.0
    assert cov.loc["FULL", "gaps"] == 0
    assert not cov.loc["FULL", "ended_early"]

    assert cov.loc["TRUNC", "first_date"] == idx[0]
    assert cov.loc["TRUNC", "last_date"] == idx[3]
    assert cov.loc["TRUNC", "n_bars"] == 3
    # Life is rows 0..3 (4 rows), one NaN inside (row 2) -> missing_pct = 1/4.
    assert cov.loc["TRUNC", "missing_pct"] == pytest.approx(0.25)
    assert cov.loc["TRUNC", "gaps"] == 1
    assert bool(cov.loc["TRUNC", "ended_early"]) is True


def test_load_prices_signature_returns_open_close_tuple(tmp_path, monkeypatch):
    """build_site.py relies on this exact call shape staying backward compatible."""

    def fake_chunk(tickers, start, retries=3):
        return {t: _fake_df() for t in tickers}

    monkeypatch.setattr(qdata, "_download_chunk", fake_chunk)
    result = qdata.load_prices(["ZZZ"], start="2020-01-01", refresh=False, cache_dir=tmp_path)
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], pd.DataFrame)
    assert isinstance(result[1], pd.DataFrame)
