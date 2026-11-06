"""The broker interface of the IB paper rebalancer (spec:
docs/methodology/broker-rebalancer.md, "Components"), plus `FakeBroker`, an
in-memory implementation for tests. Pure: never imports `market_connector`
(the IB adapter is `qrl.broker_ib`, broker environment only).

Implementation note (spec amended in the final task): the Gate must check the
paper flag, port, account id, base currency, and each position's type,
currency and whole-share quantity, which the spec's `Position(symbol, shares)`
cannot carry. So the Protocol exposes `account()` and raw `holdings()`;
`to_positions` turns checked holdings into the spec's `Position` list."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal, Protocol

Side = Literal["BUY", "SELL"]
DEAD_STATUSES = frozenset({"cancelled", "rejected"})


@dataclass(frozen=True)
class Position:
    symbol: str
    shares: int


@dataclass(frozen=True)
class Holding:
    """One IB position as reported, before the Gate checked it."""

    symbol: str
    sec_type: str
    currency: str
    quantity: Decimal


@dataclass(frozen=True)
class AccountInfo:
    """What the paper and currency checks need: the account id, its base
    currency, and the connection spec's `paper` flag and port."""

    account_id: str
    base_currency: str
    paper: bool
    port: int


@dataclass(frozen=True)
class Order:
    symbol: str
    side: Side
    shares: int

    def __post_init__(self) -> None:
        if self.side not in ("BUY", "SELL"):
            raise ValueError(f"order side must be BUY or SELL, got {self.side!r}")
        if isinstance(self.shares, bool) or not isinstance(self.shares, int) or self.shares <= 0:
            raise ValueError(f"order shares must be an int > 0, got {self.shares!r}")

    @property
    def delta(self) -> int:
        return self.shares if self.side == "BUY" else -self.shares


@dataclass(frozen=True)
class OpenOrder:
    symbol: str
    side: str
    shares: int
    order_id: int


@dataclass(frozen=True)
class SubmittedOrder:
    order: Order
    order_id: int
    status: str

    @property
    def delta(self) -> int:
        """Shares this order is expected to move: 0 if rejected or cancelled at submit."""
        return 0 if self.status in DEAD_STATUSES else self.order.delta


class Broker(Protocol):
    def account(self) -> AccountInfo: ...

    def holdings(self) -> list[Holding]: ...

    def cash(self) -> float: ...

    def open_orders(self) -> list[OpenOrder]: ...

    def submit(self, orders: list[Order]) -> list[SubmittedOrder]: ...

    def flatten(self) -> list[SubmittedOrder]: ...


def to_positions(holdings: list[Holding]) -> list[Position]:
    """Whole-share positions. Raises ValueError on a fractional quantity (the
    Gate refuses those before this is called)."""
    positions = []
    for h in holdings:
        if h.quantity != h.quantity.to_integral_value():
            raise ValueError(f"{h.symbol}: quantity {h.quantity} is not a whole number of shares")
        positions.append(Position(h.symbol, int(h.quantity)))
    return positions


def _paper_account() -> AccountInfo:
    return AccountInfo("DU123", "USD", True, 4002)


@dataclass
class FakeBroker:
    """In-memory Broker for tests. `submit` queues orders as open (status
    "submitted") unless their symbol is in `reject`; `fill_all` fills every
    queued order at the given prices, as the next open would."""

    info: AccountInfo = field(default_factory=_paper_account)
    held: list[Holding] = field(default_factory=list)
    cash_usd: float = 0.0
    pending: list[OpenOrder] = field(default_factory=list)
    reject: frozenset[str] = frozenset()
    submitted: list[SubmittedOrder] = field(default_factory=list)
    cancel_all_calls: int = 0
    next_id: int = 1

    def account(self) -> AccountInfo:
        return self.info

    def holdings(self) -> list[Holding]:
        return list(self.held)

    def cash(self) -> float:
        return self.cash_usd

    def open_orders(self) -> list[OpenOrder]:
        return list(self.pending)

    def submit(self, orders: list[Order]) -> list[SubmittedOrder]:
        out = []
        for order in orders:
            status = "rejected" if order.symbol in self.reject else "submitted"
            sub = SubmittedOrder(order, self.next_id, status)
            self.next_id += 1
            if status == "submitted":
                self.pending.append(OpenOrder(order.symbol, order.side, order.shares, sub.order_id))
            out.append(sub)
        self.submitted.extend(out)
        return out

    def flatten(self) -> list[SubmittedOrder]:
        self.cancel_all_calls += 1
        self.pending.clear()
        # int() truncation is safe: the Gate refuses fractional holdings before any fill.
        longs = [Order(h.symbol, "SELL", int(h.quantity)) for h in self.held if h.quantity > 0]
        return self.submit(longs)

    def fill_all(self, prices: dict[str, float]) -> None:
        kinds = {h.symbol: (h.sec_type, h.currency) for h in self.held}
        shares = {h.symbol: h.quantity for h in self.held}
        for o in self.pending:
            if o.symbol not in prices:
                raise ValueError(f"no fill price for {o.symbol}")
            sign = 1 if o.side == "BUY" else -1
            shares[o.symbol] = shares.get(o.symbol, Decimal(0)) + sign * o.shares
            self.cash_usd -= sign * o.shares * prices[o.symbol]
        self.pending.clear()
        self.held = [
            Holding(s, *kinds.get(s, ("STK", "USD")), q)
            for s, q in sorted(shares.items())
            if q != 0
        ]
