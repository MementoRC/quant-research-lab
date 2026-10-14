"""True-cash assumption row (spec: docs/methodology/true-cash-sleeve.md): the
optional cash_assumption key, the cash leg (CPI inflation plus a real yield),
and the row in the decision and long-run reports. Offline: synthetic prices,
synthetic CPI and fixture configs only (never market data); research period
only."""

from __future__ import annotations

import hashlib
import importlib.util
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from decision_helpers import (
    CANDIDATES,
    END,
    GOOD_SLEEVE,
    GOOD_TCASH,
    ROOT,
    criteria,
    load,
    prices,
    stress_cfg,
    write,
)
from test_decision_report import _hand_report
from test_defensive_sleeve import ALL_IDS

from qrl import decision_withdraw, longrun
from qrl.decision import (
    assumption_returns,
    portfolio_returns,
    return_rows,
    run_decision,
    start_dates,
    withdrawal_rows,
)
from qrl.decision_config import CashAssumption, load_decision_config
from qrl.decision_report import _header, _notes, render_markdown
from qrl.decision_withdraw import (
    monthly_inflation,
    monthly_withdrawals,
    path_metrics,
    usable_cpi,
    withdrawal_path,
)
from qrl.longrun import (
    CASH_ASSUMPTION,
    LongrunConfig,
    block_starts,
    check_cash_assumption,
    load_longrun_config,
    month_indices,
    monthly_returns,
    run_longrun,
    run_paths,
    summarize,
)
from qrl.longrun_report import render_markdown as render_longrun
from qrl.metrics import compute_metrics
from qrl.true_cash import cash_leg_returns, mix_returns, strict_monthly_inflation


def test_monthly_inflation_lives_in_decision_withdraw_and_longrun_reuses_it():
    assert longrun.monthly_inflation is decision_withdraw.monthly_inflation


TCASH = CashAssumption(
    id="A80-TCASH20",
    label="80% A + 20% cash at +1% real (assumption)",
    base="A",
    cash_share=0.2,
    real_yield=0.01,
)


def _shipped():
    return load_decision_config(ROOT / "config" / "decision.yaml", CANDIDATES, stress_cfg(), END)


def test_shipped_decision_config_carries_the_cash_assumption_outside_the_portfolios():
    cfg = _shipped()
    assert cfg.cash_assumptions[0] == replace(TCASH, pair="A80-CASH20")
    ids = [p.id for p in cfg.portfolios]
    assert len(ids) == 27
    assert "A80-TCASH20" not in ids


def test_shipped_longrun_cash_real_yield_matches_the_cash_assumption():
    dcfg = _shipped()
    lcfg = load_longrun_config(ROOT / "config" / "longrun.yaml", dcfg.sha256)
    check_cash_assumption(lcfg, dcfg)
    assert lcfg.cash_real_yield == TCASH.real_yield


def test_absent_cash_assumption_gives_none_and_the_same_portfolios(tmp_path):
    with_row = load(tmp_path, GOOD_TCASH)
    without = load(tmp_path, GOOD_SLEEVE)
    assert with_row.cash_assumption == TCASH
    assert without.cash_assumption is None
    assert with_row.portfolios == without.portfolios


@pytest.mark.parametrize(
    ("old", "new", "match"),
    [
        ("  base: A\n", "", "needs"),
        ("id: A80-TCASH20", "id: A80 TCASH20", "must match"),
        ("id: A80-TCASH20", "id: A80-CASH20", "already a portfolio id"),
        ("base: A", "base: Z", "not a portfolio id"),
        ("cash_share: 0.2", "cash_share: 0.0", "strictly between 0 and 1"),
        ("cash_share: 0.2", "cash_share: 1.0", "strictly between 0 and 1"),
        ("cash_share: 0.2", "cash_share: .nan", "strictly between 0 and 1"),
        ("real_yield: 0.01", "real_yield: 0.0501", "real_yield"),
        ("real_yield: 0.01", "real_yield: -0.0501", "real_yield"),
        ("real_yield: 0.01", "real_yield: .inf", "real_yield"),
        ("real_yield: 0.01", "real_yield: .nan", "real_yield"),
    ],
)
def test_cash_assumption_refusals(tmp_path, old, new, match):
    assert old in GOOD_TCASH
    with pytest.raises(ValueError, match=match):
        load(tmp_path, GOOD_TCASH.replace(old, new, 1))


@pytest.mark.parametrize("value", ["7", "", "[A, 0.2]"])
def test_cash_assumption_must_be_a_mapping(tmp_path, value):
    text = GOOD_SLEEVE.replace("windows:", f"cash_assumption: {value}\nwindows:", 1)
    with pytest.raises(ValueError, match="needs"):
        load(tmp_path, text)


@pytest.mark.parametrize("real_yield", ["0.05", "-0.05"])
def test_cash_assumption_real_yield_bounds_are_inclusive(tmp_path, real_yield):
    cfg = load(tmp_path, GOOD_TCASH.replace("real_yield: 0.01", f"real_yield: {real_yield}", 1))
    assert cfg.cash_assumption is not None
    assert cfg.cash_assumption.real_yield == float(real_yield)


def _lcfg(real_yield: float = 0.01) -> LongrunConfig:
    return LongrunConfig(
        seed=7,
        n_paths=20,
        block_months=12,
        horizon_years=30,
        real_floor=0.5,
        rates=[0.04],
        cash_real_yield=real_yield,
        sha256="ab" * 32,
    )


def test_check_cash_assumption_refuses_a_real_yield_mismatch(tmp_path):
    dcfg = load(tmp_path, GOOD_TCASH)
    with pytest.raises(ValueError, match="cash_real_yield"):
        check_cash_assumption(_lcfg(0.02), dcfg)
    check_cash_assumption(_lcfg(0.01), dcfg)  # equal: no refusal


def test_check_cash_assumption_is_silent_without_the_key(tmp_path):
    check_cash_assumption(_lcfg(0.02), load(tmp_path, GOOD_SLEEVE))


def test_run_longrun_refuses_a_mismatch_before_reading_any_data(tmp_path):
    # {} has no "close": any data access would raise KeyError, not ValueError
    with pytest.raises(ValueError, match="cash_real_yield"):
        run_longrun(_lcfg(0.02), load(tmp_path, GOOD_TCASH), {}, pd.Series(dtype=float), criteria())


def _longrun_cli():
    spec = importlib.util.spec_from_file_location(
        "longrun_cli_tcash", ROOT / "scripts" / "longrun.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LONGRUN_YAML = """\
version: 1
decision_sha256: "{sha}"
seed: 7
n_paths: 20
block_months: 12
horizon_years: 30
real_floor: 0.5
withdrawal_rates: [0.04]
cash_real_yield: {real_yield}
"""


def test_longrun_main_refuses_a_cash_yield_mismatch_before_loading_data(
    tmp_path, monkeypatch, capsys
):
    cli = _longrun_cli()

    def no_access(*args, **kwargs):
        raise AssertionError("data must not be loaded before the cash yield is checked")

    monkeypatch.setattr(cli, "load_ohlcv", no_access)
    monkeypatch.setattr(cli, "load_macro", no_access)
    decision = write(tmp_path, GOOD_TCASH)
    pinned = tmp_path / "longrun.yaml"
    sha = hashlib.sha256(decision.read_bytes()).hexdigest()
    pinned.write_text(LONGRUN_YAML.format(sha=sha, real_yield=0.02))
    out = tmp_path / "longrun.md"
    argv = ["--config", str(decision), "--longrun-config", str(pinned), "--out-md", str(out)]
    assert cli.main(argv) == 1
    printed = capsys.readouterr().out
    assert printed.startswith("refused: ")
    assert "cash_real_yield" in printed
    assert not out.exists()


FIRST = pd.Timestamp("2005-01-03")  # first synthetic trading day on/after 2005-01-01


def uneven_cpi(start: str = "1995-01", end: str = "2021-11") -> pd.Series:
    """CPI with distinct month-over-month changes (0.1% .. 0.7%), indexed by
    AVAILABILITY date (month M usable from the last day of M+1, as qrl.macro
    lags it). Unlike the constant-growth decision_helpers.cpi(), a one-month
    misalignment changes every figure."""
    months = pd.period_range(start, end, freq="M")
    levels = 100 * np.cumprod(1 + 0.001 * (1 + np.arange(len(months)) % 7))
    avail = [(m + 1).to_timestamp(how="end").normalize() for m in months]
    return pd.Series(levels, index=pd.DatetimeIndex(avail), name="CPIAUCNS")


def _trading_days() -> pd.DatetimeIndex:
    return pd.DatetimeIndex(prices()["close"].loc[:END].index)


def test_cash_leg_earns_exactly_the_real_yield_against_the_decision_deflator():
    trading = _trading_days()
    cpi = uneven_cpi().loc[:END]
    for year in range(2005, 2015):
        days = trading[trading >= pd.Timestamp(year=year, month=1, day=1)]
        cash = cash_leg_returns(days, trading, cpi, 0.01)
        growth = float(np.prod(1.0 + cash.to_numpy()))
        # path_metrics' deflator: CPI usable on the last day over the first day
        deflator = usable_cpi(cpi, days[-1]) / usable_cpi(cpi, days[0])
        assert growth / deflator == pytest.approx(1.01 ** (2019 - year), rel=1e-12), year


def test_each_whole_month_earns_its_inflation_plus_the_real_yield():
    trading = _trading_days()
    days = trading[trading >= FIRST]
    cpi = uneven_cpi().loc[:END]
    cash = cash_leg_returns(days, trading, cpi, 0.01)
    months = days.to_period("M")
    monthly = (1.0 + cash).groupby(months).prod()
    infl = monthly_inflation(cpi, pd.PeriodIndex(monthly.index))
    assert len(monthly) == 168
    assert (monthly / (1.0 + infl)).to_numpy() == pytest.approx(
        np.full(168, 1.01 ** (1 / 12)), rel=1e-13
    )
    # January 2005 by hand: December 2004's CPI (usable 2005-01-31) over
    # November 2004's (usable 2004-12-31)
    jan = cpi[pd.Timestamp("2005-01-31")] / cpi[pd.Timestamp("2004-12-31")]
    assert monthly.iloc[0] == pytest.approx(jan * 1.01 ** (1 / 12), rel=1e-13)
    # every trading day of a month earns the same rate
    assert cash.groupby(months).nunique().eq(1).all()


def test_a_partial_first_month_earns_only_its_share_of_the_month():
    trading = _trading_days()
    jan = trading[(trading >= "2005-01-01") & (trading <= "2005-01-31")]
    days = trading[trading >= jan[5]]
    cpi = uneven_cpi().loc[:END]
    cash = cash_leg_returns(days, trading, cpi, 0.01)
    full = cpi[pd.Timestamp("2005-01-31")] / cpi[pd.Timestamp("2004-12-31")] * 1.01 ** (1 / 12)
    got = float(np.prod(1.0 + cash.loc[:"2005-01-31"].to_numpy()))
    assert got == pytest.approx(full ** ((len(jan) - 5) / len(jan)), rel=1e-13)


def test_a_single_missing_cpi_month_is_refused_though_monthly_inflation_passes_it():
    cpi = uneven_cpi().loc[:END].drop(pd.Timestamp("2010-03-31"))
    months = pd.period_range("2005-01", "2018-12", freq="M")
    monthly_inflation(cpi, months)  # the 45-day tolerance lets one gap through
    with pytest.raises(ValueError, match="missing CPI for month 2010-03"):
        strict_monthly_inflation(cpi, months)


def test_a_nan_cpi_value_is_refused():
    cpi = uneven_cpi().loc[:END].copy()
    cpi[pd.Timestamp("2010-03-31")] = np.nan
    months = pd.period_range("2005-01", "2018-12", freq="M")
    with pytest.raises(ValueError, match="missing CPI for month 2010-03"):
        strict_monthly_inflation(cpi, months)


def test_the_first_month_needs_the_previous_month_end_cpi():
    cpi = uneven_cpi(start="2004-12")  # first value usable 2005-01-31
    months = pd.period_range("2005-01", "2005-03", freq="M")
    with pytest.raises(ValueError, match="missing CPI for month 2005-01"):
        strict_monthly_inflation(cpi, months)


def test_cash_leg_refuses_a_month_without_trading_days():
    trading = _trading_days()
    days = trading[trading >= FIRST]
    with pytest.raises(ValueError, match="no trading day"):
        cash_leg_returns(days, trading[trading >= "2005-02-01"], uneven_cpi(), 0.01)


def test_mix_returns_is_the_daily_weighted_sum_and_refuses_misaligned_series():
    idx = pd.bdate_range("2005-01-03", periods=4)
    base = pd.Series([0.01, -0.02, 0.0, 0.03], index=idx)
    cash = pd.Series([0.001] * 4, index=idx)
    pd.testing.assert_series_equal(
        mix_returns(base, cash, 0.2), (1 - 0.2) * base + 0.2 * cash, check_exact=True
    )
    with pytest.raises(ValueError, match="one index"):
        mix_returns(base, cash.iloc[1:], 0.2)


def _cut() -> dict[str, pd.DataFrame]:
    return {k: v.loc[:END] for k, v in prices().items()}


@pytest.fixture(scope="module")
def tsmall(tmp_path_factory):
    cfg = load(tmp_path_factory.mktemp("tcash"), GOOD_TCASH)
    by_id = {p.id: p for p in cfg.portfolios}
    return replace(
        cfg,
        portfolios=[by_id["A"], by_id["A80-CASH20"]],
        rates=[0.04],
        start_years=[2005, 2010],
    )


@pytest.fixture(scope="module")
def treport(tsmall):
    return run_decision(tsmall, prices(), uneven_cpi(), criteria(), "cd" * 32)


def test_assumption_row_is_the_base_mixed_daily_with_the_cash_leg(tsmall):
    cut, known = _cut(), uneven_cpi().loc[:END]
    row = assumption_returns(tsmall, cut, known, FIRST, 5.0)
    base = portfolio_returns(tsmall.portfolios[0], cut, FIRST, 5.0)
    cash = cash_leg_returns(
        pd.DatetimeIndex(base.index), pd.DatetimeIndex(cut["close"].index), known, 0.01
    )
    pd.testing.assert_series_equal(row, (1 - 0.2) * base + 0.2 * cash, check_exact=True)


def test_assumption_returns_none_without_a_cash_assumption_and_refuse_without_its_base(tsmall):
    cut, known = _cut(), uneven_cpi().loc[:END]
    assert assumption_returns(replace(tsmall, cash_assumption=None), cut, known, FIRST, 5.0) is None
    no_base = replace(tsmall, portfolios=tsmall.portfolios[1:])
    with pytest.raises(ValueError, match="not among the portfolios"):
        assumption_returns(no_base, cut, known, FIRST, 5.0)


def test_return_rows_add_the_assumption_row_last(tsmall):
    index = uneven_cpi()
    rows = return_rows(tsmall, prices(), criteria(), index)
    assert [r["portfolio"] for r in rows] == ["A", "A80-CASH20", "A80-TCASH20"]
    m = compute_metrics(assumption_returns(tsmall, _cut(), index.loc[:END], FIRST, 5.0))
    assert rows[-1]["cagr"] == m["cagr"]
    assert rows[-1]["max_drawdown"] == m["max_drawdown"]
    assert rows[-1]["lost_return"] == rows[0]["cagr"] - m["cagr"]


def test_return_rows_refuse_a_cash_assumption_without_cpi(tsmall):
    with pytest.raises(ValueError, match="needs `cpi`"):
        return_rows(tsmall, prices(), criteria())


def test_withdrawal_rows_add_the_assumption_row_last_for_every_start_year(tsmall):
    index = uneven_cpi()
    rows = withdrawal_rows(tsmall, prices(), index, criteria())
    assert [(r["portfolio"], r["rate"]) for r in rows] == [
        ("A", 0.04),
        ("A80-CASH20", 0.04),
        ("A80-TCASH20", 0.04),
    ]
    row, known, cut = rows[-1], index.loc[:END], _cut()
    starts = start_dates(pd.DatetimeIndex(cut["close"].index), [2005, 2010], END)
    assert sorted(row["per_year"]) == [2005, 2010]
    for year, day in starts.items():
        r = assumption_returns(tsmall, cut, known, day, 5.0)
        monthly = monthly_withdrawals(0.04, year, 2018, known)
        assert row["per_year"][year] == path_metrics(withdrawal_path(r, monthly), known)
    without = withdrawal_rows(replace(tsmall, cash_assumption=None), prices(), index, criteria())
    assert without == rows[:-1]


def test_assumption_rows_ignore_data_after_the_data_end(tsmall):
    data, index = prices(), uneven_cpi()
    rng = np.random.default_rng(11)
    after = np.asarray(data["close"].index > END)
    poisoned = {
        k: v * np.where(after[:, None], rng.uniform(0.2, 5.0, v.shape), 1.0)
        for k, v in data.items()
    }
    poisoned_cpi = index * np.where(
        np.asarray(index.index > END), rng.uniform(0.2, 5.0, len(index)), 1.0
    )
    assert not poisoned_cpi.equals(index)
    crit = criteria()
    assert return_rows(tsmall, poisoned, crit, poisoned_cpi) == return_rows(
        tsmall, data, crit, index
    )
    assert withdrawal_rows(tsmall, poisoned, poisoned_cpi, crit) == withdrawal_rows(
        tsmall, data, index, crit
    )


def test_run_decision_carries_the_row_and_keeps_it_out_of_the_other_tables(treport):
    assert treport["cash_assumption"] == {
        "id": "A80-TCASH20",
        "label": "80% A + 20% cash at +1% real (assumption)",
        "base": "A",
        "cash_share": 0.2,
        "real_yield": 0.01,
    }
    assert treport["returns"][-1]["portfolio"] == "A80-TCASH20"
    assert treport["withdrawals"][-1]["portfolio"] == "A80-TCASH20"
    assert "A80-TCASH20" not in [p["id"] for p in treport["portfolios"]]
    for key in ("windows", "scenario_rows", "year_one"):
        assert not any(r["portfolio"].startswith("A80-TCASH20") for r in treport[key]), key


CA = {
    "id": "A80-TCASH20",
    "label": "80% A + 20% cash at +1% real (assumption)",
    "base": "A",
    "cash_share": 0.2,
    "real_yield": 0.01,
}
ASSUMPTION_BULLET = (
    "- A80-TCASH20 (80% A + 20% cash at +1% real (assumption)) is an assumption row, not a "
    "fund: 20.0% cash earning each month's inflation plus 1.0% a year, the long-run report's "
    "CASH +1% real assumption, shown to answer the SHY caveat above. It is comparison 22 but "
    "not one of the 21 portfolios. Its cash leg and its daily return to 80/20 pay no trading "
    "cost, and neither does A80-CASH20: the engine charges only target-to-target turnover, "
    "so rebalancing a constant mix is free in both rows."
)
DRIFT_NOTE = (
    "- The engine never charges for drift, so the cost of real periodic rebalancing is "
    "slightly understated for every blend."
)
SCOPE_NOTE = (
    "- A80-TCASH20 appears only in the research-period return and withdrawal tables: the "
    "historical windows and the judgement-based scenarios have no cash return to give it. "
    "In `dotcom_2000` SHY is already replaced by cash at 0%, so the row would equal "
    "A80-CASH20 there; in `gfc_2008` A80-CASH20 uses SHY's actual prices; the scenarios "
    "set SHY's one-year return by judgement and set none for cash; the year-one table is "
    "built from the scenarios."
)


def _sleeve_report(**over) -> dict:
    portfolios = [{"id": i, "label": i, "states": {}} for i in ALL_IDS]
    return _hand_report(portfolios=portfolios, cost_bps=5.0, **over)


def test_decision_header_counts_the_row_and_says_it_is_an_assumption():
    lines = _header(_sleeve_report(cash_assumption=CA))
    assert any("7 in the core comparison, 22 here (A-G again plus 15 new)" in ln for ln in lines)
    assert ASSUMPTION_BULLET in lines
    assert "pays 5 bps" not in "\n".join(lines)
    shy = next(i for i, ln in enumerate(lines) if ln.startswith("- CASH here is SHY"))
    assert lines.index(ASSUMPTION_BULLET) == shy + 1


def test_decision_header_bullet_counts_come_from_the_portfolios():
    rep = _hand_report(cash_assumption=CA, cost_bps=5.0)  # one portfolio, X
    text = "\n".join(_header(rep))
    assert "It is comparison 2 but not one of the 1 portfolios." in text


def test_decision_notes_say_why_the_row_is_left_out_of_the_other_tables():
    assert SCOPE_NOTE in _notes(_sleeve_report(cash_assumption=CA))
    assert SCOPE_NOTE not in _notes(_sleeve_report())


def test_decision_report_without_the_key_is_unchanged():
    assert render_markdown(_hand_report()) == render_markdown(_hand_report(cash_assumption=None))
    rep = _sleeve_report()
    assert _header(rep) == _header(_sleeve_report(cash_assumption=None))
    assert any(
        "7 in the core comparison, 21 here (A-G again plus 14 new)" in ln for ln in _header(rep)
    )
    assert not any("A80-TCASH20" in ln for ln in _header(rep) + _notes(rep))


def _table_rows(section: str) -> list[str]:
    return [
        ln
        for ln in section.splitlines()
        if ln.startswith("| ") and not ln.lower().startswith("| portfolio")
    ]


def test_decision_report_shows_the_row_last_in_return_and_withdrawal_tables_only(treport):
    md = render_markdown(treport)
    sections = {s.split("\n", 1)[0]: s for s in md.split("\n## ")[1:]}
    returns = _table_rows(sections["Research-period return (2005-2018, no withdrawals)"])
    assert returns[-1].startswith("| A80-TCASH20 |")
    tables = sections["Withdrawals"].split("\n### ")[1:]
    assert len(tables) == 1
    for table in tables:
        assert _table_rows(table)[-1].startswith("| A80-TCASH20 |")
    for title in (
        "Portfolios (100% of capital)",
        "Historical windows",
        "Judgement-based scenarios (one year)",
        "Year-one scenario hit",
    ):
        assert "| A80-TCASH20" not in sections[title], title


def _longrun_hand(names: list[str], **over) -> dict:
    row = {
        "depleted_by": {20: 0.0, 25: 0.0, 30: 0.0},
        "median_depletion_year": None,
        "below_floor": 0.0,
        "end_real_median": 1.0,
        "end_real_p5": 0.5,
    }
    rep = {
        "data_end": "2018-12-31",
        "first_month": "2005-01",
        "last_month": "2018-12",
        "n_months": 168,
        "seed": 1,
        "n_paths": 10,
        "block_months": 12,
        "horizon_years": 30,
        "real_floor": 0.5,
        "cash_real_yield": 0.01,
        "rates": [0.04],
        "longrun_sha256": "ab" * 32,
        "decision_sha256": "cd" * 32,
        "cost_bps": 5.0,
        "rows": [{"rate": 0.04, "portfolio": n, **row} for n in names],
    }
    return rep | over


NAMES_22 = ALL_IDS[:8] + [CASH_ASSUMPTION] + ALL_IDS[8:]
TCASH_KEYS = {
    "cash_assumption_id": "A80-TCASH20",
    "cash_assumption_base": "A",
    "cash_assumption_share": 0.2,
}
LONGRUN_SLEEVE_23 = (
    f"- 23 rows per withdrawal rate, including the {CASH_ASSUMPTION} row, the A80-TCASH20 "
    "assumption row and 4 by-product rows (IEF, TLT, RSP, BONDS); only the 5 A80 rows answer "
    "the defensive-sleeve question (docs/methodology/defensive-sleeve.md)"
)
LONGRUN_NOTE = (
    "- A80-TCASH20: an assumption, not history. 80.0% A plus 20.0% cash earning each month's "
    "inflation plus 1.0% a year, rebalanced daily; its real yield is checked equal to the "
    "CASH +1% real row's. The cash leg and the daily return to 80/20 pay no trading cost, "
    "and neither does A80-CASH20: the engine charges only target-to-target turnover, so "
    "rebalancing a constant mix is free in both rows."
)


def test_longrun_header_names_the_assumption_row_and_does_not_count_it_as_a80():
    lines = render_longrun(_longrun_hand([*NAMES_22, "A80-TCASH20"], **TCASH_KEYS)).splitlines()
    assert LONGRUN_SLEEVE_23 in lines
    assert LONGRUN_NOTE in lines
    assert "pays 5 bps" not in "\n".join(lines)
    assert (
        lines.index(LONGRUN_NOTE)
        == next(i for i, ln in enumerate(lines) if ln.startswith(f"- {CASH_ASSUMPTION}:")) + 1
    )


def test_decision_single_row_has_no_cost_claim_and_the_drift_note():
    text = "\n".join(_header(_sleeve_report(cash_assumption=CA)))
    notes = _notes(_sleeve_report(cash_assumption=CA))
    assert "pays 5 bps" not in text + "\n".join(notes)
    assert DRIFT_NOTE in notes


def test_longrun_single_row_has_no_cost_claim_and_the_drift_note():
    lines = render_longrun(_longrun_hand([*NAMES_22, "A80-TCASH20"], **TCASH_KEYS)).splitlines()
    assert "pays 5 bps" not in "\n".join(lines)
    assert DRIFT_NOTE in lines


def test_longrun_report_without_the_key_is_unchanged():
    plain = render_longrun(_longrun_hand(NAMES_22))
    nones = dict.fromkeys(TCASH_KEYS)
    assert render_longrun(_longrun_hand(NAMES_22, **nones)) == plain
    assert "A80-TCASH20" not in plain


def test_run_longrun_adds_the_assumption_row_last_on_the_same_draws(tsmall):
    index = uneven_cpi()
    report = run_longrun(_lcfg(), tsmall, prices(), index, criteria())
    assert [r["portfolio"] for r in report["rows"]] == ["A", "A80-CASH20", "A80-TCASH20"]
    assert {k: report[k] for k in TCASH_KEYS} == TCASH_KEYS
    known = index.loc[:END]
    monthly = monthly_returns(assumption_returns(tsmall, _cut(), known, FIRST, 5.0))
    infl = monthly_inflation(known, pd.PeriodIndex(monthly.index)).to_numpy()
    idx = month_indices(block_starts(7, 20, 30, 168), 12, 168)
    expected = summarize(run_paths(monthly.to_numpy(), infl, idx, 0.04), 0.5)
    got = {k: v for k, v in report["rows"][-1].items() if k not in ("rate", "portfolio")}
    assert got == expected


def test_run_longrun_without_the_key_has_no_row_and_none_keys(tsmall):
    report = run_longrun(
        _lcfg(), replace(tsmall, cash_assumption=None), prices(), uneven_cpi(), criteria()
    )
    assert [r["portfolio"] for r in report["rows"]] == ["A", "A80-CASH20"]
    assert {k: report[k] for k in TCASH_KEYS} == dict.fromkeys(TCASH_KEYS)
