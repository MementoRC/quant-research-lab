"""Tests for docs/methodology/site-safety.md: the survivorship label read from
the research record, and the holdout cut-off for dashboard entries without
holdout clearance.

All data is synthetic (offline); ledgers are temp files, never research/.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

from qrl.combined import build_core_weights
from qrl.criteria import load_criteria
from qrl.data import synthetic_prices
from qrl.engine import run_backtest
from qrl.ledger import Ledger
from qrl.metrics import compute_metrics

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "build_site.py"
INDEX_PATH = ROOT / "site" / "index.html"
VALIDATION_END = "2022-12-31"

_SEARCH_CORE_PORTFOLIO = """
core:
  origin: search
  fn: core_trend
  params: {risk_on: QQQ, risk_off: GLD, lookback: 200}
sleeve:
  strategies: []
provenance:
  ledger_run_id: null
  validation_config_hash: null
  selection_date: null
  holdout_unsealed: UNSEALED
"""


def _load_build_site():
    spec = importlib.util.spec_from_file_location("build_site_safety_under_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _fake_root(tmp_path: Path, portfolio_yaml: str) -> Path:
    fake_root = tmp_path / "fake_root"
    (fake_root / "config").mkdir(parents=True)
    for name in ("criteria.yaml", "profile.yaml", "strategies.yaml"):
        shutil.copy(ROOT / "config" / name, fake_root / "config" / name)
    (fake_root / "config" / "portfolio.yaml").write_text(portfolio_yaml)
    return fake_root


def _build(monkeypatch, tmp_path: Path, portfolio_yaml: str, *, holdout_events: int | None):
    """Run build_site.main() against a fake root. `holdout_events=None` means
    no ledger file; otherwise a temp ledger with that many holdout rows."""
    fake_root = _fake_root(tmp_path, portfolio_yaml)
    if holdout_events is not None:
        with Ledger(fake_root / "research" / "ledger.sqlite") as ledger:
            for _ in range(holdout_events):
                ledger.record_holdout_event("test", "synthetic test event", git_commit="abc")
    module = _load_build_site()
    monkeypatch.setattr(module, "ROOT", fake_root)
    out_path = tmp_path / "site_data" / "results.json"
    monkeypatch.setattr(sys, "argv", ["build_site.py", "--synthetic", "--out", str(out_path)])
    module.main()
    return json.loads(out_path.read_text())


def _entry(payload, entry_id):
    return next(s for s in payload["strategies"] if s["id"] == entry_id)


def _round_metrics(metrics: dict) -> dict:
    return {k: (round(v, 6) if isinstance(v, float) else v) for k, v in metrics.items()}


def test_search_origin_core_without_clearance_is_cut_at_validation_end(tmp_path, monkeypatch):
    payload = _build(
        monkeypatch,
        tmp_path,
        _SEARCH_CORE_PORTFOLIO.replace("UNSEALED", "false"),
        holdout_events=None,
    )

    core = _entry(payload, "portfolio_core")
    full = core["metrics"]["full"]
    assert full["through"] == VALIDATION_END
    assert full["end"] <= VALIDATION_END
    assert "holdout" not in core["metrics"]

    criteria, _ = load_criteria(ROOT / "config" / "criteria.yaml")
    # build_site draws all its tickers together, so draw the same sorted set.
    open_, close = synthetic_prices(["GLD", "QQQ", "SPY"])
    _, weights = build_core_weights(
        {"origin": "search", "fn": "core_trend", "params": _core_params()}, close
    )
    res = run_backtest(
        open_[["QQQ", "GLD"]],
        close[["QQQ", "GLD"]],
        weights,
        cost_bps=criteria["costs"]["bps_per_unit_turnover"],
    )
    sl = slice(pd.Timestamp(payload["window"]["start"]), pd.Timestamp(VALIDATION_END))
    expected = compute_metrics(res.returns.loc[sl], res.turnover.loc[sl], res.executed.loc[sl])
    got = {k: v for k, v in full.items() if k != "through"}
    assert got == _round_metrics(expected)

    dates = payload["series"]["dates"]
    for key in ("equity", "drawdown"):
        values = payload["series"][key]["portfolio_core"]
        after = [v for d, v in zip(dates, values, strict=True) if d > VALIDATION_END]
        assert after, "synthetic window must extend past the validation end"
        assert all(v is None for v in after)
        assert values[dates.index("2022-12-30")] is not None


def _core_params() -> dict:
    return {"risk_on": "QQQ", "risk_off": "GLD", "lookback": 200}


def test_search_origin_core_with_ledger_clearance_shows_the_full_window(tmp_path, monkeypatch):
    payload = _build(
        monkeypatch,
        tmp_path,
        _SEARCH_CORE_PORTFOLIO.replace("UNSEALED", "true"),
        holdout_events=1,
    )

    core = _entry(payload, "portfolio_core")
    assert "through" not in core["metrics"]["full"]
    assert core["metrics"]["full"]["end"] == payload["window"]["end"]
    assert "holdout" in core["metrics"]
    dates = payload["series"]["dates"]
    for key in ("equity", "drawdown"):
        values = payload["series"][key]["portfolio_core"]
        assert all(v is not None for d, v in zip(dates, values, strict=True) if d > VALIDATION_END)


def test_holdout_unsealed_with_empty_holdout_events_raises(tmp_path, monkeypatch):
    with pytest.raises(RuntimeError, match="holdout_events"):
        _build(
            monkeypatch,
            tmp_path,
            _SEARCH_CORE_PORTFOLIO.replace("UNSEALED", "true"),
            holdout_events=0,
        )


def test_baselines_and_benchmarks_keep_the_full_window(tmp_path, monkeypatch):
    payload = _build(
        monkeypatch,
        tmp_path,
        _SEARCH_CORE_PORTFOLIO.replace("UNSEALED", "false"),
        holdout_events=None,
    )

    fixed = [s for s in payload["strategies"] if s["kind"] in ("strategy", "benchmark")]
    assert fixed
    dates = payload["series"]["dates"]
    for s in fixed:
        assert "through" not in s["metrics"]["full"]
        assert s["metrics"]["full"]["end"] == payload["window"]["end"]
        assert "holdout" in s["metrics"]
        assert "survivorship_biased" not in s
        for key in ("equity", "drawdown"):
            values = payload["series"][key][s["id"]]
            assert all(
                v is not None for d, v in zip(dates, values, strict=True) if d > VALIDATION_END
            )


def test_funnel_without_a_ledger_fails_closed(tmp_path):
    module = _load_build_site()
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "research.json").write_text(
        json.dumps({"funnel": {"tested": 10}, "total_attempts": 10})
    )

    funnel = module._research_funnel(tmp_path / "data", tmp_path)

    assert funnel["survivorship"] == {"biased": True, "universes": []}


def test_funnel_without_research_json_has_no_survivorship_key(tmp_path):
    module = _load_build_site()

    funnel = module._research_funnel(tmp_path, tmp_path)

    assert funnel["available"] is False
    assert "survivorship" not in funnel


def test_ledger_universes_reads_the_ledger_read_only(tmp_path):
    module = _load_build_site()
    path = tmp_path / "ledger.sqlite"
    assert module._ledger_universes(path) is None
    Ledger(path).close()

    assert module._ledger_universes(path) == []


def test_tested_universe_configured_biased_gives_biased_funnel():
    module = _load_build_site()

    result = module._research_survivorship([{"name": "us_large_cap_stocks", "tests": 7}], ROOT)

    assert result["biased"] is True
    assert result["universes"] == [
        {"name": "us_large_cap_stocks", "tests": 7, "survivorship_biased": True}
    ]


def test_unknown_universe_fails_closed():
    module = _load_build_site()

    result = module._research_survivorship([{"name": "no_such_universe", "tests": 3}], ROOT)

    assert result["biased"] is True
    assert result["universes"][0]["survivorship_biased"] is True


def test_unbiased_universe_config_alone_gives_unbiased_funnel(tmp_path):
    module = _load_build_site()
    (tmp_path / "config").mkdir()
    universe = yaml.safe_load((ROOT / "config" / "universe.yaml").read_text())
    universe.update(name="toy_universe", survivorship_biased=False)
    (tmp_path / "config" / "universe.yaml").write_text(yaml.safe_dump(universe))

    result = module._research_survivorship([{"name": "toy_universe", "tests": 4}], tmp_path)

    assert result == {
        "biased": False,
        "universes": [{"name": "toy_universe", "tests": 4, "survivorship_biased": False}],
    }


def test_search_origin_entry_carries_survivorship_biased_true(tmp_path, monkeypatch):
    payload = _build(
        monkeypatch,
        tmp_path,
        _SEARCH_CORE_PORTFOLIO.replace("UNSEALED", "false"),
        holdout_events=None,
    )

    assert _entry(payload, "portfolio_core")["survivorship_biased"] is True
    assert _entry(payload, "portfolio_combined")["survivorship_biased"] is True


def test_front_end_notice_covers_the_funnel_flag_and_cutoff_label():
    html = INDEX_PATH.read_text()

    assert "research_funnel.survivorship" in html
    assert "data.survivorship_biased" in html
    assert "survivorship_biased" in html.split("function renderTable")[1]
    assert "Full history (to" in html
