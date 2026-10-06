"""Decision helper (spec: docs/methodology/decision-helper.md): a fixed set of
portfolios at 100% of capital under historical windows, judgement-based
shocks and CPI-indexed withdrawals. A decision aid: it selects nothing and
recommends nothing. Pure functions; callers inject data and configs. Every
price and CPI frame is cut at the research end (2018-12-31) before use, so
validation and holdout data never enter, and `slice_period(...,
unseal_holdout=True)` is never called.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .core_compare import Build, candidate_weights
from .decision_config import DecisionConfig, Portfolio, Scenario, portfolio_states
from .periods import period_bounds
from .portfolio import combine_portfolio
from .strategies import REGISTRY
from .stress import Cell, PortfolioDef, StressConfig, run_stress

FULL = {"core": 1.0, "sleeve": 0.0}  # 100% of capital, empty sleeve (as benchmark_metrics)
_NO_CAP = 1.0  # cells carry losses only; this report compares, it tests no cap


def data_end(criteria: dict) -> pd.Timestamp:
    """The last date any decision computation may see: the research end."""
    _, end = period_bounds(criteria, "research")
    if end is None:
        raise ValueError("criteria research period needs an end")
    return end


def portfolio_tickers(p: Portfolio) -> list[str]:
    """Every ticker whose prices the portfolio's rules need (held funds and signals)."""
    return list(
        dict.fromkeys(t for cand, _ in p.parts for t in REGISTRY[cand.fn].tickers(cand.params))
    )


def portfolio_weights(p: Portfolio, close: pd.DataFrame) -> pd.DataFrame:
    """Daily target weights (fractions of capital): the share-weighted sum of
    the parts' weights, so a switching part keeps switching inside a blend. A
    row is NaN wherever any part's row is NaN (never zero-filled into cash)."""
    frames = [candidate_weights(cand, close) * share for cand, share in p.parts]
    cols = sorted({c for f in frames for c in f.columns})
    total = pd.DataFrame(0.0, index=close.index, columns=cols)
    for frame in frames:
        total = total + frame.reindex(columns=cols, fill_value=0.0)
    total[total.isna().any(axis=1)] = np.nan
    return total


def scenario_return(mix: dict[str, float], scenario: Scenario) -> float:
    """One-year return of fixed weights: sum of weight x the fund's scenario
    return. The loader guarantees every held fund has a return."""
    return float(sum(w * scenario.returns[t] for t, w in mix.items()))


def real_return(nominal: float, inflation: float) -> float:
    return (1 + nominal) / (1 + inflation) - 1


def scenario_rows(portfolios: list[Portfolio], scenarios: list[Scenario]) -> list[dict]:
    """Per portfolio x scenario: nominal and real loss (positive = loss) for
    every state, and the worse state (the larger nominal loss)."""
    rows = []
    for p in portfolios:
        states = portfolio_states(p)
        for s in scenarios:
            by_state = {}
            for name, mix in states.items():
                r = scenario_return(mix, s)
                by_state[name] = {
                    "nominal_loss": -r,
                    "real_loss": -real_return(r, s.inflation),
                }
            worst = max((v["nominal_loss"], n) for n, v in by_state.items())[1]
            rows.append(
                {
                    "portfolio": p.id,
                    "scenario": s.name,
                    "label": s.label,
                    "states": by_state,
                    "worst": worst,
                }
            )
    return rows


def _rule_build(p: Portfolio) -> Build:
    def build(data: dict[str, pd.DataFrame], keep: list[str]) -> pd.DataFrame:
        return combine_portfolio(portfolio_weights(p, data["close"]), [], FULL).combined

    return build


def _static_build(mix: dict[str, float]) -> Build:
    def build(data: dict[str, pd.DataFrame], keep: list[str]) -> pd.DataFrame:
        w = pd.DataFrame({t: float(x) for t, x in mix.items()}, index=data["close"].index)
        return combine_portfolio(w, [], FULL).combined

    return build


def stress_portfolios(
    portfolios: list[Portfolio],
) -> tuple[list[PortfolioDef], dict[str, frozenset[str]]]:
    """PortfolioDefs for `run_stress` plus the cell modes kept per name. A
    static portfolio X keeps replay and frozen cells. A switching portfolio X
    keeps its rule's replay cells, and `X[state]` (that state's fixed weights)
    keeps frozen cells, one per state."""
    defs: list[PortfolioDef] = []
    modes: dict[str, frozenset[str]] = {}
    for p in portfolios:
        defs.append(PortfolioDef(p.id, _rule_build(p), portfolio_tickers(p)))
        states = portfolio_states(p)
        if len(states) == 1:
            modes[p.id] = frozenset({"replay", "frozen"})
            continue
        modes[p.id] = frozenset({"replay"})
        for state, mix in states.items():
            name = f"{p.id}[{state}]"
            defs.append(PortfolioDef(name, _static_build(mix), list(mix)))
            modes[name] = frozenset({"frozen"})
    return defs, modes


def window_rows(cells: list[Cell], threshold: float) -> list[dict]:
    """Report rows: loss, per-class proxied share (frozen cells) and the
    indicative flag (total proxied share above `threshold`)."""
    rows = []
    for c in cells:
        shares = dict(c.detail.get("proxied_share") or {})
        rows.append(
            {
                "portfolio": c.portfolio,
                "window": c.scenario,
                "mode": c.mode,
                "loss": c.loss,
                "proxied_share": shares,
                "indicative": float(sum(shares.values())) > threshold,
                "unavailable": c.unavailable,
            }
        )
    return rows


def stress_rows(cfg: DecisionConfig, data: dict[str, pd.DataFrame], criteria: dict) -> list[dict]:
    """Historical-window cells from `qrl.stress.run_stress`, unchanged. Frames
    are cut at the data end first, so nothing later reaches it; only the
    configured windows run (no class-based hypotheticals)."""
    end = data_end(criteria)
    cut = {k: v.loc[:end] for k, v in data.items()}
    defs, modes = stress_portfolios(cfg.portfolios)
    windows_only = StressConfig(cfg.windows, [], 0)
    cells = [
        c
        for c in run_stress(windows_only, defs, cut, _NO_CAP, criteria)
        if c.mode in modes[c.portfolio]
    ]
    return window_rows(cells, cfg.proxied_threshold)
