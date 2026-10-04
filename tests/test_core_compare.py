"""Tests for the core-comparison exploration (qrl.core_compare,
scripts/core_compare.py). Offline; synthetic prices only.
Spec: docs/superpowers/specs/2026-10-03-core-compare-design.md.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qrl import core_compare
from qrl.core_compare import (
    Candidate,
    load_core_candidates,
    research_metrics,
    run_core_compare,
    split_windows,
)
from qrl.criteria import load_criteria
from qrl.data import synthetic_prices
from qrl.stress import Window, load_stress_config

ROOT = Path(__file__).resolve().parents[1]
HOLDOUT = pd.Timestamp("2023-01-01")
SPLIT = {"core": 0.8, "sleeve": 0.2}
TICKERS = ["SPY", "QQQ", "GLD", "IEF", "TLT", "SHY"]
STATIC = Candidate("T", "static", "core_mix", {"risk_on": {"SPY": 0.6, "IEF": 0.4}})


def _criteria() -> dict:
    return load_criteria(ROOT / "config" / "criteria.yaml")[0]


def _data(start: str = "1999-01-01", end: str = "2021-12-31") -> dict[str, pd.DataFrame]:
    open_, close = synthetic_prices(TICKERS, start=start, end=end)
    return {"open": open_, "close": close}


GOOD = """
version: 1
candidates:
  - {id: T1, label: "trend", fn: core_trend, params: {risk_on: SPY, risk_off: IEF, lookback: 5}}
  - {id: T2, label: "static", fn: core_mix, params: {risk_on: {SPY: 0.6, IEF: 0.4}}}
"""


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "core_candidates.yaml"
    p.write_text(text)
    return p


def test_core_compare_shipped_candidates_load():
    cands, digest = load_core_candidates(ROOT / "config" / "core_candidates.yaml")
    assert [c.id for c in cands] == list("ABCDEFG")
    assert len(digest) == 64  # full sha256
    by_id = {c.id: c for c in cands}
    assert by_id["A"].fn == "core_trend"
    assert by_id["A"].params == {"risk_on": "QQQ", "risk_off": "GLD", "lookback": 200}
    assert by_id["C"].params["risk_off"] == "IEF"
    assert by_id["D"].fn == "core_mix"
    assert "risk_off" not in by_id["D"].params
    assert by_id["F"].params["signal"] == "SPY"


def test_core_compare_rejects_duplicate_ids(tmp_path):
    with pytest.raises(ValueError, match="duplicate"):
        load_core_candidates(_write(tmp_path, GOOD.replace("id: T2", "id: T1")))


def test_core_compare_rejects_unknown_fn(tmp_path):
    with pytest.raises(ValueError, match="fn must be"):
        load_core_candidates(_write(tmp_path, GOOD.replace("fn: core_mix", "fn: buy_and_hold")))


def test_core_compare_rejects_cash_risk_off(tmp_path):
    with pytest.raises(ValueError, match="CASH"):
        load_core_candidates(_write(tmp_path, GOOD.replace("risk_off: IEF", "risk_off: CASH")))


def test_core_compare_rejects_empty_candidates(tmp_path):
    with pytest.raises(ValueError, match="non-empty"):
        load_core_candidates(_write(tmp_path, "version: 1\ncandidates: []\n"))


def test_core_compare_rejects_params_the_strategy_rejects(tmp_path):
    with pytest.raises(ValueError, match="above 1"):
        load_core_candidates(_write(tmp_path, GOOD.replace("IEF: 0.4", "IEF: 0.9")))


def test_core_compare_rejects_bad_id(tmp_path):
    # quoted: an unquoted `T[1]` would be a YAML syntax error, not a bad id
    with pytest.raises(ValueError, match="id"):
        load_core_candidates(_write(tmp_path, GOOD.replace("id: T1", 'id: "T[1]"')))


def test_core_compare_rejects_malformed_yaml(tmp_path):
    with pytest.raises(ValueError, match="valid YAML"):
        load_core_candidates(_write(tmp_path, "version: 1\ncandidates: [unclosed\n"))


def test_core_compare_rejects_non_mapping_params(tmp_path):
    text = GOOD.replace("params: {risk_on: SPY, risk_off: IEF, lookback: 5}", "params: [SPY]")
    with pytest.raises(ValueError, match="mapping"):
        load_core_candidates(_write(tmp_path, text))


def test_core_compare_split_windows_drops_validation_overlap():
    cfg, _ = load_stress_config(ROOT / "config" / "stress.yaml", HOLDOUT)
    kept, excluded = split_windows(cfg.windows, _criteria())
    assert [w.name for w in kept] == ["dotcom_2000", "gfc_2008"]
    assert [w.name for w in excluded] == ["covid_2020", "inflation_2022"]


def test_core_compare_split_windows_drops_holdout_overlap():
    early = Window("early", pd.Timestamp("2018-01-02"), pd.Timestamp("2018-12-31"), True)
    straddle = Window("straddle", pd.Timestamp("2018-06-01"), pd.Timestamp("2019-02-01"), True)
    late = Window("late", pd.Timestamp("2023-02-01"), pd.Timestamp("2023-03-01"), False)
    kept, excluded = split_windows([early, straddle, late], _criteria())
    assert [w.name for w in kept] == ["early"]
    assert [w.name for w in excluded] == ["straddle", "late"]


def test_core_compare_research_metrics_ignore_later_data():
    data = _data()
    factor = np.where(data["close"].index <= pd.Timestamp("2018-12-31"), 1.0, 5.0)
    poisoned = {k: v.mul(factor, axis=0) for k, v in data.items()}
    assert research_metrics(STATIC, data, _criteria(), SPLIT) == research_metrics(
        STATIC, poisoned, _criteria(), SPLIT
    )


def test_core_compare_research_metrics_stay_inside_research_period():
    m = research_metrics(STATIC, _data(), _criteria(), SPLIT)
    assert m["start"] >= "2005-01-01"
    assert m["end"] <= "2018-12-31"
    assert {"cagr", "sharpe", "max_drawdown", "turnover_per_year"} <= m.keys()


def test_core_compare_research_metrics_reject_unwarmed_candidate():
    late = _data(start="2005-02-01")  # first valid weight is after the research start
    with pytest.raises(ValueError, match="research start"):
        research_metrics(STATIC, late, _criteria(), SPLIT)


ALLOWED_SCENARIOS = {
    "dotcom_2000",
    "gfc_2008",
    "no_safe_haven",
    "stagflation",
    "energy_shock_severe",
    "tech_crash",
}


@pytest.fixture(scope="module")
def compared():
    cands, _ = load_core_candidates(ROOT / "config" / "core_candidates.yaml")
    cfg, _ = load_stress_config(ROOT / "config" / "stress.yaml", HOLDOUT)
    seen: dict = {}
    real = core_compare.run_stress

    def spy(cfg_, portfolios, data, max_drawdown, criteria):
        seen["last_row"] = data["close"].index.max()
        seen["windows"] = [w.name for w in cfg_.windows]
        return real(cfg_, portfolios, data, max_drawdown, criteria)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(core_compare, "run_stress", spy)
        out = run_core_compare(cands, cfg, _data(), _criteria(), SPLIT, 0.35)
    return out, seen


def test_core_compare_stress_never_sees_validation(compared):
    out, seen = compared
    assert seen["last_row"] <= pd.Timestamp("2018-12-31")
    assert seen["windows"] == ["dotcom_2000", "gfc_2008"]
    assert out["excluded_windows"] == ["covid_2020", "inflation_2022"]
    scenarios = {cell["scenario"] for c in out["candidates"] for cell in c["cells"]}
    assert scenarios == ALLOWED_SCENARIOS


def test_core_compare_every_candidate_recorded(compared):
    out, _ = compared
    assert [c["id"] for c in out["candidates"]] == list("ABCDEFG")
    for c in out["candidates"]:
        assert {"cagr", "sharpe", "max_drawdown"} <= c["research"].keys()
        assert c["breach_count"] == c["stress_breaches"] + int(c["research_breach"])


def test_core_compare_switching_candidates_split_into_branches(compared):
    out, _ = compared
    by_id = {c["id"]: c["cells"] for c in out["candidates"]}

    def modes(cells, portfolio):
        return {c["mode"] for c in cells if c["portfolio"] == portfolio}

    assert {c["portfolio"] for c in by_id["F"]} == {"F", "F[risk_on]", "F[risk_off]"}
    assert modes(by_id["F"], "F") == {"replay"}
    assert modes(by_id["F"], "F[risk_on]") == {"frozen", "hypothetical"}
    assert modes(by_id["F"], "F[risk_off]") == {"frozen", "hypothetical"}
    assert {c["portfolio"] for c in by_id["D"]} == {"D"}
    assert modes(by_id["D"], "D") == {"replay", "frozen", "hypothetical"}
    assert {c["portfolio"] for c in by_id["A"]} == {"A", "A[risk_on]", "A[risk_off]"}
