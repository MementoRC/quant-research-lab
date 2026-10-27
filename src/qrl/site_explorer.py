"""The income explorer block: a lookup over the withdrawal-rules and
staged-entry reports for the dashboard's what-if panel.

Spec: docs/methodology/income-explorer.md. Pure: it takes the blocks that
`site_core.build_withdrawal_rules` and `build_staged_entry` return and
computes nothing new except the rule-minus-fixed differences.
"""

from __future__ import annotations

import itertools
import re
from decimal import ROUND_HALF_EVEN, Decimal

_PCT = re.compile(r"-?\d+(\.\d+)?%")


def difference(rule_cell: str, fixed_cell: str) -> str:
    """`rule - fixed` in signed percentage points, or "" unless both are single percentages."""
    if not (_PCT.fullmatch(rule_cell) and _PCT.fullmatch(fixed_cell)):
        return ""
    d = (Decimal(rule_cell[:-1]) - Decimal(fixed_cell[:-1])).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_EVEN
    )
    if d == 0:
        d = Decimal("0.0")  # drop the sign of a negative zero
    return f"{d:+.1f} pp"


PORTFOLIOS = ["A", "B", "C", "D", "E", "F", "G"]
RULE_PORTFOLIOS = [*PORTFOLIOS, "CASH"]
RATES = ["2%", "3.3%", "4%", "5%"]
VIEWS = ("historical", "long_run")

BASELINE_RULE = "fixed"
RULES = ["skip_raise_after_loss", "guardrails", "pct_of_balance", "floor_ceiling"]
RULE_KEYS = ["portfolio", "rule"]
RULE_SECTIONS = {
    "historical": "Historical view: start years 2005 to 2014, each to 2018-12-31",
    "long_run": "Long-run view: 30-year resampled paths",
}
# Report table title -> normalised rate.
RULE_TABLES = {
    "Withdrawal rate 2.0% per year": "2%",
    "Withdrawal rate 3.3% per year": "3.3%",
    "Withdrawal rate 4.0% per year": "4%",
    "Withdrawal rate 5.0% per year": "5%",
}

BASELINE_ENTRY = "lump sum"
ENTRIES = ["6 months", "12 months", "24 months"]
VARIANTS = ["SHY", "CPI+1%"]
ENTRY_KEYS = ["Portfolio", "Entry"]
ENTRY_SECTIONS = {"historical": "Historical starts", "long_run": "Long run"}
ENTRY_TABLES = {f"Withdrawal rate {r}": r for r in RATES}

_DATA_END = re.compile(r"up to (\d{4}-\d{2}-\d{2})")
_PORTFOLIO_ITEM = re.compile(r"(\S+) \((.*)\)")


def _data_end(block: dict) -> str:
    m = _DATA_END.search(block["header"].get("data", ""))
    if not m:
        raise ValueError(f"{block['source']}: no 'up to YYYY-MM-DD' in the data bullet")
    return m.group(1)


def _portfolios(block: dict, expected: list[str]) -> dict[str, str]:
    out = {}
    for item in block["header"].get("portfolios", "").split("; "):
        m = _PORTFOLIO_ITEM.fullmatch(item.strip())
        if not m:
            raise ValueError(f"{block['source']}: unreadable portfolio item {item!r}")
        out[m.group(1)] = m.group(2)
    if list(out) != expected:
        raise ValueError(f"{block['source']}: portfolios {list(out)}, expected {expected}")
    return out


def _tables_by_rate(block: dict, section_title: str, titles: dict[str, str]) -> dict[str, dict]:
    found = [s for s in block["sections"] if s["title"] == section_title]
    if len(found) != 1:
        raise ValueError(f"{block['source']}: expected one section {section_title!r}, found {len(found)}")
    out: dict[str, dict] = {}
    for table in found[0]["tables"]:
        rate = titles.get(table["title"])
        if rate is None:
            raise ValueError(f"{block['source']}: unexpected table {table['title']!r} in {section_title!r}")
        if rate in out:
            raise ValueError(f"{block['source']}: duplicate table {table['title']!r} in {section_title!r}")
        out[rate] = table
    missing = [r for r in RATES if r not in out]
    if missing:
        raise ValueError(f"{block['source']}: {section_title!r} lacks rates {missing}")
    return out


def _value_columns(by_rate: dict[str, dict], keys: list[str], where: str) -> list[str]:
    columns = by_rate[RATES[0]]["columns"]
    for rate in RATES:
        cols = by_rate[rate]["columns"]
        if cols[:2] != keys:
            raise ValueError(f"{where} {rate}: key columns {cols[:2]}, expected {keys}")
        if cols != columns:
            raise ValueError(f"{where} {rate}: columns differ from the {RATES[0]} table")
    return columns[2:]


def _cells(by_rate: dict[str, dict], n_values: int, expected: set, where: str) -> dict:
    """{(portfolio, rate, label): value cells}; every expected key exactly once, nothing else."""
    out: dict[tuple, list[str]] = {}
    for rate in RATES:
        for row in by_rate[rate]["rows"]:
            if len(row) != n_values + 2:
                raise ValueError(f"{where} {rate}: row {row[:2]} has {len(row)} cells, expected {n_values + 2}")
            key = (row[0], rate, row[1])
            if key in out:
                raise ValueError(f"{where}: duplicate row {key}")
            out[key] = row[2:]
    if out.keys() != expected:
        missing = sorted(expected - out.keys())
        extra = sorted(out.keys() - expected)
        raise ValueError(f"{where}: missing {missing[:5]}, unexpected {extra[:5]}")
    return out


def _rule_part(block: dict) -> dict:
    expected = set(itertools.product(RULE_PORTFOLIOS, RATES, [BASELINE_RULE, *RULES]))
    columns: dict[str, list[str]] = {}
    rows: dict[str, dict] = {}
    diff: dict[str, dict] = {}
    for view in VIEWS:
        where = f"{block['source']} {view}"
        by_rate = _tables_by_rate(block, RULE_SECTIONS[view], RULE_TABLES)
        columns[view] = _value_columns(by_rate, RULE_KEYS, where)
        cells = _cells(by_rate, len(columns[view]), expected, where)
        for (p, rate, rule), row in cells.items():
            key = f"{p}|{rate}|{rule}"
            fixed = cells[(p, rate, BASELINE_RULE)]
            rows.setdefault(key, {})[view] = row
            diff.setdefault(key, {})[view] = [difference(r, f) for r, f in zip(row, fixed, strict=True)]
    return {
        "portfolios": RULE_PORTFOLIOS,
        "rules": RULES,
        "baseline": BASELINE_RULE,
        "columns": columns,
        "rows": rows,
        "diff": diff,
    }


def _strip_variants(columns: list[str], where: str) -> list[str]:
    """Value columns without their "SHY: " / "CPI+1%: " prefix; both groups must match."""
    groups = {v: [c.removeprefix(f"{v}: ") for c in columns if c.startswith(f"{v}: ")] for v in VARIANTS}
    first = groups[VARIANTS[0]]
    rebuilt = [f"{v}: {c}" for v in VARIANTS for c in groups[v]]
    if rebuilt != columns or any(groups[v] != first for v in VARIANTS):
        raise ValueError(f"{where}: cash-variant column groups do not match: {columns}")
    return first


def _entry_part(block: dict) -> dict:
    expected = set(itertools.product(PORTFOLIOS, RATES, [BASELINE_ENTRY, *ENTRIES]))
    columns: dict[str, list[str]] = {}
    rows: dict[str, dict] = {}
    for view in VIEWS:
        where = f"{block['source']} {view}"
        by_rate = _tables_by_rate(block, ENTRY_SECTIONS[view], ENTRY_TABLES)
        raw = _value_columns(by_rate, ENTRY_KEYS, where)
        columns[view] = _strip_variants(raw, where)
        n = len(columns[view])
        for (p, rate, entry), row in _cells(by_rate, len(raw), expected, where).items():
            for i, variant in enumerate(VARIANTS):
                rows.setdefault(f"{p}|{rate}|{entry}|{variant}", {})[view] = row[i * n : (i + 1) * n]
    return {
        "portfolios": PORTFOLIOS,
        "variants": VARIANTS,
        "entries": ENTRIES,
        "baseline": BASELINE_ENTRY,
        "columns": columns,
        "rows": rows,
    }


def build_income_explorer(withdrawal: dict | None, staged: dict | None) -> dict | None:
    """The `income_explorer` block, or None if either report is absent.

    Raises ValueError on any unexpected title, column, cutoff or combination.
    """
    if withdrawal is None or staged is None:
        return None
    data_end = _data_end(withdrawal)
    if _data_end(staged) != data_end:
        raise ValueError(f"data cutoffs differ: {data_end} vs {_data_end(staged)}")
    rule_portfolios = _portfolios(withdrawal, RULE_PORTFOLIOS)
    entry_portfolios = _portfolios(staged, PORTFOLIOS)
    differing = [p for p in PORTFOLIOS if rule_portfolios[p] != entry_portfolios[p]]
    if differing:
        raise ValueError(f"portfolio descriptions differ between the reports: {differing}")
    return {
        "sources": [withdrawal["source"], staged["source"]],
        "data_end": data_end,
        "portfolios": rule_portfolios,
        "rates": RATES,
        "rule": _rule_part(withdrawal),
        "entry": _entry_part(staged),
    }
