"""Tests for milestone 2.7's scripts/build_site.py additions (PLAN.md
section 2.7): the new results.json keys (portfolio, research funnel,
survivorship flag), the empty-sleeve degradation, and the holdout-unsealing
gate by entry kind (AGENTS.md, PLAN.md section 3).

Runs the real `build_site.main()` on synthetic (offline) data, writing to
`tmp_path` via the existing `--out` flag -- never into `site/`.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "build_site.py"


def _load_build_site():
    spec = importlib.util.spec_from_file_location("build_site_under_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _run(monkeypatch, out_path: Path, module=None):
    module = module or _load_build_site()
    monkeypatch.setattr(sys, "argv", ["build_site.py", "--synthetic", "--out", str(out_path)])
    module.main()
    return json.loads(out_path.read_text())


def _seed_fake_root(tmp_path: Path, portfolio_yaml: str) -> Path:
    """A minimal copy of config/ with a caller-supplied portfolio.yaml, so a
    test can add a sleeve member without touching the committed, honest
    config/portfolio.yaml."""
    fake_root = tmp_path / "fake_root"
    (fake_root / "config").mkdir(parents=True)
    for name in ("criteria.yaml", "profile.yaml", "strategies.yaml"):
        shutil.copy(ROOT / "config" / name, fake_root / "config" / name)
    (fake_root / "config" / "portfolio.yaml").write_text(portfolio_yaml)
    return fake_root


# ---------------------------------------------------------------------------
# New results.json keys, using the committed config/portfolio.yaml (core
# baseline, empty sleeve -- today's honest state).
# ---------------------------------------------------------------------------


def test_results_json_has_the_new_portfolio_and_funnel_keys(tmp_path, monkeypatch):
    out_path = tmp_path / "results.json"

    payload = _run(monkeypatch, out_path)

    assert "portfolio" in payload
    assert set(payload["portfolio"]) >= {
        "capital_split",
        "core",
        "sleeve",
        "provenance",
        "sleeve_holdings",
    }
    assert "research_funnel" in payload
    assert set(payload["research_funnel"]) == {"available", "total_attempts", "stages"}
    assert "survivorship_biased" in payload
    ids = {s["id"] for s in payload["strategies"]}
    assert {"portfolio_core", "portfolio_combined"} <= ids


def test_core_alone_equals_the_unscaled_core_strategy_at_full_capital(tmp_path, monkeypatch):
    # "Core alone" must be what running with NO sleeve at all looks like --
    # the same backtest as config/strategies.yaml's baseline (same fn/params
    # here), never the core's scaled 80% split share.
    out_path = tmp_path / "results.json"

    payload = _run(monkeypatch, out_path)

    baseline = next(s for s in payload["strategies"] if s["id"] == "core_trend_qqq_gld")
    core_alone = next(s for s in payload["strategies"] if s["id"] == "portfolio_core")
    assert core_alone["metrics"]["full"] == baseline["metrics"]["full"]


def test_empty_sleeve_combined_line_holds_idle_cash_and_trails_core_alone(tmp_path, monkeypatch):
    out_path = tmp_path / "results.json"

    payload = _run(monkeypatch, out_path)

    assert payload["portfolio"]["sleeve"]["count"] == 0
    assert payload["portfolio"]["sleeve_holdings"] == []
    assert payload["portfolio"]["idle_cash_pct"] == pytest.approx(0.20)

    core_alone = next(s for s in payload["strategies"] if s["id"] == "portfolio_core")
    combined = next(s for s in payload["strategies"] if s["id"] == "portfolio_combined")
    # 20% of the combined line sits in cash (uninvested), so it must trail
    # core alone, not match it.
    assert combined["metrics"]["full"]["cagr"] < core_alone["metrics"]["full"]["cagr"]
    assert combined["name"] != core_alone["name"]


def test_research_funnel_absent_by_default(tmp_path, monkeypatch):
    out_path = tmp_path / "results.json"

    payload = _run(monkeypatch, out_path)

    assert payload["research_funnel"]["available"] is False
    assert payload["research_funnel"]["total_attempts"] is None


def test_research_funnel_is_read_when_present(tmp_path, monkeypatch):
    out_path = tmp_path / "results.json"
    (tmp_path / "research.json").write_text(
        json.dumps(
            {
                "funnel": {"tested": 500, "passed_research": 40, "validated": 12},
                "total_attempts": 500,
            }
        )
    )

    payload = _run(monkeypatch, out_path)

    funnel = payload["research_funnel"]
    assert funnel["available"] is True
    assert funnel["total_attempts"] == 500
    counts = {s["key"]: s["count"] for s in funnel["stages"]}
    assert counts["tested"] == 500
    assert counts["passed_research"] == 40
    # "validated" (export_ledger.py's key) is accepted as passed_validation.
    assert counts["passed_validation"] == 12
    assert counts["passed_robustness"] is None
    assert counts["selected"] is None


def test_survivorship_flag_propagates_to_top_level(tmp_path, monkeypatch):
    out_path = tmp_path / "results.json"
    (tmp_path / "universe_coverage.json").write_text(
        json.dumps(
            {
                "name": "us_large_cap_stocks",
                "as_of": "2026-01-01",
                "survivorship_biased": True,
                "requested": 100,
                "loaded": 95,
                "failed": 5,
                "late_starters": 3,
                "ended_early": 2,
            }
        )
    )

    payload = _run(monkeypatch, out_path)

    assert payload["survivorship_biased"] is True
    assert payload["universe"]["survivorship_biased"] is True


def test_survivorship_flag_is_none_without_a_coverage_file(tmp_path, monkeypatch):
    out_path = tmp_path / "results.json"

    payload = _run(monkeypatch, out_path)

    assert payload["survivorship_biased"] is None
    assert "universe" not in payload


# ---------------------------------------------------------------------------
# Holdout gating by entry kind: a baseline keeps its holdout figures; a
# portfolio whose sleeve has a member (search/selection origin) does not,
# absent a recorded holdout_unsealed provenance flag.
# ---------------------------------------------------------------------------

_PORTFOLIO_WITH_SLEEVE = """
core:
  origin: baseline
  fn: core_trend
  params: {risk_on: QQQ, risk_off: GLD, lookback: 200}
sleeve:
  strategies:
    - fn: trend_pullback
      params:
        tickers: [QQQ, GLD]
        trend_lookback: 100
        short_ma: 10
        pullback_days: 3
        pullback_pct: 0.01
        exit_days: 5
        max_positions: 2
provenance:
  ledger_run_id: null
  validation_config_hash: null
  selection_date: null
  holdout_unsealed: false
"""


def test_searched_portfolio_has_no_holdout_figures_while_baseline_does(tmp_path, monkeypatch):
    fake_root = _seed_fake_root(tmp_path, _PORTFOLIO_WITH_SLEEVE)
    out_path = tmp_path / "site_data" / "results.json"

    module = _load_build_site()
    monkeypatch.setattr(module, "ROOT", fake_root)
    payload = _run(monkeypatch, out_path, module=module)

    baseline = next(s for s in payload["strategies"] if s["id"] == "core_trend_qqq_gld")
    combined = next(s for s in payload["strategies"] if s["id"] == "portfolio_combined")

    assert "holdout" in baseline["metrics"]
    assert "holdout" not in combined["metrics"]
    assert "research" in combined["metrics"]
    assert "validation" in combined["metrics"]


def test_unsealed_provenance_allows_holdout_for_a_searched_portfolio(tmp_path, monkeypatch):
    unsealed_yaml = _PORTFOLIO_WITH_SLEEVE.replace(
        "holdout_unsealed: false", "holdout_unsealed: true"
    )
    fake_root = _seed_fake_root(tmp_path, unsealed_yaml)
    out_path = tmp_path / "site_data" / "results.json"

    module = _load_build_site()
    monkeypatch.setattr(module, "ROOT", fake_root)
    payload = _run(monkeypatch, out_path, module=module)

    combined = next(s for s in payload["strategies"] if s["id"] == "portfolio_combined")
    assert "holdout" in combined["metrics"]


def test_no_unsealed_holdout_call_for_a_gated_entry_in_build_site_logic():
    # Belt-and-suspenders source check, mirroring tests/test_walkforward.py's
    # equivalent: build_site.py must gate its one `unseal_holdout=True` call
    # site by the per-entry `allow_holdout` flag, not call it unconditionally.
    src = SCRIPT_PATH.read_text()
    assert 'r["allow_holdout"]' in src
    assert src.count("unseal_holdout=True") == 1


def test_load_build_site_module_is_importable():
    module = _load_build_site()
    assert hasattr(module, "main")


# ---------------------------------------------------------------------------
# Sleeve families needing more than close (high/low, volume) must actually
# work, not raise -- exercised directly against `_portfolio_entries` with a
# non-empty sleeve mixing a high/low family (low_range_close) and a volume
# family (quiet_pullback), on synthetic (offline) data.
# ---------------------------------------------------------------------------

_HIGH_LOW_AND_VOLUME_PORTFOLIO = {
    "core": {
        "origin": "baseline",
        "fn": "core_trend",
        "params": {"risk_on": "QQQ", "risk_off": "GLD", "lookback": 200},
    },
    "sleeve": {
        "strategies": [
            {
                "fn": "low_range_close",
                "params": {
                    "tickers": ["QQQ", "GLD"],
                    "trend_lookback": 100,
                    "range_pct": 0.25,
                    "exit_days": 5,
                    "max_positions": 2,
                },
            },
            {
                "fn": "quiet_pullback",
                "params": {
                    "tickers": ["QQQ", "GLD"],
                    "trend_lookback": 100,
                    "short_ma": 10,
                    "vol_lookback": 20,
                    "quiet_ratio": 0.8,
                    "quiet_by": "volume",
                    "exit_days": 5,
                    "max_positions": 2,
                },
            },
        ]
    },
    "provenance": {
        "ledger_run_id": None,
        "validation_config_hash": None,
        "selection_date": None,
        "holdout_unsealed": False,
    },
}


def test_sleeve_high_low_and_volume_families_produce_and_combine_weights():
    from qrl.data import synthetic_prices

    module = _load_build_site()
    tickers = ["QQQ", "GLD"]
    open_, close = synthetic_prices(tickers)
    capital_split = {"core": 0.80, "sleeve": 0.20}

    descriptors, results_extra, holdings, idle_cash_pct = module._portfolio_entries(
        _HIGH_LOW_AND_VOLUME_PORTFOLIO,
        capital_split,
        open_,
        close,
        cost_bps=5.0,
        synthetic=True,
        refresh=False,
    )

    assert idle_cash_pct == 0.0
    assert isinstance(holdings, list)
    combined_target = results_extra["portfolio_combined"].target.fillna(0.0)
    assert (combined_target >= -1e-9).all().all()
    assert (combined_target.sum(axis=1) <= 1 + 1e-6).all()
    assert {d["id"] for d in descriptors} == {"portfolio_core", "portfolio_combined"}
