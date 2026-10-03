"""Tests for the stress-scenario diagnostic (qrl.stress, scripts/stress.py
wiring into scripts/daily_check.py). Offline; small hand-built frames only.
Spec: docs/superpowers/specs/2026-10-03-stress-scenarios-design.md.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from qrl.stress import (
    Hypothetical,
    Window,
    asset_class,
    frozen_loss,
    hypothetical_loss,
    load_stress_config,
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
    with pytest.raises(ValueError, match="no prices"):
        frozen_loss(pd.Series({"SPY": 1.0}), close, _win("2001-01-08", "2001-01-09"))
