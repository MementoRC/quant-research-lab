"""Tests for the income explorer block (docs/methodology/income-explorer.md)."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from qrl.site_core import build_staged_entry, build_withdrawal_rules
from qrl.site_explorer import (
    ENTRIES,
    ENTRY_SECTIONS,
    PORTFOLIOS,
    RATES,
    RULE_PORTFOLIOS,
    RULE_SECTIONS,
    RULES,
    build_income_explorer,
    difference,
)


@pytest.mark.parametrize(
    ("rule", "fixed", "expected"),
    [
        ("155.3%", "148.5%", "+6.8 pp"),
        ("1247.9%", "1400.0%", "-152.1 pp"),
        ("1557.3%", "1400.0%", "+157.3 pp"),
        ("0.0%", "0.7%", "-0.7 pp"),
        ("299.8%", "299.8%", "+0.0 pp"),
        ("1.2%", "1.24%", "+0.0 pp"),  # -0.04 rounds to zero: never "-0.0"
        ("-1.5%", "2%", "-3.5 pp"),
        ("0.0%", "-", ""),
        ("-", "-", ""),
        ("2014", "2013", ""),
        ("-3.3 (-10.1, +8.8)", "1.0%", ""),
        ("1.0% ", "1.0%", ""),  # must fully match
    ],
)
def test_difference(rule, fixed, expected):
    assert difference(rule, fixed) == expected


DATA = "up to 2018-12-31 only (validation and holdout stay sealed)"
W_RATE_TITLE = {"2%": "2.0%", "3.3%": "3.3%", "4%": "4.0%", "5%": "5.0%"}
W_COLUMNS = {
    "historical": [
        "portfolio",
        "rule",
        "2005: ran out",
        "worst start year",
        "2005: total real income",
    ],
    "long_run": ["portfolio", "rule", "ran out by year 30", "real value at year 30: typical"],
}
S_COLUMNS = {
    "historical": [
        "Portfolio",
        "Entry",
        "SHY: Above lump",
        "SHY: Worst start",
        "CPI+1%: Above lump",
        "CPI+1%: Worst start",
    ],
    "long_run": ["Portfolio", "Entry", "SHY: Depleted by year 30", "CPI+1%: Depleted by year 30"],
}


def _portfolio_bullet(ids):
    return "; ".join(f"{p} (about {p})" for p in ids)


def _section(title, tables=()):
    return {"title": title, "bullets": [], "paragraphs": [], "tables": list(tables)}


def _w_cells(view, rule):
    fixed = rule == "fixed"
    if view == "historical":
        return ["-" if fixed else "0.0%", "2014", "1400.0%" if fixed else "1557.3%"]
    return ["0.7%" if fixed else "0.0%", "299.8%"]


def _withdrawal_block():
    views = []
    for view in ("historical", "long_run"):
        tables = [
            {
                "title": f"Withdrawal rate {W_RATE_TITLE[r]} per year",
                "columns": list(W_COLUMNS[view]),
                "rows": [
                    [p, rule, *_w_cells(view, rule)]
                    for p in RULE_PORTFOLIOS
                    for rule in ["fixed", *RULES]
                ],
            }
            for r in RATES
        ]
        views.append(_section(RULE_SECTIONS[view], tables))
    return {
        "source": "research/withdrawal_rules.md",
        "header": {"data": DATA, "portfolios": _portfolio_bullet(RULE_PORTFOLIOS)},
        "sections": [_section("Rules"), *views],
    }


def _s_cells(view, entry):
    lump = entry == "lump sum"
    if view == "historical":
        return (
            ["—", "2005-01", "—", "2005-01"] if lump else ["40.0%", "2005-01", "41.0%", "2006-01"]
        )
    return ["0.7%", "0.6%"]


def _staged_block():
    views = []
    for view in ("historical", "long_run"):
        tables = [
            {
                "title": f"Withdrawal rate {r}",
                "columns": list(S_COLUMNS[view]),
                "rows": [
                    [p, entry, *_s_cells(view, entry)]
                    for p in PORTFOLIOS
                    for entry in ["lump sum", *ENTRIES]
                ],
            }
            for r in RATES
        ]
        views.append(_section(ENTRY_SECTIONS[view], tables))
    return {
        "source": "research/staged_entry.md",
        "header": {"data": DATA, "portfolios": _portfolio_bullet(PORTFOLIOS)},
        "sections": [_section("Notes"), *views],
    }


def test_none_when_either_block_is_missing():
    assert build_income_explorer(None, _staged_block()) is None
    assert build_income_explorer(_withdrawal_block(), None) is None


def test_top_level_shape():
    block = build_income_explorer(_withdrawal_block(), _staged_block())
    assert block["sources"] == ["research/withdrawal_rules.md", "research/staged_entry.md"]
    assert block["data_end"] == "2018-12-31"
    assert block["rates"] == ["2%", "3.3%", "4%", "5%"]
    assert list(block["portfolios"]) == [*"ABCDEFG", "CASH"]
    assert block["portfolios"]["CASH"] == "about CASH"


def test_rule_part():
    rule = build_income_explorer(_withdrawal_block(), _staged_block())["rule"]
    assert rule["portfolios"] == [*"ABCDEFG", "CASH"]
    assert rule["rules"] == [
        "skip_raise_after_loss",
        "guardrails",
        "pct_of_balance",
        "floor_ceiling",
    ]
    assert rule["baseline"] == "fixed"
    assert rule["columns"] == {
        "historical": ["2005: ran out", "worst start year", "2005: total real income"],
        "long_run": ["ran out by year 30", "real value at year 30: typical"],
    }
    assert len(rule["rows"]) == 8 * 4 * 5  # fixed rows included
    assert rule["rows"]["CASH|3.3%|fixed"] == {
        "historical": ["-", "2014", "1400.0%"],
        "long_run": ["0.7%", "299.8%"],
    }
    assert rule["diff"]["A|2%|guardrails"] == {
        "historical": ["", "", "+157.3 pp"],
        "long_run": ["-0.7 pp", "+0.0 pp"],
    }
    assert rule["diff"]["A|2%|fixed"]["historical"] == ["", "", "+0.0 pp"]
    assert rule["diff"].keys() == rule["rows"].keys()


def test_entry_part():
    entry = build_income_explorer(_withdrawal_block(), _staged_block())["entry"]
    assert entry["portfolios"] == list("ABCDEFG")
    assert entry["variants"] == ["SHY", "CPI+1%"]
    assert entry["entries"] == ["6 months", "12 months", "24 months"]
    assert entry["baseline"] == "lump sum"
    assert entry["columns"] == {
        "historical": ["Above lump", "Worst start"],
        "long_run": ["Depleted by year 30"],
    }
    assert len(entry["rows"]) == 7 * 4 * 4 * 2  # lump-sum rows included
    assert entry["rows"]["B|5%|12 months|SHY"] == {
        "historical": ["40.0%", "2005-01"],
        "long_run": ["0.7%"],
    }
    assert entry["rows"]["B|5%|12 months|CPI+1%"] == {
        "historical": ["41.0%", "2006-01"],
        "long_run": ["0.6%"],
    }
    assert entry["rows"]["G|2%|lump sum|CPI+1%"]["historical"] == ["—", "2005-01"]
    assert "diff" not in entry


def _view(block, title):
    return next(s for s in block["sections"] if s["title"] == title)


def _rename_rule_table(w, s):
    _view(w, RULE_SECTIONS["historical"])["tables"][0]["title"] = "Withdrawal rate 2.5% per year"


def _duplicate_rule_table(w, s):
    tables = _view(w, RULE_SECTIONS["long_run"])["tables"]
    tables[1]["title"] = tables[0]["title"]


def _rename_rule_section(w, s):
    _view(w, RULE_SECTIONS["historical"])["title"] = (
        "Historical view: start years 2005 to 2015, each to 2019-12-31"
    )


def _rename_entry_table(w, s):
    _view(s, ENTRY_SECTIONS["long_run"])["tables"][0]["title"] = "Withdrawal rate 4.0%"


def _drop_rule_row(w, s):
    _view(w, RULE_SECTIONS["historical"])["tables"][2]["rows"].pop(7)


def _duplicate_rule_row(w, s):
    rows = _view(w, RULE_SECTIONS["long_run"])["tables"][0]["rows"]
    rows.append(list(rows[0]))


def _extra_rule_row(w, s):
    _view(w, RULE_SECTIONS["historical"])["tables"][0]["rows"].append(
        ["A", "always_cut", "-", "2014", "1.0%"]
    )


def _drop_entry_row(w, s):
    _view(s, ENTRY_SECTIONS["historical"])["tables"][3]["rows"].pop()


def _duplicate_entry_row(w, s):
    rows = _view(s, ENTRY_SECTIONS["long_run"])["tables"][1]["rows"]
    rows.append(list(rows[5]))


def _short_row(w, s):
    _view(w, RULE_SECTIONS["historical"])["tables"][0]["rows"][0].pop()


def _rename_key_column(w, s):
    for t in _view(w, RULE_SECTIONS["long_run"])["tables"]:
        t["columns"][1] = "Rule"


def _columns_differ_between_rates(w, s):
    _view(w, RULE_SECTIONS["historical"])["tables"][3]["columns"][2] = "2006: ran out"


def _variant_groups_differ(w, s):
    for t in _view(s, ENTRY_SECTIONS["historical"])["tables"]:
        t["columns"][-1] = "CPI+1%: Best start"


def _unprefixed_column(w, s):
    for t in _view(s, ENTRY_SECTIONS["long_run"])["tables"]:
        t["columns"][2] = "Depleted by year 30"


def _cutoffs_differ(w, s):
    s["header"]["data"] = "up to 2019-12-31 only"


def _no_cutoff(w, s):
    w["header"]["data"] = "sealed"


def _descriptions_differ(w, s):
    s["header"]["portfolios"] = s["header"]["portfolios"].replace(
        "G (about G)", "G (something else)"
    )


def _missing_portfolio(w, s):
    w["header"]["portfolios"] = _portfolio_bullet(PORTFOLIOS)  # no CASH


@pytest.mark.parametrize(
    "mutate",
    [
        _rename_rule_table,
        _duplicate_rule_table,
        _rename_rule_section,
        _rename_entry_table,
        _drop_rule_row,
        _duplicate_rule_row,
        _extra_rule_row,
        _drop_entry_row,
        _duplicate_entry_row,
        _short_row,
        _rename_key_column,
        _columns_differ_between_rates,
        _variant_groups_differ,
        _unprefixed_column,
        _cutoffs_differ,
        _no_cutoff,
        _descriptions_differ,
        _missing_portfolio,
    ],
)
def test_bad_reports_raise(mutate):
    w, s = copy.deepcopy(_withdrawal_block()), copy.deepcopy(_staged_block())
    mutate(w, s)
    with pytest.raises(ValueError, match="."):
        build_income_explorer(w, s)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def committed():
    return build_income_explorer(build_withdrawal_rules(ROOT), build_staged_entry(ROOT))


def test_committed_reports_resolve_every_combination(committed):
    rule, entry = committed["rule"], committed["entry"]
    assert committed["data_end"] == "2018-12-31"
    assert len(rule["rows"]) == 160
    assert len(entry["rows"]) == 224
    assert len(rule["columns"]["historical"]) == 14
    assert len(rule["columns"]["long_run"]) == 12
    for view in ("historical", "long_run"):
        assert all(len(r[view]) == len(rule["columns"][view]) for r in rule["rows"].values())
        assert all(len(d[view]) == len(rule["columns"][view]) for d in rule["diff"].values())
        assert all(len(r[view]) == len(entry["columns"][view]) for r in entry["rows"].values())


def test_committed_columns(committed):
    assert committed["rule"]["columns"]["historical"][:2] == [
        "2005: ran out",
        "2005: real value at end",
    ]
    assert committed["rule"]["columns"]["historical"][5] == "worst start year"
    assert committed["entry"]["columns"] == {
        "historical": [
            "Above lump",
            "Gap at 4 y, pp: median (worst, best)",
            "Worst max drawdown",
            "Worst drawdown vs lump, pp",
            "Worst start",
            "Gap at data end, pp: median (worst, best)",
        ],
        "long_run": [
            "Depleted by year 30",
            "Median real value, year 30",
            "Median real value, year 5",
        ],
    }
    assert committed["portfolios"]["G"] == "static 25% each SPY/TLT/GLD/SHY"
    assert committed["portfolios"]["CASH"] == "100% SHY"


def test_committed_spot_checks(committed):
    rows, diff = committed["rule"]["rows"], committed["rule"]["diff"]
    # withdrawal_rules.md line 164
    assert rows["G|4%|guardrails"]["historical"] == [
        "-",
        "111.1%",
        "97.9%",
        "100.0%",
        "1460.0%",
        "2013",
        "-",
        "83.6%",
        "89.4%",
        "100.0%",
        "600.0%",
        "0.0%",
        "0.0%",
        "0.0%",
    ]
    # lines 42 and 44
    assert diff["A|2%|guardrails"]["historical"] == [
        "",
        "+6.8 pp",
        "+0.9 pp",
        "-19.0 pp",
        "-152.1 pp",
        "",
        "",
        "-0.2 pp",
        "+0.0 pp",
        "+0.0 pp",
        "+10.0 pp",
        "+9.5 pp",
        "+0.0 pp",
        "+0.0 pp",
    ]
    # lines 224 and 226
    assert rows["A|2%|guardrails"]["long_run"][0] == "0.0%"
    assert diff["A|2%|guardrails"]["long_run"][:3] == ["-0.7 pp", "-37.8 pp", "+19.8 pp"]
    entry = committed["entry"]["rows"]
    # staged_entry.md line 126
    assert entry["G|4%|12 months|SHY"]["historical"] == [
        "19.2%",
        "-3.3 (-10.1, +8.8)",
        "16.4%",
        "+0.6",
        "2012-01",
        "-3.7 (-11.3, +9.9)",
    ]
    assert entry["G|4%|12 months|CPI+1%"]["historical"] == [
        "19.2%",
        "-2.9 (-13.6, +8.7)",
        "16.4%",
        "+0.5",
        "2012-01",
        "-3.0 (-14.9, +9.6)",
    ]
    # line 168
    assert entry["A|2%|lump sum|SHY"]["long_run"] == ["0.7%", "299.8%", "118.4%"]
