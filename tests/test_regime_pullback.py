"""Tests for the `regime_pullback` sleeve family: trend_pullback's own
entry/exit logic plus a universe-breadth regime gate that flattens exposure
in bad regimes. See src/qrl/strategies/regime_pullback.py for the design
rationale.
"""

from __future__ import annotations

import pandas as pd
import pytest

from qrl.checks import assert_causal
from qrl.data import synthetic_prices
from qrl.strategies import SLEEVE_REGISTRY, sample_params
from qrl.strategies.regime_pullback import regime_pullback
from qrl.strategies.trend_pullback import trend_pullback

N_SAMPLES = 8
_START, _END = "2010-01-01", "2014-12-31"


# ---------------------------------------------------------------------------
# Registry wiring
# ---------------------------------------------------------------------------


def test_regime_pullback_is_registered_in_sleeve_registry():
    assert "regime_pullback" in SLEEVE_REGISTRY
    spec = SLEEVE_REGISTRY["regime_pullback"]
    assert spec.fields == ("close",)
    assert "breadth_ma" in spec.space
    assert "breadth_min" in spec.space


# ---------------------------------------------------------------------------
# Causality, sampled across the family's parameter space (same pattern as
# tests/test_strategy_templates.py uses for the other sleeves).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "params", sample_params(SLEEVE_REGISTRY["regime_pullback"].space, N_SAMPLES, seed=5)
)
def test_regime_pullback_is_causal(params):
    _, close = synthetic_prices(["A", "B", "C"], start=_START, end=_END)
    assert_causal(lambda c: regime_pullback(c, **params), close)


def test_regime_pullback_day_t_weights_unaffected_by_future_bar():
    """A single future bar tampered forward of day t must not change day t's
    weights. This targets the breadth gate specifically: if `sma_breadth`
    were computed with a centered window, or the gate were built by shifting
    data backwards instead of using a purely trailing rolling mean, this
    would fail even though `assert_causal` above (which crashes/booms
    *every* row after the cut) might still pass by coincidence for some cuts.
    """
    _, close = synthetic_prices(["A", "B", "C"], start=_START, end="2012-12-31")
    kwargs = {
        "trend_lookback": 50,
        "short_ma": 10,
        "pullback_days": 3,
        "exit_days": 5,
        "max_positions": 3,
        "breadth_ma": 50,
        "breadth_min": 0.4,
    }
    base = regime_pullback(close, **kwargs)

    cut = 300
    tampered = close.copy()
    tampered.iloc[cut + 1] = tampered.iloc[cut + 1] * 5.0  # one future bar only

    altered = regime_pullback(tampered, **kwargs)

    pd.testing.assert_frame_equal(
        base.iloc[: cut + 1].fillna(-1.0),
        altered.iloc[: cut + 1].fillna(-1.0),
    )


def test_regime_pullback_warmup_rows_are_nan():
    _, close = synthetic_prices(["A", "B"], start="2010-01-01", end="2011-12-31")
    w = regime_pullback(close, trend_lookback=200)
    assert w.iloc[:199].isna().all().all()


# ---------------------------------------------------------------------------
# Hand-checked: the regime gate actually changes behaviour vs. plain
# trend_pullback, on the same series trend_pullback's own hand-checked test
# uses (tests/test_strategy_templates.py::test_trend_pullback_hand_checked).
# ---------------------------------------------------------------------------


def test_regime_gate_suppresses_entries_vanilla_trend_pullback_would_take():
    idx = pd.RangeIndex(12)
    close = pd.DataFrame(
        {"A": [100, 102, 104, 106, 108, 107, 106, 109, 111, 113, 112, 115]}, index=idx
    ).astype(float)

    kwargs = {
        "trend_lookback": 5,
        "short_ma": 2,
        "pullback_days": 2,
        "pullback_pct": 0.0,
        "exit_days": 3,
        "max_positions": 1,
        "capital": 1.0,
    }
    vanilla = trend_pullback(close, **kwargs)
    gated = regime_pullback(close, breadth_ma=3, breadth_min=0.5, **kwargs)

    # Vanilla trend_pullback enters on rows 5 and 10 (deep pullbacks in an
    # uptrend). On both rows this single-ticker "universe" sits exactly AT
    # its own 3-day breadth average (not strictly above it), so breadth is
    # 0.0 < 0.5 and the regime gate blocks the entry outright.
    assert vanilla.loc[5, "A"] == 1.0
    assert vanilla.loc[10, "A"] == 1.0
    assert gated.loc[5, "A"] == 0.0
    assert gated.loc[10, "A"] == 0.0
    # Warm-up prefix (driven by trend_pullback's own indicators, not the
    # breadth measure) is unchanged.
    assert gated.iloc[:4].isna().all().all()


def test_regime_pullback_force_exits_a_held_position_and_does_not_auto_resume():
    """A held name must be force-exited (weight -> 0) the moment breadth
    drops below `breadth_min`, and -- because it is a real exit, not merely
    a hidden weight -- must NOT silently resume its old weight once the
    regime recovers unless it clears the entry bar again. A "pause" design
    (output multiplied by the gate post-hoc, without touching
    entry/exit_signal) would instead show 1.0 again from row 7 onward here.

    A: dips once (row 2) into a flat plateau; below_short stays satisfied
    forever (close == its own short average), but uptrend goes permanently
    False once the trend average catches up to the flat price, so A can
    only ever *enter* on row 2 -- it can never re-enter later.
    B: purely a breadth toggle, monotonically rising except for a single
    one-day dip at row 6 that is engineered to read as "not above its own
    2-day average" only on that row. B never itself satisfies entry.
    breadth_ma=2, breadth_min=0.5: with two tickers, breadth is 0.0, 0.5, or
    1.0. B alone crossing its own average pushes the 2-ticker fraction from
    0.5 (regime on) to 0.0 (regime off) on row 6 only.
    """
    idx = pd.RangeIndex(10)
    a = pd.Series([100.0, 104, 103, 103, 103, 103, 103, 103, 103, 103], index=idx)
    b = pd.Series([200.0, 202, 204, 206, 208, 210, 209, 213, 215, 217], index=idx)
    close = pd.DataFrame({"A": a, "B": b})

    w = regime_pullback(
        close,
        trend_lookback=3,
        short_ma=2,
        pullback_days=1,
        pullback_pct=0.0,
        exit_days=100,
        max_positions=1,
        breadth_ma=2,
        breadth_min=0.5,
    )

    assert w.iloc[:2].isna().all().all()
    # Entered row 2, held through row 5 (breadth == 0.5, regime on).
    assert (w.loc[2:5, "A"] == 1.0).all()
    # Row 6: B's one-day dip drops breadth to 0.0 -- forced flat.
    assert w.loc[6, "A"] == 0.0
    # Rows 7-9: regime recovers (breadth back to 0.5), but A's uptrend
    # condition is permanently False on this flat plateau, so it never
    # clears the entry bar again -- it stays flat rather than resuming.
    assert (w.loc[7:9, "A"] == 0.0).all()
    assert (w.loc[2:9, "B"] == 0.0).all()


# ---------------------------------------------------------------------------
# Temporal-offset convention: pins that neither family applies an internal
# shift, closing an audited coverage gap (see docstring below).
# ---------------------------------------------------------------------------


def _shared_pullback_space() -> dict[str, list]:
    """The parameter space shared by trend_pullback and regime_pullback --
    regime_pullback's own registered space minus its breadth-only knobs."""
    space = dict(SLEEVE_REGISTRY["regime_pullback"].space)
    space.pop("breadth_ma")
    space.pop("breadth_min")
    return space


@pytest.mark.parametrize("params", sample_params(_shared_pullback_space(), 3, seed=11))
def test_regime_pullback_with_gate_always_on_equals_trend_pullback(params):
    """Pins the shared close[t] -> weight[t] convention that both families
    rely on: neither trend_pullback nor regime_pullback applies any internal
    `.shift()` in its entry/exit/score/warmup construction -- the engine
    (src/qrl/engine.py, out of scope for this test) applies the *only*
    execution lag, uniformly, after a strategy function returns its weights.

    With the breadth gate forced permanently on, regime_pullback's
    entry/exit/score/warmup collapse to exactly trend_pullback's own, so the
    two weight frames must be identical -- not merely similar. breadth_min=0.0
    is used because `breadth = above_breadth_ma.mean(axis=1)` is a fraction
    of boolean comparisons ("close > sma_breadth"), which is False (never
    NaN) whenever `sma_breadth` itself is still NaN during warmup; the
    row-wise mean of False/True values is therefore always a finite number in
    [0, 1], so `breadth >= 0.0` is True on every single row, warmup rows
    included -- no row needs to be excluded from the comparison.

    Nothing today would catch a future edit that adds an internal `.shift()`
    to one family's entry/exit construction without the matching shift to
    the other: such a change uses no future data, so it evades both
    `assert_causal` and `test_regime_pullback_day_t_weights_unaffected_by_future_bar`
    above. This test would fail loudly on that class of bug instead.
    """
    _, close = synthetic_prices(["A", "B", "C", "D"], start=_START, end=_END)
    shared_kwargs = {**params, "capital": 1.0}

    vanilla = trend_pullback(close, **shared_kwargs)
    gated = regime_pullback(close, breadth_ma=100, breadth_min=0.0, **shared_kwargs)

    pd.testing.assert_frame_equal(vanilla, gated)
