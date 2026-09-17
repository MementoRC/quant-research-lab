"""Strategy registry.

Strategy contract:
    weights(close: DataFrame, ..., **params) -> DataFrame of target weights
    * Row t may only use data (close, and for some families high/low/volume)
      up to and including day t.
    * Rows during warm-up must be NaN (not 0), so the engine knows when to
      start.
    * Long-only, weights per row sum to <= 1 (a sleeve's `capital` share).
Every strategy in `REGISTRY` is checked by the pre-existing
tests/test_strategies.py for look-ahead, which requires a matching entry in
that file's own `EXAMPLE_PARAMS` -- a file AGENTS.md forbids editing here.
The 2.2 cross-sectional families (trend_pullback, low_range_close,
quiet_pullback) are therefore kept in a parallel `SLEEVE_REGISTRY` instead of
`REGISTRY`, so the existing registry (and its test) is untouched; they are
checked for look-ahead in the new tests/test_strategy_templates.py instead.
A later milestone that wires them into build_site.py can freely merge the
two registries.

`StrategySpec.space` is a candidate parameter space (`name -> list of
values`) used by `sample_params`/`iter_grid` and, later, by the milestone 2.4
search loop. `StrategySpec.fields` names which price frames (`"close"`,
`"high"`, `"low"`, `"volume"`) the strategy needs, matching `qrl.data.
load_ohlcv`'s keys.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from .buy_and_hold import buy_and_hold
from .core_trend import core_trend
from .low_range_close import low_range_close
from .quiet_pullback import quiet_pullback
from .trend_pullback import trend_pullback


@dataclass(frozen=True)
class StrategySpec:
    weights: Callable
    tickers: Callable[[dict], list[str]]
    fields: tuple[str, ...] = ("close",)
    space: dict[str, list] = field(default_factory=dict)


def _sleeve_tickers(params: dict) -> list[str]:
    """Cross-sectional families take the sleeve universe explicitly, since
    they trade many names at once rather than one fixed ticker/pair."""
    return list(params["tickers"])


REGISTRY: dict[str, StrategySpec] = {
    "buy_and_hold": StrategySpec(buy_and_hold, lambda p: [p["ticker"]]),
    "core_trend": StrategySpec(
        core_trend,
        lambda p: [t for t in (p.get("risk_on", "QQQ"), p.get("risk_off", "GLD")) if t != "CASH"],
        fields=("close",),
        space={
            "lookback": [50, 100, 150, 200, 250],
            "risk_off": ["GLD", "TLT", "CASH"],
        },
    ),
}

SLEEVE_REGISTRY: dict[str, StrategySpec] = {
    "trend_pullback": StrategySpec(
        trend_pullback,
        _sleeve_tickers,
        fields=("close",),
        space={
            "trend_lookback": [100, 150, 200, 250],
            "short_ma": [5, 10, 15, 20],
            "pullback_days": [2, 3, 4, 5],
            "pullback_pct": [0.0, 0.01, 0.02, 0.03],
            "exit_days": [3, 5, 8, 10],
            "max_positions": [5, 10, 15],
        },
    ),
    "low_range_close": StrategySpec(
        low_range_close,
        _sleeve_tickers,
        fields=("close", "high", "low"),
        space={
            "trend_lookback": [100, 150, 200, 250],
            "range_pct": [0.1, 0.15, 0.2, 0.25, 0.3],
            "exit_days": [3, 5, 8, 10],
            "max_positions": [5, 10, 15],
        },
    ),
    "quiet_pullback": StrategySpec(
        quiet_pullback,
        _sleeve_tickers,
        fields=("close", "volume"),
        space={
            "trend_lookback": [100, 150, 200, 250],
            "short_ma": [5, 10, 15, 20],
            "vol_lookback": [10, 20, 30],
            "quiet_ratio": [0.6, 0.7, 0.8, 0.9],
            "exit_days": [3, 5, 8, 10],
            "max_positions": [5, 10, 15],
        },
    ),
}


def iter_grid(space: dict[str, list]) -> list[dict]:
    """All combinations of a parameter space, in insertion order.

    An empty space yields a single empty parameter set (the family has no
    tunable knobs to grid over).
    """
    if not space:
        return [{}]
    keys = list(space.keys())
    combos = itertools.product(*(space[k] for k in keys))
    return [dict(zip(keys, values, strict=True)) for values in combos]


def sample_params(space: dict[str, list], n: int, seed: int = 0) -> list[dict]:
    """Deterministically sample up to `n` unique parameter sets from `space`.

    Sampling without replacement from the full grid, so the result never
    contains duplicates. If `n` covers (or exceeds) the whole grid, the full
    grid is returned in a deterministic shuffled order instead.
    """
    grid = iter_grid(space)
    rng = np.random.default_rng(seed)
    if n >= len(grid):
        order = rng.permutation(len(grid))
        return [grid[i] for i in order]
    idx = rng.choice(len(grid), size=n, replace=False)
    return [grid[i] for i in idx]
