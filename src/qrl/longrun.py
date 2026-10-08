"""Long-run withdrawals (spec: docs/methodology/longrun.md): 30-year paths
built by a paired circular block bootstrap of 2005-2018 calendar months, for
the decision helper's portfolios plus a labelled CASH +1% real assumption
row. It compares; it selects and recommends nothing. Pure functions; callers
inject data and configs. Every frame is cut at the research end (2018-12-31)
before use, so validation and holdout data never enter.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .decision import data_end, portfolio_returns
from .decision_config import DecisionConfig
from .decision_withdraw import usable_cpi
from .periods import period_bounds

DEPLETED = 1e-9  # of the starting value: at or below, the path is empty (spec "Withdrawals")
CHECKPOINT_YEARS = (20, 25, 30)
_KEYS = (
    "version",
    "decision_sha256",
    "seed",
    "n_paths",
    "block_months",
    "horizon_years",
    "real_floor",
    "withdrawal_rates",
    "cash_real_yield",
)


@dataclass(frozen=True)
class LongrunConfig:
    seed: int
    n_paths: int
    block_months: int
    horizon_years: int
    real_floor: float
    rates: list[float]
    cash_real_yield: float
    sha256: str


def load_longrun_config(path: str | Path, decision_sha256: str) -> LongrunConfig:
    """Read config/longrun.yaml. Raises ValueError if it cannot be loaded, a key
    is missing, the version is not 1, the pinned decision.yaml sha256 does not
    match `decision_sha256`, or the horizon is not a whole number of blocks."""
    try:
        raw = Path(path).read_bytes()
        doc = yaml.safe_load(raw) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"longrun.yaml: cannot be loaded ({exc})") from exc
    if not isinstance(doc, dict):
        raise ValueError("longrun.yaml: cannot be loaded (not a mapping)")
    missing = [k for k in _KEYS if k not in doc]
    if missing:
        raise ValueError(f"longrun.yaml: missing key(s) {missing}")
    if doc["version"] != 1:
        raise ValueError(f"longrun.yaml: unsupported version {doc['version']}")
    if doc["decision_sha256"] != decision_sha256:
        raise ValueError("decision.yaml changed: its sha256 does not match longrun.yaml's pin")
    months = int(doc["horizon_years"]) * 12
    if months % int(doc["block_months"]):
        raise ValueError(
            f"longrun.yaml: horizon of {months} months is not a whole number of "
            f"{doc['block_months']}-month blocks"
        )
    return LongrunConfig(
        seed=int(doc["seed"]),
        n_paths=int(doc["n_paths"]),
        block_months=int(doc["block_months"]),
        horizon_years=int(doc["horizon_years"]),
        real_floor=float(doc["real_floor"]),
        rates=[float(r) for r in doc["withdrawal_rates"]],
        cash_real_yield=float(doc["cash_real_yield"]),
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def monthly_returns(daily: pd.Series) -> pd.Series:
    """Daily net returns compounded to calendar-month returns, indexed by
    monthly Period. Refuses any NaN (a NaN is never turned into cash)."""
    if daily.isna().any():
        bad = pd.DatetimeIndex(daily.index)[daily.isna().to_numpy()][0]
        raise ValueError(f"NaN return on {bad.date()}")
    months = pd.DatetimeIndex(daily.index).to_period("M")
    return (1.0 + daily).groupby(months).prod() - 1.0


def monthly_inflation(cpi: pd.Series, months: pd.PeriodIndex) -> pd.Series:
    """Inflation of each month m: usable CPI on m's last calendar day over
    usable CPI on (m-1)'s last calendar day, minus 1 (`usable_cpi`'s
    availability rule; raises "missing CPI" if none is usable). Calendar month
    ends, not trading days: spec amendment 2026-10-08."""

    def end(p: pd.Period) -> pd.Timestamp:
        return p.to_timestamp(how="end").normalize()

    out = [usable_cpi(cpi, end(m)) / usable_cpi(cpi, end(m - 1)) - 1.0 for m in months]
    return pd.Series(out, index=months, dtype=float)


def block_starts(seed: int, n_paths: int, n_blocks: int, n_months: int) -> np.ndarray:
    """Start month of every block, uniform over all months: shape
    (n_paths, n_blocks). One draw shared by every portfolio (paired)."""
    return np.random.default_rng(seed).integers(0, n_months, size=(n_paths, n_blocks))


def month_indices(starts: np.ndarray, block_months: int, n_months: int) -> np.ndarray:
    """Month positions of every path: each block is `block_months`
    consecutive months, wrapping past the last month to the first (circular).
    Shape (n_paths, n_blocks * block_months)."""
    idx = (starts[:, :, None] + np.arange(block_months)) % n_months
    return idx.reshape(starts.shape[0], -1)


@dataclass(frozen=True)
class Paths:
    nominal: np.ndarray  # (n_paths, months): value after each month, start = 1.0
    real: np.ndarray  # nominal deflated by the path's cumulative inflation
    depleted: np.ndarray  # (n_paths,): month 1..T the path emptied, 0 if never


def run_paths(
    returns: np.ndarray, inflation: np.ndarray, idx: np.ndarray, rate: float
) -> Paths:
    """Withdrawal paths over the month positions `idx` (from `month_indices`).
    Each month: V = (V - w) x (1 + r). w = rate / 12 in months 1-12, then
    raised every 12 months by the path's own inflation over the previous 12
    months. At or below DEPLETED the path is empty from that month on."""
    r = np.asarray(returns, dtype=float)[idx]
    pi = np.asarray(inflation, dtype=float)[idx]
    n_paths, n_months = idx.shape
    value = np.ones(n_paths)
    w = np.full(n_paths, rate / 12)
    level = np.ones(n_paths)
    year = np.ones(n_paths)
    nominal = np.empty((n_paths, n_months))
    real = np.empty((n_paths, n_months))
    depleted = np.zeros(n_paths, dtype=int)
    for t in range(n_months):
        if t and t % 12 == 0:
            w = w * year
            year = np.ones(n_paths)
        alive = depleted == 0
        value = np.where(alive, (value - w) * (1.0 + r[:, t]), 0.0)
        emptied = alive & (value <= DEPLETED)
        value[emptied] = 0.0
        depleted[emptied] = t + 1
        level = level * (1.0 + pi[:, t])
        year = year * (1.0 + pi[:, t])
        nominal[:, t] = value
        real[:, t] = value / level
    return Paths(nominal, real, depleted)


def cash_assumption_returns(inflation: np.ndarray, real_yield: float) -> np.ndarray:
    """The labelled assumption row: each month earns that month's inflation
    plus `real_yield` a year, so its real return is exactly `real_yield`."""
    monthly_real = (1.0 + real_yield) ** (1 / 12)
    return np.asarray((1.0 + np.asarray(inflation, dtype=float)) * monthly_real - 1.0)


def summarize(paths: Paths, floor: float) -> dict:
    """Spec "Outputs": chance of depletion by each checkpoint year (month
    12 x N or earlier), median depletion year among depleted paths (year =
    ceil(month / 12), lower median; None if none), chance the real value is
    ever below `floor`, and the final real value's median and 5th percentile
    (depleted paths count as 0)."""
    dep = paths.depleted
    by = {y: float(np.mean((dep > 0) & (dep <= 12 * y))) for y in CHECKPOINT_YEARS}
    years = np.ceil(dep[dep > 0] / 12)
    median_year = int(np.quantile(years, 0.5, method="lower")) if years.size else None
    end = paths.real[:, -1]
    return {
        "depleted_by": by,
        "median_depletion_year": median_year,
        "below_floor": float(np.mean((paths.real < floor).any(axis=1))),
        "end_real_median": float(np.median(end)),
        "end_real_p5": float(np.quantile(end, 0.05)),
    }


CASH_ID = "CASH"
CASH_ASSUMPTION = "CASH +1% real (assumption)"


def run_longrun(
    lcfg: LongrunConfig,
    dcfg: DecisionConfig,
    data: dict[str, pd.DataFrame],
    cpi: pd.Series,
    criteria: dict,
) -> dict:
    """The whole report as plain data (rendered by `qrl.longrun_report`).
    Price and CPI frames are cut at the research end first. Raises
    ValueError on any refusal (spec "Refusals")."""
    end = data_end(criteria)
    begin, _ = period_bounds(criteria, "research")
    if begin is None:
        raise ValueError("criteria: the research period has no start")
    cut = {k: v.loc[:end] for k, v in data.items()}
    known_cpi = cpi.loc[:end]
    cost_bps = float(criteria["costs"]["bps_per_unit_turnover"])
    days = pd.DatetimeIndex(cut["close"].index)
    after = days[days >= begin]
    if after.empty:
        raise ValueError(f"no trading day on or after the research start {begin.date()}")
    first = pd.Timestamp(after[0])
    monthly = {
        p.id: monthly_returns(portfolio_returns(p, cut, first, cost_bps)) for p in dcfg.portfolios
    }
    months = pd.PeriodIndex(next(iter(monthly.values())).index)
    for pid, series in monthly.items():
        if not series.index.equals(months):
            raise ValueError(f"portfolio {pid}: months differ from the others")
    expected = pd.period_range(begin, end, freq="M")
    if not months.equals(expected):
        raise ValueError(
            f"months must run {expected[0]}..{expected[-1]} ({len(expected)} months), "
            f"got {months[0]}..{months[-1]} ({len(months)} months)"
        )
    inflation = monthly_inflation(known_cpi, months).to_numpy()
    n_months = len(months)
    n_blocks = lcfg.horizon_years * 12 // lcfg.block_months
    idx = month_indices(
        block_starts(lcfg.seed, lcfg.n_paths, n_blocks, n_months), lcfg.block_months, n_months
    )
    if idx.shape[1] != lcfg.horizon_years * 12:
        raise ValueError(
            f"paths are {idx.shape[1]} months long, expected {lcfg.horizon_years * 12}"
        )
    named: list[tuple[str, np.ndarray]] = []
    for pid, s in monthly.items():
        named.append((pid, s.to_numpy()))
        if pid == CASH_ID:
            cash = cash_assumption_returns(inflation, lcfg.cash_real_yield)
            named.append((CASH_ASSUMPTION, cash))
    rows = []
    for rate in lcfg.rates:
        for name, r in named:
            paths = run_paths(r, inflation, idx, rate)
            rows.append({"rate": rate, "portfolio": name, **summarize(paths, lcfg.real_floor)})
    return {
        "data_end": str(end.date()),
        "first_month": str(months[0]),
        "last_month": str(months[-1]),
        "n_months": n_months,
        "seed": lcfg.seed,
        "n_paths": lcfg.n_paths,
        "block_months": lcfg.block_months,
        "horizon_years": lcfg.horizon_years,
        "real_floor": lcfg.real_floor,
        "cash_real_yield": lcfg.cash_real_yield,
        "rates": lcfg.rates,
        "longrun_sha256": lcfg.sha256,
        "decision_sha256": dcfg.sha256,
        "cost_bps": cost_bps,
        "rows": rows,
    }
