from pathlib import Path

import pandas as pd
import pytest

from qrl.criteria import evaluate, load_criteria
from qrl.periods import HoldoutSealedError, slice_period

ROOT = Path(__file__).resolve().parents[1]


def test_criteria_file_loads_with_hash():
    crit, digest = load_criteria(ROOT / "config" / "criteria.yaml")
    assert set(crit["periods"]) == {"research", "validation", "holdout"}
    assert len(digest) == 12


def test_holdout_is_sealed_by_default():
    crit, _ = load_criteria(ROOT / "config" / "criteria.yaml")
    s = pd.Series(1.0, index=pd.bdate_range("2018-01-01", "2025-01-01"))
    assert slice_period(s, crit, "validation").index[0] >= pd.Timestamp("2019-01-01")
    with pytest.raises(HoldoutSealedError):
        slice_period(s, crit, "holdout")
    assert len(slice_period(s, crit, "holdout", unseal_holdout=True)) > 0


def test_periods_do_not_overlap():
    crit, _ = load_criteria(ROOT / "config" / "criteria.yaml")
    p = crit["periods"]
    assert pd.Timestamp(p["research"]["end"]) < pd.Timestamp(p["validation"]["start"])
    assert pd.Timestamp(p["validation"]["end"]) < pd.Timestamp(p["holdout"]["start"])


def test_evaluate_flags_failures():
    crit, _ = load_criteria(ROOT / "config" / "criteria.yaml")
    m = {"trades": 3, "sharpe": 0.2, "max_drawdown": 0.5, "cagr": 0.05}
    bench = {"sharpe": 0.8, "cagr": 0.1}
    checks = evaluate(m, bench, crit)
    assert not any(c["passed"] for c in checks)
