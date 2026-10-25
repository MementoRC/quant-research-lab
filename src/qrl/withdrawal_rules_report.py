"""Markdown for the withdrawal-rules comparison (spec:
docs/methodology/withdrawal-rules.md, "Report layout" and "Header and
notes"). Renders the plain data of `qrl.decision_rules.run_withdrawal_rules`;
no IO. Percentages only; rows follow config order and are never sorted by
result."""

from __future__ import annotations

from .decision_report import _pct

_PATH_COLS = (
    "ran out",
    "real value at end",
    "lowest value",
    "lowest yearly real income",
    "total real income",
)
_LONG_COLS = (
    "ran out by year {h}",
    "real value at year {h}: typical",
    "real value at year {h}: bad case (worst 5%)",
    "lowest value: typical",
    "lowest value: bad case (worst 5%)",
    "lowest yearly real income: typical",
    "lowest yearly real income: bad case (worst 5%)",
    "total real income: typical",
    "total real income: bad case (worst 5%)",
)
_LONG_KEYS = (
    "depleted",
    "end_real_median",
    "end_real_p5",
    "lowest_median",
    "lowest_p5",
    "income_low_median",
    "income_low_p5",
    "income_total_median",
    "income_total_p5",
)


def _line(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _table(cols: list[str], rows: list[list[str]]) -> list[str]:
    return [_line(cols), "|" + "---|" * len(cols), *(_line(r) for r in rows), ""]


def _rule_text(rule: str, p: dict[str, float]) -> str:
    """Plain words for one rule with its configured parameters."""
    if rule == "fixed":
        return (
            "fixed: last year's monthly amount raised by CPI each year; the rule every "
            "other report uses."
        )
    if rule == "skip_raise_after_loss":
        return (
            "skip_raise_after_loss: as fixed, but no CPI raise after a year in which the "
            "portfolio's own return (before withdrawals) was negative."
        )
    if rule == "guardrails":
        return (
            "guardrails: take the fixed amount; if 12 x amount / value is above "
            f"{_pct(p['upper'])} of the rate, cut it by {_pct(p['cut'])}; if below "
            f"{_pct(p['lower'])} of the rate, raise it by {_pct(p['raise'])}. "
            "Guyton-Klinger's capital preservation and prosperity rules with their "
            "published bands and steps, with one deviation: no 15-year exception (the "
            "original stops the cuts late in life). Their inflation rule is replaced by "
            "the fixed rule's CPI step."
        )
    if rule == "pct_of_balance":
        return "pct_of_balance: each year 12 x amount = rate x value."
    if rule == "floor_ceiling":
        return (
            "floor_ceiling: rate x value / 12, kept within "
            f"{_pct(-p['max_real_cut'])} and +{_pct(p['max_real_raise'])} of last "
            "year's amount after CPI (Vanguard's published bands, not fitted)."
        )
    raise ValueError(f"unknown rule {rule!r}")


def _header(r: dict) -> list[str]:
    n_p, n_r, n_k = len(r["portfolios"]), len(r["rules"]), len(r["rates"])
    return [
        "# Withdrawal rules: the fixed withdrawal against flexible rules",
        "",
        "Compares the fixed CPI-indexed withdrawal with rules that can cut income after a "
        "bad year, per portfolio, rule and withdrawal rate. A comparison only: no pass/fail "
        "rule and no search trial; it selects nothing and recommends nothing. Spec: "
        "docs/methodology/withdrawal-rules.md.",
        "",
        f"- data: up to {r['data_end']} only (validation and holdout stay sealed)",
        f"- withdrawal_rules.yaml sha256: `{r['rules_sha256']}`",
        f"- decision.yaml sha256: `{r['decision_sha256']}` (read unchanged)",
        f"- longrun.yaml sha256: `{r['longrun_sha256']}` (read unchanged)",
        f"- historical view: start years {min(r['start_years'])} to "
        f"{max(r['start_years'])}, each to {r['data_end']}",
        f"- long run: {r['n_paths']} paths of {r['horizon_years']} years, "
        f"{r['block_months']}-month blocks drawn from {r['n_months']} months "
        f"({r['first_month']} to {r['last_month']}, circular), seed {r['seed']}; the same "
        "paths as the long-run report",
        f"- trading costs: {r['cost_bps']:g} bps per unit traded",
        f"- {n_p} portfolios x {n_r} rules x {n_k} withdrawal rates = {n_p * n_r * n_k} "
        "rows per view",
        "- portfolios: " + "; ".join(f"{p['id']} ({p['label']})" for p in r["portfolios"]),
        "",
    ]


def _notes(r: dict) -> list[str]:
    n = len(r["start_years"])
    return [
        "## Rules",
        "",
        "Every rule starts at rate x starting value / 12 a month and changes the amount "
        "once a year: on the first trading day of each January in the historical view, and "
        "every 12 months (months 13, 25, ...) in the long run, where resampled paths start "
        "in any calendar month. The first year has no change. All parameters are the same "
        "at every rate, and a rule uses only values known at the decision point.",
        "",
        *(f"- {_rule_text(k, v)}" for k, v in r["rules"].items()),
        "",
        "## Notes",
        "",
        "- This is a comparison. It has no pass/fail rule, adds no trials to any search "
        "run, selects nothing and recommends nothing.",
        "- The rules are published or textbook rules with fixed parameters; the bands are "
        "the published ones, not fitted to these data.",
        "- The long-run decision point is every 12 months, not January.",
        "- Income is real: each year's payments in starting-date money (historical: "
        "deflated by the CPI usable on 1 January of that year; long run: by the path's own "
        "inflation to the start of that 12-month period), as a percentage of the starting "
        "income (rate x starting value). A path that ran out counts 0 for every later year "
        "and, in the year it ran out, what it received.",
        "- Years below a line: historical, the share of all calendar years of all start "
        "years (pooled), a year in or after running out counting as below every line; long "
        "run, the share of paths whose real income is below the line in any year, paths "
        "that ran out counting as below.",
        f"- The historical view has {n} overlapping start years, so it is {n} related "
        f"paths, not {n} independent tests. Its worst start year is the one with the lowest "
        "real value at the end.",
        "- Each month the withdrawal is taken first, then the day's (or month's) return. It "
        "is taken proportionally from all holdings at no extra cost, as in the decision "
        "helper. A path is empty once its value is at or below one billionth of the start; "
        "in a month emptied by the withdrawal the income is what was left.",
        "- Typical is the median path; bad case (worst 5%) is the value 1 path in 20 is "
        "below. Lowest value is the lowest nominal value, as a percentage of the starting "
        "value.",
        "",
    ]


def _path_cells(m: dict) -> list[str]:
    return [
        "-" if m["depleted"] is None else m["depleted"],
        _pct(m["end_real"]),
        _pct(m["lowest"]),
        _pct(m["income_low"]),
        _pct(m["income_total"]),
    ]


def _historical(r: dict, rate: float) -> list[str]:
    first, lines = min(r["start_years"]), r["income_lines"]
    cols = [
        "portfolio",
        "rule",
        *(f"{first}: {c}" for c in _PATH_COLS),
        "worst start year",
        *(f"worst: {c}" for c in _PATH_COLS),
        *(f"years below {_pct(x)}" for x in lines),
    ]
    rows = [
        [
            row["portfolio"],
            row["rule"],
            *_path_cells(row["first"]),
            str(row["worst_year"]),
            *_path_cells(row["worst"]),
            *(_pct(row["below"][x]) for x in lines),
        ]
        for row in r["historical"]
        if row["rate"] == rate
    ]
    return [f"### Withdrawal rate {_pct(rate)} per year", "", *_table(cols, rows)]


def _longrun(r: dict, rate: float) -> list[str]:
    lines = r["income_lines"]
    cols = [
        "portfolio",
        "rule",
        *(c.format(h=r["horizon_years"]) for c in _LONG_COLS),
        *(f"ever below {_pct(x)}" for x in lines),
    ]
    rows = [
        [
            row["portfolio"],
            row["rule"],
            *(_pct(row[k]) for k in _LONG_KEYS),
            *(_pct(row["ever_below"][x]) for x in lines),
        ]
        for row in r["longrun"]
        if row["rate"] == rate
    ]
    return [f"### Withdrawal rate {_pct(rate)} per year", "", *_table(cols, rows)]


def render_markdown(report: dict) -> str:
    years = report["start_years"]
    lines = _header(report) + _notes(report)
    lines += [
        f"## Historical view: start years {min(years)} to {max(years)}, each to "
        f"{report['data_end']}",
        "",
    ]
    for rate in report["rates"]:
        lines += _historical(report, rate)
    lines += [f"## Long-run view: {report['horizon_years']}-year resampled paths", ""]
    for rate in report["rates"]:
        lines += _longrun(report, rate)
    return "\n".join(lines).rstrip() + "\n"
