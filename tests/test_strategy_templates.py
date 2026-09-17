"""Tests for the milestone 2.2 strategy templates: trend_pullback,
low_range_close, quiet_pullback, and the core_trend variants (lookback,
risk-off asset), plus the shared cross-sectional sleeve mechanics.

`checks.assert_causal` only knows how to tamper with a single `close` frame.
low_range_close and quiet_pullback also take high/low or volume, so each is
wrapped in a closure that *derives* its extra frame(s) from the very `close`
assert_causal hands it (high = close*1.01, low = close*0.99, volume from
|returns|). That way the crash/boom it applies to `close` propagates into
the derived frames too, and the check actually exercises those code paths
instead of trivially passing on frames that never change.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qrl.checks import assert_causal
from qrl.data import synthetic_prices
from qrl.engine import run_backtest
from qrl.strategies import REGISTRY, SLEEVE_REGISTRY, sample_params
from qrl.strategies._cross_section import build_weights
from qrl.strategies.core_trend import core_trend
from qrl.strategies.low_range_close import low_range_close
from qrl.strategies.quiet_pullback import quiet_pullback
from qrl.strategies.trend_pullback import trend_pullback

N_SAMPLES = 8
_START, _END = "2010-01-01", "2014-12-31"


def _derived_high_low(close: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    return close * 1.01, close * 0.99


def _derived_volume(close: pd.DataFrame) -> pd.DataFrame:
    return (close.pct_change().abs().fillna(0.0) + 0.01) * 1_000_000


def _frame(data: dict, idx) -> pd.DataFrame:
    return pd.DataFrame(data, index=idx)


# ---------------------------------------------------------------------------
# Causality, sampled across each family's parameter space
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "params", sample_params(SLEEVE_REGISTRY["trend_pullback"].space, N_SAMPLES, seed=1)
)
def test_trend_pullback_is_causal(params):
    _, close = synthetic_prices(["A", "B", "C"], start=_START, end=_END)
    assert_causal(lambda c: trend_pullback(c, **params), close)


@pytest.mark.parametrize(
    "params", sample_params(SLEEVE_REGISTRY["low_range_close"].space, N_SAMPLES, seed=2)
)
def test_low_range_close_is_causal(params):
    _, close = synthetic_prices(["A", "B", "C"], start=_START, end=_END)

    def wrapped(c: pd.DataFrame) -> pd.DataFrame:
        high, low = _derived_high_low(c)
        return low_range_close(c, high, low, **params)

    assert_causal(wrapped, close)


@pytest.mark.parametrize(
    "params", sample_params(SLEEVE_REGISTRY["quiet_pullback"].space, N_SAMPLES, seed=3)
)
def test_quiet_pullback_is_causal(params):
    _, close = synthetic_prices(["A", "B", "C"], start=_START, end=_END)

    def wrapped(c: pd.DataFrame) -> pd.DataFrame:
        return quiet_pullback(c, _derived_volume(c), **params)

    assert_causal(wrapped, close)


@pytest.mark.parametrize("params", sample_params(REGISTRY["core_trend"].space, N_SAMPLES, seed=4))
def test_core_trend_variants_are_causal(params):
    _, close = synthetic_prices(["QQQ", "GLD", "TLT"], start=_START, end=_END)
    assert_causal(lambda c: core_trend(c, risk_on="QQQ", **params), close)


# ---------------------------------------------------------------------------
# Hand-checked unit tests: a dozen rows, exact expected weights by hand.
# ---------------------------------------------------------------------------


def test_trend_pullback_hand_checked():
    idx = pd.RangeIndex(12)
    close = pd.DataFrame(
        {"A": [100, 102, 104, 106, 108, 107, 106, 109, 111, 113, 112, 115]}, index=idx
    ).astype(float)

    w = trend_pullback(
        close,
        trend_lookback=5,
        short_ma=2,
        pullback_days=2,
        pullback_pct=0.0,
        exit_days=3,
        max_positions=1,
        capital=1.0,
    )

    # Warm-up through row 3 (SMA(5) needs 5 points). Entry on row 5 (a down
    # close below its 2-day average while still above the 5-day trend
    # average). Exit on row 7 when the close recovers above the short
    # average (before the 3-bar time exit would fire on row 8).
    expected = pd.Series(
        [np.nan, np.nan, np.nan, np.nan, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0], index=idx
    )
    pd.testing.assert_series_equal(w["A"], expected, check_names=False)


def test_low_range_close_hand_checked():
    idx = pd.RangeIndex(12)
    close_s = pd.Series(
        [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111], index=idx, dtype=float
    )
    high_s = close_s + 1.0
    low_s = close_s - 1.0
    # Row 5 gets an artificially wide range so the close sits near the low
    # of its own day's range while still in the uptrend.
    high_s.iloc[5] = 108.0
    low_s.iloc[5] = 104.5

    close = close_s.to_frame("A")
    high = high_s.to_frame("A")
    low = low_s.to_frame("A")

    w = low_range_close(
        close, high, low, trend_lookback=3, range_pct=0.25, exit_days=2, max_positions=1
    )

    # Warm-up through row 1 (SMA(3) needs 3 points). Entry on row 5. No
    # technical exit ever fires here (each day's high equals the next day's
    # close by construction), so the row-7 exit is purely the 2-bar timer.
    expected = pd.Series(
        [np.nan, np.nan, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0], index=idx
    )
    pd.testing.assert_series_equal(w["A"], expected, check_names=False)


def test_quiet_pullback_hand_checked():
    idx = pd.RangeIndex(12)
    close = pd.DataFrame(
        {"A": [100, 102, 104, 106, 108, 107, 106, 109, 111, 113, 112, 115]}, index=idx
    ).astype(float)
    volume = pd.DataFrame(
        {"A": [1000, 1000, 1000, 1000, 1000, 500, 1000, 1000, 1000, 1000, 500, 1000]}, index=idx
    ).astype(float)

    w = quiet_pullback(
        close,
        volume,
        trend_lookback=5,
        short_ma=2,
        vol_lookback=3,
        quiet_ratio=0.8,
        exit_days=3,
        max_positions=1,
    )

    # Same uptrend/pullback shape as trend_pullback's hand test; volume dips
    # to half its 3-day average exactly on the two pullback rows (5 and 10),
    # so entries line up and the exit dates match.
    expected = pd.Series(
        [np.nan, np.nan, np.nan, np.nan, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0], index=idx
    )
    pd.testing.assert_series_equal(w["A"], expected, check_names=False)


def test_core_trend_cash_hand_checked():
    idx = pd.RangeIndex(6)
    close = pd.DataFrame({"QQQ": [100, 101, 99, 98, 103, 104]}, index=idx).astype(float)

    w = core_trend(close, risk_on="QQQ", risk_off="CASH", lookback=3)

    assert list(w.columns) == ["QQQ"]
    expected = pd.Series([np.nan, np.nan, 0.0, 0.0, 1.0, 1.0], index=idx)
    pd.testing.assert_series_equal(w["QQQ"], expected, check_names=False)


# ---------------------------------------------------------------------------
# Cross-sectional mechanics
# ---------------------------------------------------------------------------


def test_cross_section_caps_positions_and_equal_weights():
    idx = pd.RangeIndex(1)
    entry = _frame({"A": [True], "B": [True], "C": [True]}, idx)
    exit_signal = _frame({"A": [False], "B": [False], "C": [False]}, idx)
    score = _frame({"A": [3.0], "B": [2.0], "C": [1.0]}, idx)
    warmup = _frame({"A": [False], "B": [False], "C": [False]}, idx)

    w = build_weights(entry, exit_signal, score, warmup, max_positions=2, capital=1.0)

    assert w.loc[0, "A"] == pytest.approx(0.5)
    assert w.loc[0, "B"] == pytest.approx(0.5)
    assert w.loc[0, "C"] == 0.0
    assert w.sum(axis=1).iloc[0] <= 1.0 + 1e-9


def test_cross_section_holds_existing_name_over_new_higher_score():
    idx = pd.RangeIndex(2)
    entry = _frame({"A": [True, True], "B": [False, True]}, idx)
    exit_signal = _frame({"A": [False, False], "B": [False, False]}, idx)
    score = _frame({"A": [1.0, 1.0], "B": [0.0, 100.0]}, idx)
    warmup = _frame({"A": [False, False], "B": [False, False]}, idx)

    w = build_weights(entry, exit_signal, score, warmup, max_positions=1, capital=1.0)

    # B outranks A on row 1, but the single slot is already held by A, whose
    # own exit rule has not fired -- B must not bump it out.
    assert w.loc[1, "A"] == 1.0
    assert w.loc[1, "B"] == 0.0


def test_cross_section_deterministic_tie_break_by_ticker():
    idx = pd.RangeIndex(1)
    entry = _frame({"C": [True], "A": [True], "B": [True]}, idx)
    exit_signal = _frame({"C": [False], "A": [False], "B": [False]}, idx)
    score = _frame({"C": [1.0], "A": [1.0], "B": [1.0]}, idx)
    warmup = _frame({"C": [False], "A": [False], "B": [False]}, idx)

    w = build_weights(entry, exit_signal, score, warmup, max_positions=2, capital=1.0)

    # Equal scores: ties break alphabetically by ticker, so A and B win.
    assert w.loc[0, "A"] == pytest.approx(0.5)
    assert w.loc[0, "B"] == pytest.approx(0.5)
    assert w.loc[0, "C"] == 0.0


def test_cross_section_is_deterministic_across_repeated_calls():
    idx = pd.RangeIndex(1)
    entry = _frame({"A": [True], "B": [True]}, idx)
    exit_signal = _frame({"A": [False], "B": [False]}, idx)
    score = _frame({"A": [1.0], "B": [1.0]}, idx)
    warmup = _frame({"A": [False], "B": [False]}, idx)

    w1 = build_weights(entry, exit_signal, score, warmup, max_positions=1, capital=1.0)
    w2 = build_weights(entry, exit_signal, score, warmup, max_positions=1, capital=1.0)
    pd.testing.assert_frame_equal(w1, w2)


# ---------------------------------------------------------------------------
# Warm-up: no weight before each family's own trend lookback is available.
# ---------------------------------------------------------------------------


def test_trend_pullback_warmup_rows_are_nan():
    _, close = synthetic_prices(["A", "B"], start="2010-01-01", end="2011-12-31")
    w = trend_pullback(close, trend_lookback=200)
    assert w.iloc[:199].isna().all().all()


def test_low_range_close_warmup_rows_are_nan():
    _, close = synthetic_prices(["A", "B"], start="2010-01-01", end="2011-12-31")
    high, low = _derived_high_low(close)
    w = low_range_close(close, high, low, trend_lookback=200)
    assert w.iloc[:199].isna().all().all()


def test_quiet_pullback_warmup_rows_are_nan():
    _, close = synthetic_prices(["A", "B"], start="2010-01-01", end="2011-12-31")
    volume = _derived_volume(close)
    w = quiet_pullback(close, volume, trend_lookback=200)
    assert w.iloc[:199].isna().all().all()


# ---------------------------------------------------------------------------
# Staggered universes: a late-starting ticker must not push the strategy's
# own start (and therefore engine.run_backtest's) out to its own warm-up.
# Rows stay NaN only while EVERY ticker is still warming up; from the first
# row any ticker is ready, every column must be numeric (0.0 for names not
# yet eligible), never NaN -- see qrl.strategies._cross_section.build_weights.
# ---------------------------------------------------------------------------


def _staggered_close() -> pd.DataFrame:
    idx = pd.RangeIndex(20)
    early1 = pd.Series(np.arange(100.0, 120.0), index=idx)  # full history, never dips
    early2 = pd.Series(np.arange(200.0, 220.0), index=idx)  # full history, never dips
    # LATE starts at row 12 (60% through); its own SMA(5) needs rows 12-16
    # to complete, so it can only act from row 16 onward.
    late_vals = [100.0, 102.0, 104.0, 106.0, 108.0, 107.0, 106.0, 109.0]
    late = pd.Series([np.nan] * 12 + late_vals, index=idx)
    return pd.DataFrame({"EARLY1": early1, "EARLY2": early2, "LATE": late})


def test_staggered_universe_start_is_driven_by_early_tickers():
    close = _staggered_close()
    open_ = close.copy()

    w = trend_pullback(
        close,
        trend_lookback=5,
        short_ma=2,
        pullback_days=2,
        pullback_pct=0.0,
        exit_days=3,
        max_positions=3,
    )

    valid_rows = w.notna().all(axis=1)
    first_valid = valid_rows.idxmax()
    # Driven by EARLY1/EARLY2's own SMA(5) completing at row 4, not LATE's
    # (which only completes at row 16). The pre-fix bug gated this on LATE.
    assert first_valid == 4
    assert w.loc[: first_valid - 1].isna().all().all()

    result = run_backtest(open_, close, w)
    assert result.returns.index[0] == first_valid + 1


def test_late_starting_ticker_becomes_eligible_after_its_own_warmup():
    close = _staggered_close()

    w = trend_pullback(
        close,
        trend_lookback=5,
        short_ma=2,
        pullback_days=2,
        pullback_pct=0.0,
        exit_days=3,
        max_positions=3,
    )

    # LATE's own SMA(5) only completes at row 16 (still 0.0, not yet
    # entry-eligible that same day); it is entered on row 17, a down close
    # below its own short average while still above its own trend average.
    assert w.loc[16, "LATE"] == 0.0
    assert w.loc[17, "LATE"] == pytest.approx(1.0)
    assert w.loc[18, "LATE"] == pytest.approx(1.0)


@pytest.mark.parametrize(
    "make_weights",
    [
        lambda close: trend_pullback(close, trend_lookback=5, short_ma=2, max_positions=3),
        lambda close: low_range_close(
            close, *_derived_high_low(close), trend_lookback=5, max_positions=3
        ),
        lambda close: quiet_pullback(
            close,
            _derived_volume(close),
            trend_lookback=5,
            short_ma=2,
            vol_lookback=5,
            max_positions=3,
        ),
        # core_trend is a fixed two-asset switch, not a cross-sectional
        # sleeve, so it never sees a staggered LATE column; included so all
        # four families are covered by the same no-NaN-after-start check.
        lambda close: core_trend(
            close[["EARLY1", "EARLY2"]], risk_on="EARLY1", risk_off="EARLY2", lookback=5
        ),
    ],
    ids=["trend_pullback", "low_range_close", "quiet_pullback", "core_trend"],
)
def test_no_nan_after_first_actionable_row_for_every_family(make_weights):
    close = _staggered_close()
    w = make_weights(close)

    valid_rows = w.notna().all(axis=1)
    assert valid_rows.any()
    first_valid = valid_rows.idxmax()
    assert not w.loc[first_valid:].isna().any().any()


def test_mid_series_shared_data_gap_does_not_flatten_a_held_position():
    """A data gap that poisons every column's rolling window on the *same*
    row, well after the strategy has already started, must not be treated
    like the leading warm-up prefix (see build_weights/_leading_true_run).

    Ticker A dips once early (entry on row 5) and then trades perfectly
    flat, so it is never exited technically and `exit_days=100` rules out a
    timed exit within this window -- it should stay held for the entire
    30-row series. Ticker B never enters. Both tickers' closes go NaN on
    row 15 only (a one-day shared gap): this poisons SMA(5) for rows
    15-19 and SMA(2) for rows 15-16 in *both* columns, so
    `warmup.all(axis=1)` is True again on rows 15-19 despite the strategy
    having been running since row 5.
    """
    idx = pd.RangeIndex(30)
    a_vals = [100.0, 102.0, 104.0, 106.0, 108.0, 107.0] + [106.0] * 24
    b_vals = [200.0 + i for i in range(30)]
    a = pd.Series(a_vals, index=idx)
    b = pd.Series(b_vals, index=idx)
    a.iloc[15] = np.nan
    b.iloc[15] = np.nan
    close = pd.DataFrame({"A": a, "B": b})

    w = trend_pullback(
        close,
        trend_lookback=5,
        short_ma=2,
        pullback_days=2,
        pullback_pct=0.0,
        exit_days=100,
        max_positions=1,
    )

    # (a) Necessary condition: no NaN anywhere from the first actionable row
    # (row 4, SMA(5) warm-up) onward, including through the row 15-19 gap.
    assert not w.loc[4:].isna().any().any()

    # (b) The semantically meaningful assertion: A was already held before
    # the gap (row 5 onward) and the gap itself creates no exit signal (a
    # comparison against NaN is False, never True), so A must still be
    # held with its *unchanged* weight all the way through the gap and
    # after it -- not reset to 0 by a naive "NaN the poisoned rows" fix.
    assert (w.loc[5:29, "A"] == 1.0).all()
    assert (w.loc[4:29, "B"] == 0.0).all()
