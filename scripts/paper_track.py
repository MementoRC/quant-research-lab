"""Forward-only paper tracker (PLAN.md 3.2, amendment 2026-10-02).

Reads the pre-registered `config/paper.yaml`, rebuilds each candidate from the
ledger (read via `Ledger`, nothing recorded), refreshes prices, and writes a
PRIVATE report to `reports/paper_track.json` (gitignored; target weights are
embedded, so never wire this into `site/`). All logic lives in `qrl.paper`;
this script does IO and formatting only. Exit 0 unless an error occurs.

Usage:
    python scripts/paper_track.py
    python scripts/paper_track.py --out reports/paper_track.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qrl.criteria import load_criteria  # noqa: E402
from qrl.data import load_ohlcv  # noqa: E402
from qrl.ledger import DEFAULT_LEDGER_PATH, Ledger  # noqa: E402
from qrl.paper import load_paper_config, run_paper_track  # noqa: E402


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:+.2f}%"


def _print_table(results: list[dict]) -> None:
    for r in results:
        print(f"test {r['test_id']} ({r['family']}, run {r['run_id']}): {r['status']}")
        print(
            f"  start {r['start_date']}, last data {r['last_data_date']}, "
            f"forward trading days {r['trading_days']}"
        )
        if "cumulative_return" in r:
            print(
                f"  return {_pct(r['cumulative_return'])} vs baseline "
                f"{_pct(r['baseline_cumulative_return'])} (excess {_pct(r['excess'])})"
            )
            print(
                f"  max drawdown {r['max_drawdown'] * 100:.2f}% "
                f"(kill above {r['kill_drawdown_threshold'] * 100:.2f}%), "
                f"next review {r['next_review_date']}"
            )
        weights = r.get("target_weights")
        if weights:
            top = ", ".join(f"{t} {w:.3f}" for t, w in sorted(weights.items()))
            print(f"  target weights: {top}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=str(ROOT / "config" / "paper.yaml"))
    ap.add_argument("--criteria", default=str(ROOT / "config" / "criteria.yaml"))
    ap.add_argument("--ledger", default=str(ROOT / DEFAULT_LEDGER_PATH))
    ap.add_argument("--out", default=str(ROOT / "reports" / "paper_track.json"))
    args = ap.parse_args(argv)

    cfg, cfg_hash = load_paper_config(args.config)
    criteria, _ = load_criteria(args.criteria)
    with Ledger(args.ledger) as ledger:
        results = run_paper_track(
            cfg,
            ledger,
            lambda tickers: load_ohlcv(tickers, refresh=True),
            criteria["costs"]["bps_per_unit_turnover"],
        )

    report = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "config_hash": cfg_hash,
        "candidates": results,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # PRIVATE ARTIFACT: embeds target weights; stays under gitignored reports/.
    out.write_text(json.dumps(report, indent=2, default=str))

    print(f"Paper track (config {cfg_hash[:12]})")
    _print_table(results)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
