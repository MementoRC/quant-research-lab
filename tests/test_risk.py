"""Tests for milestone 3.1: qrl.risk (PLAN.md section 3.1).

Owner decision, 2026-09-24: no leverage. Covers `load_risk_limits`
validation, `check_gross_exposure` (combined-frame cap),
`check_sleeve_positions` (sleeve-only caps: open positions, per-position
weight), `check_portfolio`/`assert_portfolio_within_limits` composing both
with the correct scope, and that the shipped `config/profile.yaml` loads
and passes its own limits.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pandas as pd
import pytest

from qrl.profile import load_profile
from qrl.risk import (
    RiskLimits,
    assert_portfolio_within_limits,
    check_gross_exposure,
    check_portfolio,
    check_sleeve_positions,
    load_risk_limits,
)

ROOT = Path(__file__).resolve().parents[1]

IDX = pd.bdate_range("2020-01-01", periods=3)


@pytest.fixture
def example_profile() -> dict:
    return load_profile(ROOT / "config" / "profile.yaml")


@pytest.fixture
def limits() -> RiskLimits:
    return RiskLimits(
        leverage_ceiling=1.0,
        max_gross_exposure=1.0,
        borrowing_cost_bps=0,
        max_loss_per_trade=0.04,
        max_open_positions=15,
    )


# ---------------------------------------------------------------------------
# load_risk_limits
# ---------------------------------------------------------------------------


def test_load_risk_limits_happy_path(example_profile):
    limits = load_risk_limits(example_profile)
    assert limits.leverage_ceiling == 1.0
    assert limits.max_gross_exposure == 1.0
    assert limits.borrowing_cost_bps == 0
    assert limits.max_loss_per_trade == 0.04
    assert limits.max_open_positions == 15


def test_load_risk_limits_rejects_missing_risk_block(example_profile):
    profile = copy.deepcopy(example_profile)
    del profile["risk"]
    with pytest.raises(ValueError, match="risk"):
        load_risk_limits(profile)


def test_load_risk_limits_rejects_missing_key(example_profile):
    profile = copy.deepcopy(example_profile)
    del profile["risk"]["max_open_positions"]
    with pytest.raises(ValueError, match="missing keys"):
        load_risk_limits(profile)


def test_load_risk_limits_rejects_non_positive_leverage_ceiling(example_profile):
    profile = copy.deepcopy(example_profile)
    profile["risk"]["leverage_ceiling"] = 0
    with pytest.raises(ValueError, match="leverage_ceiling"):
        load_risk_limits(profile)


def test_load_risk_limits_rejects_non_positive_max_gross_exposure(example_profile):
    profile = copy.deepcopy(example_profile)
    profile["risk"]["max_gross_exposure"] = -1
    with pytest.raises(ValueError, match="max_gross_exposure"):
        load_risk_limits(profile)


def test_load_risk_limits_rejects_gross_exposure_above_leverage_ceiling(example_profile):
    profile = copy.deepcopy(example_profile)
    profile["risk"]["max_gross_exposure"] = 1.5
    with pytest.raises(ValueError, match="must not exceed"):
        load_risk_limits(profile)


def test_load_risk_limits_rejects_negative_borrowing_cost(example_profile):
    profile = copy.deepcopy(example_profile)
    profile["risk"]["borrowing_cost_bps"] = -5
    with pytest.raises(ValueError, match="borrowing_cost_bps"):
        load_risk_limits(profile)


def test_load_risk_limits_rejects_max_loss_per_trade_at_zero(example_profile):
    profile = copy.deepcopy(example_profile)
    profile["risk"]["max_loss_per_trade"] = 0
    with pytest.raises(ValueError, match="max_loss_per_trade"):
        load_risk_limits(profile)


def test_load_risk_limits_rejects_max_loss_per_trade_above_one(example_profile):
    profile = copy.deepcopy(example_profile)
    profile["risk"]["max_loss_per_trade"] = 1.1
    with pytest.raises(ValueError, match="max_loss_per_trade"):
        load_risk_limits(profile)


def test_load_risk_limits_rejects_max_open_positions_below_one(example_profile):
    profile = copy.deepcopy(example_profile)
    profile["risk"]["max_open_positions"] = 0
    with pytest.raises(ValueError, match="max_open_positions"):
        load_risk_limits(profile)


def test_shipped_profile_passes_its_own_risk_limits(example_profile):
    """The committed config/profile.yaml must be internally consistent."""
    limits = load_risk_limits(example_profile)
    clean = pd.DataFrame(0.0, index=IDX, columns=["QQQ"])
    assert check_portfolio(combined=clean, sleeve=clean, limits=limits) == []


# ---------------------------------------------------------------------------
# check_gross_exposure: combined-frame-only cap.
# ---------------------------------------------------------------------------


def test_check_gross_exposure_clean_frame_returns_empty_list(limits):
    combined = pd.DataFrame({"AAA": [0.02, 0.02, 0.02], "BBB": [0.02, 0.02, 0.02]}, index=IDX)
    assert check_gross_exposure(combined, limits) == []


def test_check_gross_exposure_flags_over_cap(limits):
    combined = pd.DataFrame({"AAA": [0.6, 0.0, 0.0], "BBB": [0.6, 0.0, 0.0]}, index=IDX)
    violations = check_gross_exposure(combined, limits)
    assert any("gross exposure" in v for v in violations)


def test_check_gross_exposure_caps_examples(limits):
    columns = [f"T{i}" for i in range(20)]
    combined = pd.DataFrame(0.20, index=IDX, columns=columns)
    violations = check_gross_exposure(combined, limits)
    assert len(violations) <= 5


def test_check_gross_exposure_ignores_a_large_single_core_position(limits):
    """The whole point of the fix: a lone ~80% core holding is a combined
    gross-exposure question (0.80 <= 1.0, clean), never a per-trade one."""
    combined = pd.DataFrame({"QQQ": [0.80, 0.80, 0.80]}, index=IDX)
    assert check_gross_exposure(combined, limits) == []


# ---------------------------------------------------------------------------
# check_sleeve_positions: sleeve-frame-only caps (open positions, per-trade).
# ---------------------------------------------------------------------------


def test_check_sleeve_positions_clean_frame_returns_empty_list(limits):
    sleeve = pd.DataFrame({"AAA": [0.02, 0.02, 0.02], "BBB": [0.02, 0.02, 0.02]}, index=IDX)
    assert check_sleeve_positions(sleeve, limits) == []


def test_check_sleeve_positions_flags_too_many_open_positions(limits):
    columns = [f"T{i}" for i in range(16)]
    sleeve = pd.DataFrame(0.01, index=IDX, columns=columns)
    violations = check_sleeve_positions(sleeve, limits)
    assert any("open positions" in v for v in violations)


def test_check_sleeve_positions_flags_single_position_over_max_loss_per_trade(limits):
    sleeve = pd.DataFrame({"AAA": [0.10, 0.0, 0.0]}, index=IDX)
    violations = check_sleeve_positions(sleeve, limits)
    assert any("max_loss_per_trade" in v for v in violations)


def test_check_sleeve_positions_caps_examples_per_violation_kind(limits):
    columns = [f"T{i}" for i in range(20)]
    sleeve = pd.DataFrame(0.20, index=IDX, columns=columns)
    violations = check_sleeve_positions(sleeve, limits)
    loss_violations = [v for v in violations if "max_loss_per_trade" in v]
    assert len(loss_violations) <= 5


def test_check_sleeve_positions_empty_sleeve_is_clean(limits):
    """An all-zero sleeve (no sleeve selected, e.g. the shipped
    config/portfolio.yaml) must never be flagged by either sleeve cap."""
    empty_sleeve = pd.DataFrame(0.0, index=IDX, columns=["QQQ", "GLD"])
    assert check_sleeve_positions(empty_sleeve, limits) == []


# ---------------------------------------------------------------------------
# check_portfolio / assert_portfolio_within_limits: scope composition.
# ---------------------------------------------------------------------------


def test_check_portfolio_routes_gross_exposure_to_combined_only(limits):
    """A combined frame over gross exposure, with a clean sleeve, is still
    flagged -- the gross cap must see the combined frame."""
    combined = pd.DataFrame({"AAA": [0.6, 0.0, 0.0], "BBB": [0.6, 0.0, 0.0]}, index=IDX)
    sleeve = pd.DataFrame(0.0, index=IDX, columns=["AAA", "BBB"])
    violations = check_portfolio(combined=combined, sleeve=sleeve, limits=limits)
    assert any("gross exposure" in v for v in violations)


def test_check_portfolio_routes_per_trade_cap_to_sleeve_only(limits):
    """A combined frame carrying a large core position must NOT trip
    max_loss_per_trade or max_open_positions -- only the sleeve frame can."""
    combined = pd.DataFrame({"QQQ": [0.80, 0.80, 0.80]}, index=IDX)
    sleeve = pd.DataFrame(0.0, index=IDX, columns=["QQQ"])
    assert check_portfolio(combined=combined, sleeve=sleeve, limits=limits) == []


def test_check_portfolio_still_catches_a_sleeve_position_over_cap(limits):
    combined = pd.DataFrame({"QQQ": [0.80, 0.80, 0.80], "AAA": [0.10, 0.0, 0.0]}, index=IDX)
    sleeve = pd.DataFrame({"AAA": [0.10, 0.0, 0.0]}, index=IDX)
    violations = check_portfolio(combined=combined, sleeve=sleeve, limits=limits)
    assert any("max_loss_per_trade" in v for v in violations)


def test_assert_portfolio_within_limits_raises_on_sleeve_violation(limits):
    combined = pd.DataFrame({"AAA": [0.10, 0.0, 0.0]}, index=IDX)
    sleeve = combined
    with pytest.raises(ValueError, match="Risk limit violations"):
        assert_portfolio_within_limits(combined=combined, sleeve=sleeve, limits=limits)


def test_assert_portfolio_within_limits_passes_on_clean_frames(limits):
    combined = pd.DataFrame({"AAA": [0.02, 0.02, 0.02]}, index=IDX)
    sleeve = combined
    assert assert_portfolio_within_limits(combined=combined, sleeve=sleeve, limits=limits) is None


def test_assert_portfolio_within_limits_does_not_raise_on_large_core_only_combined(limits):
    """Direct regression for the scope bug: a large core-only combined frame
    with an empty sleeve must not raise, even though it would have under the
    old single-frame `check_weights`."""
    combined = pd.DataFrame({"QQQ": [0.80, 0.80, 0.80]}, index=IDX)
    sleeve = pd.DataFrame(0.0, index=IDX, columns=["QQQ"])
    assert assert_portfolio_within_limits(combined=combined, sleeve=sleeve, limits=limits) is None
