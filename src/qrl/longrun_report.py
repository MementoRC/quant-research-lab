"""Markdown for the long-run withdrawal report (spec:
docs/methodology/longrun.md, "Outputs"). Percentages only."""

from __future__ import annotations

from .decision_report import _pct
from .longrun import CASH_ASSUMPTION

_COLS = (
    "portfolio",
    "depleted by year 20",
    "by year 25",
    "by year 30",
    "median depletion year (depleted paths)",
    "real value ever below {floor}",
    "real value at year 30: median",
    "worst 5%",
)


def _header(r: dict) -> list[str]:
    return [
        "# Long-run withdrawals: 30-year resampled paths",
        "",
        "Compares portfolios over 30-year withdrawal paths built by resampling "
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
        f"- Portfolio returns pay {r['cost_bps']:g} bps per unit of turnover.",
        f"- {CASH_ASSUMPTION}: an assumption, not history. It earns each month's inflation plus "
        f"{_pct(r['cash_real_yield'])} a year.",
        "- A path is empty once its value is at or below 1e-9 of the start.",
        "- All figures are percentages of the starting value or of paths.",
        "",
    ]


def _rate_section(r: dict, rate: float) -> list[str]:
    cols = [c.format(floor=_pct(r["real_floor"])) for c in _COLS]
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
