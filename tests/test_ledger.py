import csv
import json
import sqlite3
import sys
from pathlib import Path

import pytest

from qrl.ledger import Ledger, LedgerError, candidate_key

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from export_ledger import main as export_main  # noqa: E402

CRITERIA_HASH = "abc123def456"


def _make_run(ledger: Ledger, criteria_hash: str = CRITERIA_HASH, lane: str = "A") -> int:
    return ledger.start_run(criteria_hash, lane, "seed description")


def _seed_tests(ledger: Ledger, run_id: int) -> None:
    ledger.record_test(
        run_id,
        CRITERIA_HASH,
        "trend_pullback",
        {"lookback": 20},
        "sp500",
        {"sharpe": 1.8, "trades": 40},
        passed=True,
    )
    ledger.record_test(
        run_id,
        CRITERIA_HASH,
        "trend_pullback",
        {"lookback": 30},
        "sp500",
        {"sharpe": 0.5, "trades": 10},
        passed=False,
        failure_reasons="min_sharpe",
    )
    ledger.record_test(
        run_id,
        CRITERIA_HASH,
        "low_range_close",
        {"k": 5},
        "sp500",
        {"sharpe": 2.1, "trades": 60},
        passed=True,
    )
    ledger.record_test(
        run_id,
        CRITERIA_HASH,
        "low_range_close",
        {"k": 8},
        "sp500",
        {"sharpe": 0.2, "trades": 5},
        passed=False,
        failure_reasons="min_sharpe",
    )


def test_schema_creation_and_reopen_idempotent(tmp_path):
    ledger_path = tmp_path / "ledger.sqlite"
    with Ledger(ledger_path) as ledger:
        run_id = _make_run(ledger)
        assert run_id == 1

    # Reopening must not fail, duplicate the schema, or reset the version.
    with Ledger(ledger_path) as ledger:
        conn = sqlite3.connect(str(ledger_path))
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        conn.close()
        assert version == 1
        run_id_2 = _make_run(ledger)
        assert run_id_2 == 2
        assert len(ledger.list_runs()) == 2


def test_record_test_refused_on_criteria_hash_mismatch(tmp_path):
    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        run_id = _make_run(ledger, criteria_hash="hash-a")
        with pytest.raises(LedgerError, match="criteria hash mismatch"):
            ledger.record_test(
                run_id,
                "hash-b",
                "trend_pullback",
                {"lookback": 20},
                "sp500",
                {"sharpe": 1.0},
                passed=True,
            )


def test_record_test_unknown_run_raises(tmp_path):
    with (
        Ledger(tmp_path / "ledger.sqlite") as ledger,
        pytest.raises(LedgerError, match="unknown run_id"),
    ):
        ledger.record_test(
            999,
            CRITERIA_HASH,
            "trend_pullback",
            {},
            "sp500",
            {"sharpe": 1.0},
            passed=False,
        )


def test_tests_table_rejects_non_research_period(tmp_path):
    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        run_id = _make_run(ledger)
        with pytest.raises(LedgerError):
            ledger.record_test(
                run_id,
                CRITERIA_HASH,
                "trend_pullback",
                {"lookback": 20},
                "sp500",
                {"sharpe": 1.0},
                passed=True,
                period="holdout",
            )


def test_validation_events_unique_per_test(tmp_path):
    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        run_id = _make_run(ledger)
        test_id = ledger.record_test(
            run_id,
            CRITERIA_HASH,
            "trend_pullback",
            {"lookback": 20},
            "sp500",
            {"sharpe": 1.5},
            passed=True,
        )
        ledger.record_validation(test_id, {"sharpe": 1.2})
        with pytest.raises(LedgerError, match="already has a validation event"):
            ledger.record_validation(test_id, {"sharpe": 1.3})


def test_notes_round_trip(tmp_path):
    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        run_id = _make_run(ledger)
        note_id = ledger.record_note(run_id, 1, "tried wider stops")
        row = ledger._conn.execute(
            "SELECT run_id, batch_no, text FROM notes WHERE note_id = ?", (note_id,)
        ).fetchone()
        assert row["run_id"] == run_id
        assert row["batch_no"] == 1
        assert row["text"] == "tried wider stops"


def test_holdout_events_round_trip(tmp_path):
    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        event_id = ledger.record_holdout_event(
            "final sleeve selection", "one-time final check", git_commit="deadbeef"
        )
        row = ledger._conn.execute(
            "SELECT what_unsealed, git_commit, reason FROM holdout_events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        assert row["what_unsealed"] == "final sleeve selection"
        assert row["git_commit"] == "deadbeef"
        assert row["reason"] == "one-time final check"


def test_summary_funnel_counts(tmp_path):
    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        run_id = _make_run(ledger)
        _seed_tests(ledger, run_id)
        summary = ledger.summary(run_id)

        assert summary["tested"] == 4
        assert summary["passed"] == 2
        assert summary["by_family"]["trend_pullback"] == {"tested": 2, "passed": 1}
        assert summary["by_family"]["low_range_close"] == {"tested": 2, "passed": 1}
        assert summary["near_misses"] == {"min_sharpe": 2}
        assert summary["validated"] == 0


def test_summary_and_top_candidates_unfiltered_across_runs(tmp_path):
    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        run_a = _make_run(ledger, lane="A")
        run_b = _make_run(ledger, lane="B")
        _seed_tests(ledger, run_a)
        ledger.record_test(
            run_b,
            CRITERIA_HASH,
            "core_trend",
            {"lookback": 200},
            "qqq_gld",
            {"sharpe": 3.0, "trades": 4},
            passed=True,
        )

        overall = ledger.summary(run_id=None)
        assert overall["tested"] == 5
        assert overall["passed"] == 3
        assert overall["by_family"]["core_trend"] == {"tested": 1, "passed": 1}

        top_overall = ledger.top_candidates(run_id=None, n=1, order_by="sharpe")
        assert top_overall[0]["family"] == "core_trend"
        assert top_overall[0]["run_id"] == run_b

        # The per-run view is unaffected by the other run's rows.
        assert ledger.summary(run_id=run_a)["tested"] == 4
        assert ledger.top_candidates(run_id=run_a, n=1)[0]["family"] == "low_range_close"


def test_top_candidates_ordering_and_limit(tmp_path):
    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        run_id = _make_run(ledger)
        _seed_tests(ledger, run_id)
        top = ledger.top_candidates(run_id=run_id, n=2, order_by="sharpe")

        assert len(top) == 2
        assert [c["family"] for c in top] == ["low_range_close", "trend_pullback"]
        assert top[0]["metrics"]["sharpe"] == 2.1


def test_candidate_key_stable_across_dict_order():
    key_a = candidate_key("trend_pullback", {"lookback": 20, "drop_pct": 0.03}, "sp500", "research")
    key_b = candidate_key("trend_pullback", {"drop_pct": 0.03, "lookback": 20}, "sp500", "research")
    assert key_a == key_b


def test_export_writes_expected_json_and_csv(tmp_path):
    ledger_path = tmp_path / "ledger.sqlite"
    with Ledger(ledger_path) as ledger:
        run_id = _make_run(ledger)
        _seed_tests(ledger, run_id)
        test_id = ledger.top_candidates(run_id=run_id, n=1)[0]["test_id"]
        ledger.record_validation(test_id, {"sharpe": 2.0})

    json_out = tmp_path / "site" / "data" / "research.json"
    csv_out = tmp_path / "research" / "top_candidates.csv"
    exit_code = export_main(
        [
            "--ledger",
            str(ledger_path),
            "--json-out",
            str(json_out),
            "--csv-out",
            str(csv_out),
            "--top-n",
            "3",
        ]
    )
    assert exit_code == 0

    payload = json.loads(json_out.read_text())
    assert set(payload.keys()) == {"funnel", "by_family", "near_misses", "total_attempts", "runs"}
    assert payload["funnel"] == {"tested": 4, "passed_research": 2, "validated": 1}
    assert payload["runs"][0]["seed_lane"] == "A"

    with csv_out.open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 3
    assert rows[0]["family"] == "low_range_close"
    assert set(rows[0].keys()) == {
        "test_id",
        "run_id",
        "family",
        "params",
        "universe",
        "passed",
        "validated",
        "sharpe",
        "cagr",
        "max_drawdown",
        "trades",
    }


def test_export_missing_ledger_is_a_noop(tmp_path):
    exit_code = export_main(["--ledger", str(tmp_path / "nope.sqlite")])
    assert exit_code == 0
