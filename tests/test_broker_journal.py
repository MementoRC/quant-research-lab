"""Tests for qrl.broker_journal (spec "Evening run" steps 3 and 7)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pytest

from qrl.broker import Order, SubmittedOrder
from qrl.broker_journal import (
    append_event,
    dated_path,
    expected_positions,
    latest_baseline,
    order_records,
    read_journal,
    reconcile,
    stamped_path,
    utc_iso,
    write_journal,
)

ROOT = Path(__file__).resolve().parents[1]


def _journal(root: Path, name: str, kind: str, recorded_at: str, expected: dict) -> None:
    write_journal(
        root / name, {"kind": kind, "recorded_at": recorded_at, "expected_positions": expected}
    )


def test_journal_folder_is_gitignored():
    lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "reports/" in lines


def test_utc_iso_and_paths():
    now = datetime(2026, 11, 4, 23, 30, 5, tzinfo=UTC)  # 18:30:05 EST
    assert utc_iso(now) == "2026-11-04T23:30:05+00:00"
    root = Path("r")
    assert dated_path(root, date(2026, 11, 4)) == root / "2026-11-04.json"
    assert stamped_path(root, "flatten", now) == root / "2026-11-04-flatten-183005.json"
    late = datetime(2026, 11, 5, 4, 30, tzinfo=UTC)  # 23:30 EST on 11-04
    assert stamped_path(root, "accept", late) == root / "2026-11-04-accept-233000.json"


def test_write_journal_never_overwrites(tmp_path):
    path = tmp_path / "broker" / "2026-11-04.json"
    write_journal(path, {"kind": "rebalance"})
    with pytest.raises(FileExistsError):
        write_journal(path, {"kind": "other"})
    assert json.loads(path.read_text())["kind"] == "rebalance"


def test_append_event_adds_one_line_per_call(tmp_path):
    append_event(tmp_path, {"recorded_at": "a", "status": "x"})
    append_event(tmp_path, {"recorded_at": "b", "status": "y"})
    lines = (tmp_path / "events.jsonl").read_text().splitlines()
    assert [json.loads(line)["status"] for line in lines] == ["x", "y"]


def test_baseline_is_the_greatest_recorded_at_not_the_last_filename(tmp_path):
    # "2026-11-05-accept-..." sorts BEFORE "2026-11-05.json" but was recorded later.
    _journal(tmp_path, "2026-11-05.json", "rebalance", "2026-11-05T23:30:00+00:00", {"QQQ": 158})
    _journal(
        tmp_path,
        "2026-11-05-accept-184000.json",
        "accept",
        "2026-11-05T23:40:00+00:00",
        {"QQQ": 150},
    )
    assert latest_baseline(tmp_path)["expected_positions"] == {"QQQ": 150}


def test_baseline_ignores_a_later_filename_recorded_earlier(tmp_path):
    _journal(tmp_path, "2026-11-04.json", "rebalance", "2026-11-04T23:30:00+00:00", {"QQQ": 1})
    _journal(tmp_path, "2026-11-03-flatten-120000.json", "flatten", "2026-11-05T01:00:00+00:00", {})
    _journal(tmp_path, "2026-11-09.json", "rebalance", "2026-11-04T22:00:00+00:00", {"QQQ": 9})
    assert latest_baseline(tmp_path)["kind"] == "flatten"


def test_baseline_ignores_other_files_and_handles_none(tmp_path):
    assert latest_baseline(tmp_path / "missing") is None
    write_journal(tmp_path / "notes.json", {"recorded_at": "2030-01-01T00:00:00+00:00"})
    append_event(tmp_path, {"recorded_at": "2030-01-01T00:00:00+00:00", "status": "refused"})
    assert latest_baseline(tmp_path) is None


def test_corrupt_json_halts_with_the_file_name(tmp_path):
    (tmp_path / "2026-11-04.json").write_text('{"kind": "reb', encoding="utf-8")
    with pytest.raises(ValueError, match="2026-11-04.json"):
        latest_baseline(tmp_path)


@pytest.mark.parametrize(
    "extra", [{}, {"recorded_at": "garbage"}, {"recorded_at": "2026-11-04T23:30:00"}]
)
def test_bad_recorded_at_halts_with_the_file_name(tmp_path, extra):
    write_journal(tmp_path / "2026-11-04.json", {"kind": "rebalance", **extra})
    with pytest.raises(ValueError, match="2026-11-04.json"):
        latest_baseline(tmp_path)


def test_write_journal_refuses_nan(tmp_path):
    path = tmp_path / "2026-11-04.json"
    with pytest.raises(ValueError, match="Out of range float"):
        write_journal(path, {"x": float("nan")})
    assert list(tmp_path.iterdir()) == []


def test_write_journal_serializes_dates_and_numpy(tmp_path):
    path = tmp_path / "2026-11-04.json"
    write_journal(
        path,
        {"d": date(2026, 11, 4), "t": datetime(2026, 11, 4, tzinfo=UTC), "n": np.int64(3)},
    )
    assert json.loads(path.read_text()) == {
        "d": "2026-11-04",
        "t": "2026-11-04T00:00:00+00:00",
        "n": 3,
    }
    append_event(tmp_path, {"d": date(2026, 11, 4), "n": np.float64(0.5)})
    assert json.loads((tmp_path / "events.jsonl").read_text()) == {"d": "2026-11-04", "n": 0.5}
    with pytest.raises(ValueError, match="Out of range float"):
        append_event(tmp_path, {"x": float("inf")})


def test_failed_write_leaves_no_partial_or_tmp_file(tmp_path):
    path = tmp_path / "2026-11-04.json"
    with pytest.raises(TypeError):
        write_journal(path, {"x": object()})
    assert list(tmp_path.iterdir()) == []
    write_journal(path, {"kind": "rebalance"})
    assert [p.name for p in tmp_path.iterdir()] == ["2026-11-04.json"]
    with pytest.raises(FileExistsError):
        write_journal(path, {"kind": "other"})
    assert [p.name for p in tmp_path.iterdir()] == ["2026-11-04.json"]


def test_stamped_path_collision_raises(tmp_path):
    now = datetime(2026, 11, 4, 23, 30, 5, tzinfo=UTC)
    write_journal(stamped_path(tmp_path, "flatten", now), {"kind": "flatten"})
    with pytest.raises(FileExistsError):
        write_journal(stamped_path(tmp_path, "flatten", now), {"kind": "flatten"})


def test_read_journal_round_trip_and_bad_file(tmp_path):
    path = tmp_path / "2026-11-04.json"
    write_journal(path, {"kind": "rebalance", "n": 1})
    assert read_journal(path) == {"kind": "rebalance", "n": 1}
    path.write_text("[1]", encoding="utf-8")
    with pytest.raises(ValueError, match="2026-11-04.json"):
        read_journal(path)


def test_expected_positions_count_dead_orders_as_zero():
    subs = [
        SubmittedOrder(Order("QQQ", "BUY", 8), 1, "submitted"),
        SubmittedOrder(Order("GLD", "SELL", 3), 2, "rejected"),
        SubmittedOrder(Order("SPY", "SELL", 5), 3, "submitted"),
    ]
    pre = {"QQQ": 150, "GLD": 3, "SPY": 5}
    assert expected_positions(pre, subs) == {"GLD": 3, "QQQ": 158}
    assert order_records(subs[:1]) == [
        {"symbol": "QQQ", "side": "BUY", "shares": 8, "order_id": 1, "status": "submitted"}
    ]


def test_reconcile_is_exact_symbol_by_symbol():
    assert reconcile({"QQQ": 158}, {"QQQ": 158}) == []
    assert reconcile({"QQQ": 158}, {"QQQ": 150, "XYZ": 1}) == [
        "QQQ: expected 158, IB holds 150",
        "XYZ: expected 0, IB holds 1",
    ]
    assert reconcile({}, {}) == []
