"""Tests for scripts/rebuild_validation.py: it must reproduce, read-only, the
funnel and per-candidate outcome the real `validate_survivors` returned.
Offline, synthetic data, tmp ledger.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from qrl.criteria import load_criteria
from qrl.ledger import Ledger, data_source_fingerprint
from qrl.search import SearchData, compute_benchmark_metrics, evaluate_candidate
from qrl.universe import load_universe
from qrl.validation import load_validation_config, validate_survivors

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import rebuild_validation as rv  # noqa: E402
from validate import DEFAULT_UNIVERSE_TICKERS, SEARCHABLE_SPACES  # noqa: E402

FAMILY = "core_trend"


@pytest.fixture(scope="module")
def env():
    criteria, criteria_hash = load_criteria(ROOT / "config" / "criteria.yaml")
    cfg, cfg_hash = load_validation_config(ROOT / "config" / "validation.yaml")
    strict = {**cfg, "top_n_to_validate": 3}  # real fraction_required: synthetic neighbours fail
    # fraction_required 0 lets every candidate reach validation, exercising DSR/correlation.
    cfg = {**strict, "neighborhood": {"fraction_required": 0.0}}
    universe = load_universe(ROOT / "config" / "universe.yaml")
    needed = set(universe["tickers"]) | set(DEFAULT_UNIVERSE_TICKERS) | set(criteria["benchmarks"])
    data = SearchData.load(sorted(needed), synthetic=True)
    return {
        "criteria": criteria,
        "criteria_hash": criteria_hash,
        "cfg": cfg,
        "strict": strict,
        "cfg_hash": cfg_hash,
        "universe": universe,
        "data": data,
        "bench": compute_benchmark_metrics(data, criteria),
    }


def _seed_run(ledger: Ledger, env: dict) -> int:
    uni = env["universe"]
    source = data_source_fingerprint(True, uni["name"], list(uni["tickers"]))
    run_id = ledger.start_run(env["criteria_hash"], "A", "rebuild test", data_source=source)
    for lookback in (200, 150, 100):
        params = {"lookback": lookback, "risk_off": "GLD"}
        out = evaluate_candidate(FAMILY, params, env["data"], env["criteria"], env["bench"])
        # Force survivor status regardless of the real research outcome.
        ledger.record_test(
            run_id, env["criteria_hash"], FAMILY, params, uni["name"], out["metrics"], True, None
        )
    return run_id


def _validate(ledger: Ledger, run_id: int, env: dict, cfg_hash: str, cfg_key: str = "cfg") -> dict:
    return validate_survivors(
        ledger,
        run_id,
        env["data"],
        env["criteria"],
        env[cfg_key],
        cfg_hash,
        criteria_hash=env["criteria_hash"],
        universe_name=env["universe"]["name"],
        spaces=SEARCHABLE_SPACES,
        benchmark_metrics=env["bench"],
    )


def _add_later_rows(ledger: Ledger, run_id: int, env: dict) -> None:
    """Rows recorded AFTER validation that, if wrongly included, would change
    the survivor ranking and the DSR trial set."""
    name = env["universe"]["name"]
    for lookback in (50, 250):
        params = {"lookback": lookback, "risk_off": "TLT"}
        ledger.record_test(
            run_id, env["criteria_hash"], FAMILY, params, name, {"sharpe": 99.0, "trades": 1},
            True, None,
        )  # fmt: skip
    for lookback in (50, 100, 150):
        params = {"lookback": lookback, "risk_off": "CASH"}
        ledger.record_test(
            run_id, env["criteria_hash"], FAMILY, params, name, {"sharpe": 5.0}, False, "sharpe"
        )


def _rebuild(
    path: Path, run_id: int, env: dict, *, backtest: bool, cfg_key: str = "cfg"
) -> list[dict]:
    conn = rv.connect_ro(path)
    try:
        rows = rv.load_rows(conn, run_id)
        events = rv.load_events(conn, run_id)
    finally:
        conn.close()
    return rv.rebuild(
        rows,
        events,
        env[cfg_key],
        SEARCHABLE_SPACES,
        backtest=backtest,
        data=env["data"] if backtest else None,
        criteria=env["criteria"],
        bench=env["bench"],
        invocation_gap=900.0,
    )


def _outcomes(candidates: list[dict]) -> list[tuple]:
    return [(c["test_id"], c["family"], c["stage"], c["reason"]) for c in candidates]


def test_rebuild_matches_real_report_with_later_rows(tmp_path, env):
    path = tmp_path / "ledger.sqlite"
    with Ledger(path) as ledger:
        run_id = _seed_run(ledger, env)
        report = _validate(ledger, run_id, env, env["cfg_hash"])
        assert report["funnel"]["validated"] >= 1
        _add_later_rows(ledger, run_id, env)

    (res,) = _rebuild(path, run_id, env, backtest=True)

    assert res["funnel"] == report["funnel"]
    assert _outcomes(res["candidates"]) == _outcomes(report["candidates"])
    assert not res["missing_from_replay"]
    assert not res["extra_in_replay"]
    assert all(c["tag"] == "exact" for c in res["candidates"] if "check" in c)
    assert all(c["check"] == "MATCH" for c in res["candidates"] if "check" in c)


def test_rebuild_after_an_invisible_all_rejected_invocation(tmp_path, env):
    path = tmp_path / "ledger.sqlite"
    with Ledger(path) as ledger:
        run_id = _seed_run(ledger, env)
        report = _validate(ledger, run_id, env, env["cfg_hash"], "strict")
        _add_later_rows(ledger, run_id, env)
        # The strict invocation leaves neighbour rows but no event (invisible to the
        # rebuild); the lenient one after it must still replay exactly.
        report_2 = _validate(ledger, run_id, env, "cfg_lenient")

    results = _rebuild(path, run_id, env, backtest=True, cfg_key="cfg")
    assert report["funnel"]["validated"] == 0
    (res,) = results
    assert res["funnel"] == report_2["funnel"]
    assert _outcomes(res["candidates"]) == _outcomes(report_2["candidates"])


def test_rebuild_two_invocations_with_rows_between(tmp_path, env):
    path = tmp_path / "ledger.sqlite"
    with Ledger(path) as ledger:
        run_id = _seed_run(ledger, env)
        report_1 = _validate(ledger, run_id, env, "cfg_one")
        _add_later_rows(ledger, run_id, env)
        report_2 = _validate(ledger, run_id, env, "cfg_two")
        _add_later_rows(ledger, run_id, env)

    res_1, res_2 = _rebuild(path, run_id, env, backtest=True)

    for res, report in ((res_1, report_1), (res_2, report_2)):
        assert res["funnel"] == report["funnel"]
        assert _outcomes(res["candidates"]) == _outcomes(report["candidates"])
        assert not res["missing_from_replay"]
        assert not res["extra_in_replay"]


def test_no_backtest_neighbourhood_stages_match(tmp_path, env):
    path = tmp_path / "ledger.sqlite"
    with Ledger(path) as ledger:
        run_id = _seed_run(ledger, env)
        report = _validate(ledger, run_id, env, env["cfg_hash"])
        _add_later_rows(ledger, run_id, env)

    (res,) = _rebuild(path, run_id, env, backtest=False)

    assert res["funnel"]["survivors"] == report["funnel"]["survivors"]
    assert res["funnel"]["passed_neighbourhood"] == report["funnel"]["passed_neighbourhood"]
    assert res["funnel"]["validated"] == report["funnel"]["validated"]
    assert not res["missing_from_replay"]
    assert not res["extra_in_replay"]
    real = {c["test_id"]: c for c in report["candidates"]}
    for c in res["candidates"]:
        if real[c["test_id"]]["stage"] in ("neighbourhood", "already_validated"):
            assert (c["stage"], c["reason"]) == (
                real[c["test_id"]]["stage"],
                real[c["test_id"]]["reason"],
            )
        else:
            assert c["stage"] in ("deflated_sharpe", "unknown")
            assert c["tag"] in ("approx", "unknown")


def test_cli_is_read_only_and_reports(tmp_path, env, capsys):
    path = tmp_path / "ledger.sqlite"
    cfg_file = tmp_path / "validation.yaml"
    cfg_file.write_text(
        "version: 1\nmin_deflated_sharpe: 0.95\nneighborhood:\n  fraction_required: 0.0\n"
        "max_correlation: 0.7\ntop_n_to_validate: 3\nrank_by: sharpe\n"
    )
    cfg, cfg_hash = load_validation_config(cfg_file)
    with Ledger(path) as ledger:
        run_id = _seed_run(ledger, env)
        _validate(ledger, run_id, {**env, "cfg": cfg}, cfg_hash)
        _add_later_rows(ledger, run_id, env)
    before_bytes = path.read_bytes()
    before_mtime = path.stat().st_mtime_ns

    for extra in ([], ["--no-backtest"]):
        argv = ["--run", str(run_id), "--synthetic", "--timeline", "--ledger", str(path)]
        code = rv.main([*argv, "--validation-config", str(cfg_file), *extra])
        assert code == 0

    out = capsys.readouterr().out
    assert "Overall integrity: OK" in out
    assert "Timeline" in out
    assert "cluster 1" in out
    assert path.read_bytes() == before_bytes
    assert path.stat().st_mtime_ns == before_mtime


def test_data_source_mismatch_refuses_backtest(tmp_path, env, capsys):
    path = tmp_path / "ledger.sqlite"
    with Ledger(path) as ledger:
        run_id = _seed_run(ledger, env)
    code = rv.main(["--run", str(run_id), "--ledger", str(path)])  # not --synthetic
    assert code == 2
    assert "DATA SOURCE MISMATCH" in capsys.readouterr().err


def test_source_never_writes_or_unseals():
    src = (ROOT / "scripts" / "rebuild_validation.py").read_text()
    assert "unseal_holdout=True" not in src
    assert "Ledger(" not in src
    assert "record_test(" not in src
    assert "record_validation(" not in src
