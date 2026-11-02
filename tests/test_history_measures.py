"""Tests for qrl.history.episode_measures (docs/methodology/history-scenarios.md,
"Measures"). Hand-computed on small series."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from qrl.history import (
    DAGGER,
    DOUBLE_DAGGER,
    NA_DATA,
    NO_SIGNAL,
    NOT_RECOVERED,
    Cell,
    Context,
    Episode,
    Summary,
    apply_marks,
    cell_marks,
    episode_measures,
    first_day_after,
    income_key,
    summarize,
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
        calendar=CALENDAR[end >= CALENDAR],
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


def test_a_return_on_the_peak_date_itself_is_ignored():
    # Value is 1 at the peak's close: its own day's return is already in the price.
    with_peak_day = _returns({"2000-02-01": -0.2}, start="2000-01-03")
    with_peak_day.loc["2000-01-03"] = -0.5
    without = _returns({"2000-02-01": -0.2}, start="2000-01-04")
    got = episode_measures(_episode(), with_peak_day, _ctx())
    assert got["loss"].value == pytest.approx(0.2)  # -0.5 on the peak day would give 0.6
    assert got == episode_measures(_episode(), without, _ctx())


def _step_cpi(end=END) -> pd.Series:
    """100 up to the 2000-12-31 figure, 110 from the 2001-01-31 figure on, indexed by
    availability date: the January 2002 raise is +10%, every other raise is 0."""
    months = pd.date_range("1998-01-31", end, freq="ME")
    return pd.Series(np.where(months <= pd.Timestamp("2000-12-31"), 100.0, 110.0), index=months)


def _income(peak: str, years: int, end: pd.Timestamp = END) -> Cell:
    cpi = _step_cpi(end)
    cal = CALENDAR[end >= CALENDAR]
    ctx = Context(cal, cpi, (0.12,), (years,), end)
    first = cal[cal > pd.Timestamp(peak)][0]
    r = pd.Series(0.0, index=cal[cal >= first])
    return episode_measures(_episode(peak=pd.Timestamp(peak)), r, ctx)[income_key(0.12, years)]


def test_income_with_a_cpi_step_in_the_horizon():
    # 1% of the start a month (0.12 / 12). Zero returns, so balance = 1 - withdrawals.
    # Peak 2000-01-03, horizon 2003-01-03 (a Friday, itself a trading day).
    # 2000: 12 x 0.01 = 0.12; 2001: raise 0 (CPI 100 / 100): 12 x 0.01 = 0.12;
    # 2002: raise +10% (110 / 100): 12 x 0.011 = 0.132;
    # Jan 2003 (2003-01-01 is on the calendar): raise 0 (110 / 110): 0.011.
    # Total 0.383, nominal 0.617; real = 0.617 / (110 / 100) = 0.5609090909...
    cell = _income("2000-01-03", 3)
    assert cell.value == pytest.approx(0.617 / 1.1, abs=1e-9)
    assert cell.note == ""


def test_income_from_a_september_peak():
    # Peak Friday 2000-09-01, first withdrawal on Monday 2000-09-04, horizon 2002-09-01
    # (Sunday): balance read on Friday 2002-08-30.
    # 2000: Sep..Dec = 4 x 0.01 = 0.04; 2001: raise 0: 12 x 0.01 = 0.12;
    # 2002: raise +10%: Jan..Aug = 8 x 0.011 = 0.088. Total 0.248, nominal 0.752;
    # real = 0.752 / (110 / 100) = 0.68363636...
    cell = _income("2000-09-01", 2)
    assert cell.value == pytest.approx(0.752 / 1.1, abs=1e-9)


def test_the_income_end_year_is_capped_at_the_data_end_year():
    # Data and CPI end 2004-12-31: withdrawal amounts for 2005+ cannot be built (no CPI),
    # so the path must stop at the data end year (2004 < 2000 + 11). Peak 2000-01-03,
    # horizon 2004-01-03 (Saturday): read on Friday 2004-01-02.
    # 2000: 0.12; 2001: 0.12; 2002: 12 x 0.011 = 0.132; 2003: raise 0: 0.132;
    # Jan 2004 (2004-01-01): 0.011. Total 0.515, nominal 0.485; real = 0.485 / 1.1.
    cell = _income("2000-01-03", 4, end=pd.Timestamp("2004-12-31"))
    assert cell.value == pytest.approx(0.485 / 1.1, abs=1e-9)


def test_a_fall_after_the_window_end_does_not_count():
    r = _returns({"2005-01-03": -0.5})
    cells = episode_measures(_episode(window_end=pd.Timestamp("2003-01-02")), r, _ctx())
    assert cells["loss"].value == 0.0
    assert cells["recover"].value == 0.0
    inside = episode_measures(_episode(window_end=pd.Timestamp("2006-01-02")), r, _ctx())
    assert inside["loss"].value == pytest.approx(0.5)


def test_recovery_to_one_within_float_error_counts():
    back = float(np.nextafter(2.0, 0.0)) - 1.0  # 0.5 x (1 + back) = 0.9999999999999999
    r = _returns({"2000-02-01": -0.5, "2000-03-01": back})
    assert float((1.0 + r).cumprod().iloc[-1]) < 1.0  # a strict comparison would miss it
    cells = episode_measures(_episode(), r, _ctx())
    assert cells["recover"].value == 2
    assert cells["recover"].note == ""


def test_a_dip_of_float_error_only_is_zero_months():
    r = _returns({"2000-02-01": float(np.nextafter(1.0, 0.0)) - 1.0})
    assert episode_measures(_episode(), r, _ctx())["recover"].value == 0.0


def test_empty_returns_are_no_signal():
    r = pd.Series([], index=pd.DatetimeIndex([]), dtype=float)
    cells = episode_measures(_episode(), r, _ctx())
    assert {c.note for c in cells.values()} == {NO_SIGNAL}


def test_a_window_that_ends_before_the_first_return_is_data_ends():
    cells = episode_measures(_episode(window_end=PEAK), _returns({}), _ctx())
    assert {c.note for c in cells.values()} == {NA_DATA}
    assert all(c.value is None for c in cells.values())


OWN = {
    "SPY": pd.Timestamp("1993-01-29"),
    "QQQ": pd.Timestamp("1999-03-10"),
    "SHY": pd.Timestamp("2002-07-30"),
    "IEF": pd.Timestamp("2002-07-30"),
    "TLT": pd.Timestamp("2002-07-30"),
    "GLD": pd.Timestamp("2004-11-18"),
    "RSP": pd.Timestamp("2003-04-30"),
}
GOLD_FUTURES = pd.Timestamp("2000-08-30")


def test_no_mark_when_every_held_fund_has_its_own_prices():
    assert cell_marks(pd.Timestamp("2008-01-02"), {"SPY", "IEF"}, OWN, GOLD_FUTURES) == ""


def test_dagger_when_any_held_fund_is_a_stand_in_on_the_first_day():
    assert cell_marks(pd.Timestamp("1999-01-04"), {"SPY", "QQQ"}, OWN, GOLD_FUTURES) == DAGGER


def test_dagger_covers_both_branches_and_every_blend_part():
    # a switching rule holds QQQ or GLD; a blend adds SHY
    held = {"QQQ", "GLD", "SHY"}
    assert cell_marks(pd.Timestamp("2003-01-02"), held, OWN, GOLD_FUTURES) == DAGGER
    assert cell_marks(pd.Timestamp("2003-01-02"), {"QQQ"}, OWN, GOLD_FUTURES) == ""


def test_double_dagger_only_for_gold_before_the_first_futures_close():
    assert cell_marks(pd.Timestamp("2001-01-02"), {"GLD"}, OWN, GOLD_FUTURES) == DAGGER
    assert cell_marks(pd.Timestamp("1975-01-02"), {"SPY"}, OWN, GOLD_FUTURES) == DAGGER
    both = cell_marks(pd.Timestamp("1975-01-02"), {"GLD"}, OWN, GOLD_FUTURES)
    assert both == DAGGER + DOUBLE_DAGGER


def test_a_cell_can_carry_both_marks():
    assert cell_marks(pd.Timestamp("1975-01-02"), {"QQQ", "GLD"}, OWN, GOLD_FUTURES) == "†‡"


def test_marks_go_only_on_cells_with_a_number():
    cells = {"loss": Cell(0.1), "x": Cell(None, NO_SIGNAL), "y": Cell(None, NA_DATA)}
    marked = apply_marks(cells, "†")
    assert marked["loss"].marks == "†"
    assert marked["x"].marks == ""
    assert marked["y"].marks == ""


def test_summary_skips_cells_without_a_number_and_states_the_count():
    cells = [
        ("a", Cell(0.10)),
        ("b", Cell(None, NO_SIGNAL)),
        ("c", Cell(0.30)),
        ("d", Cell(None, NA_DATA)),
        ("e", Cell(0.20)),
    ]
    s = summarize(cells, higher_is_worse=True)
    assert s == Summary(median=pytest.approx(0.20), worst=0.30, worst_label="c", count=3, total=5)


def test_summary_lower_is_worse_for_balances():
    cells = [("a", Cell(0.9)), ("b", Cell(0.0, "depleted 2008-04")), ("c", Cell(0.5))]
    s = summarize(cells, higher_is_worse=False)
    assert s.worst == 0.0
    assert s.worst_label == "b"
    assert s.median == pytest.approx(0.5)


def test_not_recovered_ranks_as_the_longest_recovery():
    cells = [("a", Cell(10.0)), ("b", Cell(math.inf, NOT_RECOVERED)), ("c", Cell(30.0))]
    s = summarize(cells, higher_is_worse=True)
    assert math.isinf(s.worst)
    assert s.worst_label == "b"
    assert s.median == 30.0


def test_dagger_boundary_a_window_starting_on_the_first_own_price_is_unmarked():
    assert cell_marks(OWN["QQQ"], {"QQQ"}, OWN, GOLD_FUTURES) == ""
    assert cell_marks(OWN["QQQ"] - pd.Timedelta(days=1), {"QQQ"}, OWN, GOLD_FUTURES) == DAGGER


def test_double_dagger_boundary_a_window_starting_on_the_first_futures_close_is_unmarked():
    start = pd.Timestamp("2000-08-30")
    # GLD has no own price yet, so the dagger stays; only the double dagger is pinned
    assert cell_marks(start, {"GLD"}, OWN, start) == DAGGER
    day_before = start - pd.Timedelta(days=1)
    assert cell_marks(day_before, {"GLD"}, OWN, start) == DAGGER + DOUBLE_DAGGER


def test_median_of_an_even_count_with_inf_is_inf():
    cells = [("a", Cell(10.0)), ("b", Cell(math.inf, NOT_RECOVERED))]
    s = summarize(cells, higher_is_worse=True)
    assert math.isinf(s.median)
    assert s.worst_label == "b"


def test_summary_with_no_usable_cell():
    s = summarize([("a", Cell(None, NO_SIGNAL))], higher_is_worse=True)
    assert s == Summary(None, None, "", 0, 1)
