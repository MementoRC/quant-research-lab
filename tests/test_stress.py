"""Tests for the stress-scenario diagnostic (qrl.stress, scripts/stress.py
wiring into scripts/daily_check.py). Offline; small hand-built frames only.
Spec: docs/superpowers/specs/2026-10-03-stress-scenarios-design.md.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

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
  - {name: h1, equity: -0.5, gold: -0.2}
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
    assert cfg.hypotheticals[0].shocks == {"equity": -0.5, "gold": -0.2}


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
    text = GOOD.replace("gold: -0.2", "bonds: -0.2")
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
    assert detail["proxied_share"] == {"equity": 0.0, "gold": 0.0}


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
    assert detail["proxied_share"] == {"equity": pytest.approx(0.6), "gold": pytest.approx(0.4)}


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
    assert detail["proxied_share"] == {"equity": 0.0, "gold": 0.0}


def test_all_cash_weights_lose_nothing():
    idx = pd.bdate_range("2001-01-08", periods=3)
    close = pd.DataFrame({"A": [100.0, 50.0, 25.0]}, index=idx)
    w = pd.Series({"A": 0.0})
    loss, _ = frozen_loss(w, close, _win("2001-01-08", "2001-01-10"))
    assert loss == pytest.approx(0.0)
    assert hypothetical_loss(w, Hypothetical("x", {"equity": -0.5, "gold": -0.2})) == pytest.approx(
        0.0
    )


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
