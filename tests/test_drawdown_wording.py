"""One drawdown rule in the decision report (spec: docs/methodology/report-wording.md,
Problem 4 and "4. One drawdown rule", new tests 2-3). Synthetic data only."""

from __future__ import annotations

import numpy as np
import pandas as pd
from decision_helpers import cpi, criteria, load, prices

from qrl import decision
from qrl.core_compare import render_markdown as render_core_compare
from qrl.decision import return_rows, run_decision
from qrl.decision_report import render_markdown as render_decision
from qrl.metrics import compute_metrics
from qrl.overlay_eval import render_markdown as render_overlay
from qrl.rsp_report import render_markdown as render_rsp
from qrl.stress import window_drawdown

FROM_START_NOTE = (
    "- Drawdowns here count the starting value as a peak. The criteria and the research "
    "dashboard use `qrl.metrics`, which does not, so their figures can be lower by up to "
    "about a point."
)


def _first_day_loss() -> pd.Series:
    index = pd.bdate_range("2005-01-03", periods=300)
    values = np.full(300, 0.001)
    values[0] = -0.10
    return pd.Series(values, index=index)


def test_return_table_drawdown_counts_a_first_day_loss(tmp_path, monkeypatch):
    series = _first_day_loss()
    monkeypatch.setattr(decision, "portfolio_returns", lambda *a, **k: series)
    rows = return_rows(load(tmp_path), prices(), criteria())
    expected = window_drawdown(series)
    assert expected > compute_metrics(series)["max_drawdown"] + 0.05
    assert rows
    assert all(r["max_drawdown"] == expected for r in rows)
    assert all(r["cagr"] == compute_metrics(series)["cagr"] for r in rows)


def test_decision_drawdown_headers_say_from_start(tmp_path):
    md = render_decision(run_decision(load(tmp_path), prices(), cpi(), criteria(), "ab" * 32))
    heads = [ln for ln in md.splitlines() if ln.startswith("|") and "drawdown" in ln.lower()]
    assert any("Max drawdown" in ln for ln in heads)
    assert any("worst drawdown" in ln for ln in heads)
    assert any("| max drawdown" in ln for ln in heads)
    assert all("drawdown (from start)" in ln for ln in heads)
    assert FROM_START_NOTE in md.splitlines()


def test_criteria_rule_drawdown_headers_in_other_reports():
    metrics = {"sharpe": 0.7, "cagr": 0.06, "max_drawdown": 0.2, "volatility": 0.08}
    result = {
        "window": ["2019-01-02", "2022-12-30"],
        "overlay": metrics,
        "G": metrics,
        "sharpe_gain": 0.0,
        "checks": [],
        "passed": False,
    }
    event = {"event_id": 1, "created_at": "2026-10-08T00:00:00+00:00", "result": result}
    header = {"overlay_sha256": "o" * 64, "candidates_sha256": "c" * 64, "criteria_hash": "abc"}
    assert "| Max drawdown (criteria rule) |" in render_overlay({"research": event}, header)

    rsp = {
        "run_id": 9,
        "passed": True,
        "failure_reasons": None,
        "metrics": {
            "trades": 1,
            "sharpe": 0.55,
            "cagr": 0.08,
            "max_drawdown": 0.5,
            "core_sharpe": 0.9,
            "core_cagr": 0.1,
            "core_max_drawdown": 0.2,
            "combined_sharpe": 0.92,
            "combined_cagr": 0.1,
            "combined_max_drawdown": 0.21,
            "improvement_sharpe": 0.1,
        },
        "validation_note": "n/a",
        "combined_config_hash": "abc123def456",
    }
    assert "| max drawdown (criteria rule) |" in render_rsp(rsp)

    bench = {
        "id": "QQQ@100",
        "label": "bench",
        "research": {"cagr": 0.1, "sharpe": 0.5, "max_drawdown": 0.3, "turnover_per_year": 0.0},
        "breach_count": 0,
    }
    report = {
        "candidates_sha256": "ab" * 32,
        "stress_sha256": "cd" * 32,
        "trial_count": 7,
        "research_period": {"start": "2005-01-01", "end": "2018-12-31"},
        "max_drawdown": 0.35,
        "capital_split": {"core": 0.8, "sleeve": 0.2},
        "excluded_windows": [],
        "candidates": [{**bench, "id": "A", "cells": []}],
        "benchmark": [bench],
    }
    md = render_core_compare(report)
    heads = [ln for ln in md.splitlines() if ln.startswith("| id | rule")]
    assert len(heads) == 2
    assert all("max drawdown (criteria rule)" in ln for ln in heads)
