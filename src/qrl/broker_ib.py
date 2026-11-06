"""IB paper adapter implementing `qrl.broker.Broker` over hb-market-connector
(spec: docs/methodology/broker-rebalancer.md, "Components", "Cash and
equity"). Importable only in the `broker` pixi environment:
scripts/rebalance.py imports it lazily, and qrl.broker / qrl.rebalance never
import it.

The connector is async-only. `IbBroker` is a context manager holding one
event loop and one connected gateway for the whole run: `__enter__` starts
the gateway on its own loop, every Broker call runs on that loop, and
`__exit__` stops the gateway and closes the loop (also on error).

- Cash is the USD summary's TotalCashValue (`get_account_summary("USD")`,
  hb-market-connector #185), never `get_balance` (AvailableFunds). An
  unreported figure raises LookupError, which the evening run refuses on.
- Base currency: `get_account_summary(None).currency` is just the literal
  "BASE", so it cannot name the base. IB reports NetLiquidation only in the
  base currency, so the base is USD exactly when the USD summary has a
  `net_liquidation`; otherwise "UNKNOWN", which the Gate refuses.
- The evening run's orders are market-on-open (`TimeInForce.OPG`, #184);
  the kill switch sells with DAY market orders so it also works during the
  session. `outside_rth` is always False. `get_fills` is not used."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Any, TypeVar

from market_connector.contracts.instrument import InstrumentRef, InstrumentType
from market_connector.exchanges.interactive_brokers.factory import build_ib_gateway
from market_connector.exchanges.interactive_brokers.specs import IbConnectionSpec
from market_connector.orders import HBOrder, OrderType, TimeInForce, TradeType

from qrl.broker import AccountInfo, Holding, OpenOrder, Order, SubmittedOrder
from qrl.broker_config import BrokerConfig

T = TypeVar("T")


def connection_spec(cfg: BrokerConfig) -> IbConnectionSpec:
    return IbConnectionSpec(
        host=cfg.host,
        port=cfg.port,
        client_id=cfg.client_id,
        account_id=cfg.account_id,
        paper=True,
        fetch_all_open_orders=True,
    )


def _hb_order(order: Order, tif: TimeInForce) -> HBOrder:
    return HBOrder(
        order_type=OrderType.MARKET,
        side=TradeType.BUY if order.side == "BUY" else TradeType.SELL,
        amount=Decimal(order.shares),
        time_in_force=tif,
        outside_rth=False,
    )


async def _total_cash_usd(gateway: Any) -> float:
    summary = await gateway.get_account_summary("USD")
    if summary.total_cash_value is None:
        raise LookupError(
            "IB reports no TotalCashValue in USD; never falling back to AvailableFunds"
        )
    return float(summary.total_cash_value)


async def _base_currency(gateway: Any) -> str:
    summary = await gateway.get_account_summary("USD")
    return "USD" if summary.net_liquidation is not None else "UNKNOWN"


class IbBroker:
    """`qrl.broker.Broker` over one IB Gateway paper connection per run; use
    it as `with IbBroker(cfg) as broker: ...`.

    `OrderHandle` has no symbol, side or quantity, so the adapter keeps its
    own `order_id -> Order` mapping (filled by `submit` and `flatten`) and
    builds `OpenOrder`s from it. An open order it did not place in this
    process is reported as UNKNOWN: the Gate only needs to know it exists."""

    def __init__(
        self, cfg: BrokerConfig, build: Callable[[IbConnectionSpec], Any] = build_ib_gateway
    ) -> None:
        self._spec = connection_spec(cfg)
        self._build = build
        self._placed: dict[int, Order] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._gateway: Any = None

    def __enter__(self) -> IbBroker:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)  # ib_async binds to the current loop when built
        try:
            gateway = self._build(self._spec)
            loop.run_until_complete(gateway.start())
        except BaseException:
            asyncio.set_event_loop(None)
            loop.close()
            raise
        self._loop, self._gateway = loop, gateway
        return self

    def __exit__(self, *exc_info: object) -> None:
        loop, gateway = self._loop, self._gateway
        self._loop, self._gateway = None, None
        if loop is None:
            return
        try:
            loop.run_until_complete(gateway.stop())
        finally:
            asyncio.set_event_loop(None)
            loop.close()

    def _session(self, op: Callable[[Any], Awaitable[T]]) -> T:
        if self._loop is None:
            raise RuntimeError("IbBroker is not connected; use it in a `with` block")
        return self._loop.run_until_complete(op(self._gateway))

    async def _place_all(
        self, gateway: Any, orders: list[Order], tif: TimeInForce
    ) -> list[SubmittedOrder]:
        out = []
        for order in orders:
            ref = InstrumentRef(order.symbol, InstrumentType.STOCK, quote_currency="USD")
            handle = await gateway.place_order(ref, _hb_order(order, tif))
            order_id = int(handle.order_id)
            self._placed[order_id] = order
            out.append(SubmittedOrder(order, order_id, str(handle.status)))
        return out

    def _open_order(self, handle: Any) -> OpenOrder:
        order_id = int(handle.order_id)
        order = self._placed.get(order_id)
        if order is None:
            return OpenOrder("UNKNOWN", "UNKNOWN", 0, order_id)
        return OpenOrder(order.symbol, order.side, order.shares, order_id)

    def account(self) -> AccountInfo:
        base = self._session(_base_currency)
        return AccountInfo(self._spec.account_id or "", base, self._spec.paper, self._spec.port)

    def holdings(self) -> list[Holding]:
        async def op(gateway: Any) -> list[Holding]:
            return [
                Holding(p.symbol, p.sec_type, p.currency, p.quantity)
                for p in await gateway.get_positions()
            ]

        return self._session(op)

    def cash(self) -> float:
        return self._session(_total_cash_usd)

    def open_orders(self) -> list[OpenOrder]:
        async def op(gateway: Any) -> list[OpenOrder]:
            return [self._open_order(h) for h in gateway.get_open_orders()]

        return self._session(op)

    def submit(self, orders: list[Order]) -> list[SubmittedOrder]:
        async def op(gateway: Any) -> list[SubmittedOrder]:
            # Market-on-open: IB queues it for the next opening auction (#184).
            return await self._place_all(gateway, orders, TimeInForce.OPG)

        return self._session(op)

    def flatten(self) -> list[SubmittedOrder]:
        async def op(gateway: Any) -> list[SubmittedOrder]:
            await gateway.cancel_all()
            positions = await gateway.get_positions()
            longs = [Order(p.symbol, "SELL", int(p.quantity)) for p in positions if p.quantity > 0]
            # DAY market: the kill switch must also work after the MOO cut-off.
            return await self._place_all(gateway, longs, TimeInForce.DAY)

        return self._session(op)
