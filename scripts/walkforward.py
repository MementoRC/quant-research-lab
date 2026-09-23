"""Milestone 2.6 walk-forward sleeve-selection CLI: grid-search meta-settings
and walk the sleeve forward, over RESEARCH + VALIDATION dates only (never
the holdout -- see `qrl.holdout` for the one guarded, one-shot exception).
See `qrl.walkforward` for the exact selection/eviction/stitching rules and
PLAN.md section 2.6.

Usage:
    python scripts/walkforward.py tune --run 1 --synthetic
    python scripts/walkforward.py tune --run 1 --search-space space.json --synthetic
    python scripts/walkforward.py run --run 1 --n-strategies 5 --lookback-days 126 --synthetic
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qrl.criteria import load_criteria  # noqa: E402
from qrl.ledger import DEFAULT_LEDGER_PATH, Ledger  # noqa: E402
from qrl.periods import period_bounds  # noqa: E402
from qrl.search import SearchData, compute_benchmark_metrics  # noqa: E402
from qrl.universe import load_universe  # noqa: E402
from qrl.walkforward import tune_meta, walk_forward  # noqa: E402

DEFAULT_UNIVERSE_TICKERS = ("QQQ", "GLD", "TLT")

# A small default grid: enough to demonstrate every meta knob PLAN.md 2.6
# names (sleeve size, lookback, reselection frequency, eviction multiples)
# without an unattended run taking long. `--search-space` overrides it.
DEFAULT_META_SEARCH_SPACE: dict[str, list] = {
    "n_strategies": [3, 5],
    "lookback_days": [63, 126],
    "frequency": ["QS"],
    "eviction_dd_multiple": [1.5, 2.0],
    "eviction_underperf_multiple": [2.0, 3.0],
}


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


def _load_context(args: argparse.Namespace) -> tuple[dict, SearchData, dict]:
    criteria, _criteria_hash = load_criteria(args.criteria)
    universe = load_universe(args.universe)
    sleeve_tickers = list(universe["tickers"])
    needed = set(sleeve_tickers) | set(DEFAULT_UNIVERSE_TICKERS) | set(criteria["benchmarks"])
    data = SearchData.load(sorted(needed), synthetic=args.synthetic)
    bench = compute_benchmark_metrics(data, criteria)
    return criteria, data, bench


def _research_validation_bounds(criteria: dict) -> tuple:
    start, _ = period_bounds(criteria, "research")
    _, end = period_bounds(criteria, "validation")
    return start, end


def cmd_tune(args: argparse.Namespace) -> int:
    criteria, data, bench = _load_context(args)
    start, end = _research_validation_bounds(criteria)
    search_space = DEFAULT_META_SEARCH_SPACE
    if args.search_space:
        search_space = json.loads(Path(args.search_space).read_text())

    with Ledger(args.ledger) as ledger:
        run = _get_run(ledger, args.run)
        if run is None:
            print(f"Unknown run {args.run}", file=sys.stderr)
            return 2
        candidate_specs = _load_candidate_specs(ledger, args.run, args.top)
        if not candidate_specs:
            print("No passing research candidates to walk-forward.", file=sys.stderr)
            return 2
        tried = tune_meta(
            candidate_specs,
            data,
            criteria,
            ledger,
            args.run,
            search_space,
            start,
            end,
            capital_share=args.capital_share,
            benchmark_metrics=bench,
        )

    print(
        f"Tried {len(tried)} meta-setting(s) over {start.date()}..{end.date()} (research+validation):"
    )
    best = max(tried, key=lambda t: t["metrics"].get("sharpe", float("-inf")))
    for t in tried:
        marker = "  <- best by sharpe" if t is best else ""
        print(f"  {t['meta']} -> sharpe={t['metrics'].get('sharpe')!r}{marker}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    criteria, data, bench = _load_context(args)
    start, end = _research_validation_bounds(criteria)
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
            print("No passing research candidates to walk-forward.", file=sys.stderr)
            return 2

    result = walk_forward(
        candidate_specs,
        data,
        criteria,
        meta,
        start,
        end,
        capital_share=args.capital_share,
        benchmark_metrics=bench,
    )

    print(f"Walk-forward over {start.date()}..{end.date()} (research+validation), meta={meta}:")
    for period in result["selections"]:
        names = ", ".join(f"{m['family']}({m['params']})" for m in period["sleeve"]) or "(cash)"
        print(f"  {period['as_of'].date()}: {names}")
    print("Stitched metrics:")
    for key, value in result["metrics"].items():
        print(f"  {key}: {value}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--ledger", default=str(ROOT / DEFAULT_LEDGER_PATH))
    ap.add_argument("--criteria", default=str(ROOT / "config" / "criteria.yaml"))
    ap.add_argument("--universe", default=str(ROOT / "config" / "universe.yaml"))
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument(
        "--top", type=int, default=40, help="how many top research survivors to consider"
    )
    ap.add_argument(
        "--capital-share",
        type=float,
        default=1.0,
        help="sleeve's capital share (config/profile.yaml)",
    )
    sub = ap.add_subparsers(dest="command", required=True)

    p_tune = sub.add_parser("tune", help="Grid-search meta-settings over research+validation.")
    p_tune.add_argument("--run", type=int, required=True)
    p_tune.add_argument("--search-space", default=None, help="path to a JSON meta search space")
    p_tune.set_defaults(func=cmd_tune)

    p_run = sub.add_parser("run", help="Walk the sleeve forward with a fixed meta-setting.")
    p_run.add_argument("--run", type=int, required=True)
    p_run.add_argument("--n-strategies", type=int, default=5)
    p_run.add_argument("--lookback-days", type=int, default=126)
    p_run.add_argument("--frequency", default="QS")
    p_run.add_argument("--eviction-dd-multiple", type=float, default=1.5)
    p_run.add_argument("--eviction-underperf-multiple", type=float, default=2.0)
    p_run.set_defaults(func=cmd_run)

    return ap


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
