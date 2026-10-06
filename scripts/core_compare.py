"""Core-comparison EXPLORATION (spec:
docs/methodology/core-comparison.md). Evaluates the
pre-registered candidates in config/core_candidates.yaml on research-period
metrics and on stress cells that never touch the validation or holdout periods
(covid_2020 and inflation_2022 are computed nowhere here). Prints a table,
writes research/core_compare.md and reports/core_compare.json (gitignored).
It tunes and selects nothing and changes no config.

Usage:
    python scripts/core_compare.py
    python scripts/core_compare.py --out-json reports/core_compare.json --out-md research/core_compare.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qrl.core_compare import (  # noqa: E402
    benchmark_metrics,
    load_core_candidates,
    render_markdown,
    run_core_compare,
)
from qrl.criteria import load_criteria  # noqa: E402
from qrl.data import load_ohlcv  # noqa: E402
from qrl.periods import period_bounds  # noqa: E402
from qrl.profile import load_profile  # noqa: E402
from qrl.strategies import REGISTRY  # noqa: E402
from qrl.stress import EQUITY_PROXY, load_stress_config  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-json", default=str(ROOT / "reports" / "core_compare.json"))
    ap.add_argument("--out-md", default=str(ROOT / "research" / "core_compare.md"))
    args = ap.parse_args(argv)

    criteria, _ = load_criteria(ROOT / "config" / "criteria.yaml")
    holdout_start, _ = period_bounds(criteria, "holdout")
    rstart, rend = period_bounds(criteria, "research")
    if rstart is None or rend is None:
        raise ValueError("criteria research period needs a start and an end")
    cfg, stress_hash = load_stress_config(ROOT / "config" / "stress.yaml", holdout_start)
    profile = load_profile(ROOT / "config" / "profile.yaml")
    cands, cand_hash = load_core_candidates(ROOT / "config" / "core_candidates.yaml")

    bench = str(criteria["pass"]["beat_benchmark"])
    tickers = sorted(
        {EQUITY_PROXY, bench} | {t for c in cands for t in REGISTRY[c.fn].tickers(c.params)}
    )
    data = load_ohlcv(tickers, refresh=True)  # as scripts/stress.py
    missing = [t for t in tickers if t not in data["close"].columns]
    if missing:
        print(f"no price data for: {missing}")  # the loader drops tickers it cannot fetch
        return 1
    # every candidate ticker (signal tickers included) must be priced on the last
    # row at or before the research end, as scripts/stress.py does for the core
    last_row = data["close"].loc[:rend, tickers].iloc[-1]
    if not last_row.notna().all():
        unpriced = sorted(last_row.index[last_row.isna()])
        print(f"unpriced at the research end {rend.date()}: {unpriced}")
        return 1

    result = run_core_compare(
        cands, cfg, data, criteria, profile["capital_split"], profile["max_drawdown"]
    )
    report = {
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "candidates_file": "config/core_candidates.yaml",
        "candidates_sha256": cand_hash,
        "stress_sha256": stress_hash,
        "trial_count": len(cands),
        "research_period": {"start": str(rstart.date()), "end": str(rend.date())},
        "max_drawdown": profile["max_drawdown"],
        "capital_split": profile["capital_split"],
        **result,
        "benchmark": benchmark_metrics(
            data, criteria, profile["capital_split"], bench, profile["max_drawdown"]
        ),
    }
    out_json, out_md = Path(args.out_json), Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    markdown = render_markdown(report)
    out_json.write_text(json.dumps(report, indent=2, default=str))
    out_md.write_text(markdown)
    print(markdown)
    print(f"Wrote {out_json} and {out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
