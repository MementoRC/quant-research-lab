"""Tests for qrl.broker_gate (spec "Evening run" step 1 and "Refusals")."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from qrl.broker import AccountInfo, FakeBroker, Holding, OpenOrder
from qrl.broker_config import BrokerConfig
from qrl.broker_gate import gate, paper_refusal

CFG = BrokerConfig(True, "127.0.0.1", 4002, 17, "DU123", 0.01, 0.005)
PAPER = AccountInfo("DU123", "USD", True, 4002)
QQQ = Holding("QQQ", "STK", "USD", Decimal("10"))


def _refusal(broker: FakeBroker, cfg: BrokerConfig = CFG) -> str:
    refusal, _ = gate(cfg, broker)
    assert refusal is not None
    return refusal


@pytest.mark.parametrize(
    ("info", "message"),
    [
        (replace(PAPER, paper=False), "paper=False"),
        (replace(PAPER, port=4001), "port 4001"),
        (replace(PAPER, port=7496), "port 7496"),
        (replace(PAPER, account_id="U1234567"), "DU"),
    ],
)
def test_each_paper_check_part_fails_on_its_own(info, message):
    assert message in paper_refusal(info)
    assert message in _refusal(FakeBroker(info=info))


def test_paper_account_passes_the_paper_check():
    assert paper_refusal(PAPER) is None


def test_non_usd_base_currency_is_refused():
    assert "base currency" in _refusal(FakeBroker(info=replace(PAPER, base_currency="EUR")))


@pytest.mark.parametrize(
    "holding",
    [Holding("ES", "FUT", "USD", Decimal("1")), Holding("SAP", "STK", "EUR", Decimal("1"))],
)
def test_non_stk_or_non_usd_position_is_refused(holding):
    assert f"not STK in USD: {holding.symbol}" in _refusal(FakeBroker(held=[holding]))


def test_fractional_quantity_is_refused():
    broker = FakeBroker(held=[Holding("QQQ", "STK", "USD", Decimal("1.5"))])
    assert "whole number" in _refusal(broker)


def test_open_order_is_refused_and_never_cancelled():
    broker = FakeBroker(pending=[OpenOrder("QQQ", "BUY", 1, 99)])
    assert "open order" in _refusal(broker)
    assert broker.cancel_all_calls == 0
    assert broker.open_orders() == [OpenOrder("QQQ", "BUY", 1, 99)]


def test_gate_order_enabled_paper_account_open_orders():
    worst = FakeBroker(
        info=AccountInfo("U1", "EUR", False, 4001),
        held=[Holding("ES", "FUT", "EUR", Decimal("0.5"))],
        pending=[OpenOrder("ES", "BUY", 1, 1)],
    )
    assert "disabled" in _refusal(worst, replace(CFG, enabled=False))
    assert "paper" in _refusal(worst)
    worst.info = replace(PAPER, base_currency="EUR")
    assert "base currency" in _refusal(worst)
    worst.info = PAPER
    assert "not STK in USD" in _refusal(worst)
    worst.held = [Holding("QQQ", "STK", "USD", Decimal("0.5"))]
    assert "whole number" in _refusal(worst)
    worst.held = [QQQ]
    assert "open order" in _refusal(worst)


def test_clean_account_passes_and_returns_its_holdings():
    assert gate(CFG, FakeBroker(held=[QQQ])) == (None, [QQQ])
