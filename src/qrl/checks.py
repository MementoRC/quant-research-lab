"""Guardrails that any strategy, human- or AI-written, must pass."""

from __future__ import annotations

import numpy as np
import pandas as pd


def assert_causal(weights_fn, close: pd.DataFrame, n_cuts: int = 12, seed: int = 0) -> None:
    """Fail if a strategy's weights at day t change when data AFTER day t changes.

    At several cut points, the future is replaced with a crash (prices x0.6) and a
    boom (prices x1.6). Weights up to and including the cut must be identical in
    both scenarios; otherwise the strategy is peeking ahead.
    """
    rng = np.random.default_rng(seed)
    base = weights_fn(close)
    lo, hi = len(close) // 3, len(close) - 2
    for cut in sorted(rng.integers(lo, hi, size=n_cuts)):
        for factor in (0.6, 1.6):
            tampered = close.copy()
            tampered.iloc[cut + 1 :] = tampered.iloc[cut + 1 :] * factor
            altered = weights_fn(tampered)
            a = base.iloc[: cut + 1].fillna(-1.0)
            b = altered.iloc[: cut + 1].fillna(-1.0)
            diff = (a != b).any(axis=1)
            if diff.any():
                raise AssertionError(
                    f"Look-ahead detected: weights on {diff[diff].index[0].date()} changed "
                    f"when only data after {close.index[cut].date()} was altered."
                )
