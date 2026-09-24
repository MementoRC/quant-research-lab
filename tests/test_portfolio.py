"""Tests for milestone 2.7: qrl.portfolio (PLAN.md section 2.7).

Covers: capital_split is respected, the combined portfolio stays long-only
and sums to at most 1, sleeve members are equal-weighted within the
sleeve's own share, an empty sleeve degrades to core-only, and
`load_portfolio_config` validates config/portfolio.yaml's shape.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from qrl.portfolio import combine_portfolio, load_portfolio_config
from qrl.profile import load_profile
from qrl.risk import RiskLimits, load_risk_limits

ROOT = Path(__file__).resolve().parents[1]

IDX = pd.bdate_range("2020-01-01", periods=10)
SPLIT = {"core": 0.80, "sleeve": 0.20}


def _frame(columns: list[str], value: float, index: pd.DatetimeIndex = IDX) -> pd.DataFrame:
    return pd.DataFrame(value, index=index, columns=columns)


# ---------------------------------------------------------------------------
# combine_portfolio
# ---------------------------------------------------------------------------


def test_combine_portfolio_respects_the_capital_split_with_no_sleeve():
    core = _frame(["QQQ"], 1.0)

    pw = combine_portfolio(core, [], SPLIT)

    assert pw.core["QQQ"].to_numpy() == pytest.approx(0.80)
    assert pw.combined["QQQ"].to_numpy() == pytest.approx(0.80)
    assert (pw.sleeve == 0.0).all().all()


def test_combine_portfolio_equal_weights_sleeve_members_within_their_share():
    core = _frame(["QQQ"], 0.0)  # core with nothing invested, isolates the sleeve's share
    member_a = _frame(["AAA"], 1.0)
    member_b = _frame(["BBB"], 1.0)

    pw = combine_portfolio(core, [member_a, member_b], SPLIT)

    # 20% sleeve share split equally between 2 members -> 10% each.
    assert pw.sleeve["AAA"].to_numpy() == pytest.approx(0.10)
    assert pw.sleeve["BBB"].to_numpy() == pytest.approx(0.10)
    assert pw.combined["AAA"].to_numpy() == pytest.approx(0.10)
    assert pw.combined["BBB"].to_numpy() == pytest.approx(0.10)


def test_combine_portfolio_combined_is_core_plus_sleeve():
    core = _frame(["QQQ"], 1.0)
    member = _frame(["AAA"], 1.0)

    pw = combine_portfolio(core, [member], SPLIT)

    assert pw.combined["QQQ"].to_numpy() == pytest.approx(0.80)
    assert pw.combined["AAA"].to_numpy() == pytest.approx(0.20)


def test_combine_portfolio_stays_long_only_and_sums_to_at_most_one():
    core = _frame(["QQQ"], 1.0)
    members = [_frame(["AAA"], 1.0), _frame(["BBB"], 1.0), _frame(["CCC"], 1.0)]

    pw = combine_portfolio(core, members, SPLIT)

    for frame in (pw.core, pw.sleeve, pw.combined):
        assert (frame >= -1e-9).all().all()
        assert (frame.sum(axis=1) <= 1 + 1e-9).all()


def test_combine_portfolio_empty_sleeve_degrades_to_core_only():
    core = _frame(["QQQ", "GLD"], 0.5)

    pw = combine_portfolio(core, [], SPLIT)

    pd.testing.assert_frame_equal(pw.combined, pw.core)
    assert (pw.sleeve == 0.0).all().all()


def test_combine_portfolio_rejects_negative_weights():
    core = _frame(["QQQ"], -0.1)

    with pytest.raises(ValueError, match="long-only"):
        combine_portfolio(core, [], SPLIT)


def test_combine_portfolio_rejects_split_summing_above_one():
    core = _frame(["QQQ"], 1.0)

    with pytest.raises(ValueError, match="above 1"):
        combine_portfolio(core, [], {"core": 0.9, "sleeve": 0.3})


def test_combine_portfolio_with_limits_none_is_unchanged():
    core = _frame(["QQQ"], 1.0)
    member = _frame(["AAA"], 1.0)

    pw_without_arg = combine_portfolio(core, [member], SPLIT)
    pw_explicit_none = combine_portfolio(core, [member], SPLIT, limits=None)

    pd.testing.assert_frame_equal(pw_without_arg.combined, pw_explicit_none.combined)
    pd.testing.assert_frame_equal(pw_without_arg.core, pw_explicit_none.core)
    pd.testing.assert_frame_equal(pw_without_arg.sleeve, pw_explicit_none.sleeve)


def test_combine_portfolio_with_limits_raises_on_gross_exposure_over_cap():
    core = _frame(["QQQ"], 1.0)
    member = _frame(["AAA"], 1.0)
    limits = RiskLimits(
        leverage_ceiling=1.0,
        max_gross_exposure=0.5,  # strict: combined 0.80 + 0.20 = 1.0 above cap
        borrowing_cost_bps=0,
        max_loss_per_trade=1.0,
        max_open_positions=15,
    )

    with pytest.raises(ValueError, match="Risk limit violations"):
        combine_portfolio(core, [member], SPLIT, limits=limits)


def test_combine_portfolio_with_limits_raises_on_sleeve_position_over_max_loss_per_trade():
    """A sleeve member above max_loss_per_trade must still be caught -- the
    scope fix narrows the cap to the sleeve frame, it does not disable it."""
    core = _frame(["QQQ"], 0.0)
    member = _frame(["AAA"], 1.0)  # scaled to the full 0.20 sleeve share
    limits = RiskLimits(
        leverage_ceiling=1.0,
        max_gross_exposure=1.0,
        borrowing_cost_bps=0,
        max_loss_per_trade=0.10,  # sleeve member weight 0.20 > 0.10
        max_open_positions=15,
    )

    with pytest.raises(ValueError, match="Risk limit violations"):
        combine_portfolio(core, [member], SPLIT, limits=limits)


def test_combine_portfolio_with_limits_does_not_raise_on_large_core_only_position():
    """Regression for the scope bug: a large core-only combined weight
    (0.80) must not trip max_loss_per_trade, since that cap is sleeve-only
    and there is no sleeve member here."""
    core = _frame(["QQQ"], 1.0)  # combined weight 0.80
    limits = RiskLimits(
        leverage_ceiling=1.0,
        max_gross_exposure=1.0,
        borrowing_cost_bps=0,
        max_loss_per_trade=0.04,  # the strict cap the old bug applied to combined
        max_open_positions=15,
    )

    pw = combine_portfolio(core, [], SPLIT, limits=limits)

    assert pw.combined["QQQ"].to_numpy() == pytest.approx(0.80)


def test_combine_portfolio_with_limits_passes_on_compliant_frame():
    core = _frame(["QQQ"], 1.0)  # combined weight 0.80
    member = _frame(["AAA"], 1.0)  # sleeve member weight 0.20
    limits = RiskLimits(
        leverage_ceiling=1.0,
        max_gross_exposure=1.0,
        borrowing_cost_bps=0,
        max_loss_per_trade=0.20,
        max_open_positions=15,
    )

    pw = combine_portfolio(core, [member], SPLIT, limits=limits)

    assert pw.combined["QQQ"].to_numpy() == pytest.approx(0.80)


def test_shipped_limits_accept_the_shipped_core_only_portfolio():
    """Regression for the scope bug this branch fixes: the SHIPPED
    config/profile.yaml risk limits, applied to the SHIPPED
    config/portfolio.yaml core (QQQ at capital_split.core, empty sleeve),
    must not raise. Under the old bug, max_loss_per_trade (0.04) applied to
    the combined frame and rejected the core's own ~80% holding outright."""
    profile = load_profile(ROOT / "config" / "profile.yaml")
    limits = load_risk_limits(profile)
    portfolio_cfg = load_portfolio_config(ROOT / "config" / "portfolio.yaml")
    assert portfolio_cfg["sleeve"]["strategies"] == []

    core_asset = portfolio_cfg["core"]["params"]["risk_on"]  # "QQQ"
    core = _frame([core_asset], 1.0)

    pw = combine_portfolio(core, [], profile["capital_split"], limits=limits)

    assert pw.combined[core_asset].to_numpy() == pytest.approx(profile["capital_split"]["core"])


def test_combine_portfolio_never_mutates_its_inputs():
    core = _frame(["QQQ"], 1.0)
    member = _frame(["AAA"], 1.0)
    core_before = core.copy()
    member_before = member.copy()

    combine_portfolio(core, [member], SPLIT)

    pd.testing.assert_frame_equal(core, core_before)
    pd.testing.assert_frame_equal(member, member_before)


# ---------------------------------------------------------------------------
# load_portfolio_config: the committed config/portfolio.yaml, plus shape
# validation on deliberately malformed variants.
# ---------------------------------------------------------------------------


def test_load_portfolio_config_reads_the_committed_file():
    cfg = load_portfolio_config(ROOT / "config" / "portfolio.yaml")

    assert cfg["core"]["origin"] in ("baseline", "search")
    assert isinstance(cfg["sleeve"]["strategies"], list)
    assert set(cfg["provenance"]) >= {
        "ledger_run_id",
        "validation_config_hash",
        "selection_date",
        "holdout_unsealed",
    }


def test_load_portfolio_config_empty_sleeve_is_not_an_error(tmp_path):
    path = tmp_path / "portfolio.yaml"
    path.write_text(
        "core: {origin: baseline, fn: core_trend, params: {lookback: 200}}\n"
        "sleeve: {strategies: []}\n"
        "provenance: {ledger_run_id: null, validation_config_hash: null, "
        "selection_date: null, holdout_unsealed: false}\n"
    )

    cfg = load_portfolio_config(path)

    assert cfg["sleeve"]["strategies"] == []


def test_load_portfolio_config_rejects_bad_origin(tmp_path):
    path = tmp_path / "portfolio.yaml"
    path.write_text(
        "core: {origin: made_up, fn: core_trend, params: {}}\n"
        "sleeve: {strategies: []}\n"
        "provenance: {ledger_run_id: null, validation_config_hash: null, "
        "selection_date: null, holdout_unsealed: false}\n"
    )

    with pytest.raises(ValueError, match="origin"):
        load_portfolio_config(path)


def test_load_portfolio_config_rejects_sleeve_member_missing_params(tmp_path):
    path = tmp_path / "portfolio.yaml"
    path.write_text(
        "core: {origin: baseline, fn: core_trend, params: {}}\n"
        "sleeve: {strategies: [{fn: trend_pullback}]}\n"
        "provenance: {ledger_run_id: null, validation_config_hash: null, "
        "selection_date: null, holdout_unsealed: false}\n"
    )

    with pytest.raises(ValueError, match="sleeve.strategies"):
        load_portfolio_config(path)


def test_load_portfolio_config_rejects_missing_provenance(tmp_path):
    path = tmp_path / "portfolio.yaml"
    path.write_text(
        "core: {origin: baseline, fn: core_trend, params: {}}\nsleeve: {strategies: []}\n"
    )

    with pytest.raises(ValueError, match="provenance"):
        load_portfolio_config(path)
