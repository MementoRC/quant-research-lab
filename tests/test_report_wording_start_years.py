"""Start-year horizon and the equal-horizon worst case (spec:
docs/methodology/report-wording.md, section 6). Offline; synthetic data."""

from __future__ import annotations

from dataclasses import replace

import pandas as pd
import pytest
from decision_helpers import cpi, criteria, load, prices
from test_decision_report import _hand_report

from qrl import decision
from qrl.decision import withdrawal_rows
from qrl.decision_report import render_markdown

YEARS = [2005, 2006, 2007]


def _fake_returns(p, data, start, cost_bps):
    """Zero returns, except: the 2005 path loses 3 bp a day in 2005-2006 (its
    first-years loss); the 2006 path loses 40 bp a day in 2018 (a late loss
    that only its full length sees)."""
    idx = pd.bdate_range(start, data["close"].index[-1])
    rets = pd.Series(0.0, index=idx)
    if start.year == 2005:
        rets[(idx.year >= 2005) & (idx.year <= 2006)] = -0.0003
    if start.year == 2006:
        rets[idx.year == 2018] = -0.004
    return rets


def _rows(tmp_path, monkeypatch, end=None):
    cfg = load(tmp_path)
    one = replace(cfg, portfolios=cfg.portfolios[:1], rates=[0.04], start_years=YEARS)
    monkeypatch.setattr(decision, "portfolio_returns", _fake_returns)
    if end is not None:
        monkeypatch.setattr(decision, "data_end", lambda crit: pd.Timestamp(end))
    (row,) = withdrawal_rows(one, prices(), cpi(monthly_growth=0.0), criteria())
    return row


def test_worst5_picks_longest_path_and_cuts_every_path_to_one_length(tmp_path, monkeypatch):
    spans: list[int] = []
    real = decision.withdrawal_path

    def spy(returns, monthly):
        spans.append(returns.index[-1].year - returns.index[0].year + 1)
        return real(returns, monthly)

    monkeypatch.setattr(decision, "withdrawal_path", spy)
    row = _rows(tmp_path, monkeypatch)
    assert row["horizon_years"] == 12  # 2018 - 2007 + 1
    assert row["worst_year"] == 2006  # lowest full-length value
    assert row["worst5_year"] == 2005  # lowest value over the first 12 years
    assert row["worst5_end_real"] < 0.52
    # three full paths (14, 13, 12 calendar years) and three cut paths, all 12 years
    assert sorted(spans) == [12, 12, 12, 12, 13, 14]


def test_worst5_horizon_follows_the_data_end(tmp_path, monkeypatch):
    row = _rows(tmp_path, monkeypatch, end="2019-12-31")
    assert row["horizon_years"] == 13  # 2019 - 2007 + 1


def test_each_start_year_horizon_is_end_year_minus_start_year_plus_one(tmp_path, monkeypatch):
    row = _rows(tmp_path, monkeypatch)
    assert row["horizons"] == {2005: 14, 2006: 13, 2007: 12}


def _withdrawal_lines(**over) -> str:
    row = {
        "portfolio": "X",
        "rate": 0.04,
        "first_year": 2005,
        "first": {
            "end_nominal": 1.2,
            "end_real": 0.9,
            "lowest": 0.5,
            "max_drawdown": 0.146,
            "below_peak_months": 7,
            "recovered": True,
            "below_peak_at_end": False,
            "depleted": None,
        },
        "worst_year": 2006,
        "worst_end_real": 0.8,
        "per_year": {},
        "horizons": {2005: 14, 2006: 13},
        "horizon_years": 6,
        "worst5_year": 2005,
        "worst5_end_real": 0.7,
    }
    rep = _hand_report(withdrawals=[row | over])
    return render_markdown(rep)


def test_report_header_names_end_date_and_old_cell_shows_its_horizon():
    md = _withdrawal_lines()
    assert "worst start year to 2018-12-31 (real ending value; horizons differ)" in md
    assert "2006, 13 y (80.0%)" in md


def test_report_new_column_header_uses_the_horizon():
    md = _withdrawal_lines()
    assert "worst 6-year start (real value after 6 years)" in md
    assert "2005 (70.0%)" in md


@pytest.mark.parametrize("h", [5, 7])
def test_report_new_column_header_tracks_h(h):
    md = _withdrawal_lines(horizon_years=h)
    assert f"worst {h}-year start (real value after {h} years)" in md
