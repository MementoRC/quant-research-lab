"""End-to-end test of run_history on synthetic data (offline): the real
config/history.yaml, config/decision.yaml and config/criteria.yaml, random-walk
prices, and the stand-in correlation bar disabled (independent random series)."""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qrl.criteria import load_criteria
from qrl.decision import data_end
from qrl.decision_config import load_decision_config
from qrl.history import run_history
from qrl.history_config import HistoryConfig, load_history_config
from qrl.history_data import RawData
from qrl.history_report import render_markdown
from qrl.periods import period_bounds
from qrl.stress import load_stress_config

ROOT = Path(__file__).resolve().parents[1]
END = pd.Timestamp("2018-12-31")


def _walk(index: pd.DatetimeIndex, seed: int, vol: float = 0.011) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return 100.0 * np.exp(np.cumsum(rng.normal(0.0003, vol, len(index))))


def _synthetic_raw(cfg: HistoryConfig) -> RawData:
    # every series starts at or just before its configured first date, so the
    # config's first-date checks pass (^GSPC from 1927-12-30, SPY from 1993, ...)
    days = pd.bdate_range("1927-12-30", END)
    close = pd.DataFrame(index=days, columns=list(cfg.yahoo), dtype=float)
    for i, (ticker, latest) in enumerate(cfg.yahoo.items()):
        sub = days[days >= latest - pd.Timedelta(days=3)]
        assert sub[0] <= latest
        close.loc[sub, ticker] = _walk(sub, i)
    fred = {}
    for i, (sid, latest) in enumerate(cfg.fred.items()):
        sub = days[days >= latest - pd.Timedelta(days=3)]
        rng = np.random.default_rng(100 + i)
        steps = rng.normal(0, 0.02, len(sub))
        fred[sid] = pd.Series(np.clip(5.0 + np.cumsum(steps), 0.5, None), index=sub)
    shiller = pd.date_range(cfg.shiller.max_first_date, END, freq="MS")
    worldbank = pd.date_range(cfg.worldbank.max_first_date, END, freq="MS")
    return RawData(
        open=close * 1.0005,
        close=close,
        fred=fred,
        shiller_yield=pd.Series(0.03, index=shiller),
        worldbank_gold=pd.Series(
            300.0 * np.exp(np.arange(len(worldbank)) * 0.002), index=worldbank
        ),
    )


def _inputs():
    criteria, _ = load_criteria(ROOT / "config" / "criteria.yaml")
    holdout_start, _ = period_bounds(criteria, "holdout")
    stress_cfg, _ = load_stress_config(ROOT / "config" / "stress.yaml", holdout_start)
    dcfg = load_decision_config(
        ROOT / "config" / "decision.yaml",
        ROOT / "config" / "core_candidates.yaml",
        stress_cfg,
        data_end(criteria),
    )
    hcfg = dataclasses.replace(
        load_history_config(ROOT / "config" / "history.yaml"), min_correlation=-1.0
    )
    months = pd.date_range("1960-01-31", END, freq="ME")
    cpi = pd.Series(100.0 * 1.03 ** (np.arange(len(months)) / 12), index=months)
    return criteria, dcfg, hcfg, cpi


def test_end_to_end_on_synthetic_data():
    criteria, dcfg, hcfg, cpi = _inputs()
    report = run_history(hcfg, dcfg, _synthetic_raw(hcfg), cpi, criteria)
    assert [pid for pid, _ in report.portfolios] == list(hcfg.portfolios)
    assert len(report.portfolios) == 12
    assert report.episodes, "a 1928-2018 random walk with 1.1% daily volatility has falls of 15%"
    assert all(ep.peak >= hcfg.episode_start for ep in report.episodes)
    assert all(ep.window_end <= END for ep in report.episodes)
    for pid, _ in report.portfolios:
        assert len(report.cells[pid]) == len(report.episodes)
    # CASH (100% SHY) is static: its first return day is the panel's second day
    assert report.starts["CASH"] > hcfg.panel_start
    # a switching portfolio needs 200 days of history first
    assert report.starts["A"] > report.starts["CASH"]
    assert set(report.config_hashes) == {
        "config/history.yaml",
        "config/decision.yaml",
        "config/core_candidates.yaml",
    }
    text = render_markdown(report)
    assert "selects nothing and recommends nothing" in text
    for line in text.splitlines():
        if re.search(r"\.yaml\b.*sha256.*`[0-9a-f]{12,64}`", line):
            assert re.match(
                r"^- (?:config/)?([\w.]+\.yaml) (?:config )?(?:sha256|hash): `([0-9a-f]{12,64})`",
                line,
            ), line


def test_no_episode_raises():
    criteria, dcfg, hcfg, cpi = _inputs()
    raw = _synthetic_raw(hcfg)
    close = raw.close.copy()
    close["^GSPC"] = close["^GSPC"].dropna().expanding().max()  # only ever rises
    with pytest.raises(ValueError, match="no episode"):
        run_history(hcfg, dcfg, dataclasses.replace(raw, close=close), cpi, criteria)


def test_a_cpi_that_starts_too_late_raises():
    criteria, dcfg, hcfg, cpi = _inputs()
    late = cpi.loc["1985-01-01":]
    with pytest.raises(ValueError, match="CPIAUCNS"):
        run_history(hcfg, dcfg, _synthetic_raw(hcfg), late, criteria)


def test_data_after_the_research_end_is_refused():
    criteria, dcfg, hcfg, cpi = _inputs()
    raw = _synthetic_raw(hcfg)
    close = raw.close.copy()
    close.loc[pd.Timestamp("2019-01-02"), "SPY"] = 1.0
    with pytest.raises(ValueError, match="after 2018-12-31"):
        run_history(hcfg, dcfg, dataclasses.replace(raw, close=close), cpi, criteria)
