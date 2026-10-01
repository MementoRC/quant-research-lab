"""Tests for the combined pass rule (PLAN.md 2.5, amendment 2026-10-01):
qrl.combined, its ledger guard, and its opt-in wiring through
scripts/search.py, scripts/validate.py and scripts/rebuild_validation.py.
Offline and on synthetic data only."""

from __future__ import annotations

import json
import math
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

import qrl.validation as validation_mod
from qrl.combined import (
    build_core_weights,
    combined_checks,
    combined_config_for_run,
    combined_evaluation,
    load_combined_config,
)
from qrl.criteria import load_criteria
from qrl.data import synthetic_prices
from qrl.engine import run_backtest
from qrl.ledger import Ledger, LedgerError
from qrl.metrics import TRADING_DAYS, compute_metrics
from qrl.periods import slice_period
from qrl.portfolio import combine_portfolio
from qrl.search import SearchData, evaluate_candidate

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import rebuild_validation as rv  # noqa: E402
from search import main as search_main  # noqa: E402
from validate import main as validate_main  # noqa: E402

TINY_TICKERS = ["AAA", "BBB", "CCC", "DDD"]
CORE = {"fn": "core_trend", "params": {"risk_on": "QQQ", "risk_off": "GLD", "lookback": 200}}
SPLIT = {"core": 0.8, "sleeve": 0.2}
COMBINED_CODES = {
    "sleeve_min_trades",
    "combined_sharpe_improvement",
    "combined_max_drawdown",
    "combined_drawdown_vs_core",
    "combined_cagr_shortfall",
}
LOOSE = {
    "version": 1,
    "sleeve_min_trades": 0,
    "min_sharpe_improvement": -100.0,
    "max_drawdown": 1.0,
    "drawdown_no_worse_than_core": False,
    "max_cagr_shortfall": 100.0,
    "rank_by": "improvement_sharpe",
}


@pytest.fixture(scope="module")
def criteria() -> dict:
    return load_criteria(CONFIG / "criteria.yaml")[0]


@pytest.fixture(scope="module")
def cfg() -> dict:
    return load_combined_config(
        CONFIG / "combined.yaml", CONFIG / "profile.yaml", CONFIG / "portfolio.yaml"
    )[0]


@pytest.fixture(scope="module")
def prices() -> tuple[pd.DataFrame, pd.DataFrame]:
    return synthetic_prices(["QQQ", "GLD", "AAA"], end="2019-12-31")


def _cash_sleeve(close: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(0.0, index=close.index, columns=["AAA"])


def _copy_configs(tmp_path: Path, combined: dict | None = None) -> dict[str, Path]:
    paths = {
        "combined": tmp_path / "combined.yaml",
        "profile": tmp_path / "profile.yaml",
        "portfolio": tmp_path / "portfolio.yaml",
    }
    if combined is None:
        paths["combined"].write_bytes((CONFIG / "combined.yaml").read_bytes())
    else:
        paths["combined"].write_text(yaml.safe_dump(combined))
    paths["profile"].write_bytes((CONFIG / "profile.yaml").read_bytes())
    paths["portfolio"].write_bytes((CONFIG / "portfolio.yaml").read_bytes())
    return paths


def _hash(paths: dict[str, Path]) -> str:
    return load_combined_config(paths["combined"], paths["profile"], paths["portfolio"])[1]


def _edit_yaml(path: Path, edit) -> None:
    data = yaml.safe_load(path.read_text())
    edit(data)
    path.write_text(yaml.safe_dump(data))


def _write_tiny_universe(path: Path) -> Path:
    path.write_text(
        yaml.safe_dump(
            {
                "name": "tiny_test_universe",
                "as_of": "2026-09",
                "source": "test fixture",
                "survivorship_biased": False,
                "tickers": TINY_TICKERS,
            }
        )
    )
    return path


def _combined_args(paths: dict[str, Path], *, profile: bool = True) -> list[str]:
    args = ["--combined-config", str(paths["combined"]), "--portfolio", str(paths["portfolio"])]
    return [*args, "--profile", str(paths["profile"])] if profile else args


def _seed_combined(tmp_path: Path, paths: dict[str, Path]) -> tuple[Path, Path, int]:
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
        "combined",
        *_combined_args(paths),
    ]
    assert search_main(argv) == 0
    with Ledger(ledger_path) as ledger:
        run_id = ledger.list_runs()[-1]["run_id"]
    return ledger_path, universe, run_id


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
        *_combined_args(paths),
    ]


# ---------------------------------------------------------------------------
# Combined metrics math against a hand-built example.
# ---------------------------------------------------------------------------


def test_core_alone_equals_a_direct_backtest_of_the_core(prices, criteria, cfg):
    open_, close = prices
    ce = combined_evaluation(_cash_sleeve(close), open_, close, CORE, SPLIT, criteria, cfg)

    tickers, core_w = build_core_weights(CORE, close)
    direct = run_backtest(
        open_[tickers],
        close[tickers],
        slice_period(core_w, criteria, "research"),
        cost_bps=criteria["costs"]["bps_per_unit_turnover"],
    )
    pd.testing.assert_series_equal(ce["core_returns"], direct.returns)
    assert ce["core_metrics"] == compute_metrics(direct.returns, direct.turnover, direct.executed)


def test_all_cash_sleeve_is_80pct_core_plus_20pct_cash(prices, criteria, cfg):
    open_, close = prices
    sleeve = _cash_sleeve(close)
    ce = combined_evaluation(sleeve, open_, close, CORE, SPLIT, criteria, cfg)

    tickers, core_w = build_core_weights(CORE, close)
    pw = combine_portfolio(core_w, [sleeve], SPLIT)
    pd.testing.assert_frame_equal(pw.combined[tickers], core_w.fillna(0.0) * 0.8)
    assert (pw.combined["AAA"] == 0.0).all()
    assert (pw.combined.sum(axis=1) <= 0.8 + 1e-12).all()  # the other 20% sits in cash

    scaled = run_backtest(
        open_[tickers],
        close[tickers],
        slice_period(core_w.fillna(0.0) * 0.8, criteria, "research"),
        cost_bps=criteria["costs"]["bps_per_unit_turnover"],
    )
    pd.testing.assert_series_equal(ce["combined_returns"], scaled.returns, check_names=False)

    improvement = ce["combined_returns"] - ce["core_returns"]
    pd.testing.assert_series_equal(ce["improvement"], improvement)
    expected = improvement.mean() / improvement.std() * math.sqrt(TRADING_DAYS)
    assert ce["improvement_sharpe"] == pytest.approx(expected)
    # An all-cash sleeve never trades, so it can never pass.
    assert ce["sleeve_trades"] == 0
    assert ce["passed"] is False
    assert "sleeve_min_trades" in ce["failure_reasons"].split(",")


def test_combined_evaluation_refuses_holdout(prices, criteria, cfg):
    open_, close = prices
    with pytest.raises(ValueError, match="holdout"):
        combined_evaluation(
            _cash_sleeve(close), open_, close, CORE, SPLIT, criteria, cfg, period="holdout"
        )


# ---------------------------------------------------------------------------
# Each failure code triggers.
# ---------------------------------------------------------------------------

_CORE_M = {"sharpe": 1.0, "max_drawdown": 0.20, "cagr": 0.10}
_GOOD_M = {"sharpe": 1.10, "max_drawdown": 0.18, "cagr": 0.10}


@pytest.mark.parametrize(
    ("code", "combined", "core", "trades"),
    [
        ("sleeve_min_trades", _GOOD_M, _CORE_M, 5),
        ("combined_sharpe_improvement", {**_GOOD_M, "sharpe": 1.04}, _CORE_M, 50),
        (
            "combined_max_drawdown",
            {**_GOOD_M, "max_drawdown": 0.40},
            {**_CORE_M, "max_drawdown": 0.45},
            50,
        ),
        ("combined_drawdown_vs_core", {**_GOOD_M, "max_drawdown": 0.25}, _CORE_M, 50),
        ("combined_cagr_shortfall", {**_GOOD_M, "cagr": 0.085}, _CORE_M, 50),
    ],
)
def test_each_failure_code_triggers_alone(cfg, code, combined, core, trades):
    checks = combined_checks(combined, core, trades, cfg)
    assert {c["rule"] for c in checks} == COMBINED_CODES
    assert {c["rule"] for c in checks if not c["passed"]} == {code}


def test_all_checks_pass_for_a_real_improvement(cfg):
    assert all(c["passed"] for c in combined_checks(_GOOD_M, _CORE_M, 50, cfg))


def test_drawdown_vs_core_check_is_optional(cfg):
    checks = combined_checks(_GOOD_M, _CORE_M, 50, {**cfg, "drawdown_no_worse_than_core": False})
    assert "combined_drawdown_vs_core" not in {c["rule"] for c in checks}


# ---------------------------------------------------------------------------
# Hash binding: combined.yaml, the capital split, and the core spec.
# ---------------------------------------------------------------------------


def test_hash_changes_with_combined_yaml_split_or_core(tmp_path):
    paths = _copy_configs(tmp_path)
    base = _hash(paths)
    assert base == _hash(paths)

    _edit_yaml(paths["profile"], lambda d: d.update(trades_per_week=4))
    assert _hash(paths) == base  # an unrelated profile field is not bound

    _edit_yaml(paths["combined"], lambda d: d.update(min_sharpe_improvement=0.04))
    changed_cfg = _hash(paths)
    assert changed_cfg != base

    _edit_yaml(paths["profile"], lambda d: d.update(capital_split={"core": 0.7, "sleeve": 0.3}))
    changed_split = _hash(paths)
    assert changed_split not in {base, changed_cfg}

    _edit_yaml(paths["portfolio"], lambda d: d["core"]["params"].update(lookback=150))
    assert _hash(paths) not in {base, changed_cfg, changed_split}


def test_loaded_config_carries_split_and_core():
    cfg, _ = load_combined_config(
        CONFIG / "combined.yaml", CONFIG / "profile.yaml", CONFIG / "portfolio.yaml"
    )
    assert cfg["capital_split"] == SPLIT
    assert cfg["core"] == CORE
    assert cfg["rank_by"] == "improvement_sharpe"


def test_ledger_refuses_a_mismatched_combined_hash(tmp_path):
    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        run_id = ledger.start_run(
            "crit", "A", "combined", pass_rule="combined", combined_config_hash="abc"
        )
        ledger.record_test(run_id, "crit", "f", {}, "u", {}, True, combined_config_hash="abc")
        with pytest.raises(LedgerError, match="combined config hash mismatch"):
            ledger.record_test(run_id, "crit", "f", {"x": 1}, "u", {}, True)
        with pytest.raises(LedgerError, match="combined config hash mismatch"):
            ledger.record_test(
                run_id, "crit", "f", {"x": 2}, "u", {}, True, combined_config_hash="zzz"
            )
        with pytest.raises(LedgerError):
            ledger.start_run("crit", "A", "no hash", pass_rule="combined")
        with pytest.raises(LedgerError):
            ledger.start_run("crit", "A", "bad rule", pass_rule="bogus")
        assert len(ledger.list_tests(run_id)) == 1


def test_batch_and_validate_refuse_when_combined_config_changed(tmp_path):
    paths = _copy_configs(tmp_path)
    ledger_path, universe, run_id = _seed_combined(tmp_path, paths)
    _edit_yaml(paths["profile"], lambda d: d.update(capital_split={"core": 0.7, "sleeve": 0.3}))

    assert search_main(_batch_argv(ledger_path, universe, run_id, 3, paths)) == 2
    validate_argv = [
        "--run",
        str(run_id),
        "--ledger",
        str(ledger_path),
        "--synthetic",
        "--universe",
        str(universe),
        *_combined_args(paths),
    ]
    assert validate_main(validate_argv) == 2
    with Ledger(ledger_path) as ledger:
        assert ledger.list_tests(run_id) == []


# ---------------------------------------------------------------------------
# Pre-existing runs and NULL pass_rule behave as standalone.
# ---------------------------------------------------------------------------


def test_legacy_runs_gain_null_columns_and_stay_standalone(tmp_path):
    path = tmp_path / "legacy.sqlite"
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(
            """
            CREATE TABLE runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                git_commit TEXT,
                criteria_hash TEXT NOT NULL,
                seed_lane TEXT NOT NULL CHECK (seed_lane IN ('A', 'B', 'C')),
                seed_description TEXT,
                data_source TEXT
            );
            """
        )
        conn.execute(
            "INSERT INTO runs (started_at, criteria_hash, seed_lane, seed_description) "
            "VALUES ('2020-01-01T00:00:00+00:00', 'crit', 'A', 'old run')"
        )
        conn.commit()
    finally:
        conn.close()

    with Ledger(path) as ledger:
        columns = {row[1] for row in ledger._conn.execute("PRAGMA table_info(runs)")}
        assert {"pass_rule", "combined_config_hash"} <= columns
        run = ledger.list_runs()[0]
        assert run["seed_description"] == "old run"
        assert run["pass_rule"] is None
        assert run["combined_config_hash"] is None
        assert ledger.pass_rule(run["run_id"]) == "standalone"
        ledger.record_test(run["run_id"], "crit", "f", {}, "u", {"sharpe": 0.7}, True)
        with pytest.raises(LedgerError, match="combined config hash mismatch"):
            ledger.record_test(
                run["run_id"], "crit", "f", {"x": 1}, "u", {}, True, combined_config_hash="abc"
            )
        assert ledger.trial_sharpes(run["run_id"]) == [0.7]
    assert combined_config_for_run(run, "unused", "unused", "unused") is None


def test_default_seed_is_standalone_and_summary_says_so(tmp_path, capsys):
    ledger_path = tmp_path / "ledger.sqlite"
    universe = _write_tiny_universe(tmp_path / "universe.yaml")
    argv = ["--ledger", str(ledger_path), "seed", "--lane", "A", "--synthetic"]
    assert search_main([*argv, "--universe", str(universe)]) == 0
    with Ledger(ledger_path) as ledger:
        run = ledger.list_runs()[-1]
        assert ledger.pass_rule(run["run_id"]) == "standalone"
    assert run["combined_config_hash"] is None
    capsys.readouterr()
    assert search_main(["--ledger", str(ledger_path), "summary", "--run", str(run["run_id"])]) == 0
    assert "Pass rule: standalone" in capsys.readouterr().out


def test_evaluate_candidate_without_combined_cfg_is_unchanged(criteria, cfg):
    data = SearchData.load([*TINY_TICKERS, "QQQ", "GLD"], synthetic=True)
    params = {"trend_lookback": 150, "short_ma": 10, "tickers": TINY_TICKERS}
    plain = evaluate_candidate("trend_pullback", params, data, criteria)
    assert set(plain) == {"metrics", "passed", "failure_reasons", "checks", "returns"}
    assert "improvement_sharpe" not in plain["metrics"]

    comb = evaluate_candidate("trend_pullback", params, data, criteria, combined_cfg=cfg)
    for key, value in plain["metrics"].items():
        assert comb["metrics"][key] == value  # standalone metrics still stored as-is
    assert {"combined_sharpe", "core_sharpe", "improvement_sharpe"} <= set(comb["metrics"])
    assert {c["rule"] for c in comb["checks"]} == COMBINED_CODES
    pd.testing.assert_series_equal(comb["returns"], plain["returns"])


# ---------------------------------------------------------------------------
# End to end: seed, batch, validate a combined run on synthetic data.
# ---------------------------------------------------------------------------


def _rows(ledger_path: Path, sql: str, args: tuple) -> list[dict]:
    conn = sqlite3.connect(str(ledger_path))
    try:
        return [json.loads(r[0]) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def test_combined_run_end_to_end(tmp_path, monkeypatch, capsys):
    paths = _copy_configs(tmp_path, combined=LOOSE)
    ledger_path, universe, run_id = _seed_combined(tmp_path, paths)
    assert search_main(_batch_argv(ledger_path, universe, run_id, 4, paths)) == 0

    with Ledger(ledger_path) as ledger:
        history = ledger.list_tests(run_id)
        assert ledger.pass_rule(run_id) == "combined"
    assert len(history) == 4
    for row in history:
        codes = set((row["failure_reasons"] or "").split(",")) - {""}
        assert codes <= COMBINED_CODES or row["failure_reasons"].startswith("error:")
    metrics = _rows(ledger_path, "SELECT metrics_json FROM tests WHERE run_id = ?", (run_id,))
    assert all(
        {"sharpe", "combined_sharpe", "core_sharpe", "improvement_sharpe"} <= set(m)
        for m in metrics
    )

    capsys.readouterr()
    assert search_main(["--ledger", str(ledger_path), "summary", "--run", str(run_id)]) == 0
    assert "Pass rule: combined" in capsys.readouterr().out

    val_cfg = yaml.safe_load((CONFIG / "validation.yaml").read_text())
    # Thresholds opened up so the accept path (and the correlation filter on
    # improvement series) is exercised; the DSR spy below checks its inputs.
    val_cfg.update(top_n_to_validate=2, max_correlation=1.0, min_deflated_sharpe=0.0)
    val_cfg["neighborhood"]["fraction_required"] = 0.0
    val_path = tmp_path / "validation.yaml"
    val_path.write_text(yaml.safe_dump(val_cfg))

    calls: list[tuple[float, list[float], int]] = []
    real_dsr = validation_mod.deflated_sharpe_ratio

    def _spy(observed, trials, n_obs, skew, kurtosis):
        calls.append((observed, list(trials), n_obs))
        return real_dsr(observed, trials, n_obs, skew, kurtosis)

    monkeypatch.setattr(validation_mod, "deflated_sharpe_ratio", _spy)
    validate_argv = [
        "--run",
        str(run_id),
        "--ledger",
        str(ledger_path),
        "--synthetic",
        "--universe",
        str(universe),
        "--validation-config",
        str(val_path),
        *_combined_args(paths),
    ]
    capsys.readouterr()
    assert validate_main(validate_argv) == 0
    out = capsys.readouterr().out
    assert "Pass rule: combined" in out
    assert " accepted" in out

    events = _rows(ledger_path, "SELECT metrics_json FROM validation_events", ())
    all_rows = _rows(
        ledger_path, "SELECT metrics_json FROM tests WHERE run_id = ? ORDER BY test_id", (run_id,)
    )
    assert calls
    assert events
    for observed, trials, n_obs in calls:
        event = next(e for e in events if e.get("improvement_sharpe") == observed)
        assert n_obs == event["combined_days"]  # the validation improvement series
        assert len(trials) > len(history)  # neighbours count as trials too
        assert trials == [m.get("improvement_sharpe", 0.0) for m in all_rows[: len(trials)]]


def test_rebuild_validation_refuses_combined_runs(tmp_path, capsys):
    paths = _copy_configs(tmp_path)
    ledger_path, universe, run_id = _seed_combined(tmp_path, paths)
    argv = ["--run", str(run_id), "--ledger", str(ledger_path), "--synthetic"]
    assert rv.main([*argv, "--universe", str(universe)]) == 2
    assert "not supported for combined runs yet" in capsys.readouterr().err
