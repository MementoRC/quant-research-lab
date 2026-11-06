"""Tests for qrl.broker_gate (spec "Evening run" step 1 and "Refusals")."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from qrl.broker import AccountInfo, Broker, FakeBroker, Holding, OpenOrder
from qrl.broker_config import BrokerConfig
from qrl.broker_gate import connection_refusal, gate, paper_refusal

CFG = BrokerConfig(True, "127.0.0.1", 4002, 17, "DU123", 0.01, 0.005)
PAPER = AccountInfo("DU123", "USD", True, 4002)
QQQ = Holding("QQQ", "STK", "USD", Decimal("10"))


def _refusal(broker: Broker, cfg: BrokerConfig = CFG) -> str:
    refusal, _ = gate(cfg, broker)
    assert refusal is not None
    return refusal


@pytest.mark.parametrize(
    ("info", "message"),
    [
        (replace(PAPER, paper=False), "paper=False"),
        (replace(PAPER, port=4001), "port 4001"),
        (replace(PAPER, port=7496), "port 7496"),
        (
            replace(PAPER, account_id="U1234567"),
            "account id 'U1234567' does not start with DU",
        ),
    ],
)
def test_each_paper_check_part_fails_on_its_own(info, message):
    assert message in paper_refusal(info)
    assert message in _refusal(FakeBroker(info=info))


@pytest.mark.parametrize("account_id", ["du123", "", " DU1", "DU", None])
def test_malformed_account_id_is_refused(account_id):
    info = replace(PAPER, account_id=account_id)
    expected = f"not a paper connection: account id {account_id!r} does not start with DU"
    assert paper_refusal(info) == expected
    assert _refusal(FakeBroker(info=info)) == expected


def test_account_other_than_the_configured_one_is_refused():
    refusal = _refusal(FakeBroker(info=replace(PAPER, account_id="DU999"), held=[QQQ]))
    assert "'DU999'" in refusal
    assert "'DU123'" in refusal


def test_connection_refusal_runs_the_paper_check_then_the_account_match():
    assert connection_refusal(PAPER, CFG) is None
    assert connection_refusal(replace(PAPER, port=4001), CFG) == paper_refusal(
        replace(PAPER, port=4001)
    )
    other = replace(PAPER, account_id="DU999")
    assert connection_refusal(other, CFG) == (
        "account 'DU999' is not the configured account 'DU123'"
    )
    live_other = replace(PAPER, account_id="U999")  # paper check wins over the match
    assert connection_refusal(live_other, CFG) == paper_refusal(live_other)


class _RecordingBroker:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def account(self) -> AccountInfo:
        self.calls.append("account")
        return PAPER

    def holdings(self) -> list[Holding]:
        self.calls.append("holdings")
        return []

    def open_orders(self) -> list[OpenOrder]:
        self.calls.append("open_orders")
        return []


def test_disabled_gate_never_touches_the_broker():
    broker = _RecordingBroker()
    assert "disabled" in _refusal(broker, replace(CFG, enabled=False))
    assert broker.calls == []


def test_infinite_quantity_is_refused():
    broker = FakeBroker(held=[Holding("QQQ", "STK", "USD", Decimal("Infinity"))])
    assert "whole number" in _refusal(broker)


def test_one_bad_holding_among_good_ones_is_refused():
    broker = FakeBroker(held=[QQQ, Holding("SPY", "STK", "USD", Decimal("2.5"))])
    assert "whole number of shares: SPY" in _refusal(broker)


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
