"""Point-in-time fundamentals: synthetic fixtures only, no network."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qrl import fundamentals as fd

DATES = pd.bdate_range("2020-01-01", "2022-12-30")


def _facts(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for col in fd.FACT_COLUMNS:
        if col not in df.columns:
            df[col] = None
    for col in ("start", "end", "filed"):
        df[col] = pd.to_datetime(df[col])
    return df[fd.FACT_COLUMNS]


def _assets(end: str, filed: str, val: float, ticker: str = "AAA") -> dict:
    return {"ticker": ticker, "concept": "Assets", "end": end, "filed": filed, "val": val}


def _flow(start: str, end: str, filed: str, val: float) -> dict:
    return {
        "ticker": "AAA",
        "concept": "NetIncomeLoss",
        "start": start,
        "end": end,
        "filed": filed,
        "val": val,
    }


def test_fact_filed_on_or_after_t_is_ignored():
    base = [_assets("2020-03-31", "2020-05-01", 100.0)]
    late = _assets("2020-06-30", "2020-08-07", 200.0)  # a Friday
    with_late = fd.pit_panel(_facts([*base, late]), "Assets", DATES, ["AAA"])
    without = fd.pit_panel(_facts(base), "Assets", DATES, ["AAA"])
    cutoff = pd.Timestamp("2020-08-07")
    pd.testing.assert_frame_equal(with_late.loc[:cutoff], without.loc[:cutoff])
    assert with_late.loc["2020-08-07", "AAA"] == 100.0  # filing day itself: not yet usable
    assert with_late.loc["2020-08-10", "AAA"] == 200.0  # first trading day after


def test_restatement_effective_only_after_its_filed_date():
    facts = _facts(
        [
            _assets("2020-03-31", "2020-05-01", 100.0),
            _assets("2020-03-31", "2020-09-15", 90.0),  # restated, same period end
        ]
    )
    p = fd.pit_panel(facts, "Assets", DATES, ["AAA"])["AAA"]
    assert p.loc["2020-05-04"] == 100.0
    assert p.loc["2020-09-15"] == 100.0
    assert p.loc["2020-09-16"] == 90.0


def test_older_period_filed_later_does_not_override_newer_period():
    facts = _facts(
        [
            _assets("2020-06-30", "2020-08-01", 200.0),
            _assets("2020-03-31", "2020-08-20", 100.0),  # prior-period comparative
        ]
    )
    p = fd.pit_panel(facts, "Assets", DATES, ["AAA"])["AAA"]
    assert p.loc["2020-09-01"] == 200.0


def test_ttm_sum_and_q4_derivation():
    facts = _facts(
        [
            _flow("2020-01-01", "2020-03-31", "2020-05-01", 10),
            _flow("2020-04-01", "2020-06-30", "2020-08-01", 20),
            _flow("2020-07-01", "2020-09-30", "2020-11-02", 30),
            _flow("2020-01-01", "2020-12-31", "2021-02-15", 100),  # 10-K: FY only
            _flow("2021-01-01", "2021-03-31", "2021-05-03", 50),
        ]
    )
    ttm = fd.ttm_panel(facts, "NetIncomeLoss", DATES, ["AAA"])["AAA"]
    assert np.isnan(ttm.loc["2020-11-03"])  # only three quarters known
    assert ttm.loc["2021-02-16"] == 100  # FY
    assert ttm.loc["2021-05-04"] == 20 + 30 + 40 + 50  # Q4 = 100 - (10+20+30) = 40
    assert ttm.loc["2021-05-03"] == 100  # Q1'21 filed that day: not yet usable


def test_ttm_nan_when_not_derivable():
    facts = _facts(
        [
            _flow("2020-01-01", "2020-03-31", "2020-05-01", 10),
            _flow("2020-07-01", "2020-09-30", "2020-11-02", 30),  # Q2 missing
            _flow("2020-10-01", "2020-12-31", "2021-02-15", 40),
            _flow("2021-01-01", "2021-03-31", "2021-05-03", 50),
        ]
    )
    ttm = fd.ttm_panel(facts, "NetIncomeLoss", DATES, ["AAA"])["AAA"]
    assert ttm.dropna().empty


def test_staleness_limit_gives_nan():
    facts = _facts([_assets("2020-03-31", "2020-05-01", 100.0)])
    p = fd.pit_panel(facts, "Assets", DATES, ["AAA"])["AAA"]
    assert p.loc["2021-05-03"] == 100.0
    assert np.isnan(p.loc["2021-08-02"])  # > 15 months after period end
    p2 = fd.pit_panel(facts, "Assets", DATES, ["AAA"], staleness_days=3000)["AAA"]
    assert p2.loc["2021-08-02"] == 100.0
    ttm_facts = _facts(
        [
            _flow("2020-01-01", "2020-12-31", "2021-02-15", 100),
        ]
    )
    ttm = fd.ttm_panel(ttm_facts, "NetIncomeLoss", DATES, ["AAA"])["AAA"]
    assert ttm.loc["2021-12-01"] == 100
    assert np.isnan(ttm.loc["2022-06-01"])


def test_missing_email_raises_before_any_request(monkeypatch, tmp_path):
    monkeypatch.delenv(fd.EMAIL_ENV_VAR, raising=False)

    def boom(*_a, **_k):
        raise AssertionError("network touched")

    monkeypatch.setattr(fd, "_http_get", boom)
    with pytest.raises(fd.SecIdentityError):
        fd.load_facts(["AAPL"], cache_dir=tmp_path, config_path=tmp_path / "none.yaml")


def test_user_agent_from_env_and_file(monkeypatch, tmp_path):
    monkeypatch.setenv(fd.EMAIL_ENV_VAR, "env@example.test")
    assert fd.sec_user_agent(tmp_path / "none.yaml") == "quant-research-lab env@example.test"
    monkeypatch.delenv(fd.EMAIL_ENV_VAR)
    cfg = tmp_path / "sec.yaml"
    cfg.write_text("contact_email: file@example.test\n")
    assert fd.sec_user_agent(cfg) == "quant-research-lab file@example.test"


def test_ticker_mapping_brk_b():
    payload = {
        "0": {"cik_str": 1067983, "ticker": "BRK-B", "title": "BERKSHIRE HATHAWAY INC"},
        "1": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    }
    m = fd.build_cik_map(payload)
    assert m[fd.normalize_ticker("BRK-B")] == 1067983
    assert m[fd.normalize_ticker("BRK.B")] == 1067983
    assert m[fd.normalize_ticker("aapl")] == 320193
    dotted = fd.build_cik_map({"0": {"cik_str": 1, "ticker": "BRK.B", "title": "x"}})
    assert dotted[fd.normalize_ticker("BRK-B")] == 1


def test_parser_handles_missing_concept_and_instant_facts():
    payload = {
        "facts": {
            "us-gaap": {
                "Assets": {
                    "units": {
                        "USD": [
                            {
                                "end": "2020-03-31",
                                "val": 5,
                                "accn": "a-1",
                                "fy": 2020,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2020-05-01",
                                "frame": "CY2020Q1I",
                            }
                        ]
                    }
                }
            }
        }
    }
    df = fd.parse_companyfacts("AAA", payload)
    assert list(df.columns) == fd.FACT_COLUMNS
    assert set(df["concept"]) == {"Assets"}
    assert df["start"].isna().all()
    empty = fd.parse_companyfacts("AAA", {"facts": {}})
    assert empty.empty
    panel = fd.pit_panel(df, "GrossProfit", DATES, ["AAA"])
    assert panel.isna().all().all()
