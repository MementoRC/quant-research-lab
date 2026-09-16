import numpy as np
import pandas as pd
import pytest

from qrl.engine import run_backtest


def _prices(n=300, seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=n)
    close = pd.DataFrame(
        100 * np.exp(np.cumsum(rng.normal(0, 0.01, (n, 2)), axis=0)), index=idx, columns=["A", "B"]
    )
    open_ = close.shift(1).fillna(100) * np.exp(rng.normal(0, 0.003, (n, 2)))
    return open_, close


def test_full_position_matches_price_path():
    open_, close = _prices()
    w = pd.DataFrame({"A": 1.0, "B": 0.0}, index=close.index)
    res = run_backtest(open_, close, w, cost_bps=0)
    # Signal on day 0 close, entry at day 1 open, hold to the last close.
    expected = close["A"].iloc[-1] / open_["A"].iloc[1]
    assert res.equity.iloc[-1] == pytest.approx(expected, rel=1e-10)


def test_entry_cost_is_charged_once():
    open_, close = _prices()
    w = pd.DataFrame({"A": 1.0, "B": 0.0}, index=close.index)
    free = run_backtest(open_, close, w, cost_bps=0).equity.iloc[-1]
    paid = run_backtest(open_, close, w, cost_bps=10).equity.iloc[-1]
    assert paid == pytest.approx(free * (1 - 0.001), rel=1e-10)


def test_switching_costs_scale_with_turnover():
    open_, close = _prices()
    flip = np.arange(len(close)) % 2
    w = pd.DataFrame({"A": flip.astype(float), "B": 1.0 - flip}, index=close.index)
    res = run_backtest(open_, close, w, cost_bps=5)
    assert (res.turnover.iloc[1:] == 2.0).all()
    assert res.costs.iloc[1:].eq(0.001).all()


def test_engine_is_causal():
    """Changing the target on day k must not affect any return up to day k."""
    open_, close = _prices()
    rng = np.random.default_rng(3)
    a = rng.uniform(0, 1, len(close))
    w = pd.DataFrame({"A": a, "B": 0.0}, index=close.index)
    base = run_backtest(open_, close, w, cost_bps=5).returns
    for k in (50, 150, 250):
        w2 = w.copy()
        w2.iloc[k:, 0] = 1.0 - w2.iloc[k:, 0]
        alt = run_backtest(open_, close, w2, cost_bps=5).returns
        day_k = close.index[k]
        pd.testing.assert_series_equal(base.loc[:day_k], alt.loc[:day_k])
        assert not base.loc[day_k:].iloc[1:].equals(alt.loc[day_k:].iloc[1:])


def test_rejects_leverage_and_shorts():
    open_, close = _prices()
    with pytest.raises(ValueError, match="leverage"):
        run_backtest(open_, close, pd.DataFrame({"A": 0.8, "B": 0.8}, index=close.index))
    with pytest.raises(ValueError, match="shorting"):
        run_backtest(open_, close, pd.DataFrame({"A": -0.5, "B": 0.0}, index=close.index))


def test_missing_price_on_held_position_raises():
    open_, close = _prices()
    close.iloc[100, 0] = np.nan
    w = pd.DataFrame({"A": 1.0, "B": 0.0}, index=close.index)
    with pytest.raises(ValueError, match="Missing price"):
        run_backtest(open_, close, w)


def test_warmup_nans_delay_start():
    open_, close = _prices()
    w = pd.DataFrame({"A": 1.0, "B": 0.0}, index=close.index)
    w.iloc[:20] = np.nan
    res = run_backtest(open_, close, w)
    # Last NaN row is 19, first signal is row 20, first execution is row 21.
    assert res.returns.index[0] == close.index[21]
