"""Report assembly and markdown (qrl.decision.run_decision,
qrl.decision_report). Offline; synthetic data. Spec:
docs/methodology/decision-helper.md."""

from __future__ import annotations

import copy
from dataclasses import replace

import pytest
from decision_helpers import CANDIDATES_SHA, cpi, criteria, load, prices

from qrl.decision import run_decision
from qrl.decision_report import render_markdown


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    cfg = load(tmp_path_factory.mktemp("decision"))
    quick = replace(cfg, start_years=[2005, 2006])  # all ten years run in the sealing test
    return run_decision(quick, prices(), cpi(), criteria(), "cd" * 32)


def _metrics(**over) -> dict:
    base = {
        "end_nominal": 1.2,
        "end_real": 0.9,
        "lowest": 0.5,
        "max_drawdown": 0.146,
        "below_peak_months": 7,
        "recovered": True,
        "below_peak_at_end": False,
        "depleted": None,
    }
    return base | over


def _hand_report(**over) -> dict:
    """A tiny hand-built report: one switching portfolio, one scenario, one rate."""
    rep = {
        "data_end": "2018-12-31",
        "decision_sha256": "d1" * 32,
        "candidates_sha256": "c1" * 32,
        "stress_sha256": "e1" * 32,
        "candidate_count": 7,
        "cost_bps": 10.0,
        "engine_cost_bps": 5.0,
        "proxied_threshold": 0.25,
        "rates": [0.04],
        "start_years": [2005, 2006],
        "portfolios": [
            {
                "id": "X",
                "label": "test mix",
                "states": {"risk_on": {"SPY": 1.0}, "risk_off": {"SHY": 1.0}},
            }
        ],
        "scenarios": [
            {
                "name": "shock",
                "label": "judgement-based, v1",
                "returns": {"SPY": -0.146, "SHY": 0.01},
                "inflation": 0.05,
            }
        ],
        "windows": [
            {
                "portfolio": "X",
                "window": "w1",
                "mode": "frozen",
                "loss": 0.146,
                "proxied_share": {"equity": 0.0, "gold": 0.0, "bonds": 0.0},
                "indicative": False,
                "unavailable": None,
            }
        ],
        "scenario_rows": [
            {
                "portfolio": "X",
                "scenario": "shock",
                "label": "judgement-based, v1",
                "states": {
                    "risk_on": {"nominal_loss": 0.146, "real_loss": 0.19},
                    "risk_off": {"nominal_loss": -0.01, "real_loss": 0.04},
                },
                "worst": "risk_on",
            }
        ],
        "withdrawals": [
            {
                "portfolio": "X",
                "rate": 0.04,
                "first_year": 2005,
                "first": _metrics(),
                "worst_year": 2006,
                "worst_end_real": 0.8,
                "per_year": {},
            }
        ],
        "year_one": [
            {
                "portfolio": "X",
                "scenario": "shock",
                "state": "risk_on",
                "rate": 0.04,
                "nominal": 0.814,
                "real": 0.775,
            }
        ],
    }
    return rep | over


def test_decision_report_has_no_dollar_amounts(report):
    assert "$" not in render_markdown(report)


def test_decision_report_is_deterministic(report):
    assert render_markdown(report) == render_markdown(copy.deepcopy(report))


def test_decision_report_sections_in_order(report):
    heads = [ln for ln in render_markdown(report).splitlines() if ln.startswith("## ")]
    assert heads == [
        "## Notes",
        "## Portfolios (100% of capital)",
        "## Historical windows",
        "## Judgement-based scenarios (one year)",
        "## Withdrawals",
        "## Year-one scenario hit",
    ]


def test_decision_report_records_hashes_and_disclosures(report):
    md = render_markdown(report)
    assert report["decision_sha256"] in md
    assert CANDIDATES_SHA in md
    assert "cd" * 32 in md
    assert "7 in the core comparison, 12 here" in md
    assert "judgement-based, v1" in md
    assert "selects nothing and recommends nothing" in md
    assert "up to 2018-12-31 only" in md
    assert "### Withdrawal rate 3.3% per year" in md


def test_decision_report_has_every_required_note(report):
    notes = render_markdown(report).split("## Portfolios")[0]
    assert "rebalanced daily" in notes
    assert "less frequent" in notes
    assert "smoother than practice" in notes
    assert "engine's default of 5 bps" in notes
    assert "10 bps" in render_markdown(_hand_report())  # withdrawal paths: criteria cost_bps
    assert "dot-com window" in notes
    assert "RSP, GLD and bonds are proxied" in notes
    assert "other than gold" in notes
    assert "dividend and interest income is not separated" in notes


def test_decision_report_shows_both_states_and_marks_the_worse(report):
    lines = render_markdown(report).splitlines()
    on = next(ln for ln in lines if ln.startswith("| A | treasury_dollar_crisis | risk_on |"))
    off = next(ln for ln in lines if ln.startswith("| A | treasury_dollar_crisis | risk_off |"))
    assert on.endswith("| worse |")
    assert not off.endswith("| worse |")


def test_decision_report_marks_indicative_and_unrecovered(report):
    def flagged(md: str) -> bool:
        return any(
            ln.startswith("|") and "mostly proxied, indicative only" in ln for ln in md.splitlines()
        )

    assert not flagged(render_markdown(report))  # synthetic prices cover every fund in 2000
    rep = copy.deepcopy(report)
    rep["windows"][0]["indicative"] = True
    rep["windows"][0]["proxied_share"] = {"equity": 0.0, "gold": 0.25, "bonds": 0.5}
    rep["withdrawals"][0]["first"]["recovered"] = False
    rep["withdrawals"][0]["first"]["below_peak_months"] = 30
    md = render_markdown(rep)
    assert flagged(md)
    assert "bonds 50%, gold 25%" in md
    assert "at least 30 months, not recovered" in md


def test_decision_report_hand_built_cells_render_exactly():
    lines = render_markdown(_hand_report()).splitlines()
    assert "| X | w1 | frozen | 14.6% |  |  |" in lines
    assert "| X | shock | risk_on | 14.6% | 19.0% | worse |" in lines
    assert "| X | shock | risk_off | -1.0% | 4.0% |  |" in lines
    withdrawal = next(ln for ln in lines if ln.startswith("| X | 90.0% |"))
    assert withdrawal == "| X | 90.0% | 50.0% | 14.6% | 7 months | no | no | 2006 (80.0%) |"
    assert "| X (risk_on) | 81.4% / 77.5% |" in lines


def test_decision_report_flag_follows_the_indicative_field_only():
    def flagged(share: float, indicative: bool) -> bool:
        rep = _hand_report()
        rep["windows"][0]["proxied_share"] = {"equity": share}
        rep["windows"][0]["indicative"] = indicative
        return any(
            ln.startswith("| X | w1") and "mostly proxied, indicative only" in ln
            for ln in render_markdown(rep).splitlines()
        )

    assert flagged(0.0, True)  # flag with no shares: the renderer does not recompute
    assert not flagged(0.9, False)  # big shares but not indicative: no flag


def test_decision_report_engine_cost_note_uses_the_report_value():
    assert "engine's default of 3 bps" in render_markdown(_hand_report(engine_cost_bps=3.0))
    assert "5 bps" not in render_markdown(_hand_report(engine_cost_bps=3.0))


def test_decision_report_dotcom_note_is_not_repeated():
    md = render_markdown(_hand_report())
    assert md.count("RSP, GLD and bonds") <= 1


def test_decision_report_year_one_names_the_worse_state_for_switching_only():
    rep = _hand_report()
    rep["portfolios"].append({"id": "S", "label": "static", "states": {"static": {"SPY": 1.0}}})
    rep["year_one"].append(
        {
            "portfolio": "S",
            "scenario": "shock",
            "state": "static",
            "rate": 0.04,
            "nominal": 0.9,
            "real": 0.85,
        }
    )
    lines = render_markdown(rep).splitlines()
    assert "| X (risk_on) | 81.4% / 77.5% |" in lines
    assert "| S | 90.0% / 85.0% |" in lines


def test_decision_report_negative_zero_percent_renders_as_zero():
    rep = _hand_report()
    rep["scenario_rows"][0]["states"]["risk_off"]["nominal_loss"] = -0.0004
    assert "| X | shock | risk_off | 0.0% | 4.0% |  |" in render_markdown(rep).splitlines()


def test_decision_report_exactly_zero_year_one_is_marked_depleted():
    rep = _hand_report()
    rep["year_one"][0] |= {"nominal": 0.0, "real": 0.0}
    assert "0.0% / 0.0% (depleted within year one)" in render_markdown(rep)


def test_decision_report_unrecovered_text_only_for_the_unrecovered_case():
    ok = render_markdown(_hand_report())
    assert "not recovered" not in ok
    rep = _hand_report()
    rep["withdrawals"][0]["first"] = _metrics(recovered=False, below_peak_months=30)
    bad = render_markdown(rep)
    assert "at least 30 months, not recovered" in bad


def test_decision_report_below_peak_at_end_and_depletion_columns():
    rep = _hand_report()
    rep["withdrawals"][0]["first"] = _metrics(below_peak_at_end=True, depleted="2011-03")
    md = render_markdown(rep)
    assert "below peak at end" in md
    assert "| X | 90.0% | 50.0% | 14.6% | 7 months | yes | 2011-03 | 2006 (80.0%) |" in md


def test_decision_report_negative_year_one_is_shown_and_marked_depleted():
    rep = _hand_report()
    rep["year_one"][0] |= {"nominal": -0.05, "real": -0.0476}
    md = render_markdown(rep)
    assert "-5.0% / -4.8% (depleted within year one)" in md
    assert "81.4%" not in md
    assert "(depleted within year one)" not in render_markdown(_hand_report())
