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

from .decision_withdraw import usable_cpi

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


def monthly_inflation(
    cpi: pd.Series, trading_days: pd.DatetimeIndex, months: pd.PeriodIndex
) -> pd.Series:
    """Inflation of each month m: usable CPI on m's last trading day over
    usable CPI on (m-1)'s last trading day, minus 1 (`usable_cpi`'s
    availability rule; raises "missing CPI" if none is usable)."""
    days = pd.DatetimeIndex(trading_days)
    last: dict[pd.Period, pd.Timestamp] = {}
    for day in days.sort_values():
        last[day.to_period("M")] = day  # ascending, so the month's last day wins
    out = []
    for m in months:
        for need in (m - 1, m):
            if need not in last:
                raise ValueError(f"no trading day in {need} for month {m}'s inflation")
        out.append(usable_cpi(cpi, last[m]) / usable_cpi(cpi, last[m - 1]) - 1.0)
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
