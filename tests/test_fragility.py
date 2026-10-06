"""Balance-sheet fragility screen (spec docs/superpowers/specs/2026-10-05-fragility-screen-design.md).

Synthetic facts and submissions only; nothing here touches the network.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import urllib.error
from pathlib import Path

import pandas as pd
import pytest
import yaml

from qrl import fragility as fr
from qrl import fundamentals as fd
from qrl import pit_universe as pu

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "fragility.yaml"
ASOF = pd.Timestamp("2025-06-01")
FY_ENDS = ["2020-12-31", "2021-12-31", "2022-12-31", "2023-12-31", "2024-12-31"]  # oldest first
INSTANTS = fr.INSTANT_CONCEPTS

# A healthy company, oldest fiscal year first. Piotroski 9, nothing breaches.
BASE: dict[str, list[float]] = {
    "LongTermDebt": [300, 280, 260, 240, 220],
    "CashAndCashEquivalentsAtCarryingValue": [100] * 5,
    "InterestExpense": [15] * 5,
    "OperatingIncomeLoss": [100] * 5,
    "NetCashProvidedByUsedInOperatingActivities": [90, 95, 100, 105, 110],
    "PaymentsToAcquirePropertyPlantAndEquipment": [30] * 5,
    "LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths": [20] * 5,
    "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo": [20] * 5,
    "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree": [20] * 5,
    "AssetsCurrent": [400] * 5,
    "LiabilitiesCurrent": [300, 290, 280, 270, 260],
    "Assets": [1000] * 5,
    "Liabilities": [500] * 5,
    "RetainedEarningsAccumulatedDeficit": [400] * 5,
    "StockholdersEquity": [500] * 5,
    "NetIncomeLoss": [50, 55, 60, 65, 70],
    "WeightedAverageNumberOfSharesOutstandingBasic": [100] * 5,
    "GrossProfit": [200, 210, 225, 240, 260],
    "Revenues": [500, 520, 540, 560, 580],
}
MAT = "LongTermDebtMaturitiesRepaymentsOfPrincipalIn"


def make_facts(
    values: dict | None = None,
    latest: dict | None = None,
    drop: tuple[str, ...] = (),
    ticker: str = "AAA",
    lag_days: int = 40,
) -> pd.DataFrame:
    """Long facts table for one company; `values` replaces whole series, `latest` the newest
    year only, `drop` removes concepts. Entries of None are skipped."""
    vals = {k: list(v) for k, v in BASE.items()}
    vals.update({k: list(v) for k, v in (values or {}).items()})
    for k, x in (latest or {}).items():
        vals.setdefault(k, [None] * 5)[-1] = x
    for k in drop:
        vals.pop(k, None)
    rows = []
    for concept, series in vals.items():
        for end_s, val in zip(FY_ENDS, series, strict=True):
            if val is None:
                continue
            end = pd.Timestamp(end_s)
            rows.append(
                {
                    "ticker": ticker,
                    "taxonomy": "us-gaap",
                    "concept": concept,
                    "unit": "USD",
                    "start": pd.NaT if concept in INSTANTS else end - pd.Timedelta(days=364),
                    "end": end,
                    "val": float(val),
                    "form": "10-K",
                    "fy": end.year,
                    "fp": "FY",
                    "filed": end + pd.Timedelta(days=lag_days),
                    "accn": "x",
                }
            )
    df = pd.DataFrame(rows, columns=fd.FACT_COLUMNS)
    for col in ("start", "end", "filed"):
        df[col] = df[col].astype("datetime64[ns]")
    return df


def add_fact(df: pd.DataFrame, concept: str, end: str, val: float, filed: str) -> pd.DataFrame:
    row = df[(df["concept"] == concept)].iloc[[-1]].copy()
    row["end"] = pd.Timestamp(end)
    row["start"] = pd.NaT if concept in INSTANTS else pd.Timestamp(end) - pd.Timedelta(days=364)
    row["val"] = float(val)
    row["filed"] = pd.Timestamp(filed)
    return pd.concat([df, row], ignore_index=True)


@pytest.fixture(scope="module")
def cfg() -> fr.FragilityConfig:
    # N = 1 pinned explicitly: these tests predate the N = 2 amendment (2026-10-05)
    return dataclasses.replace(fr.load_fragility_config(CONFIG_PATH)[0], breach_to_fragile=1)


def run(facts: pd.DataFrame, cfg, date=ASOF, sic: int | None = 3571) -> fr.CompanyResult:
    return fr.fragility_as_of("AAA", date, facts, cfg, sic=sic)


# --------------------------------------------------------------------------- measures


def test_healthy_company_is_sound(cfg):
    res = run(make_facts(), cfg)
    assert res.cls == fr.SOUND
    assert res.breached == []
    assert res.fy_end == pd.Timestamp("2024-12-31")
    assert all(m.status == "ok" for m in res.measures.values())
    assert res.measures["piotroski"].value == 9
    assert res.measures["altman_z"].value == pytest.approx(7.2, abs=0.01)
    assert res.measures["net_debt_fcf"].value == pytest.approx(1.5)
    assert res.measures["maturities"].value == pytest.approx(60 / 180)


def test_coverage_breach_and_fallbacks(cfg):
    res = run(make_facts(latest={"InterestExpense": 80}), cfg)
    m = res.measures["coverage"]
    assert m.status == "breach"
    assert m.value == pytest.approx(1.25)
    assert m.detail == "coverage 1.2x < 2.0x"
    # interest falls back to InterestExpenseDebt, then InterestAndDebtExpense
    f = make_facts(drop=("InterestExpense",), latest={"InterestExpenseDebt": 25})
    assert run(f, cfg).measures["coverage"].value == pytest.approx(4.0)
    f = make_facts(drop=("InterestExpense",), latest={"InterestAndDebtExpense": 20})
    assert run(f, cfg).measures["coverage"].value == pytest.approx(5.0)
    # EBIT falls back to pretax income + interest
    pretax = "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"
    f = make_facts(drop=("OperatingIncomeLoss",), latest={pretax: 85})
    assert run(f, cfg).measures["coverage"].value == pytest.approx(100 / 15)


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"latest": {"InterestExpense": 0}}, "interest expense <= 0"),
        ({"latest": {"InterestExpense": -5}}, "interest expense <= 0"),
        ({"drop": ("InterestExpense",)}, "missing interest expense"),
        ({"drop": ("OperatingIncomeLoss",)}, "missing EBIT"),
    ],
)
def test_coverage_unavailable(cfg, kwargs, reason):
    m = run(make_facts(**kwargs), cfg).measures["coverage"]
    assert m.status == "n/a"
    assert reason in m.display


def test_debt_reported_as_zero_is_no_debt_not_breach(cfg):
    res = run(make_facts(latest={"LongTermDebt": 0, "InterestExpense": 0}), cfg)
    for key in ("coverage", "net_debt_fcf", "rate_trend"):
        assert res.measures[key].status == "ok"
        assert res.measures[key].display == "no debt"


def test_debt_and_cash_concept_fallbacks(cfg):
    f = make_facts(
        drop=("LongTermDebt",),
        latest={
            "LongTermDebtNoncurrent": 200,
            "LongTermDebtCurrent": 20,
            "ShortTermBorrowings": 10,
            "ShortTermInvestments": 50,
        },
    )
    # debt 230, cash 150, FCF 80
    assert run(f, cfg).measures["net_debt_fcf"].value == pytest.approx(80 / 80)
    # a missing current portion is not assumed zero
    f = make_facts(drop=("LongTermDebt",), latest={"LongTermDebtNoncurrent": 220})
    assert run(f, cfg).measures["net_debt_fcf"].status == "n/a"
    # MarketableSecuritiesCurrent stands in for ShortTermInvestments
    f = make_facts(latest={"MarketableSecuritiesCurrent": 20})
    assert run(f, cfg).measures["net_debt_fcf"].value == pytest.approx((220 - 120) / 80)


def test_net_debt_to_fcf_cases(cfg):
    net_cash = run(make_facts(latest={"CashAndCashEquivalentsAtCarryingValue": 500}), cfg)
    assert net_cash.measures["net_debt_fcf"].display == "net cash"
    assert net_cash.measures["net_debt_fcf"].status == "ok"
    neg = run(make_facts(latest={"NetCashProvidedByUsedInOperatingActivities": 20}), cfg)
    assert neg.measures["net_debt_fcf"].status == "breach"
    assert neg.measures["net_debt_fcf"].display == "FCF <= 0"
    at_six = run(make_facts(latest={"NetCashProvidedByUsedInOperatingActivities": 50}), cfg)
    assert at_six.measures["net_debt_fcf"].value == pytest.approx(6.0)
    assert at_six.measures["net_debt_fcf"].status == "ok"
    over = run(make_facts(latest={"NetCashProvidedByUsedInOperatingActivities": 49}), cfg)
    assert over.measures["net_debt_fcf"].status == "breach"
    # capex falls back to PaymentsToAcquireProductiveAssets
    f = make_facts(
        drop=("PaymentsToAcquirePropertyPlantAndEquipment",),
        latest={"PaymentsToAcquireProductiveAssets": 30},
    )
    assert run(f, cfg).measures["net_debt_fcf"].value == pytest.approx(1.5)


def test_maturities_cases(cfg):
    at_one = run(make_facts(latest={MAT + "NextTwelveMonths": 140}), cfg)  # 180 / 180
    assert at_one.measures["maturities"].value == pytest.approx(1.0)
    assert at_one.measures["maturities"].status == "ok"
    over = run(make_facts(latest={MAT + "NextTwelveMonths": 141}), cfg)
    assert over.measures["maturities"].status == "breach"
    no_liq = run(
        make_facts(
            latest={
                "CashAndCashEquivalentsAtCarryingValue": 0,
                "NetCashProvidedByUsedInOperatingActivities": 20,
            }
        ),
        cfg,
    )
    assert no_liq.measures["maturities"].status == "breach"
    missing = run(make_facts(drop=(MAT + "YearTwo",)), cfg)
    assert missing.measures["maturities"].status == "n/a"
    none_due = run(
        make_facts(
            latest={
                MAT + "NextTwelveMonths": 0,
                MAT + "YearTwo": 0,
                MAT + "YearThree": 0,
                "CashAndCashEquivalentsAtCarryingValue": 0,
                "NetCashProvidedByUsedInOperatingActivities": 20,
            }
        ),
        cfg,
    )
    assert none_due.measures["maturities"].status == "ok"


def test_rate_trend_cases(cfg):
    r3 = 15 / 290  # rate three fiscal years earlier
    base = run(make_facts(), cfg).measures["rate_trend"]
    assert base.value == pytest.approx((15 / 230 - r3) * 100)
    just_under = run(make_facts(latest={"InterestExpense": (r3 + 0.019) * 230}), cfg)
    assert just_under.measures["rate_trend"].status == "ok"
    just_over = run(make_facts(latest={"InterestExpense": (r3 + 0.021) * 230}), cfg)
    assert just_over.measures["rate_trend"].status == "breach"
    assert just_over.measures["rate_trend"].display.endswith("pp")
    short = make_facts(values={"LongTermDebt": [None, 280, 260, 240, 220]})
    assert run(short, cfg).measures["rate_trend"].status == "n/a"
    no_int = make_facts(values={"InterestExpense": [15, None, 15, 15, 15]})
    assert run(no_int, cfg).measures["rate_trend"].status == "n/a"


CASH_TAG = "CashAndCashEquivalentsAtCarryingValue"


@pytest.mark.parametrize(
    ("cash", "status"),
    [
        (300, "ok"),  # net cash (-8% of assets)
        (190, "ok"),  # net debt 3% of assets
        (170, "ok"),  # net debt exactly 5% of assets
        (20, "breach"),  # net debt 20% of assets: old behaviour
    ],
)
def test_rate_trend_skipped_on_little_net_debt(cfg, cash, status):
    res = run(make_facts(latest={"InterestExpense": 80, CASH_TAG: cash}), cfg)
    m = res.measures["rate_trend"]
    assert m.status == status
    if status == "ok":
        assert "little net debt" in m.display
        assert "rate_trend" not in res.breached
    else:
        assert m.display.endswith("pp")
        assert "rate_trend" in res.breached


def test_rate_trend_skip_counts_as_available(cfg):
    # fiscal-year history too short for the normal calculation, yet little net debt
    short = make_facts(values={"LongTermDebt": [None, 280, 260, 240, 220]}, latest={CASH_TAG: 300})
    assert run(short, cfg).measures["rate_trend"].status == "ok"


def test_rate_trend_missing_assets_falls_back(cfg):
    f = make_facts(drop=("Assets",), latest={"InterestExpense": 80, CASH_TAG: 300})
    assert run(f, cfg).measures["rate_trend"].status == "breach"
    f = make_facts(drop=(CASH_TAG,), latest={"InterestExpense": 80})
    assert run(f, cfg).measures["rate_trend"].status == "breach"


def test_rate_trend_gate_config_loads(tmp_path):
    assert fr.load_fragility_config(CONFIG_PATH)[0].rate_trend_min_net_debt_to_assets == 0.05
    path = _write_cfg(tmp_path, rate_trend_min_net_debt_to_assets=0.1)
    assert fr.load_fragility_config(path)[0].rate_trend_min_net_debt_to_assets == 0.1
    with pytest.raises(ValueError, match="missing keys"):
        fr.load_fragility_config(_write_cfg(tmp_path, drop=("rate_trend_min_net_debt_to_assets",)))


def test_altman_cases(cfg):
    breach = run(make_facts(latest={"RetainedEarningsAccumulatedDeficit": -1500}), cfg)
    assert breach.measures["altman_z"].status == "breach"
    assert breach.measures["altman_z"].value < 1.1
    # Liabilities falls back to Assets - StockholdersEquity
    f = make_facts(drop=("Liabilities",))
    assert run(f, cfg).measures["altman_z"].value == pytest.approx(7.2, abs=0.01)
    f = make_facts(drop=("Liabilities", "StockholdersEquity"))
    assert run(f, cfg).measures["altman_z"].status == "n/a"
    # unclassified balance sheet: no AssetsCurrent
    assert run(make_facts(drop=("AssetsCurrent",)), cfg).measures["altman_z"].status == "n/a"


def test_piotroski_cases(cfg):
    weak = dataclasses.replace(cfg, piotroski_max_weak=9)
    assert run(make_facts(), weak).measures["piotroski"].status == "breach"
    strong = dataclasses.replace(cfg, piotroski_max_weak=8)
    assert run(make_facts(), strong).measures["piotroski"].status == "ok"
    # one fiscal year only: no prior year, no score (never a partial score)
    one_year = {k: [None] * 4 + [v[-1]] for k, v in BASE.items()}
    assert run(make_facts(values=one_year), cfg).measures["piotroski"].status == "n/a"
    # a lost signal input (no gross profit, no cost of revenue) voids the whole score
    assert run(make_facts(drop=("GrossProfit",)), cfg).measures["piotroski"].status == "n/a"


def test_piotroski_gross_profit_from_revenue_minus_cost(cfg):
    f = make_facts(
        drop=("GrossProfit",),
        values={"CostOfRevenue": [300, 310, 315, 320, 320]},
    )  # gross margin 0.4, 0.404, 0.417, 0.43, 0.448: rising
    assert run(f, cfg).measures["piotroski"].value == 9


def test_piotroski_counts_signals(cfg):
    f = make_facts(
        values={"WeightedAverageNumberOfSharesOutstandingBasic": [100, 100, 100, 100, 110]}
    )
    assert run(f, cfg).measures["piotroski"].value == 8  # shares rose: one signal lost


@pytest.mark.parametrize(
    ("key", "field", "lower_bound"),
    [
        ("coverage", "interest_coverage_min", True),
        ("net_debt_fcf", "net_debt_to_fcf_max", False),
        ("maturities", "maturities_to_liquidity_max", False),
        ("rate_trend", "rate_rise_max_pp", False),
        ("altman_z", "altman_z_min", True),
    ],
)
def test_value_exactly_at_threshold_is_not_a_breach(cfg, key, field, lower_bound):
    value = run(make_facts(), cfg).measures[key].value
    assert value is not None
    at = run(make_facts(), dataclasses.replace(cfg, **{field: value})).measures[key]
    assert at.status == "ok"
    eps = 1e-9
    past = value + eps if lower_bound else value - eps
    assert run(make_facts(), dataclasses.replace(cfg, **{field: past})).measures[key].status == (
        "breach"
    )


# --------------------------------------------------------------------------- classification


def _measures(breaches: int, available: int) -> dict[str, fr.Measure]:
    out = {}
    for i, key in enumerate(fr.MEASURE_KEYS):
        if i < breaches:
            out[key] = fr.Measure("breach", "x", 1.0, "d")
        elif i < available:
            out[key] = fr.Measure("ok", "x", 1.0)
        else:
            out[key] = fr.Measure("n/a", "n/a (r)")
    return out


@pytest.mark.parametrize(
    ("breaches", "available", "expected"),
    [
        (0, 6, fr.SOUND),
        (0, 4, fr.SOUND),  # K available
        (0, 3, fr.INSUFFICIENT),  # K - 1 available
        (0, 0, fr.INSUFFICIENT),
        (1, 6, fr.FRAGILE),  # N = 1: the single breach flags it
        (1, 1, fr.FRAGILE),  # a breach is evidence even when the rest is a gap
        (2, 6, fr.FRAGILE),  # N + 1
    ],
)
def test_classify_with_n_equal_1(cfg, breaches, available, expected):
    assert cfg.breach_to_fragile == 1
    assert fr.classify(_measures(breaches, max(available, breaches)), cfg) == expected


@pytest.mark.parametrize(
    ("breaches", "available", "expected"),
    [
        (0, 4, fr.SOUND),
        (0, 3, fr.INSUFFICIENT),
        (1, 6, fr.WATCH),  # N - 1
        (1, 1, fr.WATCH),
        (2, 2, fr.FRAGILE),  # N, though most measures are gaps
        (3, 6, fr.FRAGILE),  # N + 1
    ],
)
def test_classify_with_n_equal_2(cfg, breaches, available, expected):
    two = dataclasses.replace(cfg, breach_to_fragile=2)
    assert fr.classify(_measures(breaches, max(available, breaches)), two) == expected


def test_watch_is_empty_at_n1_and_covers_below_n(cfg):
    for b in range(1, 7):
        assert fr.classify(_measures(b, 6), cfg) == fr.FRAGILE
    three = dataclasses.replace(cfg, breach_to_fragile=3)
    assert [
        fr.classify(_named(*keys), three)
        for keys in (
            ("coverage",),
            ("coverage", "rate_trend"),
            ("coverage", "rate_trend", "altman_z"),
        )
    ] == [fr.WATCH, fr.WATCH, fr.FRAGILE]


def test_fcf_pair_makes_three_ordered_breaches_count_two(cfg):
    three = dataclasses.replace(cfg, breach_to_fragile=3)
    assert fr.classify(_measures(3, 6), three) == fr.WATCH


def test_company_with_breach_is_fragile_and_lists_it(cfg):
    res = run(make_facts(latest={"InterestExpense": 80}), cfg)
    assert res.cls == fr.FRAGILE
    assert "coverage" in res.breached
    two = dataclasses.replace(cfg, breach_to_fragile=2)
    # interest 80 also lifts the effective rate by far more than 2 pp: two breaches
    assert run(make_facts(latest={"InterestExpense": 80}), two).cls == fr.FRAGILE
    only_one = run(make_facts(latest={"InterestExpense": 45}), two)  # coverage 2.2x ok, rate up
    assert only_one.breached == ["rate_trend"]
    assert only_one.cls == fr.WATCH


# --------------------------------------------------------------------------- industry


@pytest.mark.parametrize(
    ("sic", "expected"), [(6000, True), (6021, True), (6799, True), (5999, False), (6800, False)]
)
def test_financial_firms_by_sic_range(cfg, sic, expected):
    res = run(make_facts(latest={"InterestExpense": 80}), cfg, sic=sic)
    assert (res.cls == fr.NOT_APPLICABLE) is expected
    if expected:
        assert all(m.display == "NOT APPLICABLE" for m in res.measures.values())
        assert res.breached == []


def test_override_list_and_unknown_sic(cfg):
    over = dataclasses.replace(cfg, not_applicable_tickers=("AAA",))
    assert run(make_facts(), over, sic=None).cls == fr.NOT_APPLICABLE
    assert run(make_facts(), over, sic=3571).cls == fr.NOT_APPLICABLE
    unknown = run(make_facts(latest={"InterestExpense": 80}), cfg, sic=None)
    assert unknown.cls == fr.INSUFFICIENT
    assert "industry unknown" in unknown.note


def test_no_facts_is_insufficient_not_dropped(cfg):
    empty = pd.DataFrame(columns=fd.FACT_COLUMNS)
    res = run(empty, cfg)
    assert res.cls == fr.INSUFFICIENT
    assert all(m.status == "n/a" for m in res.measures.values())
    assert res.fy_end is None


# --------------------------------------------------------------------------- point in time


def test_filing_on_or_after_as_of_is_ignored(cfg):
    filed = pd.Timestamp("2024-12-31") + pd.Timedelta(days=40)  # 2025-02-09
    on_day = run(make_facts(), cfg, date=filed)
    assert on_day.fy_end == pd.Timestamp("2023-12-31")
    next_day = run(make_facts(), cfg, date=filed + pd.Timedelta(days=1))
    assert next_day.fy_end == pd.Timestamp("2024-12-31")
    before = run(make_facts(), cfg, date=pd.Timestamp("2025-01-15"))
    assert before.fy_end == pd.Timestamp("2023-12-31")


def test_restatement_counts_only_once_filed(cfg):
    f = add_fact(make_facts(), "InterestExpense", "2024-12-31", 80, "2025-08-01")
    assert run(f, cfg, date=pd.Timestamp("2025-06-01")).measures["coverage"].status == "ok"
    assert run(f, cfg, date=pd.Timestamp("2025-08-01")).measures["coverage"].status == "ok"
    later = run(f, cfg, date=pd.Timestamp("2025-08-02"))
    assert later.measures["coverage"].status == "breach"
    assert later.measures["coverage"].value == pytest.approx(1.25)


def test_stale_data_is_unavailable(cfg):
    res = run(make_facts(), cfg, date=pd.Timestamp("2026-06-01"))  # 517 days after FY end
    assert res.cls == fr.INSUFFICIENT
    assert all(m.status == "n/a" for m in res.measures.values())
    edge = run(make_facts(), cfg, date=pd.Timestamp("2024-12-31") + pd.Timedelta(days=456))
    assert edge.fy_end == pd.Timestamp("2024-12-31")
    gone = run(make_facts(), cfg, date=pd.Timestamp("2024-12-31") + pd.Timedelta(days=457))
    assert gone.fy_end is None


def test_other_tickers_facts_are_ignored(cfg):
    mixed = pd.concat(
        [make_facts(latest={"InterestExpense": 80}, ticker="BBB"), make_facts()],
        ignore_index=True,
    )
    assert run(mixed, cfg).cls == fr.SOUND


# --------------------------------------------------------------------------- config


def _write_cfg(tmp_path: Path, drop: tuple[str, ...] = (), **changes) -> Path:
    raw = yaml.safe_load(CONFIG_PATH.read_text())
    raw.update(changes)
    for k in drop:
        raw.pop(k)
    path = tmp_path / "fragility.yaml"
    path.write_text(yaml.safe_dump(raw))
    return path


def test_shipped_config_loads():
    cfg, sha = fr.load_fragility_config(CONFIG_PATH)
    assert sha == pu.file_sha256(CONFIG_PATH)
    assert cfg.breach_to_fragile == 2
    assert cfg.min_available_for_sound == 4
    assert cfg.interest_coverage_min == 2.0
    assert cfg.net_debt_to_fcf_max == 6.0
    assert cfg.maturities_to_liquidity_max == 1.0
    assert cfg.altman_z_min == 1.1
    assert cfg.piotroski_max_weak == 2
    assert cfg.rate_rise_max_pp == 2.0
    assert cfg.not_applicable_sic == ((6000, 6799),)
    assert cfg.not_applicable_tickers == ()
    text = CONFIG_PATH.read_text()
    assert text.startswith("# PRE-REGISTERED")
    assert 'date: "2026-10-05"' in text
    assert "decided_by: owner" in text


@pytest.mark.parametrize(
    "changes",
    [
        {"version": 2},
        {"interest_coverage_min": "x"},
        {"interest_coverage_min": 0},
        {"net_debt_to_fcf_max": -1},
        {"maturities_to_liquidity_max": True},
        {"altman_z_min": 0},
        {"piotroski_max_weak": 0},
        {"rate_rise_max_pp": 0},
        {"breach_to_fragile": 0},
        {"breach_to_fragile": 7},
        {"breach_to_fragile": 1.5},
        {"min_available_for_sound": 0},
        {"min_available_for_sound": 7},
        {"not_applicable_sic": [[6000]]},
        {"not_applicable_sic": [[6799, 6000]]},
        {"not_applicable_sic": [["a", "b"]]},
        {"not_applicable_sic": "6000-6799"},
        {"not_applicable_tickers": ["X", "X"]},
        {"not_applicable_tickers": ["X", "x"]},
        {"not_applicable_tickers": [1]},
        {"not_applicable_tickers": "X"},
        {"surprise": 1},
    ],
)
def test_config_rejections(tmp_path, changes):
    with pytest.raises(ValueError, match=r"."):
        fr.load_fragility_config(_write_cfg(tmp_path, **changes))


@pytest.mark.parametrize("key", ["version", "altman_z_min", "not_applicable_sic", "decided_by"])
def test_config_missing_key_rejected(tmp_path, key):
    with pytest.raises(ValueError, match=key):
        fr.load_fragility_config(_write_cfg(tmp_path, drop=(key,)))


def test_config_accepts_n_in_range(tmp_path):
    for n in (1, 6):
        assert (
            fr.load_fragility_config(_write_cfg(tmp_path, breach_to_fragile=n))[0].breach_to_fragile
            == n
        )


# --------------------------------------------------------------------------- loaders


def payload_from(df: pd.DataFrame) -> dict:
    units: dict[str, dict] = {}
    for r in df.itertuples():
        item = {
            "end": r.end.strftime("%Y-%m-%d"),
            "val": r.val,
            "form": "10-K",
            "fy": r.end.year,
            "fp": "FY",
            "filed": r.filed.strftime("%Y-%m-%d"),
            "accn": "x",
        }
        if pd.notna(r.start):
            item["start"] = r.start.strftime("%Y-%m-%d")
        units.setdefault(r.concept, {"units": {"USD": []}})["units"]["USD"].append(item)
    return {"facts": {"us-gaap": units}}


def write_payload(sec_dir: Path, cik: int, df: pd.DataFrame) -> None:
    path = sec_dir / "facts" / f"CIK{cik:010d}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload_from(df)))


def write_pool(path: Path, ciks: dict[str, int]) -> None:
    pd.DataFrame({"ticker": list(ciks), "cik": list(ciks.values())}).to_csv(path, index=False)


def test_load_fragility_facts_reads_cache_and_stitches_predecessor(tmp_path, monkeypatch):
    sec = tmp_path / "sec"
    write_payload(sec, 1, make_facts())
    old = make_facts(values={"InterestExpense": [9] * 5})
    old = old[old["end"] < "2021-06-01"].assign(
        filed=lambda d: d["filed"] - pd.Timedelta(days=2000)
    )
    write_payload(sec, 2, old)
    pool = tmp_path / "pool.csv"
    write_pool(pool, {"AAA": 1, "BBB": 5})
    monkeypatch.setitem(pu.CIK_PREDECESSORS, "AAA", [2])
    facts = fr.load_fragility_facts(["AAA", "BBB"], pool_path=pool, sec_dir=sec)
    assert set(facts["ticker"]) == {"AAA"}  # BBB has no cached payload: absent, not an error
    assert "InterestExpense" in set(facts["concept"])
    assert facts["filed"].min() < pd.Timestamp("2020-01-01")  # predecessor history merged
    only_new = fr.load_fragility_facts(["AAA"], pool_path=pool, sec_dir=tmp_path / "empty")
    assert only_new.empty
    assert list(only_new.columns) == fd.FACT_COLUMNS


def test_load_sic_cache_only_then_fetch(tmp_path):
    sec = tmp_path / "sec"
    assert fr.load_sic(7, sec, fetch=None) is None  # cache only: no cache, no fetch
    calls: list[str] = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        return json.dumps({"cik": "7", "sic": "3571"}).encode()

    assert fr.load_sic(7, sec, fetch=fetch) == 3571
    assert calls == ["https://data.sec.gov/submissions/CIK0000000007.json"]
    assert (sec / "submissions" / "CIK0000000007.json").exists()
    assert fr.load_sic(7, sec, fetch=None) == 3571  # now cached
    assert len(calls) == 1


def test_load_sic_missing_or_blank_is_none(tmp_path):
    def not_found(url: str) -> bytes:
        raise urllib.error.HTTPError(url, 404, "nf", None, None)  # type: ignore[arg-type]

    assert fr.load_sic(8, tmp_path, fetch=not_found) is None
    blank = lambda url: json.dumps({"sic": ""}).encode()  # noqa: E731
    assert fr.load_sic(9, tmp_path, fetch=blank) is None


# --------------------------------------------------------------------------- universe filter


def _membership() -> pd.DataFrame:
    rows = [("2025-04-30", t) for t in ("AAA", "BBB")] + [
        ("2025-05-31", t) for t in ("AAA", "CCC", "DDD")
    ]
    return pd.DataFrame(
        {"month_end": pd.to_datetime([r[0] for r in rows]), "ticker": [r[1] for r in rows]}
    )


def _universe_facts() -> pd.DataFrame:
    return pd.concat(
        [
            make_facts(ticker="AAA"),  # sound
            make_facts(latest={"InterestExpense": 80}, ticker="BBB"),  # fragile, April only
            make_facts(latest={"InterestExpense": 80}, ticker="CCC"),  # fragile
            make_facts(latest={"InterestExpense": 80}, ticker="DDD"),  # fragile but a bank
        ],
        ignore_index=True,
    )


def test_members_as_of_uses_latest_month_end_strictly_before():
    m = _membership()
    assert fr.members_as_of(m, pd.Timestamp("2025-06-01")) == (
        pd.Timestamp("2025-05-31"),
        ["AAA", "CCC", "DDD"],
    )
    assert fr.members_as_of(m, pd.Timestamp("2025-05-31"))[0] == pd.Timestamp("2025-04-30")
    assert fr.members_as_of(m, pd.Timestamp("2025-04-30")) == (None, [])


def test_excluded_tickers_only_fragile_and_right_month_end(cfg):
    sics = {"AAA": 3571, "BBB": 3571, "CCC": 3571, "DDD": 6021}
    facts = _universe_facts()
    assert fr.excluded_tickers(ASOF, _membership(), facts, cfg, sics) == {"CCC"}
    # on 2025-05-31 the April month-end applies: BBB is a member, CCC is not yet
    assert fr.excluded_tickers(pd.Timestamp("2025-05-31"), _membership(), facts, cfg, sics) == {
        "BBB"
    }
    assert fr.excluded_tickers(pd.Timestamp("2025-04-30"), _membership(), facts, cfg, sics) == set()
    two = dataclasses.replace(cfg, breach_to_fragile=2)
    only_coverage = make_facts(latest={"InterestExpense": 45}, ticker="CCC")
    assert fr.excluded_tickers(ASOF, _membership(), only_coverage, two, sics) == set()


# --------------------------------------------------------------------------- report


def _report(cfg, facts=None):
    facts = _universe_facts() if facts is None else facts
    sics = {"AAA": 3571, "CCC": 3571, "DDD": 6021}  # member with no SIC: none here
    members = ["AAA", "CCC", "DDD", "EEE"]
    results = fr.screen(ASOF, members, facts, sics, cfg)
    return fr.build_report(
        results,
        as_of=ASOF,
        month_end=pd.Timestamp("2025-05-31"),
        facts=facts,
        cfg=cfg,
        config_sha256="a" * 64,
        universe_sha256="b" * 64,
    )


def test_markdown_is_deterministic_and_lists_every_member(cfg):
    report = _report(cfg)
    md = fr.render_markdown(report)
    assert md == fr.render_markdown(_report(cfg))
    assert "- as-of date: 2025-06-01" in md
    assert "- membership month-end: 2025-05-31" in md
    assert "- universe size: 4" in md
    assert "- newest filing date seen: 2025-02-09" in md
    assert f"- config/fragility.yaml sha256: `{'a' * 64}`" in md
    assert f"- universe membership sha256: `{'b' * 64}`" in md
    assert "- breach_to_fragile (N): 1" in md
    assert "- min_available_for_sound (K): 4" in md
    sections = md.split("## ")
    names = [s.splitlines()[0] for s in sections[1:]]
    assert names == ["Summary", "Fragile and watch", "All companies"]
    all_rows = [ln for ln in sections[3].splitlines() if ln.startswith("| ")][2:]
    assert [ln.split("|")[1].strip() for ln in all_rows] == ["CCC", "AAA", "EEE", "DDD"]
    fragile = [ln for ln in sections[2].splitlines() if ln.startswith("| ")][2:]
    assert len(fragile) == 1
    assert "coverage 1.2x < 2.0x" in fragile[0]
    assert "2024-12-31" in fragile[0]
    summary = sections[1]
    assert "| WATCH | 0 |" in summary  # empty at N = 1, row still rendered
    assert "| FRAGILE | 1 |" in summary
    assert "| SOUND | 1 |" in summary
    assert "| INSUFFICIENT DATA | 1 |" in summary  # EEE: no facts
    assert "| NOT APPLICABLE | 1 |" in summary
    assert "n/a (" in sections[3]
    assert "NOT APPLICABLE" in sections[3]


def test_markdown_renders_fragile_and_watch_with_empty_watch(cfg):
    md = fr.render_markdown(_report(cfg, facts=make_facts(ticker="AAA")))
    section = md.split("## Fragile and watch")[1].split("##")[0]
    rows = [ln for ln in section.splitlines() if ln.startswith("|")]
    assert len(rows) == 2  # header and separator only


def test_report_json_carries_raw_inputs(cfg):
    report = _report(cfg)
    row = next(c for c in report["companies"] if c["ticker"] == "CCC")
    assert row["class"] == fr.FRAGILE
    assert row["inputs"]["InterestExpense@2024-12-31"] == 80
    assert row["measures"]["coverage"]["status"] == "breach"
    json.dumps(report, default=str)


# --------------------------------------------------------------------------- CLI


def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "fragility_cli", ROOT / "scripts" / "fragility.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cli = _load_cli()


@pytest.fixture
def world(tmp_path):
    """A tmp SEC cache, pool.csv and PIT universe for AAA (sound) and BBB (fragile)."""
    sec = tmp_path / "sec"
    write_payload(sec, 1, make_facts(ticker="AAA"))
    write_payload(sec, 2, make_facts(latest={"InterestExpense": 80}, ticker="BBB"))
    for cik in (1, 2):
        sub = sec / "submissions" / f"CIK{cik:010d}.json"
        sub.parent.mkdir(parents=True, exist_ok=True)
        sub.write_text(json.dumps({"sic": "3571"}))
    pool = tmp_path / "pool.csv"
    write_pool(pool, {"AAA": 1, "BBB": 2, "ZZZ": 3})
    membership = pd.DataFrame(
        {
            "month_end": ["2025-01-31"] * 2 + ["2025-04-30"] * 3,
            "ticker": ["AAA", "BBB", "AAA", "BBB", "ZZZ"],
            "market_cap": 1,
            "rank": 1,
            "source": "",
        }
    )
    csv = tmp_path / "members.csv"
    membership.to_csv(csv, index=False)
    uni = tmp_path / "universe.yaml"
    uni.write_text(
        yaml.safe_dump(
            {
                "name": "t",
                "survivorship_biased": True,
                "membership_file": str(csv),
                "membership_sha256": pu.file_sha256(csv),
                "top_n": 3,
            }
        )
    )
    return {
        "sec": sec,
        "pool": pool,
        "uni": uni,
        "out_md": tmp_path / "f.md",
        "out_json": tmp_path / "f.json",
    }


def _args(w, *extra):
    return [
        "--sec-dir", str(w["sec"]),
        "--pool", str(w["pool"]),
        "--universe", str(w["uni"]),
        "--out-md", str(w["out_md"]),
        "--out-json", str(w["out_json"]),
        *extra,
    ]  # fmt: skip


@pytest.fixture
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network attempted")

    monkeypatch.setattr(fd, "_http_get", boom)


def test_cli_writes_both_outputs_without_fetching(world, no_network):
    assert cli.main(_args(world, "--as-of", "2025-06-01")) == 0
    md = world["out_md"].read_text()
    assert "- as-of date: 2025-06-01" in md
    assert "- membership month-end: 2025-04-30" in md
    assert "- universe size: 3" in md
    assert "| BBB | FRAGILE |" in md
    assert "| AAA | SOUND |" in md
    assert "| ZZZ | INSUFFICIENT DATA |" in md  # no cached facts: still listed
    data = json.loads(world["out_json"].read_text())
    assert {c["ticker"] for c in data["companies"]} == {"AAA", "BBB", "ZZZ"}
    assert data["as_of"] == "2025-06-01"


def test_cli_as_of_is_honoured(world, no_network):
    assert cli.main(_args(world, "--as-of", "2025-02-09")) == 0  # FY2024 filed ON this day
    md = world["out_md"].read_text()
    assert "- membership month-end: 2025-01-31" in md
    assert "- universe size: 2" in md
    assert "2023-12-31" in md
    assert "2024-12-31" not in md
    assert "- newest filing date seen: 2024-02-09" in md


def test_cli_refresh_facts_refetches_every_member(world, monkeypatch):
    monkeypatch.setenv(fd.EMAIL_ENV_VAR, "t@example.com")
    newer = add_fact(make_facts(ticker="AAA"), "InterestExpense", "2024-12-31", 15, "2025-03-01")
    body = json.dumps(payload_from(newer)).encode()
    calls: list[tuple[str, str]] = []

    def stub(url, ua):
        calls.append((url, ua))
        fd._validate_url(url)  # the real allowlist
        return body

    monkeypatch.setattr(fd, "_http_get", stub)
    assert cli.main(_args(world, "--as-of", "2025-06-01", "--refresh-facts")) == 0
    urls = {u for u, _ in calls}
    assert urls == {fd.FACTS_URL.format(cik=c) for c in (1, 2, 3)}  # every member, once
    assert {ua for _, ua in calls} == {"quant-research-lab t@example.com"}
    assert (world["sec"] / "facts" / "CIK0000000001.json").read_bytes() == body
    assert "- newest filing date seen: 2025-03-01" in world["out_md"].read_text()


def test_cli_fetch_sic_uses_stub_and_caches(world, monkeypatch):
    monkeypatch.setenv(fd.EMAIL_ENV_VAR, "t@example.com")
    for p in (world["sec"] / "submissions").iterdir():
        p.unlink()
    calls: list[str] = []

    def stub(url, ua):
        calls.append(url)
        fd._validate_url(url)
        return json.dumps({"sic": "6021"}).encode()

    monkeypatch.setattr(fd, "_http_get", stub)
    assert cli.main(_args(world, "--as-of", "2025-06-01", "--fetch-sic")) == 0
    assert all(u.startswith("https://data.sec.gov/submissions/CIK") for u in calls)
    assert (world["sec"] / "submissions" / "CIK0000000001.json").exists()
    assert "| AAA | NOT APPLICABLE |" in world["out_md"].read_text()
    assert not any("companyfacts" in u for u in calls)  # no --refresh-facts: no facts fetch


def test_cli_without_sic_cache_marks_industry_unknown(world, no_network):
    for p in (world["sec"] / "submissions").iterdir():
        p.unlink()
    assert cli.main(_args(world, "--as-of", "2025-06-01")) == 0
    md = world["out_md"].read_text()
    assert "| AAA | INSUFFICIENT DATA |" in md
    assert "industry unknown" in md


# --------------------------------------------------------------------------- amendments


def test_ten_q_twelve_month_flow_does_not_anchor_fiscal_year(cfg):
    f = make_facts()
    for concept in ("NetCashProvidedByUsedInOperatingActivities", "NetIncomeLoss"):
        f = add_fact(f, concept, "2025-03-31", 99, "2025-05-01")
        f.loc[f.index[-1], "form"] = "10-Q"
    res = run(f, cfg)
    assert res.fy_end == pd.Timestamp("2024-12-31")


def test_fy_end_value_supplied_only_by_ten_q_is_used(cfg):
    f = make_facts()
    mask = (f["concept"] == "LongTermDebt") & (f["end"] == pd.Timestamp("2024-12-31"))
    f.loc[mask, "form"] = "10-Q"
    f.loc[mask, "filed"] = pd.Timestamp("2025-03-01")
    res = run(f, cfg)
    assert res.fy_end == pd.Timestamp("2024-12-31")
    assert res.measures["net_debt_fcf"].status != "n/a"


def test_twelve_month_flow_supplied_only_by_proxy_is_used():
    f = make_facts()
    mask = (f["concept"] == "NetIncomeLoss") & (f["end"] == pd.Timestamp("2024-12-31"))
    f.loc[mask, "form"] = "DEF 14A"
    f.loc[mask, "filed"] = pd.Timestamp("2025-03-01")
    view = fr._View(f, "AAA", ASOF)
    assert view.get(["NetIncomeLoss"], pd.Timestamp("2024-12-31")) == 70.0
    assert pd.Timestamp("2024-12-31") in view.fiscal_ends()


def test_company_with_only_ten_q_anchors_has_no_fiscal_year(cfg):
    f = make_facts()
    f["form"] = "10-Q"
    res = run(f, cfg)
    assert res.cls == fr.INSUFFICIENT
    assert res.fy_end is None


def test_annual_forms_include_foreign_filers():
    assert {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"} == set(fr.ANNUAL_FORMS)


def _later_filing(f, concept, val, form, filed="2025-04-01", end="2024-12-31"):
    f = add_fact(f, concept, end, val, filed)
    f.loc[f.index[-1], "form"] = form
    return f


def test_annual_report_flow_beats_later_ten_q_with_same_period():
    f = _later_filing(make_facts(), "OperatingIncomeLoss", 7, "10-Q")
    view = fr._View(f, "AAA", ASOF)
    assert view.get(["OperatingIncomeLoss"], pd.Timestamp("2024-12-31")) == 100.0


def test_annual_report_instant_beats_later_ten_q_comparative():
    f = _later_filing(make_facts(), "LongTermDebt", 1.0, "10-Q")
    view = fr._View(f, "AAA", ASOF)
    assert view.get(["LongTermDebt"], pd.Timestamp("2024-12-31")) == 220.0


def test_later_ten_k_a_beats_earlier_ten_k():
    f = _later_filing(make_facts(), "OperatingIncomeLoss", 250, "10-K/A")
    view = fr._View(f, "AAA", ASOF)
    assert view.get(["OperatingIncomeLoss"], pd.Timestamp("2024-12-31")) == 250.0


def test_later_ten_q_does_not_beat_ten_k_a_over_ten_k():
    f = _later_filing(make_facts(), "OperatingIncomeLoss", 250, "10-K/A", filed="2025-03-01")
    f = _later_filing(f, "OperatingIncomeLoss", 7, "10-Q", filed="2025-04-15")
    view = fr._View(f, "AAA", ASOF)
    assert view.get(["OperatingIncomeLoss"], pd.Timestamp("2024-12-31")) == 250.0


def _named(*breached: str) -> dict[str, fr.Measure]:
    return {
        key: fr.Measure("breach", "x", 1.0, "d") if key in breached else fr.Measure("ok", "x", 1.0)
        for key in fr.MEASURE_KEYS
    }


@pytest.mark.parametrize(
    ("breached", "expected"),
    [
        (("net_debt_fcf", "maturities"), fr.WATCH),  # FCF pair counts once
        (("net_debt_fcf", "coverage"), fr.FRAGILE),
        (("maturities", "coverage"), fr.FRAGILE),
        (("net_debt_fcf", "maturities", "coverage"), fr.FRAGILE),
        (("net_debt_fcf",), fr.WATCH),
        (("coverage", "altman_z"), fr.FRAGILE),
    ],
)
def test_fcf_pair_counts_as_one_breach(cfg, breached, expected):
    two = dataclasses.replace(cfg, breach_to_fragile=2)
    assert fr.classify(_named(*breached), two) == expected


def test_shipped_config_is_n2():
    assert fr.load_fragility_config(CONFIG_PATH)[0].breach_to_fragile == 2


def test_missing_maturities_use_friendly_labels(cfg):
    f = make_facts(drop=(MAT + "NextTwelveMonths", MAT + "YearTwo", MAT + "YearThree"))
    disp = run(f, cfg).measures["maturities"].display
    assert "LongTermDebt" not in disp
    for label in ("debt due in 1y", "debt due in 2y", "debt due in 3y"):
        assert label in disp


def test_breach_detail_wording(cfg):
    nd = run(make_facts(latest={"NetCashProvidedByUsedInOperatingActivities": 49}), cfg)
    assert nd.measures["net_debt_fcf"].detail.startswith("net debt / FCF ")
    no_liq = run(
        make_facts(
            latest={
                "CashAndCashEquivalentsAtCarryingValue": 0,
                "NetCashProvidedByUsedInOperatingActivities": 20,
            }
        ),
        cfg,
    )
    m = no_liq.measures["maturities"]
    assert m.display == "no liquidity"
    assert m.detail == "maturities due with no liquidity (cash + FCF <= 0)"


def test_piotroski_missing_inputs_use_year_wording(cfg):
    f = make_facts(drop=("GrossProfit", "Revenues"))
    disp = run(f, cfg).measures["piotroski"].display
    assert "(latest)" in disp
    assert "(1y back)" in disp
    assert "(current)" not in disp
    assert "(prior)" not in disp
    f = make_facts(values={"Assets": [1000, 1000, None, 1000, 1000]})
    assert "assets (2y back)" in run(f, cfg).measures["piotroski"].display


def test_net_debt_breach_detail_extra_decimals_when_equal_at_one_dp(cfg):
    ocf = 30 + 120 / 6.04  # net debt 120, FCF = 120 / 6.04
    m = run(make_facts(latest={"NetCashProvidedByUsedInOperatingActivities": ocf}), cfg)
    m = m.measures["net_debt_fcf"]
    assert m.status == "breach"
    assert m.detail == "net debt / FCF 6.04x > 6.00x"
    assert m.display == "6.04x"


def test_maturities_breach_detail_extra_decimals(cfg):
    m = run(make_facts(latest={MAT + "NextTwelveMonths": 140.72}), cfg).measures["maturities"]
    assert m.status == "breach"
    assert m.detail == "maturities 1.004x > 1.000x of liquidity"
    assert m.display == "1.004x"


def test_negative_coverage_never_prints_negative_zero(cfg):
    res = run(make_facts(latest={"InterestExpense": 100, "OperatingIncomeLoss": -4}), cfg)
    m = res.measures["coverage"]
    assert m.display == "-0.04x"
    assert m.detail == "coverage -0.04x < 2.00x"


def test_plain_coverage_breach_keeps_one_decimal(cfg):
    m = run(make_facts(latest={"InterestExpense": 80}), cfg).measures["coverage"]
    assert m.display == "1.2x"
    assert m.detail == "coverage 1.2x < 2.0x"


@pytest.mark.parametrize(
    ("value", "threshold", "dp", "expected"),
    [
        (1.2, 2.0, 1, ("1.2", "2.0")),
        (6.04, 6.0, 1, ("6.04", "6.00")),
        (-0.00001, 2.0, 1, ("0.0000", "2.0000")),
        (-0.04, 2.0, 1, ("-0.04", "2.00")),
    ],
)
def test_fmt_vs(value, threshold, dp, expected):
    assert fr._fmt_vs(value, threshold, dp) == expected


# --------------------------------------------------------------------------- run 5 amendment

NONOP = "InterestExpenseNonoperating"
LTD_INCL = "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities"
LTD_NC = "LongTermDebtAndCapitalLeaseObligations"
LTD_CUR = "LongTermDebtAndCapitalLeaseObligationsCurrent"


def _nd(facts, cfg):
    return run(facts, cfg).measures["net_debt_fcf"]


def test_interest_nonoperating_is_the_last_fallback(cfg):
    f = make_facts(drop=("InterestExpense",), latest={NONOP: 25})
    assert run(f, cfg).measures["coverage"].value == pytest.approx(4.0)
    both = make_facts(drop=("InterestExpense",), latest={"InterestAndDebtExpense": 20, NONOP: 25})
    assert run(both, cfg).measures["coverage"].value == pytest.approx(5.0)


@pytest.mark.parametrize(
    ("latest", "debt"),
    [
        ({LTD_INCL: 230, "ShortTermBorrowings": 10}, 240),  # a: total + short-term
        ({LTD_NC: 200, LTD_CUR: 20, "ShortTermBorrowings": 10}, 230),  # b: first current part
        ({LTD_NC: 200, "LongTermDebtCurrent": 20, "ShortTermBorrowings": 10}, 230),
        ({LTD_NC: 200, LTD_CUR: 20, "LongTermDebtCurrent": 99}, 220),  # order of current parts
        ({LTD_NC: 200, "DebtCurrent": 30, "ShortTermBorrowings": 10}, 230),  # no double count
        ({"DebtLongtermAndShorttermCombinedAmount": 250, "ShortTermBorrowings": 10}, 250),  # c
    ],
)
def test_debt_fallbacks(cfg, latest, debt):
    m = _nd(make_facts(drop=("LongTermDebt",), latest=latest), cfg)
    assert m.value == pytest.approx((debt - 100) / 80)


def test_debt_fallback_edge_cases(cfg):
    # the existing chain wins over a fallback
    assert _nd(make_facts(latest={LTD_INCL: 999}), cfg).value == pytest.approx(1.5)
    # a noncurrent part without any current part is not completed with zero
    f = make_facts(drop=("LongTermDebt",), latest={LTD_NC: 200})
    assert _nd(f, cfg).status == "n/a"
    # total (a) comes before noncurrent + current (b)
    f = make_facts(drop=("LongTermDebt",), latest={LTD_INCL: 230, LTD_NC: 1, LTD_CUR: 1})
    assert _nd(f, cfg).value == pytest.approx(130 / 80)


def _untagged(**kwargs):
    return make_facts(drop=("LongTermDebt", "InterestExpense", *kwargs.pop("drop", ())), **kwargs)


def test_untagged_no_debt_rule_positive(cfg):
    res = run(_untagged(), cfg)
    for key in ("coverage", "net_debt_fcf", "rate_trend"):
        assert res.measures[key].display == "no debt"
        assert res.measures[key].status == "ok"
    assert res.note == fr.NO_DEBT_NOTE == "no debt tag; treated as no debt"
    assert res.cls == fr.SOUND


@pytest.mark.parametrize(
    "facts",
    [
        make_facts(drop=("LongTermDebt",)),  # interest expense > 0
        _untagged(drop=("Liabilities",)),  # no real balance sheet
        _untagged(drop=("Assets",)),
        _untagged(latest={"DebtInstrumentCarryingAmount": 50}),
        _untagged(latest={"CommercialPaper": 5}),
        _untagged(latest={LTD_NC: 200}),  # a debt tag is there, just not completable
    ],
)
def test_untagged_no_debt_rule_negative(cfg, facts):
    res = run(facts, cfg)
    assert res.measures["net_debt_fcf"].display == "n/a (missing debt)"
    assert res.note == ""


def test_untagged_no_debt_blocked_by_positive_interest_in_any_tag(cfg):
    f = _untagged(latest={NONOP: 5})
    assert run(f, cfg).measures["net_debt_fcf"].display == "n/a (missing debt)"
    assert run(f, cfg).note == ""
    zero = _untagged(latest={NONOP: 0})  # not > 0: still no debt
    assert run(zero, cfg).note == fr.NO_DEBT_NOTE


def test_explicit_zero_debt_gets_no_untagged_note(cfg):
    res = run(make_facts(latest={"LongTermDebt": 0, "InterestExpense": 0}), cfg)
    assert res.note == ""


CONV_NC = "ConvertibleLongTermNotesPayable"


@pytest.mark.parametrize(
    ("latest", "debt"),
    [
        ({"ConvertibleDebtNoncurrent": 200}, 200),  # d: noncurrent only
        ({CONV_NC: 200, "ConvertibleDebtCurrent": 20}, 220),  # optional current part
        ({"ConvertibleNotesPayable": 200, "ConvertibleNotesPayableCurrent": 20}, 220),
        ({"ConvertibleDebtNoncurrent": 200, CONV_NC: 99}, 200),  # order of noncurrent tags
        ({CONV_NC: 200, "ConvertibleDebtCurrent": 20, "ConvertibleNotesPayableCurrent": 99}, 220),
        ({CONV_NC: 200, "ShortTermBorrowings": 10}, 210),
    ],
)
def test_convertible_only_fallback(cfg, latest, debt):
    f = make_facts(drop=("LongTermDebt", "InterestExpense"), latest=latest)
    res = run(f, cfg)
    assert res.measures["net_debt_fcf"].value == pytest.approx((debt - 100) / 80)
    assert res.note == ""


def test_convertible_fallback_is_strict_fallback(cfg):
    assert _nd(make_facts(latest={CONV_NC: 999}), cfg).value == pytest.approx(1.5)
    f = make_facts(drop=("LongTermDebt",), latest={LTD_INCL: 230, CONV_NC: 999})
    assert _nd(f, cfg).value == pytest.approx(130 / 80)


@pytest.mark.parametrize(
    "tag",
    [
        CONV_NC,
        "ConvertibleDebtNoncurrent",
        "ConvertibleDebtCurrent",
        "ConvertibleNotesPayableCurrent",
    ],
)
def test_convertible_tag_blocks_untagged_no_debt_rule(cfg, tag):
    res = run(_untagged(latest={tag: 50}), cfg)
    assert res.note == ""
    assert res.measures["net_debt_fcf"].display != "no debt"


def test_convertible_current_part_alone_is_not_completed(cfg):
    res = run(_untagged(latest={"ConvertibleDebtCurrent": 20}), cfg)
    assert res.measures["net_debt_fcf"].display == "n/a (missing debt)"
    assert res.note == ""


# --------------------------------------------------------------------------- run 6 amendment

CASH_TAG = "CashAndCashEquivalentsAtCarryingValue"
CASH_FV = "CashAndCashEquivalentsFairValueDisclosure"
PRETAX_OLD = (
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"
)
PRETAX_NEW = "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"
OCF_TAG = "NetCashProvidedByUsedInOperatingActivities"
OCF_CONT = OCF_TAG + "ContinuingOperations"
REV_NEW = "RevenueFromContractWithCustomerIncludingAssessedTax"


def test_run6_cash_fallbacks_and_priority(cfg):
    fv = make_facts(drop=(CASH_TAG,), latest={CASH_FV: 100})
    assert _nd(fv, cfg).value == pytest.approx(1.5)
    # the original tag wins over the new one
    old = make_facts(latest={CASH_FV: 500})
    assert _nd(old, cfg).value == pytest.approx(1.5)
    # short-term investments still add to the fallback cash
    inv = make_facts(drop=(CASH_TAG,), latest={CASH_FV: 70, "ShortTermInvestments": 30})
    assert _nd(inv, cfg).value == pytest.approx(1.5)


def test_run6_bare_cash_tag_is_not_a_fallback(cfg):
    f = make_facts(drop=(CASH_TAG,), latest={"Cash": 100})
    display = _nd(f, cfg).display
    assert "missing" in display
    assert "cash" in display


def test_run6_ebit_pretax_fallback_and_priority(cfg):
    f = make_facts(drop=("OperatingIncomeLoss",), latest={PRETAX_NEW: 85})
    assert run(f, cfg).measures["coverage"].value == pytest.approx(100 / 15)
    # the existing pretax tag wins over the new one; OperatingIncomeLoss wins over both
    f = make_facts(drop=("OperatingIncomeLoss",), latest={PRETAX_OLD: 85, PRETAX_NEW: 999})
    assert run(f, cfg).measures["coverage"].value == pytest.approx(100 / 15)
    f = make_facts(latest={PRETAX_NEW: 999})
    assert run(f, cfg).measures["coverage"].value == pytest.approx(100 / 15)
    # interest is still required
    f = make_facts(drop=("OperatingIncomeLoss", "InterestExpense"), latest={PRETAX_NEW: 85})
    assert "missing EBIT" in run(f, cfg).measures["coverage"].display


def test_run6_ocf_fallback_and_priority(cfg):
    f = make_facts(drop=(OCF_TAG,), latest={OCF_CONT: 110})
    assert _nd(f, cfg).value == pytest.approx(1.5)  # FCF 80
    f = make_facts(latest={OCF_CONT: 999})
    assert _nd(f, cfg).value == pytest.approx(1.5)


def test_run6_ocf_fallback_does_not_decide_fiscal_years(cfg):
    only = make_facts(drop=(OCF_TAG, "NetIncomeLoss", "OperatingIncomeLoss"), latest={OCF_CONT: 1})
    assert run(only, cfg).cls == fr.INSUFFICIENT


@pytest.mark.parametrize(
    ("latest", "debt"),
    [
        ({"LongTermDebtNoncurrent": 200, "DebtCurrent": 30, "ShortTermBorrowings": 10}, 230),
        ({"LongTermDebtNoncurrent": 200, "DebtCurrent": 30}, 230),
        # LongTermDebtCurrent comes first and then adds ShortTermBorrowings
        (
            {
                "LongTermDebtNoncurrent": 200,
                "LongTermDebtCurrent": 20,
                "DebtCurrent": 99,
                "ShortTermBorrowings": 10,
            },
            230,
        ),
    ],
)
def test_run6_primary_noncurrent_plus_debt_current(cfg, latest, debt):
    # DebtCurrent already includes ShortTermBorrowings: never double counted
    f = make_facts(drop=("LongTermDebt",), latest=latest)
    assert fr._debt_primary(fr._View(f, "AAA", ASOF), pd.Timestamp("2024-12-31")) == debt
    assert _nd(f, cfg).value == pytest.approx((debt - 100) / 80)


def test_run6_noncurrent_without_current_part_is_still_unavailable(cfg):
    f = make_facts(drop=("LongTermDebt",), latest={"LongTermDebtNoncurrent": 220})
    assert fr._debt_primary(fr._View(f, "AAA", ASOF), pd.Timestamp("2024-12-31")) is None
    assert _nd(f, cfg).status == "n/a"


def test_run6_revenue_fallback_for_gross_profit_and_priority():
    end = pd.Timestamp("2024-12-31")
    only = make_facts(drop=("GrossProfit", "Revenues"), latest={REV_NEW: 580, "CostOfRevenue": 300})
    assert fr._pio_year(fr._View(only, "AAA", ASOF), end)["gross profit"] == 280
    both = make_facts(drop=("GrossProfit",), latest={REV_NEW: 999, "CostOfRevenue": 300})
    year = fr._pio_year(fr._View(both, "AAA", ASOF), end)
    assert year["revenue"] == 580
    assert year["gross profit"] == 280


def test_run6_revenue_constant_shared_with_other_modules_is_unchanged():
    assert REV_NEW not in fd.REVENUE_CONCEPTS
    assert REV_NEW in fr.REVENUE
