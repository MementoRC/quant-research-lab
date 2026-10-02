"""Point-in-time universe: synthetic data only, no network."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import yaml

from qrl import fundamentals as fd
from qrl import pit_universe as pu

INDEX = pd.bdate_range("2020-01-01", "2020-06-30")
MONTH_ENDS = pu.month_end_dates(INDEX, pd.Timestamp("2020-01-01"))


def _facts(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for col in fd.FACT_COLUMNS:
        if col not in df.columns:
            df[col] = None
    for col in ("start", "end", "filed"):
        df[col] = pd.to_datetime(df[col])
    return df[fd.FACT_COLUMNS]


def _dei(ticker: str, end: str, filed: str, val: float, accn: str = "a1") -> dict:
    return {
        "ticker": ticker,
        "taxonomy": "dei",
        "concept": fd.DEI_SHARES,
        "end": end,
        "filed": filed,
        "val": val,
        "accn": accn,
    }


def _close(values: dict[str, float]) -> pd.DataFrame:
    return pd.DataFrame({t: np.full(len(INDEX), v) for t, v in values.items()}, index=INDEX)


# ----------------------------------------------------------------------- shares


def test_multi_class_shares_are_summed_per_accn_and_end():
    facts = _facts(
        [
            _dei("AAA", "2020-02-10", "2020-02-12", 600.0, "k1"),  # class A
            _dei("AAA", "2020-02-10", "2020-02-12", 400.0, "k1"),  # class B
            _dei("AAA", "2020-05-05", "2020-05-07", 700.0, "k2"),  # next filing, class A
            _dei("AAA", "2020-05-05", "2020-05-07", 400.0, "k2"),
        ]
    )
    total = fd.total_shares_panel(facts, INDEX, ["AAA"])["AAA"]
    assert np.isnan(total.loc["2020-02-12"])  # filing day itself: not yet usable
    assert total.loc["2020-02-13"] == 1000.0
    assert total.loc["2020-05-08"] == 1100.0


def test_total_shares_falls_back_to_us_gaap_and_prefers_dei():
    gaap = {
        "ticker": "BBB",
        "taxonomy": "us-gaap",
        "concept": fd.GAAP_SHARES,
        "end": "2020-03-31",
        "filed": "2020-04-20",
        "val": 50.0,
        "accn": "g1",
    }
    facts = _facts(
        [
            gaap,
            _dei("AAA", "2020-02-10", "2020-02-12", 10.0),
            _dei("BBB", "2019-12-31", "2020-01-02", 5.0),
        ]
    )
    shares = fd.total_shares_panel(facts, INDEX, ["AAA", "BBB"])
    assert shares.loc["2020-04-21", "AAA"] == 10.0
    assert shares.loc["2020-04-21", "BBB"] == 5.0  # dei known -> wins over later us-gaap
    only_gaap = fd.total_shares_panel(_facts([gaap]), INDEX, ["BBB"])
    assert only_gaap.loc["2020-04-21", "BBB"] == 50.0


def _wavg(start: str, end: str, filed: str, val: float, ticker: str = "WWW") -> dict:
    return {
        "ticker": ticker,
        "taxonomy": "us-gaap",
        "concept": fd.WA_SHARES,
        "start": start,
        "end": end,
        "filed": filed,
        "val": val,
    }


def test_weighted_average_fallback_prefers_latest_quarter_then_annual():
    facts = _facts(
        [
            _wavg("2019-01-01", "2019-12-31", "2020-02-20", 90.0),  # annual
            _wavg("2020-01-01", "2020-03-31", "2020-05-01", 100.0),  # quarterly
        ]
    )
    shares, _, _, source = fd.total_shares_sourced_panels(facts, INDEX, ["WWW"])
    assert shares.loc["2020-03-02", "WWW"] == 90.0  # only the annual is public yet
    assert shares.loc["2020-05-01", "WWW"] == 90.0  # filing day itself: not usable
    assert shares.loc["2020-05-04", "WWW"] == 100.0  # quarter public -> preferred
    assert source.loc["2020-05-04", "WWW"] == "wavg"
    assert pd.isna(source.loc["2020-02-20", "WWW"])


def test_share_source_priority_is_dei_then_gaap_then_weighted_average():
    gaap = {
        "ticker": "AAA",
        "taxonomy": "us-gaap",
        "concept": fd.GAAP_SHARES,
        "end": "2020-02-01",
        "filed": "2020-02-10",
        "val": 50.0,
        "accn": "g",
    }
    facts = _facts(
        [
            _wavg("2019-10-01", "2019-12-31", "2020-01-15", 40.0, "AAA"),
            gaap,
            _dei("AAA", "2020-03-10", "2020-03-12", 60.0),
        ]
    )
    shares, _, _, source = fd.total_shares_sourced_panels(facts, INDEX, ["AAA"])
    assert (shares.loc["2020-01-16", "AAA"], source.loc["2020-01-16", "AAA"]) == (40.0, "wavg")
    assert (shares.loc["2020-02-11", "AAA"], source.loc["2020-02-11", "AAA"]) == (50.0, "us-gaap")
    assert (shares.loc["2020-03-13", "AAA"], source.loc["2020-03-13", "AAA"]) == (60.0, "dei")


def test_predecessor_facts_are_used_only_before_the_successor_first_filing():
    old = _facts(
        [
            _dei("AAA", "2020-01-05", "2020-01-10", 100.0, "o1"),
            _dei("AAA", "2020-04-05", "2020-04-10", 999.0, "o2"),  # after successor began: dropped
        ]
    )
    new = _facts([_dei("AAA", "2020-03-05", "2020-03-10", 120.0, "n1")])
    merged = pu.merge_predecessor_facts(new, old)
    assert sorted(merged["val"]) == [100.0, 120.0]
    s = fd.total_shares_panel(merged, INDEX, ["AAA"])["AAA"]
    assert s.loc["2020-02-03"] == 100.0  # from the predecessor CIK
    assert s.loc["2020-03-11"] == 120.0  # successor takes over
    assert s.loc["2020-04-13"] == 120.0  # predecessor's later filing is ignored


def test_predecessor_map_entries_are_ticker_to_int_ciks():
    assert pu.CIK_PREDECESSORS["XOM"] == [34088]
    assert all(isinstance(c, int) for v in pu.CIK_PREDECESSORS.values() for c in v)


def test_total_shares_ignores_filings_not_yet_public():
    facts = _facts([_dei("AAA", "2020-02-10", "2020-02-12", 10.0)])
    s = fd.total_shares_panel(facts, INDEX, ["AAA"])["AAA"]
    assert s.loc[:"2020-02-12"].isna().all()
    assert s.loc["2020-02-13"] == 10.0


def test_split_adjustment_uses_splits_after_the_share_date():
    facts = _facts([_dei("AAA", "2020-01-10", "2020-01-15", 100.0)])
    splits = {"AAA": pd.Series([2.0, 3.0], index=pd.to_datetime(["2020-02-20", "2020-04-20"]))}
    cap = pu.market_cap_panel(facts, _close({"AAA": 1.0}), MONTH_ENDS, splits)["AAA"]
    assert cap.loc["2020-01-31"] == 600.0  # both later splits apply to the old count


def test_count_filed_after_a_split_is_not_adjusted_again():
    # period ends before the 2-for-1 ex-date but the filing (and so the count) is post-split
    facts = _facts([_dei("AAA", "2020-02-10", "2020-03-05", 200.0)])
    splits = {"AAA": pd.Series([2.0], index=pd.to_datetime(["2020-02-20"]))}
    cap = pu.market_cap_panel(facts, _close({"AAA": 1.0}), MONTH_ENDS, splits)["AAA"]
    assert cap.loc["2020-03-31"] == 200.0


# ----------------------------------------------------------------------- ranking


def _universe(extra: list[dict] | None = None, close_after: float = 1.0):
    facts = _facts(
        [
            _dei("AAA", "2020-01-05", "2020-01-10", 100.0),
            _dei("BBB", "2020-01-05", "2020-01-10", 300.0),
            _dei("CCC", "2020-01-05", "2020-01-10", 200.0),
            *(extra or []),
        ]
    )
    close = _close({"AAA": 1.0, "BBB": 1.0, "CCC": 1.0})
    close.loc["2020-02-03":, "AAA"] = close_after  # after the Jan month-end
    return facts, close


def test_ranking_uses_only_shares_filed_before_t_and_closes_up_to_t():
    facts, close = _universe()
    base = pu.rank_membership(pu.market_cap_panel(facts, close, MONTH_ENDS), top_n=2)
    jan = pd.Timestamp("2020-01-31")
    # A huge share count filed after Jan 31 and a huge price jump after Jan 31
    facts2, close2 = _universe([_dei("AAA", "2020-02-04", "2020-02-05", 1e9, "a2")], 1e6)
    changed = pu.rank_membership(pu.market_cap_panel(facts2, close2, MONTH_ENDS), top_n=2)
    pd.testing.assert_frame_equal(
        base[base["month_end"] == jan].reset_index(drop=True),
        changed[changed["month_end"] == jan].reset_index(drop=True),
    )
    assert list(base[base["month_end"] == jan]["ticker"]) == ["BBB", "CCC"]
    feb = pd.Timestamp("2020-02-28")
    assert changed[changed["month_end"] == feb].iloc[0]["ticker"] == "AAA"  # visible later


def test_rank_membership_top_n_and_ranks():
    caps = pd.DataFrame(
        {"A": [5.0, np.nan], "B": [9.0, 2.0], "C": [7.0, 3.0], "D": [1.0, np.nan]},
        index=pd.to_datetime(["2020-01-31", "2020-02-28"]),
    )
    m = pu.rank_membership(caps, top_n=2)
    assert m.columns.tolist() == pu.MEMBERSHIP_COLUMNS
    first = m[m["month_end"] == "2020-01-31"]
    assert first["ticker"].tolist() == ["B", "C"]
    assert first["rank"].tolist() == [1, 2]
    second = m[m["month_end"] == "2020-02-28"]
    assert second["ticker"].tolist() == ["C", "B"]  # only B and C have values


# ----------------------------------------------------------------------- pool


def test_one_ticker_per_cik_picks_most_liquid_class():
    table = pd.DataFrame(
        {
            "cik": [1, 1, 2, 2, 3],
            "ticker": ["GOOG", "GOOGL", "BRK-A", "BRK-B", "ZZZ"],
            "name": ["x"] * 5,
            "exchange": ["Nasdaq"] * 5,
        }
    )
    dv = {"GOOG": 5.0, "GOOGL": 9.0, "BRK-A": 1.0, "BRK-B": 1.0}  # tie -> alphabetical; ZZZ none
    out = pu.select_one_per_cik(table, dv)
    assert out["ticker"].tolist() == ["BRK-A", "GOOGL"]


def test_exchange_filter_and_ticker_normalisation():
    payload = {
        "fields": ["cik", "name", "ticker", "exchange"],
        "data": [
            [1, "A", "BRK.B", "NYSE"],
            [2, "B", "OTCX", "OTC"],
            [3, "C", "CCC", "Nasdaq"],
            [4, "D", "CBOE1", "CBOE"],
        ],
    }
    t = pu.parse_exchange_tickers(payload)
    assert t["ticker"].tolist() == ["BRK-B", "CCC"]


def test_pool_threshold_is_a_parameter():
    caps = pd.Series({"A": 3e9, "B": 2e9, "C": 1.9e9, "D": np.nan})
    assert pu.pool_filter(caps) == ["A", "B"]
    assert pu.pool_filter(caps, 3e9) == ["A"]
    assert pu.pool_filter(caps, 1e9) == ["A", "B", "C"]


# ----------------------------------------------------------------------- mask


def test_month_end_membership_applies_from_next_trading_day():
    jan, feb = pd.Timestamp("2020-01-31"), pd.Timestamp("2020-02-28")
    membership = pd.DataFrame(
        {
            "month_end": [jan, jan, feb],
            "ticker": ["A", "B", "B"],
            "market_cap": [2.0, 1.0, 1.0],
            "rank": [1, 2, 1],
        }
    )
    dates = pd.bdate_range("2020-01-29", "2020-03-06")
    mask = pu.membership_mask(membership, dates, ["A", "B", "C"])
    assert mask.dtypes.eq(bool).all()
    assert not mask.loc["2020-01-29":"2020-01-31"].to_numpy().any()  # nothing before first
    assert mask.loc["2020-02-03", ["A", "B"]].all()  # next trading day
    assert mask.loc[feb, ["A", "B"]].all()  # through the next month-end, inclusive
    assert mask.loc["2020-03-02", "B"]
    assert not mask.loc["2020-03-02", "A"]  # Feb's membership from next day
    assert not mask["C"].any()
    assert mask.loc["2020-03-06", "B"]  # last month-end applies to all later dates


def test_month_end_dates_drops_incomplete_current_month():
    idx = pd.bdate_range("2020-01-01", "2020-03-11")
    assert pu.month_end_dates(idx, pd.Timestamp("2020-01-01")).tolist() == [
        pd.Timestamp("2020-01-31"),
        pd.Timestamp("2020-02-28"),
    ]


# ----------------------------------------------------------------------- files


def _write_universe(tmp_path, membership, tamper: bool = False):
    csv = tmp_path / "config" / "universes" / "m.csv"
    sha = pu.write_membership(membership, csv)
    meta = {
        "name": "t",
        "survivorship_biased": True,
        "membership_file": "config/universes/m.csv",
        "membership_sha256": sha,
    }
    path = tmp_path / "config" / "universe_pit.yaml"
    path.write_text(yaml.safe_dump(meta))
    if tamper:
        csv.write_text(csv.read_text() + "2020-02-28,Z,1,1\n")
    return path


def _small_membership() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "month_end": pd.to_datetime(["2020-01-31", "2020-01-31"]),
            "ticker": ["A", "B"],
            "market_cap": [2.5e9, 1.0e9],
            "rank": [1, 2],
        }
    )


def test_loader_round_trips_and_verifies_hash(tmp_path):
    path = _write_universe(tmp_path, _small_membership())
    meta, membership = pu.load_pit_universe(path)
    assert meta["survivorship_biased"] is True
    assert membership["ticker"].tolist() == ["A", "B"]
    assert membership["month_end"].dtype.kind == "M"


def test_loader_rejects_csv_with_wrong_hash(tmp_path):
    path = _write_universe(tmp_path, _small_membership(), tamper=True)
    with pytest.raises(ValueError, match="sha256"):
        pu.load_pit_universe(path)


def test_loader_requires_survivorship_flag(tmp_path):
    path = _write_universe(tmp_path, _small_membership())
    meta = yaml.safe_load(path.read_text())
    meta["survivorship_biased"] = "yes"
    path.write_text(yaml.safe_dump(meta))
    with pytest.raises(ValueError, match="survivorship_biased"):
        pu.load_pit_universe(path)


def test_screen_payload_reports_assets_and_total_shares():
    payload = {
        "facts": {
            "us-gaap": {
                "Assets": {
                    "units": {
                        "USD": [
                            {"end": "2020-03-31", "val": 5, "filed": "2020-05-01", "form": "10-Q"}
                        ]
                    }
                }
            },
            "dei": {
                fd.DEI_SHARES: {
                    "units": {
                        "shares": [
                            {"end": "2020-04-20", "val": 6, "filed": "2020-05-01", "accn": "x"},
                            {"end": "2020-04-20", "val": 4, "filed": "2020-05-01", "accn": "x"},
                        ]
                    }
                }
            },
        }
    }
    rec = pu.screen_payload(payload)
    assert rec == {
        "has_assets": True,
        "domestic_filer": True,
        "shares": 10.0,
        "shares_end": "2020-04-20",
        "shares_filed": "2020-05-01",
        "shares_source": "dei",
    }
    assert pu.screen_payload({"facts": {}})["has_assets"] is False


def test_foreign_filer_is_not_a_domestic_filer():
    asset = {"end": "2020-03-31", "val": 5, "filed": "2020-05-01", "form": "20-F"}
    payload = {"facts": {"us-gaap": {"Assets": {"units": {"USD": [asset]}}}}}
    rec = pu.screen_payload(payload)
    assert rec["has_assets"] is True
    assert rec["domestic_filer"] is False


# ----------------------------------------------------------------------- class equivalents


def test_class_equivalent_ticker_uses_a_equivalent_shares_and_the_price_ticker_close():
    wa = {"start": "2019-01-01", "end": "2019-03-31", "filed": "2019-05-04", "val": 1.6e6}
    payload = {
        "facts": {
            "us-gaap": {fd.WA_SHARES: {"units": {"shares": [{**wa, "form": "10-Q"}]}}},
            "dei": {  # Class A only: a different basis, must be ignored
                fd.DEI_SHARES: {
                    "units": {
                        "shares": [
                            {"end": "2019-04-30", "val": 999, "filed": "2019-05-04", "accn": "x"}
                        ]
                    }
                }
            },
        }
    }
    idx = pd.bdate_range("2019-01-01", "2022-12-30")
    close_a = pd.Series(100_000.0, index=idx)  # the BRK-A close
    me = pu.month_end_dates(idx, pd.Timestamp("2019-01-01"))
    out = pu.company_features("BRK-B", payload, close_a, me, None, None).set_index("month_end")
    assert np.isnan(out.loc["2019-04-30", "shares"])  # not filed yet
    last = out.iloc[-1]  # > 3 years after the last count: carried, not stale
    assert last["shares"] == 1.6e6
    assert last["market_cap"] == pytest.approx(1.6e11)
    assert last["shares_source"] == pu.CLASS_EQ_SOURCE
    assert pu.CLASS_EQUIVALENTS["BRK-B"]["price_ticker"] == "BRK-A"


# ----------------------------------------------------------------------- stale-run detector


def test_stale_run_detector_flags_internal_gaps_over_six_months_only():
    months = pd.date_range("2020-01-31", periods=24, freq="ME")

    def feats(ticker: str, ok: list[bool]) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "month_end": months,
                "ticker": ticker,
                "has_price": True,
                "shares": [1.0 if o else np.nan for o in ok],
            }
        )

    long_gap = [False] * 3 + [True] * 5 + [False] * 8 + [True] * 8  # leading gap ignored
    short_gap = [True] * 5 + [False] * 6 + [True] * 13  # exactly 6: not flagged
    features = pd.concat([feats("LONG", long_gap), feats("SHORT", short_gap)])
    pool = pd.DataFrame({"ticker": ["LONG", "SHORT"], "cik": [1, 2], "market_cap": [60e9, 60e9]})
    hits = pu.shares_stale_detector(features, pool)
    assert hits["ticker"].tolist() == ["LONG"]
    assert hits.iloc[0]["months"] == 8
    assert pu.shares_stale_detector(features, pool.assign(market_cap=1e9)).empty


# ----------------------------------------------------------------------- scale guard


def test_fix_share_scale_repairs_power_of_1000_and_drops_the_rest():
    idx = MONTH_ENDS[:4]
    volume = pd.DataFrame({"A": 1e6}, index=idx)
    shares = pd.DataFrame({"A": [2e8, 2e11, 2e5, 1e21]}, index=idx)  # ok, x1000, /1000, hopeless
    fixed = pu.fix_share_scale(shares, volume)["A"]
    assert fixed.iloc[0] == 2e8
    assert fixed.iloc[1] == pytest.approx(2e8)
    assert fixed.iloc[2] == pytest.approx(2e8)
    assert np.isnan(fixed.iloc[3])


def test_fix_share_scale_leaves_cells_without_volume_alone():
    idx = MONTH_ENDS[:2]
    shares = pd.DataFrame({"A": [5.0, 7.0]}, index=idx)
    volume = pd.DataFrame({"A": [np.nan, np.nan]}, index=idx)
    pd.testing.assert_frame_equal(pu.fix_share_scale(shares, volume), shares)


def test_market_cap_panel_applies_the_scale_guard_when_volume_given():
    facts = _facts([_dei("AAA", "2020-01-05", "2020-01-10", 1e11)])  # mis-scaled by 1000
    volume = pd.DataFrame({"AAA": np.full(len(INDEX), 1e6)}, index=INDEX)
    cap = pu.market_cap_panel(facts, _close({"AAA": 2.0}), MONTH_ENDS, volume=volume)["AAA"]
    assert cap.loc["2020-01-31"] == 2e11  # < 60 bars of volume history: no evidence, unchanged
    long_index = pd.bdate_range("2019-01-01", "2020-06-30")
    vol_long = pd.DataFrame({"AAA": np.full(len(long_index), 1e6)}, index=long_index)
    close_long = pd.DataFrame({"AAA": np.full(len(long_index), 2.0)}, index=long_index)
    me = pu.month_end_dates(long_index, pd.Timestamp("2020-01-01"))
    cap2 = pu.market_cap_panel(facts, close_long, me, volume=vol_long)["AAA"]
    assert cap2.loc["2020-01-31"] == pytest.approx(1e8 * 2.0)
