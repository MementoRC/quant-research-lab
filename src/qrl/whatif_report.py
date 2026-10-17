"""Markdown for the what-if mix report (spec: docs/methodology/whatif-mix.md). A
pure renderer: it writes its own header and notes (the decision report's header
and cash notes assume the full report) and reuses the decision report's section
builders unchanged. Deterministic (no timestamp); no currency amount appears.
"""

from __future__ import annotations

from pathlib import Path

from .decision_report import (
    DOTCOM_PROXY_NOTE,
    DRAWDOWN_NOTE,
    KNOWN_GAP_NOTE,
    deflation_sentence,
    pct,
    portfolio_section,
    return_section,
    scenario_section,
    signed,
    switching_note,
    window_section,
    withdrawal_section,
    year_one_section,
)
from .whatif import MIX_CASH_ID, MIX_ID, Shares, split_shares

REFERENCE_IDS = ("A", "CASH")


def percent_text(share: float) -> str:
    """A share as a percent with at most 2 decimals, trailing zeros dropped and
    `.` written `p` (0.3333 -> `33p33`). Two shares closer than 0.005 percent
    give the same text, so their files overwrite each other."""
    return f"{round(share * 100, 2):.2f}".rstrip("0").rstrip(".").replace(".", "p")


def slug(given: Shares) -> str:
    """`<id>.<percent>` per ingredient in input order, joined with `__`."""
    return "__".join(f"{name}.{percent_text(share)}" for name, share in given)


def report_path(reports: Path, slug_text: str) -> Path:
    """`reports/whatif-<slug>.md`, resolved and asserted to be under `reports`."""
    out = (reports / f"whatif-{slug_text}.md").resolve()
    if reports.resolve() not in out.parents:
        raise ValueError(f"refusing to write outside {reports}: {out}")
    return out


def _share(x: float) -> str:
    return f"{x * 100:.4g}%"


def _listing(shares: Shares) -> str:
    return ", ".join(f"{name} {_share(share)}" for name, share in shares)


def _tcash_header(noncash: Shares, tcash: float) -> list[str]:
    if tcash <= 0:
        return []
    lines = [f"- TCASH share: {_share(tcash)}"]
    if noncash:
        lines.append(
            f"- the `MIX` rows in the windows, scenarios and year-one tables are the non-cash "
            f"part at 100%; the full mix appears only as `{MIX_CASH_ID}`, in the returns and "
            "withdrawals tables"
        )
    else:
        lines.append(
            f"- `{MIX_CASH_ID}` is 100% true cash and appears only in the returns and "
            "withdrawals tables"
        )
    return lines


def _header(report: dict, given: Shares) -> list[str]:
    noncash, tcash = split_shares(given)
    return [
        "# What-if mix: your own blend of the report's portfolios",
        "",
        "A decision aid. This mix came from the command line, not from `config/decision.yaml`: "
        "it runs the decision report's own code on a mix you chose. It selects nothing and "
        "recommends nothing. Spec: docs/methodology/whatif-mix.md.",
        "",
        f"- mix as given: {_listing(given)}",
        *(
            [f"- {MIX_ID} (the non-cash part, renormalised to 100%): {_listing(noncash)}"]
            if noncash
            else []
        ),
        *_tcash_header(noncash, tcash),
        f"- data: up to {report['data_end']} only (validation and holdout stay sealed)",
        f"- decision.yaml sha256: `{report['decision_sha256']}`",
        f"- core_candidates.yaml sha256: `{report['candidates_sha256']}` (read unchanged)",
        f"- stress.yaml sha256: `{report['stress_sha256']}` (read unchanged)",
        f"- reference rows: {', '.join(REFERENCE_IDS)} (from the decision report)",
        "- scenarios are judgement-based, v1: owner-set what-ifs, not forecasts",
        "",
    ]


def _cash_notes(report: dict, tcash: float) -> list[str]:
    if tcash <= 0:
        return []
    row = report["cash_assumptions"][0]
    return [
        f"- {row['id']} is an assumption row, not a fund: {pct(row['cash_share'])} cash "
        f"earning each month's inflation plus {pct(row['real_yield'])} a year "
        f"({signed(row['real_yield'])} real, the yield in `config/decision.yaml`). Its cash "
        "leg and its daily rebalancing to the split pay no trading cost."
        f"{deflation_sentence(report)}",
        f"- {row['id']} appears only in the research-period return and withdrawal tables: the "
        "historical windows and the judgement-based scenarios have no cash return to give it, "
        "and the year-one table is built from the scenarios.",
    ]


def _notes(report: dict, tcash: float) -> list[str]:
    return [
        "## Notes",
        "",
        "- Every portfolio is 100% of capital, rebalanced daily to its target weights, so "
        "blends look smoother than practice: real rebalancing would be less frequent.",
        f"- Costs differ by table. Withdrawal paths pay {report['cost_bps']:g} bps per unit "
        "of turnover (criteria.yaml cost_bps). Historical-window cells come from `qrl.stress` "
        f"unchanged: replay cells use the engine's default of {report['engine_cost_bps']:g} bps, "
        "frozen cells pay none. Scenario cells are instantaneous and carry no cost.",
        *switching_note(report),
        "- The engine never charges for drift, so the cost of real periodic rebalancing is "
        "slightly understated.",
        DOTCOM_PROXY_NOTE,
        KNOWN_GAP_NOTE,
        "- CASH here is SHY, not true cash.",
        "- Prices are dividend-adjusted, so totals are correct; dividend and interest income "
        "is not separated from sales.",
        "- All figures are percentages: of capital for losses, of the starting value for "
        "withdrawal paths.",
        DRAWDOWN_NOTE,
        *_cash_notes(report, tcash),
        "",
    ]


def render_whatif(report: dict, given: Shares) -> str:
    """Deterministic markdown of a `qrl.decision.run_decision` report run on a
    `qrl.whatif.mix_config`; `given` is the parsed mix (zero shares dropped)."""
    _, tcash = split_shares(given)
    return "\n".join(
        [
            *_header(report, given),
            *_notes(report, tcash),
            *portfolio_section(report),
            *return_section(report),
            *window_section(report),
            *scenario_section(report),
            *withdrawal_section(report),
            *year_one_section(report),
        ]
    )


def summary_lines(report: dict, given: Shares, path: Path) -> list[str]:
    """The terminal summary: the mix, the path, and CAGR and max drawdown of
    each of MIX, MIX-TCASH, A and CASH that exists in the report."""
    by_id = {r["portfolio"]: r for r in report["returns"]}
    lines = [f"mix: {_listing(given)}", f"wrote: {path}"]
    for pid in (MIX_ID, MIX_CASH_ID, *REFERENCE_IDS):
        if pid in by_id:
            r = by_id[pid]
            lines.append(f"{pid}: CAGR {pct(r['cagr'])}, max drawdown {pct(r['max_drawdown'])}")
    return lines
