"""Tests for milestone 2.6: qrl.walkforward, offline and on synthetic data
only. See PLAN.md section 2.6 and section 3 ("The holdout was
contaminated", the over-eviction point).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qrl.criteria import load_criteria
from qrl.ledger import Ledger
from qrl.search import SearchData
from qrl.walkforward import period_starts, select_sleeve, tune_meta, walk_forward

ROOT = Path(__file__).resolve().parents[1]
WALKFORWARD_SRC = (ROOT / "src" / "qrl" / "walkforward.py").read_text()
CLI_SRC = (ROOT / "scripts" / "walkforward.py").read_text()


# ---------------------------------------------------------------------------
# period_starts
# ---------------------------------------------------------------------------


def test_period_starts_includes_first_index_date_and_quarter_boundaries():
    idx = pd.bdate_range("2020-01-15", "2021-01-15")
    starts = period_starts(idx, "QS")

    assert starts[0] == idx[0]
    assert starts == sorted(set(starts))
    assert len(starts) >= 4  # Apr, Jul, Oct, Jan boundaries, plus the first date
    for boundary, later in zip(starts, starts[1:], strict=False):
        assert later > boundary


def test_period_starts_empty_index_returns_empty_list():
    assert period_starts(pd.DatetimeIndex([]), "QS") == []


# ---------------------------------------------------------------------------
# select_sleeve eviction guard: ACCEPTANCE -- a normal losing streak is
# never evicted; a stretch breaching a strategy's OWN calibrated threshold
# is.
# ---------------------------------------------------------------------------

BASE_META = {
    "n_strategies": 1,
    "lookback_days": 60,
    "min_track_days": 60,
    "eviction_dd_multiple": 1.5,
    "eviction_underperf_multiple": 2.0,
}


def _flat_then_losing(daily_loss: float, n_before: int = 120, n_losing: int = 60) -> pd.Series:
    idx = pd.bdate_range("2020-01-01", periods=n_before + n_losing)
    before = np.full(n_before, 0.0005)
    losing = np.full(n_losing, daily_loss)
    return pd.Series(np.concatenate([before, losing]), index=idx)


def _entry(returns: pd.Series, backtest_metrics: dict, test_id: int = 1) -> dict:
    return {
        "family": "core_trend",
        "params": {"lookback": 200, "risk_off": "GLD"},
        "test_id": test_id,
        "returns": returns,
        "backtest_metrics": backtest_metrics,
    }


def test_select_sleeve_does_not_evict_a_normal_losing_streak():
    returns = _flat_then_losing(daily_loss=-0.001)  # a mild, ordinary bad stretch
    entry = _entry(returns, {"max_drawdown": 0.20, "volatility": 0.20})
    as_of = returns.index[-1] + pd.Timedelta(days=1)

    selection = select_sleeve([entry], as_of, BASE_META, current_sleeve=[entry])

    assert len(selection) == 1
    assert selection[0]["test_id"] == 1


def test_select_sleeve_evicts_a_strategy_breaching_its_own_drawdown_threshold():
    returns = _flat_then_losing(daily_loss=-0.02)  # a severe, sustained drop
    entry = _entry(returns, {"max_drawdown": 0.05, "volatility": 0.10})
    as_of = returns.index[-1] + pd.Timedelta(days=1)

    selection = select_sleeve([entry], as_of, BASE_META, current_sleeve=[entry])

    assert selection == []


def test_select_sleeve_ignores_a_candidate_without_enough_trailing_history():
    idx = pd.bdate_range("2020-01-01", periods=10)
    returns = pd.Series(0.001, index=idx)
    entry = _entry(returns, {"max_drawdown": 0.1, "volatility": 0.1})
    as_of = idx[-1] + pd.Timedelta(days=1)

    selection = select_sleeve([entry], as_of, BASE_META, current_sleeve=None)

    assert selection == []


def test_select_sleeve_never_mutates_its_inputs():
    returns = _flat_then_losing(daily_loss=0.0005, n_losing=60)
    entry = _entry(returns, {"max_drawdown": 0.2, "volatility": 0.2})
    as_of = returns.index[-1] + pd.Timedelta(days=1)

    select_sleeve([entry], as_of, BASE_META, current_sleeve=[entry])

    assert "trailing_sharpe" not in entry


# ---------------------------------------------------------------------------
# walk_forward ACCEPTANCE: selection at each boundary uses no data from on
# or after that boundary. Mirrors qrl.checks.assert_causal's crash/boom
# method, applied at the walk-forward level.
# ---------------------------------------------------------------------------

CAUSAL_CANDIDATE_SPECS = [
    {"family": "core_trend", "params": {"lookback": 50, "risk_off": "GLD"}, "test_id": 1},
    {"family": "core_trend", "params": {"lookback": 100, "risk_off": "TLT"}, "test_id": 2},
]
CAUSAL_META = {
    "n_strategies": 1,
    "lookback_days": 60,
    "frequency": "QS",
    "eviction_dd_multiple": 1.5,
    "eviction_underperf_multiple": 2.0,
}


def _tamper_after(frame: pd.DataFrame, cut: pd.Timestamp, factor: float) -> pd.DataFrame:
    tampered = frame.copy()
    tampered.loc[tampered.index >= cut] *= factor
    return tampered


def _tampered_data(data: SearchData, cut: pd.Timestamp, factor: float) -> SearchData:
    return SearchData(
        open_=_tamper_after(data.open_, cut, factor),
        high=_tamper_after(data.high, cut, factor),
        low=_tamper_after(data.low, cut, factor),
        close=_tamper_after(data.close, cut, factor),
        volume=data.volume,
    )


def test_walk_forward_selection_never_uses_data_on_or_after_the_boundary():
    criteria, _ = load_criteria(ROOT / "config" / "criteria.yaml")
    data = SearchData.load(["QQQ", "GLD", "TLT"], synthetic=True)
    start, end = "2010-01-01", "2014-12-31"

    baseline = walk_forward(CAUSAL_CANDIDATE_SPECS, data, criteria, CAUSAL_META, start, end)
    boundaries = [p["as_of"] for p in baseline["selections"]]
    assert len(boundaries) >= 3
    cut = boundaries[2]

    for factor in (0.6, 1.6):
        tampered = _tampered_data(data, cut, factor)
        altered = walk_forward(CAUSAL_CANDIDATE_SPECS, tampered, criteria, CAUSAL_META, start, end)

        for base_period, alt_period in zip(
            baseline["selections"], altered["selections"], strict=True
        ):
            if base_period["as_of"] <= cut:
                assert base_period["sleeve"] == alt_period["sleeve"], (
                    f"selection at {base_period['as_of'].date()} changed when only data "
                    f"on/after {cut.date()} was altered (factor {factor})"
                )

        before_cut = baseline["weights"].index < cut
        pd.testing.assert_frame_equal(
            baseline["weights"].loc[before_cut], altered["weights"].loc[before_cut]
        )


# ---------------------------------------------------------------------------
# Stitching: no gaps or overlaps, and reselection turnover costs money.
# Uses two hand-built, deterministic price series (no randomness) whose
# trailing ranking is guaranteed to flip once, so the test does not depend
# on how a random walk happens to rank two real strategies.
# ---------------------------------------------------------------------------


def _two_phase_data(n1: int = 150, n2: int = 150) -> SearchData:
    idx = pd.bdate_range("2010-01-01", periods=n1 + n2)
    aaa = np.concatenate(
        [
            100 * np.exp(0.0025 * np.arange(n1)),
            100 * np.exp(0.0025 * n1) * np.exp(-0.0008 * np.arange(n2)),
        ]
    )
    bbb = np.concatenate(
        [
            100 * np.exp(-0.0008 * np.arange(n1)),
            100 * np.exp(-0.0008 * n1) * np.exp(0.0025 * np.arange(n2)),
        ]
    )
    close = pd.DataFrame({"AAA": aaa, "BBB": bbb}, index=idx)
    open_ = close.shift(1).bfill()
    volume = pd.DataFrame(1_000_000.0, index=idx, columns=["AAA", "BBB"])
    return SearchData(open_=open_, high=close, low=close, close=close, volume=volume)


STITCH_CANDIDATE_SPECS = [
    {"family": "buy_and_hold", "params": {"ticker": "AAA"}, "test_id": 1},
    {"family": "buy_and_hold", "params": {"ticker": "BBB"}, "test_id": 2},
]
STITCH_META = {
    "n_strategies": 1,
    "lookback_days": 40,
    "frequency": "QS",
    "eviction_dd_multiple": 1.5,
    "eviction_underperf_multiple": 2.0,
}


def test_walk_forward_stitches_without_gaps_or_overlaps_and_costs_reselection_turnover():
    criteria, _ = load_criteria(ROOT / "config" / "criteria.yaml")
    data = _two_phase_data()
    start, end = data.close.index[0], data.close.index[-1]

    result = walk_forward(STITCH_CANDIDATE_SPECS, data, criteria, STITCH_META, start, end)

    calendar = data.close.loc[start:end].index
    assert result["weights"].index.equals(calendar)
    assert result["weights"].index.is_unique

    memberships = {
        tuple(sorted((m["family"], m["params"]["ticker"]) for m in p["sleeve"]))
        for p in result["selections"]
    }
    assert len(memberships) > 1, "the engineered phases must produce a reselection"
    assert result["metrics"]["turnover_per_year"] > 0


# ---------------------------------------------------------------------------
# Meta-tuning: every setting tried is logged, and it refuses holdout dates.
# ---------------------------------------------------------------------------


def test_tune_meta_logs_every_setting_tried(tmp_path):
    criteria, criteria_hash = load_criteria(ROOT / "config" / "criteria.yaml")
    data = SearchData.load(["QQQ", "GLD", "TLT"], synthetic=True)
    search_space = {
        "n_strategies": [1],
        "lookback_days": [40, 60],
        "frequency": ["QS"],
        "eviction_dd_multiple": [1.5],
        "eviction_underperf_multiple": [2.0, 3.0],
    }
    research_start = criteria["periods"]["research"]["start"]
    validation_end = criteria["periods"]["validation"]["end"]

    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        run_id = ledger.start_run(criteria_hash, "A", "walk-forward meta tuning test")
        tried = tune_meta(
            CAUSAL_CANDIDATE_SPECS,
            data,
            criteria,
            ledger,
            run_id,
            search_space,
            research_start,
            validation_end,
        )
        logged = ledger.list_meta_tests(run_id)

    expected_combos = 1 * 2 * 1 * 1 * 2
    assert len(tried) == expected_combos
    assert len(logged) == expected_combos
    logged_metas = {tuple(sorted(row["meta"].items())) for row in logged}
    tried_metas = {tuple(sorted(t["meta"].items())) for t in tried}
    assert logged_metas == tried_metas


def test_tune_meta_refuses_to_touch_holdout_dates(tmp_path):
    criteria, criteria_hash = load_criteria(ROOT / "config" / "criteria.yaml")
    data = SearchData.load(["QQQ", "GLD"], synthetic=True)
    search_space = {"n_strategies": [1], "lookback_days": [40]}

    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        run_id = ledger.start_run(criteria_hash, "A", "refusal test")
        with pytest.raises(ValueError, match="holdout"):
            tune_meta(
                [CAUSAL_CANDIDATE_SPECS[0]],
                data,
                criteria,
                ledger,
                run_id,
                search_space,
                criteria["periods"]["research"]["start"],
                criteria["periods"]["holdout"]["start"],
            )
        assert ledger.list_meta_tests(run_id) == []


# ---------------------------------------------------------------------------
# The holdout stays sealed: no unseal_holdout=True anywhere in this
# milestone's search/tuning code path.
# ---------------------------------------------------------------------------


def test_no_unsealed_holdout_call_in_walkforward_source():
    assert "unseal_holdout=True" not in WALKFORWARD_SRC
    assert "unseal_holdout=True" not in CLI_SRC
