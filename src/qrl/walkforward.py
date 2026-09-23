"""Milestone 2.6: walk-forward sleeve selection (PLAN.md section 2.6, and
section 3's "The holdout was contaminated" / the over-eviction point).

Three pieces:

- `period_starts`: the actual trading dates a reselection boundary falls on
  within a date index (quarterly by default).
- `select_sleeve`: rank candidates on a trailing window that ends STRICTLY
  BEFORE the boundary date, apply the over-eviction guard, and take the top
  `n_strategies`. Never reads a return dated on or after the boundary.
- `walk_forward`: repeat `select_sleeve` at every boundary in `[start, end]`,
  and stitch every period's selected weights into ONE combined
  target-weights matrix run through `qrl.engine.run_backtest` a single
  time, so reselection turnover is costed by the engine exactly like any
  other trade -- never assembled from separately-costed pieces.
- `tune_meta`: grid-search meta-settings (`qrl.strategies.iter_grid`) over a
  caller-given `[start, end]`, refusing outright if `end` reaches the
  holdout period, and logging EVERY combination tried to the ledger's
  `meta_tests` table (`Ledger.record_meta_test`).

Nothing here ever sets the `unseal_holdout` flag: `walk_forward` and
`tune_meta` operate on whatever `SearchData` and date bounds the caller
supplies, and every caller in this codebase bounds them to research and
validation dates. The one, one-shot exception -- running this same
`walk_forward` machinery on the actual holdout period for the final chosen
process -- goes through `qrl.holdout.unseal` alone (PLAN.md 2.6).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pandas as pd

from .engine import run_backtest
from .metrics import TRADING_DAYS, compute_metrics, drawdown
from .periods import period_bounds
from .search import SearchData, evaluate_candidate
from .strategies import REGISTRY, SLEEVE_REGISTRY, StrategySpec, iter_grid
from .tradability import exit_before_delisting

if TYPE_CHECKING:
    from .ledger import Ledger

_ALL_SPECS: dict[str, StrategySpec] = {**REGISTRY, **SLEEVE_REGISTRY}


def _spec_for(family: str) -> StrategySpec:
    try:
        return _ALL_SPECS[family]
    except KeyError:
        raise KeyError(f"Unknown strategy family: {family!r}") from None


# ---------------------------------------------------------------------------
# Reselection boundaries.
# ---------------------------------------------------------------------------


def period_starts(index: pd.Index, frequency: str = "QS") -> list[pd.Timestamp]:
    """Reselection boundary dates within `index`: the first entry of `index`
    itself, plus the first `index` date on or after every calendar boundary
    of `frequency` (a pandas date-offset alias -- `"QS"` quarter start,
    `"MS"` month start, ...) strictly after the previous boundary found.

    An empty `index` returns an empty list. Consecutive calendar boundaries
    that land in the same gap (e.g. a `frequency` finer than the data, or a
    boundary before the first trading day) collapse to the same trading
    date and are not duplicated.
    """
    idx = pd.DatetimeIndex(index)
    if len(idx) == 0:
        return []
    idx = idx.sort_values()
    starts = [idx[0]]
    for boundary in pd.date_range(idx[0], idx[-1], freq=frequency):
        if boundary <= starts[-1]:
            continue
        pos = int(idx.searchsorted(boundary, side="left"))
        if pos < len(idx) and idx[pos] > starts[-1]:
            starts.append(idx[pos])
    return starts


# ---------------------------------------------------------------------------
# Candidate identity, shared between dict-shaped candidate results (the
# `select_sleeve` API) and `CandidateTrack` objects (the `walk_forward`
# bookkeeping below).
# ---------------------------------------------------------------------------


def _hashable_params(params: dict) -> tuple:
    return tuple(sorted((k, tuple(v) if isinstance(v, list) else v) for k, v in params.items()))


def _identity(obj: dict | CandidateTrack) -> tuple:
    """A stable identity for a candidate: its ledger `test_id` if it has
    one, else `(family, sorted params)` -- used to match an incumbent
    across periods for the eviction guard, and to look a selected member's
    own price weights back up in `walk_forward`."""
    if isinstance(obj, dict):
        test_id, family, params = obj.get("test_id"), obj["family"], obj["params"]
    else:
        test_id, family, params = obj.test_id, obj.family, obj.params
    if test_id is not None:
        return ("test_id", test_id)
    return ("family_params", family, _hashable_params(params))


# ---------------------------------------------------------------------------
# select_sleeve: trailing-window ranking + the over-eviction guard.
# ---------------------------------------------------------------------------


def _trailing_window(returns: pd.Series, as_of: pd.Timestamp, lookback_days: int) -> pd.Series:
    """`returns` strictly before `as_of`, limited to the last `lookback_days`
    observations. Never includes a return dated on or after `as_of`."""
    past = returns[returns.index < as_of]
    return past.tail(lookback_days)


def _trailing_sharpe(trailing: pd.Series) -> float:
    if len(trailing) < 2:
        return float("-inf")
    std = trailing.std()
    if not std or pd.isna(std):
        return 0.0
    return float(trailing.mean() / std * math.sqrt(TRADING_DAYS))


def _trailing_max_drawdown(trailing: pd.Series) -> float:
    if trailing.empty:
        return 0.0
    return float(-drawdown(trailing).min())


def _is_evicted(entry: dict, trailing: pd.Series, meta: dict) -> bool:
    """The over-eviction guard (PLAN.md 2.6, section 3): an incumbent is
    force-dropped only for a stretch that breaches a threshold CALIBRATED
    FROM ITS OWN prior backtest -- never a fixed number shared by every
    strategy, and never an ordinary losing streak within its own historical
    range.

    `entry["backtest_metrics"]` is a FIXED, pre-computed baseline from this
    same strategy's research-period backtest (see `prepare_candidate_track`)
    -- never re-estimated from data at or after the current boundary, so
    calibration can never leak future information.

    Two independent triggers, either sufficient:

    1. Drawdown: the trailing window's max drawdown exceeds
       `meta["eviction_dd_multiple"]` times the strategy's own backtested
       max drawdown.
    2. Underperformance: the trailing window's cumulative simple return is
       worse than `-meta["eviction_underperf_multiple"]` standard
       deviations of the strategy's own backtested daily volatility, scaled
       to the window's length by `sqrt(window_len)` (the same
       time-scaling `qrl.metrics` uses to annualize). A calibrated
       multiple of several sigma only trips on a stretch far outside what
       this strategy's own history would call normal -- not a garden
       variety losing streak.
    """
    backtest = entry.get("backtest_metrics") or {}
    own_dd = backtest.get("max_drawdown")
    if (
        own_dd is not None
        and own_dd > 0
        and _trailing_max_drawdown(trailing) > (meta["eviction_dd_multiple"] * own_dd)
    ):
        return True

    own_vol = backtest.get("volatility")
    window_len = len(trailing)
    if own_vol is not None and own_vol > 0 and window_len > 0:
        own_daily_std = own_vol / math.sqrt(TRADING_DAYS)
        floor = -meta["eviction_underperf_multiple"] * own_daily_std * math.sqrt(window_len)
        if trailing.sum() < floor:
            return True

    return False


def select_sleeve(
    candidate_results: list[dict],
    as_of: pd.Timestamp,
    meta: dict,
    current_sleeve: list[dict] | None = None,
) -> list[dict]:
    """Select the sleeve to hold starting at `as_of`.

    `candidate_results`: one dict per eligible strategy --
    `{"family": str, "params": dict, "test_id": int | None,
    "returns": pd.Series (daily, ascending DatetimeIndex),
    "backtest_metrics": dict}`. `backtest_metrics` is that strategy's OWN
    FIXED research-period backtest (used only to calibrate its eviction
    thresholds -- see `_is_evicted`).

    Ranking uses each candidate's TRAILING window (`_trailing_window`,
    `meta["lookback_days"]` observations strictly before `as_of`); a
    candidate with fewer than `meta.get("min_track_days",
    meta["lookback_days"])` trailing observations is not eligible yet.
    Never reads a bar dated on or after `as_of`.

    `current_sleeve` (this function's own prior return value, or `None` for
    the first boundary) identifies incumbents (`_identity`) subject to the
    eviction guard: an incumbent whose trailing window breaches its own
    calibrated threshold (`_is_evicted`) is dropped from consideration this
    period regardless of its trailing rank. A normal losing streak never
    triggers this -- it can still fall out of the sleeve through ordinary
    reselection (ranking below the top `meta["n_strategies"]`), which is
    turnover, not eviction.

    Returns up to `meta["n_strategies"]` entries (copies of the matching
    `candidate_results` entries, plus `"trailing_sharpe"` and
    `"trailing_drawdown"` diagnostics), ranked by trailing Sharpe
    descending. Never mutates its inputs.
    """
    as_of = pd.Timestamp(as_of)
    lookback_days = meta["lookback_days"]
    min_track_days = meta.get("min_track_days", lookback_days)
    current_ids = {_identity(e) for e in (current_sleeve or [])}

    scored: list[dict] = []
    for entry in candidate_results:
        trailing = _trailing_window(entry["returns"], as_of, lookback_days)
        if len(trailing) < min_track_days:
            continue
        if _identity(entry) in current_ids and _is_evicted(entry, trailing, meta):
            continue
        scored.append(
            {
                **entry,
                "trailing_sharpe": _trailing_sharpe(trailing),
                "trailing_drawdown": _trailing_max_drawdown(trailing),
            }
        )

    scored.sort(key=lambda e: e["trailing_sharpe"], reverse=True)
    return scored[: meta["n_strategies"]]


# ---------------------------------------------------------------------------
# walk_forward: repeat select_sleeve across [start, end] and stitch.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CandidateTrack:
    """One candidate's own standalone backtest, prepared once and reused at
    every `walk_forward` boundary."""

    family: str
    params: dict
    test_id: int | None
    tickers: list[str]
    weights: pd.DataFrame  # this candidate's own raw target weights, through `end`
    returns: pd.Series  # this candidate's own standalone daily returns, through `end`
    backtest_metrics: dict  # FIXED research-period baseline, for eviction calibration


def _raw_weights(family: str, params: dict, data: SearchData) -> tuple[pd.DataFrame, list[str]]:
    spec = _spec_for(family)
    tickers = spec.tickers(params)
    weight_kwargs = {k: v for k, v in params.items() if k != "tickers"}
    frames = data.fields(spec.fields, tickers)
    weights = spec.weights(*frames, **weight_kwargs)
    weights = exit_before_delisting(weights, data.open_[tickers], data.close[tickers])
    return weights, tickers


def prepare_candidate_track(
    family: str,
    params: dict,
    data: SearchData,
    criteria: dict,
    end: pd.Timestamp,
    *,
    test_id: int | None = None,
    benchmark_metrics: dict | None = None,
) -> CandidateTrack | None:
    """Backtest one candidate standalone, from the start of its own history
    through `end`, for `walk_forward`'s trailing-lookback ranking, plus its
    FIXED research-period metrics (`qrl.search.evaluate_candidate`) as the
    eviction-calibration baseline (see `select_sleeve`'s `_is_evicted`).

    Returns `None` (never raises) if the candidate cannot be backtested at
    all over this window -- bad params, no valid signal, a missing ticker --
    matching `evaluate_candidate`'s "never kill an unattended run" rule; a
    single unusable candidate is simply excluded from sleeve consideration.
    """
    try:
        weights, tickers = _raw_weights(family, params, data)
        weights = weights.loc[:end]
        opens = data.open_[tickers].loc[:end]
        closes = data.close[tickers].loc[:end]
        result = run_backtest(
            opens, closes, weights, cost_bps=criteria["costs"]["bps_per_unit_turnover"]
        )
        baseline = evaluate_candidate(family, params, data, criteria, benchmark_metrics, "research")
        return CandidateTrack(
            family=family,
            params=params,
            test_id=test_id,
            tickers=tickers,
            weights=weights,
            returns=result.returns,
            backtest_metrics=baseline["metrics"],
        )
    except Exception:
        return None


def _track_to_candidate_result(track: CandidateTrack) -> dict:
    return {
        "family": track.family,
        "params": track.params,
        "test_id": track.test_id,
        "returns": track.returns,
        "backtest_metrics": track.backtest_metrics,
    }


def walk_forward(
    candidate_specs: list[dict],
    data: SearchData,
    criteria: dict,
    meta: dict,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    *,
    capital_share: float = 1.0,
    benchmark_metrics: dict | None = None,
) -> dict:
    """Walk the sleeve forward across `[start, end]`.

    At each boundary from `period_starts(calendar, meta.get("frequency",
    "QS"))` (`calendar = data.close.loc[start:end].index`), `select_sleeve`
    picks the sleeve using only data strictly before that boundary; the
    sleeve holds until the next boundary (or `end`). Every period's
    selected members' own weights (scaled to an equal share of
    `capital_share` among that period's selected count) are written into
    ONE combined target-weights matrix over the whole `[start, end]`
    calendar, which is then run through `qrl.engine.run_backtest` exactly
    ONCE -- so a strategy entering or leaving the sleeve at a boundary
    shows up as ordinary turnover, costed by the engine like any other
    trade, never assembled from separately-costed per-period pieces.

    `candidate_specs`: `[{"family": str, "params": dict, "test_id": int |
    None}, ...]`, the universe of strategies eligible for the sleeve. Each
    is backtested once via `prepare_candidate_track`; a candidate that
    cannot be backtested over this window is silently excluded (see that
    function's docstring).

    Returns `{"returns": pd.Series, "metrics": dict, "selections": [...],
    "weights": pd.DataFrame}`. `selections` has one entry per boundary:
    `{"as_of": Timestamp, "sleeve": [{"family", "params", "test_id",
    "trailing_sharpe", "trailing_drawdown"}, ...]}`, in boundary order.

    Raises `ValueError` if no candidate can be backtested at all, or if
    `[start, end]` covers no price data.
    """
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    tracks = [
        t
        for t in (
            prepare_candidate_track(
                c["family"],
                c["params"],
                data,
                criteria,
                end,
                test_id=c.get("test_id"),
                benchmark_metrics=benchmark_metrics,
            )
            for c in candidate_specs
        )
        if t is not None
    ]
    if not tracks:
        raise ValueError("walk_forward: no candidate could be backtested over this window.")

    calendar = data.close.loc[start:end].index
    if len(calendar) == 0:
        raise ValueError(f"walk_forward: no price data between {start.date()} and {end.date()}.")
    boundaries = period_starts(calendar, meta.get("frequency", "QS"))

    all_tickers = sorted({t for track in tracks for t in track.tickers})
    combined = pd.DataFrame(0.0, index=calendar, columns=all_tickers)
    candidate_results = [_track_to_candidate_result(t) for t in tracks]
    track_by_id = {_identity(t): t for t in tracks}

    selections_log: list[dict] = []
    current_selection: list[dict] = []
    for i, as_of in enumerate(boundaries):
        period_end = boundaries[i + 1] if i + 1 < len(boundaries) else None
        selection = select_sleeve(candidate_results, as_of, meta, current_sleeve=current_selection)
        selections_log.append(
            {
                "as_of": as_of,
                "sleeve": [
                    {
                        "family": s["family"],
                        "params": s["params"],
                        "test_id": s.get("test_id"),
                        "trailing_sharpe": s["trailing_sharpe"],
                        "trailing_drawdown": s["trailing_drawdown"],
                    }
                    for s in selection
                ],
            }
        )
        if selection:
            if period_end is not None:
                mask = (calendar >= as_of) & (calendar < period_end)
            else:
                mask = calendar >= as_of
            period_slice = calendar[mask]
            weight_per_member = capital_share / len(selection)
            for member in selection:
                track = track_by_id[_identity(member)]
                member_weights = track.weights.reindex(period_slice).fillna(0.0)[track.tickers]
                combined.loc[period_slice, track.tickers] += member_weights * weight_per_member
        current_selection = selection

    opens = data.open_[all_tickers].loc[calendar[0] : calendar[-1]]
    closes = data.close[all_tickers].loc[calendar[0] : calendar[-1]]
    result = run_backtest(
        opens, closes, combined, cost_bps=criteria["costs"]["bps_per_unit_turnover"]
    )
    metrics = compute_metrics(result.returns, result.turnover, result.executed)
    return {
        "returns": result.returns,
        "metrics": metrics,
        "selections": selections_log,
        "weights": combined,
    }


# ---------------------------------------------------------------------------
# tune_meta: meta-setting grid search, research + validation dates only.
# ---------------------------------------------------------------------------


def tune_meta(
    candidate_specs: list[dict],
    data: SearchData,
    criteria: dict,
    ledger: Ledger,
    run_id: int,
    search_space: dict[str, list],
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    *,
    capital_share: float = 1.0,
    benchmark_metrics: dict | None = None,
) -> list[dict]:
    """Grid-search meta-settings over `[start, end]`.

    `search_space` maps a meta key (`"n_strategies"`, `"lookback_days"`,
    `"frequency"`, `"eviction_dd_multiple"`, `"eviction_underperf_multiple"`,
    ...) to a list of values to try; every combination
    (`qrl.strategies.iter_grid`) is run through `walk_forward` once and
    logged to the ledger's `meta_tests` table via `Ledger.record_meta_test`
    -- EVERY meta-setting tried, not just the best (PLAN.md 2.6).

    RESEARCH + VALIDATION ONLY: refuses outright (`ValueError`, before
    running anything) if `end` reaches on or after the holdout period's
    start (`qrl.periods.period_bounds`). This is a belt-and-suspenders
    check, not the actual seal: neither this function nor `walk_forward`
    ever sets the `unseal_holdout` flag regardless of what `data` and
    dates they are given, so a caller cannot reach the holdout through this
    path even without this guard -- `qrl.holdout.unseal` is the only way,
    and never through meta-tuning.

    Returns `[{"meta": {...}, "metrics": {...}}, ...]` in
    `iter_grid`'s deterministic order, for the caller (a human, or the CLI
    printing every result) to pick a winner -- this function does not
    itself decide one.
    """
    holdout_start, _ = period_bounds(criteria, "holdout")
    end_ts = pd.Timestamp(end)
    if holdout_start is not None and end_ts >= holdout_start:
        raise ValueError(
            "tune_meta refuses to run with end on or after the holdout period's start -- "
            "meta-settings are tuned on research + validation dates only (PLAN.md 2.6)."
        )

    window = f"{pd.Timestamp(start).date()}:{end_ts.date()}"
    tried: list[dict] = []
    for meta in iter_grid(search_space):
        result = walk_forward(
            candidate_specs,
            data,
            criteria,
            meta,
            start,
            end,
            capital_share=capital_share,
            benchmark_metrics=benchmark_metrics,
        )
        ledger.record_meta_test(run_id, meta, window, result["metrics"])
        tried.append({"meta": meta, "metrics": result["metrics"]})
    return tried
