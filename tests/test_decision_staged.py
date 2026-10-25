"""Staged entry (qrl.decision_staged, qrl.staged_entry_report). Offline;
synthetic returns, prices and CPI only. Spec:
docs/methodology/staged-entry.md ("Tests")."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
from decision_helpers import CANDIDATES, END, GOOD, GOOD_TCASH_ALL, ROOT, load, stress_cfg

from qrl.decision_config import load_decision_config
from qrl.decision_staged import StagedConfig, StagedRun, load_staged_config, run_staged
from qrl.decision_withdraw import DEPLETED
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


# ---- runner (hand-computed)


def _run(returns, source, cash, withdraw, buy, n, begin=None):
    return run_staged(
        np.asarray(returns, dtype=float),
        np.asarray(source),
        np.asarray(cash, dtype=float),
        np.asarray(withdraw, dtype=float),
        np.asarray(buy),
        n,
        None if begin is None else np.asarray(begin),
    )


def test_cash_earns_between_tranches_and_the_last_tranche_takes_it_all():
    run = _run([[0.10, 0.10, 0.10]], [[0]], [[0.01] * 3], [[0, 0, 0]], [[0, -1, 1]], 2)
    # step 0: buy 0.5 -> held 0.55, cash 0.505; step 1: 0.605 + 0.51005;
    # step 2: buy all 0.51005 -> held 1.11505 x 1.1
    assert isinstance(run, StagedRun)
    assert run.values[0] == pytest.approx([1.055, 1.11505, 1.226555])
    assert run.depleted.tolist() == [0]


def test_withdrawals_come_from_cash_first():
    run = _run([[0, 1.0, 0]], [[0]], [[0, 0, 0]], [[0, 0.1, 0]], [[0, -1, 1]], 2)
    # step 1: 0.1 from cash (0.5 -> 0.4); invested 0.5 doubles -> 1.4
    # (from the invested part it would be 0.4 x 2 + 0.5 = 1.3)
    assert run.values[0] == pytest.approx([1.0, 1.4, 1.4])


def test_after_the_cash_withdrawals_come_from_tranches_proportionally():
    returns = [[0, 1.0, 0, 1.0], [0, 0, 0, 0]]
    run = _run(returns, [[0, 1]], [[0] * 4], [[0, 0, 0.3, 0]], [[0, 1, -1, -1]], 2)
    # step 1: tranches [1.0, 0.5]; step 2: 0.3 of 1.5 -> x 0.8 -> [0.8, 0.4];
    # step 3: tranche 0 doubles -> 2.0 (all from tranche 0 would give 1.9)
    assert run.values[0] == pytest.approx([1.0, 1.5, 1.2, 2.0])


def test_withdraw_then_tranche_and_a_short_cash_invests_what_is_left():
    returns = [[0, 0, 0], [0, 5.0, 0]]
    run = _run(returns, [[0, 1]], [[0] * 3], [[0.6, 0, 0.1]], [[0, 1, -1]], 2)
    # step 0: withdraw 0.6 first, then the tranche is min(0.5, 0.4) = 0.4;
    # tranche 1 gets 0 (its 500% return changes nothing); step 2: 0.1 from it
    assert run.values[0] == pytest.approx([0.4, 0.4, 0.3])


def test_withdrawals_exhaust_the_cash_before_the_last_tranche():
    returns = [[0, 0, 0], [0, 0, 0], [0, 0, 10.0]]
    w = [[0.3, 0.3, 0.3]]
    run = _run(returns, [[0, 1, 2]], [[0] * 3], w, [[0, 1, 2]], 3)
    # step 0: cash 0.7, buy 1/3; step 1: cash 0.0667 < 1/3, all of it bought;
    # step 2: 0.3 from the invested 0.4; tranche 2 is 0, its +1000% moot
    assert run.values[0] == pytest.approx([0.7, 0.4, 0.1])


def test_depletion_with_staged_cash():
    returns = [[0, 0, 1.0], [0, 0, 0]]
    run = _run(returns, [[0, 1]], [[0] * 3], [[0.7, 0.7, 0]], [[0, 1, -1]], 2)
    assert run.values[0].tolist() == [pytest.approx(0.3), 0.0, 0.0]
    assert run.depleted.tolist() == [2]


def test_cash_at_or_below_depleted_counts_as_zero():
    # step 0: withdraw 0.5 - 5e-10, buy the 0.5 tranche: 5e-10 of cash dust is left,
    # which counts as 0. Step 1: cash earns +1e9; dust kept would add 0.5.
    w = [[0.5 - DEPLETED / 2, 0]]
    run = _run([[0, 0]], [[0]], [[0, 1e9]], w, [[0, -1]], 2)
    assert run.values[0] == pytest.approx([0.5, 0.5])
    assert run.depleted.tolist() == [0]


def test_a_path_does_nothing_before_it_begins():
    r = [[0.1] * 4, [0.1] * 4]
    run = _run(
        r, [[0], [1]], [[0] * 4] * 2, [[0] * 4] * 2, [[0, -1, -1, -1], [-1, -1, 0, -1]], 1, [0, 2]
    )
    assert run.values[0] == pytest.approx([1.1, 1.21, 1.331, 1.4641])
    assert run.values[1] == pytest.approx([1.0, 1.0, 1.1, 1.21])


def test_runner_refuses_nan_in_a_live_path_only():
    r = [[0.1, np.nan, 0.1]]
    with pytest.raises(ValueError, match="NaN return"):
        _run(r, [[0]], [[0] * 3], [[0] * 3], [[0, -1, -1]], 1)
    run = _run([[np.nan, 0.1, 0.1]], [[0]], [[0] * 3], [[0] * 3], [[-1, 0, -1]], 1, [1])
    assert run.values[0] == pytest.approx([1.0, 1.1, 1.21])


def test_runner_refuses_bad_shapes():
    with pytest.raises(ValueError, match="source must have shape"):
        _run([[0.0]], [[0, 0, 0]], [[0]], [[0]], [[0]], 2)
    with pytest.raises(ValueError, match="beyond"):
        _run([[0.0]], [[0]], [[0]], [[0]], [[3]], 2)


def test_a_total_loss_after_the_tranche_empties_only_that_path():
    # path 0 buys everything at step 0, then loses 100%: empty after the returns
    returns = [[-1.0, 0.0], [0.1, 0.1]]
    buy = [[0, -1], [0, -1]]
    run = _run(returns, [[0], [1]], [[0] * 2] * 2, [[0] * 2] * 2, buy, 1)
    assert run.values[0].tolist() == [0.0, 0.0]
    assert run.values[1] == pytest.approx([1.1, 1.21])
    assert run.depleted.tolist() == [1, 0]


def test_tranches_never_bought_stay_in_cash_and_earn_the_cash_return():
    # 6 tranches, 3 steps: 1/6 bought each step, the other 3/6 never leaves cash.
    # cash: 5/6 x 1.01 = 0.841667; -1/6 = 0.675 x 1.01 = 0.68175;
    # -1/6 = 0.5150833 x 1.01 = 0.5202342. Invested stays 1/6, 2/6, 3/6 (0% returns).
    run = _run([[0.0] * 3], [[0]], [[0.01] * 3], [[0] * 3], [[0, 1, 2]], 6)
    assert run.values[0] == pytest.approx(
        [0.166667 + 0.841667, 0.333333 + 0.68175, 0.5 + 0.5202342], abs=1e-6
    )
    assert run.depleted.tolist() == [0]
