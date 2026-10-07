"""Tests for the macro overlay (qrl.overlay). Offline; synthetic prices and a
synthetic CPI only. Spec: docs/methodology/macro-overlay.md.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qrl.core_compare import Candidate, load_core_candidates
from qrl.data import synthetic_prices
from qrl.macro import lag_to_availability, load_macro_config
from qrl.overlay import (
    build_overlay,
    inflation_state,
    load_overlay_config,
    month_end_mask,
    overlay_weights,
    signal_columns,
    trend_states,
    vol_state,
)
from qrl.strategies.core_mix import core_mix

ROOT = Path(__file__).resolve().parents[1]
SHIPPED = (ROOT / "config" / "overlay.yaml").read_text()
CANDS, _ = load_core_candidates(ROOT / "config" / "core_candidates.yaml")
CPI_LAG = load_macro_config(ROOT / "config" / "macro.yaml")["series"]["CPIAUCNS"]["lag"]
CFG, _ = load_overlay_config(ROOT / "config" / "overlay.yaml", CANDS)
TICKERS = ["GLD", "SHY", "SPY", "TLT"]


def _prices(end: str = "2008-12-31") -> tuple[pd.DataFrame, pd.DataFrame]:
    return synthetic_prices(TICKERS, start="1999-01-01", end=end)


def _flat_close(start: str, end: str) -> pd.DataFrame:
    idx = pd.bdate_range(start, end)
    return pd.DataFrame(100.0, index=idx, columns=TICKERS)


def _cpi(
    start: str = "1990-01-01",
    end: str = "2024-04-01",
    jump_at: str | None = None,
    jump: float = 0.0,
    missing: str | None = None,
) -> pd.Series:
    """Synthetic CPIAUCNS: 2%/yr, optional level jump, optional missing print;
    observation-dated like FRED (1st of month), then lagged per macro.yaml."""
    obs = pd.date_range(start, end, freq="MS")
    s = pd.Series(100 * 1.02 ** (np.arange(len(obs)) / 12), index=obs, name="CPIAUCNS")
    if jump_at is not None:
        s[s.index >= pd.Timestamp(jump_at)] *= 1 + jump
    if missing is not None:
        s[pd.Timestamp(missing)] = np.nan
    return lag_to_availability(s, CPI_LAG)


def _load(tmp_path: Path, text: str, cands=None):
    p = tmp_path / "overlay.yaml"
    p.write_text(text)
    return load_overlay_config(p, cands or CANDS)


def test_shipped_config_loads_with_every_spec_number():
    cfg, sha = load_overlay_config(ROOT / "config" / "overlay.yaml", CANDS)
    raw = (ROOT / "config" / "overlay.yaml").read_bytes()
    assert sha == hashlib.sha256(raw).hexdigest()
    assert cfg.base == {"SPY": 0.25, "TLT": 0.25, "GLD": 0.25, "SHY": 0.25}
    assert cfg.safe == "SHY"
    assert cfg.cap == 0.20
    assert cfg.cost_bps == 5
    assert cfg.trend_assets == ("SPY", "TLT", "GLD")
    assert cfg.trend_sma_days == 210
    assert cfg.trend_move == pytest.approx(0.20 / 3)  # exactly 20/3 points
    assert (cfg.vol_asset, cfg.vol_days, cfg.vol_median_days) == ("SPY", 63, 1260)
    assert (cfg.vol_ratio, cfg.vol_move) == (1.5, 0.05)
    assert (cfg.cpi_series, cfg.inflation_asset) == ("CPIAUCNS", "TLT")
    assert (cfg.inflation_yoy, cfg.inflation_lookback_months) == (0.04, 3)
    assert cfg.inflation_move == 0.05
    assert (cfg.min_sharpe_gain, cfg.max_cagr_shortfall) == (0.05, 0.01)
    assert cfg.null_percentile == 95
    assert (cfg.null_seed, cfg.null_draws) == (20261007, 1000)


def test_config_rejects_wrong_version(tmp_path):
    with pytest.raises(ValueError, match="version"):
        _load(tmp_path, SHIPPED.replace("version: 1", "version: 2"))


def test_config_rejects_missing_field(tmp_path):
    with pytest.raises(ValueError, match="missing or malformed"):
        _load(tmp_path, SHIPPED.replace("  seed: 20261007\n", ""))


def test_config_rejects_a_non_fraction_share(tmp_path):
    with pytest.raises(ValueError, match="move_share_of_cap"):
        _load(tmp_path, SHIPPED.replace('move_share_of_cap: "1/3"', 'move_share_of_cap: "a third"'))


def test_config_rejects_unknown_base(tmp_path):
    with pytest.raises(ValueError, match="not in the candidates file"):
        _load(tmp_path, SHIPPED.replace("base_id: G", "base_id: ZZ"))


def test_config_rejects_switching_base(tmp_path):
    switching = Candidate(
        "G",
        "switching",
        "core_mix",
        {"risk_on": {"SPY": 1.0}, "risk_off": {"SHY": 1.0}, "signal": "SPY", "lookback": 200},
    )
    with pytest.raises(ValueError, match="static core_mix"):
        _load(tmp_path, SHIPPED, [switching])


def test_config_rejects_asset_outside_the_base(tmp_path):
    with pytest.raises(ValueError, match="not in the base mix"):
        _load(tmp_path, SHIPPED.replace("safe_asset: SHY", "safe_asset: IEF"))


def _vol_close(n_calm: int = 1400, n_wild: int = 100) -> pd.DataFrame:
    rng = np.random.default_rng(3)
    r = np.concatenate([rng.normal(0, 0.005, n_calm), rng.normal(0, 0.03, n_wild)])
    idx = pd.bdate_range("2000-01-03", periods=len(r))
    return pd.DataFrame({"SPY": 100 * np.exp(np.cumsum(r))}, index=idx)


def test_trend_is_on_below_the_sma_and_off_in_warm_up():
    idx = pd.bdate_range("2010-01-01", periods=260)
    price = np.concatenate([np.linspace(100, 150, 240), np.linspace(149, 90, 20)])
    s = trend_states(pd.DataFrame({"SPY": price}, index=idx), ("SPY",), 210)["SPY"]
    assert s.dtype == bool
    assert not s.iloc[:240].any()  # warm-up (first 209 rows) is off, then above the SMA
    assert s.iloc[-1]


def test_vol_is_on_above_ratio_times_trailing_median_and_off_in_warm_up():
    s = vol_state(_vol_close(), "SPY", 63, 1260, 1.5)
    assert s.dtype == bool
    assert not s.iloc[:1400].any()  # 63-day vol from row 63, its 1260-day median from 1322
    assert s.iloc[-1]


def test_cpi_lag_is_applied():
    # YoY jumps from 2% to ~5.06% with the March 2005 print (observation
    # 2005-03-01). macro.yaml's 2-month-end lag makes it usable from
    # 2005-04-30 (a Saturday), so the first "on" trading day is 2005-05-02.
    idx = pd.bdate_range("2004-01-01", "2006-12-29")
    s = inflation_state(_cpi(jump_at="2005-03-01", jump=0.03), idx, 0.04, 3)
    assert not s.loc[:"2005-04-29"].any()
    assert s.loc["2005-05-02"]


def test_inflation_missing_print_counts_as_off():
    idx = pd.bdate_range("2004-01-01", "2006-12-29")
    full = inflation_state(_cpi(jump_at="2005-03-01", jump=0.03), idx, 0.04, 3)
    gap = inflation_state(_cpi(jump_at="2005-03-01", jump=0.03, missing="2005-04-01"), idx, 0.04, 3)
    assert gap.dtype == bool
    assert full.loc["2005-06-15"]
    assert not gap.loc["2005-06-15"]


def test_inflation_is_off_before_the_first_print():
    idx = pd.bdate_range("1989-01-02", "1992-12-31")
    s = inflation_state(_cpi(), idx, 0.04, 3)
    assert s.dtype == bool
    assert not s.loc[:"1990-12-31"].any()
    assert not s.loc["1992-06-15"]


def test_no_signal_leaves_nan_in_warm_up_or_with_missing_cpi():
    close = _vol_close()
    idx = pd.DatetimeIndex(close.index)
    trend = trend_states(close, ("SPY",), 210)
    vol = vol_state(close, "SPY", 63, 1260, 1.5)
    infl = inflation_state(_cpi(missing="2000-06-01"), idx, 0.04, 3)
    for out in (trend, vol, infl):
        assert not out.isna().to_numpy().any()
        assert out.to_numpy().dtype.kind == "b"
    assert not vol.iloc[:1322].any()
    assert not infl.loc[:"2001-01-31"].any()


def test_signals_are_prefix_invariant():
    # Computing on data truncated at a cut gives exactly the same values on the
    # overlapping rows as computing on the full data.
    close = _vol_close(n_calm=1500, n_wild=200)
    idx = pd.DatetimeIndex(close.index)
    cut = idx[1580]
    assert idx[1581].month == cut.month  # mid-month: not a month-end edge
    cpi = _cpi(start="1995-01-01", end="2007-12-01", jump_at="2005-01-01", jump=0.03)
    cut_cpi = cpi.loc[:cut]
    part = close.loc[:cut]

    pd.testing.assert_frame_equal(
        trend_states(close, ("SPY",), 210).loc[:cut], trend_states(part, ("SPY",), 210)
    )
    pd.testing.assert_series_equal(
        vol_state(close, "SPY", 63, 1260, 1.5).loc[:cut], vol_state(part, "SPY", 63, 1260, 1.5)
    )
    full_infl = inflation_state(cpi, idx, 0.04, 3).loc[:cut]
    part_infl = inflation_state(cut_cpi, pd.DatetimeIndex(part.index), 0.04, 3)
    pd.testing.assert_series_equal(full_infl, part_infl, check_freq=False)


def test_month_end_mask_marks_last_trading_day_and_needs_no_later_rows():
    idx = pd.bdate_range("2021-01-01", "2021-03-31")
    assert list(idx[month_end_mask(idx)]) == [
        pd.Timestamp("2021-01-29"),
        pd.Timestamp("2021-02-26"),
        pd.Timestamp("2021-03-31"),
    ]
    assert not month_end_mask(idx[idx <= "2021-02-24"])[-1]


def test_cap_scales_every_move_proportionally():
    close = _flat_close("2010-01-01", "2010-03-31")
    me = close.index[month_end_mask(close.index)]
    monthly = pd.DataFrame(1.0, index=me, columns=signal_columns(CFG))
    w = overlay_weights(monthly, close, CFG).dropna().iloc[-1]
    third = 0.20 / 3
    raw = {"SPY": third + 0.05, "TLT": third + 0.05, "GLD": third}  # sums to 0.30
    scale = 0.20 / sum(raw.values())
    for ticker, move in raw.items():
        assert w[ticker] == pytest.approx(0.25 - move * scale)
    assert w["SHY"] == pytest.approx(0.45)


def test_three_trends_alone_fill_the_cap_without_scaling():
    close = _flat_close("2010-01-01", "2010-03-31")
    me = close.index[month_end_mask(close.index)]
    monthly = pd.DataFrame(0.0, index=me, columns=signal_columns(CFG))
    monthly[["trend_SPY", "trend_TLT", "trend_GLD"]] = 1.0
    w = overlay_weights(monthly, close, CFG).dropna().iloc[-1]
    for ticker in ("SPY", "TLT", "GLD"):
        assert w[ticker] == pytest.approx(0.25 - 0.20 / 3, abs=1e-15)
    assert w["SHY"] == pytest.approx(0.45, abs=1e-15)


def test_weights_capped_nonnegative_and_sum_to_one_for_any_states():
    rng = np.random.default_rng(0)
    close = _flat_close("2000-01-03", "2009-12-31")
    me = close.index[month_end_mask(close.index)]
    cols = signal_columns(CFG)
    states = rng.choice([0.0, 1.0, np.nan], size=(len(me), len(cols)))
    w = overlay_weights(pd.DataFrame(states, index=me, columns=cols), close, CFG).dropna()
    assert (w >= 0).all().all()
    assert np.allclose(w.sum(axis=1), 1.0)
    assert (w["SHY"] - 0.25 <= 0.20 + 1e-12).all()


def test_undefined_state_is_off():
    close = _flat_close("2010-01-01", "2010-03-31")
    me = close.index[month_end_mask(close.index)]
    monthly = pd.DataFrame(np.nan, index=me, columns=signal_columns(CFG))
    w = overlay_weights(monthly, close, CFG).dropna()
    assert np.allclose(w.to_numpy(), 0.25)


def test_rows_before_first_month_end_hold_the_base_mix_and_unpriced_are_nan():
    close = _flat_close("2010-01-01", "2010-03-31")
    close.loc["2010-02-10", "GLD"] = np.nan
    me = close.index[month_end_mask(close.index)]
    w = overlay_weights(pd.DataFrame(0.0, index=me, columns=signal_columns(CFG)), close, CFG)
    assert np.allclose(w.loc[: me[0]].to_numpy(), 0.25)
    assert w.loc["2010-02-10"].isna().all()
    assert w.loc["2010-02-11"].notna().all()


def test_overlay_is_invested_on_exactly_the_days_static_g_is():
    _, close = _prices()
    close.loc[:"1999-01-12", "GLD"] = np.nan  # starts before the first month end
    w = build_overlay(close, _cpi(), CFG)
    g = core_mix(close, risk_on=CFG.base)
    assert w.notna().all(axis=1).equals(g.notna().all(axis=1))
    assert w.notna().any(axis=1).any()


def test_held_weights_are_constant_within_each_month():
    _, close = _prices()
    w = build_overlay(close, _cpi(), CFG)
    held = w.shift(1).dropna()  # the engine executes row t on day t+1
    for _, month in held.groupby(held.index.to_period("M")):
        assert (month.nunique() == 1).all()
    assert len(held.drop_duplicates()) > 1  # the signals did move the weights


@pytest.mark.parametrize("cut", ["2004-06-15", "2006-03-31", "2007-11-20"])
def test_truncating_future_data_leaves_earlier_weights_unchanged(cut):
    _, close = _prices(end="2008-12-31")
    cpi = _cpi(jump_at="2006-01-01", jump=0.03)
    full = build_overlay(close, cpi, CFG)
    part = build_overlay(close.loc[:cut], cpi.loc[:cut], CFG)
    pd.testing.assert_frame_equal(full.loc[:cut], part, check_freq=False)
