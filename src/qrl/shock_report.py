"""Markdown for the what-if shock report (spec: docs/methodology/whatif-shock.md).
A pure renderer of `qrl.shock.run_shock`'s data: deterministic (no timestamp),
percentages only (no currency amount). Each value cell shows the shocked figure
and, in brackets, the decision report's own (no shock).
"""

from __future__ import annotations

from pathlib import Path

from .decision_report import below_peak, pct, signed
from .shock import GROUPS
from .whatif import MIX_CASH_ID, MIX_ID, Shares, split_shares

SUMMARY_IDS = (MIX_ID, MIX_CASH_ID, "A", "CASH")


def _listing(shares: Shares) -> str:
    return ", ".join(f"{name} {share * 100:.4g}%" for name, share in shares)


def _mix_lines(given: Shares | None) -> list[str]:
    if not given:
        return []
    noncash, tcash = split_shares(given)
    lines = [f"- mix as given: {_listing(given)}"]
    if noncash:
        lines.append(f"- {MIX_ID} (the non-cash part, renormalised to 100%): {_listing(noncash)}")
    if tcash > 0:
        base = MIX_ID if noncash else "CASH"
        lines.append(f"- {MIX_CASH_ID}: {base} plus {tcash * 100:.4g}% true cash")
    return lines


def _shock_table(report: dict) -> list[str]:
    keys = (*GROUPS, "inflation")
    lines = ["| shock year | " + " | ".join(keys) + " |", "|---|" + "---|" * len(keys)]
    for k, year in enumerate(report["years"], 1):
        lines.append(f"| {k} | " + " | ".join(pct(year[key]) for key in keys) + " |")
    return lines


def _header(report: dict, given: Shares | None) -> list[str]:
    n = report["n"]
    return [
        f"# What-if shock: {report['name']}",
        "",
        "A decision aid. This shock came from a file, not from `config/decision.yaml`: it puts "
        f"{n} made-up year(s) in front of each start year's real history and runs the decision "
        "report's own withdrawal code on the result. It selects nothing and recommends nothing. "
        "Spec: docs/methodology/whatif-shock.md.",
        "",
        f"- shock: `{report['name']}`, N = {n} year(s), read from a file (unchanged)",
        *_mix_lines(given),
        f"- data: up to {report['data_end']} only (validation and holdout stay sealed)",
        f"- decision.yaml sha256: `{report['decision_sha256']}` (read unchanged)",
        f"- core_candidates.yaml sha256: `{report['candidates_sha256']}` (read unchanged)",
        f"- stress.yaml sha256: `{report['stress_sha256']}` (read unchanged)",
        f"- every shocked path is {n} year(s) longer than the report's, with {n} more year(s) "
        "of withdrawals",
        "",
        *_shock_table(report),
        "",
    ]


def _tcash_note(report: dict) -> list[str]:
    yields = report["real_yields"]
    if not yields:
        return []
    return [
        "- True cash (the TCASH rows) earns `short_bonds` in the stretch and CPI plus "
        f"{' / '.join(signed(y) for y in yields)} real after it (each row's own yield), as in "
        "the report."
    ]


def _assumptions(report: dict) -> list[str]:
    return [
        "## Assumptions",
        "",
        "- QQQ is treated as SPY (both `stocks`), so core A (QQQ risk-on) looks less exposed "
        "than it is to a tech-led fall.",
        "- IEF earns the midpoint of the `long_bonds` and `short_bonds` returns of each year: a "
        "rough duration guess, not data.",
        "- In the stretch each state holds its fixed weights, rebalanced daily, with no costs. "
        "Because of the daily rebalancing a year does not compound to the weighted sum of the "
        "yearly returns.",
        "- Switching portfolios (and every blend, mix or TCASH row over one) run once per state "
        "in the stretch; after it the real part is the live rule, the same for every state. Per "
        "row and rate the worse state (the lower real ending value at its worst start year; a "
        "tie goes to the greater name) is headlined and supplies every column; every state is "
        "listed below each table.",
        *_tcash_note(report),
        "- The stretch dates are made up and come before each real start year, so each start "
        "year has its own stretch and its own CPI splice.",
        "- The stretch's CPI is built from your inflation; the real CPI is rescaled to join it "
        "with no jump (only its ratios are used, so nothing after the join changes).",
        f"- The first real day pays the report's purchase cost ({report['cost_bps']:g} bps per "
        "unit of turnover, criteria.yaml cost_bps); the join adds no other cost.",
        "- Every portfolio is 100% of capital, rebalanced daily to its target weights, so blends "
        "look smoother than practice; the engine never charges for drift.",
        "- CASH here is SHY, not true cash.",
        "",
    ]


def _intro(report: dict) -> list[str]:
    n, years = report["n"], report["start_years"]
    first = min(years)
    return [
        "## Withdrawals",
        "",
        "A shocked path for start year Y begins on the first weekday on or after 2 January of "
        f"Y-{n}, runs through the stretch and then the real history from the first trading day "
        f"of January Y to {report['data_end']}; start years {first}-{max(years)} are shown as Y. "
        "Values are percentages of the starting value. Withdrawals start at the stretch start "
        "at the annual rate / 12 of the starting value, taken on the first trading day of each "
        "month, and change each January by the year-over-year change of the CPI usable on "
        "1 January (in the stretch, your inflation). Each cell shows the shocked figure, then "
        "the report's own in brackets (no shock). Lowest value, max drawdown, longest below a "
        f"prior peak and depleted are for the {first} path. Worst-start cells show the year and "
        f"the horizon in years (shocked horizons include the {n} stretch year(s)); the equal "
        f"horizon is the report's plus {n} year(s).",
        "",
    ]


def _worst(row: dict, n: int) -> str:
    year = row["worst_year"]
    return f"{year + n}, {row['horizons'][year]} y ({pct(row['worst_end_real'])})"


def _equal(row: dict, n: int) -> str:
    return f"{row['worst5_year'] + n}, {row['horizon_years']} y ({pct(row['worst5_end_real'])})"


def _cells(shocked: dict, base: dict, n: int) -> list[str]:
    s, b = shocked["first"], base["first"]
    pairs = [
        (pct(s["end_real"]), pct(b["end_real"])),
        (pct(s["lowest"]), pct(b["lowest"])),
        (pct(s["max_drawdown"]), pct(b["max_drawdown"])),
        (below_peak(s), below_peak(b)),  # the report's own text (public alias)
        (s["depleted"] or "no", b["depleted"] or "no"),
        (_worst(shocked, n), _worst(base, 0)),
        (_equal(shocked, n), _equal(base, 0)),
    ]
    return [f"{x} (no shock: {y})" for x, y in pairs]


def _label(row: dict) -> str:
    return f"{row['portfolio']} ({row['state']})" if row["state"] else row["portfolio"]


def _state_table(rows: list[dict], report: dict) -> list[str]:
    switching = [r for r in rows if r["state"]]
    if not switching:
        return []
    n, first = report["n"], min(report["start_years"])
    lines = [
        "Every state of the switching rows (shocked):",
        "",
        f"| portfolio | state | real ending value (start {first}) | worst start year to "
        f"{report['data_end']} (real ending value) | headlined |",
        "|---|---|---|---|---|",
    ]
    for row in switching:
        for state, s in row["states"].items():
            mark = "yes" if state == row["state"] else ""
            lines.append(
                f"| {row['portfolio']} | {state} | {pct(s['first']['end_real'])} | "
                f"{_worst(s, n)} | {mark} |"
            )
    return [*lines, ""]


def _rate_section(report: dict, rate: float) -> list[str]:
    first = min(report["start_years"])
    rows = [r for r in report["rows"] if r["rate"] == rate]
    lines = [
        f"### Withdrawal rate {pct(rate)} per year",
        "",
        f"| portfolio | real ending value (start {first}) | lowest value | max drawdown (from "
        f"start) | longest below a prior peak | depleted | worst start year to "
        f"{report['data_end']} (real ending value) | worst equal-horizon start (real value "
        "after the horizon) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        cells = _cells(row["shocked"], row["no_shock"], report["n"])
        lines.append(f"| {_label(row)} | " + " | ".join(cells) + " |")
    return [*lines, "", *_state_table(rows, report)]


def render_shock(report: dict, given: Shares | None) -> str:
    """Deterministic markdown of a `qrl.shock.run_shock` report; `given` is the
    parsed mix (None without `--mix`)."""
    tables = [line for rate in report["rates"] for line in _rate_section(report, rate)]
    return "\n".join([*_header(report, given), *_assumptions(report), *_intro(report), *tables])


def _figure(row: dict) -> str:
    state = f" ({row['state']})" if row["state"] else ""
    return (
        f"{pct(row['rate'])}: {pct(row['shocked']['first']['end_real'])}{state} "
        f"(no shock: {pct(row['no_shock']['first']['end_real'])})"
    )


def summary_lines(report: dict, path: Path) -> list[str]:
    """The terminal summary: the shock name and N, the path, and for each of
    MIX, MIX-TCASH, A and CASH present, the first start year's real ending value
    shocked (with the headlined state) and not shocked, at every rate."""
    first = min(report["start_years"])
    lines = [f"shock: {report['name']}, N = {report['n']} year(s)", f"wrote: {path}"]
    for pid in SUMMARY_IDS:
        rows = [r for r in report["rows"] if r["portfolio"] == pid]
        if rows:
            figures = "; ".join(_figure(r) for r in rows)
            lines.append(f"{pid}, real ending value (start {first}): {figures}")
    return lines
