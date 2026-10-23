"""The decision helper's core A evidence section: figures come from the ledger,
a missing ledger or rows gives a one-line note, and the wording recommends nothing."""

from __future__ import annotations

import json
import re
import sqlite3

from qrl.decision_core_a import TITLE, UNAVAILABLE, render_core_a_section
from qrl.ledger import Ledger
from qrl.site_core import DECISION_PATH, build_decision

CRITERIA = {"pass": {"min_sharpe": 0.5, "beat_benchmark": "QQQ", "beat_on": "sharpe"}}


def _market(name: str, rule_sharpe: float, bh_sharpe: float, rule_dd: float, bh_dd: float) -> dict:
    return {
        "market": name,
        "enough_data": True,
        "rule": {"sharpe": rule_sharpe, "cagr": 0.10, "max_drawdown": rule_dd},
        "buy_and_hold": {"sharpe": bh_sharpe, "cagr": 0.12, "max_drawdown": bh_dd},
        "windows": [{"start": "2023-01-01", "end": "2026-10-21"}],
    }


MARKETS = [
    _market("EWJ", 0.81, 1.03, 0.212, 0.147),
    _market("EWU", 0.98, 1.14, 0.143, 0.126),
    _market("EWA", 0.62, 0.66, 0.221, 0.219),
]
RESULT = {
    "verdict": {
        "passed_markets": 0,
        "markets": 7,
        "required": 5,
        "average_sharpe_gain": -0.21,
        "passed": False,
    },
    "markets": MARKETS,
    "late_only": True,
    "gold_correlation": 0.93,
    "subject_status": "designated_unvalidated",
}


def _seed_us(path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        "INSERT INTO runs (run_id, started_at, criteria_hash, seed_lane) VALUES (8, 't', 'h', 'A')"
    )
    conn.execute(
        "INSERT INTO tests (test_id, run_id, family, params_json, universe, period, "
        "metrics_json, passed, failure_reasons, candidate_key, created_at) "
        "VALUES (1496, 8, 'core_trend', ?, 'u', 'research', ?, 0, ?, 'k', 't')",
        (
            json.dumps({"risk_on": "QQQ", "risk_off": "GLD", "lookback": 200}),
            json.dumps({"sharpe": 0.477, "cagr": 0.073, "max_drawdown": 0.299, "trades": 112}),
            "min_sharpe,beat_benchmark",
        ),
    )
    conn.commit()
    conn.close()


def _ledger(tmp_path, us: bool = True, intl: bool = True):
    path = tmp_path / "ledger.sqlite"
    with Ledger(path) as ledger:
        if intl:
            event = ledger.record_international_event(
                "main",
                ["main"],
                "rule",
                "r" * 64,
                "c" * 64,
                "2026-10-21",
                "d" * 64,
                "go-ahead",
                git_commit="abc",
            )
            ledger.complete_international_event(event, RESULT, "research/international_main.md")
    if us:
        _seed_us(path)
    return path


def test_section_renders_the_expected_numbers(tmp_path):
    text = render_core_a_section(_ledger(tmp_path), CRITERIA, 0.95)
    assert text.startswith(TITLE)
    assert "run 8, test 1496" in text
    assert "0.477" in text
    assert "at least 0.5" in text
    assert "Full report: research/international_main.md." in text
    assert "7.3%" in text
    assert "29.9%" in text
    assert "Trades: 112" in text
    assert "did not beat the QQQ index on Sharpe" in text
    assert "no validation was run" in text
    assert "subject not validated" in text
    assert "2023-01-01 to 2026-10-21" in text
    assert "0.93, below the 0.95 needed" in text
    assert "0 of 7 markets passed (the test needs 5)" in text
    assert "-0.21" in text
    assert "| EWJ | 0.81 | 1.03 | 10.0% vs 12.0% | 21.2% vs 14.7% |" in text
    assert "below simply holding the market in 3 of 3 markets" in text
    assert "bigger than buy-and-hold's in 3 of 3 markets" in text
    assert "The decision is the owner's." in text


def test_section_without_rows_is_a_one_line_note(tmp_path):
    with Ledger(tmp_path / "empty.sqlite"):
        pass
    text = render_core_a_section(tmp_path / "empty.sqlite", CRITERIA)
    assert text.splitlines()[0] == TITLE
    assert UNAVAILABLE in text
    assert len([ln for ln in text.splitlines() if ln.strip()]) == 2


def test_section_without_a_ledger_file_is_a_note_and_creates_nothing(tmp_path):
    path = tmp_path / "missing.sqlite"
    assert UNAVAILABLE in render_core_a_section(path, CRITERIA)
    assert not path.exists()


def test_section_with_only_one_source_still_renders(tmp_path):
    us_only = render_core_a_section(_ledger(tmp_path, intl=False), CRITERIA)
    assert "0.477" in us_only
    assert "International final test" not in us_only
    other = tmp_path / "b"
    other.mkdir()
    intl_only = render_core_a_section(_ledger(other, us=False), CRITERIA)
    assert "0 of 7 markets passed" in intl_only
    assert "US research period" not in intl_only


def test_dashboard_block_leaves_the_core_a_section_out(tmp_path):
    (tmp_path / "research").mkdir()
    ledger = _ledger(tmp_path)
    md = "# T\n\n- data: x\n\n## Notes\n\n- n\n\n" + render_core_a_section(ledger, CRITERIA)
    (tmp_path / DECISION_PATH).write_text(md)
    block = build_decision(tmp_path)
    assert block is not None
    assert [s["title"] for s in block["sections"]] == ["Notes"]


def test_section_has_no_recommendation_wording(tmp_path):
    text = render_core_a_section(_ledger(tmp_path), CRITERIA, 0.95).lower()
    assert not re.search(
        r"recommend|should|switch to|you must|best choice", text.replace("not a recommendation", "")
    )
    assert "$" not in text
