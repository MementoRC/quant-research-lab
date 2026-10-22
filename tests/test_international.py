"""Tests for qrl.international (docs/methodology/international-test.md).
Synthetic data only; nothing here downloads."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qrl.international import (
    NotCovered,
    Rule,
    derive_equity_leg,
    holds_gold,
    load_international_config,
    translate,
)
from qrl.strategies import REGISTRY

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "international.yaml"


def _cfg():
    return load_international_config(CONFIG)[0]


def _variant(tmp_path: Path, old: str, new: str) -> Path:
    text = CONFIG.read_text(encoding="utf-8")
    assert old in text
    path = tmp_path / "international.yaml"
    path.write_text(text.replace(old, new), encoding="utf-8")
    return path


def test_config_loads_as_pre_registered():
    cfg, sha = load_international_config(CONFIG)
    assert len(sha) == 64
    assert cfg.set_names == ["main", "reserve_1", "reserve_2"]
    assert cfg.market_set("main").markets == ("EWJ", "EWU", "EWG", "EWC", "EWA", "EWL", "EWQ")
    assert [s.min_pass for s in cfg.sets] == [5, 4, 3]
    assert cfg.windows == (
        (pd.Timestamp("1997-01-01"), pd.Timestamp("2004-12-31")),
        (pd.Timestamp("2023-01-01"), None),
    )
    assert cfg.min_scored_days == 500
    assert cfg.treasury == {"SHY": ("DGS2", 1.9), "IEF": ("DGS10", 7.5), "TLT": ("DGS20", 17.0)}
    assert cfg.funds == ["GLD", "IEF", "SHY", "TLT"]
    assert cfg.covered == frozenset({"core_trend", "core_mix"})
    assert cfg.cash_fred == "DTB3"
    assert cfg.fred_ids == ["DGS10", "DGS2", "DGS20", "DTB3"]
    assert cfg.gold_ticker == "GC=F"
    assert not hasattr(cfg, "equity_leg")
    assert not hasattr(cfg, "gold_lag_days")


def test_unknown_set_is_refused():
    with pytest.raises(ValueError, match="unknown market set"):
        _cfg().market_set("nicer_one")


def test_window_overlapping_excluded_years_is_refused(tmp_path):
    path = _variant(tmp_path, 'end: "2004-12-31"', 'end: "2005-06-30"')
    with pytest.raises(ValueError, match="excluded"):
        load_international_config(path)


def test_market_repeated_across_sets_is_refused(tmp_path):
    path = _variant(tmp_path, "markets: [EWN,", "markets: [EWJ,")
    with pytest.raises(ValueError, match="repeats"):
        load_international_config(path)


def test_min_pass_above_set_size_is_refused(tmp_path):
    path = _variant(tmp_path, "min_pass: 3", "min_pass: 5")
    with pytest.raises(ValueError, match="min_pass"):
        load_international_config(path)


TREND = Rule("core_trend", {"risk_on": "SPY", "risk_off": "IEF", "lookback": 200})


def test_covered_strategies_are_registry_names():
    assert _cfg().covered <= set(REGISTRY)


def test_the_equity_leg_is_derived_from_the_params():
    cfg = _cfg()
    assert derive_equity_leg(TREND, cfg) == "SPY"
    assert (
        derive_equity_leg(
            Rule("core_trend", {"risk_on": "QQQ", "risk_off": "CASH", "lookback": 150}), cfg
        )
        == "QQQ"
    )
    # an equity ticker only in risk_off, and a signal naming the same ticker
    assert (
        derive_equity_leg(Rule("core_trend", {"risk_on": "GLD", "risk_off": "QQQ"}), cfg) == "QQQ"
    )
    mix = Rule(
        "core_mix",
        {"risk_on": {"SPY": 0.6, "IEF": 0.4}, "risk_off": {"GLD": 0.5}, "signal": "SPY"},
    )
    assert derive_equity_leg(mix, cfg) == "SPY"


@pytest.mark.parametrize(
    "rule",
    [
        Rule("core_mix", {"risk_on": {"SPY": 0.5, "QQQ": 0.5}}),  # two equity legs
        Rule("core_mix", {"risk_on": {"SPY": 1.0}, "signal": "QQQ"}),  # two via signal
        Rule("core_trend", {"risk_on": "GLD", "risk_off": "IEF"}),  # zero: all defensive
        Rule("core_trend", {"risk_off": "IEF", "lookback": 200}),  # zero: leg left to a default
        Rule("buy_and_hold", {"ticker": "SPY"}),  # strategy not covered
    ],
)
def test_uncovered_rules_are_refused(rule):
    with pytest.raises(NotCovered):
        derive_equity_leg(rule, _cfg())


def test_translate_swaps_only_the_equity_ticker():
    rule = Rule(
        "core_mix",
        {
            "risk_on": {"SPY": 0.6, "IEF": 0.4},
            "risk_off": {"IEF": 0.5, "GLD": 0.5},
            "signal": "SPY",
            "lookback": 200,
        },
    )
    out = translate(rule, "SPY", "EWJ")
    assert out.params == {
        "risk_on": {"EWJ": 0.6, "IEF": 0.4},
        "risk_off": {"IEF": 0.5, "GLD": 0.5},
        "signal": "EWJ",
        "lookback": 200,
    }
    assert rule.params["signal"] == "SPY"  # the accepted rule is untouched


def test_translate_refuses_an_equity_leg_left_to_a_default():
    with pytest.raises(NotCovered, match="default"):
        translate(Rule("core_trend", {"risk_off": "GLD", "lookback": 200}), "QQQ", "EWJ")


def test_rule_sha_ignores_key_order():
    a = Rule("core_trend", {"risk_on": "SPY", "lookback": 200})
    b = Rule("core_trend", {"lookback": 200, "risk_on": "SPY"})
    assert a.sha256 == b.sha256
    assert len(a.sha256) == 64


def test_holds_gold():
    assert holds_gold(Rule("core_trend", {"risk_on": "SPY", "risk_off": "GLD"}), _cfg())
    assert not holds_gold(TREND, _cfg())


FUND_STARTS = {"SHY": "2002-07-30", "IEF": "2002-07-30", "TLT": "2002-07-30", "GLD": "2004-11-18"}

from qrl.data import synthetic_prices  # noqa: E402
from qrl.international import (  # noqa: E402
    build_panel,
    gold_correlation,
    lagged_close,
    splice,
    yield_proxy_close,
)


def synthetic_raw(markets, funds, treasury_ids, end=None):
    """Synthetic stand-in for the downloads: markets and funds from 1996, each
    fund NaN before its real first date, GC=F from 2000-08-30, flat 4% yields
    (`treasury_ids` is `cfg.fred_ids`: the Treasury ids plus DTB3 for cash)."""
    open_, close = synthetic_prices([*markets, *funds], start="1996-01-01", end=end)
    for fund, first in FUND_STARTS.items():
        if fund in close.columns:
            early = close.index < pd.Timestamp(first)
            open_.loc[early, fund] = np.nan
            close.loc[early, fund] = np.nan
    _, gold = synthetic_prices(["GC=F"], start="2000-08-30", end=end)
    yields = {fred: pd.Series(4.0, index=close.index) for fred in treasury_ids}
    return open_, close, gold["GC=F"], yields


def test_yield_proxy_follows_the_formula_and_the_lag():
    idx = pd.bdate_range("2000-01-03", periods=7)
    y = pd.Series([5.0, 5.0, 6.0, 6.0, 6.0, 6.0, 6.0], index=idx)
    unlagged = yield_proxy_close(y, 2.0, 0, idx).pct_change(fill_method=None)
    lagged = yield_proxy_close(y, 2.0, 1, idx).pct_change(fill_method=None)
    # previous yield / 252 - duration x yield change: the jump moves the price
    # the day it is observed unlagged, one business day later lagged
    assert unlagged.iloc[2] == pytest.approx(0.05 / 252 - 2.0 * 0.01)
    assert lagged.iloc[3] == pytest.approx(0.05 / 252 - 2.0 * 0.01)
    assert lagged.iloc[4] == pytest.approx(0.06 / 252)


def test_lagged_close_shifts_by_business_days():
    idx = pd.bdate_range("2000-01-03", periods=4)
    s = pd.Series([1.0, 2.0, 3.0, 4.0], index=idx)
    out = lagged_close(s, 1, idx)
    assert np.isnan(out.iloc[0])
    assert out.iloc[1] == 1.0
    assert out.iloc[3] == 3.0


def test_splice_has_no_jump_and_keeps_the_fund():
    idx = pd.bdate_range("2002-07-01", periods=10)
    proxy = pd.Series(np.linspace(100.0, 109.0, 10), index=idx)
    fund = pd.Series([np.nan] * 5 + [50.0, 51.0, 52.0, 53.0, 54.0], index=idx)
    out = splice(proxy, fund).reindex(idx)
    assert (out.iloc[5:] == fund.iloc[5:]).all()
    assert out.iloc[:5].notna().all()
    assert out.iloc[4] / out.iloc[5] == pytest.approx(proxy.iloc[4] / proxy.iloc[5])


def test_gold_correlation():
    idx = pd.bdate_range("2004-11-18", "2006-12-29")
    s = pd.Series(np.cumprod(1 + np.random.default_rng(0).normal(0, 0.01, len(idx))), index=idx)
    assert gold_correlation(s, s, idx[0], idx[-1]) == pytest.approx(1.0)
    assert gold_correlation(s, s, idx[0], idx[5]) is None  # too few days


def test_build_panel_splices_before_fund_starts_and_keeps_real_data_after():
    cfg = _cfg()
    open_, close, gold, yields = synthetic_raw(["EWJ"], cfg.funds, cfg.fred_ids, end="2006-12-29")
    p_open, p_close = build_panel(open_, close, yields, gold, cfg)
    assert p_close.loc["1997-01-02":, ["IEF", "TLT", "SHY"]].notna().all().all()
    gld_first = p_close["GLD"].first_valid_index()
    # GC=F is unlagged, so the proxy exists from its own first day
    assert pd.Timestamp("2000-08-30") <= gld_first < pd.Timestamp("2000-09-15")
    after = close.index >= pd.Timestamp("2004-11-18")
    assert p_close.loc[after, "GLD"].equals(close.loc[after, "GLD"])
    assert p_open.loc[after, "GLD"].equals(open_.loc[after, "GLD"])
    march = slice("2001-03-01", "2001-03-30")  # a proxy day's open is the previous close
    assert p_open.loc[march, "IEF"].equals(p_close["IEF"].shift(1).loc[march])
    assert "GC=F" in p_close.columns  # raw, kept for the gold check


def test_gc_f_is_spliced_unlagged():
    cfg = _cfg()
    open_, close, gold, yields = synthetic_raw(["EWJ"], cfg.funds, cfg.fred_ids, end="2006-12-29")
    _, p_close = build_panel(open_, close, yields, gold, cfg)
    before = (p_close.index >= gold.index[0]) & (p_close.index < pd.Timestamp("2004-11-18"))
    # the spliced proxy moves with GC=F on the same day: the ratio is one constant
    ratio = (p_close.loc[before, "GLD"] / gold.reindex(p_close.index)[before]).dropna()
    assert len(ratio) > 1000
    assert np.allclose(ratio, ratio.iloc[0])
    assert p_close.loc[before, "GC=F"].equals(gold.reindex(p_close.index)[before])


def test_cash_close_returns_equal_the_lagged_dtb3_over_252():
    cfg = _cfg()
    idx = pd.bdate_range("2000-01-03", periods=8)
    dtb3 = pd.Series([4.0, 4.0, 5.0, 5.0, 6.0, 6.0, 6.0, 6.0], index=idx)
    out = yield_proxy_close(dtb3, 0.0, cfg.yield_lag_days, idx).pct_change(fill_method=None)
    lagged = dtb3.shift(cfg.yield_lag_days) / 100.0  # known one business day late
    # return on day t = previous day's lagged yield / 252, decimals
    assert out.iloc[3:].to_numpy() == pytest.approx((lagged.shift(1) / 252).iloc[3:].to_numpy())
    open_, close, gold, yields = synthetic_raw(["EWJ"], cfg.funds, cfg.fred_ids, end="2006-12-29")
    p_open, p_close = build_panel(open_, close, yields, gold, cfg)
    assert "CASH" in p_close.columns
    assert p_close["CASH"].loc["1997-01-02":].notna().all()
    # flat 4% yields: a constant daily return of 0.04 / 252
    daily = p_close["CASH"].pct_change().dropna().iloc[5:].to_numpy()
    assert daily == pytest.approx(0.04 / 252)
    assert (
        p_open["CASH"]
        .loc["2001-03-01":"2001-03-30"]
        .equals(p_close["CASH"].shift(1).loc["2001-03-01":"2001-03-30"])
    )


from qrl.international import (  # noqa: E402
    evaluate_market,
    market_checks,
    scoring_index,
    with_cash,
)

DATA_END = pd.Timestamp("2026-10-19")


def _panel(markets, cfg):
    open_, close, gold, yields = synthetic_raw(markets, cfg.funds, cfg.fred_ids)
    return build_panel(open_, close, yields, gold, cfg)


def test_uninvested_weight_goes_to_the_cash_column():
    idx = pd.bdate_range("2020-01-01", periods=4)
    weights = pd.DataFrame(
        {"EWJ": [0.6, 0.0, np.nan, 1.0], "IEF": [0.3, 0.0, np.nan, 0.0]}, index=idx
    )
    out = with_cash(weights)
    assert out["CASH"].iloc[0] == pytest.approx(0.1)  # weights summing below 1
    assert out["CASH"].iloc[1] == 1.0  # fully uninvested
    assert np.isnan(out["CASH"].iloc[2])  # warm-up rows stay NaN
    assert out["CASH"].iloc[3] == 0.0
    assert (out.drop(columns="CASH").sum(axis=1) + out["CASH"]).dropna().eq(1.0).all()
    assert "CASH" not in weights.columns  # the strategy's frame is untouched


def test_core_trend_cash_risk_off_holds_cash_below_the_sma():
    cfg = _cfg()
    _, close = _panel(["EWJ"], cfg)
    rule = Rule("core_trend", {"risk_on": "EWJ", "risk_off": "CASH", "lookback": 200})
    weights = with_cash(REGISTRY[rule.family].weights(close, **rule.params))
    off = weights["EWJ"] == 0.0
    assert off.any()
    assert (weights.loc[off, "CASH"] == 1.0).all()
    assert (weights.loc[weights["EWJ"] == 1.0, "CASH"] == 0.0).all()


def test_scoring_index_never_includes_the_excluded_years():
    cfg = _cfg()
    kept = scoring_index(pd.bdate_range("1996-01-01", DATA_END), cfg.windows, DATA_END)
    assert not ((kept >= "2005-01-01") & (kept <= "2022-12-31")).any()
    assert kept[0] == pd.Timestamp("1997-01-01")
    assert kept[-1] == DATA_END


def test_scoring_index_stops_at_the_data_end():
    cfg = _cfg()
    end = pd.Timestamp("2024-06-28")
    assert scoring_index(pd.bdate_range("1996-01-01", DATA_END), cfg.windows, end)[-1] == end


def test_market_checks_use_the_core_thresholds():
    cfg = _cfg()
    bh = {"sharpe": 0.5, "max_drawdown": 0.3, "cagr": 0.06}
    ok = {"sharpe": 0.56, "max_drawdown": 0.3, "cagr": 0.051}
    assert market_checks(ok, bh, cfg) == {"sharpe": True, "max_drawdown": True, "cagr": True}
    assert not market_checks({**ok, "sharpe": 0.549}, bh, cfg)["sharpe"]
    assert not market_checks({**ok, "max_drawdown": 0.31}, bh, cfg)["max_drawdown"]
    assert not market_checks({**ok, "cagr": 0.0499}, bh, cfg)["cagr"]


def test_evaluate_market_scores_the_joined_windows_only():
    cfg = _cfg()
    open_, close = _panel(["EWJ"], cfg)
    rule = Rule("core_trend", {"risk_on": "EWJ", "risk_off": "IEF", "lookback": 200})
    res = evaluate_market(open_, close, rule, "EWJ", cfg, DATA_END)
    assert res["enough_data"]
    assert res["days"] >= cfg.min_scored_days
    assert res["days"] == sum(w["days"] for w in res["windows"])
    assert res["rule"]["start"] >= "1997-01-01"
    assert res["rule"]["end"] == "2026-10-19"
    assert [w["end"] for w in res["windows"]] == ["2004-12-31", "2026-10-19"]
    assert set(res["checks"]) == {"sharpe", "max_drawdown", "cagr"}
    assert res["passed"] == all(res["checks"].values())
    assert res["sharpe_gain"] == pytest.approx(
        res["rule"]["sharpe"] - res["buy_and_hold"]["sharpe"]
    )


def test_late_only_scores_from_2023():
    cfg = _cfg()
    open_, close = _panel(["EWJ"], cfg)
    rule = Rule("core_trend", {"risk_on": "EWJ", "risk_off": "GLD", "lookback": 200})
    res = evaluate_market(open_, close, rule, "EWJ", cfg, DATA_END, late_only=True)
    assert res["late_only"]
    assert res["rule"]["start"] >= "2023-01-01"
    assert len(res["windows"]) == 1


def test_market_with_too_little_data_does_not_pass():
    cfg = _cfg()
    open_, close = _panel(["EWZ"], cfg)
    late = close.index < pd.Timestamp("2004-06-01")
    open_.loc[late, "EWZ"] = np.nan
    close.loc[late, "EWZ"] = np.nan
    end = pd.Timestamp("2023-12-29")  # about 250 late-window days, none early
    rule = Rule("core_trend", {"risk_on": "EWZ", "risk_off": "IEF", "lookback": 200})
    res = evaluate_market(open_, close, rule, "EWZ", cfg, end)
    assert not res["enough_data"]
    assert not res["passed"]
    assert res["sharpe_gain"] is None


from qrl.international import MarketSet, set_verdict  # noqa: E402

MAIN = MarketSet("main", ("A", "B", "C", "D", "E", "F", "G"), 5)


def _m(passed, gain, enough=True):
    return {"passed": passed, "sharpe_gain": gain, "enough_data": enough}


def test_five_of_seven_with_a_negative_average_fails():
    v = set_verdict([_m(True, 0.1)] * 5 + [_m(False, -0.6)] * 2, MAIN)
    assert v["passed_markets"] == 5
    assert v["average_sharpe_gain"] < 0
    assert not v["passed"]


def test_six_of_seven_with_a_positive_average_passes():
    v = set_verdict([_m(True, 0.2)] * 6 + [_m(False, -0.1)], MAIN)
    assert v["passed"]
    assert v["required"] == 5
    assert v["markets"] == 7


def test_four_of_seven_fails():
    assert not set_verdict([_m(True, 0.3)] * 4 + [_m(False, 0.1)] * 3, MAIN)["passed"]


def test_a_market_without_enough_data_is_not_passed_and_left_out_of_the_average():
    v = set_verdict([_m(True, 0.2)] * 5 + [_m(False, None, enough=False)] * 2, MAIN)
    assert v["passed"]
    assert v["average_sharpe_gain"] == pytest.approx(0.2)
    assert v["markets"] == 7


def test_no_market_with_enough_data_fails():
    v = set_verdict([_m(False, None, enough=False)] * 7, MAIN)
    assert v["average_sharpe_gain"] is None
    assert not v["passed"]
