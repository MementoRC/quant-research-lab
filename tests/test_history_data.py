"""Tests for qrl.history_data (docs/methodology/history-scenarios.md,
"Stand-in data"). Synthetic data only; nothing here downloads."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qrl.history_config import Leg, load_history_config
from qrl.history_data import (
    FUNDS,
    RawData,
    assemble_panel,
    interpolate_monthly,
    sp_with_dividends,
    treasury_proxy,
)
from qrl.international import yield_proxy_close


def test_each_monthly_figure_sits_on_its_month_end():
    index = pd.bdate_range("2000-01-03", "2000-04-28")
    monthly = pd.Series(
        [100.0, 110.0, 121.0, 133.1],
        index=pd.to_datetime(["2000-01-01", "2000-02-01", "2000-03-01", "2000-04-01"]),
    )
    out = interpolate_monthly(monthly, index)
    for day, figure in [
        ("2000-01-31", 100.0),
        ("2000-02-29", 110.0),
        ("2000-03-31", 121.0),
        ("2000-04-28", 133.1),
    ]:
        assert out.loc[day] == pytest.approx(figure)
    assert out.loc[:"2000-01-28"].isna().all()  # nothing before the first month end


def test_days_between_month_ends_move_at_a_constant_daily_rate():
    index = pd.bdate_range("2000-01-03", "2000-04-28")
    monthly = pd.Series(
        [100.0, 110.0, 121.0, 133.1],
        index=pd.to_datetime(["2000-01-01", "2000-02-01", "2000-03-01", "2000-04-01"]),
    )
    out = interpolate_monthly(monthly, index)
    february = out.loc["2000-02-01":"2000-02-29"].pct_change().dropna()
    assert np.allclose(february, february.iloc[0])
    assert (out.loc["2000-02-01":"2000-02-29"].diff().dropna() > 0).all()


def test_interpolation_refuses_a_non_positive_figure():
    index = pd.bdate_range("2000-01-03", "2000-03-31")
    monthly = pd.Series([100.0, 0.0], index=pd.to_datetime(["2000-01-01", "2000-02-01"]))
    with pytest.raises(ValueError, match="positive"):
        interpolate_monthly(monthly, index)


def test_dividends_accrue_daily_as_yield_over_252():
    index = pd.bdate_range("2000-01-03", periods=3)
    price = pd.Series(100.0, index=index)
    yields = pd.Series(0.0252, index=pd.to_datetime(["1999-11-01", "1999-12-01", "2000-01-01"]))
    out = sp_with_dividends(price, yields)
    assert out.iloc[0] == 1.0
    assert out.iloc[1] == pytest.approx(1.0001)
    assert out.iloc[2] == pytest.approx(1.0001**2)


def test_dividend_yield_of_the_previous_month_is_used():
    index = pd.bdate_range("2000-01-31", periods=2)  # Jan 31, Feb 1
    price = pd.Series(100.0, index=index)
    yields = pd.Series([0.0252, 0.0504], index=pd.to_datetime(["1999-12-01", "2000-01-01"]))
    out = sp_with_dividends(price, yields)
    assert out.iloc[1] == pytest.approx(1.0 + 0.0504 / 252)  # Feb 1 uses January's yield


def test_dividend_return_is_additive_to_the_price_return():
    index = pd.bdate_range("2000-01-03", periods=3)
    price = pd.Series([100.0, 110.0, 99.0], index=index)
    yields = pd.Series(0.0252, index=pd.to_datetime(["1999-12-01"]))
    out = sp_with_dividends(price, yields)
    step = 0.0252 / 252
    assert out.iloc[1] == pytest.approx(1.0 + 0.10 + step)
    assert out.iloc[2] == pytest.approx((1.0 + 0.10 + step) * (1.0 - 0.10 + step))
    assert out.iloc[1] != pytest.approx(1.10 * (1.0 + step))


def test_nan_price_raises():
    index = pd.bdate_range("2000-01-03", periods=3)
    price = pd.Series([100.0, np.nan, 101.0], index=index)
    yields = pd.Series(0.03, index=pd.to_datetime(["1999-12-01"]))
    with pytest.raises(ValueError, match="missing"):
        sp_with_dividends(price, yields)


def test_empty_price_raises():
    price = pd.Series([], index=pd.DatetimeIndex([]), dtype=float)
    yields = pd.Series(0.03, index=pd.to_datetime(["1999-12-01"]))
    with pytest.raises(ValueError, match="empty"):
        sp_with_dividends(price, yields)


@pytest.mark.parametrize("days", [["2000-01-04", "2000-01-03"], ["2000-01-03", "2000-01-03"]])
def test_unsorted_or_duplicated_price_index_raises(days):
    price = pd.Series([100.0, 101.0], index=pd.to_datetime(days))
    yields = pd.Series(0.03, index=pd.to_datetime(["1999-12-01"]))
    with pytest.raises(ValueError, match="strictly increasing"):
        sp_with_dividends(price, yields)


@pytest.mark.parametrize("days", [["2000-01-04", "2000-01-03"], ["2000-01-03", "2000-01-03"]])
def test_unsorted_or_duplicated_interpolation_index_raises(days):
    monthly = pd.Series([100.0], index=pd.to_datetime(["2000-01-01"]))
    with pytest.raises(ValueError, match="strictly increasing"):
        interpolate_monthly(monthly, pd.DatetimeIndex(pd.to_datetime(days)))


def test_two_yield_figures_in_one_month_raise():
    index = pd.bdate_range("2000-01-03", periods=2)
    price = pd.Series(100.0, index=index)
    yields = pd.Series([0.03, 0.04], index=pd.to_datetime(["1999-12-01", "1999-12-15"]))
    with pytest.raises(ValueError, match="more than one"):
        sp_with_dividends(price, yields)


def test_a_missing_middle_month_is_bridged_geometrically():
    index = pd.bdate_range("2000-01-03", "2000-03-31")
    monthly = pd.Series([100.0, 121.0], index=pd.to_datetime(["2000-01-01", "2000-03-01"]))
    out = interpolate_monthly(monthly, index)
    assert out.loc["2000-01-31"] == pytest.approx(100.0)
    assert out.loc["2000-03-31"] == pytest.approx(121.0)
    steps = out.loc["2000-01-31":"2000-03-31"].pct_change().dropna()
    assert np.allclose(steps, steps.iloc[0])


def test_missing_dividend_yield_raises():
    index = pd.bdate_range("2000-01-03", periods=3)
    price = pd.Series(100.0, index=index)
    yields = pd.Series([0.03], index=pd.to_datetime(["1990-01-01"]))
    with pytest.raises(ValueError, match="dividend yield"):
        sp_with_dividends(price, yields)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "history.yaml"
PANEL_END = pd.Timestamp("2000-12-29")


def _walk(index: pd.DatetimeIndex, seed: int, start: float = 100.0, vol: float = 0.01):
    rng = np.random.default_rng(seed)
    return pd.Series(start * np.exp(np.cumsum(rng.normal(0.0002, vol, len(index)))), index=index)


def _yield(index: pd.DatetimeIndex, seed: int) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(5.0 + np.cumsum(rng.normal(0.0, 0.02, len(index))), index=index)


def test_a_yield_leg_window_chains_without_a_jump():
    index = pd.bdate_range("1990-01-01", "1993-12-31")
    d20 = pd.Series(8.0, index=pd.bdate_range("1990-01-01", "1990-12-31"))  # not published in 1991
    d20 = pd.concat([d20, pd.Series(7.0, index=pd.bdate_range("1992-01-01", "1993-12-31"))])
    d30 = pd.Series(8.5, index=pd.bdate_range("1990-01-01", "1993-12-31"))
    legs = (
        Leg("DGS20", 10.0),
        Leg("DGS30", 10.0, pd.Timestamp("1991-01-01"), pd.Timestamp("1991-12-31")),
    )
    unchained = yield_proxy_close(d20, 10.0, 1, index)
    assert unchained.pct_change().abs().max() > 0.05  # the join is a jump without the chain
    chained = treasury_proxy(legs, {"DGS20": d20, "DGS30": d30}, 1, index)
    assert chained.pct_change().abs().max() < 0.001


def test_shy_proxy_switches_to_dgs2_on_its_first_date_without_a_jump():
    index = pd.bdate_range("1990-01-01", "1991-12-31")
    first = pd.Timestamp("1991-01-01")  # DGS2's first value; DGS1 covers the days before
    d1 = pd.Series(5.0, index=index)
    d2 = pd.Series(6.5, index=index[index >= first])
    legs = (Leg("DGS1", 1.9), Leg("DGS2", 1.9, first, index[-1]))
    unchained = yield_proxy_close(d2, 1.9, 0, index).combine_first(
        yield_proxy_close(d1, 1.9, 0, index)
    )
    assert unchained.pct_change().abs().max() > 0.001  # a plain join jumps
    chained = treasury_proxy(legs, {"DGS1": d1, "DGS2": d2}, 0, index)
    assert chained.pct_change().abs().max() < 0.001
    after = chained.loc[first:].pct_change().dropna()
    expected = yield_proxy_close(d2, 1.9, 0, index).loc[first:].pct_change().dropna()
    assert after.iloc[0] == 0.0  # DGS2's first proxy day has no return of its own: flat
    pd.testing.assert_series_equal(after.iloc[1:], expected, check_names=False)


def test_a_single_leg_is_the_plain_yield_proxy():
    index = pd.bdate_range("1990-01-01", "1990-12-31")
    y = _yield(index, 1)
    out = treasury_proxy((Leg("DGS1", 1.9),), {"DGS1": y}, 1, index)
    pd.testing.assert_series_equal(out, yield_proxy_close(y, 1.9, 1, index))


def _raw(
    *,
    ixic_start: str = "1999-12-01",
    ixic_gaps: tuple[str, ...] = (),
) -> tuple[RawData, pd.DatetimeIndex]:
    days = pd.bdate_range("1999-12-01", PANEL_END)
    starts = {
        "^GSPC": "1999-12-01", "^SP500TR": "2000-03-01", "^IXIC": ixic_start,
        "GC=F": "2000-05-01", "SPY": "2000-06-01", "QQQ": "2000-04-03", "RSP": "2000-08-01",
        "IEF": "2000-07-03", "TLT": "2000-07-03", "SHY": "2000-07-03", "GLD": "2000-09-01",
    }  # fmt: skip
    close = pd.DataFrame(index=days, columns=list(starts), dtype=float)
    for i, (ticker, first) in enumerate(starts.items()):
        sub = days[days >= first]
        close.loc[sub, ticker] = _walk(sub, i).to_numpy()
    for day in ixic_gaps:
        close.loc[day, "^IXIC"] = np.nan
    open_ = close * 1.001
    fred = {
        sid: _yield(pd.bdate_range("1999-06-01", PANEL_END), seed)
        for seed, sid in enumerate(["DGS1", "DGS2", "DGS7", "DGS20", "DGS30"])
    }
    shiller = pd.Series(0.02, index=pd.date_range("1999-01-01", "2000-12-01", freq="MS"))
    worldbank = pd.Series(
        300.0 * np.exp(np.arange(15) * 0.01),
        index=pd.date_range("1999-10-01", "2000-12-01", freq="MS"),
    )
    return RawData(open_, close, fred, shiller, worldbank), days


def _cfg():
    return dataclasses.replace(
        load_history_config(CONFIG),
        panel_start=pd.Timestamp("2000-01-03"),
        lead_in_start=pd.Timestamp("1999-12-01"),
    )


def test_panel_covers_every_fund_from_the_panel_start():
    raw, _ = _raw()
    panel = assemble_panel(raw, _cfg(), PANEL_END)
    assert panel.close.index[0] == pd.Timestamp("2000-01-03")
    assert list(panel.close.columns) == list(FUNDS)
    assert not panel.close.isna().any(axis=None)
    assert not panel.open.isna().any(axis=None)


def test_own_start_and_gold_futures_start_are_the_first_real_prices():
    raw, _ = _raw()
    panel = assemble_panel(raw, _cfg(), PANEL_END)
    assert panel.own_start["SPY"] == pd.Timestamp("2000-06-01")
    assert panel.own_start["GLD"] == pd.Timestamp("2000-09-01")
    assert panel.gold_futures_start == pd.Timestamp("2000-05-01")


def test_stand_in_open_is_the_previous_close_and_fund_open_is_its_own():
    raw, _ = _raw()
    panel = assemble_panel(raw, _cfg(), PANEL_END)
    day = pd.Timestamp("2000-03-15")  # QQQ, SHY, SPY all on stand-in data
    for fund in ("QQQ", "SHY", "SPY"):
        previous = panel.close[fund].shift(1).loc[day]
        assert panel.open[fund].loc[day] == pytest.approx(previous)
    first = panel.own_start["SPY"]
    assert panel.open["SPY"].loc[first] == pytest.approx(raw.open.loc[first, "SPY"])


def test_the_fund_price_is_its_own_from_its_first_day_and_joined_without_a_jump():
    raw, _ = _raw()
    panel = assemble_panel(raw, _cfg(), PANEL_END)
    first = panel.own_start["SPY"]
    assert panel.close["SPY"].loc[first] == pytest.approx(raw.close.loc[first, "SPY"])
    after = panel.close["SPY"].loc[first:]
    pd.testing.assert_series_equal(
        after, raw.close["SPY"].loc[first:PANEL_END], check_names=False, check_freq=False
    )
    jump = panel.close["SPY"].pct_change().loc[first]
    assert abs(jump) < 0.2  # an ordinary daily move, not a level jump between sources


def test_one_day_gap_in_a_stand_in_is_filled_and_two_days_raise():
    raw, _ = _raw(ixic_gaps=("2000-02-10",))
    panel = assemble_panel(raw, _cfg(), PANEL_END)
    assert panel.close["QQQ"].loc["2000-02-10"] == panel.close["QQQ"].loc["2000-02-09"]
    raw, _ = _raw(ixic_gaps=("2000-02-10", "2000-02-11"))
    with pytest.raises(ValueError, match="gap"):
        assemble_panel(raw, _cfg(), PANEL_END)


def test_a_stand_in_that_does_not_reach_the_panel_start_raises():
    raw, _ = _raw(ixic_start="2000-01-10")
    with pytest.raises(ValueError, match="QQQ"):
        assemble_panel(raw, _cfg(), PANEL_END)


def test_the_panel_is_cut_at_the_data_end():
    raw, _ = _raw()
    panel = assemble_panel(raw, _cfg(), pd.Timestamp("2000-11-30"))
    assert panel.close.index[-1] <= pd.Timestamp("2000-11-30")
