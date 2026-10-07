"""Tests for the ledger's overlay_events table (used by scripts/overlay.py).
Spec: docs/methodology/macro-overlay.md.
"""

from __future__ import annotations

import sqlite3

import pytest

from qrl.ledger import Ledger, LedgerError


def test_overlay_event_roundtrip_started_then_done(tmp_path):
    with Ledger(tmp_path / "l.sqlite") as ledger:
        eid = ledger.record_overlay_event("research", "o" * 64)
        (ev,) = ledger.list_overlay_events("research")
        assert (ev["status"], ev["passed"], ev["result"]) == ("started", None, None)
        ledger.finish_overlay_event(eid, passed=False, result={"sharpe_gain": 0.01})
        (ev,) = ledger.list_overlay_events("research")
        assert ev["event_id"] == eid
        assert ev["status"] == "done"
        assert ev["passed"] is False
        assert ev["result"] == {"sharpe_gain": 0.01}
        assert ev["overlay_sha256"] == "o" * 64
        assert ledger.list_overlay_events("validate") == []
        assert len(ledger.list_overlay_events()) == 1


def test_second_holdout_event_is_refused(tmp_path):
    with Ledger(tmp_path / "l.sqlite") as ledger:
        ledger.record_overlay_event("holdout", "o", reason="owner go-ahead")
        with pytest.raises(LedgerError, match="holdout"):
            ledger.record_overlay_event("holdout", "o", reason="again")
        assert len(ledger.list_overlay_events("holdout")) == 1


def test_one_holdout_is_also_enforced_by_the_database(tmp_path):
    path = tmp_path / "l.sqlite"
    with Ledger(path) as ledger:
        ledger.record_overlay_event("holdout", "o")
    conn = sqlite3.connect(path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO overlay_events (kind, overlay_sha256, status, created_at) "
            "VALUES ('holdout', 'o', 'started', 'x')"
        )
    conn.close()


def test_unknown_overlay_kind_is_refused(tmp_path):
    with Ledger(tmp_path / "l.sqlite") as ledger, pytest.raises(LedgerError, match="kind"):
        ledger.record_overlay_event("tuning", "o")


def test_pre_existing_ledger_gains_the_table(tmp_path):
    path = tmp_path / "old.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE holdout_events (event_id INTEGER PRIMARY KEY, what_unsealed TEXT)")
    conn.commit()
    conn.close()
    with Ledger(path) as ledger:
        assert ledger.list_overlay_events() == []
