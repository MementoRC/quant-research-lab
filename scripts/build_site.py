"""Run all configured strategies and benchmarks, then write site/data/results.json.

Usage:
    python scripts/build_site.py              # real data from Yahoo (cached)
    python scripts/build_site.py --refresh    # re-download prices
    python scripts/build_site.py --synthetic  # offline random-walk demo data
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qrl.criteria import evaluate, load_criteria  # noqa: E402
from qrl.data import load_prices, synthetic_prices  # noqa: E402
from qrl.engine import run_backtest  # noqa: E402
from qrl.metrics import compute_metrics, drawdown  # noqa: E402
from qrl.periods import PERIOD_NAMES, slice_period  # noqa: E402
from qrl.strategies import REGISTRY  # noqa: E402


def _round(x, nd=6):
    return None if x is None or pd.isna(x) else round(float(x), nd)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "site" / "data" / "results.json"))
    args = ap.parse_args()

    criteria, criteria_hash = load_criteria(ROOT / "config" / "criteria.yaml")
    configs = yaml.safe_load((ROOT / "config" / "strategies.yaml").read_text())["strategies"]
    cost_bps = criteria["costs"]["bps_per_unit_turnover"]

    runs = [dict(c, kind="strategy") for c in configs]
    for b in criteria["benchmarks"]:
        runs.append(
            {
                "id": f"bh_{b.lower()}",
                "name": f"{b} buy and hold",
                "fn": "buy_and_hold",
                "params": {"ticker": b},
                "kind": "benchmark",
            }
        )

    tickers = sorted({t for r in runs for t in REGISTRY[r["fn"]].tickers(r["params"])})
    if args.synthetic:
        open_, close = synthetic_prices(tickers)
    else:
        open_, close = load_prices(tickers, refresh=args.refresh)

    results = {}
    for r in runs:
        spec = REGISTRY[r["fn"]]
        cols = spec.tickers(r["params"])
        target = spec.weights(close[cols], **r["params"])
        results[r["id"]] = run_backtest(open_[cols], close[cols], target, cost_bps=cost_bps)

    # Compare everything over the same window.
    common_start = max(res.returns.index[0] for res in results.values())
    common_end = min(res.returns.index[-1] for res in results.values())

    def window(res):
        return (
            res.returns.loc[common_start:common_end],
            res.turnover.loc[common_start:common_end],
            res.executed.loc[common_start:common_end],
        )

    period_metrics = {}
    for r in runs:
        ret, turn, ex = window(results[r["id"]])
        pm = {"full": compute_metrics(ret, turn, ex)}
        for name in PERIOD_NAMES:
            # Fixed baselines are never searched or tuned, so showing their holdout
            # does not leak anything. Searched candidates (Phase 2) must not do this.
            sliced = slice_period(ret, criteria, name, unseal_holdout=True)
            if len(sliced) > 20:
                pm[name] = compute_metrics(sliced, turn, ex)
        period_metrics[r["id"]] = pm

    bench_id = f"bh_{criteria['pass']['beat_benchmark'].lower()}"
    out_strats = []
    for r in runs:
        res = results[r["id"]]
        pm = period_metrics[r["id"]]
        checks = {}
        if r["kind"] == "strategy":
            for name in ("full",) + PERIOD_NAMES:
                if name in pm and name in period_metrics[bench_id]:
                    checks[name] = evaluate(pm[name], period_metrics[bench_id][name], criteria)

        target = res.target.dropna()
        last = target.iloc[-1]
        changed = (target != target.shift(1)).any(axis=1)
        since = changed[changed].index[-1] if changed.iloc[1:].any() else target.index[0]
        out_strats.append(
            {
                "id": r["id"],
                "name": r["name"],
                "kind": r["kind"],
                "fn": r["fn"],
                "params": r["params"],
                "metrics": {
                    k: {kk: (_round(vv) if isinstance(vv, float) else vv) for kk, vv in v.items()}
                    for k, v in pm.items()
                },
                "checks": checks,
                "current": {
                    "decided_on": target.index[-1].strftime("%Y-%m-%d"),
                    "weights": {k: _round(v, 4) for k, v in last.items() if v > 0},
                    "since": since.strftime("%Y-%m-%d"),
                },
            }
        )

    # Weekly series keep the JSON small; drawdown keeps each week's worst point.
    series = {"dates": None, "equity": {}, "drawdown": {}}
    for r in runs:
        ret, _, _ = window(results[r["id"]])
        eq = (1 + ret).cumprod().resample("W-FRI").last()
        dd = drawdown(ret).resample("W-FRI").min()
        series["dates"] = [d.strftime("%Y-%m-%d") for d in eq.index]
        series["equity"][r["id"]] = [_round(v, 4) for v in eq]
        series["drawdown"][r["id"]] = [_round(v, 4) for v in dd]

    payload = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data_source": "synthetic" if args.synthetic else "yahoo",
        "data_through": close.dropna(how="all").index[-1].strftime("%Y-%m-%d"),
        "window": {
            "start": common_start.strftime("%Y-%m-%d"),
            "end": common_end.strftime("%Y-%m-%d"),
        },
        "criteria_hash": criteria_hash,
        "criteria": criteria,
        "strategies": out_strats,
        "series": series,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, separators=(",", ":"), default=str))
    print(
        f"Wrote {out} ({out.stat().st_size / 1024:.0f} KB), data through {payload['data_through']}"
    )
    for s in out_strats:
        f = s["metrics"]["full"]
        print(
            f"  {s['name']:<60} CAGR {f['cagr']:6.1%}  Sharpe {f['sharpe']:.2f}  "
            f"MaxDD {f['max_drawdown']:6.1%}  trades {f.get('trades')}"
        )


if __name__ == "__main__":
    main()
