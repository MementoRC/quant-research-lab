"""Report sleeve-universe price coverage and macro-series availability, and
write site/data/universe_coverage.json for the dashboard build.

Usage:
    python scripts/data_check.py              # real data from Yahoo + FRED (cached)
    python scripts/data_check.py --refresh    # re-download prices and macro series
    python scripts/data_check.py --synthetic  # offline random-walk demo data, no macro fetch
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
from qrl.data import coverage_report, load_prices, synthetic_prices  # noqa: E402
from qrl.macro import load_macro  # noqa: E402
from qrl.periods import period_bounds  # noqa: E402
from qrl.universe import load_universe  # noqa: E402


def _research_start() -> pd.Timestamp:
    criteria, _ = load_criteria(ROOT / "config" / "criteria.yaml")
    start, _ = period_bounds(criteria, "research")
    return start


def _print_banner(universe: dict) -> None:
    if universe.get("survivorship_biased"):
        print("=" * 70)
        print(f"SURVIVORSHIP-BIASED UNIVERSE: {universe['name']} (as_of {universe['as_of']})")
        print("Free data only sees tickers that still trade today; delisted or")
        print("acquired names from the research period are silently absent.")
        print("=" * 70)


def _coverage_summary(cov: pd.DataFrame, research_start: pd.Timestamp) -> dict:
    late = cov[cov["first_date"] > research_start]
    ended_early = cov[cov["ended_early"]]
    worst = cov.sort_values("missing_pct", ascending=False).head(5)
    return {
        "late_starters": sorted(late.index.tolist()),
        "ended_early": sorted(ended_early.index.tolist()),
        "worst_missing_pct": [
            {"ticker": t, "missing_pct": round(float(row["missing_pct"]), 4)}
            for t, row in worst.iterrows()
        ],
    }


def _ticker_rows(cov: pd.DataFrame) -> dict:
    def _date(v):
        return None if pd.isna(v) else v.strftime("%Y-%m-%d")

    return {
        t: {
            "first_date": _date(row["first_date"]),
            "last_date": _date(row["last_date"]),
            "n_bars": int(row["n_bars"]),
            "missing_pct": round(float(row["missing_pct"]), 4),
            "gaps": int(row["gaps"]),
            "ended_early": bool(row["ended_early"]),
        }
        for t, row in cov.iterrows()
    }


def _macro_summary(close: pd.DataFrame, refresh: bool) -> dict:
    macro = load_macro(trading_index=close.index, refresh=refresh)
    summary = {}
    print("Macro series (aligned to the trading calendar):")
    for col in macro.columns:
        s = macro[col].dropna()
        first = s.index[0].strftime("%Y-%m-%d") if not s.empty else None
        last = s.index[-1].strftime("%Y-%m-%d") if not s.empty else None
        print(f"  {col:<16} first {first}  last {last}  n {len(s)}")
        summary[col] = {"first": first, "last": last, "n": int(len(s))}
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--universe", default=str(ROOT / "config" / "universe.yaml"))
    ap.add_argument("--out", default=str(ROOT / "site" / "data" / "universe_coverage.json"))
    args = ap.parse_args(argv)

    universe = load_universe(args.universe)
    tickers = universe["tickers"]
    _print_banner(universe)

    if args.synthetic:
        open_, close = synthetic_prices(tickers)
    else:
        open_, close = load_prices(tickers, refresh=args.refresh)
    loaded = sorted(close.columns)
    failed = sorted(set(tickers) - set(loaded))

    research_start = _research_start()
    # Coverage over the ticker's full loaded history (not clipped to the
    # research period): "late starter" means its real data begins after the
    # research period started (e.g. a recent IPO), which clipping first would hide.
    cov = coverage_report(open_, close)
    summary = _coverage_summary(cov, research_start)

    print(f"Universe {universe['name']}: {len(loaded)}/{len(tickers)} tickers loaded")
    if failed:
        print(f"  Failed to load: {failed}")
    print(
        f"  Started after {research_start.date()} (missing part of the research period): "
        f"{len(summary['late_starters'])} -> {summary['late_starters']}"
    )
    print(
        f"  Ended before the frame's last date (possible delisting): "
        f"{len(summary['ended_early'])} -> {summary['ended_early']}"
    )
    print("  Worst missing_pct:")
    for row in summary["worst_missing_pct"]:
        print(f"    {row['ticker']:<8} {row['missing_pct']:.1%}")

    macro_summary: dict = {}
    if args.synthetic:
        print("Macro: skipped (--synthetic)")
    else:
        macro_summary = _macro_summary(close, args.refresh)

    payload = {
        "name": universe["name"],
        "as_of": universe["as_of"],
        "survivorship_biased": universe["survivorship_biased"],
        "requested": len(tickers),
        "loaded": len(loaded),
        "failed": len(failed),
        "failed_tickers": failed,
        "late_starters": len(summary["late_starters"]),
        "ended_early": len(summary["ended_early"]),
        "tickers": _ticker_rows(cov),
        "macro": macro_summary,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, separators=(",", ":"), default=str))
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
