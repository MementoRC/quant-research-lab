"""Tests for the stress-scenario diagnostic (qrl.stress, scripts/stress.py
wiring into scripts/daily_check.py). Offline; small hand-built frames only.
Spec: docs/methodology/stress-scenarios.md.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

from qrl.health import CheckResult, HealthReport
from qrl.stress import (
    DataUnavailable,
    Hypothetical,
    PortfolioDef,
    StressConfig,
    Window,
    asset_class,
    file_hashes,
    frozen_loss,
    hypothetical_loss,
    load_stress_config,
    priced,
    replay_label,
    replay_loss,
    run_stress,
    stress_config_paths,
    stress_warnings,
    window_drawdown,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import daily_check  # noqa: E402

HOLDOUT = pd.Timestamp("2023-01-01")


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "stress.yaml"
    p.write_text(text)
    return p


GOOD = """
max_report_age_days: 30
windows:
  - {name: w1, start: "2008-01-02", end: "2008-06-30", replay: true}
hypotheticals:
  - {name: h1, equity: -0.5, gold: -0.2, bonds: 0.0}
"""


def test_shipped_config_loads():
    cfg, digest = load_stress_config(ROOT / "config" / "stress.yaml", HOLDOUT)
    assert [w.name for w in cfg.windows] == [
        "dotcom_2000",
        "gfc_2008",
        "covid_2020",
        "inflation_2022",
    ]
    assert not cfg.windows[0].replay
    assert {h.name for h in cfg.hypotheticals} == {
        "no_safe_haven",
        "stagflation",
        "energy_shock_severe",
        "tech_crash",
    }
    assert cfg.max_report_age_days == 30
    assert len(digest) == 64  # full sha256


def test_loads_good_config(tmp_path):
    cfg, _ = load_stress_config(_write(tmp_path, GOOD), HOLDOUT)
    w = cfg.windows[0]
    assert (w.start, w.end, w.replay) == (
        pd.Timestamp("2008-01-02"),
        pd.Timestamp("2008-06-30"),
        True,
    )
    assert cfg.hypotheticals[0].shocks == {"equity": -0.5, "gold": -0.2, "bonds": 0.0}


def test_rejects_window_reaching_holdout(tmp_path):
    text = GOOD.replace('end: "2008-06-30"', 'end: "2023-01-01"')
    with pytest.raises(ValueError, match="holdout"):
        load_stress_config(_write(tmp_path, text), HOLDOUT)


def test_rejects_start_not_before_end(tmp_path):
    text = GOOD.replace('start: "2008-01-02"', 'start: "2008-07-01"')
    with pytest.raises(ValueError, match="before"):
        load_stress_config(_write(tmp_path, text), HOLDOUT)


def test_rejects_bad_date(tmp_path):
    text = GOOD.replace('"2008-01-02"', '"not-a-date"')
    with pytest.raises(ValueError, match="not-a-date|Unknown|convert|parse"):
        load_stress_config(_write(tmp_path, text), HOLDOUT)


def test_rejects_unknown_class(tmp_path):
    text = GOOD.replace("bonds: 0.0", "crypto: 0.0")
    with pytest.raises(ValueError, match="unknown"):
        load_stress_config(_write(tmp_path, text), HOLDOUT)


def test_rejects_shock_at_or_below_minus_one(tmp_path):
    text = GOOD.replace("equity: -0.5", "equity: -1.0")
    with pytest.raises(ValueError, match="-1"):
        load_stress_config(_write(tmp_path, text), HOLDOUT)


def test_rejects_duplicate_names(tmp_path):
    text = GOOD.replace("name: h1", "name: w1")
    with pytest.raises(ValueError, match="duplicate"):
        load_stress_config(_write(tmp_path, text), HOLDOUT)


def test_rejects_hypothetical_missing_a_class(tmp_path):
    text = GOOD.replace(", gold: -0.2", "")
    with pytest.raises(ValueError, match="gold"):
        load_stress_config(_write(tmp_path, text), HOLDOUT)


@pytest.mark.parametrize("key", ["windows", "hypotheticals", "max_report_age_days"])
def test_rejects_missing_top_level_key(tmp_path, key):
    lines = [ln for ln in GOOD.splitlines() if ln.strip()]
    # drop the key and its indented children
    kept, skipping = [], False
    for ln in lines:
        if not ln.startswith(" "):
            skipping = ln.startswith(f"{key}:")
        if not skipping:
            kept.append(ln)
    with pytest.raises(ValueError, match=key):
        load_stress_config(_write(tmp_path, "\n".join(kept)), HOLDOUT)


def test_window_drawdown_counts_first_day_loss():
    # equity 1.0 -> 0.9 -> 0.945; qrl.metrics.drawdown alone would miss day 1.
    r = pd.Series([-0.10, 0.05], index=pd.bdate_range("2020-01-06", periods=2))
    assert window_drawdown(r) == pytest.approx(0.10)


def test_window_drawdown_zero_when_only_rising():
    r = pd.Series([0.01, 0.02], index=pd.bdate_range("2020-01-06", periods=2))
    assert window_drawdown(r) == pytest.approx(0.0)


def test_asset_class():
    assert asset_class("GLD") == "gold"
    assert asset_class("QQQ") == "equity"
    assert asset_class("AAPL") == "equity"


def test_hypothetical_loss_by_class():
    w = pd.Series({"AAA": 0.5, "GLD": 0.3, "BBB": 0.0})  # 0.2 cash
    h = Hypothetical("x", {"equity": -0.5, "gold": -0.2})
    assert hypothetical_loss(w, h) == pytest.approx(0.5 * 0.5 + 0.3 * 0.2)


def test_hypothetical_gain_is_negative_loss():
    w = pd.Series({"GLD": 1.0})
    assert hypothetical_loss(w, Hypothetical("x", {"gold": 0.1})) == pytest.approx(-0.1)


def _win(start, end, replay=True, name="w"):
    return Window(name, pd.Timestamp(start), pd.Timestamp(end), replay)


def test_frozen_loss_buy_and_hold_no_rebalance():
    idx = pd.bdate_range("2008-01-07", periods=3)
    close = pd.DataFrame({"AAA": [100.0, 80.0, 90.0], "GLD": [100.0, 100.0, 100.0]}, index=idx)
    w = pd.Series({"AAA": 0.5, "GLD": 0.3})  # 0.2 cash
    loss, detail = frozen_loss(w, close, _win("2008-01-07", "2008-01-09"))
    # value: 1.0 -> 0.5*0.8+0.3+0.2 = 0.9 -> 0.5*0.9+0.5 = 0.95
    assert loss == pytest.approx(0.10)
    assert detail["proxied_share"] == {"equity": 0.0, "gold": 0.0, "bonds": 0.0}


def test_frozen_loss_proxies_equity_to_spy_and_gold_to_cash():
    idx = pd.bdate_range("2001-01-08", periods=2)
    close = pd.DataFrame(
        {
            "AAA": [float("nan"), float("nan")],
            "GLD": [float("nan"), float("nan")],
            "SPY": [100.0, 50.0],
        },
        index=idx,
    )
    w = pd.Series({"AAA": 0.6, "GLD": 0.4})
    loss, detail = frozen_loss(w, close, _win("2001-01-08", "2001-01-09"))
    # AAA -> SPY (halves), GLD -> cash: 1.0 -> 0.6*0.5 + 0.4 = 0.7
    assert loss == pytest.approx(0.30)
    assert detail["proxied_share"] == {
        "equity": pytest.approx(0.6),
        "gold": pytest.approx(0.4),
        "bonds": 0.0,
    }


def test_frozen_loss_ticker_absent_from_frame_is_proxied():
    idx = pd.bdate_range("2001-01-08", periods=2)
    close = pd.DataFrame({"SPY": [100.0, 90.0]}, index=idx)
    loss, detail = frozen_loss(pd.Series({"ZZZ": 1.0}), close, _win("2001-01-08", "2001-01-09"))
    assert loss == pytest.approx(0.10)
    assert detail["proxied_share"]["equity"] == pytest.approx(1.0)


def test_frozen_loss_no_prices_in_window_raises():
    close = pd.DataFrame({"SPY": [100.0]}, index=pd.bdate_range("2010-01-04", periods=1))
    with pytest.raises(DataUnavailable, match="no prices"):
        frozen_loss(pd.Series({"SPY": 1.0}), close, _win("2001-01-08", "2001-01-09"))


def test_frozen_loss_spy_held_directly_is_not_proxied():
    idx = pd.bdate_range("2001-01-08", periods=2)
    close = pd.DataFrame({"SPY": [100.0, 90.0]}, index=idx)
    loss, detail = frozen_loss(pd.Series({"SPY": 1.0}), close, _win("2001-01-08", "2001-01-09"))
    assert loss == pytest.approx(0.10)
    assert detail["proxied_share"] == {"equity": 0.0, "gold": 0.0, "bonds": 0.0}


def test_all_cash_weights_lose_nothing():
    idx = pd.bdate_range("2001-01-08", periods=3)
    close = pd.DataFrame({"A": [100.0, 50.0, 25.0]}, index=idx)
    w = pd.Series({"A": 0.0})
    loss, _ = frozen_loss(w, close, _win("2001-01-08", "2001-01-10"))
    assert loss == pytest.approx(0.0)
    assert hypothetical_loss(w, Hypothetical("x", {"equity": -0.5, "gold": -0.2})) == pytest.approx(
        0.0
    )


@pytest.mark.parametrize("ticker", ["IEF", "TLT", "SHY", "AGG"])
def test_asset_class_bonds(ticker):
    assert asset_class(ticker) == "bonds"


def test_hypothetical_loss_includes_bonds_class():
    w = pd.Series({"SPY": 0.5, "IEF": 0.3, "GLD": 0.1})  # 0.1 cash
    h = Hypothetical("x", {"equity": -0.4, "gold": -0.1, "bonds": 0.05})
    # -(0.5 * -0.4 + 0.1 * -0.1 + 0.3 * 0.05)
    assert hypothetical_loss(w, h) == pytest.approx(0.195)


def test_frozen_loss_proxies_bonds_to_cash():
    idx = pd.bdate_range("2001-01-08", periods=2)
    close = pd.DataFrame({"IEF": [float("nan")] * 2, "SPY": [100.0, 50.0]}, index=idx)
    w = pd.Series({"SPY": 0.5, "IEF": 0.5})
    loss, detail = frozen_loss(w, close, _win("2001-01-08", "2001-01-09"))
    # SPY halves, IEF -> cash: 1.0 -> 0.5 * 0.5 + 0.5 = 0.75
    assert loss == pytest.approx(0.25)
    assert detail["proxied_share"] == {"equity": 0.0, "gold": 0.0, "bonds": pytest.approx(0.5)}


def test_rejects_hypothetical_missing_bonds(tmp_path):
    text = GOOD.replace(", bonds: 0.0", "")
    with pytest.raises(ValueError, match="bonds"):
        load_stress_config(_write(tmp_path, text), HOLDOUT)


def test_shipped_config_has_bonds_shocks():
    cfg, _ = load_stress_config(ROOT / "config" / "stress.yaml", HOLDOUT)
    assert {h.name: h.shocks["bonds"] for h in cfg.hypotheticals} == {
        "no_safe_haven": -0.15,
        "stagflation": -0.20,
        "energy_shock_severe": -0.10,
        "tech_crash": 0.05,
    }


def _frames(close: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {"open": close.copy(), "close": close}


def _hold(ticker: str, weight: float = 1.0):
    def build(data, keep):
        return pd.DataFrame({ticker: weight}, index=data["close"].index)

    return build


def test_priced_requires_every_day():
    idx = pd.bdate_range("2020-01-01", periods=3)
    close = pd.DataFrame({"A": [1.0, 1.0, 1.0], "B": [float("nan"), 1.0, 1.0]}, index=idx)
    assert priced(close, ["A", "B", "C"]) == ["A"]


def _long_close(**cols: float) -> pd.DataFrame:
    """Flat frames from 2018-01-01 (>= 2 years of warm-up before Jan 2020)."""
    idx = pd.bdate_range("2018-01-01", "2020-01-14")
    return pd.DataFrame(cols, index=idx)


def test_replay_loss_measures_inside_window_only():
    close = _long_close(A=100.0)
    # crash on Jan 13 is AFTER the window
    for day, px in {
        "2020-01-07": 90.0,
        "2020-01-08": 80.0,
        "2020-01-09": 85.0,
        "2020-01-10": 100.0,
        "2020-01-13": 10.0,
        "2020-01-14": 10.0,
    }.items():
        close.loc[day, "A"] = px
    p = PortfolioDef("p", _hold("A"), core_tickers=["A"], sleeve_universe=[], candidate=False)
    loss, detail = replay_loss(_frames(close), p, _win("2020-01-07", "2020-01-10"))
    # in-window equity 1, .9, .8, .85, 1.0 (no costs: the only trade is at the warm-up start)
    assert loss == pytest.approx(0.20)
    assert detail == {"sleeve_dropped": 0, "sleeve_dropped_share": 0.0}


def test_replay_warmup_truncated_raises():
    idx = pd.bdate_range("2020-01-01", periods=10)
    close = pd.DataFrame({"A": 100.0}, index=idx)
    p = PortfolioDef("p", _hold("A"), core_tickers=["A"], sleeve_universe=[], candidate=False)
    with pytest.raises(DataUnavailable, match="warm-up"):
        replay_loss(_frames(close), p, _win("2020-01-07", "2020-01-10"))


def test_replay_empty_window_returns_raises():
    idx = pd.bdate_range("2018-01-01", "2019-12-31")  # data ends before the window
    close = pd.DataFrame({"A": 100.0}, index=idx)
    p = PortfolioDef("p", _hold("A"), core_tickers=["A"], sleeve_universe=[], candidate=False)
    with pytest.raises(DataUnavailable, match="no returns"):
        replay_loss(_frames(close), p, _win("2020-01-07", "2020-01-10"))


def test_replay_other_value_errors_propagate():
    def build(data, keep):
        raise ValueError("boom")

    p = PortfolioDef("p", build, core_tickers=["A"], sleeve_universe=[], candidate=False)
    with pytest.raises(ValueError, match="boom") as ei:
        replay_loss(_frames(_long_close(A=100.0)), p, _win("2020-01-07", "2020-01-10"))
    assert not isinstance(ei.value, DataUnavailable)


def test_replay_real_engine_missing_price_is_data_unavailable():
    # A held ticker whose price goes NaN inside the window, weighted by a builder
    # that bypasses the priced() filter: the real run_backtest raises
    # "Missing price for a held position ...", which must surface as DataUnavailable.
    close = _long_close(A=100.0, B=50.0)
    close.loc["2020-01-08", "B"] = float("nan")
    p = PortfolioDef("p", _hold("B"), core_tickers=["A"], sleeve_universe=[], candidate=False)
    with pytest.raises(DataUnavailable, match="Missing price"):
        replay_loss(_frames(close), p, _win("2020-01-07", "2020-01-10"))


def test_replay_frames_end_at_window_end():
    close = _long_close(A=100.0)
    seen = {}

    def build(data, keep):
        seen["last"] = data["close"].index.max()
        return pd.DataFrame({"A": 1.0}, index=data["close"].index)

    p = PortfolioDef("p", build, core_tickers=["A"], sleeve_universe=[], candidate=False)
    replay_loss(_frames(close), p, _win("2020-01-07", "2020-01-08"))
    assert seen["last"] == pd.Timestamp("2020-01-08")


def test_replay_drops_unpriced_sleeve_tickers():
    close = _long_close(A=100.0, S1=50.0, S2=50.0)
    close.loc["2018-03-01", "S2"] = float("nan")
    got = {}

    def build(data, keep):
        got["keep"] = keep
        return pd.DataFrame({"A": 1.0}, index=data["close"].index)

    p = PortfolioDef("p", build, core_tickers=["A"], sleeve_universe=["S1", "S2"], candidate=True)
    _, detail = replay_loss(_frames(close), p, _win("2020-01-06", "2020-01-07"))
    assert got["keep"] == ["S1"]
    assert detail == {"sleeve_dropped": 1, "sleeve_dropped_share": 0.5}


def test_replay_unpriced_core_raises():
    close = _long_close(A=100.0)
    close.loc["2018-03-01", "A"] = float("nan")
    p = PortfolioDef("p", _hold("A"), core_tickers=["A"], sleeve_universe=[], candidate=False)
    with pytest.raises(DataUnavailable, match="core"):
        replay_loss(_frames(close), p, _win("2020-01-06", "2020-01-07"))


CRITERIA = {
    "periods": {
        "research": {"start": "2005-01-01", "end": "2018-12-31"},
        "validation": {"start": "2019-01-01", "end": "2022-12-31"},
        "holdout": {"start": "2023-01-01"},
    }
}


def test_replay_label():
    gfc, covid = _win("2007-10-09", "2009-03-09"), _win("2020-02-19", "2020-04-30")
    assert replay_label(False, gfc, CRITERIA) == "clean"
    assert replay_label(True, gfc, CRITERIA) == "in-sample"
    assert replay_label(True, covid, CRITERIA) == "validation-seen"
    assert replay_label(True, _win("2000-03-24", "2002-10-09"), CRITERIA) == "out-of-sample"


def test_run_stress_cells_labels_and_breach():
    idx = pd.bdate_range("2005-01-03", "2009-12-31")
    aaa = pd.Series(100.0, index=idx)
    aaa.loc["2008-01-02":] = 60.0  # one-day -40% step inside the gfc window
    close = pd.DataFrame({"AAA": aaa, "GLD": 100.0, "SPY": 100.0}, index=idx)
    data = _frames(close)
    cfg = StressConfig(
        windows=[
            _win("2003-01-02", "2003-06-30", replay=False, name="early"),  # before data
            _win("2007-10-09", "2009-03-09", replay=True, name="gfc"),
        ],
        hypotheticals=[Hypothetical("crash", {"equity": -0.5})],
        max_report_age_days=30,
    )
    core = PortfolioDef("chosen", _hold("AAA", 1.0), core_tickers=["AAA"])
    cand = PortfolioDef(
        "core+x",
        _hold("AAA", 1.0),
        core_tickers=["AAA"],
        sleeve_universe=["AAA", "ZZZ"],  # ZZZ has no prices
        candidate=True,
    )
    cells = run_stress(cfg, [core, cand], data, max_drawdown=0.35, criteria=CRITERIA)
    by = {(c.portfolio, c.scenario, c.mode): c for c in cells}

    assert ("chosen", "early", "replay") not in by  # frozen-only window
    early = by[("chosen", "early", "frozen")]
    assert early.loss is None
    assert early.breach is None
    assert "no prices" in early.unavailable
    for name in ("chosen", "core+x"):
        replay = by[(name, "gfc", "replay")]
        assert replay.unavailable is None
        assert replay.loss == pytest.approx(0.40, abs=1e-3)
        assert replay.breach is True
        frozen = by[(name, "gfc", "frozen")]
        assert frozen.unavailable is None
        assert frozen.loss == pytest.approx(0.40)
        assert frozen.breach is True
    assert by[("chosen", "gfc", "replay")].label == "clean"
    assert by[("core+x", "gfc", "replay")].label == "in-sample"
    assert by[("chosen", "gfc", "frozen")].label == "current-weights"
    crash = by[("chosen", "crash", "hypothetical")]
    assert crash.loss == pytest.approx(0.5)
    assert crash.breach is True
    assert crash.detail["latest_sleeve_dropped"] == 0
    assert by[("core+x", "crash", "hypothetical")].detail["latest_sleeve_dropped"] == 1
    assert by[("core+x", "gfc", "frozen")].detail["latest_sleeve_dropped"] == 1
    assert len(cells) == 2 * (1 + 2 + 1)


def test_run_stress_nan_latest_weights_make_static_cells_unavailable():
    idx = pd.bdate_range("2005-01-03", "2009-12-31")
    close = pd.DataFrame({"AAA": 100.0, "SPY": 100.0}, index=idx)

    def build(data, keep):
        w = pd.DataFrame({"AAA": 1.0}, index=data["close"].index)
        if data["close"].index[-1] == idx[-1]:  # only the full frame (today) gets NaN
            w.iloc[-1] = float("nan")
        return w

    cfg = StressConfig(
        windows=[_win("2007-10-09", "2009-03-09", replay=True, name="gfc")],
        hypotheticals=[Hypothetical("crash", {"equity": -0.5})],
        max_report_age_days=30,
    )
    p = PortfolioDef("chosen", build, core_tickers=["AAA"])
    cells = run_stress(cfg, [p], _frames(close), max_drawdown=0.35, criteria=CRITERIA)
    by = {(c.scenario, c.mode): c for c in cells}
    assert by[("gfc", "replay")].unavailable is None
    for key in (("gfc", "frozen"), ("crash", "hypothetical")):
        assert by[key].loss is None
        assert by[key].breach is None
        assert "NaN" in by[key].unavailable


NOW = pd.Timestamp("2026-10-03T12:00:00+00:00")
HASHES = {"stress.yaml": "a", "portfolio.yaml": "b", "paper.yaml": "c", "profile.yaml": "d"}


def _report(**over):
    rep = {
        "generated_at": "2026-10-01T12:00:00+00:00",
        "max_report_age_days": 30,
        "max_drawdown": 0.35,
        "hashes": dict(HASHES),
        "cells": [
            {
                "portfolio": "chosen",
                "scenario": "gfc_2008",
                "mode": "frozen",
                "loss": 0.2,
                "breach": False,
            },
        ],
    }
    rep.update(over)
    return rep


def test_stress_config_paths_and_hashes():
    paths = stress_config_paths(ROOT)
    assert set(paths) == set(HASHES)
    hashes = file_hashes(paths)
    assert all(len(h) == 64 for h in hashes.values())


def test_no_warnings_when_fresh_and_clean():
    assert stress_warnings(_report(), HASHES, NOW) == []


def test_naive_generated_at_is_treated_as_utc():
    assert stress_warnings(_report(generated_at="2026-10-01T12:00:00"), HASHES, NOW) == []
    (msg,) = stress_warnings(_report(generated_at="2026-08-01T00:00:00"), HASHES, NOW)
    assert "days old" in msg


def test_missing_report_warns():
    (msg,) = stress_warnings(None, HASHES, NOW)
    assert "missing" in msg


def test_old_report_warns():
    (msg,) = stress_warnings(_report(generated_at="2026-08-01T00:00:00+00:00"), HASHES, NOW)
    assert "days old" in msg


def test_changed_config_warns():
    (msg,) = stress_warnings(_report(), {**HASHES, "portfolio.yaml": "zzz"}, NOW)
    assert "stale" in msg
    assert "portfolio.yaml" in msg


def test_breach_warns():
    cells = [
        {
            "portfolio": "chosen",
            "scenario": "tech_crash",
            "mode": "hypothetical",
            "loss": 0.48,
            "breach": True,
        }
    ]
    (msg,) = stress_warnings(_report(cells=cells), HASHES, NOW)
    assert "BREACH" in msg
    assert "tech_crash" in msg
    assert "48.0%" in msg


def test_daily_check_stress_warnings_missing_report(tmp_path):
    msgs = daily_check._stress_warnings(tmp_path / "nope.json")
    assert len(msgs) == 1
    assert "missing" in msgs[0]


def test_daily_check_stress_warnings_reports_breach(tmp_path):
    report = {
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "max_report_age_days": 30,
        "max_drawdown": 0.35,
        "hashes": file_hashes(stress_config_paths(ROOT)),
        "cells": [
            {
                "portfolio": "chosen",
                "scenario": "tech_crash",
                "mode": "hypothetical",
                "loss": 0.48,
                "breach": True,
            }
        ],
    }
    path = tmp_path / "stress.json"
    path.write_text(json.dumps(report))
    (msg,) = daily_check._stress_warnings(path)
    assert msg.startswith("BREACH")


UNREADABLE = "stress report unreadable: re-run `pixi run stress`"


@pytest.mark.parametrize("text", ["{bad json", "{}"])
def test_daily_check_stress_warnings_unreadable_report(tmp_path, text):
    path = tmp_path / "stress.json"
    path.write_text(text)
    assert daily_check._stress_warnings(path) == [UNREADABLE]


CORE_CFG = {"fn": "core_trend", "params": {"risk_on": "QQQ", "risk_off": "GLD", "lookback": 3}}


def _stub_daily_check(monkeypatch, ok: bool) -> None:
    status = "ok" if ok else "fail"
    report = HealthReport(
        as_of=pd.Timestamp("2026-09-25"), checks=(CheckResult("data_arrived", status, ""),)
    )
    monkeypatch.setattr(daily_check, "load_universe", lambda: {"tickers": ["QQQ", "GLD"]})
    monkeypatch.setattr(
        daily_check,
        "load_portfolio_config",
        lambda path: {"core": CORE_CFG, "sleeve": {"strategies": []}},
    )
    monkeypatch.setattr(
        daily_check,
        "load_profile_with_hash",
        lambda: ({"capital_split": {"core": 0.8, "sleeve": 0.2}}, "hash"),
    )
    monkeypatch.setattr(daily_check, "load_risk_limits", lambda profile: None)
    monkeypatch.setattr(daily_check, "run_daily_health", lambda **kwargs: report)
    monkeypatch.setattr(
        daily_check, "_stress_warnings", lambda: ["BREACH chosen tech_crash: loss 48.0%"]
    )


def test_daily_check_exit_status_ignores_stress_warnings(tmp_path, monkeypatch):
    _stub_daily_check(monkeypatch, ok=True)
    out = tmp_path / "h.json"
    assert daily_check.main(["--out", str(out)]) == 0
    assert json.loads(out.read_text())["stress_warnings"]


def test_daily_check_failed_report_exits_1_regardless_of_warnings(tmp_path, monkeypatch):
    _stub_daily_check(monkeypatch, ok=False)
    out = tmp_path / "h.json"
    assert daily_check.main(["--out", str(out)]) == 1
    assert json.loads(out.read_text())["stress_warnings"]


def _load_stress_cli():
    spec = importlib.util.spec_from_file_location("stress_cli", ROOT / "scripts" / "stress.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


stress_cli = _load_stress_cli()


def test_restrict_drops_tickers_not_kept():
    params = {"tickers": ["A", "B", "C"], "lookback": 5}
    assert stress_cli._restrict(params, ["A", "C", "Z"]) == {"tickers": ["A", "C"], "lookback": 5}


def test_restrict_leaves_params_without_tickers_unchanged():
    params = {"risk_on": "QQQ", "lookback": 3}
    assert stress_cli._restrict(params, ["A"]) == params


def test_portfolios_empty_sleeve_is_core_only():
    cfg = {"core": CORE_CFG, "sleeve": {"strategies": []}}
    (chosen,) = stress_cli._portfolios(cfg, [], {"core": 0.8, "sleeve": 0.2})
    assert chosen.name == "chosen"
    assert chosen.candidate is False
    idx = pd.bdate_range("2020-01-01", periods=12)
    close = pd.DataFrame(
        {
            "QQQ": [100.0 + i for i in range(12)],
            "GLD": [50.0] * 12,
        },
        index=idx,
    )
    combined = chosen.build({"close": close}, [])
    assert list(combined.index) == list(idx)
    assert (combined.sum(axis=1) <= 0.8 + 1e-9).all()
    assert combined.to_numpy().sum() > 0  # core actually holds something


def test_stress_cli_main_fails_loudly_on_unpriced_core_ticker(tmp_path, monkeypatch):
    idx = pd.bdate_range("2020-01-01", periods=5)

    def fake_ohlcv(tickers, refresh=False):
        close = pd.DataFrame(dict.fromkeys(tickers, 100.0), index=idx)
        close.iloc[-1] = float("nan")  # every core ticker (incl. QQQ) unpriced today
        return {"close": close}

    class FakeLedger:
        def __init__(self, path):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def boom(*args, **kwargs):
        raise AssertionError("run_stress must not be called")

    monkeypatch.setattr(stress_cli, "load_ohlcv", fake_ohlcv)
    monkeypatch.setattr(stress_cli, "Ledger", FakeLedger)
    monkeypatch.setattr(stress_cli, "load_paper_config", lambda path: ({"candidates": []}, "h"))
    monkeypatch.setattr(stress_cli, "run_stress", boom)
    out = tmp_path / "stress.json"
    assert stress_cli.main(["--out", str(out)]) == 1
    assert not out.exists()
