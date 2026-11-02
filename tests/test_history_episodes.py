"""Tests for qrl.history.find_episodes (docs/methodology/history-scenarios.md,
"Episodes"). Small hand-built series."""

from __future__ import annotations

import pandas as pd
import pytest

from qrl.history import EPS, find_episodes

START = pd.Timestamp("1971-01-01")
END = pd.Timestamp("2018-12-31")


def _s(values: list[float], start: str = "1971-03-01") -> pd.Series:
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)), dtype=float)


def _find(series: pd.Series, end: pd.Timestamp = END):
    return find_episodes(series, 0.15, START, 10, end)


def test_exactly_fifteen_percent_counts():
    found = _find(_s([100.0, 85.0, 100.0]))
    assert len(found) == 1
    assert abs(found[0].depth - 0.15) < 1e-9


def test_fourteen_point_nine_percent_does_not_count():
    assert _find(_s([100.0, 85.1, 100.0])) == []


def test_two_dips_without_a_new_high_are_one_episode():
    series = _s([100.0, 80.0, 90.0, 82.0, 101.0])
    found = _find(series)
    assert len(found) == 1
    assert found[0].peak == series.index[0]
    assert found[0].trough == series.index[1]
    assert found[0].recovery == series.index[4]


def test_recovery_is_at_or_above_the_peak():
    series = _s([100.0, 80.0, 99.9, 100.0, 120.0])
    assert _find(series)[0].recovery == series.index[3]


def test_unrecovered_episode_is_kept():
    found = _find(_s([100.0, 80.0, 90.0]))
    assert len(found) == 1
    assert found[0].recovery is None
    assert found[0].months is None


def test_a_fall_that_never_reaches_the_threshold_is_not_an_episode_even_if_unrecovered():
    assert _find(_s([100.0, 90.0, 95.0])) == []


def test_peak_before_the_start_is_dropped_even_if_its_fall_is_after_it():
    series = _s([100.0] + [99.0] * 70 + [80.0, 100.0, 105.0, 80.0, 106.0], start="1970-11-02")
    assert series.index[71] > START  # the first fall happens after the start date
    found = _find(series)
    assert len(found) == 1
    assert found[0].peak == series.index[73]
    assert found[0].trough == series.index[74]
    assert found[0].recovery == series.index[75]
    assert abs(found[0].depth - (1 - 80.0 / 105.0)) < 1e-12


def test_the_running_high_is_the_full_history_high():
    series = pd.Series(
        [100.0, 95.0, 70.0],
        index=pd.to_datetime(["1970-12-30", "1971-01-04", "1971-01-05"]),
    )
    assert _find(series) == []  # a naive cut at the start would see an episode from 95


def test_months_and_window_end():
    series = pd.Series(
        [100.0, 80.0, 101.0],
        index=pd.to_datetime(["1973-01-11", "1973-03-01", "1973-07-02"]),
    )
    ep = _find(series)[0]
    assert ep.months == 6
    assert ep.window_end == pd.Timestamp("1983-01-11")


def test_window_end_is_capped_at_the_data_end():
    series = pd.Series(
        [100.0, 80.0, 90.0],
        index=pd.to_datetime(["2015-01-02", "2016-01-04", "2017-01-03"]),
    )
    assert _find(series)[0].window_end == END


def test_a_fall_from_a_close_that_only_equals_the_old_high_is_not_a_new_episode():
    series = _s([100.0, 80.0, 100.0, 80.0, 100.0])
    found = _find(series)
    assert len(found) == 1
    assert found[0].peak == series.index[0]
    assert found[0].recovery == series.index[2]


def test_a_new_strict_high_after_a_tie_rearms_and_peaks_are_distinct():
    series = _s([100.0, 80.0, 100.0, 80.0, 101.0, 80.0, 102.0])
    found = _find(series)
    assert [ep.peak for ep in found] == [series.index[0], series.index[4]]
    assert len({ep.peak for ep in found}) == len(found)


def test_unsorted_index_is_refused():
    series = pd.Series([100.0, 80.0], index=pd.to_datetime(["1972-01-04", "1972-01-03"]))
    with pytest.raises(ValueError, match="strictly increasing"):
        _find(series)


def test_duplicate_index_is_refused():
    series = pd.Series([100.0, 80.0], index=pd.to_datetime(["1972-01-03", "1972-01-03"]))
    with pytest.raises(ValueError, match="strictly increasing"):
        _find(series)


def test_float_error_just_under_the_threshold_still_counts():
    peak, trough = 9.0, 7.65
    fall = 1.0 - trough / peak
    assert fall < 0.15  # 0.1499999999999999: under 15% only by float error
    assert fall >= 0.15 - EPS
    found = _find(_s([peak, trough, peak]))
    assert len(found) == 1


def test_a_tie_with_the_high_then_an_unrecovered_fall_is_not_a_new_peak():
    # The tie is never itself the peak. A fall after it, with no strictly higher
    # close in between, is not an episode (spec: ties end an episode, not start one).
    assert _find(_s([100.0, 100.0, 80.0, 85.0])) == []


def test_a_tie_after_a_flagged_fall_keeps_the_original_peak_and_a_later_unrecovered_fall_is_ignored():
    series = _s([100.0, 80.0, 100.0, 70.0])
    found = _find(series)
    assert len(found) == 1
    assert found[0].peak == series.index[0]
    assert found[0].recovery == series.index[2]


def test_nan_values_inside_an_episode_are_ignored():
    values = [100.0, 90.0, 80.0, 90.0, 101.0]
    with_nan = [100.0, float("nan"), 90.0, 80.0, float("nan"), 90.0, 101.0]
    clean = _s(values)
    dirty = pd.Series(with_nan, index=pd.bdate_range("1971-03-01", periods=len(with_nan)))
    got = _find(dirty)
    want = _find(clean)
    assert len(got) == len(want) == 1
    assert got[0].depth == want[0].depth
    assert got[0].peak == dirty.index[0]
    assert got[0].trough == dirty.index[3]
    assert got[0].recovery == dirty.index[6]


@pytest.mark.parametrize("values", [[], [float("nan"), float("nan")]])
def test_empty_and_all_nan_input_give_no_episodes(values):
    assert _find(_s(values)) == []


def test_data_after_the_end_is_ignored():
    series = pd.Series(
        [100.0, 99.0, 70.0],
        index=pd.to_datetime(["2018-12-27", "2018-12-31", "2019-01-02"]),
    )
    assert _find(series) == []
