"""Tests for qrl.rebalance.plan (spec "Evening run" steps 4-5, "Refusals")."""

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from qrl.broker import Order, Position
from qrl.broker_config import BrokerConfig
from qrl.rebalance import plan
from qrl.risk import RiskLimits

CFG = BrokerConfig(True, "127.0.0.1", 4002, 17, "DU123", 0.01, 0.005)
LIMITS = RiskLimits(1.0, 1.0, 0.0, 0.04, 30)


def _w(**weights: float) -> pd.Series:
    return pd.Series(weights, dtype=float)


def test_targets_are_floored_python_ints():
    result = plan(_w(QQQ=0.8, GLD=0.0), _w(QQQ=333.0, GLD=200.0), [], 100_000.0, CFG, LIMITS)
    assert result.targets == {"QQQ": 237}  # floor(0.8 * 99_000 / 333) = floor(237.84)
    assert type(result.targets["QQQ"]) is int
    assert result.orders == (Order("QQQ", "BUY", 237),)
    assert result.equity == 100_000.0


def test_cash_buffer_is_left_uninvested():
    closes = _w(QQQ=100.0)
    none = plan(_w(QQQ=1.0), closes, [], 10_000.0, replace(CFG, cash_buffer=0.0), LIMITS)
    tenth = plan(_w(QQQ=1.0), closes, [], 10_000.0, replace(CFG, cash_buffer=0.10), LIMITS)
    assert (none.targets["QQQ"], tenth.targets["QQQ"]) == (100, 90)


def test_equity_is_cash_plus_held_shares_at_our_close():
    result = plan(_w(QQQ=0.8), _w(QQQ=500.0), [Position("QQQ", 158)], 21_000.0, CFG, LIMITS)
    assert result.equity == 100_000.0
    assert result.orders == ()


def test_trade_inside_the_deadband_is_skipped():
    # target floor(0.805 * 99_000 / 500) = 159, delta 1 share = $500 < 1% of $100k
    result = plan(
        _w(QQQ=0.805), _w(QQQ=500.0), [Position("QQQ", 158)], 21_000.0,
        replace(CFG, deadband=0.01), LIMITS,
    )  # fmt: skip
    assert result.orders == ()
    assert [s.symbol for s in result.skipped] == ["QQQ"]
    assert "deadband" in result.skipped[0].reason


def test_trade_at_the_deadband_goes():
    # delta $500 is not below 0.5% of $100k ($500)
    result = plan(_w(QQQ=0.805), _w(QQQ=500.0), [Position("QQQ", 158)], 21_000.0, CFG, LIMITS)
    assert result.orders == (Order("QQQ", "BUY", 1),)


def test_full_exit_always_goes_even_inside_the_deadband():
    result = plan(
        _w(QQQ=0.0, GLD=0.0), _w(QQQ=500.0, GLD=200.0), [Position("GLD", 2)], 99_600.0, CFG, LIMITS
    )
    assert result.orders == (Order("GLD", "SELL", 2),)


def test_sells_are_listed_before_buys():
    result = plan(
        _w(AAA=0.5, ZZZ=0.0),
        _w(AAA=100.0, ZZZ=100.0),
        [Position("ZZZ", 100)],
        90_000.0,
        CFG,
        LIMITS,
    )
    assert result.orders == (Order("ZZZ", "SELL", 100), Order("AAA", "BUY", 495))


def test_unheld_zero_weight_symbol_is_ignored():
    result = plan(_w(QQQ=0.0, GLD=0.0), _w(QQQ=500.0, GLD=200.0), [], 1_000.0, CFG, LIMITS)
    assert (result.orders, result.skipped, result.refusals) == ((), (), ())
