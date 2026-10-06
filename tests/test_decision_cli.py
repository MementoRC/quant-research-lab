"""config/decision.yaml, the pixi task and scripts/decision.py (IO only).
Offline: prices and CPI are monkeypatched with synthetic data."""

from __future__ import annotations

import importlib.util
import tomllib
from dataclasses import replace

from decision_helpers import (
    CANDIDATES,
    END,
    GOOD,
    ROOT,
    YEARS_LINE,
    cpi,
    load,
    stress_cfg,
    write,
)

from qrl.data import synthetic_prices
from qrl.decision_config import load_decision_config
from qrl.decision_withdraw import CPI_SERIES


def _shipped():
    return load_decision_config(ROOT / "config" / "decision.yaml", CANDIDATES, stress_cfg(), END)


def test_decision_shipped_config_loads():
    cfg = _shipped()
    assert [p.id for p in cfg.portfolios] == [*"ABCDEFG", "CASH", "G-EW", "AG", "G-CASH", "A-CASH"]
    assert [s.name for s in cfg.scenarios] == [
        "treasury_dollar_crisis",
        "trade_oil_shock",
        "ai_megacap_crash",
    ]
    assert all(s.label == "judgement-based, v1" for s in cfg.scenarios)
    by_name = {s.name: s for s in cfg.scenarios}
    assert by_name["ai_megacap_crash"].returns == {
        "SPY": -0.30,
        "QQQ": -0.45,
        "RSP": -0.15,
        "SHY": 0.03,
        "IEF": 0.06,
        "TLT": 0.12,
        "GLD": 0.05,
    }
    assert by_name["treasury_dollar_crisis"].inflation == 0.08


def test_decision_shipped_config_tripwire():
    """Exact owner-approved values; fails on any accidental edit."""
    cfg = _shipped()
    funds = ["SPY", "QQQ", "RSP", "SHY", "IEF", "TLT", "GLD"]
    table = {
        "treasury_dollar_crisis": ([-0.25, -0.30, -0.22, 0.01, -0.12, -0.30, 0.25], 0.08),
        "trade_oil_shock": ([-0.20, -0.25, -0.18, 0.02, -0.06, -0.15, 0.10], 0.07),
        "ai_megacap_crash": ([-0.30, -0.45, -0.15, 0.03, 0.06, 0.12, 0.05], 0.02),
    }
    assert {s.name: s for s in cfg.scenarios}.keys() == table.keys()
    for s in cfg.scenarios:
        returns, inflation = table[s.name]
        assert s.returns == dict(zip(funds, returns, strict=True))
        assert s.inflation == inflation
    assert cfg.rates == [0.02, 0.033, 0.04, 0.05]
    assert cfg.start_years == list(range(2005, 2015))
    assert [w.name for w in cfg.windows] == ["dotcom_2000", "gfc_2008"]
    assert cfg.proxied_threshold == 0.25
    mixes = {p.id: [(c.id, c.params["risk_on"], sh) for c, sh in p.parts] for p in cfg.portfolios}
    assert mixes["CASH"] == [("CASH", {"SHY": 1.0}, 1.0)]
    assert mixes["G-EW"][0][1] == {"RSP": 0.25, "TLT": 0.25, "GLD": 0.25, "SHY": 0.25}
    assert [(c, sh) for c, _, sh in mixes["AG"]] == [("A", 0.5), ("G", 0.5)]
    assert [(c, sh) for c, _, sh in mixes["G-CASH"]] == [("G", 0.5), ("CASH", 0.5)]
    assert [(c, sh) for c, _, sh in mixes["A-CASH"]] == [("A", 0.5), ("CASH", 0.5)]


def test_decision_shipped_config_matches_test_fixture(tmp_path):
    assert replace(_shipped(), sha256="") == replace(load(tmp_path), sha256="")


def test_decision_pixi_task():
    tasks = tomllib.loads((ROOT / "pixi.toml").read_text())["tasks"]
    assert tasks["decision"] == "python scripts/decision.py"


def _load_cli():
    spec = importlib.util.spec_from_file_location("decision_cli", ROOT / "scripts" / "decision.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cli = _load_cli()


def _fake_ohlcv(drop: str | None = None):
    def fake(tickers, refresh=False):
        open_, close = synthetic_prices(tickers, start="1999-01-01", end="2021-12-31")
        if drop is not None:
            open_, close = open_.drop(columns=drop), close.drop(columns=drop)
        return {"open": open_, "close": close}

    return fake


def _fake_macro(series):
    def fake(ids=None, trading_index=None, refresh=False, cache_dir=None, config_path=None):
        assert ids == [CPI_SERIES]
        return series.to_frame(CPI_SERIES)

    return fake


def _quick_config(tmp_path):
    return write(tmp_path, GOOD.replace(YEARS_LINE, "start_years: [2005, 2006]"))


def test_decision_main_writes_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "load_ohlcv", _fake_ohlcv())
    monkeypatch.setattr(cli, "load_macro", _fake_macro(cpi()))
    out = tmp_path / "decision.md"
    assert cli.main(["--config", str(_quick_config(tmp_path)), "--out-md", str(out)]) == 0
    md = out.read_text()
    assert "$" not in md
    assert "## Withdrawals" in md
    assert "| G-EW |" in md


def test_decision_main_fails_on_missing_ticker(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_ohlcv", _fake_ohlcv(drop="RSP"))
    monkeypatch.setattr(cli, "load_macro", _fake_macro(cpi()))
    out = tmp_path / "decision.md"
    assert cli.main(["--config", str(_quick_config(tmp_path)), "--out-md", str(out)]) == 1
    assert "RSP" in capsys.readouterr().out
    assert not out.exists()


def test_decision_main_reports_a_refusal(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_ohlcv", _fake_ohlcv())
    monkeypatch.setattr(cli, "load_macro", _fake_macro(cpi().loc[:"2005-06-30"]))
    out = tmp_path / "decision.md"
    assert cli.main(["--config", str(_quick_config(tmp_path)), "--out-md", str(out)]) == 1
    printed = capsys.readouterr().out
    assert "refused" in printed
    assert "missing CPI" in printed
    assert not out.exists()
