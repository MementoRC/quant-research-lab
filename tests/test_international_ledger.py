"""Ledger guards for the international final test: each market set once, in
order, with a reason; a started event can only be completed."""

from __future__ import annotations

import pytest

from qrl.ledger import Ledger, LedgerError

ORDER = ["main", "reserve_1", "reserve_2"]


def _record(ledger: Ledger, set_name: str = "main", **overrides) -> int:
    kwargs = {
        "set_name": set_name,
        "set_order": ORDER,
        "rule_id": "ledger test 1",
        "rule_sha256": "r" * 64,
        "config_sha256": "c" * 64,
        "data_end": "2026-10-19",
        "data_sha256": "d" * 64,
        "reason": "owner go-ahead",
        "git_commit": "abc",
    }
    kwargs.update(overrides)
    return ledger.record_international_event(**kwargs)


def test_an_event_is_recorded_as_started(tmp_path):
    with Ledger(tmp_path / "l.sqlite") as ledger:
        event_id = _record(ledger)
        (event,) = ledger.list_international_events()
    assert event["event_id"] == event_id
    assert event["status"] == "started"
    assert event["set_name"] == "main"
    assert event["data_end"] == "2026-10-19"
    assert event["result"] is None


def test_a_used_set_is_refused(tmp_path):
    with Ledger(tmp_path / "l.sqlite") as ledger:
        _record(ledger)
        with pytest.raises(LedgerError, match="already used"):
            _record(ledger)


def test_sets_run_in_order(tmp_path):
    with Ledger(tmp_path / "l.sqlite") as ledger:
        with pytest.raises(LedgerError, match="'main' is unused"):
            _record(ledger, "reserve_1")
        _record(ledger, "main")
        _record(ledger, "reserve_1")
        assert [e["set_name"] for e in ledger.list_international_events()] == ORDER[:2]


def test_a_reason_and_a_known_set_are_required(tmp_path):
    with Ledger(tmp_path / "l.sqlite") as ledger:
        with pytest.raises(LedgerError, match="reason"):
            _record(ledger, reason="  ")
        with pytest.raises(LedgerError, match="unknown"):
            _record(ledger, "nicer_one")


def test_complete_records_the_result_and_the_report(tmp_path):
    with Ledger(tmp_path / "l.sqlite") as ledger:
        event_id = _record(ledger)
        ledger.complete_international_event(event_id, {"verdict": {"passed": False}}, "r.md")
        (event,) = ledger.list_international_events()
    assert event["status"] == "completed"
    assert event["report_path"] == "r.md"
    assert event["result"] == {"verdict": {"passed": False}}
    assert event["completed_at"]


def test_get_test_returns_family_and_params(tmp_path):
    with Ledger(tmp_path / "l.sqlite") as ledger:
        run_id = ledger.start_run("crit", "A", git_commit="x")
        test_id = ledger.record_test(
            run_id, "crit", "core_trend", {"risk_on": "SPY", "lookback": 200}, "u", {}, True
        )
        assert ledger.get_test(test_id) == {
            "test_id": test_id,
            "run_id": run_id,
            "family": "core_trend",
            "params": {"risk_on": "SPY", "lookback": 200},
            "universe": "u",
            "passed": True,
        }
        assert ledger.get_test(test_id + 1) is None
