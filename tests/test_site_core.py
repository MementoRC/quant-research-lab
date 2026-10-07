from pathlib import Path

from qrl.site_core import (
    DECISION_PATH,
    FRAGILITY_PATH,
    build_core_comparison,
    build_decision,
    build_fragility,
)

ROOT = Path(__file__).resolve().parents[1]

SAMPLE_FRAGILITY = """# Balance-sheet fragility screen (exploration only)

- as-of date: 2025-06-01
- membership month-end: 2025-05-31
- universe size: 3
- newest filing date seen: 2025-02-09
- config/fragility.yaml sha256: `abc`
- breach_to_fragile (N): 1

## Summary

| class | count |
| --- | --- |
| FRAGILE | 1 |
| WATCH | 0 |
| SOUND | 1 |

## Fragile and watch

| ticker | class | breached measures | fiscal year end |
| --- | --- | --- | --- |
| CCC | FRAGILE | coverage 1.2x < 2.0x | 2024-12-31 |

## All companies

| ticker | class |
| --- | --- |
| CCC | FRAGILE |
"""


def test_parses_committed_files():
    block = build_core_comparison(ROOT)
    assert block is not None
    assert block["sources"] == {
        "compare": "research/core_compare.md",
        "reveal": "research/core_reveal.md",
    }
    research = block["research"]
    assert [r["id"] for r in research] == list("ABCDEFG")
    assert research[0]["CAGR"] == "6.1%"
    assert research[0]["rule"].startswith("current:")

    reveal = block["reveal"]
    assert reveal["event_id"] == 1
    assert "VALIDATION-SEEN" in reveal["banner"]
    assert "covid_2020" in reveal["windows"]
    assert "inflation_2022" in reveal["windows"]
    assert reveal["cut_date"] == "2022-10-31"
    assert len(reveal["cells"]) == 14
    assert {c["id"] for c in reveal["cells"]} == {"E", "F", "G"}
    assert len(reveal["breaches"]) == 3
    assert [b["id"] for b in reveal["breaches"]] == ["E", "F", "G"]


def test_missing_files_are_omitted(tmp_path):
    assert build_core_comparison(tmp_path) is None


def test_only_compare_present(tmp_path):
    (tmp_path / "research").mkdir()
    src = (ROOT / "research" / "core_compare.md").read_text()
    (tmp_path / "research" / "core_compare.md").write_text(src)
    block = build_core_comparison(tmp_path)
    assert block is not None
    assert "reveal" not in block
    assert len(block["research"]) == 7


def test_fragility_absent_returns_none(tmp_path):
    assert build_fragility(tmp_path) is None


def test_fragility_parses_sample(tmp_path):
    (tmp_path / "research").mkdir()
    (tmp_path / FRAGILITY_PATH).write_text(SAMPLE_FRAGILITY)
    block = build_fragility(tmp_path)
    assert block is not None
    assert FRAGILITY_PATH == "research/fragility.md"
    assert block["source"] == FRAGILITY_PATH
    assert block["header"]["as-of date"] == "2025-06-01"
    assert block["header"]["universe size"] == "3"
    assert block["summary"] == [
        {"class": "FRAGILE", "count": "1"},
        {"class": "WATCH", "count": "0"},
        {"class": "SOUND", "count": "1"},
    ]
    assert block["flagged"] == [
        {
            "ticker": "CCC",
            "class": "FRAGILE",
            "breached measures": "coverage 1.2x < 2.0x",
            "fiscal year end": "2024-12-31",
        }
    ]


def test_fragility_parses_rendered_report(tmp_path):
    import pandas as pd

    from qrl import fragility as fr

    cfg = fr.load_fragility_config(ROOT / "config" / "fragility.yaml")[0]
    report = fr.build_report(
        [],
        as_of=pd.Timestamp("2025-06-01"),
        month_end=pd.Timestamp("2025-05-31"),
        facts=pd.DataFrame(columns=["filed"]),
        cfg=cfg,
        config_sha256="a" * 64,
        universe_sha256="b" * 64,
    )
    (tmp_path / "research").mkdir()
    (tmp_path / FRAGILITY_PATH).write_text(fr.render_markdown(report))
    block = build_fragility(tmp_path)
    assert block is not None
    assert block["flagged"] == []
    assert block["header"]["config/fragility.yaml sha256"] == "a" * 64
    assert [r["class"] for r in block["summary"]] == [
        "FRAGILE",
        "WATCH",
        "SOUND",
        "INSUFFICIENT DATA",
        "NOT APPLICABLE",
    ]


SAMPLE_DECISION = """# Title

Intro line.

- data: up to 2018-12-31
- hash: `abc`

## Notes

- first note

## Scenarios

| name | loss |
|---|---|
| s1 | 5% |

Between the tables.

| id | value |
|---|---|
| a | 1 |
| b | 2 |

## Withdrawals

Intro.

### Rate 2%

| year | value |
|---|---|
| 1 | 100 |
"""


def test_decision_absent_returns_none(tmp_path):
    assert build_decision(tmp_path) is None


def test_decision_parses_sample(tmp_path):
    (tmp_path / "research").mkdir()
    (tmp_path / DECISION_PATH).write_text(SAMPLE_DECISION)
    block = build_decision(tmp_path)
    assert block is not None
    assert block["source"] == "research/decision.md"
    assert block["header"] == {"data": "up to 2018-12-31", "hash": "abc"}
    notes, scen, wd = block["sections"]
    assert notes["bullets"] == ["first note"]
    assert notes["tables"] == []
    assert scen["paragraphs"] == ["Between the tables."]
    assert scen["tables"] == [
        {"title": None, "columns": ["name", "loss"], "rows": [["s1", "5%"]]},
        {"title": None, "columns": ["id", "value"], "rows": [["a", "1"], ["b", "2"]]},
    ]
    assert wd["paragraphs"] == ["Intro."]
    assert wd["tables"] == [
        {"title": "Rate 2%", "columns": ["year", "value"], "rows": [["1", "100"]]}
    ]


def test_decision_parses_committed_report():
    block = build_decision(ROOT)
    assert block is not None
    sections = {s["title"].split(" (")[0]: s for s in block["sections"]}
    assert list(sections) == [
        "Notes",
        "Portfolios",
        "Historical windows",
        "Judgement-based scenarios",
        "Withdrawals",
        "Year-one scenario hit",
    ]
    assert sections["Portfolios"]["tables"][0]["columns"][0] == "id"
    withdrawals = sections["Withdrawals"]["tables"]
    assert len(withdrawals) == 4
    assert all(t["title"].startswith("Withdrawal rate ") for t in withdrawals)
    assert len(sections["Year-one scenario hit"]["tables"]) == 3
    assert len(sections["Judgement-based scenarios"]["tables"]) == 2
