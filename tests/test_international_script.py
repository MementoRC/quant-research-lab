"""scripts/international.py end to end on synthetic data. The download
function is monkeypatched; nothing here touches the network or a real
market set."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qrl.data import synthetic_prices
from qrl.ledger import Ledger

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
