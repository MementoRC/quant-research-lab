"""`run --designated` (spec amendment 2026-10-22): the owner-designated,
unvalidated subject. Synthetic data only; the download is monkeypatched."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qrl.data import synthetic_prices
from qrl.international import load_international_config
from qrl.ledger import Ledger

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import international as script  # noqa: E402

REAL_CONFIG = ROOT / "config" / "international.yaml"
PARAMS = {"risk_on": "QQQ", "risk_off": "GLD", "lookback": 200}
FUND_STARTS = {"SHY": "2002-07-30", "IEF": "2002-07-30", "TLT": "2002-07-30", "GLD": "2004-11-18"}
NOTE = "subject not validated (owner-designated; failed fixed standalone attempt, test {id})"


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


def _no_download(*args, **kwargs):
    raise AssertionError("a refused run must not download")


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


def _seed(ledger_path, passed=False, params=None, family="core_trend") -> int:
    with Ledger(ledger_path) as ledger:
        run_id = ledger.start_run("crit", "A", "designated fixture", git_commit="x")
        return ledger.record_test(run_id, "crit", family, params or PARAMS, "u", {}, passed)


def _config(tmp_path, test_id: int, transform=None) -> str:
    """A copy of the real config whose designated_core names `test_id`;
    `transform` may rewrite the text further."""
    text = REAL_CONFIG.read_text(encoding="utf-8").replace(
        "failed_attempt_test_id: 1496", f"failed_attempt_test_id: {test_id}"
    )
    if transform is not None:
        text = transform(text)
    path = tmp_path / "international.yaml"
    path.write_text(text, encoding="utf-8")
    return str(path)


def _designated(opts, config, extra=("--designated",)):
    return script.main(
        [
            "run",
            "--set",
            "main",
            "--reason",
            "owner go-ahead (test)",
            "--confirm",
            "--config",
            config,
            *opts,
            *extra,
        ]
    )


def _events(opts):
    with Ledger(opts[1]) as ledger:
        return ledger.list_international_events()


def test_the_real_config_carries_the_designated_core():
    cfg, _ = load_international_config(REAL_CONFIG)
    assert cfg.designated_core is not None
    assert cfg.designated_core.family == "core_trend"
    assert cfg.designated_core.params == PARAMS
    assert cfg.designated_core.failed_attempt_test_id == 1496


def test_designated_run_completes_and_is_labelled(opts, tmp_path, capsys):
    test_id = _seed(opts[1])
    config = _config(tmp_path, test_id)
    assert _designated(opts, config) == 0
    note = NOTE.format(id=test_id)
    (event,) = _events(opts)
    assert event["status"] == "completed"
    assert note in event["rule_id"]
    assert event["result"]["subject_status"] == "designated_unvalidated"
    assert event["result"]["subject_note"] == note
    report = (Path(opts[5]) / "international_main.md").read_text(encoding="utf-8")
    assert note in report
    assert note in capsys.readouterr().out
    with Ledger(opts[1]) as ledger:
        pin = ledger.config_pin("international")
    assert pin is not None  # the usual config pin still happens


def test_a_test_id_run_carries_no_designated_label(opts, tmp_path):
    with Ledger(opts[1]) as ledger:
        run_id = ledger.start_run("crit", "A", "validated fixture", git_commit="x")
        test_id = ledger.record_test(
            run_id,
            "crit",
            "core_trend",
            {"risk_on": "SPY", "risk_off": "IEF", "lookback": 200},
            "u",
            {},
            True,
        )
        ledger.record_validation(test_id, {"sharpe": 1.0})
        ledger.set_validation_verdict(test_id, True)
    args = ["run", "--set", "main", "--test-id", str(test_id), "--reason", "go", "--confirm"]
    assert script.main([*args, *opts]) == 0
    (event,) = _events(opts)
    assert event["rule_id"] == f"ledger test {test_id}"
    assert "subject_status" not in event["result"]
    report = (Path(opts[5]) / "international_main.md").read_text(encoding="utf-8")
    assert "not validated" not in report


def test_designated_refused_when_the_block_is_absent(opts, tmp_path, monkeypatch):
    test_id = _seed(opts[1])

    def drop(text: str) -> str:
        start = text.index("designated_core:")
        end = text.index("proxies:")
        return text[:start] + text[end:]

    config = _config(tmp_path, test_id, drop)
    monkeypatch.setattr(script, "load_raw", _no_download)
    assert _designated(opts, config) == 1
    assert _events(opts) == []
    with Ledger(opts[1]) as ledger:
        assert ledger.config_pin("international") is None


def test_designated_refused_when_the_test_id_is_missing(opts, tmp_path, monkeypatch):
    monkeypatch.setattr(script, "load_raw", _no_download)
    assert _designated(opts, _config(tmp_path, 999)) == 1
    assert _events(opts) == []


@pytest.mark.parametrize(
    ("family", "params"),
    [
        ("core_trend", {"risk_on": "QQQ", "risk_off": "GLD", "lookback": 100}),
        ("core_trend", {"risk_on": "QQQ", "risk_off": "IEF", "lookback": 200}),
        ("core_mix", {"risk_on": {"QQQ": 1.0}, "risk_off": "GLD"}),
    ],
)
def test_designated_refused_when_family_or_params_differ(
    opts, tmp_path, monkeypatch, family, params
):
    test_id = _seed(opts[1], params=params, family=family)
    monkeypatch.setattr(script, "load_raw", _no_download)
    assert _designated(opts, _config(tmp_path, test_id)) == 1
    assert _events(opts) == []


def test_designated_refused_when_the_referenced_test_passed(opts, tmp_path, monkeypatch):
    test_id = _seed(opts[1], passed=True)
    monkeypatch.setattr(script, "load_raw", _no_download)
    assert _designated(opts, _config(tmp_path, test_id)) == 1
    assert _events(opts) == []


def test_designated_refused_when_the_config_differs_from_the_pin(opts, tmp_path, monkeypatch):
    test_id = _seed(opts[1])
    with Ledger(opts[1]) as ledger:
        ledger.pin_config("international", "0" * 64, source="test")
    monkeypatch.setattr(script, "load_raw", _no_download)
    assert _designated(opts, _config(tmp_path, test_id)) == 1
    assert _events(opts) == []


def test_test_id_and_designated_together_or_neither_are_refused(opts, tmp_path, monkeypatch):
    test_id = _seed(opts[1])
    config = _config(tmp_path, test_id)
    monkeypatch.setattr(script, "load_raw", _no_download)
    with pytest.raises(SystemExit):  # argparse: mutually exclusive
        _designated(opts, config, extra=("--designated", "--test-id", str(test_id)))
    with pytest.raises(SystemExit):  # argparse: one is required
        _designated(opts, config, extra=())
    assert _events(opts) == []


@pytest.mark.parametrize(
    ("old", "new", "match"),
    [
        ("family: core_trend", "family: buy_and_hold", "not covered"),
        ("params: {risk_on: QQQ, risk_off: GLD, lookback: 200}", "params: [QQQ, GLD]", "mapping"),
        ("failed_attempt_test_id: 1496", "failed_attempt_test_id: abc", "integer"),
        ("failed_attempt_test_id: 1496", "failed_attempt_test_id: 1.5", "integer"),
        ("risk_off: GLD,", "risk_off: SPY,", "equity leg"),  # two non-defensive tickers
    ],
)
def test_the_loader_rejects_a_malformed_block(tmp_path, old, new, match):
    text = REAL_CONFIG.read_text(encoding="utf-8")
    assert old in text
    path = tmp_path / "international.yaml"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(ValueError, match=match):
        load_international_config(path)
