"""Tests for qrl.history.episode_measures (docs/methodology/history-scenarios.md,
"Measures"). Hand-computed on small series."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from qrl.history import (
    NA_DATA,
    NO_SIGNAL,
    NOT_RECOVERED,
    Context,
    Episode,
    episode_measures,
    first_day_after,
    income_key,
)

PEAK = pd.Timestamp("2000-01-03")
END = pd.Timestamp("2012-12-31")
CALENDAR = pd.bdate_range("2000-01-03", END)
CPI = pd.Series(100.0, index=pd.date_range("1998-01-31", END, freq="ME"))  # flat: no raises


def _episode(**kw) -> Episode:
    base = {
        "peak": PEAK,
        "trough": pd.Timestamp("2000-02-01"),
        "recovery": None,
        "depth": 0.2,
        "months": None,
        "window_end": pd.Timestamp("2010-01-03"),
    }
    return Episode(**{**base, **kw})


def _ctx(rates=(0.12,), years=(5, 10), end=END) -> Context:
    return Context(
        calendar=CALENDAR[CALENDAR <= end],
        cpi=CPI,
        rates=rates,
        income_years=years,
        data_end=end,
    )


def _returns(changes: dict[str, float], start="2000-01-04", end=END) -> pd.Series:
    r = pd.Series(0.0, index=pd.bdate_range(start, end))
    for day, value in changes.items():
        r.loc[day] = value
    return r


def test_worst_loss_and_months_to_recover():
    r = _returns({"2000-02-01": -0.2, "2000-05-01": 0.26})  # 0.8, then 0.8 x 1.26 = 1.008
    cells = episode_measures(_episode(), r, _ctx())
    assert cells["loss"].value == pytest.approx(0.2)
    assert cells["recover"].value == 4  # 2000-01 to 2000-05
    assert cells["recover"].note == ""


def test_a_path_that_never_falls_has_zero_loss_and_zero_months():
    r = pd.Series(0.0001, index=pd.bdate_range("2000-01-04", END))
    cells = episode_measures(_episode(), r, _ctx())
    assert cells["loss"].value == 0.0
    assert cells["recover"].value == 0.0


def test_not_recovered_by_the_data_end():
    r = _returns({"2000-02-01": -0.2})
    cell = episode_measures(_episode(), r, _ctx())["recover"]
    assert math.isinf(cell.value)
    assert cell.note == NOT_RECOVERED


def test_recovery_is_looked_for_beyond_the_ten_year_window():
    r = _returns({"2000-02-01": -0.2, "2011-03-01": 0.30})  # back above 1 after 11 years
    cells = episode_measures(_episode(), r, _ctx())
    assert cells["loss"].value == pytest.approx(0.2)
    assert cells["recover"].value == 11 * 12 + 2  # 2000-01 to 2011-03


def test_the_low_is_the_lowest_value_in_the_window_not_the_first_dip():
    r = _returns({"2000-02-01": -0.05, "2000-03-01": 0.06, "2000-06-01": -0.30, "2001-06-01": 0.60})
    cells = episode_measures(_episode(), r, _ctx())
    # dips 5%, is back above 1 in March, then falls 30% from the new level: low is June 2000
    assert cells["recover"].value == 17  # 2000-01 to 2001-06


def test_no_signal_when_the_peak_is_before_the_portfolio_starts():
    r = _returns({}, start="2001-01-02")
    cells = episode_measures(_episode(), r, _ctx())
    assert {c.note for c in cells.values()} == {NO_SIGNAL}
    assert all(c.value is None for c in cells.values())


def test_the_first_return_day_is_the_next_trading_day_after_the_peak():
    assert first_day_after(CALENDAR, PEAK) == pd.Timestamp("2000-01-04")
    assert first_day_after(CALENDAR, END) is None
    # a portfolio whose first return day is that very day has a signal
    r = _returns({"2000-02-01": -0.2}, start="2000-01-04")
    assert episode_measures(_episode(), r, _ctx())["loss"].value == pytest.approx(0.2)


def test_income_balance_after_five_years_and_depletion_by_ten():
    r = _returns({})  # zero returns: only the withdrawals move the balance
    cells = episode_measures(_episode(), r, _ctx(rates=(0.12,)))
    five = cells[income_key(0.12, 5)]
    ten = cells[income_key(0.12, 10)]
    # 0.12 / 12 = 1% of the start a month, first taken on 2000-01-04 and again on the
    # first trading day of each month: Jan 2000 .. Jan 2005 = 61 withdrawals (flat CPI)
    assert five.value == pytest.approx(0.39, abs=1e-9)
    assert five.note == ""
    # the 100th withdrawal empties it: April 2008
    assert ten.value == 0.0
    assert ten.note == "depleted 2008-04"


def test_income_horizon_past_the_data_end_is_not_available():
    end = pd.Timestamp("2004-12-31")
    r = _returns({}, end=end)
    cells = episode_measures(_episode(), r, _ctx(end=end))
    assert cells[income_key(0.12, 5)].note == NA_DATA  # 2005-01-03 is after the data
    assert cells[income_key(0.12, 5)].value is None
    assert cells[income_key(0.12, 10)].note == NA_DATA
    assert cells["loss"].value == 0.0  # the fall measures still exist


def test_income_is_reported_as_a_real_balance_deflated_by_cpi():
    months = pd.date_range("1998-01-31", END, freq="ME")
    cpi = pd.Series(100.0 * 1.02 ** (months.year - 1998).to_numpy(), index=months)
    r = _returns({})
    ctx = Context(CALENDAR, cpi, (0.02,), (5,), END)
    cell = episode_measures(_episode(), r, ctx)[income_key(0.02, 5)]
    assert 0 < cell.value < 1
    # nominal balance with raises exceeds the real one deflated by about 5 x 2% of inflation
    assert cell.value < 0.9
