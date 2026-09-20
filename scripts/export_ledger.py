"""Export the search ledger to the dashboard summary and a committed CSV.

Writes two files:
    site/data/research.json     dashboard funnel/summary (gitignored, rebuilt
                                 by the build; see .gitignore's site/data/*.json)
    research/top_candidates.csv committed: the top N candidates by a metric,
                                 sorted deterministically, so research history
                                 is visible on GitHub without the local
                                 SQLite ledger.

Usage:
    python scripts/export_ledger.py
    python scripts/export_ledger.py --ledger research/ledger.sqlite --top-n 20
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qrl.ledger import DEFAULT_LEDGER_PATH, Ledger  # noqa: E402

DEFAULT_JSON_OUT = ROOT / "site" / "data" / "research.json"
DEFAULT_CSV_OUT = ROOT / "research" / "top_candidates.csv"
CSV_METRIC_KEYS = ("sharpe", "cagr", "max_drawdown", "trades")
CSV_FIELDNAMES = (
    "test_id",
    "run_id",
    "family",
    "params",
    "universe",
    "passed",
    "validated",
    *CSV_METRIC_KEYS,
)


def _build_summary_payload(ledger: Ledger) -> dict:
    overall = ledger.summary(run_id=None)
    return {
        "funnel": {
            "tested": overall["tested"],
            "passed_research": overall["passed"],
            "validated": overall["validated"],
        },
        "by_family": overall["by_family"],
        "near_misses": overall["near_misses"],
        "total_attempts": overall["tested"],
        "runs": [
            {
                "run_id": r["run_id"],
                "started_at": r["started_at"],
                "ended_at": r["ended_at"],
                "seed_lane": r["seed_lane"],
                "criteria_hash": r["criteria_hash"],
                "git_commit": r["git_commit"],
            }
            for r in ledger.list_runs()
        ],
    }


def _candidate_row(candidate: dict) -> dict:
    row = {
        "test_id": candidate["test_id"],
        "run_id": candidate["run_id"],
        "family": candidate["family"],
        "params": json.dumps(candidate["params"], sort_keys=True, separators=(",", ":")),
        "universe": candidate["universe"],
        "passed": int(candidate["passed"]),
        "validated": int(candidate["validated"]),
    }
    for key in CSV_METRIC_KEYS:
        row[key] = candidate["metrics"].get(key)
    return row


def _write_csv(path: Path, candidates: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for candidate in candidates:
            writer.writerow(_candidate_row(candidate))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":"), default=str))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ledger", default=str(ROOT / DEFAULT_LEDGER_PATH))
    ap.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    ap.add_argument("--csv-out", default=str(DEFAULT_CSV_OUT))
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--order-by", default="sharpe")
    args = ap.parse_args(argv)

    ledger_path = Path(args.ledger)
    if not ledger_path.exists():
        print(f"No ledger at {ledger_path}; nothing to export.")
        return 0

    with Ledger(ledger_path) as ledger:
        payload = _build_summary_payload(ledger)
        candidates = ledger.top_candidates(run_id=None, n=args.top_n, order_by=args.order_by)

    candidates.sort(key=lambda c: (-c["metrics"].get(args.order_by, 0), c["test_id"]))

    _write_json(Path(args.json_out), payload)
    _write_csv(Path(args.csv_out), candidates)
    print(f"Wrote {args.json_out}")
    print(f"Wrote {args.csv_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
