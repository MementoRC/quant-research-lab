"""Tests for the RSP sleeve (spec: docs/methodology/rsp-sleeve.md): the
pre-registered fixed pass rule, `search seed --fixed` / `search fixed`, and
validate loading the recorded tests' own tickers. Offline, synthetic data only."""

from __future__ import annotations

import dataclasses
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

from qrl.combined import combined_checks, load_combined_config
from qrl.ledger import Ledger
from qrl.search import SearchData

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import rsp_sleeve as rsp_script  # noqa: E402
import search as search_mod  # noqa: E402
import validate as validate_mod  # noqa: E402
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
    _edit_yaml,
    _write_tiny_universe,
)
from validate import _candidate_tickers  # noqa: E402

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


def _batch_argv(
    ledger_path: Path, universe: Path, run_id: int, paths: dict, *extra: str
) -> list[str]:
    return [
        "--ledger", str(ledger_path), "batch", "--run", str(run_id), "--n", "3",
        "--synthetic", "--universe", str(universe), *_combined_args(paths), *extra,
    ]  # fmt: skip


def test_batch_refuses_on_a_fixed_run_even_with_families_override(tmp_path, capsys):
    ledger_path, universe, run_id, paths = _seed_fixed(tmp_path)
    capsys.readouterr()
    for extra in ([], ["--families", "trend_pullback"]):
        assert search_main(_batch_argv(ledger_path, universe, run_id, paths, *extra)) == 2
        assert "fixed-candidate run" in capsys.readouterr().err
    with Ledger(ledger_path) as ledger:
        assert ledger.list_tests(run_id) == []


def test_batch_refuses_when_the_fixed_config_changed_after_seeding(tmp_path):
    ledger_path, universe, run_id, paths = _seed_fixed(tmp_path)
    _edit_yaml(paths["combined"], lambda d: d.update(max_drawdown=0.5))
    assert search_main(_batch_argv(ledger_path, universe, run_id, paths)) == 2
    with Ledger(ledger_path) as ledger:
        assert ledger.list_tests(run_id) == []


def _fixed_argv(
    ledger_path: Path, universe: Path, run_id: int, paths: dict, **over: str
) -> list[str]:
    opts = {"family": "buy_and_hold", "params": RSP_PARAMS, **over}
    return [
        "--ledger", str(ledger_path), "fixed", "--run", str(run_id),
        "--family", opts["family"], "--params", opts["params"],
        "--synthetic", "--universe", str(universe), *_combined_args(paths),
    ]  # fmt: skip


def test_fixed_records_exactly_one_test_and_refuses_a_second(tmp_path):
    ledger_path, universe, run_id, paths = _seed_fixed(tmp_path)
    assert search_main(_fixed_argv(ledger_path, universe, run_id, paths)) == 0
    with Ledger(ledger_path) as ledger:
        tests = ledger.list_tests(run_id)
    assert len(tests) == 1
    assert (tests[0]["family"], tests[0]["params"]) == ("buy_and_hold", {"ticker": "RSP"})
    assert search_main(_fixed_argv(ledger_path, universe, run_id, paths)) == 2
    with Ledger(ledger_path) as ledger:
        assert len(ledger.list_tests(run_id)) == 1


def test_fixed_refuses_a_non_fixed_run(tmp_path, capsys):
    paths = _fixed_paths(tmp_path)
    universe = _write_tiny_universe(tmp_path / "universe.yaml")
    argv = _seed_argv(tmp_path, paths, universe, "--families", "trend_pullback")
    assert search_main(argv) == 0
    capsys.readouterr()
    assert search_main(_fixed_argv(tmp_path / "ledger.sqlite", universe, 1, paths)) == 2
    assert "not a fixed-candidate run" in capsys.readouterr().err
    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        assert ledger.list_tests(1) == []


def test_fixed_refuses_a_different_candidate_than_declared(tmp_path):
    ledger_path, universe, run_id, paths = _seed_fixed(tmp_path)
    other = json.dumps({"ticker": "SPY"})
    assert search_main(_fixed_argv(ledger_path, universe, run_id, paths, params=other)) == 2
    with Ledger(ledger_path) as ledger:
        assert ledger.list_tests(run_id) == []


def test_fixed_refuses_when_the_pass_rule_config_changed(tmp_path):
    ledger_path, universe, run_id, paths = _seed_fixed(tmp_path)
    _edit_yaml(paths["combined"], lambda d: d.update(max_drawdown=0.5))
    assert search_main(_fixed_argv(ledger_path, universe, run_id, paths)) == 2
    with Ledger(ledger_path) as ledger:
        assert ledger.list_tests(run_id) == []


def test_preflight_failure_records_nothing(tmp_path, monkeypatch, capsys):
    ledger_path, universe, run_id, paths = _seed_fixed(tmp_path)
    real = SearchData.load

    def _late_rsp(cls, tickers, **kw):
        data = real(tickers, **kw)
        close = data.close.copy()
        close.loc[close.index < "2012-01-01", "RSP"] = np.nan
        return dataclasses.replace(data, close=close)

    monkeypatch.setattr(SearchData, "load", classmethod(_late_rsp))
    capsys.readouterr()
    assert search_main(_fixed_argv(ledger_path, universe, run_id, paths)) == 2
    assert "RSP" in capsys.readouterr().err
    with Ledger(ledger_path) as ledger:
        assert ledger.list_tests(run_id) == []


def test_error_after_preflight_is_recorded_as_a_failed_test(tmp_path, monkeypatch):
    ledger_path, universe, run_id, paths = _seed_fixed(tmp_path)

    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(search_mod, "compute_benchmark_metrics", _boom)
    assert search_main(_fixed_argv(ledger_path, universe, run_id, paths)) == 0
    with Ledger(ledger_path) as ledger:
        tests = ledger.list_tests(run_id)
    assert len(tests) == 1
    assert tests[0]["passed"] is False
    assert tests[0]["failure_reasons"] == "error: boom"
    assert search_main(_fixed_argv(ledger_path, universe, run_id, paths)) == 2


def test_fixed_loads_the_candidates_own_ticker(tmp_path, monkeypatch):
    ledger_path, universe, run_id, paths = _seed_fixed(tmp_path)
    seen: list[list[str]] = []
    real = SearchData.load

    def _spy(cls, tickers, **kw):
        seen.append(list(tickers))
        return real(tickers, **kw)

    monkeypatch.setattr(SearchData, "load", classmethod(_spy))
    assert search_main(_fixed_argv(ledger_path, universe, run_id, paths)) == 0
    assert "RSP" in seen[0]
    assert not set(seen[0]) & {"AAA", "BBB", "CCC", "DDD"}  # universe not loaded


def test_candidate_tickers_resolves_known_families_and_skips_unknown():
    tests = [
        {"family": "buy_and_hold", "params": {"ticker": "RSP"}, "passed": True},
        {"family": "no_such_family", "params": {}, "passed": True},
    ]
    assert _candidate_tickers(tests) == {"RSP"}
    assert _candidate_tickers([]) == set()


def test_candidate_tickers_only_from_passed_tests_and_skips_bad_params():
    rsp = {"family": "buy_and_hold", "params": {"ticker": "RSP"}}
    tests = [
        {**rsp, "passed": True},
        {"family": "buy_and_hold", "params": {"ticker": "SPY"}, "passed": False},
        {"family": "buy_and_hold", "params": {}, "passed": True},  # bad params: KeyError
    ]
    assert _candidate_tickers(tests) == {"RSP"}
    assert _candidate_tickers([{**rsp, "passed": False}]) == set()


def _rsp_argv(ledger_path: Path, run_id: int, out: Path, note: str = "n/a") -> list[str]:
    return [
        "--run", str(run_id), "--ledger", str(ledger_path),
        "--validation-note", note, "--out-md", str(out),
    ]  # fmt: skip


def test_rsp_script_writes_a_failed_report_for_an_errored_test(tmp_path, monkeypatch):
    ledger_path, universe, run_id, paths = _seed_fixed(tmp_path)

    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(search_mod, "compute_benchmark_metrics", _boom)
    assert search_main(_fixed_argv(ledger_path, universe, run_id, paths)) == 0
    out = tmp_path / "rsp.md"
    assert rsp_script.main(_rsp_argv(ledger_path, run_id, out)) == 0
    text = out.read_text()
    assert "FAILED" in text
    assert "boom" in text
    assert "| portfolio |" not in text


def test_rsp_script_refuses_a_non_fixed_run(tmp_path, capsys):
    paths = _fixed_paths(tmp_path)
    universe = _write_tiny_universe(tmp_path / "universe.yaml")
    assert search_main(_seed_argv(tmp_path, paths, universe, "--families", "trend_pullback")) == 0
    ledger_path = tmp_path / "ledger.sqlite"
    capsys.readouterr()
    out = tmp_path / "rsp.md"
    assert rsp_script.main(_rsp_argv(ledger_path, 1, out)) == 2
    assert "not a fixed" in capsys.readouterr().err
    assert not out.exists()


def test_validate_loads_the_recorded_tests_own_tickers(tmp_path, monkeypatch):
    ledger_path, universe, run_id, paths = _seed_fixed(tmp_path)
    assert search_main(_fixed_argv(ledger_path, universe, run_id, paths)) == 0
    with sqlite3.connect(ledger_path) as conn:  # validate only loads passed tests' tickers
        conn.execute("UPDATE tests SET passed = 1 WHERE run_id = ?", (run_id,))
    seen: list[list[str]] = []
    real = SearchData.load

    def _spy(cls, tickers, **kw):
        seen.append(list(tickers))
        return real(tickers, **kw)

    monkeypatch.setattr(SearchData, "load", classmethod(_spy))
    argv = [
        "--run", str(run_id), "--ledger", str(ledger_path), "--synthetic",
        "--universe", str(universe), *_combined_args(paths),
    ]  # fmt: skip
    assert validate_mod.main(argv) == 0
    assert "RSP" in seen[0]


def test_validate_refuses_when_the_fixed_config_changed_after_seeding(tmp_path):
    ledger_path, universe, run_id, paths = _seed_fixed(tmp_path)
    assert search_main(_fixed_argv(ledger_path, universe, run_id, paths)) == 0
    _edit_yaml(paths["combined"], lambda d: d.update(max_drawdown=0.5))
    argv = [
        "--run", str(run_id), "--ledger", str(ledger_path), "--synthetic",
        "--universe", str(universe), *_combined_args(paths),
    ]  # fmt: skip
    assert validate_mod.main(argv) == 2
    with Ledger(ledger_path) as ledger:
        assert len(ledger.list_tests(run_id)) == 1  # the one attempt, nothing added
