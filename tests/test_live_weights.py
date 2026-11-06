"""Tests for qrl.live_weights: the combined portfolio's live weights, shared by
scripts/daily_check.py and the IB paper rebalancer. Offline, hand-built closes."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qrl.live_weights import (
    build_market,
    extra_fields,
    make_combine,
    member_tickers,
    weight_fns,
)
from qrl.risk import RiskLimits

CORE = {"fn": "core_trend", "params": {"risk_on": "QQQ", "risk_off": "GLD", "lookback": 3}}
SPLIT = {"core": 0.8, "sleeve": 0.2}
LIMITS = RiskLimits(1.0, 1.0, 0.0, 0.04, 30)


def _close(end: str = "2026-11-04", periods: int = 10) -> pd.DataFrame:
    index = pd.bdate_range(end=end, periods=periods)
    return pd.DataFrame({"QQQ": np.linspace(100.0, 110.0, periods), "GLD": 200.0}, index=index)


def test_member_tickers_and_extra_fields():
    assert member_tickers([CORE]) == ["GLD", "QQQ"]
    assert extra_fields([CORE]) == set()


def test_weight_fns_keys_follow_the_daily_check_convention():
    member = {"fn": "core_trend", "params": {"risk_on": "SPY", "risk_off": "TLT", "lookback": 3}}
    assert list(weight_fns(CORE, [member], {})) == ["core", "sleeve_0_core_trend"]


def test_make_combine_scales_the_core_by_its_capital_share():
    close = _close()
    weights = {"core": weight_fns(CORE, [], {})["core"](close)}
    combined, sleeve = make_combine(SPLIT)(weights)
    assert combined.iloc[-1].to_dict() == pytest.approx({"QQQ": 0.8, "GLD": 0.0})
    assert (sleeve == 0.0).all().all()


def test_make_combine_needs_the_core():
    with pytest.raises(RuntimeError, match="core weights unavailable"):
        make_combine(SPLIT)({})


def test_build_market_returns_combined_weights_when_healthy():
    close = _close()
    market = build_market(
        close=close,
        fns=weight_fns(CORE, [], {}),
        combine=make_combine(SPLIT),
        limits=LIMITS,
        as_of=pd.Timestamp("2026-11-04"),
    )
    assert market.health.ok
    assert market.close is close
    assert sorted(market.combined.columns) == ["GLD", "QQQ"]
    assert market.combined.iloc[-1]["QQQ"] == pytest.approx(0.8)


def test_build_market_returns_no_weights_when_health_fails():
    market = build_market(
        close=_close(end="2026-10-28"),
        fns=weight_fns(CORE, [], {}),
        combine=make_combine(SPLIT),
        limits=LIMITS,
        as_of=pd.Timestamp("2026-11-04"),
    )
    assert not market.health.ok
    assert market.combined.empty
