"""scripts/international.py end to end on synthetic data. The download
function is monkeypatched; nothing here touches the network or a real
market set."""

from __future__ import annotations

import hashlib
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qrl.data import synthetic_prices
from qrl.ledger import Ledger
from qrl.strategies import REGISTRY

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import international as script  # noqa: E402

FUND_STARTS = {"SHY": "2002-07-30", "IEF": "2002-07-30", "TLT": "2002-07-30", "GLD": "2004-11-18"}


def fake_load_raw(cfg, set_name, refresh, cache_dir):
    markets = cfg.market_set(set_name).markets
    open_, close = synthetic_prices([*markets, *cfg.funds], start="1996-01-01")
    for fund, first in FUND_STARTS.items():
        early = close.index < pd.Timestamp(first)
        open_.loc[early, fund] = np.nan
        close.loc[early, fund] = np.nan
    _, gold = synthetic_prices([cfg.gold_ticker], start="2000-08-30")
    yields = {fred: pd.Series(4.0, index=close.index) for fred in cfg.fred_ids}
    return open_, close, gold[cfg.gold_ticker], yields


@pytest.fixture
def opts(tmp_path, monkeypatch):
    monkeypatch.setattr(script, "load_raw", fake_load_raw)
    return [
        "--ledger",
        str(tmp_path / "ledger.sqlite"),
        "--cache-dir",
        str(tmp_path / "cache"),
        "--out-dir",
        str(tmp_path / "research"),
    ]


def test_check_data_reports_coverage_but_no_returns_or_metrics(opts, capsys):
    assert script.main(["check-data", "--set", "main", *opts]) == 0
    out = capsys.readouterr().out.lower()
    for needed in ("ewj", "gc=f", "correlation", "dgs10", "dtb3"):
        assert needed in out
    for word in ("sharpe", "cagr", "drawdown", "return", "volatility", "verdict", "pass"):
        assert word not in out
    with Ledger(opts[1]) as ledger:
        assert ledger.list_international_events() == []
        assert ledger.config_pin("international") is None  # check-data never pins


def test_check_data_refuses_an_unknown_set(opts):
    assert script.main(["check-data", "--set", "nicer_one", *opts]) == 1


CONFIG = ROOT / "config" / "international.yaml"


def _seed(ledger_path, params=None, validated=True, family="core_trend", verdict=True) -> int:
    """`validated=False`: no validation event. Otherwise an event with the given
    verdict: True (passed = 1), False (passed = 0) or None (a legacy NULL row)."""
    with Ledger(ledger_path) as ledger:
        run_id = ledger.start_run("crit", "A", "international fixture", git_commit="x")
        test_id = ledger.record_test(
            run_id,
            "crit",
            family,
            params or {"risk_on": "SPY", "risk_off": "IEF", "lookback": 200},
            "u",
            {},
            True,
        )
        if validated:
            ledger.record_validation(test_id, {"sharpe": 1.0})
            if verdict is not None:
                ledger.set_validation_verdict(test_id, verdict)
    return test_id


def _run(opts, test_id, set_name="main", extra=()):
    return script.main(
        [
            "run",
            "--set",
            set_name,
            "--test-id",
            str(test_id),
            "--reason",
            "owner go-ahead (test)",
            "--confirm",
            *opts,
            *extra,
        ]
    )


def _events(opts):
    with Ledger(opts[1]) as ledger:
        return ledger.list_international_events()


def _no_download(*args, **kwargs):
    raise AssertionError("a refused or recomputed run must not download")


def test_run_needs_confirm_and_a_reason(opts, monkeypatch):
    test_id = _seed(opts[1])
    monkeypatch.setattr(script, "load_raw", _no_download)
    base = ["run", "--set", "main", "--test-id", str(test_id), *opts]
    assert script.main([*base, "--reason", "go"]) == 2  # no --confirm
    assert script.main([*base, "--confirm"]) == 2  # no --reason
    assert script.main([*base, "--confirm", "--reason", "   "]) == 2  # blank reason
    assert _events(opts) == []
    with Ledger(opts[1]) as ledger:
        assert ledger.config_pin("international") is None  # a refused run pins nothing


def test_run_refuses_an_unknown_test_id(opts, monkeypatch):
    monkeypatch.setattr(script, "load_raw", _no_download)
    assert _run(opts, 999) == 1
    assert _events(opts) == []


def test_run_refuses_a_rule_without_a_validation_event(opts, monkeypatch):
    monkeypatch.setattr(script, "load_raw", _no_download)
    assert _run(opts, _seed(opts[1], validated=False)) == 1
    assert _events(opts) == []


def test_run_refuses_a_rule_that_failed_validation(opts, monkeypatch):
    monkeypatch.setattr(script, "load_raw", _no_download)
    assert _run(opts, _seed(opts[1], verdict=False)) == 1  # passed = 0
    assert _events(opts) == []


def test_run_refuses_a_legacy_validation_row_with_no_verdict(opts, monkeypatch):
    monkeypatch.setattr(script, "load_raw", _no_download)
    assert _run(opts, _seed(opts[1], verdict=None)) == 1  # passed IS NULL
    assert _events(opts) == []


@pytest.mark.parametrize(
    ("family", "params"),
    [
        ("buy_and_hold", {"ticker": "SPY"}),  # strategy not covered
        ("core_mix", {"risk_on": {"SPY": 0.5, "QQQ": 0.5}}),  # two non-defensive tickers
        ("core_trend", {"risk_on": "GLD", "risk_off": "IEF", "lookback": 200}),  # zero
    ],
)
def test_run_refuses_an_uncovered_rule(opts, monkeypatch, family, params):
    monkeypatch.setattr(script, "load_raw", _no_download)
    assert _run(opts, _seed(opts[1], params=params, family=family)) == 1
    assert _events(opts) == []
    with Ledger(opts[1]) as ledger:
        assert ledger.config_pin("international") is None


def test_the_first_confirmed_run_pins_the_config(opts):
    with Ledger(opts[1]) as ledger:
        assert ledger.config_pin("international") is None
    assert _run(opts, _seed(opts[1])) == 0
    with Ledger(opts[1]) as ledger:
        pin = ledger.config_pin("international")
    assert pin is not None
    assert pin["sha256"] == hashlib.sha256(CONFIG.read_bytes()).hexdigest()


def test_run_refuses_a_config_that_differs_from_the_pin(opts, monkeypatch):
    with Ledger(opts[1]) as ledger:
        ledger.pin_config("international", "0" * 64, source="test")
    monkeypatch.setattr(script, "load_raw", _no_download)
    assert _run(opts, _seed(opts[1])) == 1  # the real config's hash is not the pin
    assert _events(opts) == []
    with Ledger(opts[1]) as ledger:
        pin = ledger.config_pin("international")
    assert pin is not None
    assert pin["sha256"] == "0" * 64  # never overwritten


def test_run_writes_the_report_and_completes_the_event(opts):
    assert _run(opts, _seed(opts[1])) == 0
    (event,) = _events(opts)
    assert event["status"] == "completed"
    assert event["set_name"] == "main"
    assert event["data_end"] == "2026-10-19"  # synthetic data ends on SYNTHETIC_END
    assert len(event["result"]["markets"]) == 7
    assert event["data_sha256"]
    report = Path(opts[5]) / "international_main.md"
    assert event["report_path"] == str(report)
    assert "Verdict: **" in report.read_text(encoding="utf-8")


def test_the_event_is_recorded_before_anything_is_scored(opts, monkeypatch):
    seen = []

    def spy(*args, **kwargs):
        seen.append(_events(opts))
        raise RuntimeError("stop")

    monkeypatch.setattr(script, "evaluate_market", spy)
    with pytest.raises(RuntimeError):
        _run(opts, _seed(opts[1]))
    assert [e["status"] for e in seen[0]] == ["started"]


def test_data_after_the_recorded_end_is_dropped_and_hashed(opts):
    assert _run(opts, _seed(opts[1])) == 0
    (event,) = _events(opts)
    snap = Path(opts[3]) / "international" / "main_frozen.parquet"
    open_, close = script.read_snapshot(snap)
    assert close.index[-1] == pd.Timestamp(event["data_end"])
    assert script.freeze(open_, close, close.index[-1])[2] == event["data_sha256"]


def test_a_used_set_and_a_skipped_set_are_refused(opts):
    test_id = _seed(opts[1])
    assert _run(opts, test_id, set_name="reserve_1") == 1  # main is unused
    assert _run(opts, test_id) == 0
    assert _run(opts, test_id) == 1  # main is used
    assert [e["set_name"] for e in _events(opts)] == ["main"]


def test_a_crash_after_the_event_allows_only_a_recompute_on_the_frozen_data(opts, monkeypatch):
    test_id = _seed(opts[1])
    real = script.evaluate_market

    def crash(*args, **kwargs):
        raise RuntimeError("crash")

    monkeypatch.setattr(script, "evaluate_market", crash)
    with pytest.raises(RuntimeError):
        _run(opts, test_id)
    assert _events(opts)[0]["status"] == "started"

    other = _seed(opts[1], params={"risk_on": "SPY", "risk_off": "TLT", "lookback": 200})
    monkeypatch.setattr(script, "evaluate_market", real)
    assert _run(opts, other) == 1  # a different rule may not take the started set

    monkeypatch.setattr(script, "load_raw", _no_download)
    assert _run(opts, test_id) == 0
    (event,) = _events(opts)
    assert event["status"] == "completed"
    assert event["report_path"]


def test_a_recompute_refuses_changed_frozen_data(opts, monkeypatch):
    test_id = _seed(opts[1])

    def crash(*args, **kwargs):
        raise RuntimeError("crash")

    monkeypatch.setattr(script, "evaluate_market", crash)
    with pytest.raises(RuntimeError):
        _run(opts, test_id)
    monkeypatch.undo()
    snap = Path(opts[3]) / "international" / "main_frozen.parquet"
    open_, close = script.read_snapshot(snap)
    close.iloc[-5:, 0] = close.iloc[-5:, 0] * 1.01
    script.write_snapshot(snap, open_, close)
    monkeypatch.setattr(script, "load_raw", _no_download)
    assert _run(opts, test_id) == 1
    assert _events(opts)[0]["status"] == "started"


def test_a_strategy_error_leaves_the_event_started(opts, monkeypatch):
    def boom(*args, **kwargs):
        raise ValueError("strategy bug")

    monkeypatch.setitem(REGISTRY, "core_trend", replace(REGISTRY["core_trend"], weights=boom))
    with pytest.raises(ValueError, match="strategy bug"):
        _run(opts, _seed(opts[1]))
    (event,) = _events(opts)
    assert event["status"] == "started"
    assert event["report_path"] is None


def test_the_script_never_unseals_the_holdout():
    source = (ROOT / "scripts" / "international.py").read_text(encoding="utf-8")
    assert "unseal_holdout" not in source


def test_a_gold_rule_is_scored_late_only_when_the_gold_check_fails(opts):
    test_id = _seed(opts[1], params={"risk_on": "SPY", "risk_off": "GLD", "lookback": 200})
    assert _run(opts, test_id) == 0
    result = _events(opts)[0]["result"]
    # synthetic GC=F and GLD are independent random walks: the check fails
    assert result["late_only"] is True
    assert all(m["late_only"] for m in result["markets"])
