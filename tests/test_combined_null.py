"""Tests for the combined_null ("beat the null") pass rule (milestone 2.5,
amendment 2026-10-02, run 5): config + hash binding, the null-combined
baseline, the ledger guard, and the scripts' wiring. Offline, synthetic data,
tmp ledgers only."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from qrl.combined import (
    build_core_weights,
    combined_checks,
    combined_config_for_run,
    combined_evaluation,
    load_combined_config,
    load_rule_config,
    null_baseline_sleeve,
)
from qrl.criteria import load_criteria
from qrl.data import synthetic_prices
from qrl.engine import run_backtest
from qrl.ledger import Ledger, LedgerError
from qrl.metrics import compute_metrics
from qrl.periods import slice_period
from qrl.portfolio import combine_portfolio

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
sys.path.insert(0, str(ROOT / "scripts"))

from null_sleeve import main as null_main  # noqa: E402
from search import main as search_main  # noqa: E402
from test_combined import CORE, SPLIT, _edit_yaml, _write_tiny_universe  # noqa: E402
from validate import main as validate_main  # noqa: E402

NULL_CODES = {
    "sleeve_min_trades",
    "combined_sharpe_improvement",
    "combined_max_drawdown",
    "combined_drawdown_vs_null",
    "combined_cagr_shortfall",
}
LOOSE_NULL = {
    "version": 1,
    "baseline": "null_equal_weight",
    "sleeve_min_trades": 0,
    "min_sharpe_improvement": -100.0,
    "max_drawdown": 1.0,
    "drawdown_no_worse_than_null": False,
    "max_cagr_shortfall": 100.0,
    "rank_by": "improvement_sharpe",
}
UNIVERSE = ["WIN", "LOSE"]


@pytest.fixture(scope="module")
def criteria() -> dict:
    return load_criteria(CONFIG / "criteria.yaml")[0]


@pytest.fixture(scope="module")
def cfg() -> dict:
    loaded, _ = load_combined_config(
        CONFIG / "combined_null.yaml", CONFIG / "profile.yaml", CONFIG / "portfolio.yaml"
    )
    return {**loaded, "null_tickers": UNIVERSE}


@pytest.fixture(scope="module")
def prices() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Synthetic core tickers plus WIN/LOSE sharing one noise path: WIN drifts
    up, LOSE down, so WIN out-returns LOSE every single day."""
    open_, close = synthetic_prices(["QQQ", "GLD"], end="2019-12-31")
    rng = np.random.default_rng(7)
    t = np.arange(len(close))
    noise = np.cumsum(rng.normal(0.0, 0.01, len(close)))
    for name, drift in (("WIN", 0.001), ("LOSE", -0.001)):
        path = 100.0 * np.exp(drift * t + noise)
        close[name] = path
        open_[name] = path
    return open_, close


def _only(close: pd.DataFrame, ticker: str) -> pd.DataFrame:
    w = pd.DataFrame(0.0, index=close.index, columns=UNIVERSE)
    w[ticker] = 1.0
    return w


def _copy_configs(tmp_path: Path, combined_null: dict | None = None) -> dict[str, Path]:
    paths = {
        "combined": tmp_path / "combined_null.yaml",
        "profile": tmp_path / "profile.yaml",
        "portfolio": tmp_path / "portfolio.yaml",
    }
    if combined_null is None:
        paths["combined"].write_bytes((CONFIG / "combined_null.yaml").read_bytes())
    else:
        paths["combined"].write_text(yaml.safe_dump(combined_null))
    paths["profile"].write_bytes((CONFIG / "profile.yaml").read_bytes())
    paths["portfolio"].write_bytes((CONFIG / "portfolio.yaml").read_bytes())
    return paths


def _cfg_args(paths: dict[str, Path], *, profile: bool = True) -> list[str]:
    args = ["--combined-config", str(paths["combined"]), "--portfolio", str(paths["portfolio"])]
    return [*args, "--profile", str(paths["profile"])] if profile else args


def _seed(tmp_path: Path, extra: list[str]) -> tuple[Path, Path, int]:
    ledger_path = tmp_path / "ledger.sqlite"
    universe = _write_tiny_universe(tmp_path / "universe.yaml")
    argv = [
        "--ledger",
        str(ledger_path),
        "seed",
        "--lane",
        "B",
        "--families",
        "trend_pullback",
        "--synthetic",
        "--universe",
        str(universe),
        "--pass-rule",
        "combined_null",
        *extra,
    ]
    assert search_main(argv) == 0
    with Ledger(ledger_path) as ledger:
        run_id = ledger.list_runs()[-1]["run_id"]
    return ledger_path, universe, run_id


def _run_argv(ledger_path: Path, universe: Path, run_id: int, paths: dict) -> list[str]:
    return [
        "--run",
        str(run_id),
        "--ledger",
        str(ledger_path),
        "--synthetic",
        "--universe",
        str(universe),
        *_cfg_args(paths),
    ]


def _batch_argv(ledger_path: Path, universe: Path, run_id: int, n: int, paths: dict) -> list[str]:
    return [
        "--ledger",
        str(ledger_path),
        "batch",
        "--run",
        str(run_id),
        "--n",
        str(n),
        "--synthetic",
        "--universe",
        str(universe),
        "--seed",
        "3",
        *_cfg_args(paths),
    ]


# ---------------------------------------------------------------------------
# Config load and hash binding.
# ---------------------------------------------------------------------------


def test_config_loads_with_null_baseline_and_pre_registered_thresholds():
    cfg, digest = load_combined_config(
        CONFIG / "combined_null.yaml", CONFIG / "profile.yaml", CONFIG / "portfolio.yaml"
    )
    assert cfg["baseline"] == "null_equal_weight"
    assert cfg["sleeve_min_trades"] == 10
    assert cfg["min_sharpe_improvement"] == 0.05
    assert cfg["max_drawdown"] == 0.35
    assert cfg["drawdown_no_worse_than_null"] is True
    assert cfg["max_cagr_shortfall"] == 0.01
    assert cfg["rank_by"] == "improvement_sharpe"
    assert cfg["capital_split"] == SPLIT
    assert cfg["core"] == CORE
    combined_digest = load_combined_config(
        CONFIG / "combined.yaml", CONFIG / "profile.yaml", CONFIG / "portfolio.yaml"
    )[1]
    assert len(digest) == 12
    assert digest != combined_digest


def test_hash_binds_yaml_split_and_core(tmp_path):
    paths = _copy_configs(tmp_path)

    def _h() -> str:
        return load_combined_config(paths["combined"], paths["profile"], paths["portfolio"])[1]

    base = _h()
    _edit_yaml(paths["combined"], lambda d: d.update(min_sharpe_improvement=0.04))
    edited = _h()
    assert edited != base
    _edit_yaml(paths["profile"], lambda d: d.update(capital_split={"core": 0.7, "sleeve": 0.3}))
    split = _h()
    assert split not in {base, edited}
    _edit_yaml(paths["portfolio"], lambda d: d["core"]["params"].update(lookback=150))
    assert _h() not in {base, edited, split}


def test_rule_and_config_baseline_must_match():
    args = (CONFIG / "profile.yaml", CONFIG / "portfolio.yaml")
    with pytest.raises(ValueError, match="does not match pass rule"):
        load_rule_config("combined_null", CONFIG / "combined.yaml", *args)
    with pytest.raises(ValueError, match="does not match pass rule"):
        load_rule_config("combined", CONFIG / "combined_null.yaml", *args)


def test_run_config_needs_universe_tickers_and_adds_them():
    _, digest = load_combined_config(
        CONFIG / "combined_null.yaml", CONFIG / "profile.yaml", CONFIG / "portfolio.yaml"
    )
    run = {"run_id": 9, "pass_rule": "combined_null", "combined_config_hash": digest}
    args = (CONFIG / "combined_null.yaml", CONFIG / "profile.yaml", CONFIG / "portfolio.yaml")
    with pytest.raises(ValueError, match="universe tickers"):
        combined_config_for_run(run, *args)
    loaded = combined_config_for_run(run, *args, universe_tickers=UNIVERSE)
    assert loaded is not None
    assert loaded[0]["null_tickers"] == UNIVERSE
    with pytest.raises(ValueError, match="hash has changed"):
        combined_config_for_run({**run, "combined_config_hash": "x"}, *args, universe_tickers=["A"])


def test_batch_and_validate_refuse_when_config_changed(tmp_path):
    paths = _copy_configs(tmp_path)
    ledger_path, universe, run_id = _seed(tmp_path, _cfg_args(paths, profile=False))
    _edit_yaml(paths["combined"], lambda d: d.update(max_cagr_shortfall=0.02))

    assert search_main(_batch_argv(ledger_path, universe, run_id, 3, paths)) == 2
    assert validate_main(_run_argv(ledger_path, universe, run_id, paths)) == 2
    assert null_main(_run_argv(ledger_path, universe, run_id, paths)) == 2
    with Ledger(ledger_path) as ledger:
        assert ledger.list_tests(run_id) == []


def test_seed_refuses_combined_yaml_for_combined_null(tmp_path):
    ledger_path = tmp_path / "ledger.sqlite"
    universe = _write_tiny_universe(tmp_path / "universe.yaml")
    argv = ["--ledger", str(ledger_path), "seed", "--lane", "A", "--synthetic"]
    argv += ["--universe", str(universe), "--pass-rule", "combined_null"]
    assert search_main([*argv, "--combined-config", str(CONFIG / "combined.yaml")]) == 2
    with Ledger(ledger_path) as ledger:
        assert ledger.list_runs() == []


def test_seed_defaults_to_combined_null_yaml(tmp_path):
    ledger_path, _, run_id = _seed(tmp_path, [])
    expected = load_combined_config(
        CONFIG / "combined_null.yaml", CONFIG / "profile.yaml", CONFIG / "portfolio.yaml"
    )[1]
    with Ledger(ledger_path) as ledger:
        run = ledger.list_runs()[-1]
        assert ledger.pass_rule(run_id) == "combined_null"
    assert run["combined_config_hash"] == expected


# ---------------------------------------------------------------------------
# The null-combined baseline.
# ---------------------------------------------------------------------------


def test_null_vs_null_fails_the_sharpe_margin(prices, criteria, cfg):
    open_, close = prices
    null = null_baseline_sleeve(open_, close, UNIVERSE)
    ce = combined_evaluation(null, open_, close, CORE, SPLIT, criteria, cfg, sleeve_trades=50)
    assert (ce["improvement"] == 0.0).all()
    pd.testing.assert_series_equal(ce["combined_returns"], ce["null_returns"], check_names=False)
    assert ce["passed"] is False
    assert "combined_sharpe_improvement" in ce["failure_reasons"].split(",")


def test_improvement_is_candidate_minus_null_combined(prices, criteria, cfg):
    open_, close = prices
    ce = combined_evaluation(_only(close, "WIN"), open_, close, CORE, SPLIT, criteria, cfg)
    assert "core_returns" not in ce
    pd.testing.assert_series_equal(ce["improvement"], ce["combined_returns"] - ce["null_returns"])

    _, core_w = build_core_weights(CORE, close)
    baseline = combine_portfolio(core_w, [null_baseline_sleeve(open_, close, UNIVERSE)], SPLIT)
    cols = list(baseline.combined.columns)
    direct = run_backtest(
        open_[cols],
        close[cols],
        slice_period(baseline.combined, criteria, "research"),
        cost_bps=criteria["costs"]["bps_per_unit_turnover"],
    )
    pd.testing.assert_series_equal(ce["null_returns"], direct.returns, check_names=False)
    assert ce["null_metrics"] == compute_metrics(direct.returns, direct.turnover, direct.executed)


def test_a_sleeve_that_beats_the_null_passes(prices, criteria, cfg):
    open_, close = prices
    ce = combined_evaluation(
        _only(close, "WIN"), open_, close, CORE, SPLIT, criteria, cfg, sleeve_trades=50
    )
    assert ce["passed"] is True, ce["failure_reasons"]
    assert {c["rule"] for c in ce["checks"]} == NULL_CODES
    assert ce["improvement_sharpe"] > 0


def test_drawdown_worse_than_the_null_fails(prices, criteria, cfg):
    open_, close = prices
    ce = combined_evaluation(
        _only(close, "LOSE"), open_, close, CORE, SPLIT, criteria, cfg, sleeve_trades=50
    )
    assert ce["passed"] is False
    assert "combined_drawdown_vs_null" in ce["failure_reasons"].split(",")


_NULL_M = {"sharpe": 1.0, "max_drawdown": 0.20, "cagr": 0.10}
_GOOD_M = {"sharpe": 1.10, "max_drawdown": 0.18, "cagr": 0.10}


@pytest.mark.parametrize(
    ("code", "combined", "trades"),
    [
        ("sleeve_min_trades", _GOOD_M, 5),
        ("combined_sharpe_improvement", {**_GOOD_M, "sharpe": 1.04}, 50),
        ("combined_drawdown_vs_null", {**_GOOD_M, "max_drawdown": 0.21}, 50),
        ("combined_cagr_shortfall", {**_GOOD_M, "cagr": 0.085}, 50),
    ],
)
def test_each_null_failure_code_triggers_alone(cfg, code, combined, trades):
    checks = combined_checks(combined, _NULL_M, trades, cfg)
    assert {c["rule"] for c in checks} == NULL_CODES
    assert {c["rule"] for c in checks if not c["passed"]} == {code}


def test_absolute_drawdown_cap_still_applies(cfg):
    deep = {**_NULL_M, "max_drawdown": 0.45}
    checks = combined_checks({**_GOOD_M, "max_drawdown": 0.40}, deep, 50, cfg)
    assert {c["rule"] for c in checks if not c["passed"]} == {"combined_max_drawdown"}


def test_holdout_is_refused(prices, criteria, cfg):
    open_, close = prices
    with pytest.raises(ValueError, match="holdout"):
        combined_evaluation(
            _only(close, "WIN"), open_, close, CORE, SPLIT, criteria, cfg, period="holdout"
        )


# ---------------------------------------------------------------------------
# Ledger guard and end-to-end wiring.
# ---------------------------------------------------------------------------


def test_ledger_accepts_combined_null_with_hash_guard(tmp_path):
    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        with pytest.raises(LedgerError):
            ledger.start_run("crit", "A", "no hash", pass_rule="combined_null")
        run_id = ledger.start_run(
            "crit", "A", "run 5", pass_rule="combined_null", combined_config_hash="abc"
        )
        assert ledger.pass_rule(run_id) == "combined_null"
        ledger.record_test(run_id, "crit", "f", {}, "u", {}, True, combined_config_hash="abc")
        with pytest.raises(LedgerError, match="combined config hash mismatch"):
            ledger.record_test(run_id, "crit", "f", {"x": 1}, "u", {}, True)
        with pytest.raises(LedgerError, match="combined config hash mismatch"):
            ledger.record_test(
                run_id, "crit", "f", {"x": 2}, "u", {}, True, combined_config_hash="zzz"
            )
        assert len(ledger.list_tests(run_id)) == 1


def test_combined_null_run_end_to_end(tmp_path, capsys):
    paths = _copy_configs(tmp_path, combined_null=LOOSE_NULL)
    ledger_path, universe, run_id = _seed(tmp_path, _cfg_args(paths, profile=False))
    assert search_main(_batch_argv(ledger_path, universe, run_id, 3, paths)) == 0

    with Ledger(ledger_path) as ledger:
        history = ledger.list_tests(run_id)
        trials = ledger.trial_sharpes(run_id, key="improvement_sharpe")
    assert len(history) == 3
    for row in history:
        codes = set((row["failure_reasons"] or "").split(",")) - {""}
        assert codes <= NULL_CODES or row["failure_reasons"].startswith("error:")
    assert len(trials) == 3

    capsys.readouterr()
    assert search_main(["--ledger", str(ledger_path), "summary", "--run", str(run_id)]) == 0
    assert "Pass rule: combined_null" in capsys.readouterr().out

    before = ledger_path.read_bytes()
    assert null_main(_run_argv(ledger_path, universe, run_id, paths)) == 0
    out = capsys.readouterr().out
    assert "[equal_weight] combined_null rule" in out
    assert "Core + null" in out
    assert ledger_path.read_bytes() == before
