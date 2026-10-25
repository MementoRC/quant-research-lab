"""Markdown for the staged-entry report (spec: docs/methodology/staged-entry.md,
"Report layout", "Header and notes"). Renders the plain data of
`qrl.decision_staged.run_staged_entry`; no IO, no computation of results."""

from __future__ import annotations

from collections.abc import Callable

VARIANT_TAGS = {"shy": "SHY", "real_plus_1": "CPI+1%"}
VARIANT_LABELS = {
    "shy": "waiting cash in SHY (actual prices)",
    "real_plus_1": "waiting cash at inflation + 1% real (assumption)",
}
HIST_COLUMNS = (
    "Above lump",
    "Gap at 4 y, pp: median (worst, best)",
    "Worst max drawdown",
    "Worst drawdown vs lump, pp",
    "Worst start",
    "Gap at data end, pp: median (worst, best)",
)
_DASH = "—"


def _pct(x: float) -> str:
    return f"{round(100 * x, 1) + 0.0:.1f}%"  # + 0.0 turns -0.0 into 0.0


def _pp(x: float) -> str:
    return f"{round(100 * x, 1) + 0.0:+.1f}"


def _gap(r: dict, key: str) -> str:
    return f"{_pp(r[key + '_median'])} ({_pp(r[key + '_worst'])}, {_pp(r[key + '_best'])})"


def _entry(n: int) -> str:
    return "lump sum" if n == 0 else f"{n} months"


def _hist_cells(r: dict) -> list[str]:
    if r["period"] == 0:
        return [_DASH, _DASH, _pct(r["mdd_worst"]), _DASH, r["worst_start"], _DASH]
    return [
        _pct(r["above"]),
        _gap(r, "gap"),
        _pct(r["mdd_worst"]),
        _pp(r["mdd_worst_diff"]),
        r["worst_start"],
        _gap(r, "end_gap"),
    ]


def _long_cells(r: dict) -> list[str]:
    return [_pct(r["depleted"]), _pct(r["real_end_median"]), _pct(r["real_year5_median"])]


def _table(
    r: dict, view: str, rate: float, columns: tuple[str, ...], cells: Callable[[dict], list[str]]
) -> list[str]:
    by_key = {(x["portfolio"], x["period"], x["variant"]): x for x in r[view] if x["rate"] == rate}
    head = ["Portfolio", "Entry"] + [
        f"{VARIANT_TAGS[v]}: {c}" for v in r["variants"] for c in columns
    ]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for p in r["portfolios"]:
        for n in r["periods"]:
            row = [p["id"], _entry(n)]
            for v in r["variants"]:
                row += cells(by_key[(p["id"], n, v)])
            lines.append("| " + " | ".join(row) + " |")
    return lines


def _header(r: dict) -> list[str]:
    n_p, n_n, n_k = len(r["portfolios"]), len(r["periods"]), len(r["rates"])
    return [
        "# Staged entry: all at once or in monthly tranches, while drawing income",
        "",
        "Compares investing the starting cash all at once (lump sum) with moving it in "
        "equal monthly tranches, while drawing the fixed CPI-indexed income, per core, "
        "staging period, cash variant and withdrawal rate. A comparison only: no pass/fail "
        "rule and no search trial; it selects nothing and recommends nothing. Spec: "
        "docs/methodology/staged-entry.md.",
        "",
        f"- data: up to {r['data_end']} only (validation and holdout stay sealed)",
        f"- staged_entry.yaml sha256: `{r['staged_sha256']}`",
        f"- decision.yaml sha256: `{r['decision_sha256']}` (read unchanged)",
        f"- longrun.yaml sha256: `{r['longrun_sha256']}` (read unchanged)",
        f"- historical view: {r['n_starts']} starts, the first trading day of each month "
        f"{r['first_start']} to {r['last_start']}, each to {r['data_end']}; primary measure "
        f"at {r['horizon_months']} months (the start month counts as the first)",
        f"- long run: {r['n_paths']} paths of {r['horizon_years']} years, "
        f"{r['block_months']}-month blocks drawn from {r['n_months']} months "
        f"({r['first_month']} to {r['last_month']}, circular), seed {r['seed']}; the same "
        "paths as the long-run report",
        f"- trading costs: {r['cost_bps']:g} bps per unit traded",
        "- entry: " + ", ".join(_entry(n) for n in r["periods"]),
        "- cash variants: "
        + "; ".join(f"{VARIANT_TAGS[v]} = {VARIANT_LABELS[v]}" for v in r["variants"]),
        "- portfolios: " + "; ".join(f"{p['id']} ({p['label']})" for p in r["portfolios"]),
        f"- {n_p} portfolios x {n_n} entries x {n_k} withdrawal rates = {n_p * n_n * n_k} "
        "rows per view, one column group per cash variant",
        "",
    ]


def _notes(r: dict) -> list[str]:
    return [
        "## Notes",
        "",
        "- A comparison: it selects nothing and recommends nothing.",
        f"- The {r['n_starts']} historical starts overlap heavily (each "
        f"{r['horizon_months']}-month window shares most of its months with the next), so "
        f"they are not {r['n_starts']} independent tests.",
        "- Withdrawals (fixed, CPI-indexed) come from waiting cash first, then from the "
        "invested part, proportionally across the tranches already bought. On a day with "
        "both, the withdrawal comes first, then the tranche, then the day's returns.",
        "- Waiting cash at inflation + 1% real is an assumption, not a fund. SHY's yields "
        "were near zero in 2009-2015, so the SHY variant understates today's cash rates.",
        f"- Each historical tranche is a fresh purchase paying {r['cost_bps']:g} bps on "
        "entry; the long run charges none, which favours staging by at most "
        f"{r['cost_bps']:g} bps of the starting value. The SHY cash leg is the CASH "
        "portfolio held from the first research day, so only the first start's cash pays "
        f"its {r['cost_bps']:g} bps entry.",
        "- Gap: staged minus lump-sum real value, in percentage points of the starting "
        "value. Above lump: share of starts where staging ended strictly above. Max "
        "drawdown: of the total value (cash plus tranches, after withdrawals) from the "
        f"start to {r['horizon_months']} months, the starting value counting as a peak. "
        "Worst drawdown vs lump: the largest per-start staged-minus-lump difference.",
        "- Flexible withdrawal rules together with staging are deferred.",
        "- The historical period had a long rising market, which favours the lump sum.",
        "",
    ]


def render_markdown(r: dict) -> str:
    long_columns = (
        f"Depleted by year {r['horizon_years']}",
        f"Median real value, year {r['horizon_years']}",
        "Median real value, year 5",
    )
    lines = _header(r) + _notes(r) + ["## Historical starts", ""]
    for rate in r["rates"]:
        lines += [f"### Withdrawal rate {rate * 100:g}%", ""]
        lines += _table(r, "historical", rate, HIST_COLUMNS, _hist_cells) + [""]
    lines += ["## Long run", ""]
    for rate in r["rates"]:
        lines += [f"### Withdrawal rate {rate * 100:g}%", ""]
        lines += _table(r, "longrun", rate, long_columns, _long_cells) + [""]
    return "\n".join(lines)
