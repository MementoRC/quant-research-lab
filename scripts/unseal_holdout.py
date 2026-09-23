"""Milestone 2.6's one-shot, human-triggered holdout gateway CLI. See
`qrl.holdout.unseal`: refuses without `--confirm`, refuses a second
unsealing unless `--force` (naming the earlier event), and records every
unsealing -- including a forced repeat -- in the ledger's `holdout_events`
table.

THIS IS ONE-SHOT AND IRREVERSIBLE: it exists to run the FINAL,
ALREADY-CHOSEN walk-forward process on the holdout period, once, for the
whole project. Never run this to pick between candidates, tune
meta-settings, or "see how it does" -- every look at the holdout after this
makes any later number dishonest (PLAN.md section 3, "The holdout was
contaminated"). Exercise this CLI only against a scratch ledger with
synthetic data; the owner, not an agent, decides when to spend the real
holdout.

Usage:
    python scripts/unseal_holdout.py --run 1 --reason "final chosen process" \\
        --confirm --synthetic --ledger /tmp/scratch.sqlite
    python scripts/unseal_holdout.py --run 1 --reason "re-run after a bugfix" \\
        --confirm --force --synthetic --ledger /tmp/scratch.sqlite
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qrl.criteria import load_criteria  # noqa: E402
from qrl.holdout import HoldoutAlreadyUnsealedError, unseal  # noqa: E402
from qrl.ledger import DEFAULT_LEDGER_PATH, Ledger, current_git_commit  # noqa: E402
from qrl.search import SearchData, compute_benchmark_metrics  # noqa: E402
from qrl.universe import load_universe  # noqa: E402
from qrl.walkforward import walk_forward  # noqa: E402

DEFAULT_UNIVERSE_TICKERS = ("QQQ", "GLD", "TLT")

_WARNING = (
    "\n" + "=" * 72 + "\n"
    "  THIS UNSEALS THE HOLDOUT PERIOD. IT IS ONE-SHOT AND IRREVERSIBLE.\n"
    "  Every look at the holdout after this makes the next look less honest.\n"
    "  Only run this once, for the FINAL, ALREADY-CHOSEN walk-forward process.\n" + "=" * 72 + "\n"
)


def _get_run(ledger: Ledger, run_id: int) -> dict | None:
    for run in ledger.list_runs():
        if run["run_id"] == run_id:
            return run
    return None


def _load_candidate_specs(ledger: Ledger, run_id: int, top_n: int) -> list[dict]:
    survivors = [
        c for c in ledger.top_candidates(run_id=run_id, n=top_n, order_by="sharpe") if c["passed"]
    ]
    return [
        {"family": c["family"], "params": c["params"], "test_id": c["test_id"]} for c in survivors
    ]


def cmd_unseal(args: argparse.Namespace) -> int:
    print(_WARNING)
    criteria, _criteria_hash = load_criteria(args.criteria)
    universe = load_universe(args.universe)
    sleeve_tickers = list(universe["tickers"])
    needed = set(sleeve_tickers) | set(DEFAULT_UNIVERSE_TICKERS) | set(criteria["benchmarks"])
    data = SearchData.load(sorted(needed), synthetic=args.synthetic)
    bench = compute_benchmark_metrics(data, criteria)
    meta = {
        "n_strategies": args.n_strategies,
        "lookback_days": args.lookback_days,
        "frequency": args.frequency,
        "eviction_dd_multiple": args.eviction_dd_multiple,
        "eviction_underperf_multiple": args.eviction_underperf_multiple,
    }

    with Ledger(args.ledger) as ledger:
        run = _get_run(ledger, args.run)
        if run is None:
            print(f"Unknown run {args.run}", file=sys.stderr)
            return 2
        candidate_specs = _load_candidate_specs(ledger, args.run, args.top)
        if not candidate_specs:
            print("No passing research candidates for the final process.", file=sys.stderr)
            return 2

        try:
            holdout_close = unseal(
                ledger,
                data.close,
                criteria,
                args.reason,
                what_unsealed=f"walk-forward run {args.run} final chosen process",
                confirm=args.confirm,
                force=args.force,
                git_commit=current_git_commit(ROOT),
            )
        except (ValueError, HoldoutAlreadyUnsealedError) as err:
            print(f"Refused: {err}", file=sys.stderr)
            return 2

    if holdout_close.empty:
        print("Holdout unsealed, but no price rows fall inside it.")
        return 0

    result = walk_forward(
        candidate_specs,
        data,
        criteria,
        meta,
        holdout_close.index[0],
        holdout_close.index[-1],
        capital_share=args.capital_share,
        benchmark_metrics=bench,
    )
    print("Holdout metrics for the final chosen process:")
    for key, value in result["metrics"].items():
        print(f"  {key}: {value}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--run", type=int, required=True)
    ap.add_argument("--reason", required=True, help="why the holdout is being unsealed now")
    ap.add_argument("--confirm", action="store_true", help="required to proceed at all")
    ap.add_argument("--force", action="store_true", help="required to unseal a second time")
    ap.add_argument("--ledger", default=str(ROOT / DEFAULT_LEDGER_PATH))
    ap.add_argument("--criteria", default=str(ROOT / "config" / "criteria.yaml"))
    ap.add_argument("--universe", default=str(ROOT / "config" / "universe.yaml"))
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument(
        "--top", type=int, default=40, help="how many top research survivors to consider"
    )
    ap.add_argument("--capital-share", type=float, default=1.0)
    ap.add_argument("--n-strategies", type=int, default=5)
    ap.add_argument("--lookback-days", type=int, default=126)
    ap.add_argument("--frequency", default="QS")
    ap.add_argument("--eviction-dd-multiple", type=float, default=1.5)
    ap.add_argument("--eviction-underperf-multiple", type=float, default=2.0)
    ap.set_defaults(func=cmd_unseal)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
