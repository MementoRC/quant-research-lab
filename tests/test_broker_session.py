"""Tests for qrl.broker_session: New York dates across DST and midnight, and
the session date (latest shared bar), never the wall-clock date."""

from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest

from qrl.broker_session import ny_date, session_date


@pytest.mark.parametrize(
    ("utc", "expected"),
    [
        (
            "2026-11-03T04:30:00+00:00",
            "2026-11-02",
        ),  # 23:30 EST (DST ended 11-01); EDT would say 11-03
        ("2026-11-03T05:30:00+00:00", "2026-11-03"),  # 00:30 EST, just past midnight
        ("2026-10-30T03:30:00+00:00", "2026-10-29"),  # 23:30 EDT
        ("2026-10-30T04:30:00+00:00", "2026-10-30"),  # 00:30 EDT; EST would say 10-29
        ("2026-03-08T04:30:00+00:00", "2026-03-07"),  # 23:30 EST, before DST began 03-08
        ("2026-03-10T04:30:00+00:00", "2026-03-10"),  # 00:30 EDT; EST would say 03-09
    ],
)
def test_ny_date_across_dst_and_midnight(utc, expected):
    assert ny_date(datetime.fromisoformat(utc)) == date.fromisoformat(expected)


def test_ny_date_refuses_a_naive_clock():
    with pytest.raises(ValueError, match="timezone-aware"):
        ny_date(datetime(2026, 11, 4, 18, 30))


def _close() -> pd.DataFrame:
    index = pd.bdate_range("2026-10-30", "2026-11-04")
    close = pd.DataFrame({"QQQ": 500.0, "GLD": 200.0}, index=index)
    close.loc[pd.Timestamp("2026-11-04"), "GLD"] = np.nan  # GLD's last bar: 11-03
    return close


def test_session_date_is_the_latest_bar_all_relevant_symbols_share():
    assert session_date(_close(), {"QQQ"}) == date(2026, 11, 4)
    assert session_date(_close(), {"QQQ", "GLD"}) == date(2026, 11, 3)


def test_session_date_ignores_symbols_without_a_column_and_falls_back_to_the_frame():
    assert session_date(_close(), {"QQQ", "XYZ"}) == date(2026, 11, 4)
    assert session_date(_close(), set()) == date(2026, 11, 4)
