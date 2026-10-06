"""Tests for the decision helper's logic (qrl.decision). Offline; synthetic
prices and CPI only. Spec: docs/methodology/decision-helper.md."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from decision_helpers import END, criteria, load, prices

from qrl.decision import data_end, portfolio_tickers, portfolio_weights
from qrl.decision_config import Portfolio


def test_decision_data_end_is_research_end():
    assert data_end(criteria()) == END


def test_decision_portfolio_tickers_include_signals(tmp_path):
    by_id = {p.id: p for p in load(tmp_path).portfolios}
    assert portfolio_tickers(by_id["F"]) == ["SPY", "IEF", "GLD"]
    assert portfolio_tickers(by_id["A-CASH"]) == ["QQQ", "GLD", "SHY"]
    assert portfolio_tickers(by_id["G-EW"]) == ["RSP", "TLT", "GLD", "SHY"]


def test_decision_blend_weights_are_weighted_sum_of_components(tmp_path):
    by_id = {p.id: p for p in load(tmp_path).portfolios}
    close = prices()["close"].loc[:END]
    a = portfolio_weights(by_id["A"], close)
    g = portfolio_weights(by_id["G"], close)
    ag = portfolio_weights(by_id["AG"], close)
    cols = sorted(set(a.columns) | set(g.columns))
    expected = 0.5 * a.reindex(columns=cols, fill_value=0.0) + 0.5 * g.reindex(
        columns=cols, fill_value=0.0
    )
    valid = expected.notna().all(axis=1)
    pd.testing.assert_frame_equal(ag[valid], expected[valid])
    assert ag[~valid].isna().all(axis=None)
    assert set(ag.loc[valid, "QQQ"].unique()) == {0.0, 0.5}  # A keeps switching inside the blend


def test_decision_unequal_blend_has_absolute_weights(tmp_path):
    by_id = {p.id: p for p in load(tmp_path).portfolios}
    cash, gew = by_id["CASH"].parts[0][0], by_id["G-EW"].parts[0][0]
    blend = Portfolio("X", "x", ((cash, 0.25), (gew, 0.75)))
    w = portfolio_weights(blend, prices()["close"].loc[:END])
    valid = w.dropna()
    assert len(valid) > 0
    expected = {"SHY": 0.4375, "RSP": 0.1875, "TLT": 0.1875, "GLD": 0.1875}
    assert set(w.columns) == set(expected)
    for ticker, value in expected.items():
        assert valid[ticker].to_numpy() == pytest.approx(value, abs=1e-12)


def test_decision_static_portfolios_have_absolute_weights(tmp_path):
    by_id = {p.id: p for p in load(tmp_path).portfolios}
    close = prices()["close"].loc[:END]
    cash = portfolio_weights(by_id["CASH"], close).dropna()
    assert len(cash) > 0
    assert list(cash.columns) == ["SHY"]
    assert (cash["SHY"] == 1.0).all()
    gew = portfolio_weights(by_id["G-EW"], close).dropna()
    assert len(gew) > 0
    assert set(gew.columns) == {"RSP", "TLT", "GLD", "SHY"}
    assert (gew == 0.25).all(axis=None)


def test_decision_every_portfolio_is_fully_invested_on_valid_rows(tmp_path):
    cfg = load(tmp_path)
    close = prices()["close"].loc[:END]
    for p in cfg.portfolios:
        valid = portfolio_weights(p, close).dropna()
        assert len(valid) > 0, p.id
        assert valid.sum(axis=1).to_numpy() == pytest.approx(1.0, abs=1e-12), p.id


def test_decision_a_holds_qqq_or_gld_at_full_weight(tmp_path):
    by_id = {p.id: p for p in load(tmp_path).portfolios}
    valid = portfolio_weights(by_id["A"], prices()["close"].loc[:END]).dropna()
    risk_on = (valid["QQQ"] == 1.0) & (valid["GLD"] == 0.0)
    risk_off = (valid["QQQ"] == 0.0) & (valid["GLD"] == 1.0)
    assert (risk_on | risk_off).all()
    assert risk_on.any()
    assert risk_off.any()


def test_decision_nan_part_makes_the_whole_row_nan(tmp_path):
    by_id = {p.id: p for p in load(tmp_path).portfolios}
    close = prices()["close"].loc[:END].copy()
    day = close.index[close.index.get_indexer([pd.Timestamp("2010-06-01")], method="bfill")[0]]
    close.loc[day, "SHY"] = np.nan
    w = portfolio_weights(by_id["A-CASH"], close)
    assert w.loc[day].isna().all()  # never zero-filled into cash
    assert w.drop(index=day).loc["2006":].notna().all(axis=None)
