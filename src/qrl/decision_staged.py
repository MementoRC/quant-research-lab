"""Staged entry (spec: docs/methodology/staged-entry.md): invest the starting
cash all at once (lump sum) or in equal monthly tranches over N months, while
drawing the fixed CPI-indexed income, per core, staging period, cash variant
and withdrawal rate, in the decision helper's historical view (120 monthly
starts) and the long run's resampled paths. A comparison: no pass/fail rule,
no search trial; it selects and recommends nothing. Pure functions; callers
inject data and configs. Every price and CPI frame is cut at the research end
(2018-12-31) before use, so validation and holdout data never enter. The lump
sum is the same runner with one tranche and equals `withdrawal_path` and
`run_paths` exactly; that code and every number it publishes are unchanged.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .decision import cash_rows, data_end, portfolio_returns, research_start
from .decision_config import DecisionConfig, Portfolio
from .decision_rules import longrun_indices, month_starts
from .decision_withdraw import DEPLETED, monthly_inflation, usable_cpi
from .longrun import (
    CASH_ID,
    LongrunConfig,
    cash_assumption_returns,
    check_cash_assumption,
    check_withdrawal_rates,
    monthly_returns,
)
from .periods import period_bounds
from .true_cash import cash_leg_returns

_KEYS = (
    "version",
    "decision_sha256",
    "longrun_sha256",
    "periods_months",
    "cash_variants",
    "portfolios",
)
CASH_VARIANTS = ("shy", "real_plus_1")
_WHERE = "staged_entry.yaml"
FIRST_START = pd.Period("2005-01", freq="M")  # spec "Historical starts"
LAST_START = pd.Period("2014-12", freq="M")
HORIZON_MONTHS = 48  # the start month counts as the first
YEAR5_MONTHS = 60


@dataclass(frozen=True)
class StagedConfig:
    periods: list[int]  # staging months, 0 = lump sum first, in config order
    cash_variants: list[str]  # CASH_VARIANTS entries, in config order
    portfolios: list[str]  # decision.yaml portfolio ids, in config order
    sha256: str


def _read(path: str | Path) -> tuple[dict, bytes]:
    try:
        raw = Path(path).read_bytes()
        doc = yaml.safe_load(raw)
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"{_WHERE}: cannot be loaded ({exc})") from exc
    if not isinstance(doc, dict):
        raise ValueError(f"{_WHERE}: cannot be loaded (not a mapping)")
    return doc, raw


def _list(doc: dict, key: str) -> list:
    value = doc[key]
    if not isinstance(value, list) or not value:
        raise ValueError(f"{_WHERE}: `{key}` must be a non-empty list")
    dupes = sorted({str(v) for v in value if value.count(v) > 1})
    if dupes:
        raise ValueError(f"{_WHERE}: duplicate `{key}` entries {dupes}")
    return value


def _periods(doc: dict) -> list[int]:
    periods = _list(doc, "periods_months")
    bad = [p for p in periods if isinstance(p, bool) or not isinstance(p, int) or p < 0]
    if bad:
        raise ValueError(f"{_WHERE}: periods_months {bad} must be non-negative integers")
    if periods[0] != 0:
        raise ValueError(f"{_WHERE}: periods_months must start with 0 (the lump sum)")
    return [int(p) for p in periods]


def load_staged_config(path: str | Path, dcfg: DecisionConfig, lcfg: LongrunConfig) -> StagedConfig:
    """Read config/staged_entry.yaml (spec "Configuration"). Raises ValueError
    if it cannot be loaded, has an unknown or a missing key, a version other
    than 1, a decision.yaml or longrun.yaml pin that does not match, periods
    that are not distinct non-negative integers starting with 0, an unknown
    cash variant, a portfolio not in decision.yaml or equal to CASH, an empty
    or duplicated list; `real_plus_1` needs a decision.yaml cash_assumptions
    row whose real_yield equals longrun.yaml's cash_real_yield."""
    doc, raw = _read(path)
    unknown = sorted(str(k) for k in doc.keys() - set(_KEYS))
    if unknown:
        raise ValueError(f"{_WHERE}: unknown key(s) {unknown}")
    missing = [k for k in _KEYS if k not in doc]
    if missing:
        raise ValueError(f"{_WHERE}: missing key(s) {missing}")
    if doc["version"] != 1:
        raise ValueError(f"{_WHERE}: unsupported version {doc['version']}")
    if doc["decision_sha256"] != dcfg.sha256:
        raise ValueError(f"decision.yaml changed: its sha256 does not match {_WHERE}'s pin")
    if doc["longrun_sha256"] != lcfg.sha256:
        raise ValueError(f"longrun.yaml changed: its sha256 does not match {_WHERE}'s pin")
    periods = _periods(doc)
    variants = [str(v) for v in _list(doc, "cash_variants")]
    strange = [v for v in variants if v not in CASH_VARIANTS]
    if strange:
        raise ValueError(f"{_WHERE}: unknown cash variant(s) {strange}")
    if "real_plus_1" in variants:
        if not cash_rows(dcfg):
            raise ValueError(f"{_WHERE}: real_plus_1 needs a cash_assumptions row in decision.yaml")
        check_cash_assumption(lcfg, dcfg)
    known = {p.id for p in dcfg.portfolios}
    portfolios = [str(p) for p in _list(doc, "portfolios")]
    strangers = [p for p in portfolios if p not in known]
    if strangers:
        raise ValueError(f"{_WHERE}: portfolio(s) {strangers} not in decision.yaml")
    if CASH_ID in portfolios:
        raise ValueError(f"{_WHERE}: {CASH_ID} is excluded (staging into cash is a lump sum)")
    return StagedConfig(
        periods=periods,
        cash_variants=variants,
        portfolios=portfolios,
        sha256=hashlib.sha256(raw).hexdigest(),
    )
