import numpy as np
import pandas as pd
import pytest

from qrl.engine import run_backtest
from qrl.tradability import exit_before_delisting


def _truncated_frame():
    """A single ticker whose price history ends 3 bars before the frame's end."""
    idx = pd.bdate_range("2024-01-01", periods=6)
    close = pd.DataFrame({"B": [10.0, 10.5, 11.0, np.nan, np.nan, np.nan]}, index=idx)
    open_ = close.copy()
    return open_, close


def test_engine_raises_missing_price_when_truncated_ticker_held_without_helper():
    """(a) Without the helper, holding a delisted ticker to the end must still
    trip the engine's existing missing-price guard -- we don't reimplement it."""
    open_, close = _truncated_frame()
    w = pd.DataFrame({"B": 1.0}, index=close.index)
    with pytest.raises(ValueError, match="Missing price"):
        run_backtest(open_, close, w)


def test_helper_lets_the_backtest_run_and_zeros_the_position_from_the_right_date():
    """(b) With the helper, the same target runs cleanly and the position is
    zero from the exit row onward."""
    open_, close = _truncated_frame()
    w = pd.DataFrame({"B": 1.0}, index=close.index)
    safe_w = exit_before_delisting(w, open_, close)

    # Last valid bar is row 2 (index position 2) -> exit from row 1 onward.
    assert safe_w["B"].iloc[0] == 1.0
    assert (safe_w["B"].iloc[1:] == 0.0).all()

    res = run_backtest(open_, close, safe_w, cost_bps=0)
    # Results start at the first execution day (row 1). Its session
    # (open1 -> close1) is still fully priced and was decided before the
    # exit, so it is held; every session from row 2 onward (which would need
    # the missing row-2 close) is flat.
    assert res.executed["B"].iloc[0] == 1.0
    assert (res.executed["B"].iloc[1:] == 0.0).all()


def test_exit_before_delisting_hand_checked_tiny_example():
    """(c) A tiny, fully hand-computed example with one healthy and one
    delisted ticker."""
    idx = pd.bdate_range("2024-01-01", periods=5)
    close = pd.DataFrame(
        {
            "A": [10.0, 11.0, 12.0, 13.0, 14.0],
            "B": [20.0, 21.0, np.nan, np.nan, np.nan],
        },
        index=idx,
    )
    open_ = close.copy()
    weights = pd.DataFrame({"A": 1.0, "B": 1.0}, index=idx)

    out = exit_before_delisting(weights, open_, close)

    # A is priced throughout -> untouched.
    assert (out["A"] == 1.0).all()

    # B's last valid bar is row 1 (positions 0, 1 valid) -> exit_from = max(1-1, 0) = 0,
    # so every row is forced to 0, including row 0.
    expected_b = pd.Series([0.0, 0.0, 0.0, 0.0, 0.0], index=idx, name="B")
    pd.testing.assert_series_equal(out["B"], expected_b, check_names=False)
