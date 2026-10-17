"""What-if mix (spec: docs/methodology/whatif-mix.md). Offline: the shipped
config/decision.yaml plus synthetic prices and CPI. Existing tests are untouched."""

from __future__ import annotations

import pytest

from qrl import decision_config, decision_report
from qrl.whatif import parse_mix, parse_rate


def test_whatif_public_aliases_are_the_private_objects():
    assert decision_config.blend_portfolio is decision_config._blend
    assert decision_config.check_full is decision_config._check_full
    assert decision_config.SUM_TOLERANCE == decision_config._EPS == 1e-9
    for name in (
        "pct",
        "signed",
        "portfolio_section",
        "return_section",
        "window_section",
        "scenario_section",
        "withdrawal_section",
        "year_one_section",
        "switching_note",
    ):
        assert getattr(decision_report, name) is getattr(decision_report, f"_{name}")
    for const in ("DOTCOM_PROXY_NOTE", "KNOWN_GAP_NOTE", "DRAWDOWN_NOTE"):
        assert isinstance(getattr(decision_report, const), str)


VALID = ["A", "B", "G", "CASH", "AG", "TCASH"]


def test_parse_mix_keeps_order_and_drops_zero_shares():
    assert parse_mix("G=0.5, A=0.5 ,CASH=0", VALID) == [("G", 0.5), ("A", 0.5)]


def test_parse_mix_accepts_a_sum_within_the_loader_tolerance():
    assert parse_mix("A=0.5,CASH=0.5000000005", VALID) == [("A", 0.5), ("CASH", 0.5000000005)]


@pytest.mark.parametrize(
    ("text", "match"),
    [
        (None, "--mix is required"),
        ("", "--mix is required"),
        ("   ", "--mix is required"),
        ("A", "NAME=SHARE"),
        ("A=", "NAME=SHARE"),
        ("=1", "NAME=SHARE"),
        ("A=1,", "NAME=SHARE"),
        ("A=0.5=0.5", "NAME=SHARE"),
        ("A=abc,CASH=1", "not a number"),
        ("A=nan,CASH=1", "finite"),
        ("A=inf", "finite"),
        ("A=-0.5,CASH=1.5", "finite number >= 0"),
        ("A=0.5,A=0.5", "repeated"),
        ("A=1,A=0", "repeated"),
        ("A=0.5,Z=0.5", "unknown mix name"),
        ("Z=0,A=1", "unknown mix name"),
        ("A=0.5,CASH=0.4", "sum"),
        ("A=0.5,CASH=0.500000002", "sum"),
    ],
)
def test_parse_mix_refuses(text, match):
    with pytest.raises(ValueError, match=match):
        parse_mix(text, VALID)


def test_parse_mix_unknown_name_lists_the_valid_ones():
    with pytest.raises(ValueError, match="valid names: A, B, G, CASH, AG, TCASH"):
        parse_mix("Z=1", VALID)


def test_parse_rate():
    assert parse_rate(None) is None
    assert parse_rate("0.045") == 0.045
    assert parse_rate("0.1") == 0.1


@pytest.mark.parametrize("text", ["x", "0", "-0.01", "0.1000001", "nan", "inf"])
def test_parse_rate_refuses(text):
    with pytest.raises(ValueError, match="--rate"):
        parse_rate(text)
