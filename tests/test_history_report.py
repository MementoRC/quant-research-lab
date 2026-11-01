"""Tests for qrl.history_report (docs/methodology/history-scenarios.md, "Report")."""

from __future__ import annotations

import dataclasses
import math
import re

import pandas as pd

from qrl.history import (
    NA_DATA,
    NO_SIGNAL,
    NOT_RECOVERED,
    Cell,
    Episode,
    HistoryReport,
    income_key,
)
from qrl.history_data import CheckResult
from qrl.history_report import render_markdown

# the patterns of tests/test_docs_freshness.py
HASH_LINE = re.compile(
    r"^- (?:config/)?([\w.]+\.yaml) (?:config )?(?:sha256|hash): `([0-9a-f]{12,64})`"
)
LOOSE = re.compile(r"\b[\w.]+\.yaml\b.*\b(?:sha256|hash)\b.*`[0-9a-f]{12,64}`")
HEX = "a" * 64


def _episode(peak: str, months: int | None) -> Episode:
    p = pd.Timestamp(peak)
    return Episode(
        peak=p,
        trough=p + pd.Timedelta(days=200),
        recovery=None if months is None else p + pd.DateOffset(months=months),
        depth=0.3,
        months=months,
        window_end=p + pd.DateOffset(years=10),
    )


def _cells(loss: float, months: Cell, five: Cell, ten: Cell) -> dict[str, Cell]:
    return {
        "loss": Cell(loss, "", "†"),
        "recover": months,
        income_key(0.04, 5): five,
        income_key(0.04, 10): ten,
    }


def _report() -> HistoryReport:
    episodes = [_episode("1973-01-11", 69), _episode("2018-09-20", None)]
    a = [
        _cells(0.30, Cell(40.0), Cell(0.8), Cell(0.0, "depleted 2008-04")),
        _cells(0.20, Cell(math.inf, NOT_RECOVERED), Cell(None, NA_DATA), Cell(None, NA_DATA)),
    ]
    cash = [
        {k: Cell(None, NO_SIGNAL) for k in a[0]},
        _cells(0.01, Cell(0.0), Cell(None, NA_DATA), Cell(None, NA_DATA)),
    ]
    check = CheckResult("QQQ: ^IXIC against QQQ", "daily", "1999-03-11", "2018-12-31", 4900, 0.98)
    return HistoryReport(
        data_end=pd.Timestamp("2018-12-31"),
        threshold=0.15,
        episode_start=pd.Timestamp("1971-01-01"),
        horizon_years=10,
        rates=(0.04,),
        income_years=(5, 10),
        candidate_count=7,
        config_hashes={
            "config/history.yaml": HEX,
            "config/decision.yaml": "b" * 64,
            "config/core_candidates.yaml": "c" * 64,
        },
        raw_hashes={"^GSPC close": "d" * 64},
        portfolios=[("A", "QQQ/GLD 200d trend"), ("CASH", "100% SHY")],
        starts={"A": pd.Timestamp("1971-10-22"), "CASH": pd.Timestamp("1971-01-05")},
        episodes=episodes,
        checks=[check],
        cells={"A": a, "CASH": cash},
    )


def test_sections_come_in_spec_order():
    text = render_markdown(_report())
    headings = re.findall(r"^## (.+)$", text, flags=re.M)
    assert headings == [
        "Episodes",
        "Stand-in checks",
        "Falls summary",
        "Income summary",
        "Per-episode detail",
        "Labels",
        "Caveats",
    ]
    assert text.startswith("# History-grounded scenarios")


def test_config_hash_lines_match_the_docs_freshness_format():
    text = render_markdown(_report())
    lines = [ln for ln in text.splitlines() if LOOSE.search(ln)]
    assert len(lines) == 3
    for line in lines:
        assert HASH_LINE.match(line), line
    assert f"- config/history.yaml sha256: `{HEX}`" in text


def test_raw_hash_lines_are_not_mistaken_for_config_lines():
    text = render_markdown(_report())
    assert "- raw ^GSPC close sha256: `" + "d" * 64 + "`" in text
    assert not HASH_LINE.match("- raw ^GSPC close sha256: `" + "d" * 64 + "`")


def test_legend_caveats_and_the_no_recommendation_sentence():
    text = render_markdown(_report())
    assert "†" in text
    assert "‡" in text
    assert "selects nothing and recommends nothing" in text
    assert "few episodes" in text.lower()
    assert "smoother" in text  # interpolated monthly-average gold
    assert "RSP" in text
    assert "daily rebalancing" in text


def test_header_states_cutoff_threshold_and_comparison_count():
    text = render_markdown(_report())
    assert "2018-12-31" in text
    assert "15.0%" in text  # `_pct` prints one decimal
    assert "- portfolios compared: 2" in text
    assert "- multiple comparisons: 7 in the core comparison, 2 here" in text


def test_episode_table_shows_not_recovered_and_dash_length():
    text = render_markdown(_report())
    row = next(ln for ln in text.splitlines() if ln.startswith("| 2018-09-20"))
    assert NOT_RECOVERED in row
    assert "| - |" in row


def test_summaries_state_counts_and_skip_unusable_cells():
    text = render_markdown(_report())
    assert "median of 2" in text  # A, falls: two episodes
    assert "median of 1" in text  # CASH, falls: one usable episode
    assert NO_SIGNAL in text
    assert NA_DATA in text
    assert "depleted 2008-04" in text


def test_cells_carry_their_marks():
    text = render_markdown(_report())
    assert "30.0% †" in text


def test_cells_render_with_units():
    text = render_markdown(_report())
    row_a = next(ln for ln in text.splitlines() if ln.startswith("| A | 30.0%"))
    assert "30.0% †" in row_a
    assert any(ln.startswith("| A | 40 months |") for ln in text.splitlines())
    assert any(ln.startswith("| A | 80.0% (median of 1)") for ln in text.splitlines())


def test_the_double_dagger_sits_on_a_specific_cell():
    report = _report()
    marked = dict(report.cells["A"][0])
    marked["loss"] = dataclasses.replace(marked["loss"], marks="†‡")
    cells = {**report.cells, "A": [marked, report.cells["A"][1]]}
    text = render_markdown(dataclasses.replace(report, cells=cells))
    row = next(ln for ln in text.splitlines() if ln.startswith("| A | 30.0%"))
    assert "30.0% †‡" in row
    assert "‡" not in render_markdown(report).split("## Labels")[0]


def test_the_longest_income_horizon_heading_and_depleted_summary():
    text = render_markdown(_report())
    assert "### Real balance 10 years after the peak, withdrawing 4.0% a year" in text
    income = text.split("## Income summary")[1].split("## Per-episode detail")[0]
    a_row = next(ln for ln in income.splitlines() if ln.startswith("| A |"))
    assert "depleted (median of 1)" in a_row
    assert "depleted (worst of 1: peak 1973-01-11)" in a_row


def test_a_row_with_no_usable_cell_says_so():
    text = render_markdown(_report())
    income = text.split("## Income summary")[1].split("## Per-episode detail")[0]
    cash_row = next(ln for ln in income.splitlines() if ln.startswith("| CASH |"))
    assert "n/a (0 of 2 usable)" in cash_row


def test_a_pipe_in_a_label_or_note_does_not_split_the_table():
    report = _report()
    note = Cell(None, "n/a | odd")
    edited = [dict(report.cells["A"][0], recover=note), report.cells["A"][1]]
    text = render_markdown(
        dataclasses.replace(
            report,
            portfolios=[("A", "x"), ("CASH", "100% SHY")],
            cells={**report.cells, "A": edited},
        )
    )
    row = next(ln for ln in text.splitlines() if "odd" in ln and ln.startswith("| A |"))
    assert "n/a \\| odd" in row
    assert len(re.split(r"(?<!\\)\|", row)) == len(re.split(r"(?<!\\)\|", "| A | x | y |"))


def test_rendering_is_deterministic():
    report = _report()
    assert render_markdown(report) == render_markdown(report)


def test_rows_follow_config_order_not_results():
    text = render_markdown(_report())
    falls = text.split("## Falls summary")[1].split("## Income summary")[0]
    assert falls.index("| A |") < falls.index("| CASH |")
