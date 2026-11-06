"""Journal, events log, reconcile baseline and reconcile of the IB paper
rebalancer (spec "Evening run" steps 3 and 7). Everything lives under
`reports/broker/`: private, gitignored, never under `site/`.

- Only a run that submits orders writes `<session-date>.json`; flatten and
  accept-positions write `<NY-date>-<kind>-<HHMMSS>.json`. A journal is never
  overwritten.
- Every other outcome appends one line to `events.jsonl`.
- The reconcile baseline is the journal with the greatest `recorded_at`
  among rebalance, flatten and accept files, never the last filename."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from qrl.broker import SubmittedOrder
from qrl.broker_session import ny_time

JOURNAL_KINDS = frozenset({"rebalance", "flatten", "accept"})
EVENTS = "events.jsonl"


def utc_iso(now: datetime) -> str:
    return now.astimezone(UTC).isoformat()


def dated_path(root: Path, session: date) -> Path:
    return root / f"{session.isoformat()}.json"


def stamped_path(root: Path, kind: str, now: datetime) -> Path:
    ny = ny_time(now)
    return root / f"{ny.date().isoformat()}-{kind}-{ny:%H%M%S}.json"


def _json_default(value: Any) -> Any:
    if isinstance(value, date | datetime):
        return value.isoformat()
    if hasattr(value, "item"):  # numpy scalar
        return value.item()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def write_journal(path: Path, record: Mapping[str, Any]) -> None:
    """Write a journal file atomically; raises FileExistsError rather than
    overwrite one. A crash leaves at most a stray `.tmp`, never a truncated
    journal."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with tmp.open("x", encoding="utf-8") as fh:
            json.dump(record, fh, indent=2, sort_keys=True, allow_nan=False, default=_json_default)
            fh.flush()
            os.fsync(fh.fileno())
        os.link(tmp, path)  # fails if path exists; os.replace would overwrite
    finally:
        tmp.unlink(missing_ok=True)


def append_event(root: Path, record: Mapping[str, Any]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True, allow_nan=False, default=_json_default)
    with (root / EVENTS).open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def read_journal(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:  # JSONDecodeError and UnicodeDecodeError
        raise ValueError(f"unreadable journal {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError(f"unreadable journal {path}: not a JSON object")
    return doc


def _recorded_at(path: Path, doc: Mapping[str, Any]) -> datetime:
    try:
        stamp = datetime.fromisoformat(doc["recorded_at"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"unreadable journal {path}: bad recorded_at ({exc!r})") from exc
    if stamp.tzinfo is None:
        raise ValueError(f"unreadable journal {path}: recorded_at has no timezone")
    return stamp


def latest_baseline(root: Path) -> dict[str, Any] | None:
    """The newest journal by `recorded_at`. An unreadable `*.json` raises a
    ValueError naming it: the run must halt, not skip it."""
    best: tuple[datetime, dict[str, Any]] | None = None
    for path in root.glob("*.json"):
        doc = read_journal(path)
        if doc.get("kind") not in JOURNAL_KINDS:
            continue
        stamp = _recorded_at(path, doc)
        if best is None or stamp > best[0]:
            best = (stamp, doc)
    return None if best is None else best[1]


def expected_positions(
    pre_trade: Mapping[str, int], submitted: Iterable[SubmittedOrder]
) -> dict[str, int]:
    """Pre-trade positions plus each order's delta (0 if rejected or cancelled)."""
    out = dict(pre_trade)
    for sub in submitted:
        out[sub.order.symbol] = out.get(sub.order.symbol, 0) + sub.delta
    return {s: n for s, n in sorted(out.items()) if n != 0}


def reconcile(expected: Mapping[str, int], actual: Mapping[str, int]) -> list[str]:
    """One line per symbol whose share count differs (absent = 0)."""
    return [
        f"{s}: expected {expected.get(s, 0)}, IB holds {actual.get(s, 0)}"
        for s in sorted(set(expected) | set(actual))
        if expected.get(s, 0) != actual.get(s, 0)
    ]


def order_records(submitted: Iterable[SubmittedOrder]) -> list[dict[str, Any]]:
    return [
        {**asdict(sub.order), "order_id": sub.order_id, "status": sub.status} for sub in submitted
    ]
