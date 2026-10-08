import hashlib

import numpy as np
import pandas as pd
import pytest

from qrl.longrun import (
    LongrunConfig,
    load_longrun_config,
    monthly_inflation,
    monthly_returns,
)

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

    # Dec 2004 .. Apr 2005; Apr 30 2005 is a Saturday, so April's last trading
    # day is Fri Apr 29, before March's CPI becomes usable (Apr 30).
    days = pd.bdate_range("2004-11-01", "2005-04-29")
    months = pd.period_range("2005-01", "2005-04", freq="M")
    out = monthly_inflation(_cpi_by_availability(levels=levels), days, months)
    assert list(out.index) == list(months)

    # On month m's last trading day the usable value is month m-1's (published
    # end of m), so inflation(m) = level[m-1] / level[m-2] - 1.
    expected = [
        level("2004-12") / level("2004-11") - 1,  # Jan 31 (Mon)
        level("2005-01") / level("2004-12") - 1,  # Feb 28 (Mon)
        level("2005-02") / level("2005-01") - 1,  # Mar 31 (Thu)
        # Apr 29 (Fri): March CPI not yet usable, February's is; Mar 31 also
        # sees February's.
        level("2005-02") / level("2005-02") - 1,
    ]
    assert out.to_numpy() == pytest.approx(expected, abs=1e-12)
    assert expected[3] == 0.0

    # Using each month's FIRST trading day instead would give different numbers.
    wrong_first_day = [
        level("2004-11") / level("2004-10") - 1,  # Jan 3 vs Dec 1
        level("2004-12") / level("2004-11") - 1,  # Feb 1 vs Jan 3
        level("2005-01") / level("2004-12") - 1,  # Mar 1 vs Feb 1
        level("2005-02") / level("2005-01") - 1,  # Apr 1 vs Mar 1
    ]
    assert not np.allclose(out.to_numpy(), wrong_first_day, atol=1e-9)
    assert all(abs(o - w) > 1e-9 for o, w in zip(out.to_numpy(), wrong_first_day, strict=True))


def test_monthly_inflation_refuses_stale_cpi_mid_series():
    # Jan and Feb 2005 values (usable Feb 28 / Mar 31) are missing mid-series;
    # later months are present.
    cpi = _cpi_by_availability().drop(pd.to_datetime(["2005-02-28", "2005-03-31"]))
    days = pd.bdate_range("2004-12-01", "2005-03-31")
    months = pd.period_range("2005-01", "2005-03", freq="M")
    # Mar 31: latest usable value is Dec's (dated Jan 31), 59 days old.
    with pytest.raises(ValueError, match="missing CPI"):
        monthly_inflation(cpi, days, months)


def test_monthly_inflation_refuses_a_missing_cpi():
    days = pd.bdate_range("2004-12-01", "2005-03-31")
    months = pd.period_range("2005-01", "2005-03", freq="M")
    with pytest.raises(ValueError, match="missing CPI"):
        monthly_inflation(_cpi_by_availability(end="2004-12"), days, months)


def test_monthly_inflation_refuses_a_month_without_the_prior_month_end():
    days = pd.bdate_range("2005-01-01", "2005-03-31")  # no December 2004 trading day
    months = pd.period_range("2005-01", "2005-03", freq="M")
    with pytest.raises(ValueError, match="2004-12"):
        monthly_inflation(_cpi_by_availability(), days, months)


def test_load_longrun_config_refuses_an_unsupported_version(tmp_path):
    with pytest.raises(ValueError, match="version"):
        load_longrun_config(_write(tmp_path, GOOD.replace("version: 1", "version: 2")), DEC_SHA)


def test_block_starts_same_seed_same_draw_and_in_range():
    from qrl.longrun import block_starts

    a = block_starts(seed=3, n_paths=100, n_blocks=30, n_months=168)
    b = block_starts(seed=3, n_paths=100, n_blocks=30, n_months=168)
    assert a.shape == (100, 30)
    assert np.array_equal(a, b)
    assert a.min() >= 0
    assert a.max() <= 167


def test_block_starts_different_seed_different_draw():
    from qrl.longrun import block_starts

    a = block_starts(seed=3, n_paths=100, n_blocks=30, n_months=168)
    b = block_starts(seed=4, n_paths=100, n_blocks=30, n_months=168)
    assert not np.array_equal(a, b)


def test_month_indices_wraps_december_2018_to_january_2005():
    from qrl.longrun import month_indices

    starts = np.array([[167, 0]])  # block 1 starts at the last month (Dec 2018)
    idx = month_indices(starts, block_months=12, n_months=168)
    assert idx.shape == (1, 24)
    assert list(idx[0, :12]) == [167] + list(range(0, 11))
    assert list(idx[0, 12:]) == list(range(0, 12))
