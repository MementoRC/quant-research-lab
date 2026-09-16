import numpy as np
import pytest

from qrl.checks import assert_causal
from qrl.data import synthetic_prices
from qrl.strategies import REGISTRY
from qrl.strategies.core_trend import core_trend

EXAMPLE_PARAMS = {
    "buy_and_hold": {"ticker": "QQQ"},
    "core_trend": {"risk_on": "QQQ", "risk_off": "GLD", "lookback": 200},
}


@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_every_registered_strategy_is_causal(name):
    assert name in EXAMPLE_PARAMS, f"Add example params for '{name}' to this test."
    _, close = synthetic_prices(["QQQ", "GLD", "SPY"], start="2010-01-01", end="2014-12-31")
    params = EXAMPLE_PARAMS[name]
    assert_causal(lambda c: REGISTRY[name].weights(c, **params), close)


def test_causality_check_catches_peeking():
    _, close = synthetic_prices(["QQQ", "GLD"], start="2010-01-01", end="2014-12-31")

    def cheater(c):
        # A classic real-world bug: a centered moving average uses future closes.
        price = c["QQQ"]
        sma = price.rolling(21, center=True).mean()
        w = core_trend(c)
        above = price > sma
        ok = w["QQQ"].notna() & sma.notna()
        w.loc[ok & above, ["QQQ", "GLD"]] = [1.0, 0.0]
        w.loc[ok & ~above, ["QQQ", "GLD"]] = [0.0, 1.0]
        return w

    with pytest.raises(AssertionError, match="Look-ahead"):
        assert_causal(cheater, close)


def test_core_trend_switches_on_sma_cross():
    _, close = synthetic_prices(["QQQ", "GLD"], start="2010-01-01", end="2014-12-31")
    w = core_trend(close, lookback=50)
    sma = close["QQQ"].rolling(50).mean()
    valid = w.dropna()
    above = (close["QQQ"] > sma).loc[valid.index]
    assert (valid.loc[above, "QQQ"] == 1).all()
    assert (valid.loc[~above, "GLD"] == 1).all()
    assert w.iloc[:49].isna().all().all()
    assert np.allclose(valid.sum(axis=1), 1.0)
