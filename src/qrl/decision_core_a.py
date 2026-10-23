"""The decision helper's section on what the tests say about the held core A
(spec: docs/methodology/decision-helper.md, note 2026-10-23). Every figure is
read from the ledger, opened read-only, so the section regenerates with the
report. A missing ledger or missing rows give a one-line note, never an error.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

TITLE = "## What the tests say about core A (QQQ/GLD trend, held core)"
RUN_ID = 8  # the pre-registered fixed standalone attempt (research period)
TEST_ID = 1496
FAMILY = "core_trend"
SET_NAME = "main"  # the international main set
UNAVAILABLE = (
    "Not available: the ledger rows for the tests of core A (run 8, test 1496; "
    "international main set) were not found."
)


def _pct(x: float) -> str:
    return f"{round(x, 3) + 0.0:.1%}"


def _num(x: float) -> str:
    return f"{x:.2f}"


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _fetch(path: Path) -> tuple[sqlite3.Row | None, sqlite3.Row | None]:
    """The fixed US attempt and the completed international main event; each
    None when absent. Raises sqlite3.Error for an unreadable ledger."""
    conn = _connect(path)
    try:
        test = conn.execute(
            "SELECT params_json, metrics_json, passed, failure_reasons FROM tests "
            "WHERE test_id = ? AND run_id = ? AND family = ?",
            (TEST_ID, RUN_ID, FAMILY),
        ).fetchone()
        event = conn.execute(
            "SELECT result_json, report_path, data_end FROM international_events "
            "WHERE set_name = ? AND status = 'completed' AND result_json IS NOT NULL",
            (SET_NAME,),
        ).fetchone()
    finally:
        conn.close()
    return test, event


def _beat_failed(test: sqlite3.Row) -> bool:
    """The ledger records failed pass rules by name, e.g. 'min_sharpe,beat_benchmark'."""
    return "beat_benchmark" in (test["failure_reasons"] or "")


def _us_section(test: sqlite3.Row, criteria: dict) -> list[str]:
    m = json.loads(test["metrics_json"])
    params = json.loads(test["params_json"])
    rules = criteria["pass"]
    verdict = "passed" if test["passed"] else "failed"
    follow = "" if test["passed"] else " Because it failed, no validation was run."
    lines = [
        "### US research period (2005-2018): one fixed attempt",
        "",
        f"Core A was tried once, with settings fixed in advance (ledger run {RUN_ID}, test "
        f"{TEST_ID}: hold {params.get('risk_on')} while it is above its {params.get('lookback')}"
        f"-day average, otherwise hold {params.get('risk_off')}). It {verdict} the pass rules.{follow}",
        "",
        f"- Sharpe (return per unit of risk): {m['sharpe']:.3f}; the pass rule needs at least "
        f"{rules['min_sharpe']}",
        f"- Compound yearly return: {_pct(m['cagr'])}",
        f"- Largest peak-to-trough fall: {_pct(m['max_drawdown'])}",
        f"- Trades: {m.get('trades', 'n/a')}",
    ]
    if _beat_failed(test):
        lines.append(
            f"- It also did not beat {rules['beat_benchmark']} on {rules['beat_on'].capitalize()}, "
            "which the pass rules require"
        )
    return [*lines, ""]


def _market_row(m: dict) -> str:
    rule, bh = m["rule"], m["buy_and_hold"]
    return (
        f"| {m['market']} | {_num(rule['sharpe'])} | {_num(bh['sharpe'])} | "
        f"{_pct(rule['cagr'])} vs {_pct(bh['cagr'])} | "
        f"{_pct(rule['max_drawdown'])} vs {_pct(bh['max_drawdown'])} |"
    )


def _window(markets: list[dict], data_end: str) -> str:
    wins = markets[0].get("windows") if markets else None
    if wins:
        return f"{wins[0]['start']} to {wins[0]['end']}"
    return f"up to {data_end}"


def _gold_note(result: dict, gold_min: float | None) -> str:
    corr = result.get("gold_correlation")
    if not result.get("late_only") or corr is None or gold_min is None:
        return ""
    return (
        f" Because the gold stand-in check did not pass ({corr:.2f}, below the "
        f"{gold_min:.2f} needed), only the late window could be scored."
    )


def _intl_section(event: sqlite3.Row, gold_min: float | None) -> list[str]:
    result = json.loads(event["result_json"])
    v, markets = result["verdict"], result["markets"]
    status = result.get("subject_status")
    label = (
        'Core A was owner-designated for this test and is labelled "subject not validated" '
        "(it had not passed the US tests). "
        if status
        else ""
    )
    gain = v["average_sharpe_gain"]
    report = f"research/{Path(event['report_path']).name}" if event["report_path"] else "n/a"
    return [
        "### International final test, main set (seven foreign stock markets)",
        "",
        f"{label}The rule was scored over {_window(markets, event['data_end'])} only."
        f"{_gold_note(result, gold_min)} {v['passed_markets']} of {v['markets']} markets "
        f"passed (the test needs {v['required']}); the average Sharpe gain over simply holding "
        f"each market was {'n/a' if gain is None else f'{gain:+.2f}'}. Full report: {report}.",
        "",
        "| Market | Core A rule Sharpe | Buy-and-hold Sharpe | Yearly return: rule vs "
        "buy-and-hold | Largest fall: rule vs buy-and-hold |",
        "|---|---|---|---|---|",
        *[_market_row(m) for m in markets if m.get("enough_data")],
        "",
    ]


def _meaning_section(test: sqlite3.Row | None, event: sqlite3.Row | None) -> list[str]:
    lines = ["### What this does and does not tell you", ""]
    if event is not None:
        markets = [m for m in json.loads(event["result_json"])["markets"] if m.get("enough_data")]
        n = len(markets)
        lower = sum(m["rule"]["sharpe"] < m["buy_and_hold"]["sharpe"] for m in markets)
        deeper = sum(m["rule"]["max_drawdown"] > m["buy_and_hold"]["max_drawdown"] for m in markets)
        lines += [
            f"- In the international test, core A's risk-adjusted return (Sharpe) was below simply "
            f"holding the market in {lower} of {n} markets.",
            f"- Its largest fall was bigger than buy-and-hold's in {deeper} of {n} markets: "
            "switching to gold did not protect in those mild declines.",
        ]
    lines += [
        "- The international window was mostly rising markets and contains no large crash, "
        "so it says little about behaviour in a crash; the stress and withdrawal tables "
        "elsewhere in this report cover that.",
        "- A failed test does not make core A unusable. It means an edge over simply holding "
        "the index has not been established.",
        "- The decision is the owner's.",
    ]
    if test is not None and not test["passed"]:
        lines.insert(
            2,
            "- In the US research period, core A did not meet the pass rules"
            + (" and did not beat the QQQ index on Sharpe." if _beat_failed(test) else "."),
        )
    return [*lines, ""]


def render_core_a_section(
    ledger_path: str | Path, criteria: dict, gold_min_correlation: float | None = None
) -> str:
    """Markdown for the core A evidence section, from a read-only look at the ledger."""
    path = Path(ledger_path)
    try:
        test, event = _fetch(path) if path.exists() else (None, None)
    except (sqlite3.Error, json.JSONDecodeError):
        test, event = None, None
    if test is None and event is None:
        return "\n".join([TITLE, "", UNAVAILABLE, ""])
    lines = [
        TITLE,
        "",
        "Evidence from the research ledger, shown as it stands. It is not a recommendation.",
        "",
    ]
    lines += _us_section(test, criteria) if test is not None else []
    lines += _intl_section(event, gold_min_correlation) if event is not None else []
    lines += _meaning_section(test, event)
    return "\n".join(lines)
