"""History-grounded scenarios (spec: docs/methodology/history-scenarios.md):
pure functions, no I/O. Episodes are found on the S&P 500 price index alone,
before any portfolio result. A decision aid: it selects nothing and recommends
nothing. Only data up to the research end (2018-12-31) is ever passed in."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from .decision import data_end, portfolio_returns, portfolio_tickers, portfolio_weights
from .decision_config import DecisionConfig, Portfolio, held_tickers
from .decision_withdraw import (
    WithdrawalPath,
    _months,
    monthly_withdrawals,
    path_metrics,
    withdrawal_path,
)
from .history_config import HistoryConfig
from .history_data import (
    CheckResult,
    Panel,
    RawData,
    assemble_panel,
    check_first_date,
    raw_hashes,
    run_checks,
    validate_raw,
)

EPS = 1e-12  # float slack so a fall of exactly 15% counts


@dataclass(frozen=True)
class Episode:
    """A peak, its lowest close before recovery, and the first close at or
    above the peak (None: not recovered by the data end)."""

    peak: pd.Timestamp
    trough: pd.Timestamp
    recovery: pd.Timestamp | None
    depth: float  # peak-to-trough, positive
    months: int | None  # calendar months peak to recovery
    window_end: pd.Timestamp  # earlier of peak + horizon years and the data end


def _episode(
    peak: pd.Timestamp,
    trough: pd.Timestamp,
    depth: float,
    recovery: pd.Timestamp | None,
    horizon_years: int,
    end: pd.Timestamp,
) -> Episode:
    months = None if recovery is None else _months(peak, recovery)
    window_end = min(pd.Timestamp(peak + pd.DateOffset(years=horizon_years)), end)
    return Episode(peak, trough, recovery, depth, months, window_end)


def find_episodes(
    close: pd.Series,
    threshold: float,
    start: pd.Timestamp,
    horizon_years: int,
    data_end: pd.Timestamp,
) -> list[Episode]:
    """Episodes of the index `close` (full history, cut at `data_end`): a peak
    is a close higher than every earlier close; it counts if a later close is
    `threshold` or more below it before the index closes at or above it again
    (exactly `threshold` counts). The trough is the lowest close before
    recovery, the recovery the first close at or above the peak. A tie with the
    peak ends the episode but is not a new peak: a later fall from it is an
    episode only after a strictly higher close. Raises ValueError on an
    unsorted or duplicated index. Only peaks on or after
    `start` are returned, in date order."""
    if not close.index.is_monotonic_increasing or close.index.has_duplicates:
        raise ValueError("close index must be strictly increasing (sorted, no duplicates)")
    series = close.dropna().loc[:data_end]
    values = series.to_numpy(dtype=float)
    dates = pd.DatetimeIndex(series.index)
    found: list[Episode] = []
    if len(values) == 0:
        return found
    peak_i = trough_i = 0
    flagged = False
    armed = True  # False after a tie with the high, until a strictly higher close
    for i in range(1, len(values)):
        if values[i] >= values[peak_i]:
            if flagged:
                depth = 1.0 - values[trough_i] / values[peak_i]
                found.append(
                    _episode(
                        dates[peak_i], dates[trough_i], depth, dates[i], horizon_years, data_end
                    )
                )
            if values[i] > values[peak_i]:
                peak_i, armed = i, True
            else:
                armed = False
            trough_i, flagged = peak_i, False
            continue
        if values[i] < values[trough_i]:
            trough_i = i
        if armed and 1.0 - values[trough_i] / values[peak_i] >= threshold - EPS:
            flagged = True
    if flagged:
        depth = 1.0 - values[trough_i] / values[peak_i]
        found.append(_episode(dates[peak_i], dates[trough_i], depth, None, horizon_years, data_end))
    return [ep for ep in found if ep.peak >= start]


NO_SIGNAL = "no signal yet"
NA_DATA = "n/a (data ends)"
NOT_RECOVERED = "not recovered by 2018"


@dataclass(frozen=True)
class Cell:
    """One portfolio in one episode for one measure. `value` None: no number
    (see `note`); `inf`: not recovered. `marks`: dagger labels."""

    value: float | None
    note: str = ""
    marks: str = ""


@dataclass(frozen=True)
class Context:
    calendar: pd.DatetimeIndex  # the panel's trading days
    cpi: pd.Series  # availability-dated, cut at the data end
    rates: tuple[float, ...]
    income_years: tuple[int, ...]
    data_end: pd.Timestamp


def income_key(rate: float, years: int) -> str:
    return f"income:{rate:g}:{years}"


def first_day_after(calendar: pd.DatetimeIndex, peak: pd.Timestamp) -> pd.Timestamp | None:
    """The first trading day after `peak` (None if there is none)."""
    pos = int(calendar.searchsorted(peak, side="right"))
    return None if pos >= len(calendar) else pd.Timestamp(calendar[pos])


def _values_from_peak(returns: pd.Series, ctx: Context, peak: pd.Timestamp) -> pd.Series | None:
    """Value 1 at the peak's close, then the daily returns from the next trading
    day; None if the portfolio has no return on that day yet."""
    first = first_day_after(ctx.calendar, peak)
    if first is None or returns.empty or returns.index[0] > first:
        return None
    return (1.0 + returns.loc[first:]).cumprod()


def _recovery_cell(peak: pd.Timestamp, values: pd.Series, window: pd.Series) -> Cell:
    if float(window.min()) >= 1.0 - EPS:
        return Cell(0.0)
    after = values.loc[window.idxmin() :]
    back = after[after >= 1.0 - EPS]
    if back.empty:
        return Cell(math.inf, NOT_RECOVERED)
    return Cell(float(_months(peak, pd.Timestamp(back.index[0]))))


def _balance_cell(path: WithdrawalPath, day: pd.Timestamp, cpi: pd.Series) -> Cell:
    sub = path.values.loc[:day]
    if float(sub.iloc[-1]) <= 0.0 and path.depleted:
        return Cell(0.0, f"depleted {path.depleted}")
    end_real: float = path_metrics(WithdrawalPath(sub, None), cpi)["end_real"]
    return Cell(end_real)


def _income_cells(
    peak: pd.Timestamp, returns: pd.Series, values: pd.Series, rate: float, ctx: Context
) -> dict[str, Cell]:
    days = pd.DatetimeIndex(values.index)
    due = {y: pd.Timestamp(peak + pd.DateOffset(months=12 * y)) for y in ctx.income_years}
    reachable = [y for y in ctx.income_years if due[y] <= days[-1]]
    out = {income_key(rate, y): Cell(None, NA_DATA) for y in ctx.income_years if y not in reachable}
    if not reachable:
        return out
    stop = days[days <= max(due[y] for y in reachable)][-1]
    first = days[0]
    monthly = monthly_withdrawals(
        rate, first.year, min(first.year + 11, ctx.data_end.year), ctx.cpi
    )
    path = withdrawal_path(returns.loc[first:stop], monthly)
    for y in reachable:
        out[income_key(rate, y)] = _balance_cell(path, days[days <= due[y]][-1], ctx.cpi)
    return out


def episode_measures(episode: Episode, returns: pd.Series, ctx: Context) -> dict[str, Cell]:
    """Cells for one portfolio in one episode, keyed "loss", "recover" and
    `income_key(rate, years)`: worst loss in the measure window, months to
    recover, and the real balance of a CPI-indexed withdrawal from the peak.
    `returns` is the portfolio's daily return series over the whole panel."""
    values = _values_from_peak(returns, ctx, episode.peak)
    keys = ["loss", "recover", *(income_key(r, y) for r in ctx.rates for y in ctx.income_years)]
    if values is None:
        return {k: Cell(None, NO_SIGNAL) for k in keys}
    window = values.loc[: episode.window_end]
    if window.empty:  # the data ends before the portfolio's first return after the peak
        return {k: Cell(None, NA_DATA) for k in keys}
    cells = {
        "loss": Cell(1.0 - min(1.0, float(window.min()))),
        "recover": _recovery_cell(episode.peak, values, window),
    }
    for rate in ctx.rates:
        cells.update(_income_cells(episode.peak, returns, values, rate, ctx))
    return cells


DAGGER = "†"
DOUBLE_DAGGER = "‡"
GOLD_FUND = "GLD"


def cell_marks(
    first_day: pd.Timestamp,
    held: Iterable[str],
    own_start: Mapping[str, pd.Timestamp],
    gold_futures_start: pd.Timestamp,
) -> str:
    """Labels for a cell whose window starts on `first_day`: DAGGER if any fund
    the portfolio can hold (both branches of a switching rule, every part of a
    blend) uses stand-in data on any day of the window, i.e. the window starts
    before that fund's first own price; DOUBLE_DAGGER if it can hold GLD and the
    window includes any day before the first GC=F close (interpolated gold)."""
    funds = set(held)
    marks = DAGGER if any(first_day < own_start[t] for t in funds) else ""
    if GOLD_FUND in funds and first_day < gold_futures_start:
        marks += DOUBLE_DAGGER
    return marks


def apply_marks(cells: dict[str, Cell], marks: str) -> dict[str, Cell]:
    """`cells` with `marks` on every cell that carries a number."""
    return {
        key: replace(cell, marks=marks) if cell.value is not None else cell
        for key, cell in cells.items()
    }


@dataclass(frozen=True)
class Summary:
    median: float | None
    worst: float | None
    worst_label: str  # label of the episode with the worst usable cell
    count: int  # usable cells
    total: int  # all cells


def summarize(cells: list[tuple[str, Cell]], higher_is_worse: bool) -> Summary:
    """Median and worst over the cells that carry a number ("no signal yet" and
    "n/a" cells are skipped); a not-recovered cell (value inf) ranks as the
    largest. With an even count that includes inf the median averages the two
    middle values, so [10, inf] gives inf. `cells` are (episode label, cell)
    pairs. Describes only."""
    usable = [(label, cell.value) for label, cell in cells if cell.value is not None]
    if not usable:
        return Summary(None, None, "", 0, len(cells))
    pick = max if higher_is_worse else min
    label, worst = pick(usable, key=lambda item: item[1])
    median = float(np.median([value for _, value in usable]))
    return Summary(median, worst, label, len(usable), len(cells))


@dataclass(frozen=True)
class HistoryReport:
    """Everything the renderer needs, as plain data."""

    data_end: pd.Timestamp
    threshold: float
    episode_start: pd.Timestamp
    horizon_years: int
    rates: tuple[float, ...]
    income_years: tuple[int, ...]
    candidate_count: int  # portfolios of the core comparison (A-G)
    config_hashes: dict[str, str]  # "config/history.yaml" -> sha256
    raw_hashes: dict[str, str]  # series name -> sha256
    portfolios: list[tuple[str, str]]  # (id, label), in config order
    starts: dict[str, pd.Timestamp]  # first return day of each portfolio
    episodes: list[Episode]
    checks: list[CheckResult]
    cells: dict[str, list[dict[str, Cell]]]  # portfolio id -> per-episode cells


def portfolio_start(p: Portfolio, close: pd.DataFrame) -> pd.Timestamp:
    """The first trading day `decision.portfolio_returns` can start from: the
    day after the first day on which every weight is defined (it buys at the
    start-day open from the prior day's target row). After the 200-day warm-up
    for the switching rules; the panel's second day for a static portfolio."""
    defined = portfolio_weights(p, close).notna().all(axis=1).to_numpy()
    if not defined.any():
        raise ValueError(f"portfolio {p.id}: weights are never defined on the panel")
    pos = int(defined.argmax()) + 1
    if pos >= len(close):
        raise ValueError(f"portfolio {p.id}: no trading day after its first defined weights")
    return pd.Timestamp(close.index[pos])


def _portfolio_cells(
    p: Portfolio, panel: Panel, ctx: Context, episodes: list[Episode], cost_bps: float
) -> tuple[pd.Timestamp, list[dict[str, Cell]]]:
    """The portfolio's first return day and its marked cells, one dict per episode."""
    missing = sorted(set(portfolio_tickers(p)) - set(panel.close.columns))
    if missing:
        raise ValueError(f"portfolio {p.id}: no stand-in panel for {missing}")
    start = portfolio_start(p, panel.close)
    data = {"open": panel.open, "close": panel.close}
    returns = portfolio_returns(p, data, start, cost_bps)
    held = held_tickers([p])
    per_episode = []
    for ep in episodes:
        measured = episode_measures(ep, returns, ctx)
        first = first_day_after(ctx.calendar, ep.peak)
        marks = (
            cell_marks(first, held, panel.own_start, panel.gold_futures_start)
            if first is not None
            else ""
        )
        per_episode.append(apply_marks(measured, marks))
    return start, per_episode


def run_history(
    hcfg: HistoryConfig, dcfg: DecisionConfig, raw: RawData, cpi: pd.Series, criteria: dict
) -> HistoryReport:
    """The whole report as plain data. Raises ValueError on any refusal: a
    series that starts too late, has data past the data end or has a gap, a
    stand-in check below the bar, or no episode. Episodes are found from the
    index alone, before any portfolio result."""
    end = data_end(criteria)
    validate_raw(raw, hcfg, end)
    check_first_date("CPIAUCNS", cpi, hcfg.cpi_max_first_date)
    panel = assemble_panel(raw, hcfg, end)
    checks = run_checks(panel.links, end, hcfg.min_correlation)
    episodes = find_episodes(
        raw.close[hcfg.index_ticker], hcfg.threshold, hcfg.episode_start, hcfg.horizon_years, end
    )
    if not episodes:
        raise ValueError("no episode found: no fall of the configured size since the start date")
    by_id = {p.id: p for p in dcfg.portfolios}
    unknown = [pid for pid in hcfg.portfolios if pid not in by_id]
    if unknown:
        raise ValueError(f"portfolios {unknown} are not in the decision config")
    cost_bps = float(criteria["costs"]["bps_per_unit_turnover"])
    ctx = Context(
        pd.DatetimeIndex(panel.close.index), cpi.loc[:end], hcfg.rates, hcfg.income_years, end
    )
    cells: dict[str, list[dict[str, Cell]]] = {}
    starts: dict[str, pd.Timestamp] = {}
    for pid in hcfg.portfolios:
        starts[pid], cells[pid] = _portfolio_cells(by_id[pid], panel, ctx, episodes, cost_bps)
    return HistoryReport(
        data_end=end,
        threshold=hcfg.threshold,
        episode_start=hcfg.episode_start,
        horizon_years=hcfg.horizon_years,
        rates=hcfg.rates,
        income_years=hcfg.income_years,
        candidate_count=dcfg.candidate_count,
        config_hashes={
            "config/history.yaml": hcfg.sha256,
            "config/decision.yaml": dcfg.sha256,
            "config/core_candidates.yaml": dcfg.candidates_sha256,
        },
        raw_hashes=raw_hashes(raw),
        portfolios=[(pid, by_id[pid].label) for pid in hcfg.portfolios],
        starts=starts,
        episodes=episodes,
        checks=checks,
        cells=cells,
    )
