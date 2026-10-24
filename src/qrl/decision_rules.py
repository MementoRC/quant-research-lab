"""Withdrawal rules (spec: docs/methodology/withdrawal-rules.md): the fixed
CPI-indexed withdrawal against four flexible rules, per portfolio, rule and
rate, in the decision helper's historical view and the long run's resampled
paths. A comparison: no pass/fail rule, no search trial; it selects and
recommends nothing. Pure functions; callers inject data and configs. Every
price and CPI frame is cut at the research end (2018-12-31) before use, so
validation and holdout data never enter. The fixed rule is an independent
re-implementation that equals `withdrawal_path` and `run_paths` exactly; that
code and every number it publishes are unchanged.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd
import yaml

from .decision import data_end, portfolio_returns, research_start, start_dates
from .decision_config import DecisionConfig
from .decision_withdraw import (
    DEPLETED,
    WithdrawalPath,
    monthly_inflation,
    path_metrics,
    usable_cpi,
)
from .longrun import (
    LongrunConfig,
    block_starts,
    check_withdrawal_rates,
    month_indices,
    monthly_returns,
)
from .periods import period_bounds

_KEYS = ("version", "decision_sha256", "longrun_sha256", "rules", "income_lines", "portfolios")
RULE_PARAMS: dict[str, tuple[str, ...]] = {
    "fixed": (),
    "skip_raise_after_loss": (),
    "guardrails": ("upper", "lower", "cut", "raise"),
    "pct_of_balance": (),
    "floor_ceiling": ("max_real_cut", "max_real_raise"),
}
_WHERE = "withdrawal_rules.yaml"


@dataclass(frozen=True)
class RulesConfig:
    rules: dict[str, dict[str, float]]  # rule id -> parameters, in config order
    income_lines: list[float]  # fractions of the starting income
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


def _check_params(rule: str, p: dict[str, float]) -> None:
    """Spec "Configuration" ranges. Written as `not (in range)` so NaN is refused too."""
    if rule == "guardrails":
        if not p["upper"] > 1:
            raise ValueError(f"{_WHERE}: guardrails upper {p['upper']} must be above 1")
        if not p["lower"] < 1:
            raise ValueError(f"{_WHERE}: guardrails lower {p['lower']} must be below 1")
        for key in ("cut", "raise"):
            if not 0 < p[key] < 1:
                raise ValueError(
                    f"{_WHERE}: guardrails {key} {p[key]} must be strictly between 0 and 1"
                )
    if rule == "floor_ceiling":
        for key in ("max_real_cut", "max_real_raise"):
            if not p[key] >= 0:
                raise ValueError(f"{_WHERE}: floor_ceiling {key} {p[key]} must be 0 or more")


def _rules(raw: object) -> dict[str, dict[str, float]]:
    if not isinstance(raw, dict) or not raw:
        raise ValueError(f"{_WHERE}: `rules` must be a non-empty mapping")
    out: dict[str, dict[str, float]] = {}
    for rule, params in raw.items():
        if rule not in RULE_PARAMS:
            raise ValueError(f"{_WHERE}: unknown rule {rule!r}")
        if not isinstance(params, dict) or set(params) != set(RULE_PARAMS[rule]):
            raise ValueError(
                f"{_WHERE}: rule {rule} needs parameters {sorted(RULE_PARAMS[rule])}, "
                f"got {params!r}"
            )
        values = {str(k): _number(v, f"rule {rule} parameters") for k, v in params.items()}
        _check_params(rule, values)
        out[str(rule)] = values
    return out


def _number(value: object, what: str) -> float:
    """A real, finite YAML number: not a bool, a string or null."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{_WHERE}: {what} must be numbers, got {value!r}")
    if not math.isfinite(value):
        raise ValueError(f"{_WHERE}: {what} must be finite, got {value!r}")
    return float(value)


def _list(doc: dict, key: str) -> list:
    value = doc[key]
    if not isinstance(value, list) or not value:
        raise ValueError(f"{_WHERE}: `{key}` must be a non-empty list")
    return value


def _no_duplicates(key: str, values: list) -> None:
    dupes = sorted({str(v) for v in values if values.count(v) > 1})
    if dupes:
        raise ValueError(f"{_WHERE}: duplicate `{key}` entries {dupes}")


def _income_lines(doc: dict) -> list[float]:
    lines = [_number(x, "`income_lines` entries") for x in _list(doc, "income_lines")]
    _no_duplicates("income_lines", lines)
    bad = [x for x in lines if not 0 < x < 1]
    if bad:
        raise ValueError(f"{_WHERE}: income line(s) {bad} must be strictly between 0 and 1")
    return lines


def load_rules_config(
    path: str | Path, decision_sha256: str, longrun_sha256: str, portfolio_ids: Iterable[str]
) -> RulesConfig:
    """Read config/withdrawal_rules.yaml (spec "Configuration"). Raises
    ValueError if it cannot be loaded, has an unknown or a missing key, a
    version other than 1, a decision.yaml or longrun.yaml pin that does not
    match the given sha256, an unknown rule or a rule with a wrong parameter
    set, a parameter out of range (guardrails upper <= 1, lower >= 1, cut or
    raise outside (0, 1); floor_ceiling bands negative), an empty or
    duplicated list, an income line outside (0, 1), or a portfolio id not in
    `portfolio_ids` (decision.yaml's)."""
    doc, raw = _read(path)
    unknown = sorted(str(k) for k in doc.keys() - set(_KEYS))
    if unknown:
        raise ValueError(f"{_WHERE}: unknown key(s) {unknown}")
    missing = [k for k in _KEYS if k not in doc]
    if missing:
        raise ValueError(f"{_WHERE}: missing key(s) {missing}")
    if doc["version"] != 1:
        raise ValueError(f"{_WHERE}: unsupported version {doc['version']}")
    if doc["decision_sha256"] != decision_sha256:
        raise ValueError(f"decision.yaml changed: its sha256 does not match {_WHERE}'s pin")
    if doc["longrun_sha256"] != longrun_sha256:
        raise ValueError(f"longrun.yaml changed: its sha256 does not match {_WHERE}'s pin")
    known = set(portfolio_ids)
    portfolios = [str(p) for p in _list(doc, "portfolios")]
    _no_duplicates("portfolios", portfolios)
    strangers = [p for p in portfolios if p not in known]
    if strangers:
        raise ValueError(f"{_WHERE}: portfolio(s) {strangers} not in decision.yaml")
    return RulesConfig(
        rules=_rules(doc["rules"]),
        income_lines=_income_lines(doc),
        portfolios=portfolios,
        sha256=hashlib.sha256(raw).hexdigest(),
    )


# ---- January functions (spec "Rules"). Inputs are arrays across paths: last
# year's monthly amount as paid, the year's CPI factor, the value at the
# decision point before that month's withdrawal, the portfolio's own return
# over the prior 12 months (before withdrawals), and the rate. Output: the new
# monthly amount. The scalar case is a length-1 array.


class JanuaryRule(Protocol):
    def __call__(
        self,
        prev: np.ndarray,
        cpi: np.ndarray,
        value: np.ndarray,
        prior: np.ndarray,
        rate: np.ndarray,
        params: Mapping[str, float],
    ) -> np.ndarray: ...


def fixed(
    prev: np.ndarray,
    cpi: np.ndarray,
    value: np.ndarray,
    prior: np.ndarray,
    rate: np.ndarray,
    params: Mapping[str, float],
) -> np.ndarray:
    """`prev x cpi`, the existing `monthly_withdrawals` / `run_paths` step."""
    return np.asarray(prev * cpi)


def skip_raise_after_loss(
    prev: np.ndarray,
    cpi: np.ndarray,
    value: np.ndarray,
    prior: np.ndarray,
    rate: np.ndarray,
    params: Mapping[str, float],
) -> np.ndarray:
    """As `fixed`, but `prev` (no CPI raise) after a negative prior-year return."""
    return np.asarray(np.where(prior < 0, prev, fixed(prev, cpi, value, prior, rate, params)))


def guardrails(
    prev: np.ndarray,
    cpi: np.ndarray,
    value: np.ndarray,
    prior: np.ndarray,
    rate: np.ndarray,
    params: Mapping[str, float],
) -> np.ndarray:
    """Guyton-Klinger capital preservation and prosperity, without the 15-year
    exception: take the fixed amount; q = 12 x amount / value; above
    upper x rate cut it by `cut`, below lower x rate raise it by `raise`.
    The path runner never calls a rule on a depleted path; a value of 0 with a
    positive amount is q = inf, which cuts. NaN inputs propagate (neither
    comparison holds, so the amount is kept)."""
    amount = fixed(prev, cpi, value, prior, rate, params)
    q = np.divide(
        12 * amount, value, out=np.full_like(amount, np.inf, dtype=float), where=value != 0
    )
    return np.asarray(
        np.where(
            q > params["upper"] * rate,
            amount * (1 - params["cut"]),
            np.where(q < params["lower"] * rate, amount * (1 + params["raise"]), amount),
        )
    )


def pct_of_balance(
    prev: np.ndarray,
    cpi: np.ndarray,
    value: np.ndarray,
    prior: np.ndarray,
    rate: np.ndarray,
    params: Mapping[str, float],
) -> np.ndarray:
    """12 x amount = rate x value."""
    return np.asarray(rate * value / 12)


def floor_ceiling(
    prev: np.ndarray,
    cpi: np.ndarray,
    value: np.ndarray,
    prior: np.ndarray,
    rate: np.ndarray,
    params: Mapping[str, float],
) -> np.ndarray:
    """rate x value / 12, clamped to [prev x cpi x (1 - max_real_cut),
    prev x cpi x (1 + max_real_raise)] (Vanguard's published real bands)."""
    base = fixed(prev, cpi, value, prior, rate, params)
    low = base * (1 - params["max_real_cut"])
    high = base * (1 + params["max_real_raise"])
    return np.asarray(np.minimum(np.maximum(rate * value / 12, low), high))


RULES: dict[str, JanuaryRule] = {
    "fixed": fixed,
    "skip_raise_after_loss": skip_raise_after_loss,
    "guardrails": guardrails,
    "pct_of_balance": pct_of_balance,
    "floor_ceiling": floor_ceiling,
}


# ---- runner (spec "Computation")


@dataclass(frozen=True)
class RuleRun:
    """The result of `run_rule` for every path."""

    values: np.ndarray  # (n_paths, n_steps): value after each step, start = 1.0
    paid: np.ndarray  # (n_paths, n_months): amount received in each month
    depleted: np.ndarray  # (n_paths,) int64: month 1..n_months the path emptied; 0 = never


def month_starts(index: pd.DatetimeIndex) -> np.ndarray:
    """True on the first trading day of each calendar month (as `withdrawal_path`)."""
    if not index.is_monotonic_increasing:
        raise ValueError("index must be sorted ascending")
    months = index.to_period("M")
    flags = np.ones(len(index), dtype=bool)
    flags[1:] = np.asarray(months[1:] != months[:-1])
    return flags


def _check_inputs(r: np.ndarray, starts: np.ndarray) -> None:
    if r.ndim != 2:
        raise ValueError(f"returns must be (paths, steps), got shape {r.shape}")
    if r.shape[1] == 0:
        raise ValueError("returns need at least one step")
    if starts.shape != (r.shape[1],):
        raise ValueError(
            f"month_start must be one flag per step: got shape {starts.shape} "
            f"for returns of shape {r.shape}"
        )
    if not starts[0]:
        raise ValueError("month_start must be set on the first step")
    if np.isnan(r).any():
        raise ValueError("NaN return (a NaN is never turned into cash)")


def _per_path(value: object, n_paths: int, name: str) -> np.ndarray:
    """A finite scalar or (n_paths,) input as a read-only (n_paths,) view."""
    a = np.asarray(value, dtype=float)
    if a.ndim > 1 or (a.ndim == 1 and a.shape[0] != n_paths):
        raise ValueError(f"{name} must be a scalar or (n_paths,), got shape {a.shape}")
    if not np.isfinite(a).all():
        raise ValueError(f"{name} must be finite")
    return np.broadcast_to(a, (n_paths,))


def run_rule(
    rule: str,
    params: Mapping[str, float],
    returns: np.ndarray,
    month_start: np.ndarray,
    cpi_at: Mapping[int, np.ndarray | float],
    rate: np.ndarray | float,
) -> RuleRun:
    """One rule over every path; both views use it. A step is a trading day
    (historical) or a calendar month (long run); `month_start` flags the
    first step of each month, step 0 included. At the first step of month m
    (0-based): if m is a key of `cpi_at` (a decision; its value is that
    year's CPI factor), the rule sets the monthly amount from the amount paid
    so far, the CPI factor, the value before the withdrawal and the
    portfolio's own compounded return since the last decision (or the start).
    The rule is called on the paths still alive only. Then the month's amount
    is withdrawn, and each step's return applies after (spec:
    withdrawal-edge-cases.md). At or below DEPLETED after the withdrawal, the
    path is depleted that month with no return applied, and the month's
    income is the remaining balance. At or below DEPLETED after the step's
    return, it is depleted that month, and the income was the full amount. A
    depleted path stays at 0 and is paid nothing."""
    if rule not in RULES:
        raise ValueError(f"unknown rule {rule!r}")
    r = np.asarray(returns, dtype=float)
    starts = np.asarray(month_start, dtype=bool)
    _check_inputs(r, starts)
    n_paths, n_steps = r.shape
    rates = _per_path(rate, n_paths, "rate")
    cpis = {m: _per_path(c, n_paths, f"cpi (month {m})") for m, c in cpi_at.items()}
    w = rates / 12
    value = np.ones(n_paths)
    growth = np.ones(n_paths)
    depleted = np.zeros(n_paths, dtype=np.int64)
    values = np.empty((n_paths, n_steps))
    paid = np.zeros((n_paths, int(starts.sum())))
    month = -1
    for t in range(n_steps):
        alive = depleted == 0
        after = value
        if starts[t]:
            month += 1
            if month in cpis and alive.any():
                cpi = cpis[month]
                w[alive] = RULES[rule](
                    w[alive], cpi[alive], value[alive], growth[alive] - 1.0, rates[alive], params
                )
                growth = np.ones(n_paths)
            after = value - w
            paid[:, month] = np.where(alive, np.where(after <= DEPLETED, value, w), 0.0)
        value = np.where(alive & (after > DEPLETED), after * (1.0 + r[:, t]), 0.0)
        emptied = alive & (value <= DEPLETED)
        value[emptied] = 0.0
        depleted[emptied] = month + 1
        growth = growth * (1.0 + r[:, t])
        values[:, t] = value
    return RuleRun(values, paid, depleted)


# ---- views: decision points and CPI factors


def historical_cpi(months: pd.PeriodIndex, cpi: pd.Series) -> dict[int, float]:
    """Historical decisions: every January after the path's first month, keyed
    by 0-based month position. The factor is the CPI usable on 1 January over
    the CPI usable on the previous 1 January (`usable_cpi`), written
    `1 + (ratio - 1)` exactly as `monthly_withdrawals` applies it, so the
    fixed rule matches it bit for bit."""
    out: dict[int, float] = {}
    for m, period in enumerate(months):
        if m and period.month == 1:
            now = pd.Timestamp(year=period.year, month=1, day=1)
            before = pd.Timestamp(year=period.year - 1, month=1, day=1)
            out[m] = 1 + (usable_cpi(cpi, now) / usable_cpi(cpi, before) - 1)
    return out


def historical_run(
    returns: pd.Series,
    cpi: pd.Series,
    rates: list[float],
    rule: str,
    params: Mapping[str, float],
) -> tuple[RuleRun, pd.PeriodIndex]:
    """One start year's daily path at every rate (one row per rate, same
    returns), and the path's calendar months. `cpi` must already be cut."""
    idx = pd.DatetimeIndex(returns.index)
    months = idx.to_period("M").unique()
    paths = np.tile(returns.to_numpy(dtype=float), (len(rates), 1))
    run = run_rule(
        rule,
        params,
        paths,
        month_starts(idx),
        historical_cpi(months, cpi),
        np.asarray(rates, dtype=float),
    )
    return run, months


def month_label(depleted: int, months: pd.PeriodIndex) -> str | None:
    """ "YYYY-MM" of a 1-based depletion month (as `withdrawal_path`), None for 0."""
    return None if depleted == 0 else str(months[depleted - 1])


def longrun_cpi(pi: np.ndarray) -> tuple[dict[int, np.ndarray], np.ndarray]:
    """From the paths' monthly inflation (n_paths, n_months): the CPI factor at
    each 12-month decision (0-based months 12, 24, ...; spec months 13,
    25, ...), the product of the previous 12 months' inflation; and the
    cumulative price level after each month. Both are multiplied in the order
    `run_paths` uses, so the fixed rule and the real values match it exactly."""
    n_paths, n_months = pi.shape
    level = np.ones(n_paths)
    year = np.ones(n_paths)
    levels = np.empty((n_paths, n_months))
    cpi_at: dict[int, np.ndarray] = {}
    for t in range(n_months):
        if t and t % 12 == 0:
            cpi_at[t] = year
            year = np.ones(n_paths)
        level = level * (1.0 + pi[:, t])
        year = year * (1.0 + pi[:, t])
        levels[:, t] = level
    return cpi_at, levels


# ---- measures (spec "Measures"). Income is a fraction of the starting income
# (rate x starting value; the starting value is 1.0): 1.0 = 100%.


def historical_measures(
    values: pd.Series,
    paid: np.ndarray,
    depleted: int,
    months: pd.PeriodIndex,
    cpi: pd.Series,
    rate: float,
    lines: list[float],
) -> tuple[dict[str, float | str | None], np.ndarray]:
    """One start year's path. Returns a dict and an array. The dict has
    `path_metrics`' depletion month ("YYYY-MM" or None), real ending value
    and lowest value, plus the lowest yearly real income and the total real
    income. Each calendar year's real income is the year's payments deflated
    by the CPI usable on 1 January of that year over the CPI usable on the
    start date, as a fraction of the starting income. Years are calendar
    years, so a start or end part-way through a year gives a partial first or
    last year (its income is just the payments made in it). The array is
    (years, lines) booleans: whether that year's income is below each line. A
    year in or after the depletion year is below every line. `cpi` must
    already be cut."""
    label = month_label(depleted, months)
    metrics = path_metrics(WithdrawalPath(values, label), cpi)
    start = usable_cpi(cpi, pd.Timestamp(values.index[0]))
    years = np.asarray(months.year)
    calendar = sorted({int(y) for y in years})
    income = np.array(
        [
            paid[years == y].sum()
            / (usable_cpi(cpi, pd.Timestamp(year=y, month=1, day=1)) / start)
            / rate
            for y in calendar
        ]
    )
    gone = np.array(calendar) >= (months[depleted - 1].year if depleted else calendar[-1] + 1)
    below = (income[:, None] < np.asarray(lines)[None, :]) | gone[:, None]
    return {
        "depleted": label,
        "end_real": metrics["end_real"],
        "lowest": metrics["lowest"],
        "income_low": float(income.min()),
        "income_total": float(income.sum()),
    }, below


def longrun_measures(
    run: RuleRun, levels: np.ndarray, rate: float, lines: list[float], horizon_years: int
) -> dict[str, float | dict[float, float]]:
    """Over all paths: share depleted by `horizon_years`; real ending value
    (deflated by the path's own level), lowest nominal value, lowest yearly
    and total real income, each as median and 5th percentile; and per income
    line the share of paths whose real income is below it in any year
    (depleted paths count as below). Each 12-month period's payments are
    deflated by the path's cumulative inflation at the start of that period;
    a depleted path counts 0 after depletion. `depleted` only counts
    depletion within `horizon_years`, while `ever_below` counts a depletion
    in any year of the path, with no horizon limit; the two differ only if
    the path is longer than the horizon. Raises ValueError if the months are
    not a whole number of years or `horizon_years` is longer than the path."""
    n_paths, n_months = run.paid.shape
    if n_months % 12:
        raise ValueError(f"months must be a multiple of 12, got {n_months}")
    if 12 * horizon_years > n_months:
        raise ValueError(
            f"horizon_years {horizon_years} is longer than the path's {n_months // 12} years"
        )
    yearly = run.paid.reshape(n_paths, -1, 12).sum(axis=2)
    start = np.concatenate([np.ones((n_paths, 1)), levels[:, 11::12][:, :-1]], axis=1)
    income = yearly / start / rate
    gone = run.depleted > 0
    end_real = run.values[:, -1] / levels[:, -1]
    lowest = run.values.min(axis=1)
    low, total = income.min(axis=1), income.sum(axis=1)
    return {
        "depleted": float(np.mean(gone & (run.depleted <= 12 * horizon_years))),
        "end_real_median": float(np.median(end_real)),
        "end_real_p5": float(np.quantile(end_real, 0.05)),
        "lowest_median": float(np.median(lowest)),
        "lowest_p5": float(np.quantile(lowest, 0.05)),
        "income_low_median": float(np.median(low)),
        "income_low_p5": float(np.quantile(low, 0.05)),
        "income_total_median": float(np.median(total)),
        "income_total_p5": float(np.quantile(total, 0.05)),
        "ever_below": {line: float(np.mean((income < line).any(axis=1) | gone)) for line in lines},
    }


# ---- orchestration


def _historical_row(
    pid: str,
    rule: str,
    rate: float,
    per_year: dict[int, tuple[dict, np.ndarray]],
    lines: list[float],
) -> dict:
    """The first start year's and the worst start year's (lowest real ending
    value; ties to the earlier year, as `decision.withdrawal_rows`) figures,
    and the share of years below each line pooled over every start year's
    calendar years."""
    first = min(per_year)
    worst = min(per_year, key=lambda y: (per_year[y][0]["end_real"], y))
    below = np.concatenate([b for _, b in per_year.values()])
    return {
        "portfolio": pid,
        "rule": rule,
        "rate": rate,
        "first_year": first,
        "first": per_year[first][0],
        "worst_year": worst,
        "worst": per_year[worst][0],
        "years_pooled": int(below.shape[0]),
        "below": {line: float(below[:, i].mean()) for i, line in enumerate(lines)},
    }


def _historical_rule(
    pid: str,
    rule: str,
    params: Mapping[str, float],
    returns: dict[int, pd.Series],
    cpi: pd.Series,
    rates: list[float],
    lines: list[float],
) -> list[dict]:
    """One portfolio and rule: a row per rate (in `rates` order) over every
    start year's daily path. `cpi` must already be cut."""
    per_rate: dict[float, dict[int, tuple[dict, np.ndarray]]] = {rate: {} for rate in rates}
    for year, rets in returns.items():
        run, months = historical_run(rets, cpi, rates, rule, params)
        for i, rate in enumerate(rates):
            values = pd.Series(run.values[i], index=rets.index)
            per_rate[rate][year] = historical_measures(
                values, run.paid[i], int(run.depleted[i]), months, cpi, rate, lines
            )
    return [_historical_row(pid, rule, rate, per_rate[rate], lines) for rate in rates]


def historical_rows(
    rcfg: RulesConfig,
    dcfg: DecisionConfig,
    data: dict[str, pd.DataFrame],
    cpi: pd.Series,
    criteria: dict,
) -> list[dict]:
    """Per portfolio, rule and rate (in that order): daily paths from the
    first trading day of each start year to the data end, returns from
    `decision.portfolio_returns` (unchanged, criteria cost_bps). Price and CPI
    frames are cut at the data end first."""
    end = data_end(criteria)
    cut = {k: v.loc[:end] for k, v in data.items()}
    known_cpi = cpi.loc[:end]
    cost_bps = float(criteria["costs"]["bps_per_unit_turnover"])
    starts = start_dates(pd.DatetimeIndex(cut["close"].index), dcfg.start_years, end)
    by_id = {p.id: p for p in dcfg.portfolios}
    rows: list[dict] = []
    for pid in rcfg.portfolios:
        returns = {
            y: portfolio_returns(by_id[pid], cut, day, cost_bps) for y, day in starts.items()
        }
        for rule, params in rcfg.rules.items():
            rows += _historical_rule(
                pid, rule, params, returns, known_cpi, dcfg.rates, rcfg.income_lines
            )
    return rows


def longrun_indices(lcfg: LongrunConfig, n_months: int) -> np.ndarray:
    """The long run's month positions: the same seed, `block_starts` and
    `month_indices` as `run_longrun`, so the paths are the same paths."""
    n_blocks = lcfg.horizon_years * 12 // lcfg.block_months
    idx = month_indices(
        block_starts(lcfg.seed, lcfg.n_paths, n_blocks, n_months), lcfg.block_months, n_months
    )
    if idx.shape[1] != lcfg.horizon_years * 12:
        raise ValueError(
            f"paths are {idx.shape[1]} months long, expected {lcfg.horizon_years * 12}"
        )
    return idx


def longrun_rows(
    rcfg: RulesConfig,
    dcfg: DecisionConfig,
    lcfg: LongrunConfig,
    data: dict[str, pd.DataFrame],
    cpi: pd.Series,
    criteria: dict,
) -> tuple[list[dict], dict]:
    """Per rate, portfolio and rule (in that order) over the long run's paths:
    calendar-month returns (`monthly_returns` of `portfolio_returns` from the
    first research trading day) and `monthly_inflation`, the same draws for
    every portfolio and rule. Also the month span for the header. Price and
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
    for pid in rcfg.portfolios:
        series = monthly_returns(portfolio_returns(by_id[pid], cut, first, cost_bps))
        if not series.index.equals(months):
            raise ValueError(
                f"portfolio {pid}: months must run {months[0]}..{months[-1]} ({len(months)} months)"
            )
        monthly[pid] = series.to_numpy()
    idx = longrun_indices(lcfg, len(months))
    cpi_at, levels = longrun_cpi(monthly_inflation(known_cpi, months).to_numpy()[idx])
    every = np.ones(idx.shape[1], dtype=bool)
    rows = [
        {
            "portfolio": pid,
            "rule": rule,
            "rate": rate,
            **longrun_measures(
                run_rule(rule, params, monthly[pid][idx], every, cpi_at, rate),
                levels,
                rate,
                rcfg.income_lines,
                lcfg.horizon_years,
            ),
        }
        for rate in dcfg.rates
        for pid in rcfg.portfolios
        for rule, params in rcfg.rules.items()
    ]
    span = {"first_month": str(months[0]), "last_month": str(months[-1]), "n_months": len(months)}
    return rows, span


def run_withdrawal_rules(
    rcfg: RulesConfig,
    dcfg: DecisionConfig,
    lcfg: LongrunConfig,
    data: dict[str, pd.DataFrame],
    cpi: pd.Series,
    criteria: dict,
) -> dict:
    """The whole report as plain data (rendered by
    `qrl.withdrawal_rules_report`). Rates and start years come from
    decision.yaml, the paths from longrun.yaml, the cost from criteria.yaml.
    Raises ValueError on any refusal."""
    check_withdrawal_rates(lcfg, dcfg)
    labels = {p.id: p.label for p in dcfg.portfolios}
    strangers = [pid for pid in rcfg.portfolios if pid not in labels]
    if strangers:
        raise ValueError(f"withdrawal_rules portfolio(s) {strangers} not in decision.yaml")
    longrun, span = longrun_rows(rcfg, dcfg, lcfg, data, cpi, criteria)
    return {
        "data_end": str(data_end(criteria).date()),
        "rules_sha256": rcfg.sha256,
        "decision_sha256": dcfg.sha256,
        "longrun_sha256": lcfg.sha256,
        "cost_bps": float(criteria["costs"]["bps_per_unit_turnover"]),
        "seed": lcfg.seed,
        "n_paths": lcfg.n_paths,
        "block_months": lcfg.block_months,
        "horizon_years": lcfg.horizon_years,
        **span,
        "rates": dcfg.rates,
        "start_years": dcfg.start_years,
        "rules": rcfg.rules,
        "income_lines": rcfg.income_lines,
        "portfolios": [{"id": pid, "label": labels[pid]} for pid in rcfg.portfolios],
        "historical": historical_rows(rcfg, dcfg, data, cpi, criteria),
        "longrun": longrun,
    }
