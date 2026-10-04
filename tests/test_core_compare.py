"""Tests for the core-comparison exploration (qrl.core_compare,
scripts/core_compare.py). Offline; synthetic prices only.
Spec: docs/superpowers/specs/2026-10-03-core-compare-design.md.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qrl import core_compare
from qrl.core_compare import (
    Candidate,
    load_core_candidates,
    render_markdown,
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


def test_core_compare_research_frames_are_cut_at_research_end(monkeypatch):
    seen: dict = {}
    real_weights, real_bt = core_compare.candidate_weights, core_compare.run_backtest

    def spy_weights(cand, close):
        seen["weights"] = close.index.max()
        return real_weights(cand, close)

    def spy_bt(open_, close, weights, **kw):
        seen["backtest"] = (open_.index.max(), close.index.max(), weights.index.max())
        return real_bt(open_, close, weights, **kw)

    monkeypatch.setattr(core_compare, "candidate_weights", spy_weights)
    monkeypatch.setattr(core_compare, "run_backtest", spy_bt)
    research_metrics(STATIC, _data(), _criteria(), SPLIT)
    rend = pd.Timestamp("2018-12-31")
    assert seen["weights"] <= rend
    assert all(ts <= rend for ts in seen["backtest"])


def test_core_compare_research_gld_late_start_never_silently_shortened():
    data = _data()
    gld_start = pd.Timestamp("2004-11-18")
    for k in data:
        data[k] = data[k].copy()
        data[k].loc[data[k].index < gld_start, "GLD"] = np.nan
    cand = Candidate(
        "A", "trend", "core_trend", {"risk_on": "QQQ", "risk_off": "GLD", "lookback": 200}
    )
    try:
        m = research_metrics(cand, data, _criteria(), SPLIT)
    except ValueError:
        return  # an error row is acceptable
    assert m["start"] <= "2005-01-10"  # full research period, not a shortened one


def test_core_compare_research_rejects_nan_weights_in_research_period(monkeypatch):
    real = core_compare.candidate_weights

    def holey(cand, close):
        w = real(cand, close).copy()
        w.iloc[w.index.get_indexer([pd.Timestamp("2010-06-01")], method="bfill")[0], :] = np.nan
        return w

    monkeypatch.setattr(core_compare, "candidate_weights", holey)
    with pytest.raises(ValueError, match="NaN"):
        research_metrics(STATIC, _data(), _criteria(), SPLIT)


def test_core_compare_research_rejects_metrics_without_cagr(monkeypatch):
    monkeypatch.setattr(core_compare, "compute_metrics", lambda *a, **k: {"days": 1})
    with pytest.raises(ValueError, match="too few"):
        research_metrics(STATIC, _data(), _criteria(), SPLIT)


def test_core_compare_error_row_for_candidate_without_cagr(monkeypatch):
    monkeypatch.setattr(core_compare, "compute_metrics", lambda *a, **k: {"days": 1})
    cfg, _ = load_stress_config(ROOT / "config" / "stress.yaml", HOLDOUT)
    out = run_core_compare([STATIC], cfg, _data(), _criteria(), SPLIT, 0.35)
    assert "error" in out["candidates"][0]["research"]


def test_core_compare_markdown_footnote_explains_switching_breach_counts(compared):
    out, _ = compared
    report = {
        **out,
        "candidates_sha256": "ab" * 32,
        "stress_sha256": "cd" * 32,
        "trial_count": 7,
        "research_period": {"start": "2005-01-01", "end": "2018-12-31"},
        "max_drawdown": 0.35,
        "capital_split": SPLIT,
    }
    assert "both branch cells" in render_markdown(report)


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


def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "core_compare_cli", ROOT / "scripts" / "core_compare.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cli = _load_cli()


def test_core_compare_markdown_records_hash_and_trial_count(compared):
    out, _ = compared
    report = {
        **out,
        "candidates_sha256": "ab" * 32,
        "stress_sha256": "cd" * 32,
        "trial_count": 7,
        "research_period": {"start": "2005-01-01", "end": "2018-12-31"},
        "max_drawdown": 0.35,
        "capital_split": SPLIT,
    }
    md = render_markdown(report)
    assert "ab" * 32 in md
    assert "- trial count: 7" in md
    for cid in "ABCDEFG":
        assert f"| {cid} |" in md
    table_rows = [ln for ln in md.splitlines() if ln.startswith("|")]
    assert not any("covid_2020" in ln or "inflation_2022" in ln for ln in table_rows)
    assert "validation and holdout data never used" in md
    assert "| proxied to cash |" in md
    assert "treated as cash" in md  # footnote: the dotcom cushion is understated
    # synthetic prices cover every ticker, so inject a proxied share into one cell
    cell = report["candidates"][3]["cells"][0]  # candidate D
    cell["detail"] = {"proxied_share": {"equity": 0.0, "gold": 0.2, "bonds": 0.4}}
    row = next(ln for ln in render_markdown(report).splitlines() if "bonds 40%" in ln)
    assert row.startswith("| D |")
    assert "bonds 40%, gold 20%" in row


def _fake_ohlcv(drop: str | None = None):
    def fake(tickers, refresh=False):
        open_, close = synthetic_prices(tickers, start="1999-01-01", end="2021-12-31")
        if drop is not None:
            open_, close = open_.drop(columns=drop), close.drop(columns=drop)
        return {"open": open_, "close": close}

    return fake


def test_core_compare_main_writes_json_and_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "load_ohlcv", _fake_ohlcv())
    out_json, out_md = tmp_path / "r.json", tmp_path / "r.md"
    assert cli.main(["--out-json", str(out_json), "--out-md", str(out_md)]) == 0
    report = json.loads(out_json.read_text())
    assert report["trial_count"] == 7
    assert len(report["candidates_sha256"]) == 64
    assert [c["id"] for c in report["candidates"]] == list("ABCDEFG")
    scenarios = {cell["scenario"] for c in report["candidates"] for cell in c["cells"]}
    assert not scenarios & {"covid_2020", "inflation_2022"}
    assert "- trial count: 7" in out_md.read_text()


def test_core_compare_main_fails_on_missing_ticker(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "load_ohlcv", _fake_ohlcv(drop="IEF"))
    out_json, out_md = tmp_path / "r.json", tmp_path / "r.md"
    assert cli.main(["--out-json", str(out_json), "--out-md", str(out_md)]) == 1
    assert not out_json.exists()
    assert not out_md.exists()


def test_core_compare_main_fails_loudly_on_unpriced_candidate_ticker(tmp_path, monkeypatch, capsys):
    def fake(tickers, refresh=False):
        open_, close = synthetic_prices(tickers, start="1999-01-01", end="2021-12-31")
        close.loc[close.loc[:"2018-12-31"].index[-1], "IEF"] = float("nan")  # unpriced at the end
        return {"open": open_, "close": close}

    def boom(*args, **kwargs):
        raise AssertionError("run_core_compare must not be called")

    monkeypatch.setattr(cli, "load_ohlcv", fake)
    monkeypatch.setattr(cli, "run_core_compare", boom)
    out_json, out_md = tmp_path / "r.json", tmp_path / "r.md"
    assert cli.main(["--out-json", str(out_json), "--out-md", str(out_md)]) == 1
    assert "IEF" in capsys.readouterr().out
    assert not out_json.exists()
    assert not out_md.exists()
