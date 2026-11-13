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
import sys
from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Any, TypeVar

from market_connector.contracts.instrument import InstrumentRef, InstrumentType
from market_connector.exchanges.interactive_brokers.exceptions import CancelAllError
from market_connector.exchanges.interactive_brokers.factory import build_ib_gateway
from market_connector.exchanges.interactive_brokers.specs import IbConnectionSpec
from market_connector.orders import HBOrder, OrderType, TimeInForce, TradeType

from qrl.broker import AccountInfo, Holding, OpenOrder, Order, SubmittedOrder
from qrl.broker_config import LIVE_PORTS, BrokerConfig, is_paper_account_id

T = TypeVar("T")
_SYNC_TIMEOUT = 15.0  # seconds to wait for IB's all-open-orders answer


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


async def _account_facts(gateway: Any) -> tuple[str, str, bool]:
    """(account id, base currency, every managed account is paper).

    The summary's `account` is only the configured id echoed by the connector, so
    it proves nothing. IB's own managed-accounts list (`gateway.managed_accounts()`)
    is the independent fact. An empty or unreadable list fails closed. If the
    configured id is not in the list, the first managed account is reported, so
    the Gate refuses with "not the configured account"."""
    summary = await gateway.get_account_summary("USD")
    try:
        managed = [str(a) for a in gateway.managed_accounts()]
    except Exception as exc:
        raise RuntimeError(f"cannot read IB's managed accounts: {exc!r}") from exc
    if not managed:
        raise RuntimeError("IB reports no managed accounts; refusing to trade")
    if not summary.account:
        raise RuntimeError("IB gateway reported no account id; refusing to trade")
    reported = str(summary.account)
    account_id = reported if reported in managed else managed[0]
    base = "USD" if summary.net_liquidation is not None else "UNKNOWN"
    return account_id, base, all(is_paper_account_id(a) for a in managed)


def _ids(handle: Any) -> set[int]:
    """Every id IB may know the order by: the handle's id (permId when set, else
    orderId), its permId and its client orderId (None and 0 are ignored)."""
    found = {handle.order_id, *(getattr(handle, a, None) for a in ("perm_id", "client_order_id"))}
    return {int(i) for i in found if i}


def _handle_order(handle: Any) -> Order | None:
    """The order as IB itself describes it through the handle's public `symbol`,
    `action` and `total_quantity` accessors, or None when any part is missing or
    is not a whole-share BUY/SELL. This names orders another process or TWS
    placed, e.g. the evening run's MOO seen by a later read-only check."""
    try:
        symbol, side, qty = handle.symbol, handle.action, Decimal(str(handle.total_quantity))
    except (AttributeError, ArithmeticError):
        return None
    # The connector's `symbol` is `str(contract.symbol)`: a missing symbol is "None".
    if not isinstance(symbol, str) or symbol in ("", "None") or side not in ("BUY", "SELL"):
        return None
    if not qty.is_finite() or qty <= 0 or qty != qty.to_integral_value():
        return None
    return Order(symbol, side, int(qty))


def _sell_all(position: Any) -> Order:
    if position.quantity != position.quantity.to_integral_value():
        raise ValueError(f"{position.symbol}: fractional quantity {position.quantity}; not selling")
    return Order(position.symbol, "SELL", int(position.quantity))


class IbBroker:
    """`qrl.broker.Broker` over one IB Gateway paper connection per run; use
    it as `with IbBroker(cfg) as broker: ...`.

    The adapter keeps its own `order_id -> Order` mapping (filled by `submit`
    and `flatten`) and builds `OpenOrder`s from it. An open order it did not
    place in this process is read from the handle's public `symbol`, `action`
    and `total_quantity`; only when those are missing or unreadable is it
    reported as UNKNOWN (the Gate only needs to know it exists)."""

    def __init__(
        self, cfg: BrokerConfig, build: Callable[[IbConnectionSpec], Any] = build_ib_gateway
    ) -> None:
        # A hand-built BrokerConfig never went through the loader's checks.
        if cfg.port in LIVE_PORTS or not is_paper_account_id(cfg.account_id):
            raise ValueError(
                f"IbBroker is paper only: port {cfg.port} / account {cfg.account_id!r} refused"
            )
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
        except Exception as exc:  # never mask the run's result or an in-flight exception
            print(f"IB gateway stop failed: {exc!r}", file=sys.stderr)
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
            for known in _ids(handle):
                self._placed[known] = order
            order_id = int(handle.order_id)
            out.append(SubmittedOrder(order, order_id, str(handle.status)))
        return out

    def _open_order(self, handle: Any) -> OpenOrder:
        order_id = int(handle.order_id)
        order = next((self._placed[i] for i in _ids(handle) if i in self._placed), None)
        if order is None:
            order = _handle_order(handle)
        if order is None:
            return OpenOrder("UNKNOWN", "UNKNOWN", 0, order_id)
        return OpenOrder(order.symbol, order.side, order.shares, order_id)

    def account(self) -> AccountInfo:
        """IB's own facts, not an echo of the config: the Gate's paper and account
        checks compare them with `config/broker.yaml`."""
        account_id, base, all_paper = self._session(_account_facts)
        # IB paper accounts are DU-prefixed: that is the real paper signal (the
        # connector's `paper` flag only selects the market-data type). A login
        # that manages any non-DU account is not paper, even if ours is DU.
        # The connector exposes no connected-port attribute; this is the port we connected to.
        paper = is_paper_account_id(account_id) and all_paper
        return AccountInfo(account_id, base, paper, self._spec.port)

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
            # The connector only logs a failed all-open-orders sync at connect, so an
            # empty cache could hide live orders. Sync again here; a failure or
            # timeout raises (fail closed).
            await gateway.sync_open_orders(timeout=_SYNC_TIMEOUT)
            return [self._open_order(h) for h in gateway.get_open_orders()]

        return self._session(op)

    def submit(self, orders: list[Order]) -> list[SubmittedOrder]:
        async def op(gateway: Any) -> list[SubmittedOrder]:
            # Market-on-open: IB queues it for the next opening auction (#184).
            return await self._place_all(gateway, orders, TimeInForce.OPG)

        return self._session(op)

    def flatten(self) -> list[SubmittedOrder]:
        async def op(gateway: Any) -> list[SubmittedOrder]:
            try:
                await gateway.cancel_all()
            except CancelAllError as exc:
                # The Broker protocol's flatten result cannot carry a note, so say it on
                # stderr; the kill switch still sells (the Gate refuses on leftover orders).
                print(f"flatten: cancel_all partly failed, selling anyway: {exc}", file=sys.stderr)
            positions = await gateway.get_positions()
            longs = [_sell_all(p) for p in positions if p.quantity > 0]
            # DAY market: the kill switch must also work after the MOO cut-off.
            return await self._place_all(gateway, longs, TimeInForce.DAY)

        return self._session(op)
