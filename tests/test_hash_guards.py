"""validate, walk-forward and unseal refuse a run whose criteria hash changed
since it was seeded, before any evaluation or unsealing happens."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from qrl.criteria import load_criteria
from qrl.ledger import Ledger

ROOT = Path(__file__).resolve().parents[1]
CRITERIA = ROOT / "config" / "criteria.yaml"
REFUSAL = "Criteria hash has changed since this run started; refusing to continue."


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(
        f"{name}_guard_cli", ROOT / "scripts" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _seed(tmp_path, criteria_hash: str) -> str:
    """A ledger with one run and one passing survivor that has no neighbours."""
    path = str(tmp_path / "ledger.sqlite")
    with Ledger(path) as ledger:
        run_id = ledger.start_run(criteria_hash, "A", "synthetic guard test")
        ledger.record_test(
            run_id,
            criteria_hash,
            "core_trend",
            {"lookback": 100, "risk_off": "GLD"},
            "qqq_gld",
            {"sharpe": 1.0, "trades": 50},
            True,
            None,
        )
    assert run_id == 1
    return path


def _boom(*_args, **_kwargs):
    raise AssertionError("evaluation or unsealing reached despite a changed criteria hash")


def _stale_hash() -> str:
    _, current = load_criteria(CRITERIA)
    return "0" * len(current)


def test_validate_refuses_changed_criteria_hash_before_evaluating(tmp_path, monkeypatch, capsys):
    mod = _load_script("validate")
    monkeypatch.setattr(mod.SearchData, "load", _boom)
    monkeypatch.setattr(mod, "validate_survivors", _boom)
    ledger = _seed(tmp_path, _stale_hash())
    rc = mod.main(["--run", "1", "--synthetic", "--ledger", ledger, "--criteria", str(CRITERIA)])
    assert rc == 2
    assert REFUSAL in capsys.readouterr().err


def test_validate_unknown_run_still_reported(tmp_path, capsys):
    mod = _load_script("validate")
    _, current = load_criteria(CRITERIA)
    ledger = _seed(tmp_path, current)
    rc = mod.main(["--run", "9", "--synthetic", "--ledger", ledger, "--criteria", str(CRITERIA)])
    assert rc == 2
    assert "Unknown run 9" in capsys.readouterr().err


@pytest.mark.parametrize("command", ["run", "tune"])
def test_walkforward_refuses_changed_criteria_hash(tmp_path, monkeypatch, capsys, command):
    mod = _load_script("walkforward")
    monkeypatch.setattr(mod.SearchData, "load", _boom)
    monkeypatch.setattr(mod, "walk_forward", _boom)
    monkeypatch.setattr(mod, "tune_meta", _boom)
    ledger = _seed(tmp_path, _stale_hash())
    rc = mod.main(
        ["--ledger", ledger, "--criteria", str(CRITERIA), "--synthetic", command, "--run", "1"]
    )
    assert rc == 2
    assert REFUSAL in capsys.readouterr().err


def _seed_factor_run(tmp_path, mutate: str):
    """Seed a factor + combined_null run, then edit factor.yaml or combined yaml.
    Returns (ledger path, shared config argv)."""
    from test_combined_null import LOOSE_NULL, _cfg_args, _copy_configs
    from test_factor_run import _seed_factor, _write_setup

    paths = _copy_configs(tmp_path, combined_null=LOOSE_NULL)
    factor = _write_setup(tmp_path)
    assert _seed_factor(tmp_path, paths, factor) == 0
    target = factor if mutate == "factor" else paths["combined"]
    target.write_text(target.read_text() + "# edited after seeding\n")
    cfg = ["--factor-config", str(factor), *_cfg_args(paths)]
    return str(tmp_path / "ledger.sqlite"), cfg


@pytest.mark.parametrize("mutate", ["factor", "combined"])
@pytest.mark.parametrize("command", ["run", "tune"])
def test_walkforward_refuses_changed_factor_or_combined_hash(
    tmp_path, monkeypatch, capsys, command, mutate
):
    mod = _load_script("walkforward")
    for name in ("walk_forward", "tune_meta"):
        monkeypatch.setattr(mod, name, _boom)
    monkeypatch.setattr(mod.SearchData, "load", _boom)
    ledger, cfg = _seed_factor_run(tmp_path, mutate)
    rc = mod.main(["--ledger", ledger, "--synthetic", *cfg, command, "--run", "1"])
    assert rc == 2
    expected = "factor.yaml hash has changed" if mutate == "factor" else "Combined config hash"
    assert expected in capsys.readouterr().err


@pytest.mark.parametrize("mutate", ["factor", "combined"])
def test_unseal_refuses_changed_factor_or_combined_hash(tmp_path, monkeypatch, capsys, mutate):
    mod = _load_script("unseal_holdout")
    monkeypatch.setattr(mod.SearchData, "load", _boom)
    monkeypatch.setattr(mod, "unseal", _boom)
    monkeypatch.setattr(mod, "walk_forward", _boom)
    ledger, cfg = _seed_factor_run(tmp_path, mutate)
    rc = mod.main(
        [
            "--run",
            "1",
            "--reason",
            "guard test",
            "--confirm",
            "--synthetic",
            "--ledger",
            ledger,
            *cfg,
        ]
    )
    assert rc == 2
    expected = "factor.yaml hash has changed" if mutate == "factor" else "Combined config hash"
    assert expected in capsys.readouterr().err


def test_unseal_refuses_changed_criteria_hash_without_unsealing(tmp_path, monkeypatch, capsys):
    mod = _load_script("unseal_holdout")
    monkeypatch.setattr(mod.SearchData, "load", _boom)
    monkeypatch.setattr(mod, "unseal", _boom)
    monkeypatch.setattr(mod, "walk_forward", _boom)
    ledger = _seed(tmp_path, _stale_hash())
    rc = mod.main(
        [
            "--run",
            "1",
            "--reason",
            "guard test",
            "--confirm",
            "--synthetic",
            "--ledger",
            ledger,
            "--criteria",
            str(CRITERIA),
        ]
    )
    assert rc == 2
    assert REFUSAL in capsys.readouterr().err
