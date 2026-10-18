"""What-if shock (spec: docs/methodology/whatif-shock.md): qrl.shock_report and
scripts/whatif_shock.py. Offline: the shipped config/decision.yaml plus synthetic
prices and CPI. Existing tests are untouched."""

from __future__ import annotations

import pytest
from decision_helpers import CANDIDATES, END, ROOT, cpi, criteria, prices, stress_cfg
from test_shock import SHOCK2, _small

from qrl.decision_config import load_decision_config
from qrl.decision_report import pct
from qrl.shock import extend_config, run_shock
from qrl.shock_report import render_shock, summary_lines

GIVEN = [("A", 0.8), ("TCASH", 0.2)]


def _shipped():
    return load_decision_config(ROOT / "config" / "decision.yaml", CANDIDATES, stress_cfg(), END)


@pytest.fixture(scope="module")
def report():
    base = _small(_shipped(), years=(2005, 2006), rates=(0.04,))
    cfg = extend_config(base, GIVEN, None)
    return run_shock(cfg, prices(), cpi(), criteria(), SHOCK2, "cd" * 32)


def test_render_header_shock_table_and_assumptions(report):
    md = render_shock(report, GIVEN)
    assert md.startswith("# What-if shock: t2")
    assert "came from a file, not from `config/decision.yaml`" in md
    assert "N = 2 year(s)" in md
    assert "| 1 | -30.0% | 20.0% | -15.0% | 1.0% | 9.0% |" in md
    assert "| 2 | -10.0% | 10.0% | -10.0% | 2.0% | 8.0% |" in md
    assert "mix as given: A 80%, TCASH 20%" in md
    assert f"decision.yaml sha256: `{report['decision_sha256']}`" in md
    assert f"core_candidates.yaml sha256: `{report['candidates_sha256']}`" in md
    assert f"stress.yaml sha256: `{'cd' * 32}`" in md
    assert "data: up to 2018-12-31 only" in md
    assert "2 year(s) longer than the report's" in md
    for phrase in (
        "QQQ is treated as SPY",
        "midpoint of the `long_bonds` and `short_bonds`",
        "rebalanced daily, with no costs",
        "`short_bonds` in the stretch and CPI plus +1% real after it",
        "made up",
        "rescaled",
        "purchase cost",
        "CASH here is SHY",
    ):
        assert phrase in md
    assert "### Withdrawal rate 4.0% per year" in md
    assert "below peak at end" not in md
    assert "$" not in md


def test_render_rows_show_shocked_then_no_shock(report):
    md = render_shock(report, GIVEN)
    lines = md.splitlines()
    rows = {r["portfolio"]: r for r in report["rows"]}
    a = rows["A"]
    line = next(x for x in lines if x.startswith(f"| A ({a['state']}) |"))
    s, b = a["shocked"], a["no_shock"]
    assert f"{pct(s['first']['end_real'])} (no shock: {pct(b['first']['end_real'])})" in line
    wy = s["worst_year"]
    assert f"{wy + 2}, {s['horizons'][wy]} y ({pct(s['worst_end_real'])})" in line
    assert f"{s['worst5_year'] + 2}, {s['horizon_years']} y" in line
    assert f"(no shock: {b['worst_year']}, {b['horizons'][b['worst_year']]} y" in line
    assert any(x.startswith("| D |") for x in lines)
    assert any(x.startswith(f"| MIX-TCASH ({rows['MIX-TCASH']['state']}) |") for x in lines)


def test_render_lists_every_state_of_a_switching_row(report):
    lines = render_shock(report, GIVEN).splitlines()
    a = next(r for r in report["rows"] if r["portfolio"] == "A")
    for state in ("risk_on", "risk_off"):
        assert any(x.startswith(f"| A | {state} |") for x in lines)
    headlined = next(x for x in lines if x.startswith(f"| A | {a['state']} |"))
    assert headlined.endswith("| yes |")


def test_render_is_deterministic_and_has_no_mix_lines_without_a_mix(report):
    assert render_shock(report, GIVEN) == render_shock(report, GIVEN)
    assert "mix as given" not in render_shock(report, None)


def test_summary_lines(report, tmp_path):
    path = tmp_path / "x.md"
    lines = summary_lines(report, path)
    assert lines[:2] == ["shock: t2, N = 2 year(s)", f"wrote: {path}"]
    assert [x.split(",")[0] for x in lines[2:]] == ["MIX", "MIX-TCASH", "A", "CASH"]
    assert all("(no shock: " in x for x in lines[2:])
    a = next(r for r in report["rows"] if r["portfolio"] == "A")
    assert f"({a['state']})" in lines[4]
