"""Withdrawal rules (qrl.decision_rules, qrl.withdrawal_rules_report). Offline;
synthetic returns, prices and CPI only. Spec:
docs/methodology/withdrawal-rules.md ("Tests")."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from decision_helpers import CANDIDATES, END, ROOT, stress_cfg

from qrl.decision_config import load_decision_config
from qrl.decision_rules import (
    RULE_PARAMS,
    RULES,
    RulesConfig,
    fixed,
    floor_ceiling,
    guardrails,
    load_rules_config,
    month_starts,
    pct_of_balance,
    run_rule,
    skip_raise_after_loss,
)
from qrl.decision_withdraw import DEPLETED
from qrl.longrun import load_longrun_config

D_SHA, L_SHA = "aa" * 32, "bb" * 32
IDS = ["A", "B", "C", "D", "E", "F", "G", "CASH", "G-EW"]
RULES_BLOCK = """\
rules:
  fixed: {}
  skip_raise_after_loss: {}
  guardrails: {upper: 1.2, lower: 0.8, cut: 0.10, raise: 0.10}
  pct_of_balance: {}
  floor_ceiling: {max_real_cut: 0.025, max_real_raise: 0.05}
"""
RULES_YAML = (
    f'version: 1\ndecision_sha256: "{D_SHA}"\nlongrun_sha256: "{L_SHA}"\n'
    + RULES_BLOCK
    + "income_lines: [0.9, 0.8, 0.7]\nportfolios: [A, B, C, D, E, F, G, CASH]\n"
)


def _load_rules(
    tmp_path: Path, text: str = RULES_YAML, d_sha: str = D_SHA, l_sha: str = L_SHA
) -> RulesConfig:
    path = tmp_path / "withdrawal_rules.yaml"
    path.write_text(text)
    return load_rules_config(path, d_sha, l_sha, IDS)


# ---- config


def test_load_rules_config_reads_rules_lines_and_portfolios_in_order(tmp_path):
    cfg = _load_rules(tmp_path)
    assert list(cfg.rules) == [
        "fixed",
        "skip_raise_after_loss",
        "guardrails",
        "pct_of_balance",
        "floor_ceiling",
    ]
    assert cfg.rules["fixed"] == {}
    assert cfg.rules["guardrails"] == {"upper": 1.2, "lower": 0.8, "cut": 0.1, "raise": 0.1}
    assert cfg.rules["floor_ceiling"] == {"max_real_cut": 0.025, "max_real_raise": 0.05}
    assert cfg.income_lines == [0.9, 0.8, 0.7]
    assert cfg.portfolios == ["A", "B", "C", "D", "E", "F", "G", "CASH"]
    assert cfg.sha256 == hashlib.sha256(RULES_YAML.encode()).hexdigest()


REFUSALS = [
    ("version: 1\n", "version: 2\n", "unsupported version"),
    ("portfolios:", "extra: 1\nportfolios:", r"unknown key\(s\) \['extra'\]"),
    ("income_lines: [0.9, 0.8, 0.7]\n", "", r"missing key\(s\) \['income_lines'\]"),
    ("  pct_of_balance: {}\n", "  pct_of_wealth: {}\n", "unknown rule"),
    ("  fixed: {}\n", "  fixed: {cut: 0.1}\n", "needs parameters"),
    ("  fixed: {}\n", "  fixed: 1\n", "needs parameters"),
    ("cut: 0.10, raise: 0.10}", "cut: 0.10}", "needs parameters"),
    ("upper: 1.2", "upper: 1.0", "guardrails upper"),
    ("lower: 0.8", "lower: 1.0", "guardrails lower"),
    ("cut: 0.10", "cut: 0.0", "guardrails cut"),
    ("cut: 0.10", "cut: 1.0", "guardrails cut"),
    ("raise: 0.10", "raise: 1.5", "guardrails raise"),
    ("upper: 1.2", "upper: abc", "must be numbers"),
    ("max_real_cut: 0.025", "max_real_cut: -0.01", "floor_ceiling max_real_cut"),
    ("max_real_raise: 0.05", "max_real_raise: -0.05", "floor_ceiling max_real_raise"),
    (RULES_BLOCK, "rules: {}\n", "non-empty mapping"),
    ("income_lines: [0.9, 0.8, 0.7]", "income_lines: []", "non-empty list"),
    ("portfolios: [A, B, C, D, E, F, G, CASH]", "portfolios: []", "non-empty list"),
    ("upper: 1.2", "upper: .nan", "must be finite"),
    ("upper: 1.2", "upper: .inf", "must be finite"),
    ("lower: 0.8", "lower: -.inf", "must be finite"),
    ("max_real_cut: 0.025", "max_real_cut: .inf", "must be finite"),
    ("upper: 1.2", "upper: true", "must be numbers"),
    ("upper: 1.2", 'upper: "1.2"', "must be numbers"),
    ("upper: 1.2", "upper: null", "must be numbers"),
    ("income_lines: [0.9, 0.8, 0.7]", "income_lines: [0.9, abc]", r"income_lines.*numbers"),
    ("income_lines: [0.9, 0.8, 0.7]", "income_lines: [0.9, true]", r"income_lines.*numbers"),
    ("income_lines: [0.9, 0.8, 0.7]", 'income_lines: [0.9, "0.8"]', r"income_lines.*numbers"),
    ("income_lines: [0.9, 0.8, 0.7]", "income_lines: [0.9, .nan]", r"income_lines.*finite"),
    ("income_lines: [0.9, 0.8, 0.7]", "income_lines: 0.9", r"`income_lines` must be a non-empty"),
    ("income_lines: [0.9, 0.8, 0.7]", "income_lines: [0.9, 0.9]", r"duplicate `income_lines`"),
    ("income_lines: [0.9, 0.8, 0.7]", "income_lines: [0.5, 0.50]", r"duplicate `income_lines`"),
    ("portfolios: [A, B, C, D, E, F, G, CASH]", "portfolios: [A, A]", r"duplicate `portfolios`"),
    (
        "portfolios: [A, B, C, D, E, F, G, CASH]",
        "portfolios: A",
        r"`portfolios` must be a non-empty",
    ),
    ("income_lines: [0.9, 0.8, 0.7]", "income_lines: [0.9, 1.0]", r"income line\(s\) \[1\.0\]"),
    ("income_lines: [0.9, 0.8, 0.7]", "income_lines: [0.0, 0.8]", r"income line\(s\) \[0\.0\]"),
    ("portfolios: [A, B, C, D, E, F, G, CASH]", "portfolios: [A, ZZ]", "not in decision.yaml"),
]


@pytest.mark.parametrize(("old", "new", "match"), REFUSALS)
def test_load_rules_config_refuses(tmp_path, old, new, match):
    assert old in RULES_YAML
    with pytest.raises(ValueError, match=match):
        _load_rules(tmp_path, RULES_YAML.replace(old, new, 1))


@pytest.mark.parametrize("text", ["rules: [\n", "- 1\n", ""])
def test_load_rules_config_refuses_an_unreadable_file(tmp_path, text):
    with pytest.raises(ValueError, match="cannot be loaded"):
        _load_rules(tmp_path, text)


def test_load_rules_config_refuses_a_missing_file(tmp_path):
    with pytest.raises(ValueError, match="cannot be loaded"):
        load_rules_config(tmp_path / "nope.yaml", D_SHA, L_SHA, IDS)


def test_load_rules_config_refuses_a_changed_decision_yaml(tmp_path):
    with pytest.raises(ValueError, match=re.escape("decision.yaml changed")):
        _load_rules(tmp_path, d_sha="cc" * 32)


def test_load_rules_config_refuses_a_changed_longrun_yaml(tmp_path):
    with pytest.raises(ValueError, match=re.escape("longrun.yaml changed")):
        _load_rules(tmp_path, l_sha="cc" * 32)


def test_shipped_config_loads_against_the_shipped_decision_and_longrun_files():
    dcfg = load_decision_config(ROOT / "config" / "decision.yaml", CANDIDATES, stress_cfg(), END)
    lcfg = load_longrun_config(ROOT / "config" / "longrun.yaml", dcfg.sha256)
    cfg = load_rules_config(
        ROOT / "config" / "withdrawal_rules.yaml",
        dcfg.sha256,
        lcfg.sha256,
        [p.id for p in dcfg.portfolios],
    )
    assert list(cfg.rules) == list(RULE_PARAMS)
    assert cfg.income_lines == [0.9, 0.8, 0.7]
    assert cfg.portfolios == ["A", "B", "C", "D", "E", "F", "G", "CASH"]


# ---- January functions

GUARD = {"upper": 1.2, "lower": 0.8, "cut": 0.1, "raise": 0.1}
BANDS = {"max_real_cut": 0.025, "max_real_raise": 0.05}
PARAMS: dict[str, dict[str, float]] = {
    "fixed": {},
    "skip_raise_after_loss": {},
    "guardrails": GUARD,
    "pct_of_balance": {},
    "floor_ceiling": BANDS,
}


def _a(*xs: float) -> np.ndarray:
    return np.array(xs, dtype=float)


def test_rules_and_parameters_are_the_spec_set_in_spec_order():
    assert list(RULES) == list(PARAMS)
    assert list(RULE_PARAMS) == list(PARAMS)
    assert {k: set(v) for k, v in RULE_PARAMS.items()} == {k: set(v) for k, v in PARAMS.items()}


def test_fixed_raises_last_years_amount_by_cpi():
    out = fixed(_a(0.01, 0.02), _a(1.03, 1.0), _a(1.0, 0.5), _a(-0.2, 0.1), _a(0.12, 0.12), {})
    np.testing.assert_allclose(out, [0.0103, 0.02], rtol=1e-12)


def test_skip_raise_after_loss_keeps_the_amount_only_after_a_negative_year():
    # prior-year returns -1% (skip), 0% (not negative: raise), +20% (raise)
    out = skip_raise_after_loss(
        _a(0.01, 0.01, 0.01),
        _a(1.05, 1.05, 1.05),
        _a(1, 1, 1),
        _a(-0.01, 0.0, 0.2),
        _a(0.12, 0.12, 0.12),
        {},
    )
    np.testing.assert_allclose(out, [0.01, 0.0105, 0.0105], rtol=1e-12)


def test_guardrails_cut_keep_and_raise():
    # q = 12 x 0.01 / V = 0.12 / V against 1.2 x 0.12 = 0.144 and 0.8 x 0.12 = 0.096:
    # V 0.7 -> q 0.171 (cut 10%), V 1.0 -> q 0.12 (keep), V 1.6 -> q 0.075 (raise 10%)
    out = guardrails(
        _a(0.01, 0.01, 0.01),
        _a(1, 1, 1),
        _a(0.7, 1.0, 1.6),
        _a(0, 0, 0),
        _a(0.12, 0.12, 0.12),
        GUARD,
    )
    np.testing.assert_allclose(out, [0.009, 0.01, 0.011], rtol=1e-12)


def test_guardrails_test_the_cpi_raised_amount():
    # fixed amount 0.01 x 1.25 = 0.0125; V 1.0: q = 0.15 > 0.144 -> cut to 0.01125
    out = guardrails(_a(0.01), _a(1.25), _a(1.0), _a(0.0), _a(0.12), GUARD)
    np.testing.assert_allclose(out, [0.01125], rtol=1e-12)


def test_pct_of_balance_is_rate_times_value_over_twelve():
    out = pct_of_balance(_a(0.01, 0.01), _a(1.1, 1.1), _a(0.9, 1.2), _a(0, 0), _a(0.04, 0.05), {})
    np.testing.assert_allclose(out, [0.003, 0.005], rtol=1e-12)


def test_floor_ceiling_lower_clamp_inside_and_upper_clamp():
    # prev x cpi = 0.0102: floor 0.0102 x 0.975 = 0.009945, ceiling 0.0102 x 1.05 = 0.01071;
    # rate x V / 12 = 0.005 (below the floor), 0.0103 (inside), 0.02 (above the ceiling)
    out = floor_ceiling(
        _a(0.01, 0.01, 0.01),
        _a(1.02, 1.02, 1.02),
        _a(0.5, 1.03, 2.0),
        _a(0, 0, 0),
        _a(0.12, 0.12, 0.12),
        BANDS,
    )
    np.testing.assert_allclose(out, [0.009945, 0.0103, 0.01071], rtol=1e-12)


@pytest.mark.parametrize("rule", list(PARAMS))
def test_every_rule_takes_the_scalar_case_as_a_length_one_array(rule):
    out = RULES[rule](_a(0.01), _a(1.02), _a(1.0), _a(0.05), _a(0.04), PARAMS[rule])
    assert out.shape == (1,)


PREV = np.array([[0.01, 0.012, 0.02], [0.005, 0.01, 0.03]])
CPI = np.array([[1.02, 1.05, 1.0], [1.03, 1.01, 1.04]])
VALUE = np.array([[0.7, 1.0, 1.6], [0.4, 2.0, 0.9]])
PRIOR = np.array([[-0.1, 0.0, 0.2], [0.05, -0.02, 0.3]])
RATE2D = np.array([[0.12, 0.12, 0.12], [0.04, 0.06, 0.12]])


def _one_by_one(rule, prev, cpi, value, prior, rate):
    """Each element through the rule as a length-1 array, the scalar case."""
    return np.array(
        [
            RULES[rule](_a(p), _a(c), _a(v), _a(r), _a(t), PARAMS[rule])[0]
            for p, c, v, r, t in zip(
                prev.ravel(), cpi.ravel(), value.ravel(), prior.ravel(), rate.ravel(), strict=True
            )
        ]
    ).reshape(prev.shape)


@pytest.mark.parametrize("rule", list(PARAMS))
def test_every_rule_keeps_the_shape_and_matches_the_scalar_case(rule):
    for prev, cpi, value, prior, rate in [
        (PREV[0], CPI[0], VALUE[0], PRIOR[0], RATE2D[0]),  # (n,)
        (PREV, CPI, VALUE, PRIOR, RATE2D),  # (paths, n)
        (PREV, CPI, VALUE, PRIOR, np.full(PREV.shape, 0.05)),
    ]:
        out = RULES[rule](prev, cpi, value, prior, rate, PARAMS[rule])
        assert out.shape == prev.shape
        np.testing.assert_allclose(
            out, _one_by_one(rule, prev, cpi, value, prior, rate), rtol=1e-12
        )


@pytest.mark.parametrize("rule", list(PARAMS))
def test_every_rule_takes_a_scalar_rate_with_array_inputs(rule):
    out = RULES[rule](PREV, CPI, VALUE, PRIOR, 0.05, PARAMS[rule])  # type: ignore[arg-type]
    assert out.shape == PREV.shape
    np.testing.assert_allclose(
        out, _one_by_one(rule, PREV, CPI, VALUE, PRIOR, np.full(PREV.shape, 0.05)), rtol=1e-12
    )


def test_guardrails_cuts_when_the_value_is_zero():
    # amount > 0 over value 0 is q = inf, above the upper rail: cut, no warning
    with np.errstate(all="raise"):
        out = guardrails(_a(0.01), _a(1.0), _a(0.0), _a(0.0), _a(0.12), GUARD)
    np.testing.assert_allclose(out, [0.009], rtol=1e-12)


def test_guardrails_does_not_hide_a_nan_value():
    out = guardrails(_a(0.01), _a(1.0), _a(np.nan), _a(0.0), _a(0.12), GUARD)
    assert out[0] == 0.01  # NaN q fails both strict comparisons; it is not turned into a cut


def test_guardrails_keep_the_amount_exactly_on_either_rail():
    # amount 1, value 12: q = 1.0; upper x rate = 2.0 x 0.5 = 1.0, lower x rate = 0.5 x 2.0 = 1.0
    on_upper = {"upper": 2.0, "lower": 0.1, "cut": 0.1, "raise": 0.1}
    on_lower = {"upper": 9.0, "lower": 0.5, "cut": 0.1, "raise": 0.1}
    assert guardrails(_a(1), _a(1), _a(12), _a(0), _a(0.5), on_upper)[0] == 1.0
    assert guardrails(_a(1), _a(1), _a(12), _a(0), _a(2.0), on_lower)[0] == 1.0


def test_floor_ceiling_keeps_a_target_exactly_on_a_band_edge():
    bands = {"max_real_cut": 0.5, "max_real_raise": 0.5}  # edges 0.5 and 1.5 around 1.0
    out = floor_ceiling(_a(1, 1), _a(1, 1), _a(12, 12), _a(0, 0), _a(0.5, 1.5), bands)
    np.testing.assert_array_equal(out, [0.5, 1.5])


def test_pct_of_balance_ignores_prev_cpi_and_prior():
    a = pct_of_balance(_a(0.01), _a(1.1), _a(0.9), _a(-0.3), _a(0.04), {})
    b = pct_of_balance(_a(7.0), _a(0.5), _a(0.9), _a(0.4), _a(0.04), {})
    np.testing.assert_array_equal(a, b)


# ---- runner

HAND_R = np.zeros(37)
HAND_R[[11, 23, 35]] = [-0.2, 0.5, 1.0]  # a loss in year 1, gains in years 2 and 3
HAND_CPI = {12: 1.1, 24: 1.1, 36: 1.1}  # CPI +10% each year
# Rate 12% (0.01 a month). Returns are zero except the last month of each year,
# so the value at a decision is (V_before - 12 x w) x (1 + that month's return):
# V at month 12 = (1 - 0.12) x 0.8 = 0.704.
HAND = {
    "fixed": [0.01 * 1.1, 0.01 * 1.1**2, 0.01 * 1.1**3],
    # year 1 lost 20%: no raise; years 2 and 3 gained: normal raise
    "skip_raise_after_loss": [0.01, 0.01 * 1.1, 0.01 * 1.1**2],
    # month 12: q = 12 x 0.011 / 0.704 = 0.1875 > 0.144, cut;
    # month 24: V = (0.704 - 12 x 0.0099) x 1.5 = 0.8778, q = 12 x 0.01089 / 0.8778 = 0.1489 > 0.144, cut;
    # month 36: V = (0.8778 - 12 x 0.009801) x 2 = 1.520376, q = 12 x 0.0107811 / 1.520376 = 0.0851 < 0.096, raise
    "guardrails": [0.01 * 1.1 * 0.9, 0.01 * (1.1 * 0.9) ** 2, 0.01 * (1.1 * 0.9) ** 2 * 1.1 * 1.1],
    # w = 0.12 x V / 12: V12 = 0.704; V24 = (0.704 - 0.08448) x 1.5 = 0.92928;
    # V36 = (0.92928 - 0.1115136) x 2 = 1.6355328
    "pct_of_balance": [0.00704, 0.0092928, 0.016355328],
    # month 12: 0.00704 < floor 0.011 x 0.975; month 24: V = 0.86295, 0.0086295 < floor
    # 0.0117975 x 0.975; month 36: V = 1.4498385, 0.0144984 > ceiling 0.01265282 x 1.05
    "floor_ceiling": [
        0.01 * 1.1 * 0.975,
        0.01 * (1.1 * 0.975) ** 2,
        0.01 * (1.1 * 0.975) ** 2 * 1.1 * 1.05,
    ],
}


def _monthly(r, cpi_at, rate, rule="fixed"):
    paths = np.atleast_2d(np.asarray(r, dtype=float))
    return run_rule(rule, PARAMS[rule], paths, np.ones(paths.shape[1], dtype=bool), cpi_at, rate)


@pytest.mark.parametrize("rule", list(HAND))
def test_january_amounts_worked_by_hand(rule):
    run = _monthly(HAND_R, HAND_CPI, 0.12, rule)
    np.testing.assert_allclose(run.paid[0, :12], 0.01, rtol=1e-12)  # the first year has no decision
    np.testing.assert_allclose(run.paid[0, [12, 24, 36]], HAND[rule], rtol=1e-9)
    np.testing.assert_array_equal(run.paid[0, 12:24], run.paid[0, 12])  # one amount per year
    assert run.depleted[0] == 0


def test_value_at_the_threshold_after_the_withdrawal_is_depleted_with_no_return():
    # w = 1 - 5e-10 leaves 5e-10 <= DEPLETED: depleted in month 1, the +900% return is
    # never applied, and the income that month is the whole remaining balance (1.0)
    run = _monthly([9.0, 0.0], {}, 12 * (1 - 5e-10))
    assert run.depleted[0] == 1
    assert (run.values == 0.0).all()
    np.testing.assert_array_equal(run.paid[0], [1.0, 0.0])


def test_value_just_above_the_threshold_survives():
    run = _monthly([0.0], {}, 12 * (1 - 4e-9))
    assert run.depleted[0] == 0
    assert run.values[0, 0] > DEPLETED


def test_depletion_by_the_withdrawal_pays_only_the_remaining_balance():
    # month 1: 1.0 - 0.6 = 0.4; month 2: 0.4 - 0.6 < 0 -> depleted, income 0.4
    run = _monthly([0.0, 0.0, 0.0], {}, 7.2)
    assert run.depleted[0] == 2
    np.testing.assert_allclose(run.paid[0], [0.6, 0.4, 0.0], rtol=1e-12)
    np.testing.assert_array_equal(run.values[0, 1:], [0.0, 0.0])


def test_depletion_by_the_return_pays_the_full_amount():
    # month 1: (1.0 - 0.5) x (1 - 1.0) = 0 -> depleted by the return; 0.5 was paid in full
    run = _monthly([-1.0, 0.5], {}, 6.0)
    assert run.depleted[0] == 1
    np.testing.assert_array_equal(run.paid[0], [0.5, 0.0])
    np.testing.assert_array_equal(run.values[0], [0.0, 0.0])


def test_nothing_is_paid_after_depletion_even_at_a_decision():
    run = _monthly(np.r_[-1.0, np.zeros(24)], {12: 1.1, 24: 1.1}, 0.12)
    assert run.depleted[0] == 1
    assert (run.paid[0, 1:] == 0.0).all()
    assert (run.values[0] == 0.0).all()


def test_a_rule_is_never_called_on_a_depleted_path(monkeypatch):
    seen = []

    def spy(prev, cpi, value, prior, rate, params):
        seen.append(value.copy())
        return prev * cpi

    monkeypatch.setitem(RULES, "fixed", spy)
    r = np.zeros((2, 13))
    r[0, 0] = -1.0  # path 0 is emptied in month 1; path 1 survives to the decision
    run = run_rule("fixed", {}, r, np.ones(13, dtype=bool), {12: 1.1}, 0.12)
    assert list(run.depleted) == [1, 0]
    assert len(seen) == 1
    np.testing.assert_allclose(seen[0], [0.88])
    np.testing.assert_allclose(run.paid[1, 12], 0.011, rtol=1e-12)


def test_daily_steps_withdraw_on_each_months_first_trading_day_and_count_months():
    idx = pd.bdate_range("2005-01-03", "2005-03-31")
    starts = month_starts(idx)
    assert list(idx[starts]) == list(pd.to_datetime(["2005-01-03", "2005-02-01", "2005-03-01"]))
    r = np.zeros(len(idx))
    r[idx.get_loc(pd.Timestamp("2005-02-15"))] = -1.0
    run = run_rule("fixed", {}, r[None, :], starts, {}, 0.12)
    assert run.values[0, idx.get_loc(pd.Timestamp("2005-02-14"))] == pytest.approx(0.98)
    assert run.depleted[0] == 2  # emptied by a day's return in February: month 2
    np.testing.assert_allclose(run.paid[0], [0.01, 0.01, 0.0], rtol=1e-12)


def test_run_rule_refuses_a_nan_return():
    with pytest.raises(ValueError, match="NaN"):
        _monthly([0.0, np.nan], {}, 0.04)


def test_run_rule_refuses_a_first_step_that_is_not_a_month_start():
    with pytest.raises(ValueError, match="month_start"):
        run_rule("fixed", {}, np.zeros((1, 2)), np.array([False, True]), {}, 0.04)


def test_run_rule_refuses_an_unknown_rule():
    with pytest.raises(ValueError, match="unknown rule"):
        run_rule("nope", {}, np.zeros((1, 2)), np.ones(2, dtype=bool), {}, 0.04)
