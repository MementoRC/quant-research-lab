"""Tests for the macro overlay's pass rule, step results and report
(qrl.overlay_eval). Offline; synthetic data only.
Spec: docs/methodology/macro-overlay.md.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import pandas as pd

from qrl import overlay_eval, overlay_null
from qrl.core_compare import load_core_candidates
from qrl.criteria import load_criteria
from qrl.data import synthetic_prices
from qrl.macro import lag_to_availability, load_macro_config
from qrl.overlay import load_overlay_config
from qrl.overlay_eval import (
    evaluate_pass,
    render_markdown,
    research_result,
    validation_result,
    window_result,
)

ROOT = Path(__file__).resolve().parents[1]
CANDS, _ = load_core_candidates(ROOT / "config" / "core_candidates.yaml")
CFG, _ = load_overlay_config(ROOT / "config" / "overlay.yaml", CANDS)
CRITERIA = load_criteria(ROOT / "config" / "criteria.yaml")[0]
CPI_LAG = load_macro_config(ROOT / "config" / "macro.yaml")["series"]["CPIAUCNS"]["lag"]
BASE = {"sharpe": 0.60, "max_drawdown": 0.20, "cagr": 0.06}


def _data(end: str = "2024-06-28"):
    open_, close = synthetic_prices(["GLD", "SHY", "SPY", "TLT"], "1999-01-01", end)
    obs = pd.date_range("1990-01-01", "2024-04-01", freq="MS")
    cpi = lag_to_availability(
        pd.Series(100 * 1.02 ** (np.arange(len(obs)) / 12), index=obs), CPI_LAG
    )
    return open_, close, cpi


def _passed(overlay: dict, null=None) -> bool:
    return all(c["passed"] for c in evaluate_pass(overlay, BASE, CFG, null))


def test_pass_rule_boundaries_are_inclusive_except_the_null():
    edge = {"sharpe": 0.65, "max_drawdown": 0.20, "cagr": 0.05}
    assert _passed(edge)
    assert not _passed({**edge, "sharpe": 0.6499})
    assert not _passed({**edge, "max_drawdown": 0.2001})
    assert not _passed({**edge, "cagr": 0.0499})
    gain = edge["sharpe"] - BASE["sharpe"]
    assert not _passed(edge, np.full(100, gain))  # must EXCEED the 95th percentile
    assert _passed(edge, np.full(100, gain - 1e-6))


def test_window_result_has_no_null_check():
    idx = pd.bdate_range("2023-01-02", periods=300)
    rng = np.random.default_rng(0)
    window = pd.DataFrame(
        {"overlay": rng.normal(0, 0.01, 300), "G": rng.normal(0, 0.01, 300)}, index=idx
    )
    out = window_result(window, CFG)
    assert len(out["checks"]) == 3
    assert out["passed"] == all(c["passed"] for c in out["checks"])
    assert out["window"] == ["2023-01-02", str(idx[-1].date())]


def test_research_never_builds_on_data_after_the_research_end(monkeypatch):
    seen: list[pd.Timestamp] = []
    real = overlay_eval.run_backtest

    def spy(open_, close, weights, cost_bps=5.0):
        seen.append(max(close.index.max(), weights.index.max()))
        return real(open_, close, weights, cost_bps=cost_bps)

    monkeypatch.setattr(overlay_eval, "run_backtest", spy)
    monkeypatch.setattr(overlay_null, "run_backtest", spy)
    out = research_result(*_data(), dataclasses.replace(CFG, null_draws=3), CRITERIA)
    assert max(seen) <= pd.Timestamp("2018-12-31")
    assert out["window"][0] >= "2005-01-01"
    assert out["window"][1] <= "2018-12-31"
    assert out["null"]["draws"] == 3
    assert len(out["checks"]) == 4
    assert set(out["signal_first_on"]) == {
        "trend_SPY",
        "trend_TLT",
        "trend_GLD",
        "vol",
        "inflation",
    }


def test_null_sharpe_uses_the_same_days_as_the_overlay_vs_g_comparison(monkeypatch):
    seen: dict[str, list[pd.DatetimeIndex]] = {"eval": [], "null": []}
    real = overlay_eval.compute_metrics

    def spy(tag):
        def inner(returns):
            seen[tag].append(pd.DatetimeIndex(returns.index))
            return real(returns)

        return inner

    monkeypatch.setattr(overlay_eval, "compute_metrics", spy("eval"))
    monkeypatch.setattr(overlay_null, "compute_metrics", spy("null"))
    research_result(*_data(), dataclasses.replace(CFG, null_draws=3), CRITERIA)
    overlay_days, g_days = seen["eval"]
    assert overlay_days.equals(g_days)
    assert len(seen["null"]) == 3
    assert all(days.equals(overlay_days) for days in seen["null"])


def test_validation_is_cut_at_the_validation_end():
    out = validation_result(*_data(), CFG, CRITERIA)
    assert out["window"][0] >= "2019-01-01"
    assert out["window"][1] <= "2022-12-31"
    assert len(out["checks"]) == 3


HEADER = {"overlay_sha256": "o" * 64, "candidates_sha256": "c" * 64, "criteria_hash": "abc"}
METRICS = {"sharpe": 0.7, "cagr": 0.06, "max_drawdown": 0.2, "volatility": 0.08}
RESULT = {
    "window": ["2019-01-02", "2022-12-30"],
    "overlay": METRICS,
    "G": METRICS,
    "sharpe_gain": 0.0,
    "checks": [{"rule": "Sharpe vs G", "value": 0.7, "threshold": ">= 0.750", "passed": False}],
    "passed": False,
}


def _event(eid: int, result: dict) -> dict:
    return {"event_id": eid, "created_at": "2026-10-08T00:00:00+00:00", "result": result}


def test_report_has_hashes_and_research_null():
    research = {
        **RESULT,
        "null": {
            "draws": 1000,
            "seed": 20261007,
            "percentile": 95.0,
            "threshold": 0.1,
            "mean": 0.0,
        },
        "signal_first_on": {"vol": "2004-04-30"},
    }
    md = render_markdown({"research": _event(1, research)}, HEADER)
    assert "o" * 64 in md
    assert "event 1" in md
    assert "1000 spell-shuffle draws" in md
    assert "vol 2004-04-30" in md
    assert "VALIDATION-SEEN" not in md


def test_report_stamps_validation_seen():
    md = render_markdown({"research": _event(1, RESULT), "validate": _event(2, RESULT)}, HEADER)
    assert "VALIDATION-SEEN" in md


def test_report_shows_a_recorded_error():
    md = render_markdown({"research": _event(1, {"error": "boom"})}, HEADER)
    assert "ERROR, recorded as a failure: boom" in md
