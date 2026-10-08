import hashlib

import numpy as np
import pandas as pd
import pytest
from decision_helpers import cpi as helper_cpi
from decision_helpers import criteria as helper_criteria
from decision_helpers import load as helper_load
from decision_helpers import prices as helper_prices

from qrl.longrun import (
    CASH_ASSUMPTION,
    LongrunConfig,
    Paths,
    block_starts,
    cash_assumption_returns,
    load_longrun_config,
    month_indices,
    monthly_inflation,
    monthly_returns,
    run_longrun,
    run_paths,
    summarize,
)
from qrl.longrun_report import render_markdown

DEC_SHA = "d" * 64


def _write(tmp_path, text):
    p = tmp_path / "longrun.yaml"
    p.write_text(text, encoding="utf-8")
    return p


GOOD = f"""version: 1
decision_sha256: "{DEC_SHA}"
seed: 7
n_paths: 50
block_months: 12
horizon_years: 30
real_floor: 0.5
withdrawal_rates: [0.02, 0.05]
cash_real_yield: 0.01
"""


def test_load_longrun_config_reads_every_key_and_hashes_the_file(tmp_path):
    path = _write(tmp_path, GOOD)
    cfg = load_longrun_config(path, DEC_SHA)
    assert cfg == LongrunConfig(
        seed=7,
        n_paths=50,
        block_months=12,
        horizon_years=30,
        real_floor=0.5,
        rates=[0.02, 0.05],
        cash_real_yield=0.01,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def test_load_longrun_config_refuses_a_changed_decision_yaml(tmp_path):
    with pytest.raises(ValueError, match="decision.yaml"):
        load_longrun_config(_write(tmp_path, GOOD), "e" * 64)


def test_load_longrun_config_refuses_a_missing_key(tmp_path):
    with pytest.raises(ValueError, match="seed"):
        load_longrun_config(_write(tmp_path, GOOD.replace("seed: 7\n", "")), DEC_SHA)


def test_load_longrun_config_refuses_a_horizon_not_made_of_whole_blocks(tmp_path):
    text = GOOD.replace("block_months: 12", "block_months: 7")
    with pytest.raises(ValueError, match="block"):
        load_longrun_config(_write(tmp_path, text), DEC_SHA)


def test_load_longrun_config_refuses_a_missing_file(tmp_path):
    with pytest.raises(ValueError, match="cannot be loaded"):
        load_longrun_config(tmp_path / "nope.yaml", DEC_SHA)


def test_load_longrun_config_refuses_malformed_yaml(tmp_path):
    with pytest.raises(ValueError, match="cannot be loaded"):
        load_longrun_config(_write(tmp_path, "version: [1\n"), DEC_SHA)


def test_monthly_returns_compounds_each_calendar_month():
    idx = pd.to_datetime(["2005-01-03", "2005-01-04", "2005-02-01"])
    out = monthly_returns(pd.Series([0.10, 0.10, -0.5], index=idx))
    assert list(out.index) == [pd.Period("2005-01", "M"), pd.Period("2005-02", "M")]
    assert out.iloc[0] == pytest.approx(0.21)
    assert out.iloc[1] == pytest.approx(-0.5)


def test_monthly_returns_refuses_nan():
    idx = pd.to_datetime(["2005-01-03", "2005-01-04"])
    with pytest.raises(ValueError, match="NaN"):
        monthly_returns(pd.Series([0.1, np.nan], index=idx))


def _cpi_levels(n):
    # deterministic, distinct month-over-month growth (0.1% .. 0.7%)
    return 100 * np.cumprod(1 + 0.001 * (1 + np.arange(n) % 7))


def _cpi_by_availability(start="2004-06", end="2006-12", levels=None):
    # value for month M, usable from the last day of month M+1 (qrl.macro lag)
    months = pd.period_range(start, end, freq="M")
    avail = [(m + 1).to_timestamp(how="end").normalize() for m in months]
    values = _cpi_levels(len(months)) if levels is None else np.asarray(levels, dtype=float)
    return pd.Series(values, index=pd.DatetimeIndex(avail))


def test_monthly_inflation_uses_usable_cpi_at_consecutive_month_ends():
    start = pd.Period("2004-06", freq="M")
    levels = _cpi_levels(len(pd.period_range("2004-06", "2006-12", freq="M")))

    def level(month):
        return levels[(pd.Period(month, freq="M") - start).n]

    # Apr 30 2005 is a Saturday: March's CPI is usable on that calendar day.
    months = pd.period_range("2005-01", "2005-04", freq="M")
    out = monthly_inflation(_cpi_by_availability(levels=levels), months)
    assert list(out.index) == list(months)

    # On month m's calendar end the usable value is month m-1's (published at
    # the end of m), so inflation(m) = level[m-1] / level[m-2] - 1 for every m.
    expected = [
        level("2004-12") / level("2004-11") - 1,  # Jan
        level("2005-01") / level("2004-12") - 1,  # Feb
        level("2005-02") / level("2005-01") - 1,  # Mar
        level("2005-03") / level("2005-02") - 1,  # Apr (ends on a Saturday)
    ]
    assert out.to_numpy() == pytest.approx(expected, abs=1e-12)

    # Regression: reading the last trading day (Fri Apr 29) would see only
    # February's value on both sides and give exactly 0.0 for April.
    assert out.iloc[3] != 0.0
    assert abs(out.iloc[3]) > 1e-9


def test_monthly_inflation_refuses_stale_cpi_mid_series():
    # Jan and Feb 2005 values (usable Feb 28 / Mar 31) are missing mid-series;
    # later months are present.
    cpi = _cpi_by_availability().drop(pd.to_datetime(["2005-02-28", "2005-03-31"]))
    months = pd.period_range("2005-01", "2005-03", freq="M")
    # Mar 31: latest usable value is Dec's (dated Jan 31), 59 days old.
    with pytest.raises(ValueError, match="missing CPI"):
        monthly_inflation(cpi, months)


def test_monthly_inflation_refuses_a_missing_cpi():
    months = pd.period_range("2005-01", "2005-03", freq="M")
    with pytest.raises(ValueError, match="missing CPI"):
        monthly_inflation(_cpi_by_availability(end="2004-12"), months)


def test_load_longrun_config_refuses_an_unsupported_version(tmp_path):
    with pytest.raises(ValueError, match="version"):
        load_longrun_config(_write(tmp_path, GOOD.replace("version: 1", "version: 2")), DEC_SHA)


def test_block_starts_same_seed_same_draw_and_in_range():
    a = block_starts(seed=3, n_paths=100, n_blocks=30, n_months=168)
    b = block_starts(seed=3, n_paths=100, n_blocks=30, n_months=168)
    assert a.shape == (100, 30)
    assert np.array_equal(a, b)
    assert a.min() == 0
    assert a.max() == 167


def test_block_starts_different_seed_different_draw():
    a = block_starts(seed=3, n_paths=100, n_blocks=30, n_months=168)
    b = block_starts(seed=4, n_paths=100, n_blocks=30, n_months=168)
    assert not np.array_equal(a, b)


def test_month_indices_wraps_december_2018_to_january_2005():
    starts = np.array([[167, 0]])  # block 1 starts at the last month (Dec 2018)
    idx = month_indices(starts, block_months=12, n_months=168)
    assert idx.shape == (1, 24)
    assert list(idx[0, :12]) == [167, *range(11)]
    assert list(idx[0, 12:]) == list(range(0, 12))


def _flat(n=360, paths=1):
    return np.tile(np.arange(n), (paths, 1))


def test_zero_returns_zero_inflation_five_percent_depletes_in_month_240():
    p = run_paths(np.zeros(360), np.zeros(360), _flat(), rate=0.05)
    assert p.depleted[0] == 240
    assert p.nominal[0, 238] > 0
    assert p.nominal[0, 239] == 0.0


def test_a_depleted_path_stays_zero_even_after_gains():
    r = np.zeros(360)
    r[300:] = 0.5
    p = run_paths(r, np.zeros(360), _flat(), rate=0.05)
    assert (p.nominal[0, 239:] == 0.0).all()
    assert (p.real[0, 239:] == 0.0).all()


def test_withdrawal_comes_out_before_the_months_return():
    r = np.zeros(360)
    r[0] = 0.10
    p = run_paths(r, np.zeros(360), _flat(), rate=0.12)  # 1% a month
    assert p.nominal[0, 0] == pytest.approx((1 - 0.01) * 1.10)


def test_withdrawal_is_raised_every_12_months_by_the_paths_own_inflation():
    infl = np.zeros(360)
    infl[:12] = 0.01  # year one inflation (1.01**12)
    p = run_paths(np.zeros(360), infl, _flat(), rate=0.12)
    taken_year_one = 12 * 0.01
    month_13 = p.nominal[0, 11] - p.nominal[0, 12]
    assert p.nominal[0, 11] == pytest.approx(1 - taken_year_one)
    assert month_13 == pytest.approx(0.01 * 1.01**12)


def test_real_value_is_deflated_by_the_paths_cumulative_inflation():
    infl = np.full(360, 0.002)
    p = run_paths(np.zeros(360), infl, _flat(), rate=0.0)
    assert p.real[0, 11] == pytest.approx(1 / 1.002**12)


def test_run_paths_paths_are_independent_in_one_call():
    returns = np.concatenate([np.full(360, 0.01), np.zeros(360)])
    idx = np.vstack([np.arange(360), np.arange(360, 720)])
    p = run_paths(returns, np.zeros(720), idx, rate=0.05)
    assert p.depleted[1] == 240
    assert (p.nominal[1, 239:] == 0.0).all()
    assert p.depleted[0] == 0
    alone = run_paths(returns[:360], np.zeros(360), np.arange(360)[None, :], 0.05)
    assert np.array_equal(p.nominal[0], alone.nominal[0])


def test_run_paths_raises_follow_each_paths_own_inflation_and_compound():
    infl = np.zeros(720)
    infl[:12] = 0.01
    infl[12:24] = 0.02
    infl[372:384] = 0.03
    idx = np.vstack([np.arange(360), np.arange(360, 720)])
    p = run_paths(np.zeros(720), infl, idx, rate=0.12)
    v0, v1 = p.nominal[0], p.nominal[1]
    assert v0[11] - v0[12] == pytest.approx(0.01 * 1.01**12)
    assert v0[23] - v0[24] == pytest.approx(0.01 * 1.01**12 * 1.02**12)
    assert v1[11] - v1[12] == pytest.approx(0.01)
    assert v1[23] - v1[24] == pytest.approx(0.01 * 1.03**12)


def test_cash_assumption_row_earns_exactly_one_percent_real_a_year():
    infl = np.random.default_rng(0).normal(0.002, 0.003, 168)
    r = cash_assumption_returns(infl, real_yield=0.01)
    real_year = np.prod((1 + r[:12]) / (1 + infl[:12]))
    assert real_year == pytest.approx(1.01)


def _paths(depleted, real_end, ever_low):
    n = len(depleted)
    real = np.ones((n, 360))
    real[:, -1] = real_end
    for i, low in enumerate(ever_low):
        if low:
            real[i, 100] = 0.3
    return Paths(real.copy(), real, np.array(depleted))


def test_summarize_depletion_by_year_counts_month_12n_or_earlier():
    s = summarize(_paths([240, 241, 0, 300], [0, 0, 1, 0], [1, 1, 0, 1]), floor=0.5)
    assert s["depleted_by"] == {20: 0.25, 25: 0.75, 30: 0.75}


def test_summarize_median_depletion_year_and_none_when_nothing_depletes():
    s = summarize(_paths([12, 13, 25, 0], [0, 0, 0, 1], [1, 1, 1, 0]), floor=0.5)
    assert s["median_depletion_year"] == 2  # years 1, 2, 3 -> 2
    s2 = summarize(_paths([0, 0], [1, 1], [0, 0]), floor=0.5)
    assert s2["median_depletion_year"] is None


def test_summarize_median_depletion_year_even_count_uses_lower_median():
    s = summarize(_paths([12, 25], [0, 0], [1, 1]), floor=0.5)
    assert s["median_depletion_year"] == 1  # years 1, 3 -> lower median


def test_summarize_below_floor_and_ending_percentiles():
    real_end = np.linspace(0, 2, 101)
    s = summarize(_paths([0] * 101, real_end, [0] * 50 + [1] * 51), floor=0.5)
    assert s["below_floor"] == pytest.approx(
        np.mean(np.array([0] * 50 + [1] * 51, bool) | (real_end < 0.5))
    )
    assert s["end_real_median"] == pytest.approx(1.0)
    assert s["end_real_p5"] == pytest.approx(0.1)


def _row(rate, name, year):
    return {
        "rate": rate,
        "portfolio": name,
        "depleted_by": {20: 0.0, 25: 0.1, 30: 0.25},
        "median_depletion_year": year,
        "below_floor": 0.4,
        "end_real_median": 1.2,
        "end_real_p5": 0.05,
    }


def _report():
    rows = []
    for rate in (0.02, 0.033):
        rows += [_row(rate, "CASH", 27), _row(rate, CASH_ASSUMPTION, None), _row(rate, "G", 21)]
    return {
        "data_end": "2018-12-31",
        "first_month": "2005-01",
        "last_month": "2018-12",
        "n_months": 168,
        "seed": 4242,
        "n_paths": 777,
        "block_months": 12,
        "horizon_years": 30,
        "real_floor": 0.5,
        "cash_real_yield": 0.01,
        "rates": [0.02, 0.033],
        "longrun_sha256": "ab" * 32,
        "decision_sha256": "cd" * 32,
        "cost_bps": 5.0,
        "rows": rows,
    }


def test_render_header_settings_hashes_and_limits():
    text = render_markdown(_report())
    assert "# Long-run withdrawals: 30-year resampled paths" in text
    assert "seed 4242" in text
    assert "777 paths" in text
    assert "ab" * 32 in text
    assert "cd" * 32 in text
    for limit in (
        "one market era",
        "one large crash (2008)",
        "falling interest rates",
        "low inflation",
        "near-zero cash yields in 2009-2015",
        "cannot create a 1970s-style inflation decade",
    ):
        assert limit in text


def test_render_one_section_per_rate_with_assumption_row_after_cash():
    lines = render_markdown(_report()).splitlines()
    assert sum(x.startswith("### Withdrawal rate") for x in lines) == 2
    assert "### Withdrawal rate 2.0% per year" in lines
    assert "### Withdrawal rate 3.3% per year" in lines
    for i, line in enumerate(lines):
        if line.startswith("| CASH |"):
            assert lines[i + 1].startswith(f"| {CASH_ASSUMPTION} |")


def test_render_missing_depletion_year_is_a_dash_and_no_dollar_sign():
    text = render_markdown(_report())
    row = next(x for x in text.splitlines() if x.startswith(f"| {CASH_ASSUMPTION} |"))
    assert row.split(" | ")[4] == "-"
    assert "$" not in text


def test_render_real_run_has_one_row_per_portfolio_per_rate(tmp_path):
    dcfg = helper_load(tmp_path)
    lcfg = LongrunConfig(
        seed=7,
        n_paths=20,
        block_months=12,
        horizon_years=30,
        real_floor=0.5,
        rates=[0.04, 0.05],
        cash_real_yield=0.01,
        sha256="ab" * 32,
    )
    report = run_longrun(lcfg, dcfg, helper_prices(), helper_cpi(), helper_criteria())
    text = render_markdown(report)
    names = [p.id for p in dcfg.portfolios] + [CASH_ASSUMPTION]
    for rate in lcfg.rates:
        section = text.split(f"### Withdrawal rate {rate:.1%} per year")[1].split("###")[0]
        rows = [x for x in section.splitlines() if x.startswith("| ") and "portfolio" not in x]
        assert len(rows) == len(names)
    assert "$" not in text
