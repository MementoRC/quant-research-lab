"""Tests for the income explorer block (docs/methodology/income-explorer.md)."""

from __future__ import annotations

import copy

import pytest

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
    "historical": ["portfolio", "rule", "2005: ran out", "worst start year", "2005: total real income"],
    "long_run": ["portfolio", "rule", "ran out by year 30", "real value at year 30: typical"],
}
S_COLUMNS = {
    "historical": [
        "Portfolio", "Entry",
        "SHY: Above lump", "SHY: Worst start",
        "CPI+1%: Above lump", "CPI+1%: Worst start",
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
        return ["—", "2005-01", "—", "2005-01"] if lump else ["40.0%", "2005-01", "41.0%", "2006-01"]
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
    assert rule["rules"] == ["skip_raise_after_loss", "guardrails", "pct_of_balance", "floor_ceiling"]
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
