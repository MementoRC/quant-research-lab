"""Forward paper tracker (milestone 3.2, amendment 2026-10-02)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qrl.checks import assert_causal
from qrl.data import synthetic_ohlcv
from qrl.ledger import Ledger, LedgerError
from qrl.paper import (
    candidate_weights,
    check_paper_pin,
    find_kill,
    forward_returns,
    forward_weights,
    load_candidate,
    load_paper_config,
    run_paper_track,
    status_for,
    track_candidate,
)

ROOT = Path(__file__).resolve().parents[1]
TICKERS = ["AAA", "BBB", "CCC"]
PARAMS = {
    "tickers": TICKERS,
    "trend_lookback": 100,
    "short_ma": 5,
    "pullback_days": 2,
    "pullback_pct": 0.0,
    "exit_days": 3,
    "max_positions": 3,
}
START = pd.Timestamp("2019-06-03")
CFG, _ = load_paper_config(ROOT / "config" / "paper.yaml")
RULES = CFG["kill_rules"]


@pytest.fixture(scope="module")
def data() -> dict[str, pd.DataFrame]:
    return synthetic_ohlcv(TICKERS, start="2018-01-01", end="2020-12-31")


def _cfg(start: str) -> dict:
    return {**CFG, "start_date": start}


def test_nothing_before_start_date(data):
    raw = candidate_weights("trend_pullback", PARAMS, data)
    assert (raw.loc[: START - pd.Timedelta(days=1)] != 0).any().any()  # test is meaningful
    fwd = forward_weights(raw, START)
    assert (fwd.loc[fwd.index < START] == 0).all().all()
    returns = forward_returns(data, raw, START, cost_bps=5.0)
    assert len(returns) > 0
    assert returns.index.min() > START
    assert (returns.loc[returns.index <= START] == 0).all()


def test_weights_do_not_look_ahead(data):
    def build(close: pd.DataFrame) -> pd.DataFrame:
        return candidate_weights("trend_pullback", PARAMS, {**data, "close": close})

    assert_causal(build, data["close"])


def test_drawdown_kill_fires():
    idx = pd.bdate_range("2026-10-05", periods=30)
    rets = pd.Series([0.0] * 10 + [-0.02] * 20, index=idx)
    base = pd.Series(0.0, index=idx)
    reason, date = find_kill(rets, base, pd.Timestamp("2026-10-02"), 0.05, RULES)
    assert "drawdown" in reason
    assert date == idx[13]  # 1 - 0.98**4 = 7.8% > 7.5%
    assert find_kill(rets, base, pd.Timestamp("2026-10-02"), 0.5, RULES) is None


def test_underperformance_kill_only_at_the_six_month_review():
    start = pd.Timestamp("2026-10-02")
    idx = pd.bdate_range(start + pd.Timedelta(days=3), "2027-05-14")
    flat = pd.Series(0.0, index=idx)
    base = pd.Series(0.001, index=idx)
    reason, date = find_kill(flat, base, start, 0.5, RULES)
    assert "excess" in reason
    assert date == pd.Timestamp("2027-04-02")
    early = idx[idx < pd.Timestamp("2027-04-02")]
    assert find_kill(flat.loc[early], base.loc[early], start, 0.5, RULES) is None
    # Within 5 points of the baseline is not dropped.
    assert find_kill(flat, pd.Series(0.0002, index=idx), start, 0.5, RULES) is None


def test_status_rules():
    cfg = _cfg("2026-10-02")
    start = pd.Timestamp("2026-10-02")
    assert status_for(pd.Timestamp("2026-11-02"), 0.1, None, cfg)[0] == "tracking"
    assert status_for(pd.Timestamp("2027-01-04"), 0.1, None, cfg)[0] == "review due"
    assert status_for(pd.Timestamp("2027-10-04"), 0.01, None, cfg)[0] == "eligible"
    assert (
        status_for(pd.Timestamp("2027-10-04"), -0.01, None, cfg)[0]
        == "not eligible (behind baseline at 12 months)"
    )
    assert (
        status_for(pd.Timestamp("2027-10-04"), 0.0, None, cfg)[0]
        == "not eligible (behind baseline at 12 months)"
    )
    kill = ("drawdown", start)
    assert status_for(pd.Timestamp("2027-10-04"), 0.5, kill, cfg)[0].startswith("dropped")


def test_config_hash_changes_with_content(tmp_path):
    path = tmp_path / "paper.yaml"
    text = (ROOT / "config" / "paper.yaml").read_text()
    path.write_text(text)
    _, h1 = load_paper_config(path)
    assert load_paper_config(path)[1] == h1
    path.write_text(text.replace("drawdown_multiple: 1.5", "drawdown_multiple: 2.0"))
    assert load_paper_config(path)[1] != h1


def _ledger_with_test(tmp_path, family: str = "trend_pullback") -> tuple[Ledger, int, int]:
    ledger = Ledger(tmp_path / "ledger.sqlite")
    run_id = ledger.start_run("hash", "A", "paper test")
    test_id = ledger.record_test(
        run_id, "hash", family, PARAMS, "u", {"max_drawdown": 0.2, "sharpe": 1.0}, True
    )
    return ledger, run_id, test_id


def test_ledger_row_reconstructs_params(tmp_path):
    ledger, run_id, test_id = _ledger_with_test(tmp_path)
    entry = {"test_id": test_id, "run_id": run_id, "family": "trend_pullback"}
    cand = load_candidate(ledger, entry)
    assert cand["params"] == PARAMS
    assert cand["research_max_drawdown"] == pytest.approx(0.2)
    with pytest.raises(LedgerError):
        load_candidate(ledger, {**entry, "family": "low_range_close"})
    with pytest.raises(LedgerError):
        load_candidate(ledger, {**entry, "test_id": test_id + 99})


def test_end_to_end_forward_and_waiting(tmp_path, data):
    ledger, run_id, test_id = _ledger_with_test(tmp_path)
    cfg = {
        **_cfg(START.date().isoformat()),
        "candidates": [{"test_id": test_id, "run_id": run_id, "family": "trend_pullback"}],
    }
    (res,) = run_paper_track(cfg, ledger, lambda _t: data, 5.0)
    assert res["trading_days"] > 0
    assert res["start_date"] == "2019-06-03"
    assert np.isfinite(res["excess"])
    assert res["kill_drawdown_threshold"] == pytest.approx(0.3)

    last = data["close"].index[-1]
    waiting = track_candidate(
        {**cfg["candidates"][0], "params": PARAMS, "research_max_drawdown": 0.2},
        _cfg((last + pd.Timedelta(days=30)).date().isoformat()),
        data,
        5.0,
    )
    assert waiting["status"] == "waiting for first forward day"
    assert "cumulative_return" not in waiting


# --- paper.yaml pin (audit finding 9) ------------------------------------------

SHA_A = "a" * 64
SHA_B = "b" * 64


def _paper_track_module():
    spec = importlib.util.spec_from_file_location(
        "paper_track_cli", ROOT / "scripts" / "paper_track.py"
    )
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_pin_round_trip_and_second_pin_refused(tmp_path):
    with Ledger(tmp_path / "l.sqlite") as ledger:
        assert ledger.config_pin("paper.yaml") is None
        ledger.pin_config("paper.yaml", SHA_A, "abc123")
        pin = ledger.config_pin("paper.yaml")
        assert pin is not None
        assert pin["sha256"] == SHA_A
        assert pin["source"] == "abc123"
        assert pin["pinned_at"]
        with pytest.raises(LedgerError, match="already pinned"):
            ledger.pin_config("paper.yaml", SHA_B, "def456")
        assert ledger.config_pin("paper.yaml")["sha256"] == SHA_A


def test_pin_table_added_to_an_existing_ledger(tmp_path):
    path = tmp_path / "old.sqlite"
    Ledger(path).close()
    import sqlite3

    conn = sqlite3.connect(path)
    conn.execute("DROP TABLE config_pins")
    conn.commit()
    conn.close()
    with Ledger(path) as ledger:  # reopening creates the table, no data lost
        ledger.pin_config("paper.yaml", SHA_A, "abc123")
        assert ledger.config_pin("paper.yaml") is not None


def test_check_paper_pin_unpinned_and_mismatch(tmp_path):
    with Ledger(tmp_path / "l.sqlite") as ledger:
        with pytest.raises(LedgerError, match="--pin"):
            check_paper_pin(ledger, SHA_A)
        ledger.pin_config("paper.yaml", SHA_A, "abc123")
        check_paper_pin(ledger, SHA_A)
        with pytest.raises(LedgerError) as err:
            check_paper_pin(ledger, SHA_B)
        assert SHA_A in str(err.value)
        assert SHA_B in str(err.value)
        assert "PLAN.md" in str(err.value)


def _cli_args(tmp_path, cfg_path) -> list[str]:
    return [
        "--config",
        str(cfg_path),
        "--ledger",
        str(tmp_path / "l.sqlite"),
        "--out",
        str(tmp_path / "out.json"),
    ]


def test_paper_track_main_refuses_unpinned_and_mismatched_before_loading_data(
    tmp_path, monkeypatch, capsys
):
    cli = _paper_track_module()
    cfg_path = tmp_path / "paper.yaml"
    cfg_path.write_bytes((ROOT / "config" / "paper.yaml").read_bytes())

    def _boom(*_a, **_k):
        raise AssertionError("data must not be loaded")

    monkeypatch.setattr(cli, "load_ohlcv", _boom)
    monkeypatch.setattr(cli, "run_paper_track", _boom)

    assert cli.main(_cli_args(tmp_path, cfg_path)) == 2
    assert "not pinned" in capsys.readouterr().err

    with Ledger(tmp_path / "l.sqlite") as ledger:
        ledger.pin_config("paper.yaml", SHA_A, "abc123")
    assert cli.main(_cli_args(tmp_path, cfg_path)) == 2
    err = capsys.readouterr().err
    assert SHA_A in err
    assert load_paper_config(cfg_path)[1] in err
    assert not (tmp_path / "out.json").exists()


def test_paper_track_main_runs_when_pinned(tmp_path, monkeypatch):
    cli = _paper_track_module()
    cfg_path = tmp_path / "paper.yaml"
    cfg_path.write_bytes((ROOT / "config" / "paper.yaml").read_bytes())
    with Ledger(tmp_path / "l.sqlite") as ledger:
        ledger.pin_config("paper.yaml", load_paper_config(cfg_path)[1], "abc123")
    monkeypatch.setattr(cli, "run_paper_track", lambda *_a, **_k: [])
    assert cli.main(_cli_args(tmp_path, cfg_path)) == 0
    assert (tmp_path / "out.json").exists()


def test_pin_flag_records_hash_from_commit(tmp_path, monkeypatch, capsys):
    cli = _paper_track_module()
    cfg_path = tmp_path / "paper.yaml"
    cfg_path.write_bytes((ROOT / "config" / "paper.yaml").read_bytes())
    sha = load_paper_config(cfg_path)[1]
    monkeypatch.setattr(cli, "_committed_config", lambda _p: ("c0ffee", sha))
    assert cli.main([*_cli_args(tmp_path, cfg_path), "--pin"]) == 0
    with Ledger(tmp_path / "l.sqlite") as ledger:
        pin = ledger.config_pin("paper.yaml")
    assert pin is not None
    assert (pin["sha256"], pin["source"]) == (sha, "c0ffee")
    # a second --pin is refused
    assert cli.main([*_cli_args(tmp_path, cfg_path), "--pin"]) == 2
    assert "already pinned" in capsys.readouterr().err


def test_pin_flag_refuses_when_working_file_differs_from_commit(tmp_path, monkeypatch, capsys):
    cli = _paper_track_module()
    cfg_path = tmp_path / "paper.yaml"
    cfg_path.write_bytes((ROOT / "config" / "paper.yaml").read_bytes())
    monkeypatch.setattr(cli, "_committed_config", lambda _p: ("c0ffee", SHA_B))
    assert cli.main([*_cli_args(tmp_path, cfg_path), "--pin"]) == 2
    err = capsys.readouterr().err
    assert SHA_B in err
    assert load_paper_config(cfg_path)[1] in err
    with Ledger(tmp_path / "l.sqlite") as ledger:
        assert ledger.config_pin("paper.yaml") is None
