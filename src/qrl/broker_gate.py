"""The Gate of the IB paper rebalancer (spec "Evening run" step 1): only the
checks that need just the connection, in this order: (1) `enabled`; (2) the
3-part paper check; (3) base currency USD, every position STK in USD, every
quantity a whole number; (4) no open orders (never auto-cancelled)."""

from __future__ import annotations

from qrl.broker import AccountInfo, Broker, Holding
from qrl.broker_config import LIVE_PORTS, BrokerConfig, is_paper_account_id


def paper_refusal(info: AccountInfo) -> str | None:
    """All three must hold: spec.paper, a non-live port, a DU account id."""
    if not info.paper:
        return "not a paper connection: the connection spec has paper=False"
    if info.port in LIVE_PORTS:
        return f"not a paper connection: port {info.port} is a live port"
    if not is_paper_account_id(info.account_id):
        return f"not a paper connection: account id {info.account_id!r} does not start with DU"
    return None


def connection_refusal(info: AccountInfo, cfg: BrokerConfig) -> str | None:
    """The paper check, then the reported account must be the configured one."""
    refusal = paper_refusal(info)
    if refusal is not None:
        return refusal
    if info.account_id != cfg.account_id:
        return f"account {info.account_id!r} is not the configured account {cfg.account_id!r}"
    return None


def account_refusal(info: AccountInfo, holdings: list[Holding]) -> str | None:
    if info.base_currency != "USD":
        return f"account base currency is {info.base_currency}, not USD"
    foreign = sorted(h.symbol for h in holdings if h.sec_type != "STK" or h.currency != "USD")
    if foreign:
        return f"position(s) not STK in USD: {', '.join(foreign)}"
    fractional = sorted(
        h.symbol
        for h in holdings
        if not h.quantity.is_finite() or h.quantity != h.quantity.to_integral_value()
    )
    if fractional:
        return f"position quantity not a whole number of shares: {', '.join(fractional)}"
    return None


def gate(cfg: BrokerConfig, broker: Broker) -> tuple[str | None, list[Holding]]:
    """The first refusal (or None) and the account's holdings."""
    if not cfg.enabled:
        return "disabled: `enabled` is false in config/broker.yaml", []
    info = broker.account()
    refusal = connection_refusal(info, cfg)
    if refusal is not None:
        return refusal, []
    holdings = broker.holdings()
    refusal = account_refusal(info, holdings)
    if refusal is not None:
        return refusal, holdings
    orders = broker.open_orders()
    if orders:
        return f"{len(orders)} open order(s) on the account; never auto-cancelled", holdings
    return None, holdings
