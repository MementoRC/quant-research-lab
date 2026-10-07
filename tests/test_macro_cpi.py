"""CPI for the decision helper: the `month_ends` lag unit in qrl.macro and
the usable-CPI lookup. Month M's index is usable from the last day of M+1.
Offline. Spec: docs/methodology/decision-helper.md ("Withdrawals")."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from qrl import macro as qmacro
from qrl.decision_withdraw import CPI_SERIES, usable_cpi

ROOT = Path(__file__).resolve().parents[1]
MONTH_LAG = {"unit": "month_ends", "value": 2}


def test_month_ends_lag_usable_from_last_day_of_next_month():
    obs = pd.to_datetime(["2018-01-01", "2018-02-01", "2018-11-01", "2018-12-01"])
    lagged = qmacro.lag_to_availability(pd.Series([1.0, 2.0, 3.0, 4.0], index=obs), MONTH_LAG)
    expected = pd.to_datetime(["2018-02-28", "2018-03-31", "2018-12-31", "2019-01-31"])
    pd.testing.assert_index_equal(lagged.index, expected)


def test_cpi_month_not_used_before_last_day_of_next_month():
    obs = pd.date_range("2017-10-01", "2018-03-01", freq="MS")  # Oct=0, Nov=1, Dec=2, Jan=3
    series = pd.Series(range(len(obs)), index=obs, dtype="float64")
    lagged = qmacro.lag_to_availability(series, MONTH_LAG)
    assert usable_cpi(lagged, pd.Timestamp("2018-02-27")) == 2.0  # still December's
    assert usable_cpi(lagged, pd.Timestamp("2018-02-28")) == 3.0  # January's, from Feb 28
    # on 1 January the latest usable index is November's (usable from 31 December)
    assert usable_cpi(lagged, pd.Timestamp("2018-01-01")) == 1.0


def test_usable_cpi_refuses_missing_cpi():
    lagged = pd.Series([100.0], index=pd.to_datetime(["2005-01-31"]))
    with pytest.raises(ValueError, match="missing CPI"):
        usable_cpi(lagged, pd.Timestamp("2005-01-30"))  # nothing usable yet
    with pytest.raises(ValueError, match="missing CPI"):
        usable_cpi(lagged, pd.Timestamp("2005-06-30"))  # months without a new value


def test_unknown_lag_unit_still_rejected():
    series = pd.Series([1.0], index=pd.to_datetime(["2018-01-01"]))
    with pytest.raises(ValueError, match="Unknown lag unit"):
        qmacro.lag_to_availability(series, {"unit": "months", "value": 1})


def test_shipped_macro_config_has_cpi_with_month_end_lag():
    cfg = qmacro.load_macro_config(ROOT / "config" / "macro.yaml")
    assert cfg["series"][CPI_SERIES]["lag"] == {"unit": "month_ends", "value": 2}
    assert cfg["series"][CPI_SERIES]["frequency"] == "monthly"
    assert {"T10Y2Y", "BAA10Y", "ICSA"} <= cfg["series"].keys()
