"""The IB paper rebalancer's pure planner (spec:
docs/methodology/broker-rebalancer.md, "Evening run" steps 4-5 and
"Refusals"). Target weights, our closes, IB positions and IB cash in;
whole-share orders, skips and refusals out. No IO, no broker calls.

`plan` takes the profile's risk limits as a sixth argument (the spec's
signature omits them, but its risk-cap refusal needs them)."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field

import pandas as pd

from qrl.broker import Order, Position
from qrl.broker_config import BrokerConfig
from qrl.risk import RiskLimits


@dataclass(frozen=True)
class Skip:
    symbol: str
    reason: str


@dataclass(frozen=True)
class Plan:
    orders: tuple[Order, ...] = ()
    skipped: tuple[Skip, ...] = ()
    refusals: tuple[str, ...] = ()
    equity: float = 0.0
    targets: Mapping[str, int] = field(default_factory=dict)


def _targets(weights: pd.Series, closes: pd.Series, investable: float) -> dict[str, int]:
    return {
        str(s): math.floor(float(w) * investable / float(closes[s]))
        for s, w in weights.items()
        if w > 0
    }


def _orders(
    held: Mapping[str, int],
    targets: Mapping[str, int],
    closes: pd.Series,
    equity: float,
    deadband: float,
) -> tuple[list[Order], list[Skip]]:
    orders: list[Order] = []
    skipped: list[Skip] = []
    limit = deadband * equity
    for symbol in sorted(set(held) | set(targets)):
        target = targets.get(symbol, 0)
        delta = target - held.get(symbol, 0)
        if delta == 0:
            continue
        value = abs(delta) * float(closes[symbol])
        if target != 0 and value < limit:
            skipped.append(Skip(symbol, f"trade value {value:.2f} below deadband {limit:.2f}"))
            continue
        orders.append(Order(symbol, "BUY" if delta > 0 else "SELL", abs(delta)))
    orders.sort(key=lambda o: (o.side != "SELL", o.symbol))
    return orders, skipped


def plan(
    target_weights: pd.Series,
    closes: pd.Series,
    positions: list[Position],
    cash: float,
    cfg: BrokerConfig,
    limits: RiskLimits,
) -> Plan:
    """Size whole-share targets as floor(w x equity x (1 - cash_buffer) / close),
    equity = IB cash + held shares at our closes; skip deltas inside the
    deadband unless the target is 0; list sells before buys."""
    held = {p.symbol: p.shares for p in positions if p.shares != 0}
    equity = cash + sum(n * float(closes[s]) for s, n in held.items())
    targets = _targets(target_weights, closes, equity * (1 - cfg.cash_buffer))
    orders, skipped = _orders(held, targets, closes, equity, cfg.deadband)
    return Plan(tuple(orders), tuple(skipped), (), equity, targets)
