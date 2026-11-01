"""Tests for the stand-in checks (docs/methodology/history-scenarios.md,
"Stand-in checks"). Synthetic data only."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qrl.history_data import Link, run_checks

END = pd.Timestamp("2018-12-31")


def _walk(index, seed):
    rng = np.random.default_rng(seed)
    return pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(index)))), index=index)


def test_daily_link_above_the_bar_passes_and_reports_the_overlap():
    index = pd.bdate_range("2000-01-03", periods=300)
    fund = _walk(index, 1)
    fund.iloc[:100] = np.nan  # the fund starts later than the stand-in
    standin = _walk(index, 1) * 2.0  # same returns
    result = run_checks([Link("QQQ: x against QQQ", standin, fund, "daily")], END, 0.95)[0]
    assert result.correlation == pytest.approx(1.0)
    assert result.frequency == "daily"
    assert result.start == index[101].date().isoformat()  # first common return day
    assert result.end == index[-1].date().isoformat()
    assert result.n == 199


def test_a_stand_in_below_the_bar_raises():
    index = pd.bdate_range("2000-01-03", periods=300)
    link = Link("SHY: proxy against SHY", _walk(index, 1), _walk(index, 2), "daily")
    with pytest.raises(ValueError, match="SHY: proxy against SHY"):
        run_checks([link], END, 0.95)


def test_daily_data_after_the_end_is_not_read():
    index = pd.bdate_range("2018-06-01", "2019-06-28")
    good = _walk(index, 1)
    bad = good.copy()
    bad.loc["2019-01-01":] = _walk(index, 5).loc["2019-01-01":]  # uncorrelated after the end
    result = run_checks([Link("x", good, bad, "daily")], END, 0.95)[0]
    assert result.correlation == pytest.approx(1.0)
    assert result.end <= "2018-12-31"


def test_monthly_link_uses_month_end_returns_and_the_monthly_mean():
    index = pd.bdate_range("2000-01-03", "2004-12-31")
    futures = _walk(index, 3)
    month_end = futures.groupby(index.to_period("M")).last()
    month_mean = futures.groupby(index.to_period("M")).mean()
    # a monthly stand-in exactly equal to the monthly mean of the futures
    figure = pd.Series(month_mean.to_numpy(), index=month_mean.index.to_timestamp())
    by_mean = Link("gold: wb against mean", figure, futures, "monthly", "mean")
    assert run_checks([by_mean], END, 0.95)[0].correlation == pytest.approx(1.0)
    fund = futures * 1.5
    by_last = Link("gold: end against end", futures, fund, "monthly")
    result = run_checks([by_last], END, 0.95)[0]
    assert result.correlation == pytest.approx(1.0)
    assert result.n == len(month_end) - 1


def test_a_bond_style_link_passes_on_month_ends_though_its_daily_moves_differ():
    index = pd.bdate_range("2000-01-03", "2004-12-31")
    fund = _walk(index, 7)
    # same month-end closes, but an unrelated path inside each month
    noise = _walk(index, 8)
    month = index.to_period("M")
    is_end = pd.Series(month, index=index).ne(pd.Series(month, index=index).shift(-1)).to_numpy()
    standin = pd.Series(np.where(is_end, fund.to_numpy(), noise.to_numpy()), index=index)
    link = Link("TLT: proxy against TLT", standin, fund, "monthly")
    result = run_checks([link], END, 0.95)[0]
    assert result.frequency == "monthly"
    assert result.correlation == pytest.approx(1.0)
    assert result.n == len(fund.groupby(month).last()) - 1
    with pytest.raises(ValueError, match="TLT: proxy against TLT"):
        run_checks([Link("TLT: proxy against TLT", standin, fund, "daily")], END, 0.95)


def test_too_short_an_overlap_raises():
    index = pd.bdate_range("2000-01-03", periods=10)
    link = Link("x", _walk(index, 1), _walk(index, 1), "daily")
    with pytest.raises(ValueError, match="overlap"):
        run_checks([link], END, 0.95)


def test_all_failures_are_listed():
    index = pd.bdate_range("2000-01-03", periods=300)
    links = [
        Link("first", _walk(index, 1), _walk(index, 2), "daily"),
        Link("second", _walk(index, 3), _walk(index, 4), "daily"),
    ]
    with pytest.raises(ValueError, match="first.*second"):
        run_checks(links, END, 0.95)
