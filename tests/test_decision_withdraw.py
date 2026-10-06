"""Withdrawal mechanics (qrl.decision_withdraw). Offline; synthetic returns
and CPI. Spec: docs/methodology/decision-helper.md ("Withdrawals")."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from decision_helpers import cpi

from qrl.decision_withdraw import (
    WithdrawalPath,
    longest_below_peak,
    monthly_withdrawals,
    path_metrics,
    withdrawal_path,
)

MONTH_STARTS = pd.date_range("2005-01-01", "2006-12-01", freq="BMS")  # first business days


def test_withdrawal_path_closed_form_constant_return():
    g, w = 0.01, 0.004
    path = withdrawal_path(pd.Series(g, index=MONTH_STARTS), {2005: w, 2006: w})
    n = np.arange(1, len(MONTH_STARTS) + 1)
    expected = (1 + g) ** n - w * ((1 + g) ** n - 1) / g  # V_n = V_{n-1}(1+g) - w, V_0 = 1
    np.testing.assert_allclose(path.values.to_numpy(), expected)
    assert path.depleted is None


def test_withdrawal_comes_after_the_days_return():
    # Hand value: (1 + 0.10) - 0.05 = 1.05. Withdrawing first would give
    # (1 - 0.05) x 1.10 = 1.045.
    path = withdrawal_path(pd.Series([0.10], index=pd.to_datetime(["2005-01-03"])), {2005: 0.05})
    assert path.values.iloc[0] == pytest.approx(1.05)


def test_withdrawal_only_on_first_trading_day_of_month():
    idx = pd.bdate_range("2005-01-03", "2005-02-04")
    path = withdrawal_path(pd.Series(0.0, index=idx), {2005: 0.01})
    assert path.values.loc["2005-01-03"] == pytest.approx(0.99)
    assert path.values.loc["2005-01-31"] == pytest.approx(0.99)
    assert path.values.loc["2005-02-01"] == pytest.approx(0.98)
    assert path.values.iloc[-1] == pytest.approx(0.98)


def test_withdrawal_depletion_stops_at_zero():
    path = withdrawal_path(pd.Series(0.0, index=MONTH_STARTS), {2005: 0.3, 2006: 0.3})
    # 1.0 -> 0.7 (Jan) -> 0.4 (Feb) -> 0.1 (Mar) -> depleted in April
    assert path.values.loc["2005-03-01"] == pytest.approx(0.1)
    assert path.depleted == "2005-04"
    assert (path.values.loc["2005-04-01":] == 0.0).all()


def test_withdrawal_amount_changes_in_january_by_the_cpi_factor():
    # Hand: 2005 withdraws 0.01 a month, 2006 withdraws 0.01 x 1.5 = 0.015.
    idx = pd.to_datetime(["2005-12-01", "2006-01-02", "2006-02-01"])
    path = withdrawal_path(pd.Series(0.0, index=idx), {2005: 0.01, 2006: 0.015})
    np.testing.assert_allclose(path.values.to_numpy(), [0.99, 0.975, 0.96])


def test_monthly_withdrawals_raised_each_january_by_usable_cpi():
    amounts = monthly_withdrawals(0.04, 2005, 2007, cpi(monthly_growth=0.01))
    yoy = 1.01**12 - 1
    assert amounts[2005] == pytest.approx(0.04 / 12)
    assert amounts[2006] == pytest.approx(0.04 / 12 * (1 + yoy))
    assert amounts[2007] == pytest.approx(0.04 / 12 * (1 + yoy) ** 2)


def test_monthly_withdrawals_refuse_missing_cpi():
    with pytest.raises(ValueError, match="missing CPI"):
        monthly_withdrawals(0.04, 2005, 2007, cpi().loc[:"2005-06-30"])


def _hand_cpi(level_2004: float, level_2005: float) -> pd.Series:
    # Availability-dated: usable on 2004-01-01 is 100, on 2005-01-01 level_2004,
    # on 2006-01-01 level_2005.
    return pd.Series(
        [100.0, level_2004, level_2005],
        index=pd.to_datetime(["2003-12-31", "2004-12-31", "2005-12-31"]),
    )


def test_cpi_raise_applies_in_january_only_never_inside_a_year():
    # CPI usable 1 Jan 2005 / 1 Jan 2004 = 110 / 100: YoY exactly 10%.
    amounts = monthly_withdrawals(0.12, 2004, 2005, _hand_cpi(110.0, 121.0))
    assert amounts[2004] == pytest.approx(0.01)
    assert amounts[2005] == pytest.approx(0.011)
    idx = pd.bdate_range("2004-01-01", "2005-12-31")
    values = withdrawal_path(pd.Series(0.0, index=idx), amounts).values
    steps = -values.diff().fillna(values.iloc[0] - 1.0)
    taken = steps[steps.abs() > 1e-12]
    assert len(taken) == 24
    np.testing.assert_allclose(taken.iloc[:12].to_numpy(), 0.01)
    np.testing.assert_allclose(taken.iloc[12:].to_numpy(), 0.011)
    assert (taken.iloc[:12].index.year == 2004).all()
    assert (taken.iloc[12:].index.year == 2005).all()


def test_negative_cpi_yoy_lowers_the_amount_with_no_floor():
    # CPI falls 2%: next year's amount = 0.01 x 0.98 = 0.0098.
    amounts = monthly_withdrawals(0.12, 2004, 2005, _hand_cpi(98.0, 98.0))
    assert amounts[2005] == pytest.approx(0.0098)


def test_path_metrics_on_a_depleted_path():
    idx = pd.to_datetime(["2005-01-03", "2005-02-01", "2005-03-01"])
    m = path_metrics(WithdrawalPath(pd.Series([0.5, 0.0, 0.0], index=idx), "2005-02"), cpi())
    assert m["max_drawdown"] == 1.0
    assert m["lowest"] == 0.0
    assert m["depleted"] == "2005-02"
    assert m["below_peak_at_end"] is True


def test_value_reaching_zero_on_a_non_withdrawal_day_is_depleted():
    idx = pd.to_datetime(["2005-01-03", "2005-01-04", "2005-01-05"])
    path = withdrawal_path(pd.Series([0.0, -1.0, 0.5], index=idx), {2005: 0.01})
    assert path.depleted == "2005-01"
    assert path.values.iloc[0] == pytest.approx(0.99)
    assert (path.values.iloc[1:] == 0.0).all()


def test_nan_return_refused_with_the_date():
    idx = pd.to_datetime(["2005-01-03", "2005-01-04"])
    with pytest.raises(ValueError, match="NaN return on 2005-01-04"):
        withdrawal_path(pd.Series([0.0, np.nan], index=idx), {2005: 0.01})


def test_below_peak_at_end_with_longest_spell_recovered_earlier():
    idx = pd.to_datetime(["2005-01-03", "2005-02-01", "2005-08-01", "2005-09-01"])
    m = path_metrics(
        WithdrawalPath(pd.Series([1.0, 0.9, 1.1, 1.0], index=idx), None), cpi(monthly_growth=0.01)
    )
    assert m["below_peak_months"] == 7
    assert m["recovered"] is True
    assert m["below_peak_at_end"] is True


def test_not_below_peak_at_end_when_ending_at_a_new_high():
    idx = pd.to_datetime(["2005-01-03", "2005-02-01", "2005-03-01"])
    m = path_metrics(WithdrawalPath(pd.Series([1.0, 0.9, 1.1], index=idx), None), cpi())
    assert m["below_peak_at_end"] is False


def test_longest_below_peak_recovered():
    idx = pd.to_datetime(["2005-01-03", "2005-02-01", "2005-05-02", "2005-06-01"])
    # peak in January, back above it in May: 4 months
    assert longest_below_peak(pd.Series([1.0, 0.9, 1.1, 1.05], index=idx)) == (4, True)


def test_longest_below_peak_starting_value_is_the_first_peak():
    idx = pd.to_datetime(["2005-01-03", "2005-03-01"])
    assert longest_below_peak(pd.Series([0.99, 1.01], index=idx)) == (2, True)


def test_longest_below_peak_unrecovered_reported_as_such():
    idx = pd.to_datetime(["2005-01-03", "2005-03-01", "2005-06-01"])
    assert longest_below_peak(pd.Series([1.0, 0.8, 0.9], index=idx)) == (5, False)


def test_path_metrics_real_end_drawdown_and_lowest():
    idx = pd.to_datetime(["2005-01-03", "2005-02-01", "2005-03-01"])
    m = path_metrics(
        WithdrawalPath(pd.Series([1.2, 0.9, 1.0], index=idx), None), cpi(monthly_growth=0.01)
    )
    assert m["end_nominal"] == pytest.approx(1.0)
    # CPI usable on 2005-01-03 is Nov 2004's, on 2005-03-01 Jan 2005's: two months apart
    assert m["end_real"] == pytest.approx(1.0 / 1.01**2)
    assert m["lowest"] == pytest.approx(0.9)
    assert m["max_drawdown"] == pytest.approx(0.25)
    assert m["below_peak_months"] == 2
    assert m["recovered"] is False
    assert m["depleted"] is None
