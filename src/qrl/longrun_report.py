"""Markdown for the long-run withdrawal report (spec:
docs/methodology/longrun.md, "Outputs"). Percentages only."""

from __future__ import annotations

from .decision_report import _pct
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
