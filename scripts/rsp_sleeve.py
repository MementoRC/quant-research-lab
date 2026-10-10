"""Write research/rsp_sleeve.md from a fixed run's one recorded test (spec:
docs/methodology/rsp-sleeve.md, step 9). Reads the ledger only; selects and
changes nothing.

Usage:
    python scripts/rsp_sleeve.py --run 9 --validation-note "not run: failed on the research period"
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from search import _decode_fixed  # noqa: E402

from qrl.ledger import DEFAULT_LEDGER_PATH  # noqa: E402
from qrl.rsp_report import render_markdown  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", type=int, required=True)
    ap.add_argument("--validation-note", required=True)
    ap.add_argument("--ledger", default=str(ROOT / DEFAULT_LEDGER_PATH))
    ap.add_argument("--out-md", default=str(ROOT / "research" / "rsp_sleeve.md"))
    args = ap.parse_args(argv)

    conn = sqlite3.connect(f"file:{args.ledger}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT metrics_json, passed, failure_reasons FROM tests WHERE run_id = ?", (args.run,)
        ).fetchall()
        run = conn.execute(
            "SELECT combined_config_hash, seed_description FROM runs WHERE run_id = ?",
            (args.run,),
        ).fetchone()
    finally:
        conn.close()
    if run is not None and _decode_fixed(run["seed_description"] or "") is None:
        print(f"Run {args.run} is not a fixed-candidate run.", file=sys.stderr)
        return 2
    if run is None or len(rows) != 1:
        print(f"Run {args.run} needs exactly one recorded test; found {len(rows)}.")
        return 1
    row = rows[0]
    metrics = json.loads(row["metrics_json"])
    if "combined_sharpe" not in metrics and "error" not in metrics:
        print(f"Run {args.run}'s test has no combined metrics: {metrics}")
        return 1
    report = {
        "run_id": args.run,
        "passed": bool(row["passed"]),
        "failure_reasons": row["failure_reasons"],
        "metrics": metrics,
        "validation_note": args.validation_note,
        "combined_config_hash": run["combined_config_hash"],
    }
    Path(args.out_md).write_text(render_markdown(report))
    print(f"Wrote {args.out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
