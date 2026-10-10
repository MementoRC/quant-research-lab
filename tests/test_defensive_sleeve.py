"""Defensive-sleeve comparison (spec: docs/methodology/defensive-sleeve.md):
the A80 blends in config/decision.yaml, the longrun pin, the research-period
return rows and their report section. Offline: synthetic prices and fixture
configs only (never market data); research period only."""

from __future__ import annotations

import pytest
from decision_helpers import CANDIDATES, END, ROOT, stress_cfg

from qrl.decision_config import load_decision_config, portfolio_states
from qrl.longrun import load_longrun_config

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
