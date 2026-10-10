"""Tests for the RSP sleeve (spec: docs/methodology/rsp-sleeve.md): the
pre-registered fixed pass rule, `search seed --fixed` / `search fixed`, and
validate loading the recorded tests' own tickers. Offline, synthetic data only."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from qrl.combined import combined_checks, load_combined_config

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from search import (  # noqa: E402
    FIXED_MARKER,
    _decode_fixed,
    _decode_seed_description,
    _encode_seed_description,
)
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


RSP_FIXED = {"marker": FIXED_MARKER, "family": "buy_and_hold", "params": {"ticker": "RSP"}}


def test_fixed_description_round_trips():
    raw = _encode_seed_description("rsp", ["buy_and_hold"], RSP_FIXED)
    assert _decode_fixed(raw) == RSP_FIXED
    assert _decode_seed_description(raw) == ("rsp", ["buy_and_hold"])


def test_encoding_without_a_fixed_marker_is_unchanged():
    raw = _encode_seed_description("d", ["trend_pullback"])
    assert json.loads(raw) == {"description": "d", "families": ["trend_pullback"]}


def test_pre_change_descriptions_decode_as_not_fixed():
    assert _decode_fixed(json.dumps({"description": "d", "families": ["a"]})) is None
    assert _decode_fixed("lane A: plain text") is None
    assert _decode_fixed("") is None
    assert _decode_fixed("[1, 2]") is None
    assert _decode_fixed(json.dumps({"fixed": {"family": "x"}})) is None  # no marker
