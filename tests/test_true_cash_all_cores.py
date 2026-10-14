"""True cash for every core (spec: docs/methodology/true-cash-all-cores.md):
the loader's `cash_assumptions` list, its refusals and the shipped config.
Offline: fixture configs and the shipped decision.yaml only."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from decision_helpers import (
    CANDIDATES,
    END,
    GOOD_SLEEVE,
    GOOD_TCASH,
    GOOD_TCASH_ALL,
    ROOT,
    TCASH_ALL_BLENDS,
    criteria,
    load,
    prices,
    stress_cfg,
)
from test_true_cash import FIRST, _lcfg, uneven_cpi

from qrl.decision import (
    portfolio_returns,
    return_rows,
    run_decision,
    start_dates,
    withdrawal_rows,
)
from qrl.decision_config import CashAssumption, load_decision_config
from qrl.decision_report import _join
from qrl.decision_withdraw import monthly_withdrawals, path_metrics, withdrawal_path
from qrl.longrun import monthly_returns, run_longrun
from qrl.metrics import compute_metrics
from qrl.true_cash import cash_leg_returns

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


# ---- computation: a row for every cash assumption (decision and long-run) ----

COST = 5.0
IDS = [f"{x}80-TCASH20" for x in CORES]


@pytest.fixture(scope="module")
def seven(tmp_path_factory):
    cfg = load(tmp_path_factory.mktemp("tcash_all"), GOOD_TCASH_ALL)
    by_id = {p.id: p for p in cfg.portfolios}
    return replace(
        cfg,
        portfolios=[by_id[x] for x in CORES],
        rates=[0.04],
        start_years=[2005, 2010],
    )


def _cut():
    return {k: v.loc[:END] for k, v in prices().items()}


def _expected(cfg, ca, day):
    cut, known = _cut(), uneven_cpi().loc[:END]
    by_id = {p.id: p for p in cfg.portfolios}
    base = portfolio_returns(by_id[ca.base], cut, day, COST)
    cash = cash_leg_returns(
        pd.DatetimeIndex(base.index), pd.DatetimeIndex(cut["close"].index), known, ca.real_yield
    )
    return (1 - ca.cash_share) * base + ca.cash_share * cash


def test_return_rows_have_every_assumption_row_last_in_a_to_g_order(seven):
    rows = return_rows(seven, prices(), criteria(), uneven_cpi())
    assert [r["portfolio"] for r in rows] == [*CORES, *IDS]
    for ca, row in zip(seven.cash_assumptions, rows[len(CORES) :], strict=True):
        m = compute_metrics(_expected(seven, ca, FIRST))
        assert row["cagr"] == pytest.approx(m["cagr"], rel=1e-12)
        assert row["max_drawdown"] == pytest.approx(m["max_drawdown"], rel=1e-12)
        assert row["lost_return"] == pytest.approx(rows[0]["cagr"] - m["cagr"], rel=1e-9)


def test_return_rows_refuse_any_assumption_row_without_cpi(seven):
    with pytest.raises(ValueError, match="needs `cpi`"):
        return_rows(seven, prices(), criteria())


def test_each_row_is_the_daily_blend_of_its_base_and_the_cash_leg(seven):
    from qrl.decision import all_assumption_returns

    got = all_assumption_returns(seven, _cut(), uneven_cpi().loc[:END], FIRST, COST)
    assert list(got) == IDS
    for ca in seven.cash_assumptions:
        pd.testing.assert_series_equal(got[ca.id], _expected(seven, ca, FIRST), check_exact=True)


def test_withdrawal_rows_have_every_assumption_row_last_for_every_start_year(seven):
    index = uneven_cpi()
    rows = withdrawal_rows(seven, prices(), index, criteria())
    assert [r["portfolio"] for r in rows] == [*CORES, *IDS]
    known, cut = index.loc[:END], _cut()
    starts = start_dates(pd.DatetimeIndex(cut["close"].index), [2005, 2010], END)
    for ca, row in zip(seven.cash_assumptions, rows[len(CORES) :], strict=True):
        assert sorted(row["per_year"]) == [2005, 2010]
        for year, day in starts.items():
            monthly = monthly_withdrawals(0.04, year, 2018, known)
            path = withdrawal_path(_expected(seven, ca, day), monthly)
            assert row["per_year"][year] == path_metrics(path, known)


def test_run_decision_lists_every_row_and_nulls_the_single_key(seven):
    report = run_decision(seven, prices(), uneven_cpi(), criteria(), "cd" * 32)
    assert report["cash_assumption"] is None
    assert [r["id"] for r in report["cash_assumptions"]] == IDS
    assert report["cash_assumptions"][2] == {
        "id": "C80-TCASH20",
        "label": "80% C + 20% cash at +1% real (assumption)",
        "base": "C",
        "cash_share": 0.2,
        "real_yield": 0.01,
        "pair": "C80-CASH20",
    }
    assert [r["portfolio"] for r in report["returns"]][-7:] == IDS
    assert [r["portfolio"] for r in report["withdrawals"]][-7:] == IDS


def test_one_row_output_matches_its_slice_of_the_seven_row_output(seven):
    first = seven.cash_assumptions[0]
    one = replace(seven, cash_assumptions=(first,), cash_assumption=first)
    many = run_decision(seven, prices(), uneven_cpi(), criteria(), "cd" * 32)
    single = run_decision(one, prices(), uneven_cpi(), criteria(), "cd" * 32)
    assert single["cash_assumption"] == {
        "id": "A80-TCASH20",
        "label": "80% A + 20% cash at +1% real (assumption)",
        "base": "A",
        "cash_share": 0.2,
        "real_yield": 0.01,
    }
    assert [r["id"] for r in single["cash_assumptions"]] == ["A80-TCASH20"]
    assert single["returns"] == many["returns"][: len(CORES) + 1]
    assert single["withdrawals"] == many["withdrawals"][: len(CORES) + 1]


def test_assumption_rows_ignore_data_after_the_data_end(seven):
    data, index = prices(), uneven_cpi()
    rng = np.random.default_rng(11)
    after = np.asarray(data["close"].index > END)
    poisoned = {
        k: v * np.where(after[:, None], rng.uniform(0.2, 5.0, v.shape), 1.0)
        for k, v in data.items()
    }
    poisoned_cpi = index * np.where(
        np.asarray(index.index > END), rng.uniform(0.2, 5.0, len(index)), 1.0
    )
    crit = criteria()
    assert return_rows(seven, poisoned, crit, poisoned_cpi) == return_rows(seven, data, crit, index)
    assert withdrawal_rows(seven, poisoned, poisoned_cpi, crit) == withdrawal_rows(
        seven, data, index, crit
    )


def test_longrun_refuses_any_row_whose_yield_differs(seven):
    rows = list(seven.cash_assumptions)
    rows[2] = replace(rows[2], real_yield=0.02)
    bad = replace(seven, cash_assumptions=tuple(rows))
    with pytest.raises(ValueError, match="C80-TCASH20"):
        run_longrun(_lcfg(), bad, prices(), uneven_cpi(), criteria())


def test_longrun_adds_every_row_last_in_order_with_the_list_key(seven):
    report = run_longrun(_lcfg(), seven, prices(), uneven_cpi(), criteria())
    names = [r["portfolio"] for r in report["rows"]]
    assert names == [*CORES, *IDS]
    assert report["cash_assumptions"] == [
        {"id": ca.id, "base": ca.base, "share": 0.2, "pair": ca.pair}
        for ca in seven.cash_assumptions
    ]
    assert report["cash_assumption_id"] is None
    assert report["cash_assumption_base"] is None
    assert report["cash_assumption_share"] is None
    monthly = monthly_returns(_expected(seven, seven.cash_assumptions[4], FIRST))
    assert len(monthly) == 168


def test_longrun_one_row_keeps_the_scalar_keys(seven):
    first = seven.cash_assumptions[0]
    one = replace(seven, cash_assumptions=(first,), cash_assumption=first)
    report = run_longrun(_lcfg(), one, prices(), uneven_cpi(), criteria())
    assert [r["portfolio"] for r in report["rows"]] == [*CORES, "A80-TCASH20"]
    assert report["cash_assumption_id"] == "A80-TCASH20"
    assert report["cash_assumption_base"] == "A"
    assert report["cash_assumption_share"] == 0.2
    assert [r["id"] for r in report["cash_assumptions"]] == ["A80-TCASH20"]
    many = run_longrun(_lcfg(), seven, prices(), uneven_cpi(), criteria())
    assert report["rows"] == many["rows"][: len(CORES)] + [many["rows"][len(CORES)]]


# ---- report texts for several assumption rows (hand-built report dicts) ----

SHY_G = {"SPY": 0.75, "SHY": 0.25}


def _portfolios():
    out = [{"id": "A", "label": "A", "states": {"risk_on": {"SPY": 1.0}, "risk_off": {"SHY": 1.0}}}]
    out.append({"id": "G", "label": "G", "states": {"on": SHY_G}})
    for x in "AG":
        base = {"SPY": 1.0} if x == "A" else SHY_G
        mix = {k: 0.8 * w for k, w in base.items()}
        mix["SHY"] = mix.get("SHY", 0.0) + 0.2
        states = {"risk_on": mix, "risk_off": mix} if x == "A" else {"on": mix}
        out.append({"id": f"{x}80-CASH20", "label": x, "states": states})
    out.append({"id": "A80-IEF20", "label": "i", "states": {"on": {"IEF": 1.0}}})
    out.append({"id": "IEF", "label": "i", "states": {"on": {"IEF": 1.0}}})
    return out


def _rows_of(*cores):
    return [
        {
            "id": f"{x}80-TCASH20",
            "label": "l",
            "base": x,
            "cash_share": 0.2,
            "real_yield": 0.01,
            "pair": f"{x}80-CASH20",
        }
        for x in cores
    ]


def _report(rows, single=None):
    flag = {"unavailable": "", "window": "dotcom_2000", "mode": "frozen"}
    return {
        "candidate_count": 7,
        "portfolios": _portfolios(),
        "data_end": "2018-12-31",
        "decision_sha256": "a",
        "candidates_sha256": "b",
        "stress_sha256": "c",
        "cost_bps": 5.0,
        "engine_cost_bps": 5.0,
        "cash_assumption": single,
        "cash_assumptions": rows,
        "windows": [
            {**flag, "portfolio": "G", "indicative": True},
            {**flag, "portfolio": "A", "indicative": False},
            {**flag, "portfolio": "G80-CASH20", "indicative": True},
        ],
    }


def test_decision_header_has_the_multi_row_bullet():
    from qrl.decision_report import _header

    text = "\n".join(_header(_report(_rows_of("A", "G"))))
    assert "7 in the core comparison, 8 here (A-G again plus 1 new)" in text
    assert (
        "- A80-TCASH20 to G80-TCASH20 are 2 assumption rows, not funds: for each core, 20.0% "
        "cash earning each month's inflation plus 1.0% a year, the long-run report's CASH +1% "
        "real assumption, shown next to that core's SHY pair (A80-CASH20 to G80-CASH20) to "
        "answer the SHY caveat. They are comparisons 7-8 but not among the 6 portfolios. "
        "Their cash legs and daily returns to 80/20 pay no trading cost, while each SHY pair "
        "pays 5 bps per unit of turnover on its rebalancing, a small difference in the "
        "assumption rows' favour."
    ) in text
    assert "is an assumption row" not in text


def test_decision_notes_name_pairs_generally_and_generate_lists():
    from qrl.decision_report import _notes

    text = "\n".join(_notes(_report(_rows_of("A", "G"))))
    assert "each row would equal its SHY pair there" in text
    assert "A80-CASH20 uses" not in text
    assert "- Switching portfolios (A and A80-CASH20) are shown" in text
    assert (
        "- G already holds 25% SHY, so G80-CASH20 holds 40% SHY in all and G80-TCASH20 swaps "
        "only the added 20%."
    ) in text
    assert text.count("already holds") == 1


def test_decision_sleeve_note_adds_the_true_cash_question():
    from qrl.decision_report import _sleeve_note

    text = _sleeve_note(_report(_rows_of("A", "G")))[0]
    assert text.endswith(
        "(docs/methodology/defensive-sleeve.md); the 2 X80-CASH20 rows and the 2 assumption "
        "rows answer the true-cash question (docs/methodology/true-cash-all-cores.md)"
    )


def test_decision_mostly_proxied_list_is_the_flagged_dotcom_rows():
    from qrl.decision_report import _window_section

    report = _report(_rows_of("A", "G"))
    report["proxied_threshold"] = 0.25
    for r in report["windows"]:
        r.update(loss=0.1, proxied_share={})
    assert "and G and G80-CASH20 are mostly proxied" in "\n".join(_window_section(report))


def test_decision_texts_unchanged_for_none_or_one_row():
    from qrl.decision_report import _header, _notes, _sleeve_note

    one = _rows_of("A")
    single = {k: one[0][k] for k in ("id", "label", "base", "cash_share", "real_yield")}
    for rows, sing in [([], None), (one, single)]:
        keyed = _report(rows, sing)
        bare = {k: v for k, v in keyed.items() if k != "cash_assumptions"}
        for fn in (_header, _notes, _sleeve_note):
            assert fn(keyed) == fn(bare)
    text = "\n".join(_header(_report(one, single)) + _notes(_report(one, single)))
    assert "- A80-TCASH20 (l) is an assumption row, not a fund:" in text
    switching = [p["id"] for p in _portfolios() if len(p["states"]) > 1]
    assert switching  # the fixture must exercise the note
    assert f"- Switching portfolios ({_join(switching)}) are shown" in text
    assert "already holds" not in text


def test_longrun_sleeve_and_assumption_notes_for_several_rows():
    from qrl.longrun_report import _assumption_note, _sleeve_note

    names = ["A", "A80-CASH20", "A80-IEF20", "IEF", "CASH", *[r["id"] for r in _rows_of("A", "G")]]
    report = {
        "rows": [{"portfolio": n} for n in names],
        "cash_assumptions": [
            {"id": r["id"], "base": r["base"], "share": 0.2, "pair": r["pair"]}
            for r in _rows_of("A", "G")
        ],
        "cash_assumption_id": None,
        "cash_real_yield": 0.01,
        "cost_bps": 5.0,
    }
    assert _sleeve_note(report) == [
        "- 7 rows per withdrawal rate, including the CASH +1% real (assumption) row, 2 "
        "assumption rows (A80-TCASH20 to G80-TCASH20) and 1 by-product rows (IEF); only the "
        "2 A80 rows answer the defensive-sleeve question (docs/methodology/defensive-sleeve.md);"
        " the 2 X80-CASH20 rows and the 2 assumption rows answer the true-cash question "
        "(docs/methodology/true-cash-all-cores.md)"
    ]
    (note,) = _assumption_note(report)
    assert "(A80-TCASH20 with A80-CASH20, G80-TCASH20 with G80-CASH20)" in note
    assert note.startswith("- A80-TCASH20 to G80-TCASH20: assumptions, not history.")


def test_longrun_texts_unchanged_for_one_row_or_none():
    from qrl.longrun_report import _assumption_note, _sleeve_note

    names = ["A80-CASH20", "A80-IEF20", "CASH", "A80-TCASH20"]
    base = {
        "rows": [{"portfolio": n} for n in names],
        "cash_assumption_id": "A80-TCASH20",
        "cash_assumption_base": "A",
        "cash_assumption_share": 0.2,
        "cash_real_yield": 0.01,
        "cost_bps": 5.0,
    }
    listed = {
        **base,
        "cash_assumptions": [{"id": "A80-TCASH20", "base": "A", "share": 0.2, "pair": None}],
    }
    for fn in (_sleeve_note, _assumption_note):
        assert fn(listed) == fn(base)
    assert _sleeve_note(base)[0].startswith(
        "- 4 rows per withdrawal rate, including the CASH +1% real (assumption) row, the "
        "A80-TCASH20 assumption row and 0 by-product rows ();"
    )
    assert "only the 2 A80 rows" in _sleeve_note(base)[0]
    assert _assumption_note(base)[0].startswith("- A80-TCASH20: an assumption, not history.")


def test_longrun_rows_ignore_data_after_the_research_end(seven):
    data, index = prices(), uneven_cpi()
    rng = np.random.default_rng(5)
    after = np.asarray(data["close"].index > END)
    poisoned = {
        k: v * np.where(after[:, None], rng.uniform(0.2, 5.0, v.shape), 1.0)
        for k, v in data.items()
    }
    poisoned_cpi = index * np.where(
        np.asarray(index.index > END), rng.uniform(0.2, 5.0, len(index)), 1.0
    )
    crit = criteria()
    clean = run_longrun(_lcfg(), seven, data, index, crit)
    assert run_longrun(_lcfg(), seven, poisoned, poisoned_cpi, crit) == clean
