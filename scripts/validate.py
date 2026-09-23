"""Milestone 2.5 validation CLI: rank a run's research survivors, run each
through the neighbourhood check, one validation-period evaluation, the
deflated Sharpe ratio, and the correlation filter, then print the funnel and
a per-candidate outcome. See `qrl.validation.validate_survivors` for the
exact protocol and PLAN.md section 2.5 for why each check exists.

Usage:
    python scripts/validate.py --run 1 --synthetic
    python scripts/validate.py --run 1 --top 10 --synthetic
    python scripts/validate.py --run 1 --validation-config config/validation.yaml

Exits non-zero only on a real error (an unknown run id); "nothing accepted"
is a valid, non-error outcome and exits 0.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qrl.criteria import load_criteria  # noqa: E402
from qrl.ledger import DEFAULT_LEDGER_PATH, Ledger  # noqa: E402
from qrl.search import SearchData, compute_benchmark_metrics  # noqa: E402
from qrl.strategies import REGISTRY, SLEEVE_REGISTRY  # noqa: E402
from qrl.universe import load_universe  # noqa: E402
from qrl.validation import load_validation_config, validate_survivors  # noqa: E402

SEARCHABLE_SPACES: dict[str, dict[str, list]] = {
    **{name: spec.space for name, spec in SLEEVE_REGISTRY.items()},
    "core_trend": REGISTRY["core_trend"].space,
}
DEFAULT_UNIVERSE_TICKERS = ("QQQ", "GLD", "TLT")

FUNNEL_STAGES = (
    ("survivors", "Survivors (top research candidates)"),
    ("passed_neighbourhood", "Passed neighbourhood check"),
    ("validated", "Evaluated on validation period"),
    ("passed_deflated_sharpe", "Passed deflated Sharpe"),
    ("passed_correlation", "Passed correlation filter"),
    ("accepted", "Accepted"),
)


def _get_run(ledger: Ledger, run_id: int) -> dict | None:
    for run in ledger.list_runs():
        if run["run_id"] == run_id:
            return run
    return None


def _print_funnel(funnel: dict) -> None:
    print("Validation funnel:")
    for key, label in FUNNEL_STAGES:
        print(f"  {label:<34} {funnel[key]}")


def _print_candidates(candidates: list[dict]) -> None:
    print("Per-candidate outcome:")
    if not candidates:
        print("  (no survivors to validate)")
        return
    for c in candidates:
        stage = c["stage"]
        detail = "" if stage == "accepted" else f" -- {c['reason']}"
        print(f"  test {c['test_id']:<6} {c['family']:<16} {stage}{detail}")


def cmd_validate(args: argparse.Namespace) -> int:
    criteria, criteria_hash = load_criteria(args.criteria)
    validation_config, validation_hash = load_validation_config(args.validation_config)
    if args.top is not None:
        validation_config = {**validation_config, "top_n_to_validate": args.top}

    with Ledger(args.ledger) as ledger:
        run = _get_run(ledger, args.run)
        if run is None:
            print(f"Unknown run {args.run}", file=sys.stderr)
            return 2

        universe = load_universe(args.universe)
        sleeve_tickers = list(universe["tickers"])
        needed = set(sleeve_tickers) | set(DEFAULT_UNIVERSE_TICKERS) | set(criteria["benchmarks"])
        data = SearchData.load(sorted(needed), synthetic=args.synthetic)
        bench = compute_benchmark_metrics(data, criteria)

        report = validate_survivors(
            ledger,
            args.run,
            data,
            criteria,
            validation_config,
            validation_hash,
            criteria_hash=criteria_hash,
            universe_name=universe["name"],
            spaces=SEARCHABLE_SPACES,
            benchmark_metrics=bench,
        )

    _print_funnel(report["funnel"])
    _print_candidates(report["candidates"])
    return 0


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--run", type=int, required=True)
    ap.add_argument(
        "--top", type=int, default=None, help="override validation.yaml's top_n_to_validate"
    )
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--ledger", default=str(ROOT / DEFAULT_LEDGER_PATH))
    ap.add_argument("--criteria", default=str(ROOT / "config" / "criteria.yaml"))
    ap.add_argument("--validation-config", default=str(ROOT / "config" / "validation.yaml"))
    ap.add_argument("--universe", default=str(ROOT / "config" / "universe.yaml"))
    ap.set_defaults(func=cmd_validate)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
