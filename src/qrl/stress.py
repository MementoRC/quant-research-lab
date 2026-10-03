"""Stress scenarios: a DIAGNOSTIC of how much the current portfolio loses
under historical shock windows and pre-registered hypothetical shocks,
against the profile's max-drawdown cap. It forecasts nothing, tunes nothing
and selects nothing (spec: docs/superpowers/specs/2026-10-03-stress-scenarios-design.md).

Pure functions only: callers inject data and configs. Never slices the
holdout: windows ending on/after the holdout start are refused at load, and
replay frames are truncated by index at the window end.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

from .metrics import drawdown

SHOCK_CLASSES = ("equity", "gold")


@dataclass(frozen=True)
class Window:
    name: str
    start: pd.Timestamp
    end: pd.Timestamp
    replay: bool


@dataclass(frozen=True)
class Hypothetical:
    name: str
    shocks: dict[str, float]


@dataclass(frozen=True)
class StressConfig:
    windows: list[Window]
    hypotheticals: list[Hypothetical]
    max_report_age_days: int


def load_stress_config(path: str | Path, holdout_start: pd.Timestamp) -> tuple[StressConfig, str]:
    """Return (config, full sha256 of the raw file bytes). Raises ValueError
    on a window reaching the holdout, start >= end, a bad date, an unknown
    shock class, a shock <= -1, or a duplicate scenario name."""
    raw = Path(path).read_bytes()
    doc = yaml.safe_load(raw)

    windows = []
    for w in doc["windows"]:
        start, end = pd.Timestamp(w["start"]), pd.Timestamp(w["end"])
        if start >= end:
            raise ValueError(f"window {w['name']}: start must be before end")
        if end >= holdout_start:
            raise ValueError(
                f"window {w['name']} reaches the sealed holdout (starts {holdout_start.date()})"
            )
        windows.append(Window(str(w["name"]), start, end, bool(w["replay"])))

    hypotheticals = []
    for h in doc["hypotheticals"]:
        shocks = {k: float(v) for k, v in h.items() if k != "name"}
        unknown = set(shocks) - set(SHOCK_CLASSES)
        if unknown:
            raise ValueError(f"hypothetical {h['name']}: unknown classes {sorted(unknown)}")
        if any(v <= -1 for v in shocks.values()):
            raise ValueError(f"hypothetical {h['name']}: a shock must be above -1 (-100%)")
        hypotheticals.append(Hypothetical(str(h["name"]), shocks))

    names = [w.name for w in windows] + [h.name for h in hypotheticals]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise ValueError(f"duplicate scenario names: {dupes}")

    cfg = StressConfig(windows, hypotheticals, int(doc["max_report_age_days"]))
    return cfg, hashlib.sha256(raw).hexdigest()


GOLD_TICKERS = frozenset({"GLD"})


def asset_class(ticker: str) -> str:
    return "gold" if ticker in GOLD_TICKERS else "equity"


def window_drawdown(returns: pd.Series) -> float:
    """Worst peak-to-trough loss (positive fraction) of an equity curve that
    starts at 1.0 on the window's first day: a 0.0 return is prepended so a
    first-day loss counts (`qrl.metrics.drawdown`'s peak excludes the start)."""
    r = pd.concat([pd.Series([0.0]), returns.reset_index(drop=True)], ignore_index=True)
    return float(-drawdown(r).min())


def hypothetical_loss(weights: pd.Series, hyp: Hypothetical) -> float:
    """Single-step loss = -sum(weight x class shock); cash (unallocated) is 0%.
    Negative means a gain."""
    w = weights[weights > 0]
    return float(-sum(wt * hyp.shocks.get(asset_class(t), 0.0) for t, wt in w.items()))
