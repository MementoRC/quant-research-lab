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
from .decision_withdraw import monthly_withdrawals, path_metrics, withdrawal_path
from .engine import run_backtest
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


def start_dates(
    index: pd.DatetimeIndex, years: list[int], end: pd.Timestamp
) -> dict[int, pd.Timestamp]:
    """First trading day on or after 1 January of each start year."""
    out = {}
    for year in years:
        days = index[(index >= pd.Timestamp(year=year, month=1, day=1)) & (index <= end)]
        if days.empty:
            raise ValueError(f"no trading day in {year} on or before {end.date()}")
        out[year] = pd.Timestamp(days[0])
    return out


def portfolio_returns(
    p: Portfolio, data: dict[str, pd.DataFrame], start: pd.Timestamp, cost_bps: float
) -> pd.Series:
    """Daily net returns from `start` to the end of `data` (already cut), the
    portfolio bought fresh at the start-day open (the prior trading day's
    target row) and paying the engine's costs. Weights are built from the
    earliest data (warm-up). Refuses a held fund unpriced at `start` and NaN
    weights from the prior trading day on; a NaN is never turned into cash."""
    close = data["close"]
    held = sorted({t for mix in portfolio_states(p).values() for t in mix})
    unpriced = [t for t in held if t not in close.columns or pd.isna(close.at[start, t])]
    if unpriced:
        raise ValueError(
            f"portfolio {p.id}: held fund(s) {unpriced} unpriced at the start {start.date()}"
        )
    weights = portfolio_weights(p, close)
    pos = int(weights.index.searchsorted(start))
    if pos == 0:
        raise ValueError(f"portfolio {p.id}: no trading day before the start {start.date()}")
    target = weights.iloc[pos - 1 :]
    if target.isna().any(axis=None):
        raise ValueError(
            f"portfolio {p.id}: NaN weights on or after the start {start.date()} "
            "(a NaN is never turned into cash)"
        )
    combined = combine_portfolio(target, [], FULL).combined
    cols = list(combined.columns)
    result = run_backtest(data["open"][cols], close[cols], combined, cost_bps=cost_bps)
    return result.returns.loc[start:]


def withdrawal_rows(
    cfg: DecisionConfig, data: dict[str, pd.DataFrame], cpi: pd.Series, criteria: dict
) -> list[dict]:
    """Per portfolio and rate: the first start year's path metrics, the worst
    start year by real ending value, and every start year's metrics. Price
    and CPI (availability-dated) frames are cut at the data end first."""
    end = data_end(criteria)
    cut = {k: v.loc[:end] for k, v in data.items()}
    known_cpi = cpi.loc[:end]
    cost_bps = float(criteria["costs"]["bps_per_unit_turnover"])
    starts = start_dates(pd.DatetimeIndex(cut["close"].index), cfg.start_years, end)
    rows: list[dict] = []
    for p in cfg.portfolios:
        paths = {year: portfolio_returns(p, cut, day, cost_bps) for year, day in starts.items()}
        for rate in cfg.rates:
            per_year: dict[int, dict] = {}
            for year, returns in paths.items():
                last = pd.DatetimeIndex(returns.index)[-1]
                monthly = monthly_withdrawals(rate, year, last.year, known_cpi)
                per_year[year] = path_metrics(withdrawal_path(returns, monthly), known_cpi)
            first = min(per_year)
            worst_real, worst_year = min((m["end_real"], y) for y, m in per_year.items())
            rows.append(
                {
                    "portfolio": p.id,
                    "rate": rate,
                    "first_year": first,
                    "first": per_year[first],
                    "worst_year": worst_year,
                    "worst_end_real": worst_real,
                    "per_year": per_year,
                }
            )
    return rows


def year_one_value(ret: float, rate: float, inflation: float) -> tuple[float, float]:
    """Value after one year as a fraction of the start: (1 + scenario return)
    minus the year's withdrawals (12 x rate / 12; no raise in year one),
    nominal, and real (deflated by the scenario's inflation)."""
    nominal = 1 + ret - rate
    return nominal, nominal / (1 + inflation)


def year_one_rows(
    portfolios: list[Portfolio], scenarios: list[Scenario], rates: list[float]
) -> list[dict]:
    """Per portfolio x scenario x rate, using the worse state (lower return)."""
    rows = []
    for p in portfolios:
        states = portfolio_states(p)
        for s in scenarios:
            ret, state = min((scenario_return(mix, s), name) for name, mix in states.items())
            for rate in rates:
                nominal, real = year_one_value(ret, rate, s.inflation)
                rows.append(
                    {
                        "portfolio": p.id,
                        "scenario": s.name,
                        "state": state,
                        "rate": rate,
                        "nominal": nominal,
                        "real": real,
                    }
                )
    return rows
