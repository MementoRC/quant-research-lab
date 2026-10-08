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


def _cpi_by_availability(start="2004-06", end="2006-12", growth=0.01):
    # value for month M, usable from the last day of month M+1 (qrl.macro lag)
    months = pd.period_range(start, end, freq="M")
    avail = [(m + 1).to_timestamp(how="end").normalize() for m in months]
    return pd.Series(100 * (1 + growth) ** np.arange(len(months)), index=pd.DatetimeIndex(avail))


def test_monthly_inflation_uses_usable_cpi_at_consecutive_month_ends():
    days = pd.bdate_range("2004-12-01", "2005-03-31")
    months = pd.period_range("2005-01", "2005-03", freq="M")
    out = monthly_inflation(_cpi_by_availability(), days, months)
    assert list(out.index) == list(months)
    assert out.to_numpy() == pytest.approx([0.01, 0.01, 0.01])


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
