"""Tests for qrl.history_data (docs/methodology/history-scenarios.md,
"Stand-in data"). Synthetic data only; nothing here downloads."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qrl.history_data import interpolate_monthly, sp_with_dividends


def test_each_monthly_figure_sits_on_its_month_end():
    index = pd.bdate_range("2000-01-03", "2000-04-28")
    monthly = pd.Series(
        [100.0, 110.0, 121.0, 133.1],
        index=pd.to_datetime(["2000-01-01", "2000-02-01", "2000-03-01", "2000-04-01"]),
    )
    out = interpolate_monthly(monthly, index)
    for day, figure in [
        ("2000-01-31", 100.0),
        ("2000-02-29", 110.0),
        ("2000-03-31", 121.0),
        ("2000-04-28", 133.1),
    ]:
        assert out.loc[day] == pytest.approx(figure)
    assert out.loc[:"2000-01-28"].isna().all()  # nothing before the first month end


def test_days_between_month_ends_move_at_a_constant_daily_rate():
    index = pd.bdate_range("2000-01-03", "2000-04-28")
    monthly = pd.Series(
        [100.0, 110.0, 121.0, 133.1],
        index=pd.to_datetime(["2000-01-01", "2000-02-01", "2000-03-01", "2000-04-01"]),
    )
    out = interpolate_monthly(monthly, index)
    february = out.loc["2000-02-01":"2000-02-29"].pct_change().dropna()
    assert np.allclose(february, february.iloc[0])
    assert (out.loc["2000-02-01":"2000-02-29"].diff().dropna() > 0).all()


def test_interpolation_refuses_a_non_positive_figure():
    index = pd.bdate_range("2000-01-03", "2000-03-31")
    monthly = pd.Series([100.0, 0.0], index=pd.to_datetime(["2000-01-01", "2000-02-01"]))
    with pytest.raises(ValueError, match="positive"):
        interpolate_monthly(monthly, index)


def test_dividends_accrue_daily_as_yield_over_252():
    index = pd.bdate_range("2000-01-03", periods=3)
    price = pd.Series(100.0, index=index)
    yields = pd.Series(0.0252, index=pd.to_datetime(["1999-11-01", "1999-12-01", "2000-01-01"]))
    out = sp_with_dividends(price, yields)
    assert out.iloc[0] == 1.0
    assert out.iloc[1] == pytest.approx(1.0001)
    assert out.iloc[2] == pytest.approx(1.0001**2)


def test_dividend_yield_of_the_previous_month_is_used():
    index = pd.bdate_range("2000-01-31", periods=2)  # Jan 31, Feb 1
    price = pd.Series(100.0, index=index)
    yields = pd.Series([0.0252, 0.0504], index=pd.to_datetime(["1999-12-01", "2000-01-01"]))
    out = sp_with_dividends(price, yields)
    assert out.iloc[1] == pytest.approx(1.0 + 0.0504 / 252)  # Feb 1 uses January's yield


def test_dividend_return_is_additive_to_the_price_return():
    index = pd.bdate_range("2000-01-03", periods=3)
    price = pd.Series([100.0, 110.0, 99.0], index=index)
    yields = pd.Series(0.0252, index=pd.to_datetime(["1999-12-01"]))
    out = sp_with_dividends(price, yields)
    step = 0.0252 / 252
    assert out.iloc[1] == pytest.approx(1.0 + 0.10 + step)
    assert out.iloc[2] == pytest.approx((1.0 + 0.10 + step) * (1.0 - 0.10 + step))
    assert out.iloc[1] != pytest.approx(1.10 * (1.0 + step))


def test_nan_price_raises():
    index = pd.bdate_range("2000-01-03", periods=3)
    price = pd.Series([100.0, np.nan, 101.0], index=index)
    yields = pd.Series(0.03, index=pd.to_datetime(["1999-12-01"]))
    with pytest.raises(ValueError, match="missing"):
        sp_with_dividends(price, yields)


def test_empty_price_raises():
    price = pd.Series([], index=pd.DatetimeIndex([]), dtype=float)
    yields = pd.Series(0.03, index=pd.to_datetime(["1999-12-01"]))
    with pytest.raises(ValueError, match="empty"):
        sp_with_dividends(price, yields)


@pytest.mark.parametrize("days", [["2000-01-04", "2000-01-03"], ["2000-01-03", "2000-01-03"]])
def test_unsorted_or_duplicated_price_index_raises(days):
    price = pd.Series([100.0, 101.0], index=pd.to_datetime(days))
    yields = pd.Series(0.03, index=pd.to_datetime(["1999-12-01"]))
    with pytest.raises(ValueError, match="strictly increasing"):
        sp_with_dividends(price, yields)


@pytest.mark.parametrize("days", [["2000-01-04", "2000-01-03"], ["2000-01-03", "2000-01-03"]])
def test_unsorted_or_duplicated_interpolation_index_raises(days):
    monthly = pd.Series([100.0], index=pd.to_datetime(["2000-01-01"]))
    with pytest.raises(ValueError, match="strictly increasing"):
        interpolate_monthly(monthly, pd.DatetimeIndex(pd.to_datetime(days)))


def test_two_yield_figures_in_one_month_raise():
    index = pd.bdate_range("2000-01-03", periods=2)
    price = pd.Series(100.0, index=index)
    yields = pd.Series([0.03, 0.04], index=pd.to_datetime(["1999-12-01", "1999-12-15"]))
    with pytest.raises(ValueError, match="more than one"):
        sp_with_dividends(price, yields)


def test_a_missing_middle_month_is_bridged_geometrically():
    index = pd.bdate_range("2000-01-03", "2000-03-31")
    monthly = pd.Series([100.0, 121.0], index=pd.to_datetime(["2000-01-01", "2000-03-01"]))
    out = interpolate_monthly(monthly, index)
    assert out.loc["2000-01-31"] == pytest.approx(100.0)
    assert out.loc["2000-03-31"] == pytest.approx(121.0)
    steps = out.loc["2000-01-31":"2000-03-31"].pct_change().dropna()
    assert np.allclose(steps, steps.iloc[0])


def test_missing_dividend_yield_raises():
    index = pd.bdate_range("2000-01-03", periods=3)
    price = pd.Series(100.0, index=index)
    yields = pd.Series([0.03], index=pd.to_datetime(["1990-01-01"]))
    with pytest.raises(ValueError, match="dividend yield"):
        sp_with_dividends(price, yields)
