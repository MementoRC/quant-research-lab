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
from qrl.macro import lag_to_availability, load_macro_config
from qrl.overlay import inflation_state, load_overlay_config, trend_states, vol_state

ROOT = Path(__file__).resolve().parents[1]
SHIPPED = (ROOT / "config" / "overlay.yaml").read_text()
CANDS, _ = load_core_candidates(ROOT / "config" / "core_candidates.yaml")
CPI_LAG = load_macro_config(ROOT / "config" / "macro.yaml")["series"]["CPIAUCNS"]["lag"]


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
    gap = inflation_state(
        _cpi(jump_at="2005-03-01", jump=0.03, missing="2005-04-01"), idx, 0.04, 3
    )
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
        assert (out.dtypes == bool).all() if isinstance(out, pd.DataFrame) else out.dtype == bool
    assert not vol.iloc[:1322].any()
    assert not infl.loc[:"2001-01-31"].any()


def test_signals_are_prefix_invariant():
    # Computing on data truncated at a cut gives exactly the same values on the
    # overlapping rows as computing on the full data.
    close = _vol_close(n_calm=1500, n_wild=200)
    idx = pd.DatetimeIndex(close.index)
    cut = idx[1580]  # not a month edge or holiday-sensitive
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
