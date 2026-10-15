"""Tests for the milestone 2.5 validation module: qrl.validation, offline and
on synthetic data only. See milestone 2.5 ("Thousands of
candidates guarantee lucky winners", "The holdout was contaminated") for why
each check exists.
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest

from qrl.criteria import load_criteria
from qrl.ledger import Ledger
from qrl.search import SearchData, compute_benchmark_metrics, evaluate_candidate
from qrl.validation import (
    correlation_filter,
    deflated_sharpe_ratio,
    load_validation_config,
    neighbourhood_check,
    validate_survivors,
)

ROOT = Path(__file__).resolve().parents[1]
VALIDATION_SRC = (ROOT / "src" / "qrl" / "validation.py").read_text()
VALIDATE_CLI_SRC = (ROOT / "scripts" / "validate.py").read_text()


# ---------------------------------------------------------------------------
# Neighbourhood check: ACCEPTANCE -- a lone spike surrounded by failing
# neighbours is rejected.
# ---------------------------------------------------------------------------


def test_neighbourhood_check_rejects_a_lone_spike():
    space = {"x": [1, 2, 3, 4, 5]}
    params = {"x": 3}

    def evaluate_fn(_family: str, p: dict) -> dict:
        # Only the exact spike passes; every one-step neighbour fails.
        return {"passed": p["x"] == 3, "metrics": {}, "failure_reasons": None}

    result = neighbourhood_check("fam", params, space, evaluate_fn, fraction_required=0.6)

    assert result["passed"] is False
    assert result["fraction_passed"] == 0.0
    assert len(result["neighbours"]) == 2  # x=2 and x=4


def test_neighbourhood_check_accepts_a_robust_region():
    space = {"x": [1, 2, 3, 4, 5]}
    params = {"x": 3}

    def evaluate_fn(_family: str, _p: dict) -> dict:
        return {"passed": True, "metrics": {}, "failure_reasons": None}

    result = neighbourhood_check("fam", params, space, evaluate_fn, fraction_required=0.6)

    assert result["passed"] is True
    assert result["fraction_passed"] == 1.0


def test_neighbourhood_check_edge_parameter_has_fewer_neighbours():
    space = {"x": [1, 2, 3]}
    params = {"x": 1}  # already at the minimum -- no "down" neighbour

    def evaluate_fn(_family: str, _p: dict) -> dict:
        return {"passed": True, "metrics": {}, "failure_reasons": None}

    result = neighbourhood_check("fam", params, space, evaluate_fn, fraction_required=0.6)
    assert len(result["neighbours"]) == 1


def test_neighbourhood_check_vacuous_pass_with_no_space():
    result = neighbourhood_check("fam", {"x": 3}, {}, lambda f, p: {"passed": False}, 0.6)
    assert result["passed"] is True
    assert result["neighbours"] == []


# ---------------------------------------------------------------------------
# Deflated Sharpe ratio: hand-checked values, the annualized-to-daily
# conversion, and monotonic decrease with more trials.
# ---------------------------------------------------------------------------


def test_deflated_sharpe_ratio_hand_checked_zero_case():
    # A single trial (N=1) gives SR0=0 (nothing to deflate against yet).
    # SR annualized = 0 -> daily = 0 too. skew=0, kurtosis=3 (normal) ->
    # denominator = 1, numerator = 0 -> DSR = Phi(0) = 0.5 exactly.
    assert deflated_sharpe_ratio(0.0, [0.0], n_obs=252, skew=0.0, kurtosis=3.0) == 0.5


def test_deflated_sharpe_ratio_applies_annualized_to_daily_conversion():
    daily_sr = 1.0 / math.sqrt(252)
    # Hand-computed: single trial -> SR0 = 0. skew=0 and kurtosis=1 are
    # chosen so the variance term (1 - skew*SR + (kurtosis-1)/4 * SR^2)
    # collapses to exactly 1, isolating the annualized-to-daily conversion
    # from the skew/kurtosis correction terms -> numerator = daily_sr *
    # sqrt(251), denominator = 1.
    expected = 0.5 * (1.0 + math.erf((daily_sr * math.sqrt(251)) / math.sqrt(2.0)))
    got = deflated_sharpe_ratio(1.0, [0.0], n_obs=252, skew=0.0, kurtosis=1.0)
    assert abs(got - expected) < 1e-9

    # Treating the annualized SR as if it were already daily gives a
    # different (much larger) answer -- this guards against forgetting the
    # conversion documented in qrl.validation.annualized_to_daily_sharpe.
    wrong = 0.5 * (1.0 + math.erf((1.0 * math.sqrt(251)) / math.sqrt(2.0)))
    assert abs(got - wrong) > 0.1


def _balanced_trials(std: float, n: int) -> list[float]:
    """`n` annualized trial Sharpes with population std exactly `std` and
    mean 0, regardless of `n` -- isolates the trial-COUNT effect on the
    deflated Sharpe ratio from any effect of the trial-Sharpe spread."""
    half = n // 2
    trials = [std] * half + [-std] * half
    if n % 2:
        trials.append(0.0)
    return trials


def test_deflated_sharpe_ratio_decreases_monotonically_as_trial_count_rises():
    observed_sr, n_obs = 1.2, 756
    dsrs = [
        deflated_sharpe_ratio(observed_sr, _balanced_trials(0.3, n), n_obs, 0.0, 3.0)
        for n in (2, 10, 100, 1000)
    ]
    assert dsrs == sorted(dsrs, reverse=True)
    assert dsrs[0] > dsrs[-1]


def test_deflated_sharpe_ratio_rejects_a_decent_sharpe_once_trials_are_many():
    # ACCEPTANCE: a candidate with a decent raw (annualized) Sharpe of 1.2
    # clears the 0.95 bar when almost nothing else was tried, but not once
    # the run has tried many other candidates with a similar Sharpe spread.
    observed_sr, n_obs = 1.2, 756
    small_n_dsr = deflated_sharpe_ratio(observed_sr, _balanced_trials(0.3, 2), n_obs, 0.0, 3.0)
    large_n_dsr = deflated_sharpe_ratio(observed_sr, _balanced_trials(0.3, 1000), n_obs, 0.0, 3.0)

    assert small_n_dsr >= 0.95
    assert large_n_dsr < 0.95


# ---------------------------------------------------------------------------
# Correlation filter: drop the weaker of a highly correlated pair.
# ---------------------------------------------------------------------------


def test_correlation_filter_drops_the_weaker_of_two_correlated_candidates():
    idx = pd.bdate_range("2020-01-01", periods=60)
    trend = pd.Series(range(60), index=idx, dtype=float)
    strong = trend + 0.01  # already-accepted, stronger survivor
    weak = trend + 0.02  # a later, weaker candidate -- perfectly correlated

    result = correlation_filter(weak, [strong], max_correlation=0.7)
    assert result["passed"] is False
    assert result["correlation"] > 0.7

    # Nothing accepted yet ahead of it -- the first survivor always passes.
    result_first = correlation_filter(strong, [], max_correlation=0.7)
    assert result_first["passed"] is True
    assert result_first["correlation"] is None

    # An uncorrelated candidate against the same accepted survivor passes.
    uncorrelated = pd.Series([1, -1] * 30, index=idx, dtype=float)
    result_uncorr = correlation_filter(uncorrelated, [strong], max_correlation=0.7)
    assert result_uncorr["passed"] is True


# ---------------------------------------------------------------------------
# One shared evaluation path: qrl.search.evaluate_candidate grades both the
# research and validation periods, so they can never silently drift apart
# (same weight-building, delisting treatment, cost setting, and metrics
# call). Holdout stays refused outright.
# ---------------------------------------------------------------------------


def test_evaluate_candidate_research_and_validation_share_one_code_path():
    criteria, _ = load_criteria(ROOT / "config" / "criteria.yaml")
    # Point "validation" at the exact same date bounds as "research": if the
    # two call sites shared one code path with identical treatment, grading
    # the same candidate under each period name must reproduce the same
    # metrics, not just similar ones.
    same_bounds = criteria["periods"]["research"]
    criteria = {**criteria, "periods": {**criteria["periods"], "validation": same_bounds}}
    data = SearchData.load(["QQQ", "GLD", "SPY"], synthetic=True)
    bench = compute_benchmark_metrics(data, criteria)
    params = {"lookback": 200, "risk_off": "GLD"}

    research_outcome = evaluate_candidate(
        "core_trend", params, data, criteria, bench, period="research"
    )
    validation_outcome = evaluate_candidate(
        "core_trend", params, data, criteria, bench, period="validation"
    )

    assert research_outcome["metrics"] == validation_outcome["metrics"]
    assert research_outcome["passed"] == validation_outcome["passed"]
    assert research_outcome["returns"].equals(validation_outcome["returns"])


def test_evaluate_candidate_refuses_holdout_period():
    criteria, _ = load_criteria(ROOT / "config" / "criteria.yaml")
    data = SearchData.load(["QQQ", "GLD"], synthetic=True)

    with pytest.raises(ValueError, match="holdout"):
        evaluate_candidate(
            "core_trend", {"lookback": 200, "risk_off": "GLD"}, data, criteria, period="holdout"
        )


# ---------------------------------------------------------------------------
# One-shot validation: a second attempt is skipped, never silently re-run.
# ---------------------------------------------------------------------------


def test_validate_survivors_skips_an_already_validated_candidate(tmp_path):
    criteria, criteria_hash = load_criteria(ROOT / "config" / "criteria.yaml")
    validation_config, validation_hash = load_validation_config(ROOT / "config" / "validation.yaml")
    data = SearchData.load(["QQQ", "GLD", "SPY"], synthetic=True)
    bench = compute_benchmark_metrics(data, criteria)

    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        run_id = ledger.start_run(criteria_hash, "A", "one-shot validation test")
        params = {"lookback": 200, "risk_off": "GLD"}
        outcome = evaluate_candidate("core_trend", params, data, criteria, bench)
        test_id = ledger.record_test(
            run_id,
            criteria_hash,
            "core_trend",
            params,
            "qqq_gld",
            outcome["metrics"],
            True,  # force survivor status regardless of the real research outcome
            None,
        )

        kwargs = {
            "criteria_hash": criteria_hash,
            "universe_name": "qqq_gld",
            "spaces": {},  # no neighbours to vary -> deterministic vacuous pass
            "benchmark_metrics": bench,
        }
        report_1 = validate_survivors(
            ledger, run_id, data, criteria, validation_config, validation_hash, **kwargs
        )
        assert report_1["funnel"]["validated"] == 1
        assert ledger.is_validated(test_id)

        report_2 = validate_survivors(
            ledger, run_id, data, criteria, validation_config, validation_hash, **kwargs
        )
        assert report_2["funnel"]["validated"] == 0
        assert report_2["rejected"][0]["stage"] == "already_validated"

        count = ledger._conn.execute(
            "SELECT COUNT(*) FROM validation_events WHERE test_id = ?", (test_id,)
        ).fetchone()[0]
        assert count == 1


def test_validate_survivors_backfills_past_a_failed_top_ranked_candidate(tmp_path):
    """A failed research test with a higher sharpe than the real survivor
    must not consume the single validation slot when top_n_to_validate=1."""
    criteria, criteria_hash = load_criteria(ROOT / "config" / "criteria.yaml")
    validation_config, validation_hash = load_validation_config(ROOT / "config" / "validation.yaml")
    validation_config = {**validation_config, "top_n_to_validate": 1}
    data = SearchData.load(["QQQ", "GLD", "SPY"], synthetic=True)
    bench = compute_benchmark_metrics(data, criteria)

    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        run_id = ledger.start_run(criteria_hash, "A", "backfill past a failed top-ranked candidate")

        # Highest sharpe in the run, but failed -- must not consume the
        # single top_n_to_validate=1 slot ahead of the real passing survivor.
        ledger.record_test(
            run_id,
            criteria_hash,
            "core_trend",
            {"lookback": 50, "risk_off": "GLD"},
            "qqq_gld",
            {"sharpe": 99.0, "trades": 1},
            False,
            "max_drawdown",
        )

        params = {"lookback": 200, "risk_off": "GLD"}
        outcome = evaluate_candidate("core_trend", params, data, criteria, bench)
        test_id = ledger.record_test(
            run_id,
            criteria_hash,
            "core_trend",
            params,
            "qqq_gld",
            outcome["metrics"],
            True,  # force survivor status regardless of the real research outcome
            None,
        )

        kwargs = {
            "criteria_hash": criteria_hash,
            "universe_name": "qqq_gld",
            "spaces": {},  # no neighbours to vary -> deterministic vacuous pass
            "benchmark_metrics": bench,
        }
        report = validate_survivors(
            ledger, run_id, data, criteria, validation_config, validation_hash, **kwargs
        )

        assert report["funnel"]["survivors"] == 1
        assert report["funnel"]["validated"] == 1
        assert ledger.is_validated(test_id)


# ---------------------------------------------------------------------------
# Program-wide deflated Sharpe (audit finding 8): informational, never a gate.
# ---------------------------------------------------------------------------


def _record(ledger, run_id, criteria_hash, lookback, metrics, **kw):
    return ledger.record_test(
        run_id,
        criteria_hash,
        "core_trend",
        {"lookback": lookback, "risk_off": "GLD"},
        "qqq_gld",
        metrics,
        True,
        None,
        **kw,
    )


def test_program_trial_sharpes_pool_key_and_cutoff(tmp_path):
    with Ledger(tmp_path / "l.sqlite") as ledger:
        run_a = ledger.start_run("h", "A", "standalone a")
        run_b = ledger.start_run("h", "A", "standalone b", pass_rule="standalone")
        run_c = ledger.start_run(
            "h", "A", "combined", pass_rule="combined", combined_config_hash="c"
        )
        run_d = ledger.start_run(
            "h", "A", "null", pass_rule="combined_null", combined_config_hash="c"
        )
        comb = {"combined_config_hash": "c"}
        _record(ledger, run_a, "h", 10, {"sharpe": 1.0})
        _record(ledger, run_c, "h", 20, {"sharpe": 9.0, "improvement_sharpe": 0.5}, **comb)
        _record(ledger, run_b, "h", 30, {"trades": 1})  # no sharpe -> 0.0
        _record(ledger, run_d, "h", 40, {"sharpe": 8.0, "improvement_sharpe": 0.25}, **comb)
        _record(ledger, run_a, "h", 50, {"sharpe": 2.0})
        far_future = "9999-01-01T00:00:00+00:00"
        assert ledger.program_trial_sharpes("sharpe", up_to=far_future) == [1.0, 0.0, 2.0]
        assert ledger.program_trial_sharpes("improvement_sharpe", up_to=far_future) == [0.5, 0.25]
        # rows after the cut-off are excluded
        ledger._conn.execute(
            "UPDATE tests SET created_at = '2030-01-01T00:00:00+00:00' WHERE metrics_json LIKE '%2.0%'"
        )
        ledger._conn.commit()
        before = ledger.program_trial_sharpes("sharpe", up_to="2029-01-01T00:00:00+00:00")
        assert before == [1.0, 0.0]


def _accepted_entry(ledger, run_id, criteria_hash, validation_hash, min_dsr, data, criteria, bench):
    cfg, _ = load_validation_config(ROOT / "config" / "validation.yaml")
    cfg = {**cfg, "min_deflated_sharpe": min_dsr, "max_correlation": 1.0}
    return validate_survivors(
        ledger,
        run_id,
        data,
        criteria,
        cfg,
        validation_hash,
        criteria_hash=criteria_hash,
        universe_name="qqq_gld",
        spaces={},
        benchmark_metrics=bench,
    )


def test_program_wide_dsr_is_informational_and_pass_fail_unchanged(tmp_path):
    criteria, criteria_hash = load_criteria(ROOT / "config" / "criteria.yaml")
    _, validation_hash = load_validation_config(ROOT / "config" / "validation.yaml")
    data = SearchData.load(["QQQ", "GLD", "SPY"], synthetic=True)
    bench = compute_benchmark_metrics(data, criteria)
    params = {"lookback": 200, "risk_off": "GLD"}
    outcome = evaluate_candidate("core_trend", params, data, criteria, bench)

    def _seed(ledger, noisy_other_run: bool) -> int:
        run_id = ledger.start_run(criteria_hash, "A", "program dsr")
        ledger.record_test(
            run_id, criteria_hash, "core_trend", params, "qqq_gld", outcome["metrics"], True, None
        )
        if noisy_other_run:
            other = ledger.start_run(criteria_hash, "A", "other standalone run")
            for i, sr in enumerate([-3.0, 4.0, -2.0, 5.0, -4.0, 3.0] * 5):
                _record(ledger, other, criteria_hash, 300 + i, {"sharpe": sr})
        return run_id

    with Ledger(tmp_path / "alone.sqlite") as ledger:
        run_id = _seed(ledger, False)
        report = _accepted_entry(
            ledger, run_id, criteria_hash, validation_hash, 0.0, data, criteria, bench
        )
        (entry,) = report["accepted"]
        per_run = entry["deflated_sharpe"]
        # Alone in the ledger the program pool is the run's own trial list.
        assert entry["program_trial_count"] == len(ledger.trial_sharpes(run_id))
        assert entry["program_deflated_sharpe"] == pytest.approx(per_run)

    with Ledger(tmp_path / "program.sqlite") as ledger:
        run_id = _seed(ledger, True)
        # threshold exactly at the per-run DSR: accepted although the program-wide DSR is lower
        report = _accepted_entry(
            ledger, run_id, criteria_hash, validation_hash, per_run - 1e-9, data, criteria, bench
        )
        (entry,) = report["accepted"]
        assert entry["deflated_sharpe"] == pytest.approx(per_run)
        assert entry["program_trial_count"] == 1 + 30
        assert entry["program_deflated_sharpe"] < per_run
        assert not report["rejected"]


# ---------------------------------------------------------------------------
# The holdout stays sealed: no unseal_holdout=True anywhere in the new code,
# including comments and docstrings.
# ---------------------------------------------------------------------------


def test_no_unsealed_holdout_call_in_validation_source():
    assert "unseal_holdout=True" not in VALIDATION_SRC
    assert "unseal_holdout=True" not in VALIDATE_CLI_SRC
