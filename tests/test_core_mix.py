"""Tests for the core_mix strategy family (static or trend-switched fixed mixes).
Offline; small hand-built frames and synthetic prices only.
Spec: docs/superpowers/specs/2026-10-03-core-compare-design.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qrl.checks import assert_causal
from qrl.data import synthetic_prices
from qrl.strategies import REGISTRY
from qrl.strategies.core_mix import core_mix, core_mix_tickers
from qrl.strategies.core_trend import core_trend


def _close(**cols: list[float]) -> pd.DataFrame:
    n = len(next(iter(cols.values())))
    return pd.DataFrame(cols, index=pd.bdate_range("2020-01-01", periods=n))


def test_core_mix_static_weights_are_constant():
    close = _close(SPY=[1.0] * 4, IEF=[1.0] * 4)
    w = core_mix(close, {"SPY": 0.6, "IEF": 0.4})
    assert list(w.columns) == ["SPY", "IEF"]
    assert (w["SPY"] == 0.6).all()
    assert (w["IEF"] == 0.4).all()


def test_core_mix_static_is_nan_until_every_held_ticker_is_priced():
    nan = float("nan")
    close = _close(SPY=[1.0] * 4, IEF=[nan, nan, 1.0, 1.0])
    w = core_mix(close, {"SPY": 0.6, "IEF": 0.4})
    assert w.iloc[:2].isna().all().all()
    assert w.iloc[2:].notna().all().all()


def test_core_mix_switches_on_and_off_on_a_hand_built_series():
    # SPY 3-day SMA: nan, nan, 10.00, 10.67, 10.00, 9.67, 9.33
    # SPY close:     10,  10,  10,    12,    8,     9,    11
    # above SMA:      -    -    no     yes    no     no    yes
    close = _close(SPY=[10.0, 10.0, 10.0, 12.0, 8.0, 9.0, 11.0], IEF=[100.0] * 7, GLD=[100.0] * 7)
    w = core_mix(
        close,
        risk_on={"SPY": 0.6, "IEF": 0.4},
        risk_off={"IEF": 0.5, "GLD": 0.5},
        signal="SPY",
        lookback=3,
    )
    on, off, nan = [0.6, 0.4, 0.0], [0.0, 0.5, 0.5], [np.nan] * 3
    expected = pd.DataFrame(
        [nan, nan, off, on, off, off, on], index=close.index, columns=["SPY", "IEF", "GLD"]
    )
    pd.testing.assert_frame_equal(w, expected)


def test_core_mix_one_ticker_each_matches_core_trend():
    _, close = synthetic_prices(["QQQ", "GLD"], start="2010-01-01", end="2014-12-31")
    mixed = core_mix(close, {"QQQ": 1.0}, risk_off={"GLD": 1.0}, signal="QQQ", lookback=50)
    pd.testing.assert_frame_equal(mixed, core_trend(close, "QQQ", "GLD", 50))


def test_core_mix_weights_are_causal():
    _, close = synthetic_prices(["QQQ", "GLD", "SPY"], start="2010-01-01", end="2014-12-31")
    params = {
        "risk_on": {"SPY": 0.6, "QQQ": 0.4},
        "risk_off": {"GLD": 1.0},
        "signal": "SPY",
        "lookback": 50,
    }
    assert_causal(lambda c: core_mix(c, **params), close)


@pytest.mark.parametrize(
    ("risk_on", "risk_off"),
    [
        ({"SPY": 0.7, "IEF": 0.5}, None),
        ({"SPY": 1.0}, {"IEF": 0.6, "GLD": 0.6}),
    ],
)
def test_core_mix_rejects_weights_summing_above_one(risk_on, risk_off):
    close = _close(SPY=[1.0] * 5, IEF=[1.0] * 5, GLD=[1.0] * 5)
    extra = {} if risk_off is None else {"risk_off": risk_off, "signal": "SPY", "lookback": 2}
    with pytest.raises(ValueError, match="above 1"):
        core_mix(close, risk_on, **extra)


def test_core_mix_rejects_negative_weight():
    close = _close(SPY=[1.0] * 5, IEF=[1.0] * 5)
    with pytest.raises(ValueError, match="negative"):
        core_mix(close, {"SPY": 1.2, "IEF": -0.2})


def test_core_mix_switching_requires_signal_and_lookback():
    close = _close(SPY=[1.0] * 5, IEF=[1.0] * 5)
    with pytest.raises(ValueError, match="signal and lookback"):
        core_mix(close, {"SPY": 1.0}, risk_off={"IEF": 1.0})


def test_core_mix_static_mix_rejects_signal():
    close = _close(SPY=[1.0] * 5)
    with pytest.raises(ValueError, match="static mix"):
        core_mix(close, {"SPY": 1.0}, signal="SPY")


def test_core_mix_tickers_include_signal_but_columns_do_not():
    static = {"risk_on": {"SPY": 0.6, "IEF": 0.4}}
    assert core_mix_tickers(static) == ["SPY", "IEF"]
    switching = {
        "risk_on": {"SPY": 0.6, "IEF": 0.4},
        "risk_off": {"IEF": 0.5, "GLD": 0.5},
        "signal": "QQQ",
        "lookback": 3,
    }
    assert REGISTRY["core_mix"].tickers(switching) == ["SPY", "IEF", "GLD", "QQQ"]
    close = _close(SPY=[1.0] * 5, IEF=[1.0] * 5, GLD=[1.0] * 5, QQQ=[1.0] * 5)
    w = core_mix(close, **switching)
    assert list(w.columns) == ["SPY", "IEF", "GLD"]
