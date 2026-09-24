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
