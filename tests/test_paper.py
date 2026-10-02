"""Forward paper tracker (PLAN.md 3.2, amendment 2026-10-02)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qrl.checks import assert_causal
from qrl.data import synthetic_ohlcv
from qrl.ledger import Ledger, LedgerError
from qrl.paper import (
    candidate_weights,
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
