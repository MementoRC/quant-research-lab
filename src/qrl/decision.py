"""Decision helper (spec: docs/methodology/decision-helper.md): a fixed set of
portfolios at 100% of capital under historical windows, judgement-based
shocks and CPI-indexed withdrawals. A decision aid: it selects nothing and
recommends nothing. Pure functions; callers inject data and configs. Every
price and CPI frame is cut at the research end (2018-12-31) before use, so
validation and holdout data never enter, and `slice_period(...,
unseal_holdout=True)` is never called.
"""

from __future__ import annotations

import inspect

import numpy as np
import pandas as pd

from .core_compare import Build, candidate_weights
from .decision_config import CashAssumption, DecisionConfig, Portfolio, Scenario, portfolio_states
from .decision_withdraw import monthly_withdrawals, path_metrics, withdrawal_path
from .engine import run_backtest
from .metrics import compute_metrics
from .periods import period_bounds
from .portfolio import combine_portfolio
from .strategies import REGISTRY
from .stress import Cell, PortfolioDef, StressConfig, run_stress, window_drawdown
from .true_cash import cash_leg_returns, mix_returns, nominal_loss_stats

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


def worst_state(states: dict[str, dict[str, float]], scenario: Scenario) -> tuple[str, float]:
    """The worse state (the larger nominal loss) and its return. One rule for
    every table, so a tie names the same state everywhere."""
    loss, name = max((-scenario_return(mix, scenario), n) for n, mix in states.items())
    return name, -loss


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
            worst, _ = worst_state(states, s)
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


def assumption_returns(
    cfg: DecisionConfig,
    data: dict[str, pd.DataFrame],
    cpi: pd.Series,
    start: pd.Timestamp,
    cost_bps: float,
) -> pd.Series | None:
    """Daily returns of the cash-assumption row (spec:
    docs/methodology/true-cash-sleeve.md): the base portfolio's
    `portfolio_returns`, unchanged, mixed daily with a cash leg earning CPI
    inflation plus real_yield. `data` and `cpi` must already be cut at the
    data end. None without a cash_assumption; raises ValueError if its base
    is not among the portfolios."""
    rows = cash_rows(cfg)
    return _row_returns(rows[0], cfg, data, cpi, start, cost_bps) if rows else None


def cash_rows(cfg: DecisionConfig) -> tuple[CashAssumption, ...]:
    """The cash-assumption rows in A-G order (spec:
    docs/methodology/true-cash-all-cores.md); empty without any."""
    return cfg.cash_assumptions


def _row_returns(
    ca: CashAssumption,
    cfg: DecisionConfig,
    data: dict[str, pd.DataFrame],
    cpi: pd.Series,
    start: pd.Timestamp,
    cost_bps: float,
) -> pd.Series:
    by_id = {p.id: p for p in cfg.portfolios}
    if ca.base not in by_id:
        raise ValueError(f"cash_assumption base {ca.base!r} is not among the portfolios")
    base = portfolio_returns(by_id[ca.base], data, start, cost_bps)
    cash = cash_leg_returns(
        pd.DatetimeIndex(base.index), pd.DatetimeIndex(data["close"].index), cpi, ca.real_yield
    )
    return mix_returns(base, cash, ca.cash_share)


def all_assumption_returns(
    cfg: DecisionConfig,
    data: dict[str, pd.DataFrame],
    cpi: pd.Series,
    start: pd.Timestamp,
    cost_bps: float,
) -> dict[str, pd.Series]:
    """Daily returns of every cash-assumption row, keyed by id in A-G order
    (empty without any); each as `assumption_returns` computes one."""
    return {ca.id: _row_returns(ca, cfg, data, cpi, start, cost_bps) for ca in cash_rows(cfg)}


def _withdrawal_rows_for(
    pid: str, paths: dict[int, pd.Series], cfg: DecisionConfig, cpi: pd.Series
) -> list[dict]:
    """One row per withdrawal rate for row `pid`: the first start year's path
    metrics, the worst start year by real ending value, and every start
    year's metrics. `paths` maps start year to daily returns; `cpi` is
    already cut at the data end. Also the equal-horizon worst case (spec:
    docs/methodology/report-wording.md, section 6): the horizon H is the last
    path's end year minus the last start year plus one, every path is cut to
    its first H years, and `worst5_*` is the lowest real value after H years."""
    end_years = {y: pd.DatetimeIndex(r.index)[-1].year for y, r in paths.items()}
    horizon = end_years[max(paths)] - max(paths) + 1
    cut = {y: _first_years(r, horizon) for y, r in paths.items()}
    rows: list[dict] = []
    for rate in cfg.rates:
        per_year = {
            y: path_metrics(
                withdrawal_path(r, monthly_withdrawals(rate, y, end_years[y], cpi)), cpi
            )
            for y, r in paths.items()
        }
        at_horizon = {
            y: path_metrics(
                withdrawal_path(r, monthly_withdrawals(rate, y, y + horizon - 1, cpi)), cpi
            )["end_real"]
            for y, r in cut.items()
        }
        first = min(per_year)
        worst_real, worst_year = min((m["end_real"], y) for y, m in per_year.items())
        worst5_real, worst5_year = min((v, y) for y, v in at_horizon.items())
        rows.append(
            {
                "portfolio": pid,
                "rate": rate,
                "first_year": first,
                "first": per_year[first],
                "worst_year": worst_year,
                "worst_end_real": worst_real,
                "horizons": {y: end_years[y] - y + 1 for y in paths},
                "horizon_years": horizon,
                "worst5_year": worst5_year,
                "worst5_end_real": worst5_real,
                "per_year": per_year,
            }
        )
    return rows


def _first_years(returns: pd.Series, years: int) -> pd.Series:
    """The path's returns for its first `years` calendar years. Paths start on the
    first trading day of a January, so this is start to start + `years` years,
    exclusive, without spilling a few days into the next January."""
    index = pd.DatetimeIndex(returns.index)
    return returns[index.year < index[0].year + years]


def withdrawal_rows(
    cfg: DecisionConfig, data: dict[str, pd.DataFrame], cpi: pd.Series, criteria: dict
) -> list[dict]:
    """Per portfolio and rate, then the cash-assumption row if the config has
    one (spec: docs/methodology/true-cash-sleeve.md): the first start year's
    path metrics, the worst start year by real ending value, and every start
    year's metrics. Price and CPI (availability-dated) frames are cut at the
    data end first."""
    end = data_end(criteria)
    cut = {k: v.loc[:end] for k, v in data.items()}
    known_cpi = cpi.loc[:end]
    cost_bps = float(criteria["costs"]["bps_per_unit_turnover"])
    starts = start_dates(pd.DatetimeIndex(cut["close"].index), cfg.start_years, end)
    rows: list[dict] = []
    for p in cfg.portfolios:
        paths = {year: portfolio_returns(p, cut, day, cost_bps) for year, day in starts.items()}
        rows += _withdrawal_rows_for(p.id, paths, cfg, known_cpi)
    per_start = {
        year: all_assumption_returns(cfg, cut, known_cpi, day, cost_bps)
        for year, day in starts.items()
    }
    for ca in cash_rows(cfg):
        assumed = {year: rets[ca.id] for year, rets in per_start.items()}
        rows += _withdrawal_rows_for(ca.id, assumed, cfg, known_cpi)
    return rows


def research_start(index: pd.DatetimeIndex, criteria: dict) -> pd.Timestamp:
    """The first trading day on or after the research start (as `qrl.longrun`)."""
    begin, _ = period_bounds(criteria, "research")
    if begin is None:
        raise ValueError("criteria: the research period has no start")
    after = index[index >= begin]
    if after.empty:
        raise ValueError(f"no trading day on or after the research start {begin.date()}")
    return pd.Timestamp(after[0])


def return_rows(
    cfg: DecisionConfig,
    data: dict[str, pd.DataFrame],
    criteria: dict,
    cpi: pd.Series | None = None,
) -> list[dict]:
    """Research-period return per portfolio, in config order (spec:
    docs/methodology/defensive-sleeve.md), then the cash-assumption row if
    the config has one (docs/methodology/true-cash-sleeve.md; it needs
    `cpi`): bought at the first research trading day, held to the data end
    with no withdrawals, paying criteria cost_bps. CAGR from
    `qrl.metrics.compute_metrics`; max drawdown (positive) from
    `qrl.stress.window_drawdown`, which counts the start as a peak (spec:
    docs/methodology/report-wording.md, item 4). `lost_return` is A's CAGR
    minus the row's, in CAGR units (0.01 = one percentage point); None
    without portfolio A. Price and CPI frames are cut at the data end first."""
    end = data_end(criteria)
    rows = cash_rows(cfg)
    if rows and cpi is None:
        raise ValueError(f"return_rows: the cash_assumption row {rows[0].id} needs `cpi`")
    cut = {k: v.loc[:end] for k, v in data.items()}
    first = research_start(pd.DatetimeIndex(cut["close"].index), criteria)
    cost_bps = float(criteria["costs"]["bps_per_unit_turnover"])
    series = {p.id: portfolio_returns(p, cut, first, cost_bps) for p in cfg.portfolios}
    if cpi is not None:
        series.update(all_assumption_returns(cfg, cut, cpi.loc[:end], first, cost_bps))
    metrics = {pid: compute_metrics(r) for pid, r in series.items()}
    base = metrics["A"]["cagr"] if "A" in metrics else None
    return [
        {
            "portfolio": pid,
            "cagr": m["cagr"],
            "max_drawdown": window_drawdown(series[pid]),
            "lost_return": None if base is None else base - m["cagr"],
        }
        for pid, m in metrics.items()
    ]


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
            state, ret = worst_state(states, s)
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


def engine_default_cost_bps() -> float:
    """The engine's own default cost, which `qrl.stress` replay cells pay."""
    return float(inspect.signature(run_backtest).parameters["cost_bps"].default)


def run_decision(
    cfg: DecisionConfig,
    data: dict[str, pd.DataFrame],
    cpi: pd.Series,
    criteria: dict,
    stress_sha256: str,
) -> dict:
    """The whole report as plain data (rendered by `qrl.decision_report`).
    Raises ValueError on any refusal (spec "Refusals")."""
    rows = cash_rows(cfg)
    return {
        "data_end": str(data_end(criteria).date()),
        "decision_sha256": cfg.sha256,
        "candidates_sha256": cfg.candidates_sha256,
        "stress_sha256": stress_sha256,
        "candidate_count": cfg.candidate_count,
        "cost_bps": float(criteria["costs"]["bps_per_unit_turnover"]),
        "engine_cost_bps": engine_default_cost_bps(),
        "proxied_threshold": cfg.proxied_threshold,
        "rates": cfg.rates,
        "start_years": cfg.start_years,
        "portfolios": [
            {"id": p.id, "label": p.label, "states": portfolio_states(p)} for p in cfg.portfolios
        ],
        "scenarios": [
            {"name": s.name, "label": s.label, "returns": s.returns, "inflation": s.inflation}
            for s in cfg.scenarios
        ],
        "windows": stress_rows(cfg, data, criteria),
        "scenario_rows": scenario_rows(cfg.portfolios, cfg.scenarios),
        "withdrawals": withdrawal_rows(cfg, data, cpi, criteria),
        "year_one": year_one_rows(cfg.portfolios, cfg.scenarios, cfg.rates),
        "returns": return_rows(cfg, data, criteria, cpi),
        "cash_assumption": _cash_fields(rows[0]) if len(rows) == 1 else None,
        "cash_assumptions": [{**_cash_fields(ca), "pair": ca.pair} for ca in rows],
        "cash_nominal_loss": _cash_nominal_loss(cfg, data, cpi, criteria),
    }


def _cash_nominal_loss(
    cfg: DecisionConfig, data: dict[str, pd.DataFrame], cpi: pd.Series, criteria: dict
) -> dict | None:
    """`nominal_loss_stats` of the cash leg over the research period to the data
    end, as the assumption rows use it; None without a cash-assumption row."""
    rows = cash_rows(cfg)
    if not rows:
        return None
    end = data_end(criteria)
    trading = pd.DatetimeIndex(data["close"].loc[:end].index)
    days = trading[trading >= research_start(trading, criteria)]
    if len({r.real_yield for r in rows}) > 1:
        raise ValueError("cash_assumption rows have different real_yield values")
    leg = cash_leg_returns(days, trading, cpi.loc[:end], rows[0].real_yield)
    return nominal_loss_stats(leg)


def _cash_fields(ca: CashAssumption) -> dict:
    return {
        "id": ca.id,
        "label": ca.label,
        "base": ca.base,
        "cash_share": ca.cash_share,
        "real_yield": ca.real_yield,
    }


# Public name for qrl.shock (spec: docs/methodology/whatif-shock.md). It points to
# the same object; the private name and its behaviour are unchanged.
first_years = _first_years
