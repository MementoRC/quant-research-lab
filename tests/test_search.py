"""Tests for the milestone 2.4 search loop: qrl.search (library) and
scripts/search.py (CLI), offline and on synthetic data only.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest
import yaml

from qrl.ledger import Ledger, candidate_key
from qrl.search import SearchData, evaluate_candidate, propose_batch, pruned_regions

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SEARCH_SRC = (ROOT / "src" / "qrl" / "search.py").read_text()
CLI_SRC = (SCRIPTS / "search.py").read_text()
sys.path.insert(0, str(SCRIPTS))

from search import main as search_main  # noqa: E402

TINY_TICKERS = ["AAA", "BBB", "CCC", "DDD"]


def _write_tiny_universe(path: Path, tickers: list[str] = TINY_TICKERS) -> Path:
    path.write_text(
        yaml.safe_dump(
            {
                "name": "tiny_test_universe",
                "as_of": "2026-09",
                "source": "test fixture",
                "survivorship_biased": False,
                "tickers": tickers,
            }
        )
    )
    return path


def _seed_and_batch(
    tmp_path: Path, n: int, *, max_seconds: float | None = None, families: str | None = None
) -> tuple[Path, int]:
    ledger_path = tmp_path / "ledger.sqlite"
    universe_path = _write_tiny_universe(tmp_path / "universe.yaml")
    seed_argv = ["--ledger", str(ledger_path), "seed", "--lane", "A", "--synthetic"]
    assert search_main(seed_argv) == 0

    with Ledger(ledger_path) as ledger:
        run_id = ledger.list_runs()[-1]["run_id"]

    batch_argv = [
        "--ledger",
        str(ledger_path),
        "batch",
        "--run",
        str(run_id),
        "--n",
        str(n),
        "--synthetic",
        "--universe",
        str(universe_path),
        "--seed",
        "3",
    ]
    if max_seconds is not None:
        batch_argv += ["--max-seconds", str(max_seconds)]
    if families is not None:
        batch_argv += ["--families", families]
    assert search_main(batch_argv) == 0
    return ledger_path, run_id


# ---------------------------------------------------------------------------
# End-to-end: every test recorded, including failures.
# ---------------------------------------------------------------------------


def test_end_to_end_batch_records_every_test_including_failures(tmp_path):
    ledger_path, run_id = _seed_and_batch(tmp_path, n=10)

    with Ledger(ledger_path) as ledger:
        history = ledger.list_tests(run_id)
        summary = ledger.summary(run_id)

    assert len(history) == 10
    assert summary["tested"] == 10
    # A short synthetic window against real pass criteria (min Sharpe, beats
    # QQQ, drawdown, trade count) should produce at least one failure -- the
    # acceptance criterion is that failures are recorded at all, not hidden.
    assert any(not row["passed"] for row in history)


def test_summary_and_note_cli_round_trip(tmp_path, capsys):
    ledger_path, run_id = _seed_and_batch(tmp_path, n=6)

    note_argv = [
        "--ledger",
        str(ledger_path),
        "note",
        "--run",
        str(run_id),
        "--batch",
        "1",
        "--text",
        "tried the sleeve families",
    ]
    assert search_main(note_argv) == 0

    capsys.readouterr()
    summary_argv = ["--ledger", str(ledger_path), "summary", "--run", str(run_id)]
    assert search_main(summary_argv) == 0
    out = capsys.readouterr().out
    assert f"Run {run_id}" in out
    assert "tried the sleeve families" in out


# ---------------------------------------------------------------------------
# A raising candidate is recorded as a failure, and the batch continues.
# ---------------------------------------------------------------------------


def test_evaluate_candidate_never_raises_on_unknown_family(tmp_path):
    data = SearchData.load(TINY_TICKERS, synthetic=True)
    from qrl.criteria import load_criteria

    criteria, _ = load_criteria(ROOT / "config" / "criteria.yaml")

    outcome = evaluate_candidate("not_a_real_family", {"tickers": TINY_TICKERS}, data, criteria)

    assert outcome["passed"] is False
    assert outcome["failure_reasons"].startswith("error:")
    assert outcome["metrics"] == {"error": outcome["metrics"]["error"]}


def test_batch_continues_after_a_candidate_raises(tmp_path, monkeypatch):
    import qrl.search as search_mod
    from qrl.criteria import load_criteria

    criteria, criteria_hash = load_criteria(ROOT / "config" / "criteria.yaml")
    data = SearchData.load([*TINY_TICKERS, "QQQ"], synthetic=True)
    bench = search_mod.compute_benchmark_metrics(data, criteria)

    def _boom(*_args, **_kwargs):
        raise RuntimeError("deliberately broken candidate")

    real_spec_for = search_mod._spec_for

    def _patched_spec_for(family):
        if family == "boom_family":

            class _Broken:
                fields = ("close",)

                @staticmethod
                def tickers(_params):
                    return TINY_TICKERS

                weights = staticmethod(_boom)

            return _Broken()
        return real_spec_for(family)

    monkeypatch.setattr(search_mod, "_spec_for", _patched_spec_for)

    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        run_id = ledger.start_run(criteria_hash, "A", "boom test")
        families_and_params = [
            ("core_trend", {"lookback": 50, "risk_off": "GLD"}),
            ("boom_family", {"tickers": TINY_TICKERS}),
            ("core_trend", {"lookback": 100, "risk_off": "TLT"}),
        ]
        for family, params in families_and_params:
            outcome = search_mod.evaluate_candidate(family, params, data, criteria, bench)
            ledger.record_test(
                run_id,
                criteria_hash,
                family,
                params,
                "tiny",
                outcome["metrics"],
                outcome["passed"],
                outcome["failure_reasons"],
            )
        history = ledger.list_tests(run_id)

    assert len(history) == 3
    boom_row = next(r for r in history if r["family"] == "boom_family")
    assert boom_row["passed"] is False
    assert "deliberately broken candidate" in boom_row["failure_reasons"]
    # The two good candidates on either side of the broken one were still recorded.
    assert sum(1 for r in history if r["family"] == "core_trend") == 2


# ---------------------------------------------------------------------------
# propose_batch: determinism, skip, mutate, prune.
# ---------------------------------------------------------------------------


def test_propose_batch_is_deterministic_for_a_fixed_seed():
    spaces = {"trend_pullback": {"trend_lookback": [100, 150, 200], "short_ma": [5, 10, 15]}}
    a = propose_batch([], spaces, n=6, seed=42, universe="u", sleeve_tickers=TINY_TICKERS)
    b = propose_batch([], spaces, n=6, seed=42, universe="u", sleeve_tickers=TINY_TICKERS)
    assert a == b


def test_propose_batch_never_repeats_a_tested_candidate_key():
    space = {"a": [1, 2], "b": [1, 2]}
    spaces = {"fam": space}
    all_combos = [{"a": a, "b": b} for a in space["a"] for b in space["b"]]
    tested = all_combos[:3]
    history = [
        {
            "family": "fam",
            "params": params,
            "passed": False,
            "failure_reasons": "min_sharpe,max_drawdown",
            "candidate_key": candidate_key("fam", params, "u", "research"),
        }
        for params in tested
    ]

    proposed = propose_batch(history, spaces, n=5, seed=1, universe="u")

    assert len(proposed) == 1
    family, params = proposed[0]
    assert family == "fam"
    assert params == all_combos[3]


def test_propose_batch_mutates_a_passing_candidate():
    space = {"trend_lookback": [100, 150, 200, 250], "short_ma": [5, 10, 15, 20]}
    spaces = {"trend_pullback": space}
    base_params = {"trend_lookback": 150, "short_ma": 10, "tickers": TINY_TICKERS}
    history = [
        {
            "family": "trend_pullback",
            "params": base_params,
            "passed": True,
            "failure_reasons": None,
            "candidate_key": candidate_key("trend_pullback", base_params, "u", "research"),
        }
    ]

    proposed = propose_batch(
        history, spaces, n=25, seed=7, universe="u", sleeve_tickers=TINY_TICKERS
    )

    def _is_one_step_neighbor(params: dict) -> bool:
        diffs = [k for k in space if params[k] != base_params[k]]
        if len(diffs) != 1:
            return False
        key = diffs[0]
        values = space[key]
        return abs(values.index(params[key]) - values.index(base_params[key])) == 1

    assert any(_is_one_step_neighbor(params) for _, params in proposed)


def test_propose_batch_prunes_an_all_failure_parameter_value():
    space = {"x": [1, 9]}
    spaces = {"fam": space}
    history = [
        {
            "family": "fam",
            "params": {"x": 1},
            "passed": False,
            "failure_reasons": "min_sharpe,max_drawdown",
            "candidate_key": f"tested-{i}",
        }
        for i in range(6)
    ]

    pruned = pruned_regions(history, spaces, min_attempts=5)
    assert ("fam", "x", 1) in pruned

    proposed = propose_batch(history, spaces, n=3, seed=5, universe="u")
    assert proposed  # the space is not fully exhausted -- x=9 remains
    assert all(params["x"] == 9 for _, params in proposed)


def test_propose_batch_empty_spaces_returns_empty_list():
    assert propose_batch([], {}, n=5, seed=0, universe="u") == []


# ---------------------------------------------------------------------------
# Research period only, and no unsealed holdout anywhere in the new code.
# ---------------------------------------------------------------------------


def test_all_recorded_tests_use_the_research_period(tmp_path):
    ledger_path, run_id = _seed_and_batch(tmp_path, n=5)
    conn = sqlite3.connect(str(ledger_path))
    try:
        periods = {row[0] for row in conn.execute("SELECT DISTINCT period FROM tests")}
    finally:
        conn.close()
    assert periods == {"research"}


def test_no_unsealed_holdout_call_in_search_source():
    assert "unseal_holdout=True" not in SEARCH_SRC
    assert "unseal_holdout=True" not in CLI_SRC


# ---------------------------------------------------------------------------
# Budgets: --n and --max-seconds both stop a batch.
# ---------------------------------------------------------------------------


def test_n_budget_stops_the_batch(tmp_path):
    ledger_path, run_id = _seed_and_batch(tmp_path, n=4)
    with Ledger(ledger_path) as ledger:
        assert len(ledger.list_tests(run_id)) == 4


def test_max_seconds_budget_stops_the_batch_early(tmp_path):
    ledger_path, run_id = _seed_and_batch(tmp_path, n=1000, max_seconds=0.0)
    with Ledger(ledger_path) as ledger:
        tested = len(ledger.list_tests(run_id))
    assert tested < 1000


# ---------------------------------------------------------------------------
# Lane B/C plumbing (offline, synthetic).
# ---------------------------------------------------------------------------


def test_seed_lane_b_requires_families(tmp_path, capsys):
    ledger_path = tmp_path / "ledger.sqlite"
    exit_code = search_main(["--ledger", str(ledger_path), "seed", "--lane", "B", "--synthetic"])
    assert exit_code == 2


def test_seed_lane_c_requires_confirmation(tmp_path):
    ledger_path = tmp_path / "ledger.sqlite"
    exit_code = search_main(["--ledger", str(ledger_path), "seed", "--lane", "C", "--synthetic"])
    assert exit_code == 2
    with Ledger(ledger_path) as ledger:
        assert ledger.list_runs() == []


def test_seed_lane_c_with_confirmation_starts_a_run(tmp_path):
    ledger_path = tmp_path / "ledger.sqlite"
    exit_code = search_main(
        ["--ledger", str(ledger_path), "seed", "--lane", "C", "--confirm-lane-c", "--synthetic"]
    )
    assert exit_code == 0
    with Ledger(ledger_path) as ledger:
        assert len(ledger.list_runs()) == 1


@pytest.mark.parametrize("bad_family", ["not_a_family"])
def test_seed_lane_b_rejects_unknown_family(tmp_path, bad_family):
    ledger_path = tmp_path / "ledger.sqlite"
    exit_code = search_main(
        [
            "--ledger",
            str(ledger_path),
            "seed",
            "--lane",
            "B",
            "--families",
            bad_family,
            "--synthetic",
        ]
    )
    assert exit_code == 2
