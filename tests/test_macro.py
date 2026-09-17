from pathlib import Path

import pandas as pd
import pytest
import yaml

from qrl import macro as qmacro

BUSINESS_LAG = {"unit": "business_days", "value": 2}
WEEKLY_LAG = {"unit": "calendar_days", "value": 6}


def test_daily_series_lag_hand_checked():
    """2-business-day lag on a short run of daily observations, with an exact
    hand-computed availability date for each row."""
    obs_dates = pd.to_datetime(
        ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"]
    )
    series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], index=obs_dates)

    lagged = qmacro.lag_to_availability(series, BUSINESS_LAG)

    expected_availability = pd.to_datetime(
        ["2024-01-04", "2024-01-05", "2024-01-08", "2024-01-09", "2024-01-10"]
    )
    pd.testing.assert_index_equal(lagged.index, expected_availability)


def test_daily_series_aligned_to_trading_calendar_hand_checked():
    obs_dates = pd.to_datetime(
        ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"]
    )
    series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], index=obs_dates)
    lagged = qmacro.lag_to_availability(series, BUSINESS_LAG)

    trading_index = pd.bdate_range("2024-01-02", "2024-01-12")
    aligned = qmacro.align_to_trading_days(lagged, trading_index)

    expected = pd.Series(
        [None, None, 1.0, 2.0, 3.0, 4.0, 5.0, 5.0, 5.0],
        index=trading_index,
        dtype="float64",
    )
    pd.testing.assert_series_equal(aligned, expected, check_names=False)

    # No value may appear before its availability date.
    known_from = obs_dates[0] + pd.tseries.offsets.BDay(2)
    assert aligned.loc[trading_index[trading_index < known_from]].isna().all()


def test_weekend_stamped_observation_does_not_produce_duplicate_availability_dates():
    """Real FRED data quirk: some daily series occasionally stamp a value on a
    weekend (carrying Friday's value forward). Business-day rollover then maps
    both the Friday and Saturday observations onto the same availability date;
    the later observation must win, not raise or silently duplicate rows."""
    obs_dates = pd.to_datetime(["2024-01-04", "2024-01-05", "2024-01-06"])  # Thu, Fri, Sat
    series = pd.Series([1.0, 2.0, 2.0], index=obs_dates)

    lagged = qmacro.lag_to_availability(series, BUSINESS_LAG)

    assert lagged.index.is_unique
    # Fri(01-05)+2BD and Sat(01-06)+2BD both roll to Tue 01-09; the Saturday
    # observation (later) wins.
    assert lagged.loc[pd.Timestamp("2024-01-09")] == 2.0


def test_weekly_saturday_dated_series_aligned_hand_checked():
    """ICSA-style: observation dated the week-ending Saturday, released 6
    calendar days later. Crosses a weekend gap in the trading calendar."""
    obs_dates = pd.to_datetime(["2024-01-06", "2024-01-13"])  # Saturdays
    series = pd.Series([100.0, 110.0], index=obs_dates)
    lagged = qmacro.lag_to_availability(series, WEEKLY_LAG)

    expected_availability = pd.to_datetime(["2024-01-12", "2024-01-19"])  # Fridays
    pd.testing.assert_index_equal(lagged.index, expected_availability)

    trading_index = pd.bdate_range("2024-01-08", "2024-01-22")
    aligned = qmacro.align_to_trading_days(lagged, trading_index)

    before_first = trading_index[trading_index < expected_availability[0]]
    assert aligned.loc[before_first].isna().all()
    assert aligned.loc["2024-01-12"] == 100.0
    assert aligned.loc["2024-01-18"] == 100.0  # still ffilled, one day before release
    assert aligned.loc["2024-01-19"] == 110.0
    assert aligned.loc["2024-01-22"] == 110.0


@pytest.mark.parametrize("lag", [BUSINESS_LAG, WEEKLY_LAG])
def test_property_every_aligned_value_is_known_by_its_trading_day(lag):
    """For every trading day t, an aligned value's source observation date plus
    its lag must be <= t (the acceptance property: macro series are lagged)."""
    # Real daily FRED series (T10Y2Y, BAMLH0A0HYM2) only observe business days;
    # weekly series (ICSA) observe every 7th calendar day.
    freq = "7D" if lag is WEEKLY_LAG else "B"
    obs_dates = pd.date_range("2024-01-01", periods=40, freq=freq)
    series = pd.Series(range(len(obs_dates)), index=obs_dates, dtype="float64")
    lagged = qmacro.lag_to_availability(series, lag)

    trading_index = pd.bdate_range(obs_dates[0], obs_dates[-1] + pd.Timedelta(days=30))
    aligned = qmacro.align_to_trading_days(lagged, trading_index)

    availability_dates = lagged.index
    for t in trading_index:
        value = aligned.loc[t]
        if pd.isna(value):
            continue
        # The most recent availability date <= t must be the one that produced this value.
        usable = availability_dates[availability_dates <= t]
        assert not usable.empty
        assert lagged.loc[usable[-1]] == value


def test_load_macro_lags_and_aligns_with_fetch_monkeypatched(tmp_path, monkeypatch):
    config = {
        "series": {
            "FAKE": {
                "description": "synthetic",
                "frequency": "daily",
                "lag": BUSINESS_LAG,
            }
        }
    }
    config_path = tmp_path / "macro.yaml"
    config_path.write_text(yaml.safe_dump(config))

    obs_dates = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
    fake_series = pd.Series([1.0, 2.0, 3.0], index=obs_dates, name="FAKE")

    def fake_fetch(series_id, refresh=False, cache_dir=Path("data/cache")):
        assert series_id == "FAKE"
        return fake_series

    monkeypatch.setattr(qmacro, "fetch_series", fake_fetch)

    trading_index = pd.bdate_range("2024-01-02", "2024-01-10")
    df = qmacro.load_macro(ids=["FAKE"], trading_index=trading_index, config_path=config_path)

    assert list(df.columns) == ["FAKE"]
    known_from = obs_dates[0] + pd.tseries.offsets.BDay(2)
    before = df.loc[trading_index[trading_index < known_from], "FAKE"]
    assert before.isna().all()
    assert df.loc[known_from, "FAKE"] == 1.0
