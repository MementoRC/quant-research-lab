"""Markdown for the decision helper report (spec:
docs/methodology/decision-helper.md). A pure renderer: computed rows in, a
string out, no IO. Deterministic (no timestamp), so a re-run on the same data
diffs cleanly. Every figure is a percentage, of capital or of the starting
value; no currency amount appears anywhere.
"""

from __future__ import annotations


def _pct(x: float | None) -> str:
    if x is None:
        return "n/a"
    return f"{round(x, 3) + 0.0:.1%}"  # round first, then + 0.0 turns -0.0 into 0.0


def _mix(mix: dict[str, float]) -> str:
    return ", ".join(f"{t} {_pct(w)}" for t, w in sorted(mix.items()))


def _header(report: dict) -> list[str]:
    n, prior = len(report["portfolios"]), report["candidate_count"]
    return [
        "# Decision helper: portfolios, scenarios and withdrawals",
        "",
        "A decision aid for deploying savings while withdrawing for income. It compares a "
        "fixed set of portfolios; it selects nothing and recommends nothing. Spec: "
        "docs/methodology/decision-helper.md.",
        "",
        f"- data: up to {report['data_end']} only (validation and holdout stay sealed)",
        f"- decision.yaml sha256: `{report['decision_sha256']}`",
        f"- core_candidates.yaml sha256: `{report['candidates_sha256']}` (read unchanged)",
        f"- stress.yaml sha256: `{report['stress_sha256']}` (read unchanged)",
        f"- multiple comparisons: {prior} in the core comparison, {n} here (A-G again plus "
        f"{n - prior} new); the more portfolios compared, the likelier the best-looking one "
        "is luck",
        "- scenarios are judgement-based, v1: owner-set what-ifs, not forecasts",
        "",
    ]


def _notes(report: dict) -> list[str]:
    return [
        "## Notes",
        "",
        "- Every portfolio is 100% of capital, rebalanced daily to its target weights, so "
        "blends look smoother than practice: real rebalancing would be less frequent.",
        f"- Costs differ by table. Withdrawal paths pay {report['cost_bps']:g} bps per unit "
        "of turnover (criteria.yaml cost_bps). Historical-window cells come from `qrl.stress` "
        f"unchanged: replay cells use the engine's default of {report['engine_cost_bps']:g} bps, "
        "frozen cells pay none. "
        "Scenario cells are instantaneous and carry no cost.",
        "- Switching portfolios (A, B, C, F and blends holding A) are shown in both states, "
        "risk-on and risk-off, because their current state would need sealed data; the worse "
        "is marked.",
        "- In the dot-com window (2000) RSP, GLD and bonds are proxied (they did not yet "
        "trade), so those cells are indicative only.",
        "- Known gap: no portfolio holds an asset that gains from a falling dollar other "
        "than gold.",
        "- Prices are dividend-adjusted, so totals are correct; dividend and interest income "
        "is not separated from sales.",
        "- All figures are percentages: of capital for losses, of the starting value for "
        "withdrawal paths.",
        "",
    ]


def _portfolio_section(report: dict) -> list[str]:
    lines = [
        "## Portfolios (100% of capital)",
        "",
        "| id | definition | state | weights |",
        "|---|---|---|---|",
    ]
    for p in report["portfolios"]:
        for state, mix in p["states"].items():
            lines.append(f"| {p['id']} | {p['label']} | {state} | {_mix(mix)} |")
    return [*lines, ""]


def _proxied(shares: dict[str, float]) -> str:
    return ", ".join(f"{cls} {s:.0%}" for cls, s in sorted(shares.items()) if s > 0)


def _window_flag(row: dict) -> str:
    if row["unavailable"]:
        return f"unavailable: {row['unavailable']}"
    return "mostly proxied, indicative only" if row["indicative"] else ""


def _window_section(report: dict) -> list[str]:
    threshold = report["proxied_threshold"]
    lines = [
        "## Historical windows",
        "",
        "| portfolio | window | mode | worst drawdown | proxied (per class) | flag |",
        "|---|---|---|---|---|---|",
    ]
    for r in report["windows"]:
        lines.append(
            f"| {r['portfolio']} | {r['window']} | {r['mode']} | {_pct(r['loss'])} | "
            f"{_proxied(r['proxied_share'])} | {_window_flag(r)} |"
        )
    return [
        *lines,
        "",
        "Proxies (`qrl.stress`): in a frozen cell, a fund without a price at the window start "
        "is replaced by SPY (equity) or by cash (bonds, gold). A cell more than "
        f"{threshold:.0%} proxied is marked mostly proxied, indicative only. "
        "`dotcom_2000` starts before SHY, IEF and TLT (2002), RSP (2003) and GLD (2004): CASH "
        "is entirely cash there (0% loss by construction) and G, G-EW, G-CASH and A-CASH are "
        "mostly proxied.",
        "",
        "Switching portfolios: the replay cell runs the rule; `[risk_on]` / `[risk_off]` "
        "frozen cells hold that state's fixed weights.",
        "",
    ]


def _scenario_section(report: dict) -> list[str]:
    funds = sorted({t for s in report["scenarios"] for t in s["returns"]})
    lines = [
        "## Judgement-based scenarios (one year)",
        "",
        "| scenario | label | " + " | ".join(funds) + " | inflation |",
        "|---|---|" + "---|" * (len(funds) + 1),
    ]
    for s in report["scenarios"]:
        cells = " | ".join(_pct(s["returns"].get(t)) for t in funds)
        lines.append(f"| {s['name']} | {s['label']} | {cells} | {_pct(s['inflation'])} |")
    lines += [
        "",
        "Loss is positive; a negative loss is a gain. Real = (1 + nominal) / (1 + inflation) - 1.",
        "",
        "| portfolio | scenario | state | nominal loss | real loss | worse state |",
        "|---|---|---|---|---|---|",
    ]
    for row in report["scenario_rows"]:
        for state, v in row["states"].items():
            mark = "worse" if len(row["states"]) > 1 and state == row["worst"] else ""
            lines.append(
                f"| {row['portfolio']} | {row['scenario']} | {state} | "
                f"{_pct(v['nominal_loss'])} | {_pct(v['real_loss'])} | {mark} |"
            )
    return [*lines, ""]


def _below_peak(m: dict) -> str:
    months = m["below_peak_months"]
    return f"{months} months" if m["recovered"] else f"at least {months} months, not recovered"


def _withdrawal_section(report: dict) -> list[str]:
    years = report["start_years"]
    first = min(years)
    lines = [
        "## Withdrawals",
        "",
        f"Paths start on the first trading day of each January {first}-{max(years)} and end "
        f"{report['data_end']}. Values are percentages of the starting value. The monthly "
        "withdrawal (annual rate / 12 of the starting value) is taken on the first trading "
        "day of each month, after that day's return, proportionally from all holdings, with "
        "no extra trading cost. It changes each January by the year-over-year change of "
        "CPIAUCNS usable on 1 January (month M is usable from the last day of month M+1). "
        "Real values are deflated by the same CPI. Lowest value, max drawdown, longest "
        f"time below a prior peak and below peak at end are for the {first} path.",
        "",
    ]
    for rate in report["rates"]:
        lines += [
            f"### Withdrawal rate {_pct(rate)} per year",
            "",
            f"| portfolio | real ending value (start {first}) | lowest value | max drawdown | "
            "longest below a prior peak | below peak at end | depleted | "
            "worst start year (real ending value) |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for row in report["withdrawals"]:
            if row["rate"] != rate:
                continue
            m = row["first"]
            lines.append(
                f"| {row['portfolio']} | {_pct(m['end_real'])} | {_pct(m['lowest'])} | "
                f"{_pct(m['max_drawdown'])} | {_below_peak(m)} | "
                f"{'yes' if m['below_peak_at_end'] else 'no'} | {m['depleted'] or 'no'} | "
                f"{row['worst_year']} ({_pct(row['worst_end_real'])}) |"
            )
        lines.append("")
    return lines


def _year_one_cell(v: dict) -> str:
    cell = f"{_pct(v['nominal'])} / {_pct(v['real'])}"
    return f"{cell} (depleted within year one)" if v["nominal"] <= 0 else cell


def _year_one_section(report: dict) -> list[str]:
    rates = report["rates"]
    values = {(r["portfolio"], r["scenario"], r["rate"]): r for r in report["year_one"]}
    switching = {p["id"] for p in report["portfolios"] if len(p["states"]) > 1}
    lines = [
        "## Year-one scenario hit",
        "",
        "Value after one year as a percentage of the start: (1 + the worse state's scenario "
        "return) minus the year's withdrawals at that rate (no raise in year one); nominal / "
        "real (deflated by the scenario's inflation). A negative value is shown as computed "
        "and marked depleted within year one.",
        "",
    ]
    for s in report["scenarios"]:
        lines += [
            f"### {s['name']}",
            "",
            "| portfolio | " + " | ".join(f"{_pct(rate)} nominal / real" for rate in rates) + " |",
            "|---|" + "---|" * len(rates),
        ]
        for p in report["portfolios"]:
            rows = [values[(p["id"], s["name"], rate)] for rate in rates]
            name = f"{p['id']} ({rows[0]['state']})" if p["id"] in switching else p["id"]
            lines.append(f"| {name} | " + " | ".join(_year_one_cell(v) for v in rows) + " |")
        lines.append("")
    return lines


def render_markdown(report: dict) -> str:
    """Deterministic markdown of a `qrl.decision.run_decision` report."""
    return "\n".join(
        [
            *_header(report),
            *_notes(report),
            *_portfolio_section(report),
            *_window_section(report),
            *_scenario_section(report),
            *_withdrawal_section(report),
            *_year_one_section(report),
        ]
    )
