"""Load the locked criteria file and evaluate metrics against it."""
from __future__ import annotations

import hashlib
from pathlib import Path

import yaml


def load_criteria(path: str | Path) -> tuple[dict, str]:
    raw = Path(path).read_bytes()
    return yaml.safe_load(raw), hashlib.sha256(raw).hexdigest()[:12]


def evaluate(metrics: dict, benchmark_metrics: dict | None, criteria: dict) -> list[dict]:
    rules = criteria["pass"]
    checks = [
        {
            "rule": "Enough trades",
            "value": metrics.get("trades"),
            "threshold": f">= {rules['min_trades']}",
            "passed": (metrics.get("trades") or 0) >= rules["min_trades"],
        },
        {
            "rule": "Sharpe ratio",
            "value": round(metrics["sharpe"], 2),
            "threshold": f">= {rules['min_sharpe']}",
            "passed": metrics["sharpe"] >= rules["min_sharpe"],
        },
        {
            "rule": "Max drawdown",
            "value": round(metrics["max_drawdown"], 3),
            "threshold": f"<= {rules['max_drawdown']}",
            "passed": metrics["max_drawdown"] <= rules["max_drawdown"],
        },
    ]
    if benchmark_metrics:
        key = rules["beat_on"]
        checks.append({
            "rule": f"Beats {rules['beat_benchmark']} on {key}",
            "value": round(metrics[key], 3),
            "threshold": f"> {round(benchmark_metrics[key], 3)}",
            "passed": metrics[key] > benchmark_metrics[key],
        })
    return checks
