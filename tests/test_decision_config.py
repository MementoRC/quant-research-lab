"""Tests for the decision-helper config and portfolio model (qrl.decision_config).
Offline. Spec: docs/methodology/decision-helper.md."""

from __future__ import annotations

import hashlib

import pytest
from decision_helpers import (
    CANDIDATES,
    CANDIDATES_SHA,
    END,
    GOOD,
    load,
    stress_cfg,
    write,
)

from qrl.core_compare import Candidate
from qrl.decision_config import (
    Portfolio,
    held_tickers,
    load_decision_config,
    portfolio_states,
)

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


def test_decision_held_tickers_exclude_zero_weight_tickers():
    zero = Candidate("Z", "zero weight", "core_mix", {"risk_on": {"SPY": 1.0, "GLD": 0.0}})
    assert held_tickers([_one(zero)]) == {"SPY"}


def test_decision_config_loads_good(tmp_path):
    cfg = load(tmp_path)
    assert [p.id for p in cfg.portfolios] == [*"ABCDEFG", "CASH", "G-EW", "AG", "G-CASH", "A-CASH"]
    assert cfg.candidate_count == 7
    assert cfg.candidates_sha256 == CANDIDATES_SHA
    assert cfg.sha256 == hashlib.sha256((tmp_path / "decision.yaml").read_bytes()).hexdigest()
    assert [w.name for w in cfg.windows] == ["dotcom_2000", "gfc_2008"]
    assert [s.name for s in cfg.scenarios] == [
        "treasury_dollar_crisis",
        "trade_oil_shock",
        "ai_megacap_crash",
    ]
    assert cfg.rates == [0.02, 0.033, 0.04, 0.05]
    assert cfg.start_years == list(range(2005, 2015))
    assert cfg.proxied_threshold == 0.25
    by_id = {p.id: p for p in cfg.portfolios}
    assert [(c.id, s) for c, s in by_id["A-CASH"].parts] == [("A", 0.5), ("CASH", 0.5)]
    assert [(c.id, s) for c, s in by_id["G-CASH"].parts] == [("G", 0.5), ("CASH", 0.5)]


def test_decision_config_hash_changes_when_yaml_is_edited(tmp_path):
    first = load(tmp_path).sha256
    second = load(tmp_path, GOOD + "# edited\n").sha256
    assert first != second
    assert second == hashlib.sha256((tmp_path / "decision.yaml").read_bytes()).hexdigest()


def test_decision_config_refuses_inflation_at_or_below_minus_one(tmp_path):
    with pytest.raises(ValueError, match="above -1"):
        load(tmp_path, GOOD.replace("inflation: 0.08", "inflation: -1.0"))


def test_decision_config_refuses_candidates_sha_mismatch(tmp_path):
    edited = tmp_path / "core_candidates.yaml"
    edited.write_text(CANDIDATES.read_text() + "# edited\n")
    with pytest.raises(ValueError, match="sha256 mismatch"):
        load_decision_config(write(tmp_path, GOOD), edited, stress_cfg(), END)


def test_decision_config_refuses_scenario_missing_a_held_fund(tmp_path):
    with pytest.raises(ValueError, match="missing held fund"):
        load(tmp_path, GOOD.replace("RSP: -0.22, ", ""))


def test_decision_config_refuses_return_at_or_below_minus_one(tmp_path):
    with pytest.raises(ValueError, match="above -1"):
        load(tmp_path, GOOD.replace("QQQ: -0.45", "QQQ: -1.0"))


def test_decision_config_refuses_window_past_data_end(tmp_path):
    text = GOOD.replace("windows: [dotcom_2000, gfc_2008]", "windows: [dotcom_2000, covid_2020]")
    with pytest.raises(ValueError, match="past the data end"):
        load(tmp_path, text)


def test_decision_config_refuses_unknown_window(tmp_path):
    text = GOOD.replace("windows: [dotcom_2000, gfc_2008]", "windows: [dotcom_2000, nope]")
    with pytest.raises(ValueError, match="not in stress.yaml"):
        load(tmp_path, text)


def test_decision_config_refuses_start_year_past_data_end(tmp_path):
    with pytest.raises(ValueError, match="past the data end"):
        load(tmp_path, GOOD.replace("2014]", "2014, 2019]"))


def test_decision_config_refuses_blend_not_at_full_capital(tmp_path):
    with pytest.raises(ValueError, match="not 100%"):
        load(tmp_path, GOOD.replace("parts: {A: 0.5, G: 0.5}", "parts: {A: 0.5, G: 0.4}"))


def test_decision_config_refuses_static_mix_not_at_full_capital(tmp_path):
    with pytest.raises(ValueError, match="not 100%"):
        load(tmp_path, GOOD.replace("mix: {SHY: 1.0}", "mix: {SHY: 0.9}"))


def test_decision_config_refuses_unknown_blend_component(tmp_path):
    text = GOOD.replace("parts: {G: 0.5, CASH: 0.5}", "parts: {G: 0.5, CASHX: 0.5}")
    with pytest.raises(ValueError, match="unknown component"):
        load(tmp_path, text)


def test_decision_config_refuses_duplicate_portfolio_id(tmp_path):
    with pytest.raises(ValueError, match="duplicate portfolio id"):
        load(tmp_path, GOOD.replace("id: G-EW", "id: CASH"))


def test_decision_config_refuses_duplicate_scenario_name(tmp_path):
    text = GOOD.replace("name: trade_oil_shock", "name: treasury_dollar_crisis")
    with pytest.raises(ValueError, match="duplicate scenario"):
        load(tmp_path, text)


def test_decision_config_refuses_missing_key(tmp_path):
    with pytest.raises(ValueError, match="missing key"):
        load(tmp_path, GOOD.replace("proxied_indicative_above: 0.25\n", ""))


def test_decision_config_refuses_malformed_yaml(tmp_path):
    with pytest.raises(ValueError, match="valid YAML"):
        load(tmp_path, "version: 1\nstatic: [unclosed\n")
