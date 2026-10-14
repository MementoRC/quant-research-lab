"""Markdown for the long-run withdrawal report (spec:
docs/methodology/longrun.md, "Outputs"). Percentages only."""

from __future__ import annotations

from .decision_report import BY_PRODUCT_IDS, SLEEVE_PREFIX, _pct, _span, _split
from .longrun import CASH_ASSUMPTION

_COLS = (
    "portfolio",
    "money ran out by year 20",
    "by year 25",
    "by year 30",
    "typical year it ran out (paths that ran out)",
    "real value ever below {floor}",
    "real value at year {h}: typical",
    "real value at year {h}: bad case (worst 5%)",
)


def _rows(r: dict) -> list[dict]:
    """The `cash_assumptions` list (spec: docs/methodology/true-cash-all-cores.md);
    a missing key counts as empty."""
    rows: list[dict] = r.get("cash_assumptions") or []
    return rows


def _sleeve_note(r: dict) -> list[str]:
    """Which rows answer the defensive-sleeve question; nothing without A80 rows.
    The cash-assumption row (docs/methodology/true-cash-sleeve.md) is named as
    an assumption row, not counted as an A80 row; a missing key counts as None."""
    names = list(dict.fromkeys(row["portfolio"] for row in r["rows"]))
    cash_id = r.get("cash_assumption_id")
    rows = _rows(r)
    sleeves = [
        n
        for n in names
        if n.startswith(SLEEVE_PREFIX) and n != cash_id and n not in {x["id"] for x in rows}
    ]
    if not sleeves:
        return []
    extra = [n for n in names if n in BY_PRODUCT_IDS]
    if len(rows) > 1:
        pairs = [x for x in rows if x.get("pair")]
        return [
            f"- {len(names)} rows per withdrawal rate, including the {CASH_ASSUMPTION} "
            f"row, {len(rows)} assumption rows ({_span([x['id'] for x in rows])}) and "
            f"{len(extra)} by-product rows ({', '.join(extra)}); only the {len(sleeves)} A80 "
            "rows answer the defensive-sleeve question "
            f"(docs/methodology/defensive-sleeve.md); the {len(pairs)} X80-CASH20 rows and "
            f"the {len(rows)} assumption rows answer the true-cash question "
            "(docs/methodology/true-cash-all-cores.md)"
        ]
    assumption = f", the {cash_id} assumption row" if cash_id else ""
    return [
        f"- {len(names)} rows per withdrawal rate, including the {CASH_ASSUMPTION} "
        f"row{assumption} and {len(extra)} by-product rows ({', '.join(extra)}); only the "
        f"{len(sleeves)} A80 rows answer the defensive-sleeve question "
        "(docs/methodology/defensive-sleeve.md)"
    ]


def _multi_assumption_note(r: dict, rows: list[dict]) -> list[str]:
    share = rows[0]["share"]
    pairs = [f"{x['id']} with {x['pair']}" for x in rows if x.get("pair")]
    pair_text = f" ({', '.join(pairs)})" if pairs else ""
    return [
        f"- {_span([x['id'] for x in rows])}: assumptions, not history. Each is "
        f"{_pct(1 - share)} of its own core plus {_pct(share)} cash earning each month's "
        f"inflation plus {_pct(r['cash_real_yield'])} a year, rebalanced daily; every real "
        "yield is checked equal to the CASH +1% real row's. The cash legs and the daily "
        f"returns to {_split(share)} pay no trading cost, and neither do their SHY "
        f"pairs{pair_text}: the engine charges only target-to-target turnover, so "
        "rebalancing a constant mix is free in both rows."
    ]


def _assumption_note(r: dict) -> list[str]:
    """The cash-assumption row is an assumption, not history; nothing without it."""
    rows = _rows(r)
    if len(rows) > 1:
        return _multi_assumption_note(r, rows)
    cash_id = r.get("cash_assumption_id")
    if not cash_id:
        return []
    share = r["cash_assumption_share"]
    return [
        f"- {cash_id}: an assumption, not history. {_pct(1 - share)} "
        f"{r['cash_assumption_base']} plus {_pct(share)} cash earning each month's inflation "
        f"plus {_pct(r['cash_real_yield'])} a year, rebalanced daily; its real yield is "
        "checked equal to the CASH +1% real row's. The cash leg and the daily return to "
        f"{_split(share)} pay no trading cost, and neither does A80-CASH20: the engine "
        "charges only target-to-target turnover, so rebalancing a constant mix is free in "
        "both rows."
    ]


def _header(r: dict) -> list[str]:
    h = r["horizon_years"]
    return [
        f"# Long-run withdrawals: {h}-year resampled paths",
        "",
        f"Compares portfolios over {h}-year withdrawal paths built by resampling "
        f"{r['first_month']} to {r['last_month']} months. It selects and recommends "
        "nothing. Spec: docs/methodology/longrun.md.",
        "",
        f"- data: up to {r['data_end']} only (validation and holdout stay sealed)",
        f"- {r['n_paths']} paths of {r['horizon_years']} years, {r['block_months']}-month "
        f"blocks drawn from {r['n_months']} months (circular), seed {r['seed']}; every "
        "portfolio sees the same draws",
        f"- longrun.yaml sha256: `{r['longrun_sha256']}`",
        f"- decision.yaml sha256: `{r['decision_sha256']}` (read unchanged)",
        *_sleeve_note(r),
        "",
        "## How to read this",
        "",
        f"- Each path is one made-up {h}-year retirement, built by stringing together real "
        f"12-month stretches of {r['first_month']} to {r['last_month']} in random order. "
        f"There are {r['n_paths']:,} paths, and every portfolio is run through the same "
        "ones, so differences between portfolios are not luck of the draw.",
        "- Money ran out means the portfolio fell to effectively zero.",
        "- Real value means value after inflation, in today's money, as a percentage of "
        "the starting amount.",
        "- Bad case (worst 5%) is the value that 1 path in 20 ends below.",
        "- Withdrawals start at the annual rate / 12 of the starting amount each month and "
        "rise every 12 months with that path's own inflation.",
        "",
        "## Limits",
        "",
        "- one market era (2005-2018)",
        "- one large crash (2008)",
        "- falling interest rates that flatter bonds",
        "- low inflation",
        "- near-zero cash yields in 2009-2015",
        "",
        "Resampling recombines these months. It cannot create a 1970s-style inflation decade.",
        "",
        "## Notes",
        "",
        "- Each month the withdrawal is taken first, then the month's return applies. It "
        "starts at the annual rate / 12 of the starting value and is raised every 12 months "
        "by the path's own inflation.",
        f"- Portfolio returns pay trading costs of {r['cost_bps']:g} bps (0.01% each) "
        "per unit traded.",
        f"- {CASH_ASSUMPTION}: an assumption, not history. It earns each month's inflation plus {_pct(r['cash_real_yield'])} a year.",
        *_assumption_note(r),
        "- The engine never charges for drift, so the cost of real periodic rebalancing is "
        "slightly understated for every blend.",
        "- A path is empty once its value is effectively zero (below one billionth of the start).",
        "- All figures are percentages of the starting value or of paths.",
        "",
    ]


def _rate_section(r: dict, rate: float) -> list[str]:
    cols = [c.format(floor=_pct(r["real_floor"]), h=r["horizon_years"]) for c in _COLS]
    out = [
        f"### Withdrawal rate {_pct(rate)} per year",
        "",
        "| " + " | ".join(cols) + " |",
        "|" + "---|" * len(cols),
    ]
    for row in (x for x in r["rows"] if x["rate"] == rate):
        year = row["median_depletion_year"]
        out.append(
            "| "
            + " | ".join(
                [
                    row["portfolio"],
                    _pct(row["depleted_by"][20]),
                    _pct(row["depleted_by"][25]),
                    _pct(row["depleted_by"][30]),
                    "-" if year is None else str(year),
                    _pct(row["below_floor"]),
                    _pct(row["end_real_median"]),
                    _pct(row["end_real_p5"]),
                ]
            )
            + " |"
        )
    return out + [""]


def render_markdown(report: dict) -> str:
    lines = _header(report) + ["## Withdrawals", ""]
    for rate in report["rates"]:
        lines += _rate_section(report, rate)
    return "\n".join(lines).rstrip() + "\n"
