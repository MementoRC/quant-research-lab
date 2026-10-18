"""What-if shock (spec: docs/methodology/whatif-shock.md): qrl.shock and its three
public aliases. Offline: the shipped config/decision.yaml plus synthetic prices
and CPI. Existing tests are untouched."""

from __future__ import annotations

import pandas as pd
import pytest
from decision_helpers import CANDIDATES, END, ROOT, stress_cfg

from qrl import decision, decision_config, decision_report
from qrl.core_compare import Candidate
from qrl.decision_config import Portfolio, held_tickers, load_decision_config
from qrl.shock import (
    FUND_GROUP,
    Shock,
    cash_returns,
    check_fund_map,
    fund_return,
    load_shock,
    stretch_days,
    stretch_returns,
)


def test_shock_public_aliases_are_the_private_objects():
    assert decision.first_years is decision._first_years
    assert decision_config.ID_PATTERN is decision_config._ID
    assert decision_report.below_peak is decision_report._below_peak


Y1 = {"stocks": -0.30, "gold": 0.20, "long_bonds": -0.15, "short_bonds": 0.01, "inflation": 0.09}
Y2 = {"stocks": -0.10, "gold": 0.10, "long_bonds": -0.10, "short_bonds": 0.02, "inflation": 0.08}


def _year_text(year=None, **override):
    """One YAML flow mapping; an override of None drops that key, a string is
    written raw (so "true", "'x'", ".nan" reach YAML as such)."""
    values = {**(year or Y1), **override}
    return "{" + ", ".join(f"{k}: {v}" for k, v in values.items() if v is not None) + "}"


def _shock_text(*years, name="stagflation-5y"):
    return f"name: {name}\nyears:\n" + "".join(f"  - {y}\n" for y in years)


GOOD_SHOCK = _shock_text(_year_text(Y1), _year_text(Y2))


def _shock_file(tmp_path, text=GOOD_SHOCK):
    path = tmp_path / "shock.yaml"
    path.write_text(text)
    return path


def test_load_shock_reads_a_valid_file(tmp_path):
    shock = load_shock(_shock_file(tmp_path))
    assert shock == Shock("stagflation-5y", (Y1, Y2))
    assert all(isinstance(v, float) for year in shock.years for v in year.values())


def test_load_shock_accepts_the_bounds_and_ten_years(tmp_path):
    text = _shock_text(
        _year_text(stocks=2, gold=-0.999, inflation=-0.1), _year_text(inflation=0.3), name="A_b-9"
    )
    shock = load_shock(_shock_file(tmp_path, text))
    assert shock.years[0]["stocks"] == 2.0
    assert shock.years[1]["inflation"] == 0.3
    ten = _shock_text(*[_year_text()] * 10)
    assert len(load_shock(_shock_file(tmp_path, ten)).years) == 10


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("name: [unclosed\n", "not valid YAML"),
        ("", "must be a mapping"),
        ("- a\n- b\n", "must be a mapping"),
        ("name: x\n", "missing key"),
        (GOOD_SHOCK + "extra: 1\n", "unknown key"),
        (_shock_text(_year_text(), name="bad/name"), "must match"),
        (_shock_text(_year_text(), name="'../x'"), "must match"),
        (_shock_text(_year_text(), name="123"), "must match"),
        ("name: x\nyears: []\n", "1 to 10"),
        ("name: x\nyears: {a: 1}\n", "1 to 10"),
        (_shock_text(*[_year_text()] * 11), "1 to 10"),
        ("name: x\nyears:\n  - [1, 2]\n", "must be a mapping"),
        (_shock_text(_year_text(inflation=None)), "missing key"),
        (_shock_text(_year_text(cash=0.0)), "unknown key"),
        (_shock_text(_year_text(stocks="true")), "not a finite number"),
        (_shock_text(_year_text(stocks="'x'")), "not a finite number"),
        (_shock_text(_year_text(stocks=".nan")), "not a finite number"),
        (_shock_text(_year_text(gold=".inf")), "not a finite number"),
        (_shock_text(_year_text(stocks=-1)), "above -1"),
        (_shock_text(_year_text(short_bonds=-1.5)), "above -1"),
        (_shock_text(_year_text(gold=2.01)), "at most 2"),
        (_shock_text(_year_text(inflation=0.31)), "inflation"),
        (_shock_text(_year_text(inflation=-0.11)), "inflation"),
    ],
)
def test_load_shock_refuses(tmp_path, text, match):
    with pytest.raises(ValueError, match=match):
        load_shock(_shock_file(tmp_path, text))


def test_load_shock_refuses_a_missing_file(tmp_path):
    with pytest.raises(ValueError, match="cannot be read"):
        load_shock(tmp_path / "nope.yaml")


def test_load_shock_refuses_an_unreadable_path(tmp_path):
    with pytest.raises(ValueError, match="cannot be read"):
        load_shock(tmp_path)  # a directory


@pytest.fixture(scope="module")
def shipped():
    return load_decision_config(ROOT / "config" / "decision.yaml", CANDIDATES, stress_cfg(), END)


def test_fund_map_covers_exactly_the_held_funds(shipped):
    assert held_tickers(shipped.portfolios) == set(FUND_GROUP)
    check_fund_map(shipped.portfolios)  # no refusal


@pytest.mark.parametrize(
    ("fund", "group"),
    [
        ("SPY", "stocks"),
        ("QQQ", "stocks"),
        ("RSP", "stocks"),
        ("GLD", "gold"),
        ("TLT", "long_bonds"),
        ("SHY", "short_bonds"),
    ],
)
def test_fund_return_is_the_group_return(fund, group):
    for year in (Y1, Y2):
        assert fund_return(fund, year) == year[group]


def test_ief_is_the_midpoint_of_long_and_short_bonds():
    for year in (Y1, Y2):
        assert fund_return("IEF", year) == (year["long_bonds"] + year["short_bonds"]) / 2
    assert fund_return("IEF", Y1) == pytest.approx(-0.07)


def _foreign():
    cand = Candidate("X", "x", "core_mix", {"risk_on": {"EFA": 0.5, "SPY": 0.5}})
    return Portfolio("X", "x", ((cand, 1.0),))


def test_check_fund_map_refuses_a_held_fund_outside_the_map(shipped):
    with pytest.raises(ValueError, match="no shock group"):
        check_fund_map([*shipped.portfolios, _foreign()])


def test_fund_return_refuses_a_fund_outside_the_map():
    with pytest.raises(ValueError, match="no shock group"):
        fund_return("EFA", Y1)


SHOCK2 = Shock("t2", (Y1, Y2))
SHOCK10 = Shock(
    "t10", tuple({**Y2, "short_bonds": 0.01 * k, "inflation": 0.01 * k} for k in range(10))
)


def test_stretch_days_are_weekdays_from_2_january():
    days = stretch_days(2005, 1)
    assert days[0] == pd.Timestamp("2004-01-02")  # 1 Jan 2004 (a Thursday) is skipped
    assert days[-1] == pd.Timestamp("2004-12-31")
    assert (days.dayofweek < 5).all()
    assert len(days) == len(pd.bdate_range("2004-01-01", "2004-12-31")) - 1


def test_stretch_first_day_when_2_january_is_a_weekend():
    assert stretch_days(2011, 1)[0] == pd.Timestamp("2010-01-04")  # 2 Jan 2010: a Saturday
    assert stretch_days(2012, 1)[0] == pd.Timestamp("2011-01-03")  # 2 Jan 2011: a Sunday
    assert stretch_days(2006, 1)[-1] == pd.Timestamp("2005-12-30")  # 31 Dec 2005: a Saturday


def test_later_stretch_years_include_1_january_when_a_weekday():
    days = stretch_days(2009, 2)  # 2007 and 2008
    assert days[0] == pd.Timestamp("2007-01-02")  # 1 Jan 2007, a Monday, is skipped
    assert pd.Timestamp("2008-01-01") in days  # a Tuesday, included


@pytest.mark.parametrize("fund", sorted(FUND_GROUP))
def test_stretch_compounds_to_each_funds_yearly_return(fund):
    days = stretch_days(2007, 2)  # 2005 and 2006
    rets = stretch_returns({fund: 1.0}, SHOCK2, days)
    assert rets.index.equals(days)
    for year, values in zip((2005, 2006), SHOCK2.years, strict=True):
        part = rets[rets.index.year == year]
        assert part.nunique() == 1  # spread evenly
        assert float((1.0 + part).prod()) == pytest.approx(
            1.0 + fund_return(fund, values), rel=1e-12
        )


def test_stretch_returns_are_the_weighted_sum_rebalanced_daily():
    days = stretch_days(2007, 2)
    got = stretch_returns({"SPY": 0.6, "IEF": 0.4}, SHOCK2, days)
    spy = stretch_returns({"SPY": 1.0}, SHOCK2, days)
    ief = stretch_returns({"IEF": 1.0}, SHOCK2, days)
    assert got.to_numpy() == pytest.approx((0.6 * spy + 0.4 * ief).to_numpy(), rel=1e-12)
    grown = float((1.0 + got[got.index.year == 2005]).prod())
    weighted = 1.0 + 0.6 * Y1["stocks"] + 0.4 * fund_return("IEF", Y1)
    assert grown != pytest.approx(weighted)  # daily rebalancing: not the yearly weighted sum


def test_cash_leg_in_the_stretch_earns_short_bonds():
    days = stretch_days(2007, 2)
    cash = cash_returns(SHOCK2, days)
    assert cash.equals(stretch_returns({"SHY": 1.0}, SHOCK2, days))
    for year, values in zip((2005, 2006), SHOCK2.years, strict=True):
        part = cash[cash.index.year == year]
        assert float((1.0 + part).prod()) == pytest.approx(1.0 + values["short_bonds"], rel=1e-12)


def test_stretch_days_must_cover_exactly_the_shock_years():
    with pytest.raises(ValueError, match="calendar year"):
        stretch_returns({"SPY": 1.0}, SHOCK2, stretch_days(2008, 3))


def test_ten_year_stretch():
    days = stretch_days(2005, 10)
    assert days[0] == pd.Timestamp("1995-01-02")  # 1 Jan 1995: a Sunday
    assert days[-1] == pd.Timestamp("2004-12-31")
    rets = cash_returns(SHOCK10, days)
    for k in range(10):
        part = rets[rets.index.year == 1995 + k]
        assert float((1.0 + part).prod()) == pytest.approx(1.0 + 0.01 * k, rel=1e-12)
