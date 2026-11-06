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


def write_journal(path: Path, record: Mapping[str, Any]) -> None:
    """Write a journal file; raises FileExistsError rather than overwrite one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, sort_keys=True)


def append_event(root: Path, record: Mapping[str, Any]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    with (root / EVENTS).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def latest_baseline(root: Path) -> dict[str, Any] | None:
    best: tuple[datetime, dict[str, Any]] | None = None
    for path in root.glob("*.json"):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or doc.get("kind") not in JOURNAL_KINDS:
            continue
        stamp = datetime.fromisoformat(doc["recorded_at"])
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
