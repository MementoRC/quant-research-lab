"""The pre-registered "combined" pass rule (PLAN.md 2.5, amendment
2026-10-01): a sleeve candidate passes if adding it as the sleeve share of the
profile's capital split, next to the configured core, improves the combined
portfolio relative to the core alone at 100% of capital.

Opt-in per run (`runs.pass_rule = 'combined'`, run 4 onward). Thresholds live
in `config/combined.yaml`, outside the locked `config/criteria.yaml`, for the
same reason `config/validation.yaml` does. `load_combined_config` hashes that
file's raw bytes together with a canonical JSON of the capital split and the
core spec actually used, so a silent change to either trips the run's guard
(`Ledger.record_test`).

Pure library code: every backtest goes through `qrl.engine.run_backtest` and
every metric through `qrl.metrics.compute_metrics`, with the same costs and
period slicing (`qrl.periods.slice_period`) as the standalone path. The
holdout is refused outright, exactly like `qrl.search.evaluate_candidate`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import yaml

from .engine import run_backtest
from .metrics import compute_metrics
from .periods import slice_period
from .portfolio import combine_portfolio, load_portfolio_config
from .strategies import REGISTRY, SLEEVE_REGISTRY

PASS_RULES = ("standalone", "combined")

_ALL_SPECS = {**REGISTRY, **SLEEVE_REGISTRY}
_REQUIRED_KEYS = {
    "sleeve_min_trades",
    "min_sharpe_improvement",
    "max_drawdown",
    "drawdown_no_worse_than_core",
    "max_cagr_shortfall",
    "rank_by",
}


def load_combined_config(
    path: str | Path, profile_path: str | Path, portfolio_path: str | Path
) -> tuple[dict, str]:
    """Load `config/combined.yaml` plus the capital split
    (`profile.yaml`'s `capital_split`) and core spec (`portfolio.yaml`'s
    `core` fn/params) it is judged against.

    Returns `(cfg, hash)`. `cfg` is the YAML mapping with two added keys,
    `capital_split` and `core`. The 12-character hash covers the YAML's raw
    bytes plus a canonical JSON of that capital split and core, so editing
    any of the three is visible to the run guard.
    """
    raw = Path(path).read_bytes()
    cfg = yaml.safe_load(raw)
    if not isinstance(cfg, dict) or not _REQUIRED_KEYS.issubset(cfg):
        raise ValueError(f"{path}: expected a mapping with {sorted(_REQUIRED_KEYS)}.")
    profile = yaml.safe_load(Path(profile_path).read_text())
    split = profile["capital_split"]
    capital_split = {"core": float(split["core"]), "sleeve": float(split["sleeve"])}
    core_cfg = load_portfolio_config(portfolio_path)["core"]
    core = {"fn": core_cfg["fn"], "params": dict(core_cfg["params"])}
    bound = json.dumps(
        {"capital_split": capital_split, "core": core}, sort_keys=True, separators=(",", ":")
    )
    digest = hashlib.sha256(raw + b"\n" + bound.encode("utf-8")).hexdigest()[:12]
    return {**cfg, "capital_split": capital_split, "core": core}, digest


def combined_config_for_run(
    run: dict,
    path: str | Path,
    profile_path: str | Path,
    portfolio_path: str | Path,
) -> tuple[dict, str] | None:
    """`(cfg, hash)` for a combined-rule run (a `Ledger.list_runs` row), or
    None for a standalone one (`pass_rule` 'standalone' or NULL). Raises
    `ValueError` if the current combined config hash differs from the one
    the run was seeded with -- the scripts refuse to continue on that,
    mirroring the criteria-hash guard."""
    if (run.get("pass_rule") or "standalone") != "combined":
        return None
    cfg, digest = load_combined_config(path, profile_path, portfolio_path)
    if digest != run.get("combined_config_hash"):
        raise ValueError(
            f"Combined config hash has changed since run {run.get('run_id')} started "
            f"({run.get('combined_config_hash')!r} -> {digest!r}); refusing to continue."
        )
    return cfg, digest


def core_tickers(core: dict) -> list[str]:
    """Tickers a `{fn, params}` core spec trades (so callers can load them)."""
    return list(_ALL_SPECS[core["fn"]].tickers(core["params"]))


def build_core_weights(core: dict, close: pd.DataFrame) -> tuple[list[str], pd.DataFrame]:
    """The core strategy's tickers and target weights from a `{fn, params}`
    spec (e.g. `config/portfolio.yaml`'s `core`). Shared with
    `scripts/build_site.py`, so the dashboard and the combined rule build the
    core identically."""
    tickers = _ALL_SPECS[core["fn"]].tickers(core["params"])
    kwargs = {k: v for k, v in core["params"].items() if k != "tickers"}
    return tickers, _ALL_SPECS[core["fn"]].weights(close[tickers], **kwargs)


def combined_checks(
    combined_metrics: dict, core_metrics: dict, sleeve_trades: int, cfg: dict
) -> list[dict]:
    """Grade combined vs core-alone metrics against `cfg`. Each check's
    `rule` is its failure code."""
    comb_sharpe, core_sharpe = combined_metrics["sharpe"], core_metrics["sharpe"]
    comb_dd, core_dd = combined_metrics["max_drawdown"], core_metrics["max_drawdown"]
    comb_cagr, core_cagr = combined_metrics["cagr"], core_metrics["cagr"]
    sharpe_floor = core_sharpe + cfg["min_sharpe_improvement"]
    cagr_floor = core_cagr - cfg["max_cagr_shortfall"]
    checks = [
        {
            "rule": "sleeve_min_trades",
            "value": sleeve_trades,
            "threshold": f">= {cfg['sleeve_min_trades']}",
            "passed": sleeve_trades >= cfg["sleeve_min_trades"],
        },
        {
            "rule": "combined_sharpe_improvement",
            "value": round(comb_sharpe, 3),
            "threshold": f">= {round(sharpe_floor, 3)}",
            "passed": comb_sharpe >= sharpe_floor,
        },
        {
            "rule": "combined_max_drawdown",
            "value": round(comb_dd, 3),
            "threshold": f"<= {cfg['max_drawdown']}",
            "passed": comb_dd <= cfg["max_drawdown"],
        },
    ]
    if cfg["drawdown_no_worse_than_core"]:
        checks.append(
            {
                "rule": "combined_drawdown_vs_core",
                "value": round(comb_dd, 3),
                "threshold": f"<= {round(core_dd, 3)}",
                "passed": comb_dd <= core_dd,
            }
        )
    checks.append(
        {
            "rule": "combined_cagr_shortfall",
            "value": round(comb_cagr, 4),
            "threshold": f">= {round(cagr_floor, 4)}",
            "passed": comb_cagr >= cagr_floor,
        }
    )
    return checks


def _sleeve_trades(
    sleeve_weights: pd.DataFrame,
    open_: pd.DataFrame,
    close: pd.DataFrame,
    criteria: dict,
    period: str,
    cost_bps: float,
) -> int:
    cols = list(sleeve_weights.columns)
    sliced = slice_period(sleeve_weights, criteria, period)
    result = run_backtest(open_[cols], close[cols], sliced, cost_bps=cost_bps)
    return int(compute_metrics(result.returns, result.turnover, result.executed).get("trades", 0))


def combined_evaluation(
    sleeve_weights: pd.DataFrame,
    open_: pd.DataFrame,
    close: pd.DataFrame,
    core: dict,
    capital_split: dict[str, float],
    criteria: dict,
    cfg: dict,
    *,
    period: str = "research",
    sleeve_trades: int | None = None,
) -> dict:
    """Backtest core + sleeve (via `combine_portfolio`) and the core alone at
    100% on `period`, with criteria.yaml's costs and the engine's timing, and
    grade the pair with `combined_checks`.

    `sleeve_weights` are the candidate's full-history target weights (the
    period slice happens here). `sleeve_trades` is the candidate's standalone
    trade count if the caller already has it; otherwise the sleeve is
    backtested alone to count it.

    Both return series are compared on their common dates. Returns
    `combined_metrics`, `core_metrics`, `combined_returns`, `core_returns`,
    `improvement` (combined minus core-alone daily returns),
    `improvement_sharpe` (annualised by `compute_metrics`), `sleeve_trades`,
    `checks`, `passed`, and `failure_reasons` (comma-joined codes or None).
    """
    if period == "holdout":
        raise ValueError("combined_evaluation refuses period='holdout'; the holdout stays sealed.")
    cost_bps = criteria["costs"]["bps_per_unit_turnover"]
    core_tickers, core_weights = build_core_weights(core, close)
    pw = combine_portfolio(core_weights, [sleeve_weights], capital_split)
    cols = list(pw.combined.columns)
    combined = run_backtest(
        open_[cols], close[cols], slice_period(pw.combined, criteria, period), cost_bps=cost_bps
    )
    core_alone = run_backtest(
        open_[core_tickers],
        close[core_tickers],
        slice_period(core_weights, criteria, period),
        cost_bps=cost_bps,
    )
    common = combined.returns.index.intersection(core_alone.returns.index)
    combined_returns = combined.returns.loc[common]
    core_returns = core_alone.returns.loc[common]
    combined_metrics = compute_metrics(combined_returns, combined.turnover, combined.executed)
    core_metrics = compute_metrics(core_returns, core_alone.turnover, core_alone.executed)
    improvement = combined_returns - core_returns
    improvement_sharpe = float(compute_metrics(improvement).get("sharpe", 0.0))
    if sleeve_trades is None:
        sleeve_trades = _sleeve_trades(sleeve_weights, open_, close, criteria, period, cost_bps)

    checks = combined_checks(combined_metrics, core_metrics, sleeve_trades, cfg)
    failed = [c["rule"] for c in checks if not c["passed"]]
    return {
        "combined_metrics": combined_metrics,
        "core_metrics": core_metrics,
        "combined_returns": combined_returns,
        "core_returns": core_returns,
        "improvement": improvement,
        "improvement_sharpe": improvement_sharpe,
        "sleeve_trades": sleeve_trades,
        "checks": checks,
        "passed": not failed,
        "failure_reasons": ",".join(failed) if failed else None,
    }
