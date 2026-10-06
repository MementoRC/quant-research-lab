"""Decision helper (spec: docs/methodology/decision-helper.md): a fixed set of
portfolios at 100% of capital under historical windows, judgement-based
shocks and CPI-indexed withdrawals. A decision aid: it selects nothing and
recommends nothing. Pure functions; callers inject data and configs. Every
price and CPI frame is cut at the research end (2018-12-31) before use, so
validation and holdout data never enter, and `slice_period(...,
unseal_holdout=True)` is never called.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .core_compare import candidate_weights
from .decision_config import Portfolio
from .periods import period_bounds
from .strategies import REGISTRY


def data_end(criteria: dict) -> pd.Timestamp:
    """The last date any decision computation may see: the research end."""
    _, end = period_bounds(criteria, "research")
    if end is None:
        raise ValueError("criteria research period needs an end")
    return end


def portfolio_tickers(p: Portfolio) -> list[str]:
    """Every ticker whose prices the portfolio's rules need (held funds and signals)."""
    return list(
        dict.fromkeys(t for cand, _ in p.parts for t in REGISTRY[cand.fn].tickers(cand.params))
    )


def portfolio_weights(p: Portfolio, close: pd.DataFrame) -> pd.DataFrame:
    """Daily target weights (fractions of capital): the share-weighted sum of
    the parts' weights, so a switching part keeps switching inside a blend. A
    row is NaN wherever any part's row is NaN (never zero-filled into cash)."""
    frames = [candidate_weights(cand, close) * share for cand, share in p.parts]
    cols = sorted({c for f in frames for c in f.columns})
    total = pd.DataFrame(0.0, index=close.index, columns=cols)
    for frame in frames:
        total = total + frame.reindex(columns=cols, fill_value=0.0)
    total[total.isna().any(axis=1)] = np.nan
    return total
