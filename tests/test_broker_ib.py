"""qrl.broker_ib against a mocked gateway (AsyncMock). Runs only where
hb-market-connector is installed: `pixi run -e broker pytest tests/test_broker_ib.py`."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("market_connector")

from market_connector.contracts.instrument import InstrumentRef, InstrumentType  # noqa: E402
from market_connector.exchanges.interactive_brokers.exceptions import CancelAllError  # noqa: E402
from market_connector.exchanges.interactive_brokers.transport import IbAccountSummary  # noqa: E402
from market_connector.orders import HBOrder, OrderType, TimeInForce, TradeType  # noqa: E402

from qrl.broker import AccountInfo, Holding, OpenOrder, Order, SubmittedOrder  # noqa: E402
from qrl.broker_config import BrokerConfig  # noqa: E402
from qrl.broker_gate import account_refusal, connection_refusal  # noqa: E402
from qrl.broker_ib import IbBroker, connection_spec  # noqa: E402

CFG = BrokerConfig(True, "10.0.0.5", 4002, 17, "DU123")


def _summary(
    currency: str,
    net_liq: str | None = None,
    cash: str | None = None,
    account: str = "DU123",
) -> IbAccountSummary:
    def dec(x: str | None) -> Decimal | None:
        return None if x is None else Decimal(x)

    return IbAccountSummary(account, currency, dec(net_liq), None, dec(cash))


# A USD-base paper account: IB reports NetLiquidation only in the base currency.
USD_BASE = {
    "USD": _summary("USD", net_liq="100000", cash="1234.5"),
    "BASE": _summary("BASE", cash="1234.5"),
}


def _pos(symbol: str, qty: str, sec_type: str = "STK", currency: str = "USD") -> SimpleNamespace:
    return SimpleNamespace(
        symbol=symbol, sec_type=sec_type, currency=currency, quantity=Decimal(qty)
    )


def _gateway(positions=(), summaries=USD_BASE, open_orders=(), managed=("DU123",)) -> MagicMock:
    gw = MagicMock()
    # The connector's ib_async IB instance: IB's own managed-accounts list, and the
    # all-open-orders request the adapter repeats before reading open orders.
    gw.unified_transport._ib.managedAccounts = MagicMock(return_value=list(managed))
    gw.unified_transport._ib.reqAllOpenOrdersAsync = AsyncMock(return_value=[])
    gw.start = AsyncMock()
    gw.stop = AsyncMock()
    gw.get_positions = AsyncMock(return_value=list(positions))
    gw.get_account_summary = AsyncMock(
        side_effect=lambda currency=None: summaries[
            "BASE" if currency is None else currency.upper()
        ]
    )
    gw.get_balance = AsyncMock(return_value=Decimal("999999"))
    gw.get_fills = AsyncMock(return_value=[])
    gw.cancel_all = AsyncMock(return_value=[])
    gw.get_open_orders = MagicMock(return_value=list(open_orders))
    ids = iter(range(100, 200))
    gw.place_order = AsyncMock(
        side_effect=lambda ref, order, **kw: SimpleNamespace(order_id=next(ids), status="submitted")
    )
    return gw


def _connected(gw: MagicMock) -> IbBroker:
    return IbBroker(CFG, build=lambda spec: gw)


def test_connection_spec_is_paper_and_fetches_all_open_orders():
    spec = connection_spec(CFG)
    assert (spec.host, spec.port, spec.client_id, spec.account_id) == (
        "10.0.0.5",
        4002,
        17,
        "DU123",
    )
    assert spec.paper is True
    assert spec.fetch_all_open_orders is True


def test_one_start_and_one_stop_per_run_across_many_calls():
    gw = _gateway()
    with _connected(gw) as broker:
        broker.account()
        broker.holdings()
        broker.open_orders()
        broker.cash()
        broker.submit([Order("QQQ", "BUY", 1)])
        broker.submit([Order("GLD", "BUY", 1)])
    assert (gw.start.await_count, gw.stop.await_count) == (1, 1)


def test_the_gateway_is_stopped_and_the_loop_closed_on_error():
    gw = _gateway()
    gw.get_positions = AsyncMock(side_effect=RuntimeError("socket"))
    broker = _connected(gw)
    with pytest.raises(RuntimeError, match="socket"), broker:
        broker.holdings()
    gw.stop.assert_awaited_once()
    with pytest.raises(RuntimeError, match="not connected"):
        broker.holdings()


def test_calls_outside_the_with_block_are_refused():
    with pytest.raises(RuntimeError, match="not connected"):
        _connected(_gateway()).cash()


def test_a_failed_connect_propagates_and_leaves_the_broker_unconnected():
    gw = _gateway()
    gw.start = AsyncMock(side_effect=ConnectionRefusedError("refused"))
    broker = _connected(gw)
    with pytest.raises(ConnectionRefusedError), broker:
        pytest.fail("the with body must not run")
    with pytest.raises(RuntimeError, match="not connected"):
        broker.cash()


def test_holdings_map_ib_positions():
    gw = _gateway(positions=[_pos("QQQ", "158"), _pos("ES", "1", sec_type="FUT")])
    with _connected(gw) as broker:
        assert broker.holdings() == [
            Holding("QQQ", "STK", "USD", Decimal("158")),
            Holding("ES", "FUT", "USD", Decimal("1")),
        ]


def test_cash_is_the_usd_summarys_total_cash_value_never_available_funds():
    gw = _gateway()
    with _connected(gw) as broker:
        assert broker.cash() == 1234.5
    gw.get_account_summary.assert_awaited_with("USD")
    gw.get_balance.assert_not_called()
    gw.get_fills.assert_not_called()


def test_unreported_total_cash_value_raises_lookup_error_instead_of_falling_back():
    gw = _gateway(summaries={**USD_BASE, "USD": _summary("USD", net_liq="100000", cash=None)})
    with _connected(gw) as broker, pytest.raises(LookupError, match="TotalCashValue"):
        broker.cash()
    gw.get_balance.assert_not_called()


def _reporting(account: str, managed: tuple[str, ...] | None = None) -> MagicMock:
    return _gateway(
        summaries={**USD_BASE, "USD": _summary("USD", "1", "2", account=account)},
        managed=(account,) if managed is None else managed,
    )


def test_an_empty_managed_accounts_list_fails_closed():
    with (
        _connected(_gateway(managed=())) as broker,
        pytest.raises(RuntimeError, match="no managed"),
    ):
        broker.account()


def test_an_unreadable_managed_accounts_list_fails_closed():
    gw = _gateway()
    gw.unified_transport._ib.managedAccounts = MagicMock(side_effect=OSError("down"))
    with _connected(gw) as broker, pytest.raises(RuntimeError, match="managed accounts"):
        broker.account()


def test_a_configured_id_absent_from_the_managed_list_is_refused_by_the_gate():
    # The connector echoes the configured id in the summary; IB manages another account.
    with _connected(_gateway(managed=("DU555",))) as broker:
        info = broker.account()
    assert info.account_id == "DU555"
    assert "not the configured account" in connection_refusal(info, CFG)


def test_a_mixed_live_and_paper_login_is_not_paper():
    with _connected(_gateway(managed=("DU123", "U777"))) as broker:
        info = broker.account()
    assert (info.account_id, info.paper) == ("DU123", False)
    assert "not a paper connection" in connection_refusal(info, CFG)


def test_all_du_managed_accounts_containing_the_configured_id_pass():
    with _connected(_gateway(managed=("DU999", "DU123"))) as broker:
        info = broker.account()
    assert info == AccountInfo("DU123", "USD", True, 4002)
    assert connection_refusal(info, CFG) is None


def test_open_orders_resync_with_ib_and_fail_closed_when_it_fails():
    gw = _gateway()
    with _connected(gw) as broker:
        broker.open_orders()
    gw.unified_transport._ib.reqAllOpenOrdersAsync.assert_awaited_once()

    bad = _gateway()
    bad.unified_transport._ib.reqAllOpenOrdersAsync = AsyncMock(side_effect=OSError("no answer"))
    with _connected(bad) as broker, pytest.raises(OSError, match="no answer"):
        broker.open_orders()


def test_usd_base_account_reports_the_gateways_account_paper_by_du_prefix_and_port():
    with _connected(_gateway()) as broker:
        assert broker.account() == AccountInfo("DU123", "USD", True, 4002)


def test_the_gateway_reported_id_is_used_even_when_it_differs_from_cfg():
    with _connected(_reporting("DU999")) as broker:
        info = broker.account()
    assert info.account_id == "DU999"
    assert "not the configured account" in connection_refusal(info, CFG)  # the Gate sees it


def test_a_non_du_reported_id_is_not_paper():
    with _connected(_reporting("U555")) as broker:
        info = broker.account()
    assert info.paper is False
    assert "not a paper connection" in connection_refusal(info, CFG)


def test_a_missing_reported_id_raises():
    with _connected(_reporting("")) as broker, pytest.raises(RuntimeError, match="no account id"):
        broker.account()


def test_account_port_is_the_configured_port_from_the_connection_spec():
    cfg = BrokerConfig(True, "10.0.0.5", 7497, 17, "DU123")
    with IbBroker(cfg, build=lambda spec: _gateway()) as broker:
        assert broker.account().port == 7497


@pytest.mark.parametrize(
    "cfg",
    [
        BrokerConfig(True, "h", 4001, 1, "DU123"),
        BrokerConfig(True, "h", 7496, 1, "DU123"),
        BrokerConfig(True, "h", 4002, 1, "U123"),
        BrokerConfig(True, "h", 4002, 1, ""),
    ],
)
def test_the_adapter_refuses_live_ports_and_non_paper_accounts(cfg):
    with pytest.raises(ValueError, match="paper only"):
        IbBroker(cfg, build=lambda spec: _gateway())


def test_flatten_still_sells_when_cancel_all_partly_fails(capsys):
    gw = _gateway(positions=[_pos("QQQ", "10")])
    gw.cancel_all = AsyncMock(side_effect=CancelAllError("1 of 2 failed", [RuntimeError("x")]))
    with _connected(gw) as broker:
        subs = broker.flatten()
    assert [s.order for s in subs] == [Order("QQQ", "SELL", 10)]
    assert "cancel_all partly failed" in capsys.readouterr().err


def test_a_stop_failure_is_swallowed_and_the_loop_closes(capsys):
    gw = _gateway()
    gw.stop = AsyncMock(side_effect=RuntimeError("stop boom"))
    broker = _connected(gw)
    with broker:
        loop = broker._loop
    assert loop is not None
    assert loop.is_closed()
    assert "stop boom" in capsys.readouterr().err


def test_a_stop_failure_does_not_mask_an_in_flight_exception():
    gw = _gateway()
    gw.stop = AsyncMock(side_effect=RuntimeError("stop boom"))
    with pytest.raises(KeyError), _connected(gw):
        raise KeyError("body")


def test_flatten_refuses_a_fractional_long_instead_of_truncating():
    gw = _gateway(positions=[_pos("QQQ", "1.5")])
    with _connected(gw) as broker, pytest.raises(ValueError, match="fractional"):
        broker.flatten()
    gw.place_order.assert_not_called()


def test_open_orders_match_by_perm_id_or_order_id():
    gw = _gateway()
    trade = SimpleNamespace(order=SimpleNamespace(permId=9001, orderId=7))
    gw.place_order = AsyncMock(
        return_value=SimpleNamespace(order_id=7, status="submitted", _trade=trade)
    )
    with _connected(gw) as broker:
        broker.submit([Order("QQQ", "BUY", 3)])
        gw.get_open_orders.return_value = [
            SimpleNamespace(order_id=9001, status="submitted"),  # later seen by permId
            SimpleNamespace(order_id=7, status="submitted"),  # seen by orderId
        ]
        assert broker.open_orders() == [
            OpenOrder("QQQ", "BUY", 3, 9001),
            OpenOrder("QQQ", "BUY", 3, 7),
        ]


def test_non_usd_base_account_reports_unknown_so_the_gate_refuses():
    # EUR base: NetLiquidation comes in EUR, so the USD summary has none.
    eur_base = {"USD": _summary("USD", cash="10"), "BASE": _summary("BASE", cash="50")}
    with _connected(_gateway(summaries=eur_base)) as broker:
        info = broker.account()
    assert info.base_currency == "UNKNOWN"
    assert "base currency" in account_refusal(info, [])


def test_open_orders_come_from_the_adapters_own_order_mapping():
    gw = _gateway()
    with _connected(gw) as broker:
        broker.submit([Order("QQQ", "BUY", 3)])  # order_id 100
        gw.get_open_orders.return_value = [
            SimpleNamespace(order_id=100, status="submitted"),
            SimpleNamespace(order_id=55, status="submitted"),  # not placed by this adapter
        ]
        assert broker.open_orders() == [
            OpenOrder("QQQ", "BUY", 3, 100),
            OpenOrder("UNKNOWN", "UNKNOWN", 0, 55),
        ]


def test_submit_places_market_on_open_orders():
    gw = _gateway()
    with _connected(gw) as broker:
        subs = broker.submit([Order("GLD", "SELL", 2), Order("QQQ", "BUY", 8)])
    assert subs == [
        SubmittedOrder(Order("GLD", "SELL", 2), 100, "submitted"),
        SubmittedOrder(Order("QQQ", "BUY", 8), 101, "submitted"),
    ]
    ref, order = gw.place_order.await_args_list[1].args
    assert ref == InstrumentRef("QQQ", InstrumentType.STOCK, quote_currency="USD")
    assert order == HBOrder(
        order_type=OrderType.MARKET,
        side=TradeType.BUY,
        amount=Decimal(8),
        time_in_force=TimeInForce.OPG,
        outside_rth=False,
    )


def test_flatten_sells_with_day_market_orders_not_moo():
    gw = _gateway(positions=[_pos("QQQ", "10")])
    with _connected(gw) as broker:
        broker.flatten()
    _, order = gw.place_order.await_args.args
    assert (order.order_type, order.side, order.time_in_force, order.outside_rth) == (
        OrderType.MARKET, TradeType.SELL, TimeInForce.DAY, False,
    )  # fmt: skip


def test_flatten_cancels_all_first_then_sells_longs_only():
    gw = _gateway(positions=[_pos("QQQ", "10"), _pos("GLD", "-2")])
    calls: list[str] = []
    gw.cancel_all.side_effect = lambda: calls.append("cancel_all") or []
    place = gw.place_order.side_effect
    gw.place_order.side_effect = lambda ref, order, **kw: (
        calls.append(ref.symbol) or place(ref, order)
    )
    with _connected(gw) as broker:
        subs = broker.flatten()
    assert calls == ["cancel_all", "QQQ"]
    assert [s.order for s in subs] == [Order("QQQ", "SELL", 10)]
