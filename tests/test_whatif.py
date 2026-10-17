"""What-if mix (spec: docs/methodology/whatif-mix.md). Offline: the shipped
config/decision.yaml plus synthetic prices and CPI. Existing tests are untouched."""

from __future__ import annotations

from dataclasses import replace

import pytest
from decision_helpers import CANDIDATES, END, ROOT, stress_cfg

from qrl import decision_config, decision_report
from qrl.decision_config import load_decision_config, portfolio_states
from qrl.whatif import mix_cash_row, mix_portfolio, parse_mix, parse_rate, split_shares


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


@pytest.fixture(scope="module")
def shipped():
    return load_decision_config(ROOT / "config" / "decision.yaml", CANDIDATES, stress_cfg(), END)


def _same_states(a, b):
    sa, sb = portfolio_states(a), portfolio_states(b)
    assert sa.keys() == sb.keys()
    for state in sa:
        assert sa[state] == pytest.approx(sb[state])


def test_split_shares_renormalises_the_non_cash_part():
    noncash, tcash = split_shares([("G", 0.5), ("A", 0.3), ("TCASH", 0.2)])
    assert tcash == 0.2
    assert [n for n, _ in noncash] == ["G", "A"]
    assert noncash[0][1] == pytest.approx(0.625)
    assert sum(s for _, s in noncash) == pytest.approx(1.0, abs=1e-15)


def test_split_shares_without_tcash_and_with_only_tcash():
    assert split_shares([("A", 0.8), ("CASH", 0.2)]) == ([("A", 0.8), ("CASH", 0.2)], 0.0)
    assert split_shares([("TCASH", 1.0)]) == ([], 1.0)


def test_split_shares_clamps_tcash_within_the_sum_tolerance():
    # parse_mix accepts a sum up to 1e-9 above 1; the cash row must still get share 1
    assert parse_mix("TCASH=1.0000000005", VALID) == [("TCASH", 1.0000000005)]
    assert split_shares([("TCASH", 1.0000000005)]) == ([], 1.0)


def test_mix_portfolio_is_the_loaders_blend(shipped):
    mix = mix_portfolio([("A", 0.8), ("CASH", 0.2)], shipped)
    ref = {p.id: p for p in shipped.portfolios}["A80-CASH20"]
    assert mix.id == "MIX"
    assert mix.parts == ref.parts


def test_mix_portfolio_flattens_a_blend_ingredient(shipped):
    mix = mix_portfolio([("AG", 1.0)], shipped)
    assert [(c.id, s) for c, s in mix.parts] == [("A", 0.5), ("G", 0.5)]


def test_mix_portfolio_merges_duplicate_candidates(shipped):
    merged = mix_portfolio([("A", 0.3), ("AG", 0.7)], shipped)
    alone = mix_portfolio([("A", 0.65), ("G", 0.35)], shipped)
    assert [c.id for c, _ in merged.parts] == ["A", "G"]
    assert len(portfolio_states(merged)) == 2  # no state pairs A with itself
    _same_states(merged, alone)


def test_two_switching_ingredients_give_four_states(shipped):
    assert len(portfolio_states(mix_portfolio([("A", 0.5), ("B", 0.5)], shipped))) == 4


def test_mix_portfolio_is_fully_invested_in_every_state(shipped):
    mix = mix_portfolio([("G", 0.5), ("A", 0.3), ("BONDS", 0.2)], shipped)
    for weights in portfolio_states(mix).values():
        assert sum(weights.values()) == pytest.approx(1.0, abs=1e-9)


def test_mix_portfolio_is_none_without_a_non_cash_part(shipped):
    assert mix_portfolio([], shipped) is None


IDS = {"A", "CASH", "MIX"}


def test_cash_row_over_the_mix(shipped):
    row = mix_cash_row(shipped, 0.2, "MIX", IDS)
    assert (row.id, row.base, row.cash_share, row.real_yield, row.pair) == (
        "MIX-TCASH",
        "MIX",
        0.2,
        0.01,
        None,
    )


def test_cash_row_allows_one_hundred_percent_over_cash(shipped):
    row = mix_cash_row(shipped, 1.0, "CASH", {"A", "CASH"})
    assert (row.base, row.cash_share) == ("CASH", 1.0)
    assert row.label == "100% true cash (assumption)"


def test_cash_row_label_over_the_mix(shipped):
    assert mix_cash_row(shipped, 0.2, "MIX", IDS).label == "80% MIX + 20% cash (assumption)"


def test_cash_row_is_none_without_tcash(shipped):
    assert mix_cash_row(shipped, 0.0, "MIX", IDS) is None


def _with_yields(cfg, second):
    rows = list(cfg.cash_assumptions)
    rows[1] = replace(rows[1], real_yield=second)
    return replace(cfg, cash_assumptions=tuple(rows))


@pytest.mark.parametrize("tcash", [0.0, 0.2])
def test_cash_row_refuses_rows_with_different_yields(shipped, tcash):
    with pytest.raises(ValueError, match="different real_yield"):
        mix_cash_row(_with_yields(shipped, 0.02), tcash, "MIX", IDS)


def test_cash_row_refuses_a_yield_beyond_the_bound(shipped):
    rows = tuple(replace(r, real_yield=0.06) for r in shipped.cash_assumptions)
    with pytest.raises(ValueError, match="real_yield"):
        mix_cash_row(replace(shipped, cash_assumptions=rows), 0.2, "MIX", IDS)


def test_cash_row_needs_a_yield_in_the_config(shipped):
    bare = replace(shipped, cash_assumptions=())
    assert mix_cash_row(bare, 0.0, "MIX", IDS) is None
    with pytest.raises(ValueError, match="no cash_assumptions"):
        mix_cash_row(bare, 0.2, "MIX", IDS)


def test_cash_row_checks_base_id_and_share(shipped):
    with pytest.raises(ValueError, match="base 'MIX'"):
        mix_cash_row(shipped, 0.2, "MIX", {"A", "CASH"})
    with pytest.raises(ValueError, match="already a portfolio id"):
        mix_cash_row(shipped, 0.2, "MIX", {*IDS, "MIX-TCASH"})
    with pytest.raises(ValueError, match="cash_share"):
        mix_cash_row(shipped, 1.5, "MIX", IDS)
