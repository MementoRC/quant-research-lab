"""Forward-only paper tracking of pre-registered candidates (PLAN.md 3.2,
amendment 2026-10-02).

The rule lives in `config/paper.yaml` and is fixed for the whole track. Each
candidate's strategy is rebuilt from its ledger row; weights are computed on
the full price history (lookbacks need it) and then forced to zero before
`start_date`, and the backtest only ever sees rows from `start_date` onward, so
no return dated on or before the start row is produced or reported. This
module never calls `slice_period` and never touches the sealed holdout.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .controls import null_sleeve_weights
from .engine import run_backtest
from .ledger import Ledger, LedgerError
from .metrics import drawdown
from .strategies import REGISTRY, SLEEVE_REGISTRY
from .tradability import exit_before_delisting

_ALL_SPECS = {**REGISTRY, **SLEEVE_REGISTRY}
_DUE_WINDOW_DAYS = 7


def load_paper_config(path: str | Path) -> tuple[dict, str]:
    """Return (config, sha256 hex digest of the raw file bytes)."""
    raw = Path(path).read_bytes()
    return yaml.safe_load(raw), hashlib.sha256(raw).hexdigest()


def load_candidate(ledger: Ledger, entry: dict) -> dict:
    """Rebuild one candidate from its ledger row: family, params, and the
    research-period max drawdown. Raises if the row or family does not match."""
    rows = [t for t in ledger.list_tests(entry["run_id"]) if t["test_id"] == entry["test_id"]]
    if not rows:
        raise LedgerError(f"test {entry['test_id']} not found in run {entry['run_id']}")
    row = rows[0]
    if row["family"] != entry["family"]:
        raise LedgerError(
            f"test {entry['test_id']}: config says {entry['family']!r}, "
            f"ledger says {row['family']!r}"
        )
    metrics_row = ledger._conn.execute(
        "SELECT metrics_json FROM tests WHERE test_id = ?", (entry["test_id"],)
    ).fetchone()
    metrics = json.loads(metrics_row["metrics_json"])
    if "max_drawdown" not in metrics:
        raise LedgerError(f"test {entry['test_id']} has no recorded max_drawdown")
    return {
        **entry,
        "params": row["params"],
        "research_max_drawdown": float(metrics["max_drawdown"]),
    }


def required_tickers(candidates: list[dict]) -> list[str]:
    return sorted({t for c in candidates for t in _ALL_SPECS[c["family"]].tickers(c["params"])})


def candidate_weights(family: str, params: dict, data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Full-history target weights, built exactly like `qrl.search` and
    `scripts/daily_check.py` (the "tickers" param is a universe, not a kwarg)."""
    spec = _ALL_SPECS[family]
    cols = spec.tickers(params)
    kwargs = {k: v for k, v in params.items() if k != "tickers"}
    weights = spec.weights(*[data[f][cols] for f in spec.fields], **kwargs)
    return exit_before_delisting(weights, data["open"][cols], data["close"][cols])


def forward_weights(weights: pd.DataFrame, start: pd.Timestamp) -> pd.DataFrame:
    """Force every weight dated before `start` to zero."""
    out = weights.copy()
    out.loc[out.index < start] = 0.0
    return out


def forward_returns(
    data: dict[str, pd.DataFrame],
    weights: pd.DataFrame,
    start: pd.Timestamp,
    cost_bps: float,
) -> pd.Series:
    """Engine returns for weights from `start` onward (same costs and
    execution convention as research backtests). Empty if no forward day."""
    cols = list(weights.columns)
    fwd = forward_weights(weights, start).loc[start:]
    if len(fwd) < 2:
        return pd.Series(dtype=float)
    return run_backtest(data["open"][cols], data["close"][cols], fwd, cost_bps=cost_bps).returns


def _cumulative(returns: pd.Series) -> float:
    return float(np.prod(1 + returns.to_numpy(dtype=float))) - 1.0


def _review_dates(start: pd.Timestamp, months: list[int]) -> list[pd.Timestamp]:
    return [start + pd.DateOffset(months=m) for m in months]


def _drawdown_kill(returns: pd.Series, threshold: float) -> tuple[pd.Timestamp, float] | None:
    dd = -drawdown(returns)
    breach = dd[dd > threshold]
    return (breach.index[0], float(breach.iloc[0])) if len(breach) else None


def _underperformance_kill(
    returns: pd.Series, base: pd.Series, start: pd.Timestamp, rules: dict
) -> tuple[pd.Timestamp, float] | None:
    review = start + pd.DateOffset(months=rules["underperformance_review_month"])
    if returns.index[-1] < review:
        return None
    excess = _cumulative(returns.loc[:review]) - _cumulative(base.loc[:review])
    return (review, excess) if excess < rules["underperformance_min_excess"] else None


def find_kill(
    returns: pd.Series,
    base: pd.Series,
    start: pd.Timestamp,
    research_dd: float,
    rules: dict,
) -> tuple[str, pd.Timestamp] | None:
    """The earliest kill rule that fires, as (reason, date), or None."""
    threshold = rules["drawdown_multiple"] * research_dd
    hits: list[tuple[pd.Timestamp, str]] = []
    dd_hit = _drawdown_kill(returns, threshold)
    if dd_hit:
        hits.append((dd_hit[0], f"drawdown {dd_hit[1]:.3f} > {threshold:.3f}"))
    up_hit = _underperformance_kill(returns, base, start, rules)
    if up_hit:
        hits.append((up_hit[0], f"excess {up_hit[1]:+.3f} at review"))
    if not hits:
        return None
    date, reason = min(hits)
    return reason, date


def status_for(
    last: pd.Timestamp,
    excess: float,
    kill: tuple[str, pd.Timestamp] | None,
    cfg: dict,
) -> tuple[str, str | None]:
    """(status, next review date). Status is tracking, dropped, review due or
    eligible; "review due" holds for a week after a 3/6-month review date."""
    start = pd.Timestamp(cfg["start_date"])
    reviews = _review_dates(start, cfg["reviews_months"])
    upcoming = [r for r in reviews if r > last]
    next_review = upcoming[0].date().isoformat() if upcoming else None
    if kill:
        return f"dropped ({kill[0]}, {kill[1].date()})", next_review
    promote = cfg["promote_rule"]
    if last >= start + pd.DateOffset(months=promote["review_month"]):
        return ("eligible" if excess > promote["min_excess"] else "review due"), next_review
    passed = [r for r in reviews if r <= last]
    if passed and (last - passed[-1]).days <= _DUE_WINDOW_DAYS:
        return "review due", next_review
    return "tracking", next_review


def _nonzero_row(weights: pd.DataFrame) -> dict[str, float]:
    row = weights.iloc[-1].dropna()
    return {str(t): round(float(w), 6) for t, w in row.items() if abs(w) > 1e-9}


def track_candidate(
    cand: dict,
    cfg: dict,
    data: dict[str, pd.DataFrame],
    cost_bps: float,
) -> dict:
    start = pd.Timestamp(cfg["start_date"])
    weights = candidate_weights(cand["family"], cand["params"], data)
    cols = list(weights.columns)
    returns = forward_returns(data, weights, start, cost_bps)
    out: dict = {
        "test_id": cand["test_id"],
        "run_id": cand["run_id"],
        "family": cand["family"],
        "start_date": start.date().isoformat(),
        "last_data_date": weights.index[-1].date().isoformat(),
        "trading_days": int(len(returns)),
    }
    if returns.empty:
        out["status"] = "waiting for first forward day"
        if weights.index[-1] >= start:
            out["target_weights"] = _nonzero_row(forward_weights(weights, start))
        return out

    base_w = exit_before_delisting(
        null_sleeve_weights(data["close"], cols, cfg["baseline"]),
        data["open"][cols],
        data["close"][cols],
    )
    base = forward_returns(data, base_w, start, cost_bps)
    threshold = cfg["kill_rules"]["drawdown_multiple"] * cand["research_max_drawdown"]
    kill = find_kill(returns, base, start, cand["research_max_drawdown"], cfg["kill_rules"])
    cum, base_cum = _cumulative(returns), _cumulative(base)
    status, next_review = status_for(returns.index[-1], cum - base_cum, kill, cfg)
    out.update(
        {
            "last_data_date": returns.index[-1].date().isoformat(),
            "cumulative_return": cum,
            "baseline_cumulative_return": base_cum,
            "excess": cum - base_cum,
            "max_drawdown": float(-drawdown(returns).min()),
            "kill_drawdown_threshold": threshold,
            "status": status,
            "next_review_date": next_review,
            "target_weights": _nonzero_row(forward_weights(weights, start)),
        }
    )
    return out


def run_paper_track(
    cfg: dict,
    ledger: Ledger,
    load_data: Callable[[list[str]], dict[str, pd.DataFrame]],
    cost_bps: float,
) -> list[dict]:
    """Track every configured candidate. `load_data(tickers)` returns
    {"open","high","low","close","volume"} frames (injectable for tests)."""
    cands = [load_candidate(ledger, e) for e in cfg["candidates"]]
    data = load_data(required_tickers(cands))
    return [track_candidate(c, cfg, data, cost_bps) for c in cands]
