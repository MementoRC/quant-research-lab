"""Shared offline fixtures for the decision-helper tests: synthetic prices and
synthetic availability-dated CPI only (never market data). `GOOD` mirrors
config/decision.yaml (tests/test_decision_cli.py checks they load equal)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from qrl.criteria import load_criteria
from qrl.data import synthetic_prices
from qrl.decision_config import DecisionConfig, load_decision_config
from qrl.stress import StressConfig, load_stress_config

ROOT = Path(__file__).resolve().parents[1]
HOLDOUT = pd.Timestamp("2023-01-01")
END = pd.Timestamp("2018-12-31")
FUNDS = ["SPY", "QQQ", "RSP", "SHY", "IEF", "TLT", "GLD"]
CANDIDATES = ROOT / "config" / "core_candidates.yaml"
CANDIDATES_SHA = "1a84847ed4ae59e81627c420b88f7736357f0bdc0bcb654a945c5d2ad88107e3"
YEARS_LINE = "start_years: [2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014]"

GOOD = """\
version: 1
candidates_sha256: "1a84847ed4ae59e81627c420b88f7736357f0bdc0bcb654a945c5d2ad88107e3"
static:
  - {id: CASH, label: "100% SHY", mix: {SHY: 1.0}}
  - {id: G-EW, label: "25% each RSP / TLT / GLD / SHY", mix: {RSP: 0.25, TLT: 0.25, GLD: 0.25, SHY: 0.25}}
blends:
  - {id: AG, label: "1/2 A + 1/2 G", parts: {A: 0.5, G: 0.5}}
  - {id: G-CASH, label: "1/2 G + 1/2 CASH", parts: {G: 0.5, CASH: 0.5}}
  - {id: A-CASH, label: "1/2 A + 1/2 CASH", parts: {A: 0.5, CASH: 0.5}}
windows: [dotcom_2000, gfc_2008]
proxied_indicative_above: 0.25
scenarios:
  - name: treasury_dollar_crisis
    label: "judgement-based, v1"
    returns: {SPY: -0.25, QQQ: -0.30, RSP: -0.22, SHY: 0.01, IEF: -0.12, TLT: -0.30, GLD: 0.25}
    inflation: 0.08
  - name: trade_oil_shock
    label: "judgement-based, v1"
    returns: {SPY: -0.20, QQQ: -0.25, RSP: -0.18, SHY: 0.02, IEF: -0.06, TLT: -0.15, GLD: 0.10}
    inflation: 0.07
  - name: ai_megacap_crash
    label: "judgement-based, v1"
    returns: {SPY: -0.30, QQQ: -0.45, RSP: -0.15, SHY: 0.03, IEF: 0.06, TLT: 0.12, GLD: 0.05}
    inflation: 0.02
withdrawal_rates: [0.02, 0.033, 0.04, 0.05]
start_years: [2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014]
"""


def criteria() -> dict:
    return load_criteria(ROOT / "config" / "criteria.yaml")[0]


def stress_cfg() -> StressConfig:
    return load_stress_config(ROOT / "config" / "stress.yaml", HOLDOUT)[0]


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "decision.yaml"
    path.write_text(text)
    return path


def load(tmp_path: Path, text: str = GOOD) -> DecisionConfig:
    return load_decision_config(write(tmp_path, text), CANDIDATES, stress_cfg(), END)


def prices(start: str = "1999-01-01", end: str = "2021-12-31") -> dict[str, pd.DataFrame]:
    open_, close = synthetic_prices(FUNDS, start=start, end=end)
    return {"open": open_, "close": close}


def cpi(
    monthly_growth: float = 0.002, start: str = "1995-01-01", end: str = "2021-12-01"
) -> pd.Series:
    """CPI-like index indexed by AVAILABILITY date: month M (dated the 1st, as
    FRED does) is usable from the last day of month M+1."""
    obs = pd.date_range(start, end, freq="MS")
    values = 100.0 * (1.0 + monthly_growth) ** np.arange(len(obs))
    return pd.Series(values, index=obs + pd.offsets.MonthEnd(2), name="CPIAUCNS")
