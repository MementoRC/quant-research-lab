"""Point-in-time size-ranked universe (Phase 4, milestone 2).

    python scripts/pit_universe.py build [--refresh] [--top-n 300] [--min-cap 2e9]
    python scripts/pit_universe.py coverage

`build` fetches the SEC exchange ticker list and companyfacts, Yahoo prices and splits
(all cached; reruns resume), ranks each month-end from 2009 and writes
config/universes/us_large_cap_pit.csv + config/universe_pit.yaml. `--refresh`
re-downloads everything. Needs a SEC contact email (env SEC_USER_AGENT_EMAIL or the
gitignored config/sec.local.yaml).

`coverage` is read-only apart from the report: it reads the tracked membership plus the
feature cache `build` left in data/cache/pit/ and writes research/pit_coverage.txt.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qrl import pit_universe as pu  # noqa: E402
from qrl.fundamentals import SecIdentityError  # noqa: E402
from qrl.universe import load_universe  # noqa: E402

REPORT_PATH = ROOT / "research" / "pit_coverage.txt"


def _log(msg: str) -> None:
    print(msg, flush=True)


def cmd_build(args: argparse.Namespace) -> int:
    try:
        diag = pu.run_build(args.top_n, args.min_cap, args.refresh, _log)
    except SecIdentityError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    _log(f"no Yahoo data ({len(diag['no_yahoo_data'])}): {' '.join(diag['no_yahoo_data'][:60])}")
    _log(f"split fetch failed: {diag['split_fetch_failed']}")
    summary = {k: v for k, v in diag.items() if k not in ("no_yahoo_data", "split_fetch_failed")}
    _log(f"done: {summary}")
    return 1 if diag["split_fetch_failed"] else 0


def cmd_coverage(_: argparse.Namespace) -> int:
    meta, membership = pu.load_pit_universe(pu.UNIVERSE_PIT_PATH)
    features_path = pu.PIT_CACHE_DIR / "features.parquet"
    if not features_path.exists():
        print(f"error: {features_path} missing; run `pixi run build-pit-universe`", file=sys.stderr)
        return 2
    features = pd.read_parquet(features_path)
    today = load_universe(ROOT / "config" / "universe.yaml")["tickers"]
    table = pu.coverage_table(membership, features, today)
    text = pu.format_coverage(table, membership, today, meta)
    REPORT_PATH.write_text(text)
    print(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="fetch, rank and write the universe files")
    b.add_argument("--refresh", action="store_true")
    b.add_argument("--top-n", type=int, default=pu.DEFAULT_TOP_N)
    b.add_argument("--min-cap", type=float, default=pu.DEFAULT_MIN_CAP)
    b.set_defaults(func=cmd_build)
    c = sub.add_parser("coverage", help="per-year input coverage report (read-only)")
    c.set_defaults(func=cmd_coverage)
    args = ap.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
