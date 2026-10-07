"""Macro overlay evaluation (spec: docs/methodology/macro-overlay.md): the
pass rule versus static G, the research trial with its spell-shuffle null,
the validation and holdout results, and the markdown report. Pure functions:
frames are cut at the period end BEFORE any weights are built, and the
holdout is only ever sliced by the caller, through `qrl.holdout.unseal`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .engine import run_backtest
from .metrics import compute_metrics
from .overlay import OverlayConfig, monthly_states, overlay_weights
from .overlay_null import null_improvements
from .periods import period_bounds, slice_period
from .strategies.core_mix import core_mix


def evaluate_pass(
    overlay: dict, base: dict, cfg: OverlayConfig, null: np.ndarray | None = None
) -> list[dict]:
    """Checks of overlay-G vs static G; the null check only when `null` is given."""
    gain = overlay["sharpe"] - base["sharpe"]
    checks = [
        {
            "rule": "Sharpe vs G",
            "value": round(overlay["sharpe"], 3),
            "threshold": f">= {base['sharpe'] + cfg.min_sharpe_gain:.3f}",
            "passed": overlay["sharpe"] >= base["sharpe"] + cfg.min_sharpe_gain,
        },
        {
            "rule": "Max drawdown vs G",
            "value": round(overlay["max_drawdown"], 4),
            "threshold": f"<= {base['max_drawdown']:.4f}",
            "passed": overlay["max_drawdown"] <= base["max_drawdown"],
        },
        {
            "rule": "CAGR vs G",
            "value": round(overlay["cagr"], 4),
            "threshold": f">= {base['cagr'] - cfg.max_cagr_shortfall:.4f}",
            "passed": overlay["cagr"] >= base["cagr"] - cfg.max_cagr_shortfall,
        },
    ]
    if null is not None:
        p = float(np.percentile(null, cfg.null_percentile))
        checks.append(
            {
                "rule": f"Sharpe gain vs null p{cfg.null_percentile:g}",
                "value": round(gain, 3),
                "threshold": f"> {p:.3f}",
                "passed": gain > p,
            }
        )
    return checks


def step_returns(
    open_: pd.DataFrame, close: pd.DataFrame, cpi: pd.Series, cfg: OverlayConfig
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(daily net returns of overlay-G and static G on their common days,
    month-end states). Same engine, same cost."""
    monthly = monthly_states(close, cpi, cfg)
    overlay = run_backtest(open_, close, overlay_weights(monthly, close, cfg), cost_bps=cfg.cost_bps)
    base = run_backtest(open_, close, core_mix(close, risk_on=cfg.base), cost_bps=cfg.cost_bps)
    returns = pd.DataFrame({"overlay": overlay.returns, "G": base.returns}).dropna()
    return returns, monthly


def _result(overlay: dict, base: dict, checks: list[dict]) -> dict:
    return {
        "window": [overlay["start"], overlay["end"]],
        "overlay": overlay,
        "G": base,
        "sharpe_gain": overlay["sharpe"] - base["sharpe"],
        "checks": checks,
        "passed": all(c["passed"] for c in checks),
    }


def window_result(window: pd.DataFrame, cfg: OverlayConfig) -> dict:
    """Both portfolios over an already-sliced window: the three thresholds, no null."""
    if len(window) < 2:
        raise ValueError("the window has fewer than 2 return days")
    overlay, base = compute_metrics(window["overlay"]), compute_metrics(window["G"])
    return _result(overlay, base, evaluate_pass(overlay, base, cfg))


def _first_on(states: pd.Series) -> str:
    """The first month end at which the signal is on (states are bool: an
    undefined signal is off, so "defined from" is not observable here)."""
    on = states[states]
    return "never" if on.empty else str(pd.Timestamp(on.index[0]).date())


def research_result(
    open_: pd.DataFrame, close: pd.DataFrame, cpi: pd.Series, cfg: OverlayConfig, criteria: dict
) -> dict:
    """The one research trial: three thresholds plus the null."""
    _, end = period_bounds(criteria, "research")
    open_, close, cpi = open_.loc[:end], close.loc[:end], cpi.loc[:end]
    returns, monthly = step_returns(open_, close, cpi, cfg)
    window = slice_period(returns, criteria, "research")
    if len(window) < 2:
        raise ValueError("the research window has fewer than 2 return days")
    overlay, base = compute_metrics(window["overlay"]), compute_metrics(window["G"])
    null = null_improvements(monthly, open_, close, cfg, criteria, "research", base["sharpe"])
    out = _result(overlay, base, evaluate_pass(overlay, base, cfg, null))
    out["null"] = {
        "draws": cfg.null_draws,
        "seed": cfg.null_seed,
        "percentile": cfg.null_percentile,
        "threshold": float(np.percentile(null, cfg.null_percentile)),
        "mean": float(null.mean()),
    }
    out["signal_live_from"] = {c: _first_on(monthly[c]) for c in monthly.columns}
    return out


def validation_result(
    open_: pd.DataFrame, close: pd.DataFrame, cpi: pd.Series, cfg: OverlayConfig, criteria: dict
) -> dict:
    """2019-2022 vs static G, three thresholds, no null. VALIDATION-SEEN."""
    _, end = period_bounds(criteria, "validation")
    returns, _ = step_returns(open_.loc[:end], close.loc[:end], cpi.loc[:end], cfg)
    return window_result(slice_period(returns, criteria, "validation"), cfg)


def holdout_returns(
    open_: pd.DataFrame, close: pd.DataFrame, cpi: pd.Series, cfg: OverlayConfig
) -> pd.DataFrame:
    """Full-history returns of both portfolios. The CALLER slices the holdout,
    and only through `qrl.holdout.unseal`."""
    return step_returns(open_, close, cpi, cfg)[0]
