"""Proxy-era gold gaps (spec amendment 2026-10-23): single-day interior NaNs in
the spliced GLD leg are forward-filled at scoring time, never in the frozen
snapshot. Synthetic data only; the download is monkeypatched."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qrl.international import fill_proxy_gaps, proxy_gaps
from qrl.ledger import Ledger

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import international as script  # noqa: E402

INDEX = pd.bdate_range("2001-01-01", "2001-03-30")
REAL_START = INDEX[40]
GAP = INDEX[10]
PARAMS = {"risk_on": "QQQ", "risk_off": "GLD", "lookback": 200}


def _frames(gaps=(GAP,)):
    """A spliced panel: GLD priced from INDEX[2], real fund from REAL_START."""
    base = pd.Series(np.linspace(100.0, 140.0, len(INDEX)), index=INDEX)
    close = pd.DataFrame({"GLD": base, "EWJ": base * 0.5, "IEF": base * 0.9})
    close.loc[INDEX[:2], "GLD"] = np.nan
    open_ = close.shift(1)
    open_.loc[INDEX[2], "GLD"] = close.loc[INDEX[2], "GLD"]
    for day in gaps:
        close.loc[day, "GLD"] = np.nan
    open_ = close.shift(1)
    return open_, close


def _fill(open_, close, **kwargs):
    return fill_proxy_gaps(open_, close, ["GLD"], {"GLD": REAL_START}, **kwargs)


def test_a_single_proxy_day_gap_is_filled_with_a_zero_return():
    open_, close = _frames()
    new_open, new_close = _fill(open_, close)
    prev = close.loc[INDEX[9], "GLD"]
    assert new_close.loc[GAP, "GLD"] == prev  # close == previous close: zero return
    assert new_open.loc[GAP, "GLD"] == prev
    assert new_open.loc[INDEX[11], "GLD"] == prev  # the next open is the prior close
    assert new_close.loc[INDEX[11], "GLD"] == close.loc[INDEX[11], "GLD"]
    assert not new_close["GLD"].loc[INDEX[2] :].isna().any()
    assert not new_open["GLD"].loc[INDEX[3] :].isna().any()


def test_the_inputs_are_not_mutated_and_only_nan_cells_change():
    open_, close = _frames()
    open_copy, close_copy = open_.copy(), close.copy()
    new_open, new_close = _fill(open_, close)
    pd.testing.assert_frame_equal(open_, open_copy)
    pd.testing.assert_frame_equal(close, close_copy)
    for old, new in ((open_, new_open), (close, new_close)):
        changed = (old != new) & ~(old.isna() & new.isna())
        assert (old.isna() | ~changed).all().all()  # a changed cell was NaN before
        assert set(changed.columns[changed.any()]) <= {"GLD"}


def test_market_columns_and_the_real_fund_era_are_untouched():
    open_, close = _frames()
    close.loc[INDEX[50], "GLD"] = np.nan  # a NaN inside the real-fund era
    close.loc[INDEX[20], "EWJ"] = np.nan  # and in a market column
    open_ = close.shift(1)
    new_open, new_close = _fill(open_, close)
    pd.testing.assert_series_equal(new_close["EWJ"], close["EWJ"])
    pd.testing.assert_series_equal(new_open["EWJ"], open_["EWJ"])
    pd.testing.assert_series_equal(new_close["IEF"], close["IEF"])
    real = INDEX >= REAL_START
    assert np.isnan(new_close.loc[INDEX[50], "GLD"])
    pd.testing.assert_series_equal(new_close["GLD"][real], close["GLD"][real])
    pd.testing.assert_series_equal(new_open["GLD"][real], open_["GLD"][real])


def test_leading_nans_before_the_first_price_stay():
    open_, close = _frames()
    _, new_close = _fill(open_, close)
    assert new_close.loc[INDEX[:2], "GLD"].isna().all()


def test_a_gap_longer_than_the_limit_refuses():
    open_, close = _frames(gaps=(INDEX[10], INDEX[11]))
    with pytest.raises(ValueError, match="exceeds the fill limit"):
        _fill(open_, close)
    _fill(open_, close, limit=2)  # an explicit larger limit is the caller's choice


def test_two_separate_single_day_gaps_are_both_filled():
    open_, close = _frames(gaps=(INDEX[10], INDEX[20]))
    _, new_close = _fill(open_, close)
    assert new_close.loc[INDEX[20], "GLD"] == close.loc[INDEX[19], "GLD"]
    assert not new_close["GLD"].loc[INDEX[2] :].isna().any()


def test_proxy_gaps_reports_dates_and_the_longest_run():
    _, close = _frames(gaps=(INDEX[10], INDEX[20], INDEX[21]))
    dates, longest = proxy_gaps(close, ["GLD"], {"GLD": REAL_START})["GLD"]
    assert dates == [INDEX[10], INDEX[20], INDEX[21]]
    assert longest == 2


# --- scripts/international.py -------------------------------------------------

FUND_STARTS = {"SHY": "2002-07-30", "IEF": "2002-07-30", "TLT": "2002-07-30", "GLD": "2004-11-18"}
GOLD_GAP = pd.Timestamp("2001-11-23")


def gappy_load_raw(cfg, set_name, refresh, cache_dir):
    from qrl.data import synthetic_prices

    markets = cfg.market_set(set_name).markets
    open_, close = synthetic_prices([*markets, *cfg.funds], start="1996-01-01")
    for fund, first in FUND_STARTS.items():
        early = close.index < pd.Timestamp(first)
        open_.loc[early, fund] = np.nan
        close.loc[early, fund] = np.nan
    _, gold = synthetic_prices([cfg.gold_ticker], start="2000-08-30")
    gold_close = gold[cfg.gold_ticker].copy()
    gold_close.loc[GOLD_GAP] = np.nan  # a US half-session with no GC=F bar
    yields = {fred: pd.Series(4.0, index=close.index) for fred in cfg.fred_ids}
    return open_, close, gold_close, yields


def _no_download(*args, **kwargs):
    raise AssertionError("a recompute must not download")


@pytest.fixture
def opts(tmp_path, monkeypatch):
    monkeypatch.setattr(script, "load_raw", gappy_load_raw)
    return [
        "--ledger",
        str(tmp_path / "ledger.sqlite"),
        "--cache-dir",
        str(tmp_path / "cache"),
        "--out-dir",
        str(tmp_path / "research"),
    ]


def test_check_data_prints_the_gap_report_without_return_figures(opts, capsys):
    assert script.main(["check-data", "--set", "main", *opts]) == 0
    out = capsys.readouterr().out
    assert "GLD: 1 gaps, max run 1 (within the fill limit)" in out
    assert "2001-11-23" in out
    for leg in ("IEF: 0 gaps", "SHY: 0 gaps", "TLT: 0 gaps"):
        assert leg in out
    for word in ("sharpe", "cagr", "drawdown", "return", "volatility", "verdict", "pass"):
        assert word not in out.lower()


def test_a_resumed_started_event_with_a_proxy_gap_completes_as_designated(
    opts, tmp_path, monkeypatch
):
    with Ledger(opts[1]) as ledger:
        run_id = ledger.start_run("crit", "A", "gap fixture", git_commit="x")
        test_id = ledger.record_test(run_id, "crit", "core_trend", PARAMS, "u", {}, False)
    config = ROOT / "config" / "international.yaml"
    text = config.read_text(encoding="utf-8").replace(
        "failed_attempt_test_id: 1496", f"failed_attempt_test_id: {test_id}"
    )
    cfg_path = tmp_path / "international.yaml"
    cfg_path.write_text(text, encoding="utf-8")
    argv = [
        "run",
        "--set",
        "main",
        "--designated",
        "--reason",
        "owner go-ahead (test)",
        "--confirm",
        "--config",
        str(cfg_path),
        *opts,
    ]

    original = script.evaluate_market

    def crash(*args, **kwargs):
        raise RuntimeError("crash")

    monkeypatch.setattr(script, "evaluate_market", crash)
    with pytest.raises(RuntimeError):
        script.main(argv)
    with Ledger(opts[1]) as ledger:
        (started,) = ledger.list_international_events()
    assert started["status"] == "started"

    snapshot = Path(opts[3]) / "international" / "main_frozen.parquet"
    raw_open, raw_close = script.read_snapshot(snapshot)
    assert raw_close.loc[GOLD_GAP, "GLD"] != raw_close.loc[GOLD_GAP, "GLD"]  # NaN, kept raw

    seen = {}

    def spy(open_, close, *args, **kwargs):
        seen["gold"] = close.loc[GOLD_GAP, "GLD"]
        return original(open_, close, *args, **kwargs)

    monkeypatch.setattr(script, "evaluate_market", spy)
    monkeypatch.setattr(script, "load_raw", _no_download)
    assert script.main(argv) == 0
    assert seen["gold"] == raw_close.loc[GOLD_GAP - pd.offsets.BDay(1), "GLD"]
    with Ledger(opts[1]) as ledger:
        (event,) = ledger.list_international_events()
    assert event["event_id"] == started["event_id"]  # resumed, not a new attempt
    assert event["status"] == "completed"
    assert event["data_sha256"] == started["data_sha256"]
    assert event["result"]["subject_status"] == "designated_unvalidated"
