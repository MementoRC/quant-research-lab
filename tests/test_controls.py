"""Tests for the null-sleeve control (qrl.controls, scripts/null_sleeve.py):
causal, long-only weights, and a script that refuses non-combined runs and
hash mismatches and never writes to the ledger. Offline, synthetic data."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qrl.checks import assert_causal
from qrl.controls import NULL_KINDS, null_sleeve_weights
from qrl.data import synthetic_prices
from qrl.ledger import Ledger

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from null_sleeve import main as null_main  # noqa: E402
from search import main as search_main  # noqa: E402
from test_combined import (  # noqa: E402
    LOOSE,
    TINY_TICKERS,
    _batch_argv,
    _combined_args,
    _copy_configs,
    _edit_yaml,
    _seed_combined,
    _write_tiny_universe,
)


@pytest.fixture(scope="module")
def close() -> pd.DataFrame:
    return synthetic_prices(TINY_TICKERS, end="2012-12-31")[1]


@pytest.mark.parametrize("kind", NULL_KINDS)
def test_null_weights_are_causal_long_only_and_capped(close, kind):
    assert_causal(lambda c: null_sleeve_weights(c, TINY_TICKERS, kind), close)
    w = null_sleeve_weights(close, TINY_TICKERS, kind)
    assert (w >= 0).all().all()
    assert (w.sum(axis=1) <= 1.0 + 1e-9).all()
    assert not w.isna().any().any()


def test_equal_weight_with_constant_prices():
    idx = pd.bdate_range("2020-01-01", periods=10)
    flat = pd.DataFrame(100.0, index=idx, columns=["A", "B", "C", "D"])
    w = null_sleeve_weights(flat, ["A", "B", "C", "D"], "equal_weight")
    assert np.allclose(w.to_numpy(), 0.25)


def test_equal_weight_skips_unpriced_tickers():
    idx = pd.bdate_range("2020-01-01", periods=4)
    px = pd.DataFrame(100.0, index=idx, columns=["A", "B"])
    px.loc[idx[:2], "B"] = np.nan
    w = null_sleeve_weights(px, ["A", "B"], "equal_weight")
    assert w["A"].tolist() == [1.0, 1.0, 0.5, 0.5]
    assert w["B"].tolist() == [0.0, 0.0, 0.5, 0.5]


def test_trend_kind_is_cash_before_200_days_then_holds_uptrends():
    idx = pd.bdate_range("2020-01-01", periods=260)
    px = pd.DataFrame(
        {"UP": np.linspace(100, 200, 260), "DOWN": np.linspace(200, 100, 260)}, index=idx
    )
    w = null_sleeve_weights(px, ["UP", "DOWN"], "equal_weight_trend")
    assert (w.iloc[:199] == 0.0).all().all()
    assert w["UP"].iloc[-1] == 1.0
    assert w["DOWN"].iloc[-1] == 0.0


def test_unknown_kind_raises(close):
    with pytest.raises(ValueError, match="unknown null sleeve kind"):
        null_sleeve_weights(close, TINY_TICKERS, "nope")


def _argv(ledger_path: Path, universe: Path, run_id: int, paths: dict) -> list[str]:
    return [
        "--run",
        str(run_id),
        "--ledger",
        str(ledger_path),
        "--synthetic",
        "--universe",
        str(universe),
        *_combined_args(paths),
    ]


def test_script_refuses_a_standalone_run(tmp_path):
    ledger_path = tmp_path / "ledger.sqlite"
    universe = _write_tiny_universe(tmp_path / "universe.yaml")
    seed = ["--ledger", str(ledger_path), "seed", "--lane", "A", "--synthetic"]
    assert search_main([*seed, "--universe", str(universe)]) == 0
    with Ledger(ledger_path) as ledger:
        run_id = ledger.list_runs()[-1]["run_id"]
    paths = _copy_configs(tmp_path)
    assert null_main(_argv(ledger_path, universe, run_id, paths)) == 2


def test_script_refuses_a_hash_mismatch(tmp_path):
    paths = _copy_configs(tmp_path)
    ledger_path, universe, run_id = _seed_combined(tmp_path, paths)
    _edit_yaml(paths["profile"], lambda d: d.update(capital_split={"core": 0.7, "sleeve": 0.3}))
    assert null_main(_argv(ledger_path, universe, run_id, paths)) == 2


def test_script_refuses_unknown_run_and_missing_ledger(tmp_path):
    paths = _copy_configs(tmp_path)
    ledger_path, universe, run_id = _seed_combined(tmp_path, paths)
    assert null_main(_argv(ledger_path, universe, run_id + 5, paths)) == 2
    assert null_main(_argv(tmp_path / "missing.sqlite", universe, run_id, paths)) == 2


def test_script_leaves_the_ledger_byte_identical(tmp_path, capsys):
    paths = _copy_configs(tmp_path, combined=LOOSE)
    ledger_path, universe, run_id = _seed_combined(tmp_path, paths)
    assert search_main(_batch_argv(ledger_path, universe, run_id, 4, paths)) == 0
    before = ledger_path.read_bytes()
    capsys.readouterr()

    assert null_main(_argv(ledger_path, universe, run_id, paths)) == 0

    assert ledger_path.read_bytes() == before
    out = capsys.readouterr().out
    assert "VERDICT [equal_weight]" in out
    assert "VERDICT [equal_weight_trend]" in out
    assert "recorded tests" in out
    with Ledger(ledger_path) as ledger:
        assert len(ledger.list_tests(run_id)) == 4
