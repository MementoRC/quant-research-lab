"""Long-run withdrawals (spec: docs/methodology/longrun.md): 30-year paths
built by a paired circular block bootstrap of 2005-2018 calendar months, for
the decision helper's portfolios plus a labelled CASH +1% real assumption
row. It compares; it selects and recommends nothing. Pure functions; callers
inject data and configs. Every frame is cut at the research end (2018-12-31)
before use, so validation and holdout data never enter.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

DEPLETED = 1e-9  # of the starting value: at or below, the path is empty (spec "Withdrawals")
CHECKPOINT_YEARS = (20, 25, 30)
_KEYS = (
    "version",
    "decision_sha256",
    "seed",
    "n_paths",
    "block_months",
    "horizon_years",
    "real_floor",
    "withdrawal_rates",
    "cash_real_yield",
)


@dataclass(frozen=True)
class LongrunConfig:
    seed: int
    n_paths: int
    block_months: int
    horizon_years: int
    real_floor: float
    rates: list[float]
    cash_real_yield: float
    sha256: str


def load_longrun_config(path: str | Path, decision_sha256: str) -> LongrunConfig:
    """Read config/longrun.yaml. Raises ValueError if it cannot be loaded, a key
    is missing, the version is not 1, the pinned decision.yaml sha256 does not
    match `decision_sha256`, or the horizon is not a whole number of blocks."""
    try:
        raw = Path(path).read_bytes()
        doc = yaml.safe_load(raw) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"longrun.yaml: cannot be loaded ({exc})") from exc
    if not isinstance(doc, dict):
        raise ValueError("longrun.yaml: cannot be loaded (not a mapping)")
    missing = [k for k in _KEYS if k not in doc]
    if missing:
        raise ValueError(f"longrun.yaml: missing key(s) {missing}")
    if doc["version"] != 1:
        raise ValueError(f"longrun.yaml: unsupported version {doc['version']}")
    if doc["decision_sha256"] != decision_sha256:
        raise ValueError("decision.yaml changed: its sha256 does not match longrun.yaml's pin")
    months = int(doc["horizon_years"]) * 12
    if months % int(doc["block_months"]):
        raise ValueError(
            f"longrun.yaml: horizon of {months} months is not a whole number of "
            f"{doc['block_months']}-month blocks"
        )
    return LongrunConfig(
        seed=int(doc["seed"]),
        n_paths=int(doc["n_paths"]),
        block_months=int(doc["block_months"]),
        horizon_years=int(doc["horizon_years"]),
        real_floor=float(doc["real_floor"]),
        rates=[float(r) for r in doc["withdrawal_rates"]],
        cash_real_yield=float(doc["cash_real_yield"]),
        sha256=hashlib.sha256(raw).hexdigest(),
    )
