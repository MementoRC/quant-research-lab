"""Markdown for the decision helper report (spec:
docs/methodology/decision-helper.md). A pure renderer: computed rows in, a
string out, no IO. Deterministic (no timestamp), so a re-run on the same data
diffs cleanly. Every figure is a percentage, of capital or of the starting
value; no currency amount appears anywhere.
"""

from __future__ import annotations

SLEEVE_PREFIX = "A80-"  # the defensive-sleeve rows (docs/methodology/defensive-sleeve.md)
BY_PRODUCT_IDS = ("IEF", "TLT", "RSP", "BONDS")  # sleeves held alone; blend parts only
DOTCOM_SLEEVE = (
    "IEF, TLT and BONDS are, like CASH, entirely cash in `dotcom_2000` (0% loss), so the "
    "A80-CASH20, A80-IEF20, A80-TLT20 and A80-BONDS20 frozen cells are identical there and "
    "that window cannot tell the bond sleeves apart; A80-RSP20 uses the SPY proxy."
)


def _pct(x: float | None) -> str:
    if x is None:
        return "n/a"
    return f"{round(x, 3) + 0.0:.1%}"  # round first, then + 0.0 turns -0.0 into 0.0


def _signed(x: float) -> str:
    """A real yield as a signed whole-or-decimal percentage: 0.01 -> '+1%'."""
    return f"{x * 100:+g}%"


def _pp(x: float | None) -> str:
    """A CAGR difference (0.01 = one percentage point) in percentage points."""
    if x is None:
        return "n/a"
    return f"{round(x * 100, 1) + 0.0:.1f} pp"  # + 0.0 turns -0.0 into 0.0


def _mix(mix: dict[str, float]) -> str:
    return ", ".join(f"{t} {_pct(w)}" for t, w in sorted(mix.items()))


def _cash_row(report: dict) -> dict | None:
    """The cash-assumption row's config fields; a missing key counts as None
    (spec: docs/methodology/true-cash-sleeve.md)."""
    row: dict | None = report.get("cash_assumption")
    return row


def _split(share: float) -> str:
    """The two legs' shares as whole percentages, e.g. 80/20."""
    return f"{round((1 - share) * 100)}/{round(share * 100)}"


def _rows(report: dict) -> list[dict]:
    """Every cash-assumption row (docs/methodology/true-cash-all-cores.md); a
    missing `cash_assumptions` key counts as empty."""
    rows: list[dict] = report.get("cash_assumptions") or []
    return rows


def _multi(report: dict) -> bool:
    """Several assumption rows: the only case where the texts below change."""
    return len(_rows(report)) > 1


def _join(names: list[str]) -> str:
    """'a', 'a and b', 'a, b and c'."""
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def _span(ids: list[str]) -> str:
    """'A to G' for several ids, the id itself for one."""
    return ids[0] if len(ids) == 1 else f"{ids[0]} to {ids[-1]}"


def _pairs(report: dict) -> list[str]:
    return [r["pair"] for r in _rows(report) if r.get("pair")]


def deflation_sentence(report: dict) -> str:
    """The true-cash deflation disclosure from `report["cash_nominal_loss"]`
    (`qrl.true_cash.nominal_loss_stats`), with its leading space; '' when the
    report carries no such figures."""
    s = report.get("cash_nominal_loss")
    if not s:
        return ""
    head = "It follows unadjusted CPI, so it "
    if s["n"] == 0:
        return f" {head}would lose money in a deflation month: 0 of {s['N']} months here."
    return (
        f" {head}loses money in deflation months: {s['n']} of {s['N']} months here, "
        f"worst {round(s['worst'] * 100, 1):.1f}% from {s['start']} to {s['end']}. "
        "A 0% floor would make true cash look better in the crash windows."
    )


def _multi_assumption_note(report: dict) -> list[str]:
    rows = _rows(report)
    first = rows[0]
    n = len(report["portfolios"])
    pairs = _pairs(report)
    pair_ids = f" ({_span(pairs)})" if pairs else ""
    return [
        f"- {_span([r['id'] for r in rows])} are {len(rows)} assumption rows, not funds: for "
        f"each core, {_pct(first['cash_share'])} cash earning each month's inflation plus "
        f"{_pct(first['real_yield'])} a year, the long-run report's CASH {_signed(first['real_yield'])} "
        "real assumption, "
        f"shown next to that core's SHY pair{pair_ids} to answer the SHY caveat. "
        f"They are comparisons {n + 1}-{n + len(rows)} but not among the {n} portfolios. "
        f"Their cash legs and daily returns to {_split(first['cash_share'])} pay no trading "
        "cost, and neither do their SHY pairs: the engine charges only target-to-target "
        f"turnover, so rebalancing a constant mix is free in both rows.{deflation_sentence(report)}"
    ]


def _shy_weight(portfolio: dict) -> float:
    """The SHY weight a portfolio holds in every state; 0 when it differs by state."""
    weights = {mix.get("SHY", 0.0) for mix in portfolio["states"].values()}
    return weights.pop() if len(weights) == 1 else 0.0


def _shy_notes(report: dict) -> list[str]:
    """Rows whose base portfolio already holds SHY: the pair holds more SHY than
    the added share, and the assumption row swaps only the added share."""
    by_id = {p["id"]: p for p in report["portfolios"]}
    out = []
    for r in _rows(report):
        base, pair = by_id.get(r["base"]), r.get("pair")
        x = 0.0 if base is None else _shy_weight(base)
        if x <= 0 or not pair:
            continue
        s = r["cash_share"]
        out.append(
            f"- {r['base']} already holds {round(x * 100, 1):g}% SHY, so {pair} holds "
            f"{round(((1 - s) * x + s) * 100, 1):g}% SHY in all and {r['id']} swaps only the "
            f"added {round(s * 100, 1):g}%."
        )
    return out


def _assumption_note(report: dict) -> list[str]:
    """The cash-assumption row is an assumption, not a fund; nothing without it."""
    if _multi(report):
        return _multi_assumption_note(report)
    ca = _cash_row(report)
    if ca is None:
        return []
    n = len(report["portfolios"])
    return [
        f"- {ca['id']} ({ca['label']}) is an assumption row, not a fund: "
        f"{_pct(ca['cash_share'])} cash earning each month's inflation plus "
        f"{_pct(ca['real_yield'])} a year, the long-run report's CASH {_signed(ca['real_yield'])} "
        "real assumption, "
        "shown to answer the SHY caveat above. "
        f"It is comparison {n + 1} but not one of the {n} portfolios. "
        f"Its cash leg and its daily return to {_split(ca['cash_share'])} pay no trading cost, "
        "and neither does A80-CASH20: the engine charges only target-to-target turnover, "
        f"so rebalancing a constant mix is free in both rows.{deflation_sentence(report)}"
    ]


def _assumption_scope_note(report: dict) -> list[str]:
    """Why the row is only in the return and withdrawal tables; nothing without it."""
    if _multi(report):
        return [
            f"- {_span([r['id'] for r in _rows(report)])} appear only in the research-period "
            "return and withdrawal tables: the historical windows and the judgement-based "
            "scenarios have no cash return to give them. In `dotcom_2000` SHY is already "
            "replaced by cash at 0%, so each row would equal its SHY pair there; in "
            "`gfc_2008` each SHY pair uses SHY's actual prices; the scenarios set SHY's "
            "one-year return by judgement and set none for cash; the year-one table is "
            "built from the scenarios.",
            *_shy_notes(report),
        ]
    ca = _cash_row(report)
    if ca is None:
        return []
    return [
        f"- {ca['id']} appears only in the research-period return and withdrawal tables: the "
        "historical windows and the judgement-based scenarios have no cash return to give it. "
        "In `dotcom_2000` SHY is already replaced by cash at 0%, so the row would equal "
        "A80-CASH20 there; in `gfc_2008` A80-CASH20 uses SHY's actual prices; the scenarios "
        "set SHY's one-year return by judgement and set none for cash; the year-one table is "
        "built from the scenarios."
    ]


def _has_sleeves(report: dict) -> bool:
    return any(p["id"].startswith(SLEEVE_PREFIX) for p in report["portfolios"])


def _sleeve_note(report: dict) -> list[str]:
    """Which rows answer the defensive-sleeve question, and the SHY-as-cash caveat;
    nothing without A80 rows."""
    if not _has_sleeves(report):
        return []
    ids = [p["id"] for p in report["portfolios"]]
    sleeves = [i for i in ids if i.startswith(SLEEVE_PREFIX)]
    extra = [i for i in ids if i in BY_PRODUCT_IDS]
    true_cash = ""
    if _multi(report):
        true_cash = (
            f"; the {len(_pairs(report))} X80-CASH20 rows and the {len(_rows(report))} "
            "assumption rows answer the true-cash question "
            "(docs/methodology/true-cash-all-cores.md)"
        )
    return [
        f"- of the {len(ids)} portfolios here, {len(extra)} are by-product rows, each a "
        f"sleeve held alone ({', '.join(extra)}); only the {len(sleeves)} A80 rows "
        f"({', '.join(sleeves)}) answer the defensive-sleeve question "
        f"(docs/methodology/defensive-sleeve.md){true_cash}",
        "- CASH here is SHY, not true cash: SHY's near-zero 2009-2015 yields make the "
        "A80-CASH20 baseline look worse than cash at today's rates",
    ]


def _header(report: dict) -> list[str]:
    prior = report["candidate_count"]
    extra_rows = len(_rows(report)) if _multi(report) else int(_cash_row(report) is not None)
    n = len(report["portfolios"]) + extra_rows
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
        *_sleeve_note(report),
        *_assumption_note(report),
        "- scenarios are judgement-based, v1: owner-set what-ifs, not forecasts",
        "",
    ]


def _switching_label(report: dict) -> str:
    """Every portfolio shown in more than one state; '' when there is none."""
    names = [p["id"] for p in report["portfolios"] if len(p["states"]) > 1]
    return _join(names) if names else ""


def _mostly_proxied(report: dict) -> str:
    """The portfolios flagged indicative in `dotcom_2000`; '' when there is none."""
    flagged = [
        r["portfolio"]
        for r in report["windows"]
        if r["window"] == "dotcom_2000" and r["indicative"] and not r["unavailable"]
    ]
    return _join(list(dict.fromkeys(flagged))) if flagged else ""


def _switching_note(report: dict) -> list[str]:
    label = _switching_label(report)
    if not label:
        return []
    return [
        f"- Switching portfolios ({label}) are shown in both states, "
        "risk-on and risk-off, because their current state would need sealed data; the worse "
        "is marked."
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
        *_switching_note(report),
        "- The engine never charges for drift, so the cost of real periodic rebalancing is "
        "slightly understated for every blend.",
        "- In the dot-com window (2000) RSP, GLD and bonds are proxied (they did not yet "
        "trade), so those cells are indicative only.",
        "- Known gap: no portfolio holds an asset that gains from a falling dollar other "
        "than gold.",
        "- Prices are dividend-adjusted, so totals are correct; dividend and interest income "
        "is not separated from sales.",
        "- All figures are percentages: of capital for losses, of the starting value for "
        "withdrawal paths.",
        "- Drawdowns here count the starting value as a peak. The criteria and the research "
        "dashboard use `qrl.metrics`, which does not, so their figures can be lower by up to "
        "about a point.",
        *_assumption_scope_note(report),
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


def _return_section(report: dict) -> list[str]:
    """Research-period return, no withdrawals; omitted when `returns` is absent or empty."""
    rows = report.get("returns") or []
    if not rows:
        return []
    lines = [
        "## Research-period return (2005-2018, no withdrawals)",
        "",
        "Each portfolio bought on the first trading day of the research period and held to "
        f"{report['data_end']} with no withdrawals, paying {report['cost_bps']:g} bps per unit "
        "of turnover. Max drawdown is a positive loss. CAGR given up vs A is A's CAGR minus "
        "the row's, in percentage points (pp); negative means the row earned more than A, "
        "n/a means A is not in the report.",
        "",
        "| Portfolio | CAGR | Max drawdown (from start) | CAGR given up vs A |",
        "|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['portfolio']} | {_pct(r['cagr'])} | {_pct(r['max_drawdown'])} | "
            f"{_pp(r['lost_return'])} |"
        )
    return [*lines, ""]


def _proxied(shares: dict[str, float]) -> str:
    return ", ".join(f"{cls} {s:.0%}" for cls, s in sorted(shares.items()) if s > 0)


def _window_flag(row: dict) -> str:
    if row["unavailable"]:
        return f"unavailable: {row['unavailable']}"
    return "mostly proxied, indicative only" if row["indicative"] else ""


def _window_section(report: dict) -> list[str]:
    threshold = report["proxied_threshold"]
    proxied = _mostly_proxied(report)
    lines = [
        "## Historical windows",
        "",
        "| portfolio | window | mode | worst drawdown (from start) | proxied (per class) | flag |",
        "|---|---|---|---|---|---|",
    ]
    for r in report["windows"]:
        lines.append(
            f"| {r['portfolio']} | {r['window']} | {r['mode']} | {_pct(r['loss'])} | "
            f"{_proxied(r['proxied_share'])} | {_window_flag(r)} |"
        )
    proxies = " ".join(
        [
            "Proxies (`qrl.stress`): in a frozen cell, a fund without a price at the window "
            "start is replaced by SPY (equity) or by cash (bonds, gold). A cell more than "
            f"{threshold:.0%} proxied is marked mostly proxied, indicative only. "
            "`dotcom_2000` starts before SHY, IEF and TLT (2002), RSP (2003) and GLD (2004): "
            "CASH is entirely cash there (0% loss by construction)"
            + (f" and {proxied} are mostly proxied." if proxied else "."),
            *([DOTCOM_SLEEVE] if _has_sleeves(report) else []),
        ]
    )
    return [
        *lines,
        "",
        proxies,
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
        rows = [r for r in report["withdrawals"] if r["rate"] == rate]
        h = rows[0]["horizon_years"] if rows else ""
        lines += [
            f"### Withdrawal rate {_pct(rate)} per year",
            "",
            f"| portfolio | real ending value (start {first}) | lowest value | max drawdown (from start) | "
            "longest below a prior peak | below peak at end | depleted | "
            f"worst start year to {report['data_end']} (real ending value; horizons differ) | "
            f"worst {h}-year start (real value after {h} years) |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for row in rows:
            m = row["first"]
            wy = row["worst_year"]
            lines.append(
                f"| {row['portfolio']} | {_pct(m['end_real'])} | {_pct(m['lowest'])} | "
                f"{_pct(m['max_drawdown'])} | {_below_peak(m)} | "
                f"{'yes' if m['below_peak_at_end'] else 'no'} | {m['depleted'] or 'no'} | "
                f"{wy}, {row['horizons'][wy]} y ({_pct(row['worst_end_real'])}) | "
                f"{row['worst5_year']} ({_pct(row['worst5_end_real'])}) |"
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
            *_return_section(report),
            *_window_section(report),
            *_scenario_section(report),
            *_withdrawal_section(report),
            *_year_one_section(report),
        ]
    )
