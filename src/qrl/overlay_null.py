"""Random-signal null for the macro overlay (spec:
docs/methodology/macro-overlay.md). For each signal, its on and off spells
are shuffled into random order. The alternation pattern, the fraction of time
on and every spell length are kept, so turnover is roughly matched. The
shuffled states then go through the same cap, month-end hold and engine as the
real overlay. Fixed seed from config/overlay.yaml.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .engine import run_backtest
from .metrics import compute_metrics
from .overlay import OverlayConfig, overlay_weights
from .periods import period_bounds, slice_period


def shuffle_spells(states: pd.Series, rng: np.random.Generator) -> pd.Series:
    """Reorder a 0/1 series' on spells among themselves and its off spells
    among themselves, keeping the alternation (and the first spell's state).
    NaN positions (undefined: warm-up or missing input) stay where they are."""
    defined = states.dropna()
    values = defined.to_numpy(dtype=float)
    if len(values) == 0:
        return states.copy()
    change = np.flatnonzero(np.diff(values)) + 1
    bounds = np.concatenate([[0], change, [len(values)]])
    lengths, kinds = np.diff(bounds), values[bounds[:-1]]
    on_iter = iter(rng.permutation(lengths[kinds == 1]))
    off_iter = iter(rng.permutation(lengths[kinds == 0]))
    spells = [np.full(next(on_iter) if k == 1 else next(off_iter), k) for k in kinds]
    out = states.astype(float)
    out.loc[defined.index] = np.concatenate(spells)
    return out


def shuffle_states(
    monthly: pd.DataFrame, rng: np.random.Generator, start: pd.Timestamp
) -> pd.DataFrame:
    """Shuffle every signal column independently over month ends >= `start`;
    earlier rows are unchanged. Returns 0/1 floats (the signal layer's bool
    states are converted)."""
    out = monthly.astype(float)
    window = out.index >= start
    for col in out.columns:
        out.loc[window, col] = shuffle_spells(out.loc[window, col], rng).to_numpy()
    return out


def _governing_start(index: pd.Index, criteria: dict, period: str) -> pd.Timestamp:
    """The last month end before the period starts: its weights are the ones
    held on the period's first days."""
    start, _ = period_bounds(criteria, period)
    before = index[index < start] if start is not None else index[:0]
    return pd.Timestamp(before[-1] if len(before) else index[0])


def null_improvements(
    monthly: pd.DataFrame,
    open_: pd.DataFrame,
    close: pd.DataFrame,
    cfg: OverlayConfig,
    criteria: dict,
    period: str,
    g_sharpe: float,
) -> np.ndarray:
    """Sharpe minus `g_sharpe` over `period` for `cfg.null_draws` shuffled
    overlays (seed `cfg.null_seed`). Callers pass frames already cut at the
    period end; `slice_period` keeps the holdout sealed."""
    rng = np.random.default_rng(cfg.null_seed)
    start = _governing_start(monthly.index, criteria, period)
    out = np.empty(cfg.null_draws)
    for i in range(cfg.null_draws):
        weights = overlay_weights(shuffle_states(monthly, rng, start), close, cfg)
        returns = run_backtest(open_, close, weights, cost_bps=cfg.cost_bps).returns
        out[i] = compute_metrics(slice_period(returns, criteria, period))["sharpe"] - g_sharpe
    return out
