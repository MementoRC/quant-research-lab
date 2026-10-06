"""Tests for the decision-helper config and portfolio model (qrl.decision_config).
Offline. Spec: docs/methodology/decision-helper.md."""

from __future__ import annotations

import pytest

from qrl.core_compare import Candidate
from qrl.decision_config import Portfolio, held_tickers, portfolio_states

A = Candidate("A", "trend", "core_trend", {"risk_on": "QQQ", "risk_off": "GLD", "lookback": 200})
G = Candidate(
    "G", "static", "core_mix", {"risk_on": {"SPY": 0.25, "TLT": 0.25, "GLD": 0.25, "SHY": 0.25}}
)
CASH = Candidate("CASH", "100% SHY", "core_mix", {"risk_on": {"SHY": 1.0}})
F = Candidate(
    "F",
    "switched mix",
    "core_mix",
    {
        "risk_on": {"SPY": 0.6, "IEF": 0.4},
        "risk_off": {"IEF": 0.5, "GLD": 0.5},
        "signal": "SPY",
        "lookback": 200,
    },
)


def _one(cand: Candidate) -> Portfolio:
    return Portfolio(cand.id, cand.label, ((cand, 1.0),))


def test_decision_static_portfolio_has_one_state():
    assert portfolio_states(_one(G)) == {
        "static": {"SPY": 0.25, "TLT": 0.25, "GLD": 0.25, "SHY": 0.25}
    }
    assert portfolio_states(_one(CASH)) == {"static": {"SHY": 1.0}}


def test_decision_switching_core_has_both_states():
    assert portfolio_states(_one(A)) == {"risk_on": {"QQQ": 1.0}, "risk_off": {"GLD": 1.0}}
    assert portfolio_states(_one(F)) == {
        "risk_on": {"SPY": 0.6, "IEF": 0.4},
        "risk_off": {"IEF": 0.5, "GLD": 0.5},
    }


def test_decision_blend_with_switching_part_has_exactly_two_states():
    ag = Portfolio("AG", "1/2 A + 1/2 G", ((A, 0.5), (G, 0.5)))
    states = portfolio_states(ag)
    assert list(states) == ["risk_on", "risk_off"]
    assert states["risk_on"] == pytest.approx(
        {"QQQ": 0.5, "SPY": 0.125, "TLT": 0.125, "GLD": 0.125, "SHY": 0.125}
    )
    assert states["risk_off"] == pytest.approx(
        {"GLD": 0.625, "SPY": 0.125, "TLT": 0.125, "SHY": 0.125}
    )


def test_decision_static_blend_is_static():
    gc = Portfolio("G-CASH", "1/2 G + 1/2 CASH", ((G, 0.5), (CASH, 0.5)))
    states = portfolio_states(gc)
    assert list(states) == ["static"]
    assert states["static"] == pytest.approx(
        {"SPY": 0.125, "TLT": 0.125, "GLD": 0.125, "SHY": 0.625}
    )


def test_decision_held_tickers_exclude_signal_only_tickers():
    signal_only = Candidate(
        "S",
        "switch on QQQ",
        "core_mix",
        {"risk_on": {"SPY": 1.0}, "risk_off": {"IEF": 1.0}, "signal": "QQQ", "lookback": 5},
    )
    assert held_tickers([_one(A), _one(CASH)]) == {"QQQ", "GLD", "SHY"}
    assert held_tickers([_one(signal_only)]) == {"SPY", "IEF"}
