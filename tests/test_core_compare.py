"""Tests for the core-comparison exploration (qrl.core_compare,
scripts/core_compare.py). Offline; synthetic prices only.
Spec: docs/superpowers/specs/2026-10-03-core-compare-design.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from qrl.core_compare import load_core_candidates

ROOT = Path(__file__).resolve().parents[1]

GOOD = """
version: 1
candidates:
  - {id: T1, label: "trend", fn: core_trend, params: {risk_on: SPY, risk_off: IEF, lookback: 5}}
  - {id: T2, label: "static", fn: core_mix, params: {risk_on: {SPY: 0.6, IEF: 0.4}}}
"""


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "core_candidates.yaml"
    p.write_text(text)
    return p


def test_core_compare_shipped_candidates_load():
    cands, digest = load_core_candidates(ROOT / "config" / "core_candidates.yaml")
    assert [c.id for c in cands] == list("ABCDEFG")
    assert len(digest) == 64  # full sha256
    by_id = {c.id: c for c in cands}
    assert by_id["A"].fn == "core_trend"
    assert by_id["A"].params == {"risk_on": "QQQ", "risk_off": "GLD", "lookback": 200}
    assert by_id["C"].params["risk_off"] == "IEF"
    assert by_id["D"].fn == "core_mix"
    assert "risk_off" not in by_id["D"].params
    assert by_id["F"].params["signal"] == "SPY"


def test_core_compare_rejects_duplicate_ids(tmp_path):
    with pytest.raises(ValueError, match="duplicate"):
        load_core_candidates(_write(tmp_path, GOOD.replace("id: T2", "id: T1")))


def test_core_compare_rejects_unknown_fn(tmp_path):
    with pytest.raises(ValueError, match="fn must be"):
        load_core_candidates(_write(tmp_path, GOOD.replace("fn: core_mix", "fn: buy_and_hold")))


def test_core_compare_rejects_cash_risk_off(tmp_path):
    with pytest.raises(ValueError, match="CASH"):
        load_core_candidates(_write(tmp_path, GOOD.replace("risk_off: IEF", "risk_off: CASH")))


def test_core_compare_rejects_empty_candidates(tmp_path):
    with pytest.raises(ValueError, match="non-empty"):
        load_core_candidates(_write(tmp_path, "version: 1\ncandidates: []\n"))


def test_core_compare_rejects_params_the_strategy_rejects(tmp_path):
    with pytest.raises(ValueError, match="above 1"):
        load_core_candidates(_write(tmp_path, GOOD.replace("IEF: 0.4", "IEF: 0.9")))


def test_core_compare_rejects_bad_id(tmp_path):
    # quoted: an unquoted `T[1]` would be a YAML syntax error, not a bad id
    with pytest.raises(ValueError, match="id"):
        load_core_candidates(_write(tmp_path, GOOD.replace("id: T1", 'id: "T[1]"')))


def test_core_compare_rejects_malformed_yaml(tmp_path):
    with pytest.raises(ValueError, match="valid YAML"):
        load_core_candidates(_write(tmp_path, "version: 1\ncandidates: [unclosed\n"))


def test_core_compare_rejects_non_mapping_params(tmp_path):
    text = GOOD.replace("params: {risk_on: SPY, risk_off: IEF, lookback: 5}", "params: [SPY]")
    with pytest.raises(ValueError, match="mapping"):
        load_core_candidates(_write(tmp_path, text))
