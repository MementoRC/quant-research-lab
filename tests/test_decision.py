"""Tests for the decision helper's logic (qrl.decision). Offline; synthetic
prices and CPI only. Spec: docs/methodology/decision-helper.md."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from decision_helpers import END, cpi, criteria, load, prices

from qrl import decision
from qrl.decision import (
    data_end,
    portfolio_returns,
    portfolio_tickers,
    portfolio_weights,
    real_return,
    scenario_return,
    scenario_rows,
    start_dates,
    stress_portfolios,
    stress_rows,
    window_rows,
    withdrawal_rows,
)
from qrl.decision_config import Portfolio, Scenario
from qrl.stress import Cell


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


TWO_FUND = Scenario("s", "judgement-based, v1", {"SPY": -0.25, "SHY": 0.01}, 0.08)


def test_decision_scenario_arithmetic_two_fund_hand_checked():
    r = scenario_return({"SPY": 0.6, "SHY": 0.4}, TWO_FUND)
    assert r == pytest.approx(-0.146)  # 0.6 x -25% + 0.4 x +1%
    assert real_return(r, TWO_FUND.inflation) == pytest.approx(0.854 / 1.08 - 1)  # -20.93%


def test_decision_underinvested_weights_treat_missing_weight_as_zero_return():
    r = scenario_return({"SPY": 0.5}, TWO_FUND)
    assert r == pytest.approx(-0.125)  # 0.5 x -25%; the other 50% earns 0
    assert real_return(r, TWO_FUND.inflation) == pytest.approx(0.875 / 1.08 - 1)


def test_decision_scenario_rows_both_states_and_worse(tmp_path):
    cfg = load(tmp_path)
    rows = scenario_rows(cfg.portfolios, cfg.scenarios)
    assert len(rows) == 12 * 3

    def row(pid: str, scenario: str) -> dict:
        return next(r for r in rows if r["portfolio"] == pid and r["scenario"] == scenario)

    a = row("A", "treasury_dollar_crisis")
    assert set(a["states"]) == {"risk_on", "risk_off"}
    assert a["states"]["risk_on"]["nominal_loss"] == pytest.approx(0.30)  # QQQ -30%
    assert a["states"]["risk_off"]["nominal_loss"] == pytest.approx(-0.25)  # GLD +25% (a gain)
    assert a["states"]["risk_on"]["real_loss"] == pytest.approx(1 - 0.70 / 1.08)
    assert a["states"]["risk_off"]["real_loss"] == pytest.approx(1 - 1.25 / 1.08)
    assert a["worst"] == "risk_on"
    assert a["label"] == "judgement-based, v1"
    d = row("D", "ai_megacap_crash")
    assert list(d["states"]) == ["static"]
    assert d["states"]["static"]["nominal_loss"] == pytest.approx(0.156)  # 0.6 x -30% + 0.4 x +6%
    assert d["states"]["static"]["real_loss"] == pytest.approx(1 - 0.844 / 1.02)
    assert d["worst"] == "static"
    ac = row("A-CASH", "ai_megacap_crash")
    assert set(ac["states"]) == {"risk_on", "risk_off"}
    assert ac["states"]["risk_on"]["nominal_loss"] == pytest.approx(0.21)  # 0.5 x -45% + 0.5 x +3%
    assert ac["states"]["risk_off"]["nominal_loss"] == pytest.approx(-0.04)  # 0.5 x +5% + 0.5 x +3%
    assert ac["states"]["risk_on"]["real_loss"] == pytest.approx(1 - 0.79 / 1.02)
    assert ac["worst"] == "risk_on"
    cash = row("CASH", "trade_oil_shock")
    assert cash["states"]["static"]["nominal_loss"] == pytest.approx(-0.02)
    assert cash["states"]["static"]["real_loss"] == pytest.approx(1 - 1.02 / 1.07)


def test_decision_worse_state_is_the_lower_return_when_risk_off_is_worse(tmp_path):
    cfg = load(tmp_path)
    # Hand-built: in this scenario GLD falls 10% and QQQ rises 5%, so A's risk_off is worse.
    s = Scenario("flip", "judgement-based, v1", {"QQQ": 0.05, "GLD": -0.10}, 0.0)
    a = next(p for p in cfg.portfolios if p.id == "A")
    (row,) = scenario_rows([a], [s])
    assert row["states"]["risk_on"]["nominal_loss"] == pytest.approx(-0.05)
    assert row["states"]["risk_off"]["nominal_loss"] == pytest.approx(0.10)
    assert row["worst"] == "risk_off"


def _cell(shares: dict[str, float]) -> Cell:
    return Cell("P", "w", "frozen", "l", 0.1, None, {"proxied_share": shares})


def test_decision_indicative_flag_is_strictly_above_threshold_on_summed_shares():
    flags = [
        window_rows([_cell(s)], 0.25)[0]["indicative"]
        for s in (
            {"equity": 0.25, "bonds": 0.0, "gold": 0.0},  # exactly 25%: not flagged
            {"equity": 0.2501, "bonds": 0.0, "gold": 0.0},  # just above: flagged
            {"equity": 0.15, "bonds": 0.15, "gold": 0.0},  # no class above 25%, sum 30%: flagged
        )
    ]
    assert flags == [False, True, True]


def test_decision_window_row_without_proxied_share_is_not_indicative():
    cell = Cell("P", "w", "replay", "l", 0.1, None, {})
    (row,) = window_rows([cell], 0.25)
    assert row["proxied_share"] == {}
    assert row["indicative"] is False


INCEPTION = {  # real first trading days; synthetic prices otherwise cover 1999 on
    "SHY": "2002-07-30",
    "IEF": "2002-07-30",
    "TLT": "2002-07-30",
    "RSP": "2003-05-01",
    "GLD": "2004-11-18",
}


def _inception_masked(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    out = {}
    for key, frame in data.items():
        masked = frame.copy()
        for ticker, first in INCEPTION.items():
            masked.loc[masked.index < pd.Timestamp(first), ticker] = np.nan
        out[key] = masked
    return out


def test_decision_stress_portfolios_modes(tmp_path):
    defs, modes = stress_portfolios(load(tmp_path).portfolios)
    names = [d.name for d in defs]
    assert len(defs) == 12 + 2 * 6  # A, B, C, F, AG and A-CASH switch
    assert "AG[risk_on]" in names
    assert "AG[risk_off]" in names
    assert "G-CASH[static]" not in names
    assert modes["AG"] == frozenset({"replay"})
    assert modes["AG[risk_off]"] == frozenset({"frozen"})
    assert modes["G-CASH"] == frozenset({"replay", "frozen"})


@pytest.fixture(scope="module")
def masked_rows(tmp_path_factory):
    cfg = load(tmp_path_factory.mktemp("decision"))
    return stress_rows(cfg, _inception_masked(prices()), criteria())


def test_decision_window_rows_modes(masked_rows):
    keys = {(r["portfolio"], r["window"], r["mode"]) for r in masked_rows}
    assert ("A", "gfc_2008", "replay") in keys
    assert ("A", "gfc_2008", "frozen") not in keys
    assert ("A[risk_off]", "gfc_2008", "frozen") in keys
    assert ("D", "gfc_2008", "replay") in keys
    assert ("D", "dotcom_2000", "frozen") in keys
    assert not any(k[1] == "dotcom_2000" and k[2] == "replay" for k in keys)
    assert {k[1] for k in keys} == {"dotcom_2000", "gfc_2008"}


def test_decision_dotcom_cells_report_proxied_share_and_flag(masked_rows):
    rows = {(r["portfolio"], r["window"], r["mode"]): r for r in masked_rows}
    cash = rows[("CASH", "dotcom_2000", "frozen")]
    assert cash["loss"] == pytest.approx(0.0)  # entirely cash by construction
    assert cash["proxied_share"]["bonds"] == pytest.approx(1.0)
    assert cash["indicative"] is True
    gew = rows[("G-EW", "dotcom_2000", "frozen")]
    assert gew["proxied_share"] == pytest.approx({"equity": 0.25, "gold": 0.25, "bonds": 0.5})
    assert gew["indicative"] is True
    a_on = rows[("A[risk_on]", "dotcom_2000", "frozen")]  # QQQ priced in 2000
    assert a_on["proxied_share"] == pytest.approx({"equity": 0.0, "gold": 0.0, "bonds": 0.0})
    assert a_on["indicative"] is False
    g_gfc = rows[("G", "gfc_2008", "frozen")]
    assert sum(g_gfc["proxied_share"].values()) == 0.0
    assert g_gfc["indicative"] is False
    assert rows[("A", "gfc_2008", "replay")]["loss"] is not None


def test_decision_stress_frames_cut_at_data_end(tmp_path, monkeypatch):
    seen: dict = {}
    real = decision.run_stress

    def spy(cfg, portfolios, data, max_drawdown, criteria_):
        seen["last"] = data["close"].index.max()
        seen["windows"] = [w.name for w in cfg.windows]
        seen["hypotheticals"] = cfg.hypotheticals
        return real(cfg, portfolios, data, max_drawdown, criteria_)

    monkeypatch.setattr(decision, "run_stress", spy)
    stress_rows(load(tmp_path), prices(), criteria())
    assert seen["last"] <= END
    assert seen["windows"] == ["dotcom_2000", "gfc_2008"]
    assert seen["hypotheticals"] == []


def _cut() -> dict[str, pd.DataFrame]:
    return {k: v.loc[:END].copy() for k, v in prices().items()}


def test_decision_start_dates_first_trading_day_of_january():
    idx = pd.bdate_range("2004-12-01", "2006-02-01")
    assert start_dates(idx, [2005, 2006], END) == {
        2005: pd.Timestamp("2005-01-03"),
        2006: pd.Timestamp("2006-01-02"),
    }


def test_decision_start_dates_refuse_year_without_data():
    with pytest.raises(ValueError, match="no trading day"):
        start_dates(pd.bdate_range("2004-12-01", "2005-06-01"), [2006], END)


def test_decision_portfolio_returns_start_fresh_with_costs(tmp_path):
    by_id = {p.id: p for p in load(tmp_path).portfolios}
    data = _cut()
    start = pd.Timestamp("2005-01-03")
    r = portfolio_returns(by_id["CASH"], data, start, 5.0)
    assert r.index[0] == start
    assert r.index[-1] == END
    o, c = data["open"]["SHY"], data["close"]["SHY"]
    # bought at the start-day open (cost 5 bps on turnover 1), held to the close
    assert r.iloc[0] == pytest.approx(c.loc[start] / o.loc[start] * (1 - 5.0 / 10_000) - 1)
    free = portfolio_returns(by_id["CASH"], data, start, 0.0)
    assert free.iloc[0] == pytest.approx(c.loc[start] / o.loc[start] - 1)
    assert free.iloc[0] != pytest.approx(r.iloc[0], abs=1e-6)


def test_decision_portfolio_returns_cost_hits_switching_turnover(tmp_path):
    by_id = {p.id: p for p in load(tmp_path).portfolios}
    data = _cut()
    start = pd.Timestamp("2005-01-03")
    paid = portfolio_returns(by_id["A"], data, start, 50.0)
    free = portfolio_returns(by_id["A"], data, start, 0.0)
    assert (paid <= free + 1e-15).all()
    assert (paid < free - 1e-6).sum() >= 2  # the purchase plus at least one switch
    assert (1 + paid).prod() < (1 + free).prod()


def test_decision_refuses_held_fund_unpriced_at_start(tmp_path):
    by_id = {p.id: p for p in load(tmp_path).portfolios}
    data = _cut()
    start = pd.Timestamp("2007-01-01")
    data["close"].loc[start, "RSP"] = np.nan
    with pytest.raises(ValueError, match="unpriced at the start"):
        portfolio_returns(by_id["G-EW"], data, start, 5.0)


def test_decision_refuses_nan_weights_after_start(tmp_path, monkeypatch):
    by_id = {p.id: p for p in load(tmp_path).portfolios}
    real = decision.portfolio_weights

    def holey(p, close):
        w = real(p, close).copy()
        w.loc[pd.Timestamp("2010-06-01")] = np.nan
        return w

    monkeypatch.setattr(decision, "portfolio_weights", holey)
    with pytest.raises(ValueError, match="NaN weights"):
        portfolio_returns(by_id["G"], _cut(), pd.Timestamp("2005-01-03"), 5.0)


def test_decision_withdrawal_rows_shape_on_engine_paths(tmp_path):
    cfg = load(tmp_path)
    small = replace(
        cfg,
        portfolios=[p for p in cfg.portfolios if p.id in {"A", "CASH"}],
        rates=[0.04],
        start_years=[2005, 2006, 2007],
    )
    rows = withdrawal_rows(small, prices(), cpi(), criteria())
    assert [(r["portfolio"], r["rate"]) for r in rows] == [("A", 0.04), ("CASH", 0.04)]
    for r in rows:
        assert r["first_year"] == 2005
        assert r["first"] == r["per_year"][2005]
        assert r["first"].keys() >= {
            "end_real",
            "lowest",
            "max_drawdown",
            "below_peak_months",
            "recovered",
            "below_peak_at_end",
            "depleted",
        }
        assert r["worst_end_real"] == min(m["end_real"] for m in r["per_year"].values())
        assert r["per_year"][r["worst_year"]]["end_real"] == r["worst_end_real"]


def test_decision_withdrawal_rows_worst_year_is_lowest_real_end(tmp_path, monkeypatch):
    # Flat CPI, zero returns except start-2006 (-1 bp a day): every path is
    # 1 - rate x (years held), so 2005 ends 1 - 0.04 x 14 = 0.44 and 2007 ends
    # 1 - 0.04 x 12 = 0.52; the 2006 path loses on top of its 13 years.
    cfg = load(tmp_path)
    one = replace(cfg, portfolios=cfg.portfolios[:1], rates=[0.04], start_years=[2005, 2006, 2007])
    seen_bps: list[float] = []

    def fake(p, data, start, cost_bps):
        seen_bps.append(cost_bps)
        idx = pd.bdate_range(start, END)
        return pd.Series(-0.0001 if start.year == 2006 else 0.0, index=idx)

    monkeypatch.setattr(decision, "portfolio_returns", fake)
    flat = cpi(monthly_growth=0.0)
    (row,) = withdrawal_rows(one, prices(), flat, criteria())
    per = row["per_year"]
    assert per[2005]["end_real"] == pytest.approx(0.44)
    assert per[2007]["end_real"] == pytest.approx(0.52)
    assert per[2006]["end_real"] < 0.44
    assert row["worst_year"] == 2006
    assert row["worst_end_real"] == per[2006]["end_real"]
    assert row["first_year"] == 2005
    assert row["first"]["end_real"] == pytest.approx(0.44)
    assert row["first"]["lowest"] == pytest.approx(0.44)
    assert row["first"]["below_peak_at_end"] is True  # zero return, only withdrawals
    assert row["first"]["depleted"] is None
    assert seen_bps == [criteria()["costs"]["bps_per_unit_turnover"]] * 3


def test_decision_withdrawal_rows_refuse_missing_cpi(tmp_path):
    cfg = load(tmp_path)
    small = replace(cfg, portfolios=cfg.portfolios[:1], rates=[0.04], start_years=[2005])
    with pytest.raises(ValueError, match="missing CPI"):
        withdrawal_rows(small, prices(), cpi().loc[:"2010-12-31"], criteria())
