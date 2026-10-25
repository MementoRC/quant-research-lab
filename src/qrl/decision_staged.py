"""Staged entry (spec: docs/methodology/staged-entry.md): invest the starting
cash all at once (lump sum) or in equal monthly tranches over N months, while
drawing the fixed CPI-indexed income, per core, staging period, cash variant
and withdrawal rate, in the decision helper's historical view (120 monthly
starts) and the long run's resampled paths. A comparison: no pass/fail rule,
no search trial; it selects and recommends nothing. Pure functions; callers
inject data and configs. Every price and CPI frame is cut at the research end
(2018-12-31) before use, so validation and holdout data never enter. The lump
sum is the same runner with one tranche and equals `withdrawal_path` and
`run_paths` exactly; that code and every number it publishes are unchanged.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .decision import cash_rows, data_end, portfolio_returns, research_start
from .decision_config import DecisionConfig, Portfolio
from .decision_rules import longrun_indices, month_starts
from .decision_withdraw import DEPLETED, monthly_inflation, usable_cpi
from .longrun import (
    CASH_ID,
    LongrunConfig,
    cash_assumption_returns,
    check_cash_assumption,
    check_withdrawal_rates,
    monthly_returns,
)
from .periods import period_bounds
from .true_cash import cash_leg_returns

_KEYS = (
    "version",
    "decision_sha256",
    "longrun_sha256",
    "periods_months",
    "cash_variants",
    "portfolios",
)
CASH_VARIANTS = ("shy", "real_plus_1")
_WHERE = "staged_entry.yaml"
FIRST_START = pd.Period("2005-01", freq="M")  # spec "Historical starts"
LAST_START = pd.Period("2014-12", freq="M")
HORIZON_MONTHS = 48  # the start month counts as the first
YEAR5_MONTHS = 60


@dataclass(frozen=True)
class StagedConfig:
    periods: list[int]  # staging months, 0 = lump sum first, in config order
    cash_variants: list[str]  # CASH_VARIANTS entries, in config order
    portfolios: list[str]  # decision.yaml portfolio ids, in config order
    sha256: str


def _read(path: str | Path) -> tuple[dict, bytes]:
    try:
        raw = Path(path).read_bytes()
        doc = yaml.safe_load(raw)
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"{_WHERE}: cannot be loaded ({exc})") from exc
    if not isinstance(doc, dict):
        raise ValueError(f"{_WHERE}: cannot be loaded (not a mapping)")
    return doc, raw


def _list(doc: dict, key: str) -> list:
    value = doc[key]
    if not isinstance(value, list) or not value:
        raise ValueError(f"{_WHERE}: `{key}` must be a non-empty list")
    dupes = sorted({str(v) for v in value if value.count(v) > 1})
    if dupes:
        raise ValueError(f"{_WHERE}: duplicate `{key}` entries {dupes}")
    return value


def _periods(doc: dict) -> list[int]:
    periods = _list(doc, "periods_months")
    bad = [p for p in periods if isinstance(p, bool) or not isinstance(p, int) or p < 0]
    if bad:
        raise ValueError(f"{_WHERE}: periods_months {bad} must be non-negative integers")
    if periods[0] != 0:
        raise ValueError(f"{_WHERE}: periods_months must start with 0 (the lump sum)")
    return [int(p) for p in periods]


def load_staged_config(path: str | Path, dcfg: DecisionConfig, lcfg: LongrunConfig) -> StagedConfig:
    """Read config/staged_entry.yaml (spec "Configuration"). Raises ValueError
    if it cannot be loaded, has an unknown or a missing key, a version other
    than 1, a decision.yaml or longrun.yaml pin that does not match, periods
    that are not distinct non-negative integers starting with 0, an unknown
    cash variant, a portfolio not in decision.yaml or equal to CASH, an empty
    or duplicated list; `real_plus_1` needs a decision.yaml cash_assumptions
    row whose real_yield equals longrun.yaml's cash_real_yield."""
    doc, raw = _read(path)
    unknown = sorted(str(k) for k in doc.keys() - set(_KEYS))
    if unknown:
        raise ValueError(f"{_WHERE}: unknown key(s) {unknown}")
    missing = [k for k in _KEYS if k not in doc]
    if missing:
        raise ValueError(f"{_WHERE}: missing key(s) {missing}")
    if doc["version"] != 1:
        raise ValueError(f"{_WHERE}: unsupported version {doc['version']}")
    if doc["decision_sha256"] != dcfg.sha256:
        raise ValueError(f"decision.yaml changed: its sha256 does not match {_WHERE}'s pin")
    if doc["longrun_sha256"] != lcfg.sha256:
        raise ValueError(f"longrun.yaml changed: its sha256 does not match {_WHERE}'s pin")
    periods = _periods(doc)
    variants = [str(v) for v in _list(doc, "cash_variants")]
    strange = [v for v in variants if v not in CASH_VARIANTS]
    if strange:
        raise ValueError(f"{_WHERE}: unknown cash variant(s) {strange}")
    if "real_plus_1" in variants:
        if not cash_rows(dcfg):
            raise ValueError(f"{_WHERE}: real_plus_1 needs a cash_assumptions row in decision.yaml")
        check_cash_assumption(lcfg, dcfg)
    known = {p.id for p in dcfg.portfolios}
    portfolios = [str(p) for p in _list(doc, "portfolios")]
    strangers = [p for p in portfolios if p not in known]
    if strangers:
        raise ValueError(f"{_WHERE}: portfolio(s) {strangers} not in decision.yaml")
    if CASH_ID in portfolios:
        raise ValueError(f"{_WHERE}: {CASH_ID} is excluded (staging into cash is a lump sum)")
    return StagedConfig(
        periods=periods,
        cash_variants=variants,
        portfolios=portfolios,
        sha256=hashlib.sha256(raw).hexdigest(),
    )


@dataclass(frozen=True)
class StagedRun:
    """The result of `run_staged` for every path."""

    values: np.ndarray  # (n_paths, n_steps): cash + tranches after each step; 1.0 before begin
    depleted: np.ndarray  # (n_paths,) int64: step + 1 at which the path emptied; 0 = never


def run_staged(
    returns: np.ndarray,
    source: np.ndarray,
    cash: np.ndarray,
    withdraw: np.ndarray,
    buy: np.ndarray,
    n_tranches: int,
    begin: np.ndarray | None = None,
) -> StagedRun:
    """Spec "Value path". Each path starts at step `begin` (default 0) with 1.0
    in cash and nothing invested. At each step, in this order: withdraw
    `withdraw[p, t]` from cash first, then from the invested part
    (proportionally across the tranches already bought, no extra cost); buy
    tranche `buy[p, t]` (-1 = none): 1 / n_tranches of the starting value, or
    all remaining cash if less or if it is the last tranche; then apply the
    step's returns: cash earns `cash[p, t]`, group g earns
    `returns[source[p, g], t]`. `source` has one column per tranche, or one
    column shared by all tranches. Cash at or below DEPLETED counts as 0. A
    total at or below DEPLETED, after the withdrawal and tranche or after the
    returns, empties the path for good; one emptied before the returns gets
    none. With one tranche this is `withdrawal_path` / `run_paths`, same
    operations in the same order."""
    r_all = np.asarray(returns, dtype=float)
    src = np.asarray(source, dtype=np.int64)
    c_all = np.asarray(cash, dtype=float)
    w_all = np.asarray(withdraw, dtype=float)
    b_all = np.asarray(buy, dtype=np.int64)
    n_paths, n_steps = w_all.shape
    if n_tranches < 1:
        raise ValueError("n_tranches must be 1 or more")
    if src.ndim != 2 or src.shape[0] != n_paths or src.shape[1] not in (1, n_tranches):
        raise ValueError(f"source must have shape ({n_paths}, 1) or ({n_paths}, {n_tranches})")
    if c_all.shape != w_all.shape or b_all.shape != w_all.shape or r_all.shape[1] != n_steps:
        raise ValueError("returns, cash, withdraw and buy must cover the same steps")
    if b_all.max(initial=-1) >= n_tranches:
        raise ValueError(f"buy names a tranche beyond the {n_tranches} tranches")
    start = np.zeros(n_paths, np.int64) if begin is None else np.asarray(begin, np.int64)
    shared = src.shape[1] == 1
    size = 1.0 / n_tranches
    rows = np.arange(n_paths)
    bal = np.ones(n_paths)
    held = np.zeros(src.shape)
    values = np.ones((n_paths, n_steps))
    depleted = np.zeros(n_paths, dtype=np.int64)
    for t in range(n_steps):
        live = (t >= start) & (depleted == 0)
        w = np.where(live, w_all[:, t], 0.0)
        take = np.minimum(bal, w)
        bal = bal - take
        bal[bal <= DEPLETED] = 0.0
        rest = w - take
        if shared:
            held[:, 0] -= rest
        else:
            invested = held.sum(axis=1)
            trim = (rest > 0) & (invested > 0)
            held[trim] *= ((invested[trim] - rest[trim]) / invested[trim])[:, None]
        k = np.where(live, b_all[:, t], -1)
        buying = k >= 0
        if buying.any():
            move = np.where(k == n_tranches - 1, bal, np.minimum(size, bal))
            move = np.where(buying, move, 0.0)
            group = np.zeros(n_paths, np.int64) if shared else np.maximum(k, 0)
            held[rows, group] += move
            bal = bal - move
            bal[bal <= DEPLETED] = 0.0
        total = bal + held.sum(axis=1)
        empty = live & (total <= DEPLETED)
        bal[empty], held[empty], total[empty] = 0.0, 0.0, 0.0
        depleted[empty] = t + 1
        grow = live & ~empty
        r = r_all[src, t]
        c = c_all[:, t]
        if np.isnan(r[grow]).any() or np.isnan(c[grow]).any():
            raise ValueError(f"NaN return at step {t}")
        held = np.where(grow[:, None], held * (1.0 + r), held)
        bal = np.where(grow, bal * (1.0 + c), bal)
        total = bal + held.sum(axis=1)
        empty = grow & (total <= DEPLETED)
        bal[empty], held[empty], total[empty] = 0.0, 0.0, 0.0
        depleted[empty] = t + 1
        values[:, t] = np.where(t >= start, total, 1.0)
    return StagedRun(values, depleted)


def month_firsts(days: pd.DatetimeIndex) -> np.ndarray:
    """Positions in `days` of the first trading day of each calendar month."""
    firsts = np.flatnonzero(month_starts(days))
    months = pd.DatetimeIndex(days[firsts]).to_period("M")
    wanted = pd.period_range(months[0], months[-1], freq="M")
    if len(wanted) != len(months):
        gone = wanted[~wanted.isin(months)][0]
        raise ValueError(f"missing month {gone}: no trading day in a calendar month of the data")
    return firsts


def start_months(days: pd.DatetimeIndex, firsts: np.ndarray) -> np.ndarray:
    """Indices into `firsts` of the historical starts FIRST_START..LAST_START
    (spec "Historical starts"). Raises ValueError if a month has no trading day."""
    months = pd.Index(pd.DatetimeIndex(days[firsts]).to_period("M"))
    wanted = pd.period_range(FIRST_START, LAST_START, freq="M")
    pos = months.get_indexer(wanted)
    if (pos < 0).any():
        missing = [str(m) for m, p in zip(wanted, pos, strict=True) if p < 0]
        raise ValueError(f"no trading day in start month(s) {missing}")
    return pos.astype(np.int64)


def horizon_positions(firsts: np.ndarray, starts: np.ndarray) -> np.ndarray:
    """Position of the last trading day of the HORIZON_MONTHS-th month of each
    start, the start month counting as the first."""
    after = np.asarray(starts) + HORIZON_MONTHS
    if after.max() >= len(firsts):
        raise ValueError(f"the {HORIZON_MONTHS}-month horizon of a start runs past the data")
    return np.asarray(firsts[after] - 1)


def historical_withdrawals(
    days: pd.DatetimeIndex, begin: int, rate: float, cpi: pd.Series
) -> np.ndarray:
    """Amount withdrawn on each of `days` (0 off the month firsts), from
    days[begin]: rate / 12, raised on each 12-month anniversary by the CPI
    usable on its first trading day over the CPI usable on the previous one
    (spec "Raises"). Written as amount x (1 + change), as
    `monthly_withdrawals`, so a January start equals it bit for bit."""
    out = np.zeros(len(days))
    amount = rate / 12
    anchor = days[begin]
    for j, pos in enumerate(np.flatnonzero(month_starts(days[begin:])) + begin):
        if j and j % 12 == 0:
            change = usable_cpi(cpi, days[int(pos)]) / usable_cpi(cpi, anchor) - 1
            amount = amount * (1 + change)
            anchor = days[int(pos)]
        out[pos] = amount
    return out


def longrun_withdrawals(inflation: np.ndarray, rate: float) -> np.ndarray:
    """Per path and month: rate / 12 in months 1-12, then raised every 12
    months by the path's own inflation over the previous 12 (as `run_paths`,
    same operations in the same order)."""
    pi = np.asarray(inflation, dtype=float)
    n_paths, n_months = pi.shape
    out = np.empty((n_paths, n_months))
    w = np.full(n_paths, rate / 12)
    year = np.ones(n_paths)
    for t in range(n_months):
        if t and t % 12 == 0:
            w = w * year
            year = np.ones(n_paths)
        out[:, t] = w
        year = year * (1.0 + pi[:, t])
    return out


def longrun_levels(inflation: np.ndarray) -> np.ndarray:
    """Price level after each month, from 1.0 (as `run_paths`' real values)."""
    pi = np.asarray(inflation, dtype=float)
    out = np.empty(pi.shape)
    level = np.ones(pi.shape[0])
    for t in range(pi.shape[1]):
        level = level * (1.0 + pi[:, t])
        out[:, t] = level
    return out


def tranche_returns(
    p: Portfolio,
    cut: dict[str, pd.DataFrame],
    days: pd.DatetimeIndex,
    dates: pd.DatetimeIndex,
    cost_bps: float,
) -> np.ndarray:
    """One row per date: a fresh purchase of `p` on that date
    (`decision.portfolio_returns`, unchanged, the engine's entry cost inside
    its first day) on `days`, 0.0 before the date. Computed once per core and
    date and shared by every start and period (spec "Tranche returns")."""
    out = np.zeros((len(dates), len(days)))
    for i, d in enumerate(dates):
        held = np.asarray(days >= d)
        aligned = portfolio_returns(p, cut, d, cost_bps).reindex(days[held])
        if aligned.isna().any():
            raise ValueError(f"portfolio {p.id}: returns from {d.date()} do not cover the path")
        out[i, held] = aligned.to_numpy()
    return out


def daily_cash(
    variant: str,
    cash_portfolio: Portfolio,
    cut: dict[str, pd.DataFrame],
    days: pd.DatetimeIndex,
    trading: pd.DatetimeIndex,
    cpi: pd.Series,
    cost_bps: float,
    real_yield: float,
) -> np.ndarray:
    """Daily return of waiting cash on `days`. shy: the CASH portfolio (100%
    SHY) held from days[0] (Open question 1); real_plus_1:
    `true_cash.cash_leg_returns` (strict CPI check), `trading` giving each
    month's trading-day count."""
    if variant == "shy":
        r = portfolio_returns(cash_portfolio, cut, days[0], cost_bps).reindex(days)
    elif variant == "real_plus_1":
        r = cash_leg_returns(days, trading, cpi, real_yield)
    else:
        raise ValueError(f"unknown cash variant {variant!r}")
    if r.isna().any():
        raise ValueError(f"cash {variant}: a day has no return")
    return r.to_numpy(dtype=float)


def historical_run(
    tranche: np.ndarray,
    firsts: np.ndarray,
    starts: np.ndarray,
    cash: np.ndarray,
    withdraw: np.ndarray,
    period: int,
) -> StagedRun:
    """Every (cash variant, rate, start) path, in that order, start fastest.
    `tranche` row j is a purchase on month first j (`tranche_returns` on
    days[firsts[:n]]); `cash` is (n_variants, n_days); `withdraw` is
    (n_rates, n_starts, n_days). Tranche k of a start in month i0 is bought on
    firsts[i0 + k] and earns row i0 + k; period 0 is one tranche (lump sum)."""
    n_t = max(period, 1)
    n_v, n_days = cash.shape
    n_r, n_s, _ = withdraw.shape
    n = n_v * n_r * n_s
    v_of, r_of, s_of = np.unravel_index(np.arange(n), (n_v, n_r, n_s))
    i0 = np.asarray(starts)[s_of]
    if int(i0.max()) + n_t > len(tranche):
        raise ValueError("tranche returns do not cover every tranche date")
    source = i0[:, None] + np.arange(n_t)
    buy = np.full((n, n_days), -1, dtype=np.int64)
    for k in range(n_t):
        buy[np.arange(n), firsts[i0 + k]] = k
    return run_staged(tranche, source, cash[v_of], withdraw[r_of, s_of], buy, n_t, firsts[i0])


def longrun_run(core: np.ndarray, cash: np.ndarray, withdraw: np.ndarray, period: int) -> StagedRun:
    """Monthly paths (spec "Long run"): `core` and `cash` are each path's
    monthly returns (already indexed by `month_indices`), `withdraw` from
    `longrun_withdrawals`. Tranches are bought at the start of months
    0..N-1 and all earn the core's return (one shared group), with no entry
    cost, so period 0 equals `run_paths` exactly."""
    n_t = max(period, 1)
    n_paths, n_months = core.shape
    if n_t > n_months:
        raise ValueError(f"staging period {period} is longer than the {n_months}-month paths")
    buy = np.full((n_paths, n_months), -1, dtype=np.int64)
    buy[:, :n_t] = np.arange(n_t)
    return run_staged(core, np.arange(n_paths)[:, None], cash, withdraw, buy, n_t)


def path_measures(
    values: np.ndarray,
    begin: np.ndarray,
    horizon: np.ndarray,
    days: pd.DatetimeIndex,
    cpi: pd.Series,
) -> dict[str, np.ndarray]:
    """Per path (spec "Measures"): real value at the horizon and at the data
    end (the last of `days`), each deflated by the CPI usable on that day over
    the CPI usable on the start day; max drawdown of the total value from the
    start to the horizon, the starting 1.0 counting as a peak (Open question 2)."""
    usable: dict[int, float] = {}

    def at(pos: int) -> float:
        if pos not in usable:
            usable[pos] = usable_cpi(cpi, days[pos])
        return usable[pos]

    n, last = len(values), len(days) - 1
    real4, real_end, mdd = np.empty(n), np.empty(n), np.empty(n)
    for p in range(n):
        b, h = int(begin[p]), int(horizon[p])
        real4[p] = values[p, h] / (at(h) / at(b))
        real_end[p] = values[p, last] / (at(last) / at(b))
        seg = values[p, b : h + 1]
        peaks = np.maximum.accumulate(np.concatenate([[1.0], seg]))[1:]
        mdd[p] = float((1.0 - seg / peaks).max())
    return {"real4": real4, "real_end": real_end, "mdd": mdd}


def compare(staged: dict, lump: dict, months: list[str]) -> dict:
    """One staged row against the lump sum over the same starts: share of
    starts strictly above at the horizon; median, best and worst real gap
    (staged minus lump, fractions of the starting value) at the horizon and at
    the data end; worst staged max drawdown; largest staged-minus-lump
    drawdown (Open question 3); the start month with the lowest staged value."""
    gap = staged["real4"] - lump["real4"]
    end_gap = staged["real_end"] - lump["real_end"]
    return {
        "above": float(np.mean(staged["real4"] > lump["real4"])),
        "gap_median": float(np.median(gap)),
        "gap_best": float(gap.max()),
        "gap_worst": float(gap.min()),
        "mdd_worst": float(staged["mdd"].max()),
        "mdd_worst_diff": float((staged["mdd"] - lump["mdd"]).max()),
        "worst_start": months[int(np.argmin(staged["real4"]))],
        "end_gap_median": float(np.median(end_gap)),
        "end_gap_best": float(end_gap.max()),
        "end_gap_worst": float(end_gap.min()),
    }


def lump_only(lump: dict, months: list[str]) -> dict:
    """The lump-sum row: its own worst max drawdown and worst start; the
    comparison fields are None (Open question 6)."""
    return {
        "above": None,
        "gap_median": None,
        "gap_best": None,
        "gap_worst": None,
        "mdd_worst": float(lump["mdd"].max()),
        "mdd_worst_diff": None,
        "worst_start": months[int(np.argmin(lump["real4"]))],
        "end_gap_median": None,
        "end_gap_best": None,
        "end_gap_worst": None,
    }


def longrun_measures(run: StagedRun, levels: np.ndarray, horizon_years: int) -> dict:
    """Share of paths depleted by the horizon; median real value at the
    horizon and at year 5 (values over the path's price level). Depletion
    counts only within the horizon. Raises ValueError if `horizon_years` is
    longer than the path."""
    n_months = run.values.shape[1]
    if 12 * horizon_years > n_months:
        raise ValueError(
            f"horizon_years {horizon_years} is longer than the path's {n_months // 12} years"
        )
    real = run.values / levels
    return {
        "depleted": float(np.mean((run.depleted > 0) & (run.depleted <= 12 * horizon_years))),
        "real_end_median": float(np.median(real[:, horizon_years * 12 - 1])),
        "real_year5_median": float(np.median(real[:, YEAR5_MONTHS - 1])),
    }


def historical_rows(
    scfg: StagedConfig,
    dcfg: DecisionConfig,
    lcfg: LongrunConfig,
    data: dict[str, pd.DataFrame],
    cpi: pd.Series,
    criteria: dict,
) -> tuple[list[dict], dict]:
    """Per rate, portfolio, period and cash variant (in that order): the
    measures over the 120 historical starts, each to the data end. Price and
    CPI frames are cut at the data end first. Also the span for the header."""
    end = data_end(criteria)
    cut = {k: v.loc[:end] for k, v in data.items()}
    known_cpi = cpi.loc[:end]
    cost_bps = float(criteria["costs"]["bps_per_unit_turnover"])
    trading = pd.DatetimeIndex(cut["close"].index)
    days = trading[trading >= research_start(trading, criteria)]
    firsts = month_firsts(days)
    starts = start_months(days, firsts)
    horizon = horizon_positions(firsts, starts)
    months = [str(m) for m in pd.DatetimeIndex(days[firsts[starts]]).to_period("M")]
    by_id = {p.id: p for p in dcfg.portfolios}
    cash = np.vstack(
        [
            daily_cash(
                v, by_id[CASH_ID], cut, days, trading, known_cpi, cost_bps, lcfg.cash_real_yield
            )
            for v in scfg.cash_variants
        ]
    )
    withdraw = np.stack(
        [
            [historical_withdrawals(days, int(firsts[i]), rate, known_cpi) for i in starts]
            for rate in dcfg.rates
        ]
    )
    n_v, n_r, n_s = len(scfg.cash_variants), len(dcfg.rates), len(starts)
    s_of = np.tile(np.arange(n_s), n_v * n_r)
    begin, hz = firsts[starts][s_of], horizon[s_of]
    n_rows = int(starts.max()) + max(max(scfg.periods), 1)
    cells: dict[tuple, dict] = {}
    for pid in scfg.portfolios:
        tranche = tranche_returns(by_id[pid], cut, days, days[firsts[:n_rows]], cost_bps)
        per = {
            n: path_measures(
                historical_run(tranche, firsts, starts, cash, withdraw, n).values,
                begin,
                hz,
                days,
                known_cpi,
            )
            for n in scfg.periods
        }
        for ri, rate in enumerate(dcfg.rates):
            for vi, v in enumerate(scfg.cash_variants):
                block = slice((vi * n_r + ri) * n_s, (vi * n_r + ri + 1) * n_s)
                lump = {k: a[block] for k, a in per[0].items()}
                for n in scfg.periods:
                    staged = {k: a[block] for k, a in per[n].items()}
                    cells[(rate, pid, n, v)] = (
                        lump_only(lump, months) if n == 0 else compare(staged, lump, months)
                    )
    rows = [
        {"portfolio": pid, "period": n, "rate": rate, "variant": v, **cells[(rate, pid, n, v)]}
        for rate in dcfg.rates
        for pid in scfg.portfolios
        for n in scfg.periods
        for v in scfg.cash_variants
    ]
    span = {
        "n_starts": n_s,
        "first_start": months[0],
        "last_start": months[-1],
        "horizon_months": HORIZON_MONTHS,
    }
    return rows, span


def longrun_rows(
    scfg: StagedConfig,
    dcfg: DecisionConfig,
    lcfg: LongrunConfig,
    data: dict[str, pd.DataFrame],
    cpi: pd.Series,
    criteria: dict,
) -> tuple[list[dict], dict]:
    """Per rate, portfolio, period and cash variant (in that order) over the
    long run's paths (`decision_rules.longrun_indices`: the same seed, blocks
    and paths as longrun.md). Monthly returns are `monthly_returns` of
    `portfolio_returns` from the first research trading day; SHY cash is the
    CASH portfolio's, real + 1% is `longrun.cash_assumption_returns`. Price and
    CPI frames are cut at the data end first."""
    end = data_end(criteria)
    begin, _ = period_bounds(criteria, "research")
    if begin is None:
        raise ValueError("criteria: the research period has no start")
    cut = {k: v.loc[:end] for k, v in data.items()}
    known_cpi = cpi.loc[:end]
    cost_bps = float(criteria["costs"]["bps_per_unit_turnover"])
    first = research_start(pd.DatetimeIndex(cut["close"].index), criteria)
    by_id = {p.id: p for p in dcfg.portfolios}
    months = pd.period_range(begin, end, freq="M")
    monthly: dict[str, np.ndarray] = {}
    for pid in [*scfg.portfolios, CASH_ID]:
        series = monthly_returns(portfolio_returns(by_id[pid], cut, first, cost_bps))
        if not series.index.equals(months):
            raise ValueError(
                f"portfolio {pid}: months must run {months[0]}..{months[-1]} ({len(months)} months)"
            )
        monthly[pid] = series.to_numpy()
    inflation = monthly_inflation(known_cpi, months).to_numpy()
    cash = {
        "shy": monthly[CASH_ID],
        "real_plus_1": cash_assumption_returns(inflation, lcfg.cash_real_yield),
    }
    idx = longrun_indices(lcfg, len(months))
    pi = inflation[idx]
    levels = longrun_levels(pi)
    withdraw = {rate: longrun_withdrawals(pi, rate) for rate in dcfg.rates}
    rows = [
        {
            "portfolio": pid,
            "period": n,
            "rate": rate,
            "variant": v,
            **longrun_measures(
                longrun_run(monthly[pid][idx], cash[v][idx], withdraw[rate], n),
                levels,
                lcfg.horizon_years,
            ),
        }
        for rate in dcfg.rates
        for pid in scfg.portfolios
        for n in scfg.periods
        for v in scfg.cash_variants
    ]
    span = {"first_month": str(months[0]), "last_month": str(months[-1]), "n_months": len(months)}
    return rows, span


def run_staged_entry(
    scfg: StagedConfig,
    dcfg: DecisionConfig,
    lcfg: LongrunConfig,
    data: dict[str, pd.DataFrame],
    cpi: pd.Series,
    criteria: dict,
) -> dict:
    """The whole report as plain data (rendered by `qrl.staged_entry_report`).
    Rates and the cash yield come from decision.yaml, the paths from
    longrun.yaml, the cost from criteria.yaml. Raises ValueError on any refusal."""
    check_withdrawal_rates(lcfg, dcfg)
    if "real_plus_1" in scfg.cash_variants:
        check_cash_assumption(lcfg, dcfg)
    labels = {p.id: p.label for p in dcfg.portfolios}
    strangers = [pid for pid in [*scfg.portfolios, CASH_ID] if pid not in labels]
    if strangers:
        raise ValueError(f"staged_entry portfolio(s) {strangers} not in decision.yaml")
    historical, hspan = historical_rows(scfg, dcfg, lcfg, data, cpi, criteria)
    longrun, lspan = longrun_rows(scfg, dcfg, lcfg, data, cpi, criteria)
    return {
        "data_end": str(data_end(criteria).date()),
        "staged_sha256": scfg.sha256,
        "decision_sha256": dcfg.sha256,
        "longrun_sha256": lcfg.sha256,
        "portfolios": [{"id": pid, "label": labels[pid]} for pid in scfg.portfolios],
        "periods": list(scfg.periods),
        "variants": list(scfg.cash_variants),
        "rates": list(dcfg.rates),
        **hspan,
        **lspan,
        "seed": lcfg.seed,
        "n_paths": lcfg.n_paths,
        "block_months": lcfg.block_months,
        "horizon_years": lcfg.horizon_years,
        "cost_bps": float(criteria["costs"]["bps_per_unit_turnover"]),
        "historical": historical,
        "longrun": longrun,
    }
