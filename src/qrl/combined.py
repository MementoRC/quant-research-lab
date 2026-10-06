"""The pre-registered "combined" pass rule (milestone 2.5, amendment
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

Amendment 2026-10-02 (run 5): the `combined_null` ("beat the null") rule,
thresholds in `config/combined_null.yaml` (`baseline: null_equal_weight`).
Same machinery, but the baseline is core + the equal-weight null sleeve
(`qrl.controls.null_sleeve_weights`) over the run's universe in the sleeve
slot, instead of the core alone; the improvement series is candidate-combined
minus null-combined returns. Hash-bound identically. A config with no
`baseline` key is the original core-alone rule, unchanged.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

import pandas as pd
import yaml

from .controls import null_sleeve_weights
from .engine import run_backtest
from .ledger import COMBINED_PASS_RULES
from .metrics import compute_metrics
from .periods import slice_period
from .pit_universe import membership_mask
from .portfolio import combine_portfolio, load_portfolio_config
from .strategies import REGISTRY, SLEEVE_REGISTRY
from .tradability import exit_before_delisting

PASS_RULES = ("standalone", *COMBINED_PASS_RULES)
NULL_BASELINE = "null_equal_weight"
# Default config file (under config/) per combined-family pass rule.
CONFIG_FILES = {"combined": "combined.yaml", "combined_null": "combined_null.yaml"}
# Baseline label per pass rule: prefixes stored metrics (`core_*`/`null_*`)
# and names the drawdown check and its config flag.
_RULE_LABELS = {"combined": "core", "combined_null": "null"}

_ALL_SPECS = {**REGISTRY, **SLEEVE_REGISTRY}
_COMMON_KEYS = {
    "sleeve_min_trades",
    "min_sharpe_improvement",
    "max_drawdown",
    "max_cagr_shortfall",
    "rank_by",
}


def baseline_label(cfg: dict) -> str:
    """'core' (no `baseline` key: core alone at 100%) or 'null'
    (`baseline: null_equal_weight`: core + equal-weight null sleeve)."""
    baseline = cfg.get("baseline")
    if baseline is None:
        return "core"
    if baseline == NULL_BASELINE:
        return "null"
    raise ValueError(f"unknown combined baseline {baseline!r}; expected {NULL_BASELINE!r}")


def config_path_for(rule: str, override: str | Path | None, config_dir: str | Path) -> Path:
    """`override` if given, else `config_dir`'s default file for `rule`
    (combined.yaml for anything that is not combined_null)."""
    if override:
        return Path(override)
    return Path(config_dir) / CONFIG_FILES.get(rule, CONFIG_FILES["combined"])


def load_combined_config(
    path: str | Path, profile_path: str | Path, portfolio_path: str | Path
) -> tuple[dict, str]:
    """Load `config/combined.yaml` plus the capital split
    (`profile.yaml`'s `capital_split`) and core spec (`portfolio.yaml`'s
    `core` fn/params) it is judged against.

    Returns `(cfg, hash)`. `cfg` is the YAML mapping with two added keys,
    `capital_split` and `core`. The 12-character hash covers the YAML's raw
    bytes plus a canonical JSON of that capital split and core, so editing
    any of the three is visible to the run guard. Also loads
    `config/combined_null.yaml` (`baseline: null_equal_weight`, whose drawdown
    flag is `drawdown_no_worse_than_null`).
    """
    raw = Path(path).read_bytes()
    cfg = yaml.safe_load(raw)
    if not isinstance(cfg, dict):
        raise ValueError(f"{path}: expected a mapping.")
    required = _COMMON_KEYS | {f"drawdown_no_worse_than_{baseline_label(cfg)}"}
    if not required.issubset(cfg):
        raise ValueError(f"{path}: expected a mapping with {sorted(required)}.")
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
    *,
    universe_tickers: Sequence[str] | None = None,
    null_membership: pd.DataFrame | None = None,
) -> tuple[dict, str] | None:
    """`(cfg, hash)` for a combined-family run (a `Ledger.list_runs` row), or
    None for a standalone one (`pass_rule` 'standalone' or NULL). Raises
    `ValueError` if the current combined config hash differs from the one
    the run was seeded with -- the scripts refuse to continue on that,
    mirroring the criteria-hash guard.

    A `combined_null` run needs `universe_tickers` (the run's universe; its
    data-source fingerprint binds them): they are added to `cfg` as
    `null_tickers`, the null sleeve's tickers. A factor run also passes
    `null_membership` (its point-in-time membership table), added as
    `null_membership`: the null then holds only each day's members. Neither
    key is part of the config hash (the yaml, split and core are); a factor
    run binds the membership by its own hash (`qrl.factor_run`)."""
    rule = run.get("pass_rule") or "standalone"
    if rule not in COMBINED_PASS_RULES:
        return None
    cfg, digest = load_rule_config(rule, path, profile_path, portfolio_path)
    if digest != run.get("combined_config_hash"):
        raise ValueError(
            f"Combined config hash has changed since run {run.get('run_id')} started "
            f"({run.get('combined_config_hash')!r} -> {digest!r}); refusing to continue."
        )
    if baseline_label(cfg) == "null":
        if not universe_tickers:
            raise ValueError(f"run {run.get('run_id')} (combined_null) needs universe tickers.")
        cfg = {**cfg, "null_tickers": list(universe_tickers)}
        if null_membership is not None:
            cfg["null_membership"] = null_membership
    return cfg, digest


def load_rule_config(
    rule: str, path: str | Path, profile_path: str | Path, portfolio_path: str | Path
) -> tuple[dict, str]:
    """`load_combined_config`, refusing a file whose `baseline` does not
    match `rule` (e.g. combined.yaml for a combined_null run)."""
    cfg, digest = load_combined_config(path, profile_path, portfolio_path)
    if baseline_label(cfg) != _RULE_LABELS[rule]:
        raise ValueError(
            f"{path}: baseline {cfg.get('baseline')!r} does not match pass rule {rule!r}."
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
    """Grade combined vs baseline metrics against `cfg`. `core_metrics` is
    the baseline's: core alone, or core + null sleeve for a
    `baseline: null_equal_weight` cfg (drawdown check/flag then named
    `..._null`). Each check's `rule` is its failure code."""
    label = baseline_label(cfg)
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
    if cfg[f"drawdown_no_worse_than_{label}"]:
        checks.append(
            {
                "rule": f"combined_drawdown_vs_{label}",
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


def null_baseline_sleeve(
    open_: pd.DataFrame,
    close: pd.DataFrame,
    tickers: Sequence[str],
    membership: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """The combined_null baseline's sleeve: the equal-weight null over
    `tickers`, with the same delisting exits a candidate gets in
    `qrl.search.evaluate_candidate` (and `scripts/null_sleeve.py` applies).

    `membership` (a `qrl.pit_universe` long table; factor runs only) makes it
    the equal weight of each day's point-in-time members among `tickers` --
    the factor-run reading of "the same universe" (Phase 4)."""
    cols = list(tickers)
    mask = None if membership is None else membership_mask(membership, close.index, cols)
    weights = null_sleeve_weights(close, cols, "equal_weight", member_mask=mask)
    return exit_before_delisting(weights, open_[cols], close[cols])


def _baseline_weights(
    core_weights: pd.DataFrame,
    core_cols: list[str],
    open_: pd.DataFrame,
    close: pd.DataFrame,
    capital_split: dict[str, float],
    cfg: dict,
) -> tuple[list[str], pd.DataFrame]:
    """Columns and full-history weights of the portfolio the candidate is
    graded against: the core alone, or core + null sleeve."""
    if baseline_label(cfg) == "core":
        return core_cols, core_weights
    null = null_baseline_sleeve(open_, close, cfg["null_tickers"], cfg.get("null_membership"))
    pw = combine_portfolio(core_weights, [null], capital_split)
    return list(pw.combined.columns), pw.combined


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

    With a `baseline: null_equal_weight` cfg (combined_null; needs
    `cfg["null_tickers"]`), the baseline is core + the equal-weight null
    sleeve at the same capital split instead of the core alone; its results
    are keyed `null_metrics`/`null_returns` and `improvement` is
    candidate-combined minus null-combined returns.
    """
    if period == "holdout":
        raise ValueError("combined_evaluation refuses period='holdout'; the holdout stays sealed.")
    label = baseline_label(cfg)
    cost_bps = criteria["costs"]["bps_per_unit_turnover"]
    core_tickers, core_weights = build_core_weights(core, close)
    pw = combine_portfolio(core_weights, [sleeve_weights], capital_split)
    cols = list(pw.combined.columns)
    combined = run_backtest(
        open_[cols], close[cols], slice_period(pw.combined, criteria, period), cost_bps=cost_bps
    )
    base_cols, base_weights = _baseline_weights(
        core_weights, core_tickers, open_, close, capital_split, cfg
    )
    baseline = run_backtest(
        open_[base_cols],
        close[base_cols],
        slice_period(base_weights, criteria, period),
        cost_bps=cost_bps,
    )
    common = combined.returns.index.intersection(baseline.returns.index)
    combined_returns = combined.returns.loc[common]
    base_returns = baseline.returns.loc[common]
    combined_metrics = compute_metrics(combined_returns, combined.turnover, combined.executed)
    base_metrics = compute_metrics(base_returns, baseline.turnover, baseline.executed)
    improvement = combined_returns - base_returns
    improvement_sharpe = float(compute_metrics(improvement).get("sharpe", 0.0))
    if sleeve_trades is None:
        sleeve_trades = _sleeve_trades(sleeve_weights, open_, close, criteria, period, cost_bps)

    checks = combined_checks(combined_metrics, base_metrics, sleeve_trades, cfg)
    failed = [c["rule"] for c in checks if not c["passed"]]
    return {
        "combined_metrics": combined_metrics,
        f"{label}_metrics": base_metrics,
        "combined_returns": combined_returns,
        f"{label}_returns": base_returns,
        "improvement": improvement,
        "improvement_sharpe": improvement_sharpe,
        "sleeve_trades": sleeve_trades,
        "checks": checks,
        "passed": not failed,
        "failure_reasons": ",".join(failed) if failed else None,
    }
