"""Tests for the RSP sleeve (spec: docs/methodology/rsp-sleeve.md): the
pre-registered fixed pass rule, `search seed --fixed` / `search fixed`, and
validate loading the recorded tests' own tickers. Offline, synthetic data only."""

from __future__ import annotations

import sys
from pathlib import Path

from qrl.combined import combined_checks, load_combined_config

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from test_combined import _CORE_M, _GOOD_M  # noqa: E402

FIXED = CONFIG / "combined_fixed.yaml"


def _load(path: Path) -> dict:
    return load_combined_config(path, CONFIG / "profile.yaml", CONFIG / "portfolio.yaml")[0]


def test_fixed_config_loads_and_only_turns_off_min_trades():
    fixed, base = _load(FIXED), _load(CONFIG / "combined.yaml")
    assert fixed["sleeve_min_trades"] == 0
    assert base["sleeve_min_trades"] == 10
    assert {k: v for k, v in fixed.items() if k != "sleeve_min_trades"} == {
        k: v for k, v in base.items() if k != "sleeve_min_trades"
    }


def test_both_configs_differ_only_on_the_min_trades_check():
    fixed, base = _load(FIXED), _load(CONFIG / "combined.yaml")
    under_fixed = combined_checks(_GOOD_M, _CORE_M, 1, fixed)
    under_base = combined_checks(_GOOD_M, _CORE_M, 1, base)
    assert all(c["passed"] for c in under_fixed)
    assert {c["rule"] for c in under_base if not c["passed"]} == {"sleeve_min_trades"}
    other = [c for c in under_fixed if c["rule"] != "sleeve_min_trades"]
    assert other == [c for c in under_base if c["rule"] != "sleeve_min_trades"]
