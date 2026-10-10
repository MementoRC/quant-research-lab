"""Defensive-sleeve comparison (spec: docs/methodology/defensive-sleeve.md):
the A80 blends in config/decision.yaml, the longrun pin, the research-period
return rows and their report section. Offline: synthetic prices and fixture
configs only (never market data); research period only."""

from __future__ import annotations

import copy
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from decision_helpers import (
    CANDIDATES,
    END,
    GOOD_SLEEVE,
    ROOT,
    cpi,
    criteria,
    load,
    prices,
    stress_cfg,
)

from qrl import decision
from qrl.decision import portfolio_returns, return_rows, run_decision
from qrl.decision_config import load_decision_config, portfolio_states
from qrl.longrun import load_longrun_config
from qrl.metrics import compute_metrics

SLEEVES = {
    "CASH": {"SHY": 1.0},
    "IEF": {"IEF": 1.0},
    "TLT": {"TLT": 1.0},
    "BONDS": {"SHY": 1 / 3, "IEF": 1 / 3, "TLT": 1 / 3},
    "RSP": {"RSP": 1.0},
}
A80 = ["A80-CASH20", "A80-IEF20", "A80-TLT20", "A80-BONDS20", "A80-RSP20"]


def _shipped():
    return load_decision_config(ROOT / "config" / "decision.yaml", CANDIDATES, stress_cfg(), END)


def test_shipped_sleeve_statics_hold_their_funds():
    by_id = {p.id: p for p in _shipped().portfolios}
    for sid, mix in SLEEVES.items():
        states = portfolio_states(by_id[sid])
        assert list(states) == ["static"], sid
        assert states["static"] == pytest.approx(mix, abs=1e-12), sid
        assert sum(states["static"].values()) == pytest.approx(1.0, abs=1e-9), sid


def test_shipped_a80_blends_hold_80_percent_a_and_20_percent_sleeve():
    by_id = {p.id: p for p in _shipped().portfolios}
    a_states = portfolio_states(by_id["A"])
    assert set(a_states) == {"risk_on", "risk_off"}
    for sid, sleeve in SLEEVES.items():
        blend = by_id[f"A80-{sid}20"]
        assert blend.label == f"80% A + 20% {sid}"
        assert [(c.id, share) for c, share in blend.parts] == [("A", 0.8), (sid, 0.2)]
        states = portfolio_states(blend)
        assert set(states) == set(a_states)
        for name, a_mix in a_states.items():
            expected: dict[str, float] = {}
            for mix, share in ((a_mix, 0.8), (sleeve, 0.2)):
                for ticker, weight in mix.items():
                    expected[ticker] = expected.get(ticker, 0.0) + share * weight
            assert states[name] == pytest.approx(expected, abs=1e-12), (sid, name)
            assert sum(states[name].values()) == pytest.approx(1.0, abs=1e-9), (sid, name)


def test_shipped_decision_config_counts_21_portfolios_with_five_a80_rows():
    ids = [p.id for p in _shipped().portfolios]
    assert len(ids) == 21
    assert [i for i in ids if i.startswith("A80-")] == A80


def test_shipped_longrun_pin_matches_shipped_decision_config():
    lcfg = load_longrun_config(ROOT / "config" / "longrun.yaml", _shipped().sha256)
    assert (lcfg.seed, lcfg.n_paths, lcfg.block_months, lcfg.horizon_years) == (
        20261008,
        10000,
        12,
        30,
    )
    assert lcfg.real_floor == 0.5
    assert lcfg.rates == [0.02, 0.033, 0.04, 0.05]
    assert lcfg.cash_real_yield == 0.01


FIRST = pd.Timestamp("2005-01-03")  # first synthetic trading day on/after 2005-01-01
SMALL_IDS = ("A", "CASH", "A80-CASH20", "A80-BONDS20")


@pytest.fixture(scope="module")
def small(tmp_path_factory):
    cfg = load(tmp_path_factory.mktemp("sleeve"), GOOD_SLEEVE)
    by_id = {p.id: p for p in cfg.portfolios}
    return replace(cfg, portfolios=[by_id[i] for i in SMALL_IDS], start_years=[2005])


def test_return_rows_match_compute_metrics(small):
    data = prices()
    rows = return_rows(small, data, criteria())
    assert [r["portfolio"] for r in rows] == list(SMALL_IDS)
    cut = {k: v.loc[:END] for k, v in data.items()}
    by_id = {p.id: p for p in small.portfolios}
    expected = {i: compute_metrics(portfolio_returns(by_id[i], cut, FIRST, 5.0)) for i in SMALL_IDS}
    for r in rows:
        m = expected[r["portfolio"]]
        assert set(r) == {"portfolio", "cagr", "max_drawdown", "lost_return"}
        assert r["cagr"] == pytest.approx(m["cagr"], abs=1e-12)
        assert r["max_drawdown"] == pytest.approx(m["max_drawdown"], abs=1e-12)
        assert r["max_drawdown"] > 0  # positive, as metrics.py returns it
        assert r["lost_return"] == pytest.approx(expected["A"]["cagr"] - m["cagr"], abs=1e-12)
    assert rows[0]["lost_return"] == 0.0


def test_return_rows_start_at_the_research_start_and_stop_at_the_data_end(small, monkeypatch):
    seen = []
    real = decision.portfolio_returns

    def spy(p, data, start, cost_bps):
        seen.append((start, data["close"].index[-1], data["open"].index[-1], cost_bps))
        return real(p, data, start, cost_bps)

    monkeypatch.setattr(decision, "portfolio_returns", spy)
    return_rows(small, prices(), criteria())
    assert len(seen) == len(SMALL_IDS)
    assert all(s == (FIRST, END, END, 5.0) for s in seen)


def test_return_rows_ignore_data_after_the_data_end(small):
    data = prices()
    after = np.asarray(data["close"].index > END)
    rng = np.random.default_rng(5)
    poisoned = {
        k: v * np.where(after[:, None], rng.uniform(0.2, 5.0, v.shape), 1.0)
        for k, v in data.items()
    }
    assert not poisoned["close"].equals(data["close"])
    assert return_rows(small, poisoned, criteria()) == return_rows(small, data, criteria())


def test_return_rows_lost_return_is_none_without_a(small):
    no_a = replace(small, portfolios=[p for p in small.portfolios if p.id != "A"])
    rows = return_rows(no_a, prices(), criteria())
    assert [r["portfolio"] for r in rows] == list(SMALL_IDS[1:])
    assert all(r["lost_return"] is None for r in rows)


def test_return_rows_refuse_a_research_period_without_start(small):
    crit = copy.deepcopy(criteria())
    crit["periods"]["research"]["start"] = None
    with pytest.raises(ValueError, match="research period has no start"):
        return_rows(small, prices(), crit)


def test_run_decision_carries_the_return_rows(small):
    data, crit = prices(), criteria()
    report = run_decision(small, data, cpi(), crit, "cd" * 32)
    assert report["returns"] == return_rows(small, data, crit)
