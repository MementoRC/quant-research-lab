"""Tests for milestone 2.6's holdout gateway: qrl.holdout, offline and on
synthetic data only. See PLAN.md section 2.6 and section 3 ("The holdout
was contaminated").
"""

from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
import pytest

from qrl.criteria import load_criteria
from qrl.holdout import HoldoutAlreadyUnsealedError, unseal
from qrl.ledger import Ledger

ROOT = Path(__file__).resolve().parents[1]


def _sample_frame() -> pd.DataFrame:
    idx = pd.bdate_range("2005-01-01", "2024-12-31")
    return pd.DataFrame({"QQQ": 1.0}, index=idx)


# ---------------------------------------------------------------------------
# Refuses without confirm; records an event on success.
# ---------------------------------------------------------------------------


def test_unseal_refuses_without_confirm(tmp_path):
    criteria, _ = load_criteria(ROOT / "config" / "criteria.yaml")
    frame = _sample_frame()

    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        with pytest.raises(ValueError, match="confirm=True"):
            unseal(ledger, frame, criteria, "trying without confirm")
        assert ledger.list_holdout_events() == []


def test_unseal_records_event_and_returns_the_holdout_slice(tmp_path):
    criteria, _ = load_criteria(ROOT / "config" / "criteria.yaml")
    frame = _sample_frame()
    holdout_start = pd.Timestamp(criteria["periods"]["holdout"]["start"])

    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        sliced = unseal(
            ledger, frame, criteria, "final chosen process", confirm=True, git_commit="deadbeef"
        )
        events = ledger.list_holdout_events()

    assert len(sliced) > 0
    assert (sliced.index >= holdout_start).all()
    assert len(events) == 1
    assert events[0]["reason"] == "final chosen process"
    assert events[0]["git_commit"] == "deadbeef"
    assert events[0]["forced"] is False


# ---------------------------------------------------------------------------
# A second attempt is refused, naming the first; a forced repeat is
# recorded and flagged.
# ---------------------------------------------------------------------------


def test_unseal_second_attempt_refused_and_names_the_first(tmp_path):
    criteria, _ = load_criteria(ROOT / "config" / "criteria.yaml")
    frame = _sample_frame()
    ledger_path = tmp_path / "ledger.sqlite"

    with Ledger(ledger_path) as ledger:
        unseal(ledger, frame, criteria, "first reason", confirm=True, git_commit="commit-1")
        with pytest.raises(HoldoutAlreadyUnsealedError) as exc_info:
            unseal(ledger, frame, criteria, "second reason", confirm=True, git_commit="commit-2")

    message = str(exc_info.value)
    assert "commit-1" in message
    assert "first reason" in message

    with Ledger(ledger_path) as ledger:
        assert len(ledger.list_holdout_events()) == 1


def test_unseal_forced_repeat_is_recorded_and_flagged(tmp_path):
    criteria, _ = load_criteria(ROOT / "config" / "criteria.yaml")
    frame = _sample_frame()

    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        unseal(ledger, frame, criteria, "first reason", confirm=True, git_commit="commit-1")
        unseal(
            ledger,
            frame,
            criteria,
            "re-run after a bugfix",
            confirm=True,
            force=True,
            git_commit="commit-2",
        )
        events = ledger.list_holdout_events()

    assert len(events) == 2
    assert events[0]["forced"] is False
    assert events[1]["forced"] is True
    assert events[1]["reason"] == "re-run after a bugfix"


def test_unseal_forced_repeat_still_requires_a_reason(tmp_path):
    criteria, _ = load_criteria(ROOT / "config" / "criteria.yaml")
    frame = _sample_frame()

    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        unseal(ledger, frame, criteria, "first reason", confirm=True)
        with pytest.raises(ValueError, match="reason"):
            unseal(ledger, frame, criteria, "", confirm=True, force=True)


def test_unseal_without_force_after_a_prior_event_never_records_a_second(tmp_path):
    criteria, _ = load_criteria(ROOT / "config" / "criteria.yaml")
    frame = _sample_frame()

    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        unseal(ledger, frame, criteria, "first reason", confirm=True)
        with pytest.raises(HoldoutAlreadyUnsealedError):
            unseal(ledger, frame, criteria, "oops, forgot force", confirm=True)
        assert len(ledger.list_holdout_events()) == 1


# ---------------------------------------------------------------------------
# ACCEPTANCE: exactly one call site in src/ passes unseal_holdout=True, and
# it lives inside qrl.holdout.unseal.
# ---------------------------------------------------------------------------


def _unseal_true_call_sites(root: Path) -> list[tuple[Path, int]]:
    """Every AST `Call` node anywhere under `root` that passes the keyword
    argument `unseal_holdout=True` -- deliberately AST-based, not a plain
    text search, so a string that merely mentions the flag (like
    `qrl.periods`'s pre-existing, locked sealed-holdout error message) is
    never mistaken for an actual call site."""
    hits: list[tuple[Path, int]] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if (
                    kw.arg == "unseal_holdout"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value is True
                ):
                    hits.append((path, node.lineno))
    return hits


def test_exactly_one_unseal_holdout_true_call_site_in_src():
    hits = _unseal_true_call_sites(ROOT / "src")
    assert len(hits) == 1
    path, _lineno = hits[0]
    assert path == ROOT / "src" / "qrl" / "holdout.py"


def test_new_milestone_2_6_files_do_not_spell_out_the_literal_elsewhere():
    # The ONE real call site inside qrl.holdout.unseal, and nowhere else --
    # no docstring or comment in these new files spells out the literal
    # keyword argument (qrl.periods is pre-existing, locked by AGENTS.md,
    # and already mentions it once in its own sealed-holdout error message;
    # this test does not touch that file).
    holdout_src = (ROOT / "src" / "qrl" / "holdout.py").read_text()
    assert holdout_src.count("unseal_holdout=True") == 1

    walkforward_src = (ROOT / "src" / "qrl" / "walkforward.py").read_text()
    assert "unseal_holdout=True" not in walkforward_src

    for script in ("walkforward.py", "unseal_holdout.py"):
        assert "unseal_holdout=True" not in (ROOT / "scripts" / script).read_text()
