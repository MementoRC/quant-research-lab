"""The combined portfolio's live target weights: the wiring shared by
`scripts/daily_check.py` and the IB paper rebalancer
(docs/methodology/broker-rebalancer.md). It lives in the library, not in
scripts/, so `pytest --cov=qrl` covers it. No IO."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import cast

import pandas as pd

from qrl.health import HealthReport, run_daily_health
from qrl.portfolio import combine_portfolio
from qrl.risk import RiskLimits
from qrl.strategies import REGISTRY, SLEEVE_REGISTRY, StrategySpec

ALL_SPECS: dict[str, StrategySpec] = {**REGISTRY, **SLEEVE_REGISTRY}

WeightFn = Callable[[pd.DataFrame], pd.DataFrame]
CombineFn = Callable[[Mapping[str, pd.DataFrame]], tuple[pd.DataFrame, pd.DataFrame]]


def member_tickers(members: list[dict]) -> list[str]:
    """Sorted tickers that any configured core or sleeve member trades."""
    return sorted({t for m in members for t in ALL_SPECS[m["fn"]].tickers(m["params"])})


def extra_fields(members: list[dict]) -> set[str]:
    """Fields beyond "close" (high/low/volume) any member's family needs."""
    return {f for m in members for f in ALL_SPECS[m["fn"]].fields} - {"close"}


def member_weights_fn(member: dict, extra_frames: Mapping[str, pd.DataFrame]) -> WeightFn:
    """A close-only callable (`run_daily_health`'s `build_weights` contract)
    closing over any non-close fields this member's family needs."""
    spec = ALL_SPECS[member["fn"]]
    cols = spec.tickers(member["params"])
    kwargs = {k: v for k, v in member["params"].items() if k != "tickers"}

    def _weights(close: pd.DataFrame) -> pd.DataFrame:
        frames = [close[cols] if f == "close" else extra_frames[f][cols] for f in spec.fields]
        return cast(pd.DataFrame, spec.weights(*frames, **kwargs))

    return _weights


def weight_fns(
    core: dict, sleeve_members: list[dict], extra_frames: Mapping[str, pd.DataFrame]
) -> dict[str, WeightFn]:
    """`{"core": ..., "sleeve_<i>_<fn>": ...}`: the keys `make_combine` expects."""
    fns = {"core": member_weights_fn(core, extra_frames)}
    for i, member in enumerate(sleeve_members):
        fns[f"sleeve_{i}_{member['fn']}"] = member_weights_fn(member, extra_frames)
    return fns


def make_combine(capital_split: dict[str, float]) -> CombineFn:
    """`run_daily_health`'s `combine`: the core plus the equal-weighted sleeve,
    scaled by `capital_split`; returns `(combined, sleeve)`."""

    def combine(weights: Mapping[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
        if "core" not in weights:
            raise RuntimeError("core weights unavailable; core strategy failed earlier.")
        sleeve = [w for key, w in weights.items() if key != "core"]
        pw = combine_portfolio(weights["core"], sleeve, capital_split)
        return pw.combined, pw.sleeve

    return combine


@dataclass(frozen=True)
class Market:
    """One evening's inputs: the health report, our closes, and the combined
    weight frame (empty when the health report is not ok)."""

    health: HealthReport
    close: pd.DataFrame
    combined: pd.DataFrame


def build_market(
    *,
    close: pd.DataFrame,
    fns: Mapping[str, WeightFn],
    combine: CombineFn,
    limits: RiskLimits,
    as_of: pd.Timestamp,
    max_staleness_bdays: int = 1,
) -> Market:
    """Run the `qrl.health` daily checks on `close`; if they pass, build the
    combined weight frame from the same closes."""
    health = run_daily_health(
        load_close=lambda: close,
        build_weights=fns,
        combine=combine,
        limits=limits,
        as_of=as_of,
        max_staleness_bdays=max_staleness_bdays,
    )
    if not health.ok:
        return Market(health, close, pd.DataFrame())
    combined, _ = combine({name: fn(close) for name, fn in fns.items()})
    return Market(health, close, combined)
