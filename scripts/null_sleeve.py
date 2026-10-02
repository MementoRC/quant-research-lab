"""Read-only null-sleeve control for combined-rule runs.

Asks one question: does a deliberately dumb sleeve on the run's own stock
universe also pass the combined rule? If so, the rule cannot separate strategy
from universe (e.g. survivorship bias in a today's-large-caps list).

Usage:
    python scripts/null_sleeve.py --run 4
    python scripts/null_sleeve.py --run 1 --synthetic

This is a diagnostic, not a candidate. The ledger is opened read-only
(`mode=ro`), nothing is recorded as a test (so the deflated-Sharpe trial
count is untouched), nothing is written to tracked files, and only the
research period is evaluated. Exits 2 on a standalone run, a combined config
hash mismatch, a data-source mismatch, or an unknown run/ledger.

On a `combined_null` run (amendment 2026-10-02) both nulls are graded by the
beat-the-null rule. The `equal_weight` null IS that rule's baseline, so it
fails by construction (zero improvement series); `equal_weight_trend` is the
informative check there.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qrl.combined import (  # noqa: E402
    baseline_label,
    combined_config_for_run,
    combined_evaluation,
    config_path_for,
    core_tickers,
)
from qrl.controls import NULL_KINDS, null_sleeve_weights  # noqa: E402
from qrl.criteria import load_criteria  # noqa: E402
from qrl.engine import run_backtest  # noqa: E402
from qrl.ledger import (  # noqa: E402
    COMBINED_PASS_RULES,
    DEFAULT_LEDGER_PATH,
    data_source_fingerprint,
)
from qrl.metrics import compute_metrics  # noqa: E402
from qrl.periods import slice_period  # noqa: E402
from qrl.search import SearchData  # noqa: E402
from qrl.tradability import exit_before_delisting  # noqa: E402
from qrl.universe import load_universe  # noqa: E402

DEFAULT_UNIVERSE_TICKERS = ("QQQ", "GLD", "TLT")


def _open_readonly(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _read_run(conn: sqlite3.Connection, run_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if row is None:
        return None
    run = dict(row)
    raw = run.get("data_source")
    run["data_source"] = json.loads(raw) if raw else None
    return run


def _read_tests(conn: sqlite3.Connection, run_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT passed, metrics_json FROM tests WHERE run_id = ?", (run_id,)
    ).fetchall()
    return [{"passed": bool(r["passed"]), "metrics": json.loads(r["metrics_json"])} for r in rows]


def _fmt(metrics: dict) -> str:
    return (
        f"Sharpe {metrics.get('sharpe', float('nan')):.3f}  "
        f"CAGR {metrics.get('cagr', float('nan')):.4f}  "
        f"maxDD {metrics.get('max_drawdown', float('nan')):.3f}"
    )


def _print_comparison(imp: float, tests: list[dict]) -> None:
    passed = [t for t in tests if t["passed"]]
    print(f"  Run's recorded tests: {len(passed)}/{len(tests)} passed")
    values = [
        float(t["metrics"]["improvement_sharpe"])
        for t in passed
        if isinstance(t["metrics"].get("improvement_sharpe"), (int, float))
    ]
    if not values:
        print("  No passing candidates with improvement_sharpe to rank against.")
        return
    arr = np.array(values)
    pct = 100.0 * float((arr <= imp).sum()) / len(arr)
    print(
        f"  Null improvement_sharpe {imp:.3f} ranks at percentile {pct:.0f} of "
        f"{len(arr)} passing candidates (min {arr.min():.3f}, "
        f"median {float(np.median(arr)):.3f}, max {arr.max():.3f})"
    )


def _run_kind(
    kind: str,
    tickers: list[str],
    data: SearchData,
    criteria: dict,
    combined_cfg: dict,
    tests: list[dict],
) -> None:
    weights = null_sleeve_weights(data.close, tickers, kind)
    # Same delisting handling the families get in qrl.search.evaluate_candidate.
    weights = exit_before_delisting(weights, data.open_[tickers], data.close[tickers])
    result = run_backtest(
        data.open_[tickers],
        data.close[tickers],
        slice_period(weights, criteria, "research"),
        cost_bps=criteria["costs"]["bps_per_unit_turnover"],
    )
    sleeve = compute_metrics(result.returns, result.turnover, result.executed)
    ce = combined_evaluation(
        weights,
        data.open_,
        data.close,
        combined_cfg["core"],
        combined_cfg["capital_split"],
        criteria,
        combined_cfg,
        period="research",
        sleeve_trades=int(sleeve.get("trades", 0)),
    )
    label = baseline_label(combined_cfg)
    rule = "combined" if label == "core" else "combined_null"
    status = "PASS" if ce["passed"] else f"FAIL ({ce['failure_reasons']})"
    print(f"\n[{kind}] {rule} rule: {status}")
    print(f"  Combined   : {_fmt(ce['combined_metrics'])}")
    base_name = "Core alone " if label == "core" else "Core + null"
    print(f"  {base_name}: {_fmt(ce[f'{label}_metrics'])}")
    print(f"  improvement_sharpe: {ce['improvement_sharpe']:.3f}")
    print(f"  Sleeve alone: {_fmt(sleeve)}  trades {int(sleeve.get('trades', 0))}")
    _print_comparison(float(ce["improvement_sharpe"]), tests)
    if ce["passed"]:
        print(f"  VERDICT [{kind}]: NULL PASSES (the rule cannot separate strategy from universe)")
    else:
        print(f"  VERDICT [{kind}]: NULL FAILS")


def cmd_null_sleeve(args: argparse.Namespace) -> int:
    try:
        conn = _open_readonly(args.ledger)
        try:
            run = _read_run(conn, args.run)
            tests = _read_tests(conn, args.run) if run is not None else []
        finally:
            conn.close()
    except sqlite3.Error as err:
        print(f"Cannot read ledger {args.ledger}: {err}", file=sys.stderr)
        return 2
    if run is None:
        print(f"Unknown run {args.run}", file=sys.stderr)
        return 2
    rule = run.get("pass_rule") or "standalone"
    if rule not in COMBINED_PASS_RULES:
        print(f"Run {args.run} is not a combined-rule run; refusing.", file=sys.stderr)
        return 2
    universe = load_universe(args.universe)
    tickers = list(universe["tickers"])
    try:
        combined = combined_config_for_run(
            run,
            config_path_for(rule, args.combined_config, ROOT / "config"),
            args.profile,
            args.portfolio,
            universe_tickers=tickers,
        )
    except ValueError as err:
        print(str(err), file=sys.stderr)
        return 2
    if combined is None:
        return 2
    combined_cfg, combined_hash = combined

    criteria, _ = load_criteria(args.criteria)
    fingerprint = data_source_fingerprint(args.synthetic, universe["name"], tickers)
    if run["data_source"] is None:
        print(
            f"Run {args.run} has no recorded data source; cannot verify --synthetic/--universe.",
            file=sys.stderr,
        )
    elif run["data_source"] != fingerprint:
        print(
            f"data source mismatch for run {args.run}: run started with "
            f"{run['data_source']!r}, got {fingerprint!r}",
            file=sys.stderr,
        )
        return 2

    needed = set(tickers) | set(DEFAULT_UNIVERSE_TICKERS) | set(criteria["benchmarks"])
    needed |= set(core_tickers(combined_cfg["core"]))
    data = SearchData.load(sorted(needed), synthetic=args.synthetic)

    print(f"Null-sleeve control, run {args.run} (combined config hash {combined_hash})")
    print("Diagnostic only: nothing is recorded in the ledger.")
    for kind in NULL_KINDS:
        _run_kind(kind, tickers, data, criteria, combined_cfg, tests)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--run", type=int, required=True)
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--ledger", default=str(ROOT / DEFAULT_LEDGER_PATH))
    ap.add_argument("--criteria", default=str(ROOT / "config" / "criteria.yaml"))
    ap.add_argument("--universe", default=str(ROOT / "config" / "universe.yaml"))
    # Default: config/combined.yaml or config/combined_null.yaml per pass rule.
    ap.add_argument("--combined-config", default=None)
    ap.add_argument("--profile", default=str(ROOT / "config" / "profile.yaml"))
    ap.add_argument("--portfolio", default=str(ROOT / "config" / "portfolio.yaml"))
    ap.set_defaults(func=cmd_null_sleeve)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
