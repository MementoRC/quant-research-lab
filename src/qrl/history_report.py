"""Markdown for the history-grounded scenarios (spec:
docs/methodology/history-scenarios.md, "Report"). Renders a `HistoryReport`;
no IO. Rows follow config order and are never sorted by result."""

from __future__ import annotations

import math

import pandas as pd

from .decision_report import _pct
from .history import (
    DAGGER,
    DOUBLE_DAGGER,
    NOT_RECOVERED,
    Cell,
    HistoryReport,
    Summary,
    income_key,
    summarize,
)


def _escape(text: str) -> str:
    """A pipe inside a markdown table cell would split it."""
    return text.replace("|", "\\|")


def _line(cells: list[str]) -> str:
    return "| " + " | ".join(_escape(c) for c in cells) + " |"


def _table(cols: list[str], rows: list[list[str]]) -> list[str]:
    return [_line(cols), "|" + "---|" * len(cols), *(_line(r) for r in rows), ""]


def _day(ts: pd.Timestamp) -> str:
    return f"{ts:%Y-%m-%d}"


def _value(value: float, kind: str) -> str:
    if math.isinf(value):
        return NOT_RECOVERED
    if kind == "months":
        return f"{value:g} months"
    if kind == "balance" and value == 0.0:
        return "depleted"
    return _pct(value)


def _cell_text(cell: Cell, kind: str) -> str:
    if cell.value is None or math.isinf(cell.value) or (cell.note and cell.value == 0.0):
        body = cell.note
    else:
        body = _value(cell.value, kind)
    return f"{body} {cell.marks}".strip()


def _summary_texts(summary: Summary, kind: str) -> tuple[str, str]:
    if summary.count == 0 or summary.median is None or summary.worst is None:
        none = f"n/a (0 of {summary.total} usable)"
        return none, none
    median = f"{_value(summary.median, kind)} (median of {summary.count})"
    worst = f"{_value(summary.worst, kind)} (worst of {summary.count}: peak {summary.worst_label})"
    return median, worst


def _header(report: HistoryReport) -> list[str]:
    n = len(report.portfolios)
    prior = report.candidate_count
    return [
        f"# History-grounded scenarios: every large fall since {report.episode_start.year}",
        "",
        f"- data cutoff: {_day(report.data_end)} (the end of the research period); "
        "validation and holdout data are never read",
        f"- episodes: a fall of {_pct(report.threshold)} or more from an all-time high of the "
        "S&P 500 price index (without dividends), peaks on or after "
        f"{_day(report.episode_start)}; the threshold and start date were fixed in the config "
        "before any result",
        *(f"- {name} sha256: `{digest}`" for name, digest in report.config_hashes.items()),
        *(f"- raw {name} sha256: `{digest}`" for name, digest in report.raw_hashes.items()),
        f"- portfolios compared: {n}",
        f"- multiple comparisons: {prior} in the core comparison, {n} here (A-G again plus "
        f"{n - prior} new); the more portfolios compared, the likelier the best-looking one "
        "is luck",
        "",
    ]


def _episodes(report: HistoryReport) -> list[str]:
    rows = [
        [
            _day(ep.peak),
            _day(ep.trough),
            _day(ep.recovery) if ep.recovery is not None else NOT_RECOVERED,
            _pct(ep.depth),
            "-" if ep.months is None else f"{ep.months} months",
            _day(ep.window_end),
        ]
        for ep in report.episodes
    ]
    cols = [
        "peak",
        "trough",
        "recovery",
        "S&P 500 depth",
        "length (peak to recovery)",
        "measure window ends",
    ]
    return ["## Episodes", "", *_table(cols, rows)]


def _checks(report: HistoryReport) -> list[str]:
    rows = [
        [c.label, c.frequency, f"{c.start} to {c.end}", str(c.n), f"{c.correlation:.4f}"]
        for c in report.checks
    ]
    cols = [
        "check (stand-in against the next series)",
        "frequency",
        "overlap",
        "returns",
        "correlation",
    ]
    return ["## Stand-in checks", "", *_table(cols, rows)]


def _labels(report: HistoryReport) -> list[str]:
    return [_day(ep.peak) for ep in report.episodes]


def _pairs(report: HistoryReport, pid: str, key: str) -> list[tuple[str, Cell]]:
    return list(zip(_labels(report), (c[key] for c in report.cells[pid]), strict=True))


def _falls(report: HistoryReport) -> list[str]:
    rows = []
    for pid, _ in report.portfolios:
        loss = summarize(_pairs(report, pid, "loss"), higher_is_worse=True)
        rec = summarize(_pairs(report, pid, "recover"), higher_is_worse=True)
        loss_median, loss_worst = _summary_texts(loss, "pct")
        rec_median, rec_worst = _summary_texts(rec, "months")
        rows.append([pid, loss_median, loss_worst, rec_median, rec_worst])
    cols = [
        "portfolio",
        "median worst loss",
        "deepest loss",
        "median months to recover",
        "longest recovery",
    ]
    return ["## Falls summary", "", *_table(cols, rows)]


def _income(report: HistoryReport) -> list[str]:
    out = ["## Income summary", ""]
    for rate in report.rates:
        out += [f"### Withdrawal {_pct(rate)} a year (real balance, % of the start)", ""]
        cols = ["portfolio"]
        for years in report.income_years:
            cols += [f"{years}-year median", f"{years}-year worst"]
        rows = []
        for pid, _ in report.portfolios:
            row = [pid]
            for years in report.income_years:
                s = summarize(_pairs(report, pid, income_key(rate, years)), higher_is_worse=False)
                row += list(_summary_texts(s, "balance"))
            rows.append(row)
        out += _table(cols, rows)
    return out


def _detail_table(report: HistoryReport, key: str, kind: str) -> list[str]:
    cols = ["portfolio", *_labels(report)]
    rows = [
        [pid, *(_cell_text(c[key], kind) for c in report.cells[pid])]
        for pid, _ in report.portfolios
    ]
    return _table(cols, rows)


def _detail(report: HistoryReport) -> list[str]:
    out = ["## Per-episode detail", "", "Columns are episodes, named by their peak date.", ""]
    out += ["### Worst loss in the measure window", "", *_detail_table(report, "loss", "pct")]
    out += ["### Months from the peak to recover", "", *_detail_table(report, "recover", "months")]
    longest = max(report.income_years)
    for rate in report.rates:
        out += [
            f"### Real balance {longest} years after the peak, withdrawing {_pct(rate)} a year",
            "",
            *_detail_table(report, income_key(rate, longest), "balance"),
        ]
    return out


def _legend(report: HistoryReport) -> list[str]:
    starts = ", ".join(f"{pid} {_day(report.starts[pid])}" for pid, _ in report.portfolios)
    return [
        "## Labels",
        "",
        f"- {DAGGER} the portfolio can hold a fund (either branch of a switching rule, every "
        "part of a blend) whose prices are stand-in data on some day of the cell's window.",
        f"- {DOUBLE_DAGGER} the portfolio can hold GLD and the window includes days before the "
        "first gold futures close, where gold is the interpolated World Bank monthly average.",
        "- A cell can carry both. Summary cells mix marked and unmarked episodes; see the "
        "per-episode tables.",
        "- no signal yet: the peak is before the portfolio's first return day (a switching "
        f"rule needs 200 days of history). First return days: {starts}.",
        "- n/a (data ends): the horizon ends after the data does. The 5-year and 10-year "
        "columns therefore have different counts.",
        "",
    ]


def _caveats() -> list[str]:
    return [
        "## Caveats",
        "",
        "- There are few episodes (about 10), so a median is a rough guide and every "
        "episode is shown on its own row.",
        "- Stand-ins are not the funds: before a fund existed, an index, a yield-based bond "
        "proxy or a gold price stands in for it. The stand-in checks above show how closely "
        "each tracks the fund where they overlap.",
        "- Gold before 2000 is a World Bank monthly average placed on month ends and "
        "interpolated daily, which makes it smoother than gold really was.",
        "- RSP is approximated by the S&P 500 (total return) before it existed; it has no check.",
        "- Every portfolio uses daily rebalancing to its target weights at the engine's "
        "normal cost.",
        "- Withdrawals are nominal amounts raised by CPI each January; balances are shown "
        "in real terms.",
        "- This report selects nothing and recommends nothing.",
        "",
    ]


def render_markdown(report: HistoryReport) -> str:
    lines = [
        *_header(report),
        *_episodes(report),
        *_checks(report),
        *_falls(report),
        *_income(report),
        *_detail(report),
        *_legend(report),
        *_caveats(),
    ]
    return "\n".join(lines)
