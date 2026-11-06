"""Runs of the IB paper rebalancer (spec: docs/methodology/broker-rebalancer.md):
the evening run (Task 10), and `--flatten` / `--accept-positions` (Task 11).
Every input is injected (broker, market loader, risk limits, journal folder,
clock) so tests drive the runs with FakeBroker; `scripts/rebalance.py` only
wires the real objects.

Evening run order: Gate; health checks; weights and closes; session date;
(a) "no new session" (exit 0), (b) same-session rerun, (c) unknown
position; reconcile; size; submit; journal. "No new session" comes first so
late data on the evening after a submitted run exits 0, not as a rerun.
Every outcome other than a submitting run appends one `events.jsonl` line and
never writes a dated journal."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, NoReturn

import pandas as pd

from qrl.broker import Broker, Order, Position, SubmittedOrder, to_positions
from qrl.broker_config import BrokerConfig
from qrl.broker_gate import gate
from qrl.broker_journal import (
    append_event,
    dated_path,
    expected_positions,
    latest_baseline,
    order_records,
    reconcile,
    utc_iso,
    write_journal,
)
from qrl.broker_session import ny_date, session_date
from qrl.live_weights import Market
from qrl.rebalance import Plan, plan
from qrl.risk import RiskLimits


@dataclass(frozen=True)
class RunContext:
    cfg: BrokerConfig
    broker: Broker
    load_market: Callable[[date], Market]
    limits: RiskLimits
    root: Path
    now: Callable[[], datetime]


@dataclass(frozen=True)
class RunResult:
    status: str
    exit_code: int
    detail: str
    path: Path | None = None


class _HaltError(Exception):
    """Raised by `_halt` after its events line is written; carries the run's result."""

    def __init__(self, result: RunResult) -> None:
        super().__init__(result.detail)
        self.result = result


def _halt(
    ctx: RunContext, stamp: datetime, status: str, detail: str, *, exit_code: int = 1, **extra: Any
) -> NoReturn:
    """Append one events line and stop the run; never touches a dated journal."""
    append_event(
        ctx.root, {"recorded_at": utc_iso(stamp), "status": status, "detail": detail, **extra}
    )
    raise _HaltError(RunResult(status, exit_code, detail))


def _guarded(ctx: RunContext, body: Callable[[RunContext, datetime], RunResult]) -> RunResult:
    """Run `body`; a halt returns its result; any other exception (data
    download, broker call, a partial submit) is recorded as one "error"
    events line and exits 1, so cron always sees a status and a log line."""
    stamp = ctx.now()
    try:
        return body(ctx, stamp)
    except _HaltError as halt:
        return halt.result
    except Exception as exc:
        detail = repr(exc)
        append_event(ctx.root, {"recorded_at": utc_iso(stamp), "status": "error", "detail": detail})
        return RunResult("error", 1, detail)


def _cash(ctx: RunContext, stamp: datetime) -> float:
    """IB cash (TotalCashValue); an adapter that cannot read it raises LookupError: refuse."""
    try:
        return ctx.broker.cash()
    except LookupError as exc:
        _halt(ctx, stamp, "refused", f"cash unavailable: {exc}")


def _submit_each(
    broker: Broker, orders: list[Order]
) -> tuple[list[SubmittedOrder], Exception | None]:
    """Submit one order at a time so a failure partway still tells us which
    orders IB accepted; returns those and the error, if any."""
    submitted: list[SubmittedOrder] = []
    for order in orders:
        try:
            submitted.extend(broker.submit([order]))
        except Exception as exc:
            return submitted, exc
    return submitted, None


def _healthy_market(ctx: RunContext, stamp: datetime, today: date) -> Market:
    market = ctx.load_market(today)
    if not market.health.ok:
        failed = "; ".join(
            f"{c.name}: {c.detail}" for c in market.health.checks if c.status != "ok"
        )
        _halt(ctx, stamp, "refused", f"health checks failed: {failed}")
    return market


def _session_checks(
    ctx: RunContext,
    stamp: datetime,
    session: date,
    held: Mapping[str, int],
    universe: pd.Index,
) -> None:
    today = ny_date(stamp)
    if session > today:
        detail = f"latest session {session} is after {today} (America/New_York): future bar or clock skew"
        _halt(ctx, stamp, "refused", detail)
    if session < today:
        detail = f"latest session {session} is before {today} (America/New_York)"
        _halt(ctx, stamp, "no new session", detail, exit_code=0)
    if dated_path(ctx.root, session).exists():
        _halt(ctx, stamp, "refused", f"session {session} already has a submitted journal (rerun)")
    outside = sorted(set(held) - set(universe))
    if outside:
        _halt(ctx, stamp, "refused", f"held symbol(s) outside the universe: {', '.join(outside)}")


def _reconcile(ctx: RunContext, stamp: datetime, held: Mapping[str, int]) -> dict[str, str]:
    try:
        baseline = latest_baseline(ctx.root)
    except ValueError as exc:  # an unreadable journal: halt, never trade on a guess
        _halt(ctx, stamp, "refused", str(exc))
    if baseline is None:
        return {"status": "skipped", "reason": "no previous journal"}
    mismatches = reconcile(baseline["expected_positions"], held)
    if mismatches:
        detail = "positions differ from the previous journal; check, then run --accept-positions"
        _halt(
            ctx,
            stamp,
            "reconcile mismatch",
            detail,
            mismatches=mismatches,
            baseline=baseline["recorded_at"],
        )
    return {"status": "ok", "baseline": str(baseline["recorded_at"])}


def _trade(
    ctx: RunContext,
    stamp: datetime,
    session: date,
    weights: pd.Series,
    closes: pd.Series,
    positions: list[Position],
    reconciled: dict[str, str],
) -> RunResult:
    cash = _cash(ctx, stamp)
    result = plan(weights, closes, positions, cash, ctx.cfg, ctx.limits)
    if result.refusals:
        _halt(ctx, stamp, "refused", "; ".join(result.refusals))
    skipped = [asdict(s) for s in result.skipped]
    if not result.orders:
        detail = f"every delta is zero or inside the deadband ({len(skipped)} skipped)"
        if result.notes:
            detail += f"; {'; '.join(result.notes)}"
        _halt(ctx, stamp, "nothing to trade", detail, exit_code=0, skipped=skipped)
    held = {p.symbol: p.shares for p in positions if p.shares != 0}
    submitted, error = _submit_each(ctx.broker, list(result.orders))
    path = dated_path(ctx.root, session)
    if submitted:  # only a run that submitted orders writes the dated journal
        write_journal(
            path,
            _journal(
                ctx, stamp, session, weights, closes, cash, result, held, submitted, reconciled
            )
            | {"submit_error": None if error is None else repr(error)},
        )
    if error is not None:
        raise error  # recorded by _guarded as one "error" events line, exit 1
    return RunResult("submitted", 0, f"{len(submitted)} order(s) queued for the next open", path)


def _journal(
    ctx: RunContext,
    stamp: datetime,
    session: date,
    weights: pd.Series,
    closes: pd.Series,
    cash: float,
    result: Plan,
    held: dict[str, int],
    submitted: list[SubmittedOrder],
    reconciled: dict[str, str],
) -> dict[str, Any]:
    """The dated journal: inputs, weights, equity, plan, pre-trade and expected
    positions, order ids and statuses (only the orders actually submitted)."""
    return {
        "kind": "rebalance",
        "recorded_at": utc_iso(stamp),
        "session_date": session.isoformat(),
        "inputs": {
            "account_id": ctx.cfg.account_id,
            "cash_buffer": ctx.cfg.cash_buffer,
            "deadband": ctx.cfg.deadband,
        },
        "weights": {str(s): float(w) for s, w in weights.items()},
        "closes": {str(s): float(c) for s, c in closes.items() if pd.notna(c)},
        "cash": cash,
        "equity": result.equity,
        "targets": dict(result.targets),
        "plan": {
            "orders": [asdict(o) for o in result.orders],
            "skipped": [asdict(s) for s in result.skipped],
            "notes": list(result.notes),
        },
        "pre_trade_positions": held,
        "submitted": order_records(submitted),
        "expected_positions": expected_positions(held, submitted),
        "reconcile": reconciled,
    }


def _evening(ctx: RunContext, stamp: datetime) -> RunResult:
    refusal, holdings = gate(ctx.cfg, ctx.broker)
    if refusal is not None:
        _halt(ctx, stamp, "refused", refusal)
    market = _healthy_market(ctx, stamp, ny_date(stamp))
    weights = market.combined.iloc[-1]
    positions = to_positions(holdings)
    held = {p.symbol: p.shares for p in positions if p.shares != 0}
    session = session_date(market.close, set(held) | {str(s) for s, w in weights.items() if w > 0})
    _session_checks(ctx, stamp, session, held, market.combined.columns)
    reconciled = _reconcile(ctx, stamp, held)
    closes: pd.Series = market.close.loc[pd.Timestamp(session)]
    return _trade(ctx, stamp, session, weights, closes, positions, reconciled)


def evening_run(ctx: RunContext) -> RunResult:
    """The daily evening run; see the module docstring for the order of steps."""
    return _guarded(ctx, _evening)
