"""Staged entry (qrl.decision_staged, qrl.staged_entry_report). Offline;
synthetic returns, prices and CPI only. Spec:
docs/methodology/staged-entry.md ("Tests")."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from decision_helpers import (
    CANDIDATES,
    END,
    GOOD,
    GOOD_TCASH_ALL,
    ROOT,
    criteria,
    load,
    prices,
    stress_cfg,
)
from decision_helpers import cpi as cpi_series

import qrl.decision_staged as staged_mod
from qrl.decision import portfolio_returns, research_start
from qrl.decision_config import load_decision_config
from qrl.decision_staged import (
    StagedConfig,
    StagedRun,
    compare,
    daily_cash,
    historical_run,
    historical_withdrawals,
    horizon_positions,
    load_staged_config,
    longrun_levels,
    longrun_measures,
    longrun_run,
    longrun_withdrawals,
    lump_only,
    month_firsts,
    path_measures,
    run_staged,
    run_staged_entry,
    start_months,
    tranche_returns,
)
from qrl.decision_withdraw import DEPLETED, monthly_withdrawals, usable_cpi, withdrawal_path
from qrl.longrun import (
    LongrunConfig,
    block_starts,
    cash_assumption_returns,
    load_longrun_config,
    month_indices,
    run_paths,
)

D_SHA = "d" * 64  # placeholder replaced by the test decision.yaml's sha256
L_SHA = "e" * 64  # the test LongrunConfig's sha256

STAGED_YAML = f"""\
version: 1
decision_sha256: "{D_SHA}"
longrun_sha256: "{L_SHA}"
periods_months: [0, 6, 12, 24]
cash_variants: [shy, real_plus_1]
portfolios: [A, B, C, D, E, F, G]
"""


def _lcfg(**kw) -> LongrunConfig:
    base = LongrunConfig(
        seed=7,
        n_paths=50,
        block_months=12,
        horizon_years=30,
        real_floor=0.5,
        rates=[0.02, 0.033, 0.04, 0.05],
        cash_real_yield=0.01,
        sha256=L_SHA,
    )
    return replace(base, **kw)


def _write(tmp_path, text, dcfg):
    path = tmp_path / "staged_entry.yaml"
    path.write_text(text.replace(D_SHA, dcfg.sha256))
    return path


# ---- config


def test_loader_reads_the_config(tmp_path):
    dcfg = load(tmp_path, GOOD_TCASH_ALL)
    scfg = load_staged_config(_write(tmp_path, STAGED_YAML, dcfg), dcfg, _lcfg())
    assert isinstance(scfg, StagedConfig)
    assert scfg.periods == [0, 6, 12, 24]
    assert scfg.cash_variants == ["shy", "real_plus_1"]
    assert scfg.portfolios == list("ABCDEFG")
    assert len(scfg.sha256) == 64


REFUSALS = [
    ("version: 1", "version: 2", "unsupported version"),
    ("portfolios:", "extra: 1\nportfolios:", "unknown key"),
    ("cash_variants: [shy, real_plus_1]\n", "", "missing key"),
    ("[0, 6, 12, 24]", "[6, 0, 12]", "must start with 0"),
    ("[0, 6, 12, 24]", "[0, 6, 6]", "duplicate"),
    ("[0, 6, 12, 24]", "[0, -6]", "non-negative integers"),
    ("[0, 6, 12, 24]", "[0, 6.5]", "non-negative integers"),
    ("[0, 6, 12, 24]", "[0, true]", "non-negative integers"),
    ("[0, 6, 12, 24]", "[]", "non-empty list"),
    ("[shy, real_plus_1]", "[shy, cash]", "unknown cash variant"),
    ("[shy, real_plus_1]", "[shy, shy]", "duplicate"),
    ("[shy, real_plus_1]", "[]", "non-empty list"),
    ("[A, B, C, D, E, F, G]", "[A, Z]", "not in decision.yaml"),
    ("[A, B, C, D, E, F, G]", "[A, CASH]", "is excluded"),
    ("[A, B, C, D, E, F, G]", "[A, A]", "duplicate"),
    ("[A, B, C, D, E, F, G]", "[]", "non-empty list"),
    (f'"{L_SHA}"', '"' + "0" * 64 + '"', "longrun.yaml changed"),
]


@pytest.mark.parametrize(("old", "new", "match"), REFUSALS)
def test_loader_refuses(tmp_path, old, new, match):
    dcfg = load(tmp_path, GOOD_TCASH_ALL)
    assert old in STAGED_YAML
    with pytest.raises(ValueError, match=match):
        load_staged_config(_write(tmp_path, STAGED_YAML.replace(old, new), dcfg), dcfg, _lcfg())


def test_loader_refuses_a_stale_decision_pin(tmp_path):
    dcfg = load(tmp_path, GOOD_TCASH_ALL)
    path = tmp_path / "staged_entry.yaml"
    path.write_text(STAGED_YAML)  # D_SHA left in place: not decision.yaml's sha256
    with pytest.raises(ValueError, match="decision.yaml changed"):
        load_staged_config(path, dcfg, _lcfg())


def test_loader_refuses_real_plus_1_without_a_cash_assumption(tmp_path):
    dcfg = load(tmp_path, GOOD)
    with pytest.raises(ValueError, match="needs a cash_assumptions row"):
        load_staged_config(_write(tmp_path, STAGED_YAML, dcfg), dcfg, _lcfg())
    shy_only = STAGED_YAML.replace("[shy, real_plus_1]", "[shy]")
    assert load_staged_config(_write(tmp_path, shy_only, dcfg), dcfg, _lcfg()).cash_variants == [
        "shy"
    ]


def test_loader_refuses_a_cash_yield_unlike_longrun(tmp_path):
    dcfg = load(tmp_path, GOOD_TCASH_ALL)
    with pytest.raises(ValueError, match="differs from longrun.yaml cash_real_yield"):
        load_staged_config(_write(tmp_path, STAGED_YAML, dcfg), dcfg, _lcfg(cash_real_yield=0.02))


@pytest.mark.parametrize("text", [None, "- a\n", "a: [\n"])
def test_loader_refuses_an_unreadable_file(tmp_path, text):
    dcfg = load(tmp_path, GOOD_TCASH_ALL)
    path = tmp_path / "staged_entry.yaml"
    if text is not None:
        path.write_text(text)
    with pytest.raises(ValueError, match="cannot be loaded"):
        load_staged_config(path, dcfg, _lcfg())


def test_shipped_config_loads():
    dcfg = load_decision_config(ROOT / "config" / "decision.yaml", CANDIDATES, stress_cfg(), END)
    lcfg = load_longrun_config(ROOT / "config" / "longrun.yaml", dcfg.sha256)
    scfg = load_staged_config(ROOT / "config" / "staged_entry.yaml", dcfg, lcfg)
    assert scfg.periods == [0, 6, 12, 24]
    assert scfg.portfolios == list("ABCDEFG")


# ---- runner (hand-computed)


def _run(returns, source, cash, withdraw, buy, n, begin=None):
    return run_staged(
        np.asarray(returns, dtype=float),
        np.asarray(source),
        np.asarray(cash, dtype=float),
        np.asarray(withdraw, dtype=float),
        np.asarray(buy),
        n,
        None if begin is None else np.asarray(begin),
    )


def test_cash_earns_between_tranches_and_the_last_tranche_takes_it_all():
    run = _run([[0.10, 0.10, 0.10]], [[0]], [[0.01] * 3], [[0, 0, 0]], [[0, -1, 1]], 2)
    # step 0: buy 0.5 -> held 0.55, cash 0.505; step 1: 0.605 + 0.51005;
    # step 2: buy all 0.51005 -> held 1.11505 x 1.1
    assert isinstance(run, StagedRun)
    assert run.values[0] == pytest.approx([1.055, 1.11505, 1.226555])
    assert run.depleted.tolist() == [0]


def test_withdrawals_come_from_cash_first():
    run = _run([[0, 1.0, 0]], [[0]], [[0, 0, 0]], [[0, 0.1, 0]], [[0, -1, 1]], 2)
    # step 1: 0.1 from cash (0.5 -> 0.4); invested 0.5 doubles -> 1.4
    # (from the invested part it would be 0.4 x 2 + 0.5 = 1.3)
    assert run.values[0] == pytest.approx([1.0, 1.4, 1.4])


def test_after_the_cash_withdrawals_come_from_tranches_proportionally():
    returns = [[0, 1.0, 0, 1.0], [0, 0, 0, 0]]
    run = _run(returns, [[0, 1]], [[0] * 4], [[0, 0, 0.3, 0]], [[0, 1, -1, -1]], 2)
    # step 1: tranches [1.0, 0.5]; step 2: 0.3 of 1.5 -> x 0.8 -> [0.8, 0.4];
    # step 3: tranche 0 doubles -> 2.0 (all from tranche 0 would give 1.9)
    assert run.values[0] == pytest.approx([1.0, 1.5, 1.2, 2.0])


def test_withdraw_then_tranche_and_a_short_cash_invests_what_is_left():
    returns = [[0, 0, 0], [0, 5.0, 0]]
    run = _run(returns, [[0, 1]], [[0] * 3], [[0.6, 0, 0.1]], [[0, 1, -1]], 2)
    # step 0: withdraw 0.6 first, then the tranche is min(0.5, 0.4) = 0.4;
    # tranche 1 gets 0 (its 500% return changes nothing); step 2: 0.1 from it
    assert run.values[0] == pytest.approx([0.4, 0.4, 0.3])


def test_withdrawals_exhaust_the_cash_before_the_last_tranche():
    returns = [[0, 0, 0], [0, 0, 0], [0, 0, 10.0]]
    w = [[0.3, 0.3, 0.3]]
    run = _run(returns, [[0, 1, 2]], [[0] * 3], w, [[0, 1, 2]], 3)
    # step 0: cash 0.7, buy 1/3; step 1: cash 0.0667 < 1/3, all of it bought;
    # step 2: 0.3 from the invested 0.4; tranche 2 is 0, its +1000% moot
    assert run.values[0] == pytest.approx([0.7, 0.4, 0.1])


def test_depletion_with_staged_cash():
    returns = [[0, 0, 1.0], [0, 0, 0]]
    run = _run(returns, [[0, 1]], [[0] * 3], [[0.7, 0.7, 0]], [[0, 1, -1]], 2)
    assert run.values[0].tolist() == [pytest.approx(0.3), 0.0, 0.0]
    assert run.depleted.tolist() == [2]


def test_cash_at_or_below_depleted_counts_as_zero():
    # step 0: withdraw 0.5 - 5e-10, buy the 0.5 tranche: 5e-10 of cash dust is left,
    # which counts as 0. Step 1: cash earns +1e9; dust kept would add 0.5.
    w = [[0.5 - DEPLETED / 2, 0]]
    run = _run([[0, 0]], [[0]], [[0, 1e9]], w, [[0, -1]], 2)
    assert run.values[0] == pytest.approx([0.5, 0.5])
    assert run.depleted.tolist() == [0]


def test_a_path_does_nothing_before_it_begins():
    r = [[0.1] * 4, [0.1] * 4]
    run = _run(
        r, [[0], [1]], [[0] * 4] * 2, [[0] * 4] * 2, [[0, -1, -1, -1], [-1, -1, 0, -1]], 1, [0, 2]
    )
    assert run.values[0] == pytest.approx([1.1, 1.21, 1.331, 1.4641])
    assert run.values[1] == pytest.approx([1.0, 1.0, 1.1, 1.21])


def test_runner_refuses_nan_in_a_live_path_only():
    r = [[0.1, np.nan, 0.1]]
    with pytest.raises(ValueError, match="NaN return"):
        _run(r, [[0]], [[0] * 3], [[0] * 3], [[0, -1, -1]], 1)
    run = _run([[np.nan, 0.1, 0.1]], [[0]], [[0] * 3], [[0] * 3], [[-1, 0, -1]], 1, [1])
    assert run.values[0] == pytest.approx([1.0, 1.1, 1.21])


def test_runner_refuses_bad_shapes():
    with pytest.raises(ValueError, match="source must have shape"):
        _run([[0.0]], [[0, 0, 0]], [[0]], [[0]], [[0]], 2)
    with pytest.raises(ValueError, match="beyond"):
        _run([[0.0]], [[0]], [[0]], [[0]], [[3]], 2)


def test_a_total_loss_after_the_tranche_empties_only_that_path():
    # path 0 buys everything at step 0, then loses 100%: empty after the returns
    returns = [[-1.0, 0.0], [0.1, 0.1]]
    buy = [[0, -1], [0, -1]]
    run = _run(returns, [[0], [1]], [[0] * 2] * 2, [[0] * 2] * 2, buy, 1)
    assert run.values[0].tolist() == [0.0, 0.0]
    assert run.values[1] == pytest.approx([1.1, 1.21])
    assert run.depleted.tolist() == [1, 0]


def test_tranches_never_bought_stay_in_cash_and_earn_the_cash_return():
    # 6 tranches, 3 steps: 1/6 bought each step, the other 3/6 never leaves cash.
    # cash: 5/6 x 1.01 = 0.841667; -1/6 = 0.675 x 1.01 = 0.68175;
    # -1/6 = 0.5150833 x 1.01 = 0.5202342. Invested stays 1/6, 2/6, 3/6 (0% returns).
    run = _run([[0.0] * 3], [[0]], [[0.01] * 3], [[0] * 3], [[0, 1, 2]], 6)
    assert run.values[0] == pytest.approx(
        [0.166667 + 0.841667, 0.333333 + 0.68175, 0.5 + 0.5202342], abs=1e-6
    )
    assert run.depleted.tolist() == [0]


# ---- schedules


def _bdays(start="2005-01-01", end="2018-12-31") -> pd.DatetimeIndex:
    return pd.bdate_range(start, end)


def test_starts_are_the_120_month_firsts_and_the_horizon_is_48_months():
    days = _bdays()
    firsts = month_firsts(days)
    starts = start_months(days, firsts)
    assert len(starts) == 120
    assert str(days[firsts[starts[0]]].to_period("M")) == "2005-01"
    assert str(days[firsts[starts[-1]]].to_period("M")) == "2014-12"
    horizon = horizon_positions(firsts, starts)
    assert days[horizon[0]] == pd.Timestamp("2008-12-31")
    assert days[horizon[-1]] == pd.Timestamp("2018-11-30")


def test_starts_refuse_missing_months_and_a_horizon_past_the_data():
    days = _bdays("2006-01-01")
    with pytest.raises(ValueError, match="no trading day in start month"):
        start_months(days, month_firsts(days))
    days = _bdays(end="2018-06-30")
    firsts = month_firsts(days)
    with pytest.raises(ValueError, match="runs past the data"):
        horizon_positions(firsts, start_months(days, firsts))


def test_a_calendar_month_with_no_trading_day_is_refused():
    days = _bdays()
    days = days[(days < "2016-03-01") | (days >= "2016-04-01")]
    with pytest.raises(ValueError, match="missing month 2016-03"):
        month_firsts(days)


def test_january_start_withdrawals_equal_monthly_withdrawals_exactly():
    days, index = _bdays(), cpi_series().loc[:END]
    firsts = month_firsts(days)
    for i0 in (0, 36, 108):
        begin = int(firsts[i0])
        out = historical_withdrawals(days, begin, 0.04, index)
        monthly = monthly_withdrawals(0.04, days[begin].year, END.year, index)
        expected = np.zeros(len(days))
        for pos in firsts[i0:]:
            expected[pos] = monthly[days[pos].year]
        assert np.array_equal(out, expected)


def test_other_starts_are_raised_on_each_anniversary_by_usable_cpi():
    days, index = _bdays(), cpi_series(monthly_growth=0.003).loc[:END]
    firsts = month_firsts(days)
    begin = int(firsts[2])  # 2005-03
    out = historical_withdrawals(days, begin, 0.05, index)
    a0, a12, a24 = days[firsts[2]], days[firsts[14]], days[firsts[26]]
    first = 0.05 / 12
    second = first * (1 + (usable_cpi(index, a12) / usable_cpi(index, a0) - 1))
    third = second * (1 + (usable_cpi(index, a24) / usable_cpi(index, a12) - 1))
    assert out[firsts[2]] == first
    assert out[firsts[13]] == first
    assert out[firsts[14]] == second
    assert out[firsts[25]] == second
    assert out[firsts[26]] == third
    assert out[:begin].sum() == 0
    assert np.count_nonzero(out) == len(firsts) - 2


def test_long_run_withdrawals_and_levels_follow_the_paths_inflation():
    pi = np.array([[0.01] * 12 + [0.0] * 12 + [0.02] * 3])
    w = longrun_withdrawals(pi, 0.06)
    assert (w[0, :12] == 0.005).all()
    assert w[0, 12] == pytest.approx(0.005 * 1.01**12)
    assert w[0, 24] == pytest.approx(0.005 * 1.01**12)
    levels = longrun_levels(pi)
    assert levels[0, 11] == pytest.approx(1.01**12)
    assert levels[0, -1] == pytest.approx(1.01**12 * 1.02**3)


# ---- historical view


@pytest.fixture(scope="module")
def setup(tmp_path_factory):
    dcfg = load(tmp_path_factory.mktemp("staged"), GOOD_TCASH_ALL)
    return dcfg, prices(), cpi_series()


def _cut(data, index):
    return {k: v.loc[:END] for k, v in data.items()}, index.loc[:END]


def _days(cut):
    trading = pd.DatetimeIndex(cut["close"].index)
    days = trading[trading >= research_start(trading, criteria())]
    return trading, days, month_firsts(days)


def _cost() -> float:
    return float(criteria()["costs"]["bps_per_unit_turnover"])


def test_each_historical_tranche_is_a_fresh_purchase_paying_the_entry_cost(setup):
    dcfg, data, index = setup
    cut, _ = _cut(data, index)
    _, days, firsts = _days(cut)
    p = {x.id: x for x in dcfg.portfolios}["A"]
    rows = tranche_returns(p, cut, days, days[firsts[:3]], _cost())
    for j in range(3):
        expected = portfolio_returns(p, cut, days[firsts[j]], _cost()).to_numpy()
        assert np.array_equal(rows[j, firsts[j] :], expected)
        assert (rows[j, : firsts[j]] == 0.0).all()
    free = tranche_returns(p, cut, days, days[firsts[:1]], 0.0)
    assert rows[0, 0] < free[0, 0]  # the entry cost is inside the first day


def test_daily_cash_variants(setup):
    dcfg, data, index = setup
    cut, known = _cut(data, index)
    known = known.copy()
    known.loc["2006-01-31"] *= 1.01  # perturb one value so the month read is checked
    trading, days, _ = _days(cut)
    by_id = {x.id: x for x in dcfg.portfolios}
    shy = daily_cash("shy", by_id["CASH"], cut, days, trading, known, _cost(), 0.01)
    ref = portfolio_returns(by_id["CASH"], cut, days[0], _cost()).to_numpy()
    assert np.array_equal(shy, ref)
    real = daily_cash("real_plus_1", by_id["CASH"], cut, days, trading, known, _cost(), 0.01)
    jan = days.to_period("M") == pd.Period("2006-01", freq="M")
    # January's inflation: usable CPI on 2006-01-31 over usable CPI on 2005-12-31
    growth = known.loc["2006-01-31"] / known.loc["2005-12-31"] * 1.01 ** (1 / 12)
    assert np.prod(1.0 + real[jan]) == pytest.approx(growth)


def test_historical_schedule_buys_each_tranche_on_its_month_first(monkeypatch):
    seen = {}

    def spy(returns, source, cash, withdraw, buy, n, begin):
        seen.update(source=source, buy=buy, n=n, begin=begin, cash=cash, withdraw=withdraw)
        return StagedRun(np.ones(withdraw.shape), np.zeros(len(withdraw), np.int64))

    monkeypatch.setattr(staged_mod, "run_staged", spy)
    days = _bdays()
    firsts = month_firsts(days)
    starts = np.array([0, 5])
    cash = np.vstack([np.zeros(len(days)), np.ones(len(days))])
    withdraw = np.arange(2 * 2 * len(days), dtype=float).reshape(1, 2, 2, len(days))[0]
    historical_run(np.zeros((12, len(days))), firsts, starts, cash, withdraw, 3)
    assert seen["n"] == 3
    assert seen["source"].tolist() == [[0, 1, 2], [5, 6, 7]] * 4
    assert seen["begin"].tolist() == [firsts[0], firsts[5]] * 4
    for p, i0 in enumerate([0, 5] * 4):
        assert np.flatnonzero(seen["buy"][p] >= 0).tolist() == list(firsts[i0 : i0 + 3])
        assert seen["buy"][p][firsts[i0 : i0 + 3]].tolist() == [0, 1, 2]
    # paths ordered (variant, rate, start)
    assert (seen["cash"][4:] == 1.0).all()
    assert (seen["cash"][:4] == 0.0).all()
    assert np.array_equal(seen["withdraw"][1], withdraw[0, 1])
    assert np.array_equal(seen["withdraw"][2], withdraw[1, 0])


def test_lump_sum_historical_equals_withdrawal_path_for_january_starts(setup):
    dcfg, data, index = setup
    cut, known = _cut(data, index)
    trading, days, firsts = _days(cut)
    by_id = {x.id: x for x in dcfg.portfolios}
    p = by_id["A"]
    starts = np.arange(0, 120, 12)
    tranche = tranche_returns(p, cut, days, days[firsts[:120]], _cost())
    cash = np.vstack(
        [
            daily_cash(v, by_id["CASH"], cut, days, trading, known, _cost(), 0.01)
            for v in ("shy", "real_plus_1")
        ]
    )
    withdraw = np.stack(
        [
            [historical_withdrawals(days, int(firsts[i]), r, known) for i in starts]
            for r in dcfg.rates
        ]
    )
    run = historical_run(tranche, firsts, starts, cash, withdraw, 0)
    n_r, n_s = len(dcfg.rates), len(starts)
    ends = []
    for si, i0 in enumerate(starts):
        b = int(firsts[i0])
        returns = portfolio_returns(p, cut, days[b], _cost())
        for ri, rate in enumerate(dcfg.rates):
            ref = withdrawal_path(
                returns, monthly_withdrawals(rate, days[b].year, END.year, known)
            ).values.to_numpy()
            for vi in range(2):
                row = (vi * n_r + ri) * n_s + si
                assert np.array_equal(run.values[row, b:], ref)
                assert (run.values[row, :b] == 1.0).all()
                ends.append(ref[-1])
    ends_arr = np.array(ends)
    assert (ends_arr != 1.0).any()  # the compared paths moved
    assert (ends_arr > DEPLETED).any()  # and not all of them are depleted


# ---- long-run view


def test_lump_sum_long_run_equals_run_paths_exactly():
    rng = np.random.default_rng(11)
    n_months = 120
    core = rng.normal(0.006, 0.05, n_months)
    shy = rng.normal(0.002, 0.003, n_months)
    pi = rng.normal(0.002, 0.003, n_months)
    idx = month_indices(block_starts(7, 300, 30, n_months), 12, n_months)
    for rate in (0.02, 0.05, 0.12):
        paths = run_paths(core, pi, idx, rate)
        w = longrun_withdrawals(pi[idx], rate)
        levels = longrun_levels(pi[idx])
        for cash in (shy, cash_assumption_returns(pi, 0.01)):
            run = longrun_run(core[idx], cash[idx], w, 0)
            assert np.array_equal(run.values, paths.nominal)
            assert np.array_equal(run.values / levels, paths.real)
            assert np.array_equal(run.depleted, paths.depleted)
        if rate == 0.12:
            assert paths.depleted.any()  # the depletion branch is exercised


def test_long_run_tranches_are_bought_monthly_at_no_cost():
    core = np.full((1, 3), 0.01)
    run = longrun_run(core, np.zeros((1, 3)), np.zeros((1, 3)), 2)
    # month 0: 0.5 invested x 1.01 + 0.5 cash; month 1: all in, x 1.01
    assert run.values[0] == pytest.approx([1.005, 1.01505, 1.0252005])


def test_long_run_refuses_a_period_longer_than_the_paths():
    with pytest.raises(ValueError, match="longer than"):
        longrun_run(np.zeros((1, 3)), np.zeros((1, 3)), np.zeros((1, 3)), 4)


# ---- measures


def _flat_cpi() -> pd.Series:
    return pd.Series(100.0, index=pd.date_range("2004-01-31", "2006-12-31", freq="ME"))


def test_path_measures_real_values_and_drawdown_to_the_horizon():
    days = pd.bdate_range("2005-01-03", periods=5)
    values = np.array([[1.1, 0.9, 1.2, 1.0, 1.3]])
    m = path_measures(values, np.array([0]), np.array([3]), days, _flat_cpi())
    assert m["real4"].tolist() == [1.0]
    assert m["real_end"].tolist() == [1.3]
    assert m["mdd"][0] == pytest.approx(1 - 0.9 / 1.1)  # 1.3 after the horizon is ignored


def test_path_measures_deflate_by_usable_cpi_and_count_the_start_as_a_peak():
    days = pd.bdate_range("2005-01-03", "2005-06-30")
    index = _flat_cpi().copy()
    index.loc["2005-05-31":] = 110.0
    values = np.full((1, len(days)), 0.95)
    h = len(days) - 1
    m = path_measures(values, np.array([0]), np.array([h]), days, index)
    assert m["real4"][0] == pytest.approx(0.95 / 1.1)
    assert m["mdd"][0] == pytest.approx(0.05)


def test_compare_and_lump_only():
    staged = {
        "real4": np.array([1.2, 0.8, 1.0]),
        "real_end": np.array([1.5, 1.0, 1.1]),
        "mdd": np.array([0.2, 0.3, 0.1]),
    }
    lump = {
        "real4": np.array([1.0, 1.0, 1.0]),
        "real_end": np.array([1.4, 1.2, 1.1]),
        "mdd": np.array([0.25, 0.2, 0.1]),
    }
    months = ["2005-01", "2005-02", "2005-03"]
    c = compare(staged, lump, months)
    assert c["above"] == pytest.approx(1 / 3)  # a tie is not above
    assert (c["gap_median"], c["gap_best"], c["gap_worst"]) == pytest.approx((0.0, 0.2, -0.2))
    assert c["mdd_worst"] == 0.3
    assert c["mdd_worst_diff"] == pytest.approx(0.1)
    assert c["worst_start"] == "2005-02"
    assert (c["end_gap_median"], c["end_gap_best"], c["end_gap_worst"]) == pytest.approx(
        (0.0, 0.1, -0.2)
    )
    lo = lump_only(lump, months)
    assert lo["mdd_worst"] == 0.25
    assert lo["worst_start"] == "2005-01"
    assert lo["above"] is None
    assert lo["gap_median"] is None
    assert lo["mdd_worst_diff"] is None
    assert set(lo) == set(c)


def test_longrun_measures():
    values = np.ones((4, 72))
    values[0, 30:] = 0.0
    values[:, 59] = [0.0, 1.0, 2.0, 3.0]
    values[:, 71] = [0.0, 2.0, 4.0, 6.0]
    levels = np.full((4, 72), 2.0)
    run = StagedRun(values, np.array([31, 0, 0, 0]))
    m = longrun_measures(run, levels, horizon_years=6)
    assert m == {"depleted": 0.25, "real_end_median": 1.5, "real_year5_median": 0.75}


def test_longrun_measures_count_only_depletion_within_the_horizon():
    values = np.ones((4, 72))
    levels = np.ones((4, 72))
    # horizon 5 years = 60 months: month 40 counts, 61 does not, 0 never depleted
    run = StagedRun(values, np.array([40, 61, 0, 60]))
    m = longrun_measures(run, levels, horizon_years=5)
    assert m["depleted"] == 0.5  # paths 0 and 3 (60 is within 12 * 5)


def test_longrun_measures_refuse_a_horizon_longer_than_the_paths():
    run = StagedRun(np.ones((2, 72)), np.zeros(2, dtype=int))
    with pytest.raises(ValueError, match="longer than"):
        longrun_measures(run, np.ones((2, 72)), horizon_years=7)


def test_path_measures_a_depleted_path_has_a_drawdown_of_exactly_one():
    days = pd.bdate_range("2005-01-03", periods=4)
    values = np.array([[1.2, 0.5, 0.0, 0.0]])
    m = path_measures(values, np.array([0]), np.array([3]), days, _flat_cpi())
    assert m["mdd"][0] == 1.0


def test_path_measures_ignore_values_before_the_begin_day():
    days = pd.bdate_range("2005-01-03", periods=6)
    # before begin (pos 2): 2.0 -> 0.5 would be a 75% drawdown; in window only
    # 1.0 (start peak) -> 0.8 -> 1.5 -> 1.2, so the drawdown is 1 - 1.2/1.5 = 0.2
    values = np.array([[2.0, 0.5, 0.8, 1.5, 1.2, 1.3]])
    m = path_measures(values, np.array([2]), np.array([4]), days, _flat_cpi())
    assert m["mdd"][0] == pytest.approx(0.2)


# ---- orchestration on offline data


def _scfg() -> StagedConfig:
    return StagedConfig(
        periods=[0, 6],
        cash_variants=["shy", "real_plus_1"],
        portfolios=["A", "G"],
        sha256="s" * 64,
    )


@pytest.fixture(scope="module")
def report(setup):
    dcfg, data, index = setup
    return run_staged_entry(_scfg(), dcfg, _lcfg(), data, index, criteria())


def test_report_shape_and_order(report, setup):
    dcfg, _, _ = setup
    n = len(dcfg.rates) * 2 * 2 * 2
    assert len(report["historical"]) == n
    assert len(report["longrun"]) == n
    keys = [(r["rate"], r["portfolio"], r["period"], r["variant"]) for r in report["historical"]]
    assert keys == [
        (rate, pid, per, v)
        for rate in dcfg.rates
        for pid in "AG"
        for per in (0, 6)
        for v in ("shy", "real_plus_1")
    ]
    assert keys == [
        (r["rate"], r["portfolio"], r["period"], r["variant"]) for r in report["longrun"]
    ]
    assert report["n_starts"] == 120
    assert (report["first_start"], report["last_start"]) == ("2005-01", "2014-12")
    assert report["horizon_months"] == 48
    assert report["n_months"] == 168
    assert report["n_paths"] == 50
    assert report["staged_sha256"] == "s" * 64
    assert report["longrun_sha256"] == L_SHA
    assert [p["id"] for p in report["portfolios"]] == ["A", "G"]


def test_lump_sum_rows_are_the_same_in_both_cash_variants(report):
    for view in ("historical", "longrun"):
        rows = {
            (r["rate"], r["portfolio"], r["variant"]): r for r in report[view] if r["period"] == 0
        }
        for (rate, pid, v), r in rows.items():
            if v == "shy":
                assert r == {**rows[(rate, pid, "real_plus_1")], "variant": "shy"}


def test_staged_rows_carry_every_measure(report):
    staged = [r for r in report["historical"] if r["period"] == 6]
    assert all(0.0 <= r["above"] <= 1.0 for r in staged)
    assert all(r["gap_worst"] <= r["gap_median"] <= r["gap_best"] for r in staged)
    assert all(r["worst_start"][:2] == "20" for r in staged)
    lump = [r for r in report["historical"] if r["period"] == 0]
    assert all(r["above"] is None and r["mdd_worst"] >= 0.0 for r in lump)
    assert all(0.0 <= r["depleted"] <= 1.0 for r in report["longrun"])


def test_run_refuses_rates_unlike_longrun(setup):
    dcfg, data, index = setup
    with pytest.raises(ValueError, match="withdrawal_rates"):
        run_staged_entry(_scfg(), dcfg, _lcfg(rates=[0.04]), data, index, criteria())
