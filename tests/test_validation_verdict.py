"""validation_events.passed: the persisted validation verdict (owner decision,
international final test). NULL on rows written before the column existed."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from qrl.criteria import load_criteria
from qrl.ledger import Ledger, LedgerError
from qrl.search import SearchData, compute_benchmark_metrics, evaluate_candidate
from qrl.validation import load_validation_config, validate_survivors

ROOT = Path(__file__).resolve().parents[1]


def _test_id(ledger: Ledger) -> int:
    run_id = ledger.start_run("crit", "A", "verdict fixture", git_commit="x")
    return ledger.record_test(run_id, "crit", "core_trend", {"lookback": 200}, "u", {}, True)


def test_a_new_validation_row_has_no_verdict_until_one_is_set(tmp_path):
    with Ledger(tmp_path / "l.sqlite") as ledger:
        test_id = _test_id(ledger)
        assert ledger.validation_passed(test_id) is None  # no validation event at all
        ledger.record_validation(test_id, {"sharpe": 1.0})
        assert ledger.validation_passed(test_id) is None  # validated, verdict not yet set
        ledger.set_validation_verdict(test_id, True)
        assert ledger.validation_passed(test_id) is True


def test_a_rejected_verdict_reads_false(tmp_path):
    with Ledger(tmp_path / "l.sqlite") as ledger:
        test_id = _test_id(ledger)
        ledger.record_validation(test_id, {"sharpe": 1.0})
        ledger.set_validation_verdict(test_id, False)
        assert ledger.validation_passed(test_id) is False


def test_setting_a_verdict_needs_a_validation_event(tmp_path):
    with (
        Ledger(tmp_path / "l.sqlite") as ledger,
        pytest.raises(LedgerError, match="no validation event"),
    ):
        ledger.set_validation_verdict(_test_id(ledger), True)


def test_the_column_only_accepts_zero_one_or_null(tmp_path):
    with Ledger(tmp_path / "l.sqlite") as ledger:
        test_id = _test_id(ledger)
        ledger.record_validation(test_id, {"sharpe": 1.0})
        with pytest.raises(sqlite3.IntegrityError):
            ledger._conn.execute(
                "UPDATE validation_events SET passed = 2 WHERE test_id = ?", (test_id,)
            )


def test_migration_adds_passed_to_a_legacy_ledger_and_leaves_old_rows_null(tmp_path):
    path = tmp_path / "legacy.sqlite"
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(
            """
            CREATE TABLE validation_events (
                test_id INTEGER PRIMARY KEY,
                metrics_json TEXT NOT NULL,
                validation_config_hash TEXT,
                created_at TEXT NOT NULL
            );
            INSERT INTO validation_events VALUES (7, '{}', NULL, '2020-01-01T00:00:00+00:00');
            """
        )
        conn.commit()
    finally:
        conn.close()
    with Ledger(path) as ledger:
        columns = {row[1] for row in ledger._conn.execute("PRAGMA table_info(validation_events)")}
        assert "passed" in columns
        assert ledger.is_validated(7)
        assert ledger.validation_passed(7) is None  # not back-filled


def _validate(ledger: Ledger, forced_min_dsr: float | None = None, lookbacks=(200,)):
    criteria, criteria_hash = load_criteria(ROOT / "config" / "criteria.yaml")
    validation_config, validation_hash = load_validation_config(ROOT / "config" / "validation.yaml")
    if forced_min_dsr is not None:
        validation_config = {**validation_config, "min_deflated_sharpe": forced_min_dsr}
    data = SearchData.load(["QQQ", "GLD", "SPY"], synthetic=True)
    bench = compute_benchmark_metrics(data, criteria)
    run_id = ledger.start_run(criteria_hash, "A", "verdict call site")
    test_ids = []
    for lookback in lookbacks:
        params = {"lookback": lookback, "risk_off": "GLD"}
        outcome = evaluate_candidate("core_trend", params, data, criteria, bench)
        test_ids.append(
            ledger.record_test(
                run_id,
                criteria_hash,
                "core_trend",
                params,
                "qqq_gld",
                outcome["metrics"],
                True,
                None,
            )
        )
    test_id = test_ids[0] if len(test_ids) == 1 else test_ids
    report = validate_survivors(
        ledger,
        run_id,
        data,
        criteria,
        validation_config,
        validation_hash,
        criteria_hash=criteria_hash,
        universe_name="qqq_gld",
        spaces={},
        benchmark_metrics=bench,
    )
    return test_id, report


def test_validate_survivors_records_zero_for_a_rejected_candidate(tmp_path):
    # an unreachable floor (10.0) forces the deflated_sharpe rejection
    with Ledger(tmp_path / "l.sqlite") as ledger:
        test_id, report = _validate(ledger, forced_min_dsr=10.0)
        assert report["funnel"]["accepted"] == 0
        assert report["rejected"]
        assert ledger.is_validated(test_id)
        assert ledger.validation_passed(test_id) is False


def test_validate_survivors_records_zero_when_validation_has_too_few_observations(
    tmp_path, monkeypatch
):
    import qrl.validation as validation

    real = validation.evaluate_candidate

    def no_sharpe(*args, **kwargs):
        outcome = real(*args, **kwargs)
        if kwargs.get("period") == "validation":
            outcome["metrics"] = {k: v for k, v in outcome["metrics"].items() if k != "sharpe"}
        return outcome

    monkeypatch.setattr(validation, "evaluate_candidate", no_sharpe)
    with Ledger(tmp_path / "l.sqlite") as ledger:
        test_id, report = _validate(ledger, forced_min_dsr=0.0)
        assert report["rejected"][0]["reason"].startswith("validation period had too few")
        assert ledger.validation_passed(test_id) is False


def test_validate_survivors_records_zero_for_a_correlated_second_candidate(tmp_path):
    with Ledger(tmp_path / "l.sqlite") as ledger:
        (first, second), report = _validate(ledger, forced_min_dsr=-100.0, lookbacks=(200, 201))
        stages = {c["test_id"]: c["stage"] for c in report["candidates"]}
        assert stages[second] == "correlation" or stages[first] == "correlation"
        verdicts = {t: ledger.validation_passed(t) for t in (first, second)}
        assert sorted(verdicts.values()) == [False, True]


def test_validate_survivors_records_one_for_an_accepted_candidate(tmp_path):
    with Ledger(tmp_path / "l.sqlite") as ledger:
        test_id, report = _validate(ledger, forced_min_dsr=0.0)
        assert report["funnel"]["accepted"] == 1
        assert ledger.validation_passed(test_id) is True
