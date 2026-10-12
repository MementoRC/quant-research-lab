"""True cash for every core (spec: docs/methodology/true-cash-all-cores.md):
the loader's `cash_assumptions` list, its refusals and the shipped config.
Offline: fixture configs and the shipped decision.yaml only."""

from __future__ import annotations

import pytest
from decision_helpers import (
    CANDIDATES,
    END,
    GOOD_SLEEVE,
    GOOD_TCASH,
    GOOD_TCASH_ALL,
    ROOT,
    TCASH_ALL_BLENDS,
    load,
    stress_cfg,
)

from qrl.decision_config import CashAssumption, load_decision_config

CORES = "ABCDEFG"


def _row(x: str) -> CashAssumption:
    return CashAssumption(
        id=f"{x}80-TCASH20",
        label=f"80% {x} + 20% cash at +1% real (assumption)",
        base=x,
        cash_share=0.2,
        real_yield=0.01,
        pair=f"{x}80-CASH20",
    )


def _with_rows(rows: str) -> str:
    """GOOD_SLEEVE plus the six X80-CASH20 blends and the given YAML rows."""
    text = GOOD_SLEEVE.replace("windows:", TCASH_ALL_BLENDS + "windows:", 1)
    return text.replace("windows:", rows + "windows:", 1)


def test_list_form_loads_seven_rows_in_order(tmp_path):
    cfg = load(tmp_path, GOOD_TCASH_ALL)
    assert cfg.cash_assumptions == tuple(_row(x) for x in CORES)
    assert cfg.cash_assumption == cfg.cash_assumptions[0]


def test_singular_form_is_a_one_element_tuple(tmp_path):
    cfg = load(tmp_path, GOOD_TCASH)
    assert cfg.cash_assumption is not None
    assert cfg.cash_assumptions == (cfg.cash_assumption,)
    assert cfg.cash_assumption.pair is None


def test_singular_form_accepts_a_pair(tmp_path):
    text = GOOD_TCASH.replace("  real_yield: 0.01\n", "  real_yield: 0.01\n  pair: A80-CASH20\n", 1)
    assert load(tmp_path, text).cash_assumption.pair == "A80-CASH20"


def test_no_key_gives_none_and_empty_tuple(tmp_path):
    cfg = load(tmp_path, GOOD_SLEEVE)
    assert cfg.cash_assumption is None
    assert cfg.cash_assumptions == ()


def test_both_keys_are_refused(tmp_path):
    text = GOOD_TCASH_ALL.replace("windows:", "cash_assumption:\n  id: X\nwindows:", 1)
    with pytest.raises(ValueError, match="both"):
        load(tmp_path, text)


@pytest.mark.parametrize("value", ["[]", "7", "{id: A80-TCASH20}"])
def test_list_key_must_be_a_non_empty_list(tmp_path, value):
    with pytest.raises(ValueError, match="non-empty list"):
        load(tmp_path, _with_rows(f"cash_assumptions: {value}\n"))


def test_duplicate_id_is_refused(tmp_path):
    text = GOOD_TCASH_ALL.replace("id: B80-TCASH20", "id: A80-TCASH20", 1)
    with pytest.raises(ValueError, match=r"duplicate cash_assumption id"):
        load(tmp_path, text)


def test_duplicate_base_is_refused(tmp_path):
    tail = "cash_share: 0.2, real_yield: 0.01, pair:"
    text = GOOD_TCASH_ALL.replace(f"base: B, {tail} B80", f"base: A, {tail} A80", 1)
    with pytest.raises(ValueError, match=r"duplicate cash_assumption base"):
        load(tmp_path, text)


@pytest.mark.parametrize(
    ("old", "new", "match"),
    [
        ("pair: B80-CASH20", "pair: Z80-CASH20", "not a portfolio id"),
        ("pair: B80-CASH20", "pair: A80-IEF20", "exactly"),
        ("pair: B80-CASH20", "pair: A80-CASH20", "exactly"),
        ("pair: B80-CASH20", "pair: B", "exactly"),
        ("pair: B80-CASH20", "pair: AG", "exactly"),
    ],
)
def test_pair_must_be_the_matching_cash_blend(tmp_path, old, new, match):
    assert old in GOOD_TCASH_ALL
    with pytest.raises(ValueError, match=match):
        load(tmp_path, GOOD_TCASH_ALL.replace(old, new, 1))


def test_pair_share_must_match_cash_share(tmp_path):
    text = GOOD_TCASH_ALL.replace("base: B, cash_share: 0.2,", "base: B, cash_share: 0.3,", 1)
    with pytest.raises(ValueError, match="exactly"):
        load(tmp_path, text)


def test_per_entry_refusals_still_apply_in_the_list(tmp_path):
    text = GOOD_TCASH_ALL.replace("base: C, cash_share: 0.2", "base: Z, cash_share: 0.2", 1)
    with pytest.raises(ValueError, match="not a portfolio id"):
        load(tmp_path, text)


def test_shipped_config_loads_seven_rows_and_27_portfolios():
    cfg = load_decision_config(ROOT / "config" / "decision.yaml", CANDIDATES, stress_cfg(), END)
    assert [r.id for r in cfg.cash_assumptions] == [f"{x}80-TCASH20" for x in CORES]
    assert [r.base for r in cfg.cash_assumptions] == list(CORES)
    assert [r.pair for r in cfg.cash_assumptions] == [f"{x}80-CASH20" for x in CORES]
    assert cfg.cash_assumption == cfg.cash_assumptions[0]
    assert len(cfg.portfolios) == 27
