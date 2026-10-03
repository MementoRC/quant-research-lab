"""Synthetic-only tests for the Phase 4 factor families (value_ey, profitability,
low_investment) and the `qrl.factor_data` provider behind their extra `fields`.

The generic look-ahead loop in tests/test_strategies.py only builds close frames
and only walks `REGISTRY`; the factor families sit in `SLEEVE_REGISTRY` and need
fundamentals frames, so their look-ahead checks live here. They read the
families' `EXAMPLE_PARAMS` from that file (so the registration rule of AGENTS.md
is still enforced) and reuse `qrl.checks.assert_causal` with random fixed
fundamentals/membership frames and a tampered close.
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
import pytest
from test_strategies import EXAMPLE_PARAMS

import qrl.search as search_mod
from qrl import fundamentals as fd
from qrl.checks import assert_causal
from qrl.data import synthetic_prices
from qrl.factor_data import (
    FACTOR_FIELDS,
    FactorData,
    assets_lag1y_panel,
    build_panel,
    factor_universe,
)
from qrl.search import SearchData
from qrl.strategies import FACTOR_FAMILIES, SLEEVE_REGISTRY, iter_grid
from qrl.strategies.factors import (
    low_investment,
    profitability,
    rebalance_flags,
    value_ey,
)

IDX = pd.bdate_range("2010-12-01", "2012-12-31")
COLS = list("ABCDEF")
FAMILIES = sorted(FACTOR_FAMILIES)


def const(values, dtype=float) -> pd.DataFrame:
    return pd.DataFrame(
        np.tile(np.asarray(values, dtype=dtype), (len(IDX), 1)), index=IDX, columns=COLS
    )


def all_members() -> pd.DataFrame:
    return const([True] * 6, dtype=bool)


def flat_close(values=(10.0,) * 6) -> pd.DataFrame:
    return const(list(values))


def held(w: pd.DataFrame, row: int) -> set[str]:
    return set(w.columns[w.iloc[row].fillna(0.0) > 0])


def first_rebalance_row(w: pd.DataFrame) -> int:
    return int(np.flatnonzero(w.notna().all(axis=1).to_numpy())[0])


# --------------------------------------------------------------------------- registration


def test_families_registered_with_example_params_and_fields():
    for name in FAMILIES:
        assert name in SLEEVE_REGISTRY
        assert name in EXAMPLE_PARAMS
        spec = SLEEVE_REGISTRY[name]
        assert spec.fields[0] == "close"
        assert spec.fields[1] == "pit_member"
        assert set(spec.fields[1:]) <= set(FACTOR_FIELDS)
        assert len(iter_grid(spec.space)) == 8
        assert spec.tickers({"tickers": ["A", "B"]}) == ["A", "B"]
    assert FAMILIES == ["low_investment", "profitability", "value_ey"]


# --------------------------------------------------------------------------- generic look-ahead


def _random_frames(close: pd.DataFrame, fields: tuple[str, ...], seed: int) -> dict:
    rng = np.random.default_rng(seed)
    shape = close.shape
    frames = {
        "pit_member": pd.DataFrame(
            rng.random(shape) > 0.3, index=close.index, columns=close.columns
        )
    }
    for f in fields[2:]:
        lo, hi = (50, 150) if f == "fund_shares" else (-1, 5)
        frames[f] = pd.DataFrame(
            rng.uniform(lo, hi, shape), index=close.index, columns=close.columns
        )
    return frames


@pytest.mark.parametrize("name", FAMILIES)
@pytest.mark.parametrize(
    "extra",
    [{}, {"rebalance": "quarterly", "n_hold": 3, "trend_filter": True}, {"n_hold": 2}],
)
def test_factor_families_are_causal(name, extra):
    spec = SLEEVE_REGISTRY[name]
    _, close = synthetic_prices(list("ABCDEF"), start="2010-12-01", end="2012-12-31")
    frames = _random_frames(close, spec.fields, seed=3)
    params = {**EXAMPLE_PARAMS[name], **extra}

    def fn(c):
        args = [c if f == "close" else frames[f] for f in spec.fields]
        return spec.weights(*args, **params)

    assert_causal(fn, close)


def _facts(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=fd.FACT_COLUMNS)
    for col in ("start", "end", "filed"):
        df[col] = pd.to_datetime(df[col]).astype("datetime64[ns]")
    return df


def _row(ticker, concept, end, val, filed, *, start=None, taxonomy="us-gaap") -> dict:
    return {
        "ticker": ticker,
        "taxonomy": taxonomy,
        "concept": concept,
        "unit": "USD",
        "start": start,
        "end": end,
        "val": val,
        "form": "10-Q",
        "fy": None,
        "fp": None,
        "filed": filed,
        "accn": f"{ticker}-{concept}-{pd.Timestamp(filed):%Y%m%d}",
    }


def _company_rows(ticker: str, scale: float, quarters: int = 14) -> list[dict]:
    rows = []
    for q in range(quarters):
        end = pd.Timestamp(2010 + q // 4, 3 * (q % 4) + 3, 1) + pd.offsets.MonthEnd(0)
        filed = end + pd.Timedelta(days=40)
        start = end - pd.Timedelta(days=89)
        value = scale * (1 + 0.1 * q)
        rows += [
            _row(ticker, "NetIncomeLoss", end, value, filed, start=start),
            _row(ticker, "OperatingIncomeLoss", end, 2 * value, filed, start=start),
            _row(ticker, "Assets", end, 100 * value, filed),
            _row(ticker, fd.DEI_SHARES, end, 1000 * scale, filed, taxonomy="dei"),
        ]
    return rows


def _membership(tickers, idx) -> pd.DataFrame:
    month_ends = pd.Series(idx, index=idx).groupby([idx.year, idx.month]).max()
    return pd.DataFrame([{"month_end": m, "ticker": t} for m in month_ends for t in tickers])


def _all_rows(factor: float = 1.0, tampered_from: pd.Timestamp | None = None) -> pd.DataFrame:
    rows = []
    for k, t in enumerate(["AAA", "BBB", "CCC"]):
        for r in _company_rows(t, scale=(k + 1) * factor):
            if tampered_from is not None and r["filed"] >= tampered_from:
                r = {**r, "val": r["val"] * 7 + 13}
            rows.append(r)
    return _facts(rows)


CUT = pd.Timestamp("2012-06-01")
TICKS = ["AAA", "BBB", "CCC"]


def test_fundamentals_filed_on_or_after_t_cannot_change_weights_at_t(tmp_path):
    idx = pd.bdate_range("2010-12-01", "2013-03-29")
    _, close = synthetic_prices(TICKS, start="2010-12-01", end="2013-03-29")
    mem = _membership(TICKS, idx)
    pa = FactorData(mem, _all_rows(), {}, cache_dir=tmp_path / "a")
    pb = FactorData(mem, _all_rows(tampered_from=CUT), {}, cache_dir=tmp_path / "b")
    pos = int(idx.searchsorted(CUT, side="right"))  # rows <= CUT
    for name in FAMILIES:
        spec = SLEEVE_REGISTRY[name]
        wa, wb = (
            spec.weights(close, *[p.panel(f, idx, TICKS) for f in spec.fields[1:]], n_hold=2)
            for p in (pa, pb)
        )
        pd.testing.assert_frame_equal(wa.iloc[:pos], wb.iloc[:pos])
    for field in FACTOR_FIELDS[1:]:
        a, b = pa.panel(field, idx, TICKS), pb.panel(field, idx, TICKS)
        pd.testing.assert_frame_equal(a.iloc[:pos], b.iloc[:pos])
        if field != "fund_assets_lag1y":  # its values come from older, untampered filings
            assert not a.iloc[pos:].equals(b.iloc[pos:]), field


def test_prices_after_t_cannot_change_weights_at_t_with_provider_panels(tmp_path):
    idx = pd.bdate_range("2010-12-01", "2013-03-29")
    _, close = synthetic_prices(TICKS, start="2010-12-01", end="2013-03-29")
    p = FactorData(_membership(TICKS, idx), _all_rows(), {}, cache_dir=tmp_path)
    spec = SLEEVE_REGISTRY["value_ey"]
    panels = [p.panel(f, idx, TICKS) for f in spec.fields[1:]]
    assert_causal(lambda c: spec.weights(c, *panels, n_hold=2), close)


# --------------------------------------------------------------------------- ranking


def test_value_ey_prefers_high_earnings_yield():
    ni = const([10.0] * 6)
    close = flat_close((50, 40, 30, 20, 10, 5))  # cap falls -> EY rises along the columns
    w = value_ey(close, all_members(), ni, const([1.0] * 6), n_hold=2)
    assert held(w, first_rebalance_row(w)) == {"E", "F"}
    assert w.iloc[first_rebalance_row(w)].sum() == pytest.approx(1.0)


def test_value_ey_uses_shares_times_close_as_market_cap():
    ni = const([10.0] * 6)
    shares = const([1.0, 1.0, 1.0, 1.0, 1.0, 100.0])  # F: huge share count -> low EY
    w = value_ey(flat_close((5, 10, 20, 30, 40, 1)), all_members(), ni, shares, n_hold=1)
    assert held(w, first_rebalance_row(w)) == {"A"}


def test_value_ey_excludes_non_positive_net_income():
    ni = const([-5.0, 0.0, 10.0, 20.0, 30.0, 40.0])
    close = flat_close((1.0, 1.0, 100.0, 100.0, 100.0, 100.0))  # A,B would otherwise lead
    w = value_ey(close, all_members(), ni, const([1.0] * 6), n_hold=6)
    row = w.iloc[first_rebalance_row(w)]
    assert set(w.columns[row > 0]) == {"C", "D", "E", "F"}
    assert row[["A", "B"]].eq(0).all()


def test_profitability_prefers_high_operating_income_over_assets():
    opinc = const([10.0] * 6)
    assets = const([100.0, 50.0, 200.0, 25.0, 400.0, 10.0])
    w = profitability(flat_close(), all_members(), opinc, assets, n_hold=2)
    assert held(w, first_rebalance_row(w)) == {"F", "D"}


def test_low_investment_prefers_lowest_asset_growth():
    assets = const([100.0] * 6)
    growth = np.array([0.5, 0.1, -0.2, 0.3, 0.0, 0.9])
    lag = const(list(100.0 / (1.0 + growth)))
    w = low_investment(flat_close(), all_members(), assets, lag, n_hold=2)
    assert held(w, first_rebalance_row(w)) == {"C", "E"}


def test_low_investment_requires_both_assets_values():
    assets = const([100.0] * 6)
    growth = np.array([0.5, 0.1, -0.2, 0.3, 0.0, 0.9])
    lag = const(list(100.0 / (1.0 + growth)))
    lag["C"] = np.nan  # best name has no year-earlier value -> ineligible
    assets["E"] = np.nan  # next best has no current value -> ineligible
    w = low_investment(flat_close(), all_members(), assets, lag, n_hold=2)
    assert held(w, first_rebalance_row(w)) == {"B", "D"}


# --------------------------------------------------------------------------- membership & holding rules


def test_non_members_are_never_held():
    member = const([False, False, True, True, True, True], dtype=bool)
    ni = const([100.0, 90.0, 1.0, 2.0, 3.0, 4.0])
    w = value_ey(flat_close(), member, ni, const([1.0] * 6), n_hold=2)
    assert w[["A", "B"]].fillna(0.0).eq(0).all().all()
    assert held(w, first_rebalance_row(w)) == {"E", "F"}


def test_monthly_rebalance_dates_and_constant_weights_between():
    rng = np.random.default_rng(5)
    ni = pd.DataFrame(rng.uniform(1, 9, (len(IDX), 6)), index=IDX, columns=COLS)
    w = value_ey(flat_close(), all_members(), ni, const([1.0] * 6), n_hold=2)
    expected = rebalance_flags(IDX, "monthly")
    firsts = pd.Series(IDX).groupby([IDX.year, IDX.month]).min()
    assert set(IDX[expected]) == set(firsts) - {IDX[0]}
    changed = w.dropna().diff().abs().sum(axis=1).gt(0)
    assert set(changed[changed].index) <= set(IDX[expected])
    assert changed.sum() > 3  # scores move, so selections do change at rebalances


def test_quarterly_rebalance_only_in_quarter_start_months():
    flags = rebalance_flags(IDX, "quarterly")
    assert set(IDX[flags].month) == {1, 4, 7, 10}
    assert len(IDX[flags]) == 8  # Jan 2011 .. Oct 2012
    with pytest.raises(ValueError, match="rebalance must be"):
        rebalance_flags(IDX, "weekly")


def test_departed_member_is_held_until_next_quarterly_rebalance():
    member = all_members()
    member.loc["2011-02-15":, "F"] = False  # F leaves mid-quarter
    ni = const([1.0, 1.0, 1.0, 1.0, 1.0, 100.0])
    w = value_ey(flat_close(), member, ni, const([1.0] * 6), n_hold=1, rebalance="quarterly")
    assert w.loc["2011-03-31", "F"] == 1.0  # kept until the next rebalance
    assert w.loc["2011-04-01", "F"] == 0.0  # weight goes to cash there
    assert w.loc["2011-04-01"].sum() == pytest.approx(1.0)  # replaced by an eligible name


def test_fewer_eligible_than_n_hold_holds_one_over_n_each_rest_cash():
    member = const([True, True, False, False, False, False], dtype=bool)
    w = value_ey(flat_close(), member, const([5.0] * 6), const([1.0] * 6), n_hold=4)
    row = w.iloc[first_rebalance_row(w)]
    assert row[["A", "B"]].eq(0.25).all()
    assert row.sum() == pytest.approx(0.5)


def test_weights_warmup_prefix_is_nan_then_numeric_and_long_only():
    w = profitability(flat_close(), all_members(), const([1.0] * 6), const([10.0] * 6), n_hold=3)
    k = first_rebalance_row(w)
    assert k > 0
    assert w.iloc[:k].isna().all().all()
    assert w.iloc[k:].notna().all().all()
    assert (w.iloc[k:] >= 0).all().all()
    assert (w.iloc[k:].sum(axis=1) <= 1 + 1e-12).all()


# --------------------------------------------------------------------------- trend filter


def _regime_close() -> pd.DataFrame:
    n = len(IDX)
    drift = np.where(np.arange(n) < 350, 0.001, -0.01)
    level = 100 * np.exp(np.cumsum(drift))
    return pd.DataFrame(np.tile(level[:, None], (1, 6)), index=IDX, columns=COLS)


def test_trend_filter_goes_to_cash_when_members_below_200d_average():
    close = _regime_close()
    args = (close, all_members(), const([1.0] * 6), const([1.0] * 6))
    plain = value_ey(*args, n_hold=2)
    filt = value_ey(*args, n_hold=2, trend_filter=True)
    assert filt.iloc[100].sum() == 0.0  # 200-day average not available yet -> cash
    assert plain.iloc[100].sum() == pytest.approx(1.0)
    assert filt.iloc[300].sum() == pytest.approx(1.0)  # rising: invested
    assert filt.iloc[-1].sum() == 0.0  # long decline: cash
    assert plain.iloc[-1].sum() == pytest.approx(1.0)


# --------------------------------------------------------------------------- Assets one year earlier


def _assets_facts() -> pd.DataFrame:
    spec = [
        ("2010-12-31", "2011-02-15", 100.0),
        ("2011-03-31", "2011-05-10", 110.0),
        ("2011-06-30", "2011-08-10", 120.0),
        ("2011-09-30", "2011-11-09", 130.0),
        ("2011-12-31", "2012-02-15", 150.0),
        ("2012-03-31", "2012-05-10", 160.0),
        ("2011-03-31", "2012-06-01", 115.0),  # restated comparative, public from 2012-06-04
    ]
    return _facts([_row("X", "Assets", e, v, f) for e, f, v in spec])


def test_assets_lag1y_is_value_for_period_end_one_year_before_latest_balance_sheet():
    dates = pd.DatetimeIndex(
        ["2011-02-16", "2012-02-14", "2012-02-16", "2012-05-11", "2012-06-01", "2012-06-04"]
    )
    out = assets_lag1y_panel(_assets_facts(), dates, ["X"])["X"]
    assert np.isnan(out["2011-02-16"])  # only one balance sheet known
    assert np.isnan(out["2012-02-14"])  # latest 2011-09-30: nothing within 45d of 2010-09-30
    assert out["2012-02-16"] == 100.0  # latest 2011-12-31 -> 2010-12-31
    assert out["2012-05-11"] == 110.0  # latest 2012-03-31 -> 2011-03-31 as first filed
    assert out["2012-06-01"] == 110.0  # restatement filed 2012-06-01 is not yet usable
    assert out["2012-06-04"] == 115.0  # ... and replaces the original once public
    plain = fd.pit_panel(_assets_facts(), "Assets", dates, ["X"])["X"]
    assert plain["2012-06-04"] == 160.0  # fund_assets stays the latest balance sheet


# --------------------------------------------------------------------------- provider


def _provider(tmp_path, splits=None) -> tuple[FactorData, pd.DatetimeIndex]:
    idx = pd.bdate_range("2010-12-01", "2013-03-29")
    mem = _membership(["AAA", "BBB"], idx)
    mem = mem[~((mem["ticker"] == "BBB") & (mem["month_end"] < "2012-01-01"))]
    return FactorData(mem, _all_rows(), splits or {}, cache_dir=tmp_path), idx


def test_provider_panels_align_to_price_index_and_cache(tmp_path):
    prov, idx = _provider(tmp_path)
    cols = ["AAA", "BBB", "CCC"]
    first = {f: prov.panel(f, idx, cols) for f in FACTOR_FIELDS}
    for name, frame in first.items():
        assert frame.index.equals(idx), name
        assert list(frame.columns) == cols, name
    assert first["pit_member"].dtypes.eq(bool).all()
    assert first["pit_member"]["CCC"].eq(False).all()  # never a member
    assert not first["pit_member"].loc["2010-12-30", "AAA"]  # on/before the first month-end
    assert first["pit_member"].loc["2011-01-03", "AAA"]
    assert first["pit_member"].loc["2012-06-01", "AAA"]
    assert not first["pit_member"].loc["2011-06-01", "BBB"]
    assert first["fund_ni_ttm"].loc["2012-06-01", "AAA"] > 0
    assert len(list(tmp_path.glob("*.parquet"))) == len(FACTOR_FIELDS) - 1
    again = FactorData(prov.membership, prov.facts, {}, cache_dir=tmp_path)
    for f in FACTOR_FIELDS:
        pd.testing.assert_frame_equal(again.panel(f, idx, cols), first[f], check_freq=False)
    with pytest.raises(KeyError):
        prov.panel("fund_nonsense", idx, cols)


def test_provider_cache_key_changes_with_facts(tmp_path):
    prov, idx = _provider(tmp_path)
    other = FactorData(prov.membership, _all_rows(factor=2.0), {}, cache_dir=tmp_path)
    a = prov.panel("fund_assets", idx, TICKS)
    b = other.panel("fund_assets", idx, TICKS)
    assert not a.equals(b)


def test_fund_shares_are_split_adjusted_total_shares(tmp_path):
    splits = {"AAA": pd.Series([2.0], index=pd.DatetimeIndex(["2012-01-03"]))}
    prov, idx = _provider(tmp_path, splits)
    s = prov.panel("fund_shares", idx, TICKS)
    # AAA scale 1 -> 1000 shares filed 2011-05-10 (before the split) -> doubled
    assert s.loc["2011-06-01", "AAA"] == 2000.0
    assert s.loc["2011-06-01", "BBB"] == 2000.0  # scale 2, no split
    assert s["CCC"].dropna().iloc[0] == 3000.0


def test_build_panel_rejects_unknown_field():
    with pytest.raises(KeyError):
        build_panel("nope", _all_rows(), IDX, TICKS)


def test_factor_universe_is_every_ticker_ever_a_member():
    mem = pd.DataFrame(
        {"month_end": pd.to_datetime(["2011-01-31", "2011-02-28"]), "ticker": ["ZZ", "AA"]}
    )
    assert factor_universe(mem) == ["AA", "ZZ"]


def test_search_fields_price_only_unchanged_and_factor_fields_resolved(tmp_path, monkeypatch):
    data = SearchData.load(["AAA", "BBB"], synthetic=True, start="2010-12-01")
    tickers = ["AAA", "BBB"]
    out = data.fields(("close", "volume", "high"), tickers)
    pd.testing.assert_frame_equal(out[0], data.close[tickers])
    pd.testing.assert_frame_equal(out[1], data.volume[tickers])
    pd.testing.assert_frame_equal(out[2], data.high[tickers])

    prov = FactorData(_membership(TICKS, data.close.index), _all_rows(), {}, cache_dir=tmp_path)
    monkeypatch.setattr(search_mod, "default_provider", lambda: prov)
    close, member, ni, shares = data.fields(SLEEVE_REGISTRY["value_ey"].fields, tickers)
    for f in (member, ni, shares):
        assert f.index.equals(close.index)
        assert list(f.columns) == tickers
    w = value_ey(close, member, ni, shares, n_hold=1)
    assert w.shape == close.shape


@pytest.mark.parametrize(
    ("n_hold", "rebalance", "trend"),
    list(itertools.product([30, 50], ["monthly", "quarterly"], [False, True])),
)
def test_every_searchable_combination_runs(n_hold, rebalance, trend):
    for name in FAMILIES:
        spec = SLEEVE_REGISTRY[name]
        frames = _random_frames(flat_close(), spec.fields, seed=1)
        args = [flat_close() if f == "close" else frames[f] for f in spec.fields]
        w = spec.weights(*args, n_hold=n_hold, rebalance=rebalance, trend_filter=trend)
        assert w.shape == flat_close().shape
        assert (w.dropna().sum(axis=1) <= 1 + 1e-12).all()
