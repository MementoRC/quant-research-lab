"""Strategy registry.

Strategy contract:
    weights(close: DataFrame, **params) -> DataFrame of target weights
    * Row t may only use closes up to and including day t.
    * Rows during warm-up must be NaN (not 0), so the engine knows when to start.
    * Long-only, weights per row sum to <= 1.
Every registered strategy is checked by tests/test_strategies.py for look-ahead.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .buy_and_hold import buy_and_hold
from .core_trend import core_trend


@dataclass(frozen=True)
class StrategySpec:
    weights: Callable
    tickers: Callable[[dict], list[str]]


REGISTRY: dict[str, StrategySpec] = {
    "buy_and_hold": StrategySpec(buy_and_hold, lambda p: [p["ticker"]]),
    "core_trend": StrategySpec(core_trend, lambda p: [p["risk_on"], p["risk_off"]]),
}
