"""Tests for qrl.broker: order/position types, to_positions and FakeBroker."""

from __future__ import annotations

from decimal import Decimal

import pytest

from qrl.broker import (
    FakeBroker,
    Holding,
    OpenOrder,
    Order,
    Position,
    SubmittedOrder,
    to_positions,
)


@pytest.mark.parametrize(
    ("side", "shares", "message"),
    [
        ("HOLD", 1, "side"),
        ("BUY", 0, "shares"),
        ("SELL", -3, "shares"),
        ("BUY", 1.5, "shares"),
        ("BUY", True, "shares"),
    ],
)
def test_order_rejects_bad_side_or_shares(side, shares, message):
    with pytest.raises(ValueError, match=message):
        Order("QQQ", side, shares)


def test_order_delta_is_signed():
    assert Order("QQQ", "BUY", 5).delta == 5
    assert Order("QQQ", "SELL", 5).delta == -5


@pytest.mark.parametrize(("status", "delta"), [("submitted", 5), ("rejected", 0), ("cancelled", 0)])
def test_rejected_or_cancelled_orders_count_as_zero(status, delta):
    assert SubmittedOrder(Order("QQQ", "BUY", 5), 1, status).delta == delta


def test_to_positions_keeps_whole_shares():
    holdings = [
        Holding("QQQ", "STK", "USD", Decimal("158")),
        Holding("GLD", "STK", "USD", Decimal("-2")),
    ]
    assert to_positions(holdings) == [Position("QQQ", 158), Position("GLD", -2)]


def test_to_positions_refuses_a_fraction():
    with pytest.raises(ValueError, match="whole number"):
        to_positions([Holding("QQQ", "STK", "USD", Decimal("1.5"))])


def test_fake_broker_submit_queues_orders_and_rejects_listed_symbols():
    broker = FakeBroker(cash_usd=1000.0, reject=frozenset({"GLD"}))
    subs = broker.submit([Order("QQQ", "BUY", 2), Order("GLD", "BUY", 1)])
    assert [(s.order_id, s.status) for s in subs] == [(1, "submitted"), (2, "rejected")]
    assert broker.open_orders() == [OpenOrder("QQQ", "BUY", 2, 1)]
    assert broker.submitted == subs


def test_fake_broker_fill_all_moves_shares_and_cash():
    broker = FakeBroker(cash_usd=1000.0, held=[Holding("GLD", "STK", "USD", Decimal("3"))])
    broker.submit([Order("GLD", "SELL", 3), Order("QQQ", "BUY", 2)])
    broker.fill_all({"GLD": 100.0, "QQQ": 400.0})
    assert broker.holdings() == [Holding("QQQ", "STK", "USD", Decimal("2"))]
    assert broker.cash() == pytest.approx(1000.0 + 300.0 - 800.0)
    assert broker.open_orders() == []


def test_fake_broker_fill_all_keeps_existing_currency():
    broker = FakeBroker(held=[Holding("VOD", "STK", "GBP", Decimal("3"))])
    broker.submit([Order("VOD", "BUY", 2)])
    broker.fill_all({"VOD": 10.0})
    assert broker.holdings() == [Holding("VOD", "STK", "GBP", Decimal("5"))]


def test_fake_broker_fill_all_needs_a_price():
    broker = FakeBroker()
    broker.submit([Order("QQQ", "BUY", 1)])
    with pytest.raises(ValueError, match="no fill price for QQQ"):
        broker.fill_all({})


def test_fake_broker_flatten_cancels_first_then_sells_longs_only():
    broker = FakeBroker(
        held=[
            Holding("QQQ", "STK", "USD", Decimal("4")),
            Holding("GLD", "STK", "USD", Decimal("-1")),
        ]
    )
    broker.submit([Order("QQQ", "BUY", 9)])
    subs = broker.flatten()
    assert broker.cancel_all_calls == 1
    assert [s.order for s in subs] == [Order("QQQ", "SELL", 4)]
    assert broker.open_orders() == [OpenOrder("QQQ", "SELL", 4, subs[0].order_id)]
