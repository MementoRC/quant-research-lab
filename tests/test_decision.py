"""Tests for the decision helper's logic (qrl.decision). Offline; synthetic
prices and CPI only. Spec: docs/methodology/decision-helper.md."""

from __future__ import annotations

import numpy as np
import pandas as pd
from decision_helpers import END, criteria, load, prices

from qrl.decision import data_end, portfolio_tickers, portfolio_weights


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


def test_decision_nan_part_makes_the_whole_row_nan(tmp_path):
    by_id = {p.id: p for p in load(tmp_path).portfolios}
    close = prices()["close"].loc[:END].copy()
    day = close.index[close.index.get_indexer([pd.Timestamp("2010-06-01")], method="bfill")[0]]
    close.loc[day, "SHY"] = np.nan
    w = portfolio_weights(by_id["A-CASH"], close)
    assert w.loc[day].isna().all()  # never zero-filled into cash
    assert w.drop(index=day).loc["2006":].notna().all(axis=None)
