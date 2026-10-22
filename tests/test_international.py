"""Tests for qrl.international (docs/methodology/international-test.md).
Synthetic data only; nothing here downloads."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from qrl.international import (
    NotCovered,
    Rule,
    derive_equity_leg,
    holds_gold,
    load_international_config,
    translate,
)
from qrl.strategies import REGISTRY

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "international.yaml"


def _cfg():
    return load_international_config(CONFIG)[0]


def _variant(tmp_path: Path, old: str, new: str) -> Path:
    text = CONFIG.read_text(encoding="utf-8")
    assert old in text
    path = tmp_path / "international.yaml"
    path.write_text(text.replace(old, new), encoding="utf-8")
    return path


def test_config_loads_as_pre_registered():
    cfg, sha = load_international_config(CONFIG)
    assert len(sha) == 64
    assert cfg.set_names == ["main", "reserve_1", "reserve_2"]
    assert cfg.market_set("main").markets == ("EWJ", "EWU", "EWG", "EWC", "EWA", "EWL", "EWQ")
    assert [s.min_pass for s in cfg.sets] == [5, 4, 3]
    assert cfg.windows == (
        (pd.Timestamp("1997-01-01"), pd.Timestamp("2004-12-31")),
        (pd.Timestamp("2023-01-01"), None),
    )
    assert cfg.min_scored_days == 500
    assert cfg.treasury == {"SHY": ("DGS2", 1.9), "IEF": ("DGS10", 7.5), "TLT": ("DGS20", 17.0)}
    assert cfg.funds == ["GLD", "IEF", "SHY", "TLT"]
    assert cfg.covered == frozenset({"core_trend", "core_mix"})
    assert cfg.cash_fred == "DTB3"
    assert cfg.fred_ids == ["DGS10", "DGS2", "DGS20", "DTB3"]
    assert cfg.gold_ticker == "GC=F"
    assert not hasattr(cfg, "equity_leg")
    assert not hasattr(cfg, "gold_lag_days")


def test_unknown_set_is_refused():
    with pytest.raises(ValueError, match="unknown market set"):
        _cfg().market_set("nicer_one")


def test_window_overlapping_excluded_years_is_refused(tmp_path):
    path = _variant(tmp_path, 'end: "2004-12-31"', 'end: "2005-06-30"')
    with pytest.raises(ValueError, match="excluded"):
        load_international_config(path)


def test_market_repeated_across_sets_is_refused(tmp_path):
    path = _variant(tmp_path, "markets: [EWN,", "markets: [EWJ,")
    with pytest.raises(ValueError, match="repeats"):
        load_international_config(path)


def test_min_pass_above_set_size_is_refused(tmp_path):
    path = _variant(tmp_path, "min_pass: 3", "min_pass: 5")
    with pytest.raises(ValueError, match="min_pass"):
        load_international_config(path)


TREND = Rule("core_trend", {"risk_on": "SPY", "risk_off": "IEF", "lookback": 200})


def test_covered_strategies_are_registry_names():
    assert _cfg().covered <= set(REGISTRY)


def test_the_equity_leg_is_derived_from_the_params():
    cfg = _cfg()
    assert derive_equity_leg(TREND, cfg) == "SPY"
    assert (
        derive_equity_leg(
            Rule("core_trend", {"risk_on": "QQQ", "risk_off": "CASH", "lookback": 150}), cfg
        )
        == "QQQ"
    )
    # an equity ticker only in risk_off, and a signal naming the same ticker
    assert (
        derive_equity_leg(Rule("core_trend", {"risk_on": "GLD", "risk_off": "QQQ"}), cfg) == "QQQ"
    )
    mix = Rule(
        "core_mix",
        {"risk_on": {"SPY": 0.6, "IEF": 0.4}, "risk_off": {"GLD": 0.5}, "signal": "SPY"},
    )
    assert derive_equity_leg(mix, cfg) == "SPY"


@pytest.mark.parametrize(
    "rule",
    [
        Rule("core_mix", {"risk_on": {"SPY": 0.5, "QQQ": 0.5}}),  # two equity legs
        Rule("core_mix", {"risk_on": {"SPY": 1.0}, "signal": "QQQ"}),  # two via signal
        Rule("core_trend", {"risk_on": "GLD", "risk_off": "IEF"}),  # zero: all defensive
        Rule("core_trend", {"risk_off": "IEF", "lookback": 200}),  # zero: leg left to a default
        Rule("buy_and_hold", {"ticker": "SPY"}),  # strategy not covered
    ],
)
def test_uncovered_rules_are_refused(rule):
    with pytest.raises(NotCovered):
        derive_equity_leg(rule, _cfg())


def test_translate_swaps_only_the_equity_ticker():
    rule = Rule(
        "core_mix",
        {
            "risk_on": {"SPY": 0.6, "IEF": 0.4},
            "risk_off": {"IEF": 0.5, "GLD": 0.5},
            "signal": "SPY",
            "lookback": 200,
        },
    )
    out = translate(rule, "SPY", "EWJ")
    assert out.params == {
        "risk_on": {"EWJ": 0.6, "IEF": 0.4},
        "risk_off": {"IEF": 0.5, "GLD": 0.5},
        "signal": "EWJ",
        "lookback": 200,
    }
    assert rule.params["signal"] == "SPY"  # the accepted rule is untouched


def test_translate_refuses_an_equity_leg_left_to_a_default():
    with pytest.raises(NotCovered, match="default"):
        translate(Rule("core_trend", {"risk_off": "GLD", "lookback": 200}), "QQQ", "EWJ")


def test_rule_sha_ignores_key_order():
    a = Rule("core_trend", {"risk_on": "SPY", "lookback": 200})
    b = Rule("core_trend", {"lookback": 200, "risk_on": "SPY"})
    assert a.sha256 == b.sha256
    assert len(a.sha256) == 64


def test_holds_gold():
    assert holds_gold(Rule("core_trend", {"risk_on": "SPY", "risk_off": "GLD"}), _cfg())
    assert not holds_gold(TREND, _cfg())
