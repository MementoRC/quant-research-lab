"""Defensive-sleeve comparison (spec: docs/methodology/defensive-sleeve.md):
the A80 blends in config/decision.yaml, the longrun pin, the research-period
return rows and their report section. Offline: synthetic prices and fixture
configs only (never market data); research period only."""

from __future__ import annotations

import copy
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from decision_helpers import (
    CANDIDATES,
    END,
    GOOD_SLEEVE,
    ROOT,
    cpi,
    criteria,
    load,
    prices,
    stress_cfg,
)
from test_decision_report import _hand_report

from qrl import decision
from qrl.decision import portfolio_returns, return_rows, run_decision
from qrl.decision_config import load_decision_config, portfolio_states
from qrl.decision_report import _header, _notes, render_markdown
from qrl.longrun import CASH_ASSUMPTION, load_longrun_config
from qrl.longrun_report import render_markdown as render_longrun
from qrl.metrics import compute_metrics

SLEEVES = {
    "CASH": {"SHY": 1.0},
    "IEF": {"IEF": 1.0},
    "TLT": {"TLT": 1.0},
    "BONDS": {"SHY": 1 / 3, "IEF": 1 / 3, "TLT": 1 / 3},
    "RSP": {"RSP": 1.0},
}
A80 = ["A80-CASH20", "A80-IEF20", "A80-TLT20", "A80-BONDS20", "A80-RSP20"]


def _shipped():
    return load_decision_config(ROOT / "config" / "decision.yaml", CANDIDATES, stress_cfg(), END)


def test_shipped_sleeve_statics_hold_their_funds():
    by_id = {p.id: p for p in _shipped().portfolios}
    for sid, mix in SLEEVES.items():
        states = portfolio_states(by_id[sid])
        assert list(states) == ["static"], sid
        assert states["static"] == pytest.approx(mix, abs=1e-12), sid
        assert sum(states["static"].values()) == pytest.approx(1.0, abs=1e-9), sid


def test_shipped_a80_blends_hold_80_percent_a_and_20_percent_sleeve():
    by_id = {p.id: p for p in _shipped().portfolios}
    a_states = portfolio_states(by_id["A"])
    assert set(a_states) == {"risk_on", "risk_off"}
    for sid, sleeve in SLEEVES.items():
        blend = by_id[f"A80-{sid}20"]
        assert blend.label == f"80% A + 20% {sid}"
        assert [(c.id, share) for c, share in blend.parts] == [("A", 0.8), (sid, 0.2)]
        states = portfolio_states(blend)
        assert set(states) == set(a_states)
        for name, a_mix in a_states.items():
            expected: dict[str, float] = {}
            for mix, share in ((a_mix, 0.8), (sleeve, 0.2)):
                for ticker, weight in mix.items():
                    expected[ticker] = expected.get(ticker, 0.0) + share * weight
            assert states[name] == pytest.approx(expected, abs=1e-12), (sid, name)
            assert sum(states[name].values()) == pytest.approx(1.0, abs=1e-9), (sid, name)


def test_shipped_decision_config_counts_21_portfolios_with_five_a80_rows():
    ids = [p.id for p in _shipped().portfolios]
    assert len(ids) == 27
    assert [i for i in ids if i.startswith("A80-")] == A80


def test_shipped_longrun_pin_matches_shipped_decision_config():
    lcfg = load_longrun_config(ROOT / "config" / "longrun.yaml", _shipped().sha256)
    assert (lcfg.seed, lcfg.n_paths, lcfg.block_months, lcfg.horizon_years) == (
        20261008,
        10000,
        12,
        30,
    )
    assert lcfg.real_floor == 0.5
    assert lcfg.rates == [0.02, 0.033, 0.04, 0.05]
    assert lcfg.cash_real_yield == 0.01


FIRST = pd.Timestamp("2005-01-03")  # first synthetic trading day on/after 2005-01-01
SMALL_IDS = ("A", "CASH", "A80-CASH20", "A80-BONDS20")


@pytest.fixture(scope="module")
def small(tmp_path_factory):
    cfg = load(tmp_path_factory.mktemp("sleeve"), GOOD_SLEEVE)
    by_id = {p.id: p for p in cfg.portfolios}
    return replace(cfg, portfolios=[by_id[i] for i in SMALL_IDS], start_years=[2005])


def test_return_rows_match_compute_metrics(small):
    data = prices()
    rows = return_rows(small, data, criteria())
    assert [r["portfolio"] for r in rows] == list(SMALL_IDS)
    cut = {k: v.loc[:END] for k, v in data.items()}
    by_id = {p.id: p for p in small.portfolios}
    expected = {i: compute_metrics(portfolio_returns(by_id[i], cut, FIRST, 5.0)) for i in SMALL_IDS}
    for r in rows:
        m = expected[r["portfolio"]]
        assert set(r) == {"portfolio", "cagr", "max_drawdown", "lost_return"}
        assert r["cagr"] == pytest.approx(m["cagr"], abs=1e-12)
        assert r["max_drawdown"] == pytest.approx(m["max_drawdown"], abs=1e-12)
        assert r["max_drawdown"] > 0  # positive, as metrics.py returns it
        assert r["lost_return"] == pytest.approx(expected["A"]["cagr"] - m["cagr"], abs=1e-12)
    assert rows[0]["lost_return"] == 0.0


def test_return_rows_start_at_the_research_start_and_stop_at_the_data_end(small, monkeypatch):
    seen = []
    real = decision.portfolio_returns

    def spy(p, data, start, cost_bps):
        seen.append((start, data["close"].index[-1], data["open"].index[-1], cost_bps))
        return real(p, data, start, cost_bps)

    monkeypatch.setattr(decision, "portfolio_returns", spy)
    return_rows(small, prices(), criteria())
    assert len(seen) == len(SMALL_IDS)
    assert all(s == (FIRST, END, END, 5.0) for s in seen)


def test_return_rows_ignore_data_after_the_data_end(small):
    data = prices()
    after = np.asarray(data["close"].index > END)
    rng = np.random.default_rng(5)
    poisoned = {
        k: v * np.where(after[:, None], rng.uniform(0.2, 5.0, v.shape), 1.0)
        for k, v in data.items()
    }
    assert not poisoned["close"].equals(data["close"])
    assert return_rows(small, poisoned, criteria()) == return_rows(small, data, criteria())


def test_return_rows_lost_return_is_none_without_a(small):
    no_a = replace(small, portfolios=[p for p in small.portfolios if p.id != "A"])
    rows = return_rows(no_a, prices(), criteria())
    assert [r["portfolio"] for r in rows] == list(SMALL_IDS[1:])
    assert all(r["lost_return"] is None for r in rows)


def test_return_rows_refuse_a_research_period_without_start(small):
    crit = copy.deepcopy(criteria())
    crit["periods"]["research"]["start"] = None
    with pytest.raises(ValueError, match="research period has no start"):
        return_rows(small, prices(), crit)


def test_run_decision_carries_the_return_rows(small):
    data, crit = prices(), criteria()
    report = run_decision(small, data, cpi(), crit, "cd" * 32)
    assert report["returns"] == return_rows(small, data, crit)


RETURN_HEAD = "## Research-period return (2005-2018, no withdrawals)"
DOTCOM_SLEEVE = (
    "IEF, TLT and BONDS are, like CASH, entirely cash in `dotcom_2000` (0% loss), so the "
    "A80-CASH20, A80-IEF20, A80-TLT20 and A80-BONDS20 frozen cells are identical there and "
    "that window cannot tell the bond sleeves apart; A80-RSP20 uses the SPY proxy."
)
ALL_IDS = [
    *"ABCDEFG",
    "CASH",
    "G-EW",
    "IEF",
    "TLT",
    "RSP",
    "BONDS",
    "AG",
    "G-CASH",
    "A-CASH",
    *A80,
]


def _returns() -> list[dict]:
    return [
        {"portfolio": "A", "cagr": 0.12, "max_drawdown": 0.256, "lost_return": 0.0},
        {"portfolio": "A80-CASH20", "cagr": 0.1, "max_drawdown": 0.2, "lost_return": 0.02},
        {"portfolio": "RSP", "cagr": 0.125, "max_drawdown": 0.5, "lost_return": -0.005},
    ]


def test_return_section_renders_cagr_drawdown_and_gap_to_a():
    lines = render_markdown(_hand_report(returns=_returns())).splitlines()
    assert RETURN_HEAD in lines
    assert "| Portfolio | CAGR | Max drawdown (from start) | CAGR given up vs A |" in lines
    assert "| A | 12.0% | 25.6% | 0.0 pp |" in lines
    assert "| A80-CASH20 | 10.0% | 20.0% | 2.0 pp |" in lines
    assert "| RSP | 12.5% | 50.0% | -0.5 pp |" in lines
    heads = [ln for ln in lines if ln.startswith("## ")]
    assert heads.index(RETURN_HEAD) == heads.index("## Portfolios (100% of capital)") + 1
    assert heads.index(RETURN_HEAD) == heads.index("## Historical windows") - 1


def test_return_section_shows_n_a_without_a():
    rows = [{"portfolio": "CASH", "cagr": 0.01, "max_drawdown": 0.02, "lost_return": None}]
    assert (
        "| CASH | 1.0% | 2.0% | n/a |" in render_markdown(_hand_report(returns=rows)).splitlines()
    )


def test_return_section_is_omitted_when_returns_absent_or_empty():
    assert RETURN_HEAD not in render_markdown(_hand_report())
    assert RETURN_HEAD not in render_markdown(_hand_report(returns=[]))


def _with_a80():
    year_one = [
        {
            "portfolio": i,
            "scenario": "shock",
            "state": "static",
            "rate": 0.04,
            "nominal": 0.9,
            "real": 0.85,
        }
        for i in ALL_IDS
    ]
    return _hand_report(
        portfolios=[{"id": i, "label": i, "states": {}} for i in ALL_IDS], year_one=year_one
    )


def test_dotcom_note_tells_that_the_bond_sleeves_are_identical_there():
    md = render_markdown(_with_a80())
    assert md.count(DOTCOM_SLEEVE) == 1
    assert md.count("(0% loss by construction). IEF, TLT and BONDS are, like CASH,") == 1


def test_dotcom_sleeve_sentence_is_absent_without_a80_rows():
    md = render_markdown(_hand_report())
    assert "A80-" not in md
    assert "cannot tell the bond sleeves apart" not in md
    assert "are mostly proxied" not in md


def _window_row(portfolio: str, window: str, indicative: bool, unavailable=None) -> dict:
    return {
        "portfolio": portfolio,
        "window": window,
        "mode": "frozen",
        "loss": 0.1,
        "proxied_share": {"equity": 0.0, "gold": 0.0, "bonds": 0.0},
        "indicative": indicative,
        "unavailable": unavailable,
    }


def test_mostly_proxied_sentence_names_exactly_the_flagged_dotcom_portfolios():
    windows = [
        _window_row("P", "dotcom_2000", True),
        _window_row("Q", "dotcom_2000", False),
        _window_row("R", "dotcom_2000", True, unavailable="no data"),
        _window_row("S", "w1", True),
        _window_row("T", "dotcom_2000", True),
        _window_row("P", "dotcom_2000", True),
    ]
    md = render_markdown(_hand_report(windows=windows))
    assert "(0% loss by construction) and P and T are mostly proxied." in md
    assert "G-CASH" not in md


def test_mostly_proxied_sentence_is_absent_without_flagged_dotcom_rows():
    windows = [_window_row("Q", "dotcom_2000", False), _window_row("S", "w1", True)]
    assert "are mostly proxied" not in render_markdown(_hand_report(windows=windows))


def _stated(pid: str, n_states: int) -> dict:
    states = {"risk_on": {"SPY": 1.0}, "risk_off": {"SHY": 1.0}}
    return {"id": pid, "label": pid, "states": dict(list(states.items())[:n_states])}


def test_switching_note_names_exactly_the_portfolios_with_several_states():
    portfolios = [_stated("X", 2), _stated("Y", 1), _stated("Z", 2)]
    text = "\n".join(_notes(_hand_report(portfolios=portfolios)))
    assert "- Switching portfolios (X and Z) are shown in both states" in text
    assert "A, B, C, F" not in text


def test_switching_note_is_absent_without_multi_state_portfolios():
    text = "\n".join(_notes(_hand_report(portfolios=[_stated("Y", 1)])))
    assert "Switching portfolios (" not in text


def test_shy_baseline_note_is_shown_only_with_a80_rows():
    note = (
        "- CASH here is SHY, not true cash: SHY's near-zero 2009-2015 yields make the "
        "A80-CASH20 baseline look worse than cash at today's rates"
    )
    assert note in _header(_with_a80())
    assert not any("near-zero" in ln for ln in _header(_hand_report()))


def test_header_sleeve_note_counts_by_products_and_a80_rows():
    rep = _hand_report(portfolios=[{"id": i, "label": i, "states": {}} for i in ALL_IDS])
    lines = _header(rep)
    assert any("7 in the core comparison, 21 here (A-G again plus 14 new)" in ln for ln in lines)
    assert (
        "- of the 21 portfolios here, 4 are by-product rows, each a sleeve held alone "
        "(IEF, TLT, RSP, BONDS); only the 5 A80 rows (A80-CASH20, A80-IEF20, A80-TLT20, "
        "A80-BONDS20, A80-RSP20) answer the defensive-sleeve question "
        "(docs/methodology/defensive-sleeve.md)"
    ) in lines


def test_header_sleeve_note_is_absent_without_a80_rows():
    assert not any("defensive-sleeve" in ln for ln in _header(_hand_report()))


def _longrun_report(names: list[str]) -> dict:
    row = {
        "depleted_by": {20: 0.0, 25: 0.0, 30: 0.0},
        "median_depletion_year": None,
        "below_floor": 0.0,
        "end_real_median": 1.0,
        "end_real_p5": 0.5,
    }
    return {
        "data_end": "2018-12-31",
        "first_month": "2005-01",
        "last_month": "2018-12",
        "n_months": 168,
        "seed": 1,
        "n_paths": 10,
        "block_months": 12,
        "horizon_years": 30,
        "real_floor": 0.5,
        "cash_real_yield": 0.01,
        "rates": [0.04],
        "longrun_sha256": "ab" * 32,
        "decision_sha256": "cd" * 32,
        "cost_bps": 5.0,
        "rows": [{"rate": 0.04, "portfolio": n, **row} for n in names],
    }


def test_longrun_header_sleeve_note_counts_22_rows():
    names = ALL_IDS[:8] + [CASH_ASSUMPTION] + ALL_IDS[8:]
    text = render_longrun(_longrun_report(names))
    assert (
        f"- 22 rows per withdrawal rate, including the {CASH_ASSUMPTION} row and 4 by-product "
        "rows (IEF, TLT, RSP, BONDS); only the 5 A80 rows answer the defensive-sleeve "
        "question (docs/methodology/defensive-sleeve.md)"
    ) in text.splitlines()
    assert text.index("defensive-sleeve question") < text.index("## How to read this")


def test_longrun_header_sleeve_note_is_absent_without_a80_rows():
    text = render_longrun(_longrun_report(["CASH", CASH_ASSUMPTION, "G"]))
    assert "defensive-sleeve" not in text
