"""Tests for the RSP sleeve (spec: docs/methodology/rsp-sleeve.md): the
pre-registered fixed pass rule, `search seed --fixed` / `search fixed`, and
validate loading the recorded tests' own tickers. Offline, synthetic data only."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

from qrl.combined import combined_checks, load_combined_config
from qrl.ledger import Ledger

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from search import (  # noqa: E402
    FIXED_MARKER,
    SEARCHABLE_SPACES,
    _decode_fixed,
    _decode_seed_description,
    _encode_seed_description,
)
from search import main as search_main  # noqa: E402
from test_combined import (  # noqa: E402
    _CORE_M,
    _GOOD_M,
    _combined_args,
    _copy_configs,
    _write_tiny_universe,
)

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


RSP_PARAMS = json.dumps({"ticker": "RSP"})


def _fixed_paths(tmp_path: Path) -> dict[str, Path]:
    """Tmp copies of the configs, with combined_fixed.yaml as the combined one."""
    return _copy_configs(tmp_path, combined=yaml.safe_load(FIXED.read_text()))


def _seed_argv(tmp_path: Path, paths: dict, universe: Path, *extra: str) -> list[str]:
    return [
        "--ledger", str(tmp_path / "ledger.sqlite"),
        "seed", "--lane", "B", "--synthetic", "--universe", str(universe),
        "--pass-rule", "combined", *_combined_args(paths), *extra,
    ]  # fmt: skip


def _seed_fixed(tmp_path: Path) -> tuple[Path, Path, int, dict]:
    paths = _fixed_paths(tmp_path)
    universe = _write_tiny_universe(tmp_path / "universe.yaml")
    argv = _seed_argv(
        tmp_path, paths, universe, "--fixed", "--families", "buy_and_hold", "--params", RSP_PARAMS
    )
    assert search_main(argv) == 0
    ledger_path = tmp_path / "ledger.sqlite"
    with Ledger(ledger_path) as ledger:
        run_id = ledger.list_runs()[-1]["run_id"]
    return ledger_path, universe, run_id, paths


def test_buy_and_hold_stays_out_of_the_searchable_spaces():
    assert "buy_and_hold" not in SEARCHABLE_SPACES


def test_seed_fixed_stores_the_marker_family_and_params(tmp_path):
    ledger_path, _, run_id, _ = _seed_fixed(tmp_path)
    with Ledger(ledger_path) as ledger:
        run = next(r for r in ledger.list_runs() if r["run_id"] == run_id)
    assert _decode_fixed(run["seed_description"]) == RSP_FIXED
    assert run["pass_rule"] == "combined"


def test_seed_without_fixed_still_rejects_buy_and_hold(tmp_path):
    paths = _fixed_paths(tmp_path)
    universe = _write_tiny_universe(tmp_path / "universe.yaml")
    assert search_main(_seed_argv(tmp_path, paths, universe, "--families", "buy_and_hold")) == 2


@pytest.mark.parametrize(
    "extra",
    [
        ["--families", "buy_and_hold,trend_pullback", "--params", RSP_PARAMS],  # two families
        ["--families", "nonesuch", "--params", RSP_PARAMS],  # unknown family
        ["--families", "buy_and_hold"],  # no params
        ["--families", "buy_and_hold", "--params", "not json"],
        ["--families", "buy_and_hold", "--params", '{"tk": "RSP"}'],  # no ticker key
    ],
)
def test_seed_fixed_rejects_a_bad_declaration(tmp_path, extra):
    paths = _fixed_paths(tmp_path)
    universe = _write_tiny_universe(tmp_path / "universe.yaml")
    assert search_main(_seed_argv(tmp_path, paths, universe, "--fixed", *extra)) == 2
    assert (
        not (tmp_path / "ledger.sqlite").exists()
        or not Ledger(tmp_path / "ledger.sqlite").list_runs()
    )


def test_seed_fixed_needs_the_combined_pass_rule(tmp_path):
    universe = _write_tiny_universe(tmp_path / "universe.yaml")
    argv = [
        "--ledger", str(tmp_path / "ledger.sqlite"), "seed", "--lane", "B", "--fixed",
        "--families", "buy_and_hold", "--params", RSP_PARAMS,
        "--synthetic", "--universe", str(universe),
    ]  # fmt: skip
    assert search_main(argv) == 2
