"""What-if shock (spec: docs/methodology/whatif-shock.md): qrl.shock and its three
public aliases. Offline: the shipped config/decision.yaml plus synthetic prices
and CPI. Existing tests are untouched."""

from __future__ import annotations

from dataclasses import replace

import pandas as pd
import pytest
from decision_helpers import CANDIDATES, END, ROOT, cpi, criteria, prices, stress_cfg

from qrl import decision, decision_config, decision_report
from qrl.core_compare import Candidate
from qrl.decision import (
    all_assumption_returns,
    first_years,
    portfolio_returns,
    start_dates,
    withdrawal_rows,
)
from qrl.decision_config import Portfolio, held_tickers, load_decision_config, portfolio_states
from qrl.decision_withdraw import monthly_withdrawals, path_metrics, usable_cpi, withdrawal_path
from qrl.shock import (
    FUND_GROUP,
    Shock,
    cash_returns,
    check_fund_map,
    extend_config,
    fund_return,
    headline_rows,
    join_returns,
    load_shock,
    run_shock,
    shock_paths,
    shocked_path,
    stretch_cpi,
    stretch_days,
    stretch_returns,
    withdrawal_step,
    worse_state,
)
from qrl.true_cash import cash_leg_returns, mix_returns


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
        (_shock_text(_year_text(inflation=0.31)), r"inflation .* must be in"),
        (_shock_text(_year_text(inflation=-0.11)), r"inflation .* must be in"),
        (_shock_text(_year_text(stocks="1" + "0" * 400)), "not a finite number"),
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


SHOCK3 = Shock("t3", (Y1, Y2, {**Y2, "inflation": -0.02}))


def _jan(series, year):
    """The CPI usable on 1 January of `year`."""
    return usable_cpi(series, pd.Timestamp(year=year, month=1, day=1))


def test_stretch_cpi_dates():
    s = stretch_cpi(SHOCK3, 2010)  # stretch 2007-2009
    assert s.index[0] == pd.Timestamp("2006-12-31")
    assert s.iloc[0] == 100.0
    assert len(s) == 1 + 12 * 3
    assert s.index[-1] == pd.Timestamp("2009-12-31")
    assert s.index.is_monotonic_increasing
    assert (s.index == s.index + pd.offsets.MonthEnd(0)).all()  # every date a month end
    assert list(s.index[1:13].month) == list(range(1, 13))
    assert set(s.index[1:13].year) == {2007}
    assert (s.index[1:] - s.index[:-1]).max() <= pd.Timedelta(days=31)


def test_stretch_cpi_steps_up_by_each_years_inflation():
    s = stretch_cpi(SHOCK3, 2010)
    for k, year in enumerate(SHOCK3.years):
        ratio = _jan(s, 2008 + k) / _jan(s, 2007 + k)
        assert ratio == pytest.approx(1.0 + year["inflation"], rel=1e-12)
    assert _jan(s, 2010) == s.iloc[-1]  # the end level is usable on 1 January Y
    amounts = monthly_withdrawals(0.04, 2007, 2010, s)
    assert amounts[2008] / amounts[2007] == pytest.approx(1.0 + Y1["inflation"], rel=1e-12)


def test_stretch_cpi_is_usable_on_every_stretch_day():
    s = stretch_cpi(SHOCK3, 2010)
    days = stretch_days(2010, 3)
    for day in days:
        usable_cpi(s, day)  # raises "missing CPI" if a value were older than 45 days
    assert usable_cpi(s, days[0]) == 100.0
    assert usable_cpi(s, days[-1]) == s.iloc[-1]


def test_shocked_path_joins_the_real_cpi_with_no_jump():
    real = cpi().loc[:END]
    s = shocked_path(real, SHOCK2, 2005)
    synthetic = stretch_cpi(SHOCK2, 2005)
    join = pd.Timestamp("2004-12-31")
    f = synthetic.iloc[-1] / real.loc[join]
    assert s.index.is_monotonic_increasing
    assert s.index.is_unique  # the real 31 Dec Y-1 value is dropped, not duplicated
    assert s.loc[:join].index.equals(synthetic.index)
    assert s.loc[:join].tolist() == synthetic.tolist()
    assert s.loc[join] == synthetic.iloc[-1]
    assert s.loc[join] == pytest.approx(real.loc[join] * f, rel=1e-12)  # no step at the join
    after = s.loc[s.index > join]
    assert after.index.equals(real.loc[real.index > join].index)
    assert after.tolist() == (real.loc[real.index > join] * f).tolist()


def test_shocked_path_step_ups_are_the_shock_then_the_real_ones():
    real = cpi().loc[:END]
    s = shocked_path(real, SHOCK2, 2005)
    assert _jan(s, 2005) == stretch_cpi(SHOCK2, 2005).iloc[-1]
    assert _jan(s, 2004) / _jan(s, 2003) == pytest.approx(1.0 + Y1["inflation"], rel=1e-12)
    # January Y: the last shock year's inflation
    assert _jan(s, 2005) / _jan(s, 2004) == pytest.approx(1.0 + Y2["inflation"], rel=1e-12)
    for year in range(2006, 2019):  # from January Y+1 the real step-ups
        want = _jan(real, year) / _jan(real, year - 1)
        assert _jan(s, year) / _jan(s, year - 1) == pytest.approx(want, rel=1e-12)


def test_shocked_path_requires_a_real_value_dated_exactly_31_december():
    # 30 Nov 2004 would still be usable on 1 Jan 2005 (32 days old), but the join is strict
    real = cpi().loc[:END].drop([pd.Timestamp("2004-12-31")])
    with pytest.raises(
        ValueError, match="missing CPI: no CPIAUCNS value dated 2004-12-31 for the join"
    ):
        shocked_path(real, SHOCK2, 2005)


def test_shocked_path_refuses_a_nan_on_the_join_date():
    real = cpi().loc[:END].copy()
    real.loc[pd.Timestamp("2004-12-31")] = float("nan")
    with pytest.raises(ValueError, match="for the join"):
        shocked_path(real, SHOCK2, 2005)


def test_join_returns_puts_the_stretch_before_the_real_series():
    stretch = cash_returns(SHOCK2, stretch_days(2005, 2))
    real = pd.Series(0.001, index=pd.bdate_range("2005-01-03", "2005-03-31"))
    joined = join_returns(stretch, real)
    assert len(joined) == len(stretch) + len(real)
    assert joined.index.is_monotonic_increasing
    assert joined.index.is_unique
    assert joined.iloc[: len(stretch)].tolist() == stretch.tolist()
    assert joined.iloc[len(stretch) :].tolist() == real.tolist()


def test_join_returns_refuses_an_overlap():
    stretch = cash_returns(SHOCK2, stretch_days(2005, 2))
    overlap = pd.Series(0.0, index=pd.bdate_range("2004-12-31", "2005-01-31"))
    with pytest.raises(ValueError, match="before the real start"):
        join_returns(stretch, overlap)


def _small(cfg, ids=("A", "CASH", "D"), cash=1, years=(2005, 2006, 2007), rates=(0.02, 0.04)):
    """The shipped config cut down for speed: some portfolios, the first `cash`
    cash rows (their bases must be among `ids`), some start years and rates."""
    by_id = {p.id: p for p in cfg.portfolios}
    return replace(
        cfg,
        portfolios=[by_id[i] for i in ids],
        cash_assumptions=cfg.cash_assumptions[:cash],
        start_years=list(years),
        rates=list(rates),
    )


def _cost():
    return float(criteria()["costs"]["bps_per_unit_turnover"])


def _cut():
    return {k: v.loc[:END] for k, v in prices().items()}


def _starts(cfg, cut):
    return start_dates(pd.DatetimeIndex(cut["close"].index), cfg.start_years, END)


def test_withdrawal_step_gives_the_report_rows_back(shipped):
    """Parity: fed the unshocked paths and the real CPI, the step returns the
    report's own withdrawal rows exactly."""
    cfg = _small(shipped)
    want = withdrawal_rows(cfg, prices(), cpi(), criteria())
    cut, known = _cut(), cpi().loc[:END]
    starts = _starts(cfg, cut)
    got = []
    for p in cfg.portfolios:
        paths = {y: portfolio_returns(p, cut, day, _cost()) for y, day in starts.items()}
        got += withdrawal_step(p.id, paths, dict.fromkeys(paths, known), cfg.rates)
    per_start = {
        y: all_assumption_returns(cfg, cut, known, day, _cost()) for y, day in starts.items()
    }
    for ca in cfg.cash_assumptions:
        paths = {y: rets[ca.id] for y, rets in per_start.items()}
        got += withdrawal_step(ca.id, paths, dict.fromkeys(paths, known), cfg.rates)
    assert len(want) == 4 * 2  # not vacuous: 3 portfolios + 1 cash row, 2 rates
    assert got == want


def test_withdrawal_step_equal_horizon_on_a_small_case():
    real = cpi()
    daily = {2000: 0.0003, 2001: -0.0004, 2002: 0.0001}
    paths = {
        y: pd.Series(r, index=pd.bdate_range(f"{y}-01-02", "2004-12-31")) for y, r in daily.items()
    }
    (row,) = withdrawal_step("X", paths, dict.fromkeys(paths, real), [0.04])
    assert row["horizon_years"] == 3  # last end year 2004 - last key 2002 + 1
    assert row["horizons"] == {2000: 5, 2001: 4, 2002: 3}
    assert first_years(paths[2000], 3).index[-1] == pd.Timestamp("2002-12-31")
    assert first_years(paths[2001], 3).index[-1] == pd.Timestamp("2003-12-31")
    at = {
        y: path_metrics(
            withdrawal_path(first_years(r, 3), monthly_withdrawals(0.04, y, y + 2, real)), real
        )["end_real"]
        for y, r in paths.items()
    }
    assert (row["worst5_end_real"], row["worst5_year"]) == min((v, y) for y, v in at.items())


def test_extend_config_without_a_mix_keeps_the_report_rows(shipped):
    cfg = extend_config(shipped, None, None)
    assert cfg.portfolios == shipped.portfolios
    assert cfg.cash_assumptions == shipped.cash_assumptions
    assert cfg.rates == shipped.rates


def test_extend_config_adds_mix_and_its_cash_row_to_the_full_config(shipped):
    cfg = extend_config(shipped, [("G", 0.5), ("A", 0.3), ("TCASH", 0.2)], 0.045)
    assert [p.id for p in cfg.portfolios] == [*(p.id for p in shipped.portfolios), "MIX"]
    assert [c.id for c in cfg.cash_assumptions] == [
        *(c.id for c in shipped.cash_assumptions),
        "MIX-TCASH",
    ]
    row = cfg.cash_assumptions[-1]
    assert (row.base, row.cash_share, row.real_yield) == ("MIX", 0.2, 0.01)
    assert cfg.rates == [0.02, 0.033, 0.04, 0.045, 0.05]
    assert len(shipped.portfolios) == 27  # not mutated
    assert len(shipped.cash_assumptions) == 7


def test_extend_config_without_tcash_adds_only_mix(shipped):
    cfg = extend_config(shipped, [("A", 0.8), ("CASH", 0.2)], None)
    assert cfg.portfolios[-1].id == "MIX"
    assert cfg.cash_assumptions == shipped.cash_assumptions


def test_extend_config_all_tcash_has_no_mix(shipped):
    cfg = extend_config(shipped, [("TCASH", 1.0)], None)
    assert [p.id for p in cfg.portfolios] == [p.id for p in shipped.portfolios]
    row = cfg.cash_assumptions[-1]
    assert (row.id, row.base, row.cash_share) == ("MIX-TCASH", "CASH", 1.0)


def _odd_yields(cfg):
    rows = list(cfg.cash_assumptions)
    rows[1] = replace(rows[1], real_yield=0.02)
    return replace(cfg, cash_assumptions=tuple(rows))


@pytest.mark.parametrize("given", [[("A", 1.0)], [("A", 0.8), ("TCASH", 0.2)]])
def test_extend_config_with_a_mix_refuses_cash_rows_with_different_yields(shipped, given):
    with pytest.raises(ValueError, match="different real_yield"):
        extend_config(_odd_yields(shipped), given, None)


def test_extend_config_without_a_mix_keeps_cash_rows_with_different_yields(shipped):
    odd = _odd_yields(shipped)
    cfg = extend_config(odd, None, 0.045)  # no MIX, no MIX-TCASH: the report's rows as they are
    assert cfg.cash_assumptions == odd.cash_assumptions
    assert cfg.portfolios == odd.portfolios


@pytest.fixture(scope="module")
def assembled(shipped):
    base = _small(shipped, ids=("A", "B", "CASH", "D"), cash=2, years=(2005, 2006), rates=(0.04,))
    cfg = extend_config(base, [("A", 0.4), ("B", 0.4), ("TCASH", 0.2)], None)
    paths, cpi_by_key = shock_paths(cfg, prices(), cpi(), criteria(), SHOCK2)
    return cfg, paths, cpi_by_key


def test_shock_paths_rows_states_and_keys(assembled):
    _, paths, _ = assembled
    assert list(paths) == ["A", "B", "CASH", "D", "MIX", "A80-TCASH20", "B80-TCASH20", "MIX-TCASH"]
    assert set(paths["A"]) == {"risk_on", "risk_off"}
    assert list(paths["D"]) == ["static"]
    four = {"risk_on+risk_on", "risk_on+risk_off", "risk_off+risk_on", "risk_off+risk_off"}
    assert set(paths["MIX"]) == four  # a mix of two switching cores
    assert set(paths["MIX-TCASH"]) == four
    assert set(paths["A80-TCASH20"]) == {"risk_on", "risk_off"}  # a TCASH row, switching base
    for states in paths.values():
        for by_key in states.values():
            assert list(by_key) == [2003, 2004]  # keyed by Y - N


def test_shock_paths_are_the_stretch_then_the_report_returns(assembled):
    cfg, paths, _ = assembled
    cut = _cut()
    starts = _starts(cfg, cut)
    by_id = {p.id: p for p in cfg.portfolios}
    for pid in ("A", "D", "MIX"):
        real = {y: portfolio_returns(by_id[pid], cut, day, _cost()) for y, day in starts.items()}
        for state, mix in portfolio_states(by_id[pid]).items():
            for y, day in starts.items():
                path = paths[pid][state][y - 2]
                days = stretch_days(y, 2)
                assert path.index[0] == days[0]
                assert len(path) == len(days) + len(real[y])
                assert path.loc[: days[-1]].tolist() == stretch_returns(mix, SHOCK2, days).tolist()
                assert path.loc[day:].index.equals(real[y].index)
                assert path.loc[day:].tolist() == real[y].tolist()  # exactly the report's


def test_shock_paths_tcash_rows_mix_the_base_state_with_short_bonds(assembled):
    cfg, paths, _ = assembled
    cut, known = _cut(), cpi().loc[:END]
    by_id = {p.id: p for p in cfg.portfolios}
    for y, day in _starts(cfg, cut).items():
        report = all_assumption_returns(cfg, cut, known, day, _cost())
        days = stretch_days(y, 2)
        for ca in cfg.cash_assumptions:
            for state, mix in portfolio_states(by_id[ca.base]).items():
                path = paths[ca.id][state][y - 2]
                want = mix_returns(
                    stretch_returns(mix, SHOCK2, days), cash_returns(SHOCK2, days), ca.cash_share
                )
                assert path.loc[: days[-1]].tolist() == want.tolist()
                assert path.loc[day:].tolist() == report[ca.id].tolist()


def test_true_cash_follows_short_bonds_then_cpi_plus_the_real_yield(shipped):
    base = _small(shipped, ids=("A", "CASH"), cash=1, years=(2005,), rates=(0.04,))
    cfg = extend_config(base, [("TCASH", 1.0)], None)
    paths, _ = shock_paths(cfg, prices(), cpi(), criteria(), SHOCK2)
    (by_key,) = paths["MIX-TCASH"].values()
    path = by_key[2003]
    cut = _cut()
    day = _starts(cfg, cut)[2005]
    for year, values in zip((2003, 2004), SHOCK2.years, strict=True):
        part = path[path.index.year == year]
        assert float((1.0 + part).prod()) == pytest.approx(1.0 + values["short_bonds"], rel=1e-12)
    real = path.loc[day:]
    leg = cash_leg_returns(
        pd.DatetimeIndex(real.index), pd.DatetimeIndex(cut["close"].index), cpi().loc[:END], 0.01
    )
    assert real.to_numpy() == pytest.approx(leg.to_numpy(), rel=1e-12, abs=1e-15)


def test_shock_paths_cpi_per_key_is_each_start_years_splice(assembled):
    _, _, cpi_by_key = assembled
    known = cpi().loc[:END]
    assert list(cpi_by_key) == [2003, 2004]
    for key, year in ((2003, 2005), (2004, 2006)):
        assert cpi_by_key[key].equals(shocked_path(known, SHOCK2, year))


def test_equal_horizon_cut_dates_of_a_shocked_path(assembled):
    _, paths, _ = assembled
    # H = H0 + N = (2018 - 2006 + 1) + 2 = 15; a path keyed Y-N is cut at the end of Y+H0-1
    assert first_years(paths["D"]["static"][2003], 15).index[-1] == pd.Timestamp("2017-12-29")
    assert first_years(paths["D"]["static"][2004], 15).index[-1] == pd.Timestamp("2018-12-31")


def test_ten_year_shock_paths(shipped):
    cfg = _small(shipped, ids=("CASH",), cash=0, years=(2005,), rates=(0.04,))
    paths, cpi_by_key = shock_paths(cfg, prices(), cpi(), criteria(), SHOCK10)
    path = paths["CASH"]["static"][1995]
    assert path.index[0] == pd.Timestamp("1995-01-02")
    assert sorted(set(path.index.year)) == list(range(1995, 2019))
    assert cpi_by_key[1995].index[0] == pd.Timestamp("1994-12-31")


def _at(**values):
    return {name: {"worst_end_real": v} for name, v in values.items()}


def test_worse_state_is_the_lower_worst_start_value():
    assert worse_state(_at(risk_on=0.5, risk_off=0.3)) == "risk_off"
    assert worse_state(_at(risk_on=0.2, risk_off=0.3)) == "risk_on"


def test_worse_state_tie_goes_to_the_greater_name():
    assert worse_state(_at(risk_on=0.3, risk_off=0.3)) == "risk_on"
    assert worse_state(_at(risk_on=0.0, risk_off=0.0)) == "risk_on"  # every state depleted
    four = {
        "risk_off+risk_off": {"worst_end_real": 0.1},
        "risk_on+risk_off": {"worst_end_real": 0.1},
        "risk_on+risk_on": {"worst_end_real": 0.4},
    }
    assert worse_state(four) == "risk_on+risk_off"


@pytest.fixture(scope="module")
def small_report(shipped):
    base = _small(shipped, years=(2005, 2006), rates=(0.04,))
    cfg = extend_config(base, [("A", 0.8), ("CASH", 0.2)], None)
    return base, cfg, run_shock(cfg, prices(), cpi(), criteria(), SHOCK2, "cd" * 32)


def _numbers(rows):
    return [{k: v for k, v in r.items() if k != "portfolio"} for r in rows]


def test_run_shock_report_fields(small_report):
    _, cfg, report = small_report
    assert (report["name"], report["n"], report["years"]) == ("t2", 2, [Y1, Y2])
    assert report["data_end"] == "2018-12-31"
    assert report["decision_sha256"] == cfg.sha256
    assert report["candidates_sha256"] == cfg.candidates_sha256
    assert report["stress_sha256"] == "cd" * 32
    assert (report["rates"], report["start_years"]) == ([0.04], [2005, 2006])
    assert report["real_yields"] == [0.01]
    assert [r["portfolio"] for r in report["rows"]] == ["A", "CASH", "D", "MIX", "A80-TCASH20"]


def test_run_shock_headlines_the_worse_state(small_report):
    _, _, report = small_report
    rows = {r["portfolio"]: r for r in report["rows"]}
    a = rows["A"]
    assert set(a["states"]) == {"risk_on", "risk_off"}
    # the stretch sinks stocks (QQQ) and lifts gold, and the real part is shared
    assert a["state"] == "risk_on"
    assert a["state"] == worse_state(a["states"])
    assert a["shocked"] is a["states"][a["state"]]
    assert a["shocked"]["worst_end_real"] == min(s["worst_end_real"] for s in a["states"].values())
    assert rows["D"]["state"] is None
    assert list(rows["D"]["states"]) == ["static"]
    assert rows["A80-TCASH20"]["state"] == worse_state(rows["A80-TCASH20"]["states"])


def test_run_shock_no_shock_columns_are_the_report_rows(shipped, small_report):
    base, _, report = small_report
    want = withdrawal_rows(base, prices(), cpi(), criteria())
    assert [r["no_shock"] for r in report["rows"] if r["portfolio"] != "MIX"] == want
    by_id = {p.id: p for p in shipped.portfolios}
    blend = replace(base, portfolios=[by_id["A80-CASH20"]], cash_assumptions=())
    ref = withdrawal_rows(blend, prices(), cpi(), criteria())
    mix = [r["no_shock"] for r in report["rows"] if r["portfolio"] == "MIX"]
    assert _numbers(mix) == _numbers(ref)  # parity on MIX too
    assert mix  # not vacuous


def test_run_shock_equal_horizon_is_h0_plus_n(small_report):
    _, _, report = small_report
    for row in report["rows"]:
        s, b = row["shocked"], row["no_shock"]
        assert b["horizon_years"] == 2018 - 2006 + 1  # H0
        assert s["horizon_years"] == b["horizon_years"] + 2  # H0 + N
        assert (s["first_year"], b["first_year"]) == (2003, 2005)
        assert s["horizons"] == {2003: 16, 2004: 15}


def test_cash_path_through_a_one_year_stretch_in_closed_form(shipped):
    cfg = _small(shipped, ids=("CASH",), cash=0, years=(2005,), rates=(0.04,))
    shock = Shock("t1", (Y1,))
    paths, cpi_by_key = shock_paths(cfg, prices(), cpi(), criteria(), shock)
    path = paths["CASH"]["static"][2004]
    days = stretch_days(2005, 1)
    rate, w = 0.04, 0.04 / 12
    d = (1.0 + Y1["short_bonds"]) ** (1.0 / len(days)) - 1.0  # the geometric daily return
    month_starts = [days[days.month == m][0] for m in range(1, 13)]
    remaining = [int((days >= first).sum()) for first in month_starts]
    # each month's withdrawal, taken before that day's return, then compounded to year end
    closed = (1.0 + d) ** len(days) - w * sum((1.0 + d) ** c for c in remaining)
    monthly = monthly_withdrawals(rate, 2004, 2018, cpi_by_key[2004])
    values = withdrawal_path(path, monthly).values
    assert values.loc[days[-1]] == pytest.approx(closed, rel=1e-12)
    assert monthly[2004] == w
    assert monthly[2005] == pytest.approx(w * (1.0 + Y1["inflation"]), rel=1e-12)


def test_run_shock_refuses_a_held_fund_outside_the_map(shipped):
    cfg = _small(shipped, years=(2005,), rates=(0.04,))
    cfg = replace(cfg, portfolios=[*cfg.portfolios, _foreign()])
    with pytest.raises(ValueError, match="no shock group"):
        run_shock(cfg, prices(), cpi(), criteria(), SHOCK2, "cd" * 32)


def _flat(daily: float, key: int) -> pd.Series:
    return pd.Series(daily, index=pd.bdate_range(f"{key}-01-02", "2004-12-31"))


def _two_state_paths():
    """State `a` is the better one at the first start key (2000) and the worse
    one at its worst start key (2001); state `b` is the reverse."""
    return {
        "a": {2000: _flat(0.0006, 2000), 2001: _flat(-0.0004, 2001)},
        "b": {2000: _flat(0.0002, 2000), 2001: _flat(-0.0001, 2001)},
    }


def _no_shock(rates):
    return [{"portfolio": "X", "rate": r} for r in rates]


def test_headline_is_the_worst_start_year_pick_not_the_first_start_years():
    real = cpi()
    rates = [0.04]
    (row,) = headline_rows(
        "X", _two_state_paths(), dict.fromkeys((2000, 2001), real), rates, _no_shock(rates)
    )
    a, b = row["states"]["a"], row["states"]["b"]
    # the two rankings disagree: a leads at the first key, b leads at the worst key
    assert a["first"]["end_real"] > b["first"]["end_real"]
    assert a["worst_end_real"] < b["worst_end_real"]
    assert (a["worst_year"], b["worst_year"]) == (2001, 2001)
    assert row["state"] == "a"
    assert row["shocked"] is a


def test_headline_state_is_chosen_per_rate():
    real = cpi()
    rates = [0.0, 0.5]
    rows = headline_rows(
        "X", _two_state_paths(), dict.fromkeys((2000, 2001), real), rates, _no_shock(rates)
    )
    for row in rows:
        assert row["state"] == worse_state(row["states"])
        assert row["shocked"] is row["states"][row["state"]]
    # no withdrawals: a ends lower at its worst key; 50% a year depletes both (0 = 0), the greater name wins
    assert rows[0]["states"]["a"]["worst_end_real"] < rows[0]["states"]["b"]["worst_end_real"]
    assert (
        rows[1]["states"]["a"]["worst_end_real"] == rows[1]["states"]["b"]["worst_end_real"] == 0.0
    )
    assert [r["state"] for r in rows] == ["a", "b"]


def test_withdrawal_step_uses_each_keys_own_cpi(shipped):
    real = cpi().loc[:END]
    other = real * (1.0 + 0.5 * (real.index - real.index[0]).days / 3650.0)
    cpis = {2000: real, 2001: other}
    paths = {2000: _flat(0.0003, 2000), 2001: _flat(0.0002, 2001)}
    cfg = _small(shipped, rates=(0.04,))
    (row,) = withdrawal_step("X", paths, cpis, [0.04])
    for key in paths:
        (alone,) = decision._withdrawal_rows_for("X", {key: paths[key]}, cfg, cpis[key])
        assert row["per_year"][key] == alone["per_year"][key]
    # the equal-horizon figures: each key's path cut to the row's horizon, own CPI
    horizon = row["horizon_years"]
    at_horizon = {}
    for key in paths:
        cut = {key: first_years(paths[key], horizon)}
        (alone,) = decision._withdrawal_rows_for("X", cut, cfg, cpis[key])
        assert alone["horizon_years"] == horizon
        at_horizon[key] = alone["worst5_end_real"]
    worst5_real, worst5_year = min((v, k) for k, v in at_horizon.items())
    assert (row["worst5_end_real"], row["worst5_year"]) == (worst5_real, worst5_year)
    swapped = decision._withdrawal_rows_for("X", {2001: paths[2001]}, cfg, real)[0]
    assert row["per_year"][2001] != swapped["per_year"][2001]  # one CPI for all keys would differ


def test_run_shock_refuses_missing_cpi(shipped):
    cfg = _small(shipped, years=(2005,), rates=(0.04,))
    holes = cpi().drop([pd.Timestamp("2004-11-30"), pd.Timestamp("2004-12-31")])
    with pytest.raises(ValueError, match="missing CPI"):
        run_shock(cfg, prices(), holes, criteria(), SHOCK2, "cd" * 32)
