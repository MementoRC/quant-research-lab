"""Staged entry (qrl.decision_staged, qrl.staged_entry_report). Offline;
synthetic returns, prices and CPI only. Spec:
docs/methodology/staged-entry.md ("Tests")."""

from __future__ import annotations

from dataclasses import replace

import pytest
from decision_helpers import CANDIDATES, END, GOOD, GOOD_TCASH_ALL, ROOT, load, stress_cfg

from qrl.decision_config import load_decision_config
from qrl.decision_staged import StagedConfig, load_staged_config
from qrl.longrun import LongrunConfig, load_longrun_config

D_SHA = "d" * 64  # placeholder replaced by the test decision.yaml's sha256
L_SHA = "e" * 64  # the test LongrunConfig's sha256

STAGED_YAML = f"""\
version: 1
decision_sha256: "{D_SHA}"
longrun_sha256: "{L_SHA}"
periods_months: [0, 6, 12, 24]
cash_variants: [shy, real_plus_1]
portfolios: [A, B, C, D, E, F, G]
"""


def _lcfg(**kw) -> LongrunConfig:
    base = LongrunConfig(
        seed=7,
        n_paths=50,
        block_months=12,
        horizon_years=30,
        real_floor=0.5,
        rates=[0.02, 0.033, 0.04, 0.05],
        cash_real_yield=0.01,
        sha256=L_SHA,
    )
    return replace(base, **kw)


def _write(tmp_path, text, dcfg):
    path = tmp_path / "staged_entry.yaml"
    path.write_text(text.replace(D_SHA, dcfg.sha256))
    return path


# ---- config


def test_loader_reads_the_config(tmp_path):
    dcfg = load(tmp_path, GOOD_TCASH_ALL)
    scfg = load_staged_config(_write(tmp_path, STAGED_YAML, dcfg), dcfg, _lcfg())
    assert isinstance(scfg, StagedConfig)
    assert scfg.periods == [0, 6, 12, 24]
    assert scfg.cash_variants == ["shy", "real_plus_1"]
    assert scfg.portfolios == list("ABCDEFG")
    assert len(scfg.sha256) == 64


REFUSALS = [
    ("version: 1", "version: 2", "unsupported version"),
    ("portfolios:", "extra: 1\nportfolios:", "unknown key"),
    ("cash_variants: [shy, real_plus_1]\n", "", "missing key"),
    ("[0, 6, 12, 24]", "[6, 0, 12]", "must start with 0"),
    ("[0, 6, 12, 24]", "[0, 6, 6]", "duplicate"),
    ("[0, 6, 12, 24]", "[0, -6]", "non-negative integers"),
    ("[0, 6, 12, 24]", "[0, 6.5]", "non-negative integers"),
    ("[0, 6, 12, 24]", "[0, true]", "non-negative integers"),
    ("[0, 6, 12, 24]", "[]", "non-empty list"),
    ("[shy, real_plus_1]", "[shy, cash]", "unknown cash variant"),
    ("[shy, real_plus_1]", "[shy, shy]", "duplicate"),
    ("[shy, real_plus_1]", "[]", "non-empty list"),
    ("[A, B, C, D, E, F, G]", "[A, Z]", "not in decision.yaml"),
    ("[A, B, C, D, E, F, G]", "[A, CASH]", "is excluded"),
    ("[A, B, C, D, E, F, G]", "[A, A]", "duplicate"),
    ("[A, B, C, D, E, F, G]", "[]", "non-empty list"),
    (f'"{L_SHA}"', '"' + "0" * 64 + '"', "longrun.yaml changed"),
]


@pytest.mark.parametrize(("old", "new", "match"), REFUSALS)
def test_loader_refuses(tmp_path, old, new, match):
    dcfg = load(tmp_path, GOOD_TCASH_ALL)
    assert old in STAGED_YAML
    with pytest.raises(ValueError, match=match):
        load_staged_config(_write(tmp_path, STAGED_YAML.replace(old, new), dcfg), dcfg, _lcfg())


def test_loader_refuses_a_stale_decision_pin(tmp_path):
    dcfg = load(tmp_path, GOOD_TCASH_ALL)
    path = tmp_path / "staged_entry.yaml"
    path.write_text(STAGED_YAML)  # D_SHA left in place: not decision.yaml's sha256
    with pytest.raises(ValueError, match="decision.yaml changed"):
        load_staged_config(path, dcfg, _lcfg())


def test_loader_refuses_real_plus_1_without_a_cash_assumption(tmp_path):
    dcfg = load(tmp_path, GOOD)
    with pytest.raises(ValueError, match="needs a cash_assumptions row"):
        load_staged_config(_write(tmp_path, STAGED_YAML, dcfg), dcfg, _lcfg())
    shy_only = STAGED_YAML.replace("[shy, real_plus_1]", "[shy]")
    assert load_staged_config(_write(tmp_path, shy_only, dcfg), dcfg, _lcfg()).cash_variants == [
        "shy"
    ]


def test_loader_refuses_a_cash_yield_unlike_longrun(tmp_path):
    dcfg = load(tmp_path, GOOD_TCASH_ALL)
    with pytest.raises(ValueError, match="differs from longrun.yaml cash_real_yield"):
        load_staged_config(_write(tmp_path, STAGED_YAML, dcfg), dcfg, _lcfg(cash_real_yield=0.02))


@pytest.mark.parametrize("text", [None, "- a\n", "a: [\n"])
def test_loader_refuses_an_unreadable_file(tmp_path, text):
    dcfg = load(tmp_path, GOOD_TCASH_ALL)
    path = tmp_path / "staged_entry.yaml"
    if text is not None:
        path.write_text(text)
    with pytest.raises(ValueError, match="cannot be loaded"):
        load_staged_config(path, dcfg, _lcfg())


def test_shipped_config_loads():
    dcfg = load_decision_config(ROOT / "config" / "decision.yaml", CANDIDATES, stress_cfg(), END)
    lcfg = load_longrun_config(ROOT / "config" / "longrun.yaml", dcfg.sha256)
    scfg = load_staged_config(ROOT / "config" / "staged_entry.yaml", dcfg, lcfg)
    assert scfg.periods == [0, 6, 12, 24]
    assert scfg.portfolios == list("ABCDEFG")
