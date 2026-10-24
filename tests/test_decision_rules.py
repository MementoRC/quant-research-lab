"""Withdrawal rules (qrl.decision_rules, qrl.withdrawal_rules_report). Offline;
synthetic returns, prices and CPI only. Spec:
docs/methodology/withdrawal-rules.md ("Tests")."""

from __future__ import annotations

import hashlib
import re
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from decision_helpers import CANDIDATES, END, ROOT, criteria, load, prices, stress_cfg
from decision_helpers import cpi as cpi_series

from qrl.decision import withdrawal_rows
from qrl.decision_config import load_decision_config
from qrl.decision_rules import (
    RULE_PARAMS,
    RULES,
    RuleRun,
    RulesConfig,
    _historical_row,
    fixed,
    floor_ceiling,
    guardrails,
    historical_cpi,
    historical_measures,
    historical_run,
    load_rules_config,
    longrun_cpi,
    longrun_measures,
    month_label,
    month_starts,
    pct_of_balance,
    run_rule,
    run_withdrawal_rules,
    skip_raise_after_loss,
)
from qrl.decision_withdraw import DEPLETED, monthly_withdrawals, withdrawal_path
from qrl.longrun import (
    LongrunConfig,
    block_starts,
    load_longrun_config,
    month_indices,
    run_longrun,
    run_paths,
)
from qrl.withdrawal_rules_report import render_markdown

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


# ---- runner input checks


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_run_rule_refuses_a_non_finite_rate(bad):
    with pytest.raises(ValueError, match="rate must be finite"):
        _monthly([0.0, 0.0], {}, bad)


@pytest.mark.parametrize("bad", [np.nan, np.inf])
def test_run_rule_refuses_a_non_finite_cpi(bad):
    with pytest.raises(ValueError, match="cpi.*finite"):
        _monthly([0.0, 0.0], {1: bad}, 0.04)


def test_run_rule_refuses_a_wrong_length_rate_or_cpi():
    r = np.zeros((3, 2))
    ones = np.ones(2, dtype=bool)
    with pytest.raises(ValueError, match=r"rate must be a scalar or \(n_paths,\)"):
        run_rule("fixed", {}, r, ones, {}, np.array([0.04, 0.05]))
    with pytest.raises(ValueError, match=r"cpi.*must be a scalar or \(n_paths,\)"):
        run_rule("fixed", {}, r, ones, {1: np.array([1.0, 1.1])}, 0.04)
    with pytest.raises(ValueError, match=r"rate must be a scalar or \(n_paths,\)"):
        run_rule("fixed", {}, r, ones, {}, np.full((3, 1), 0.04))


def test_run_rule_shape_errors_name_the_shapes():
    with pytest.raises(ValueError, match=r"\(paths, steps\).*\(3,\)"):
        run_rule("fixed", {}, np.zeros(3), np.ones(3, dtype=bool), {}, 0.04)
    with pytest.raises(ValueError, match=r"one flag per step.*\(3,\).*\(2, 2\)"):
        run_rule("fixed", {}, np.zeros((2, 2)), np.ones(3, dtype=bool), {}, 0.04)


def test_run_rule_refuses_zero_steps_cleanly():
    with pytest.raises(ValueError, match="at least one step"):
        run_rule("fixed", {}, np.zeros((1, 0)), np.zeros(0, dtype=bool), {}, 0.04)


def test_month_starts_refuses_an_unsorted_index():
    idx = pd.DatetimeIndex(["2005-01-04", "2005-01-03"])
    with pytest.raises(ValueError, match="sorted"):
        month_starts(idx)


def test_month_starts_on_a_weekend_first_and_a_holiday_skipped_first_day():
    # 2005-02-01 is a (skipped) holiday, 2005-05-01 is a Sunday; March is absent
    idx = pd.DatetimeIndex(
        ["2005-01-28", "2005-01-31", "2005-02-02", "2005-02-03", "2005-04-29", "2005-05-02"]
        + ["2005-05-03"]
    )
    starts = month_starts(idx)
    assert list(starts) == [True, False, True, False, True, True, False]
    assert list(idx[starts]) == list(
        pd.to_datetime(["2005-01-28", "2005-02-02", "2005-04-29", "2005-05-02"])
    )
    run = run_rule("fixed", {}, np.zeros((1, len(idx))), starts, {}, 0.12)
    assert run.paid.shape == (1, 4)


def test_run_rule_does_not_mutate_its_inputs():
    r = np.array([[0.01, -0.02, 0.03, 0.0], [0.0, 0.0, -1.0, 0.0]])
    rate = np.array([0.12, 0.06])
    cpi = np.array([1.1, 1.2])
    r0, rate0, cpi0 = r.copy(), rate.copy(), cpi.copy()
    starts = np.ones(4, dtype=bool)
    run_rule("guardrails", GUARD, r, starts, {2: cpi}, rate)
    np.testing.assert_array_equal(r, r0)
    np.testing.assert_array_equal(rate, rate0)
    np.testing.assert_array_equal(cpi, cpi0)


def test_run_rule_depleted_is_an_int64_with_zero_meaning_never():
    run = _monthly([-1.0, 0.0], {}, 0.12)
    assert run.depleted.dtype == np.int64
    assert run.depleted[0] == 1
    assert _monthly([0.0, 0.0], {}, 0.12).depleted[0] == 0


# ---- runner: dead paths are masked, mixed paths equal their single-path runs


def test_a_rule_gets_only_the_surviving_paths_values_and_a_dead_path_stays_zero(monkeypatch):
    calls = []

    def spy(prev, cpi, value, prior, rate, params):
        calls.append((prev.copy(), cpi.copy(), value.copy(), prior.copy(), rate.copy()))
        return value * 0.01  # depends on the value

    monkeypatch.setitem(RULES, "fixed", spy)
    r = np.zeros((2, 13))
    r[0, 0] = -1.0  # path 0 is paid in month 1, then emptied; path 1 survives
    run = run_rule(
        "fixed",
        {},
        r,
        np.ones(13, dtype=bool),
        {12: np.array([1.3, 1.1])},
        np.array([0.12, 0.24]),
    )
    assert list(run.depleted) == [1, 0]
    assert len(calls) == 1
    prev, cpi, value, prior, rate = calls[0]
    assert all(len(a) == 1 for a in calls[0])
    np.testing.assert_allclose(prev, [0.02])
    np.testing.assert_allclose(cpi, [1.1])
    np.testing.assert_allclose(value, [1.0 - 12 * 0.02])
    np.testing.assert_allclose(prior, [0.0], atol=1e-15)
    np.testing.assert_allclose(rate, [0.24])
    np.testing.assert_allclose(run.paid[1, 12], 0.76 * 0.01, rtol=1e-12)
    assert run.paid[0, 0] == pytest.approx(0.01)
    assert (run.paid[0, 1:] == 0.0).all()
    assert (run.values[0] == 0.0).all()


def _mixed_returns():
    rng = np.random.default_rng(7)
    r = rng.normal(0.004, 0.04, size=(4, 40))
    r[2, :6] = -0.1  # rate 1.0 below: path 2 is emptied before the decision at month 12
    r[3] = -1.0  # path 3 is emptied in month 1
    return r


MIXED_RATE = np.array([0.04, 0.12, 1.0, 0.08])
MIXED_CPI = {
    12: np.array([1.02, 1.03, 1.04, 1.05]),
    24: np.array([1.01, 1.06, 1.02, 1.03]),
    36: np.array([1.03, 1.02, 1.01, 1.04]),
}


@pytest.mark.parametrize("rule", list(PARAMS))
def test_a_mixed_run_equals_each_paths_single_run(rule):
    r = _mixed_returns()
    starts = np.ones(40, dtype=bool)
    both = run_rule(rule, PARAMS[rule], r, starts, MIXED_CPI, MIXED_RATE)
    assert both.depleted[2] in range(1, 12)  # gone before the first decision
    assert both.depleted[3] == 1
    assert both.depleted[0] == 0
    for i in range(len(r)):
        cpi_i = {m: v[i] for m, v in MIXED_CPI.items()}
        one = run_rule(rule, PARAMS[rule], r[i : i + 1], starts, cpi_i, MIXED_RATE[i])
        np.testing.assert_array_equal(both.values[i], one.values[0])
        np.testing.assert_array_equal(both.paid[i], one.paid[0])
        assert both.depleted[i] == one.depleted[0]


@pytest.mark.parametrize("rule", list(PARAMS))
def test_every_path_depleted_before_a_decision_is_fine(rule):
    r = np.zeros((2, 14))
    r[:, 0] = -1.0
    run = run_rule(rule, PARAMS[rule], r, np.ones(14, dtype=bool), {12: 1.1}, [0.12, 0.2])
    assert list(run.depleted) == [1, 1]
    assert (run.values == 0.0).all()
    assert (run.paid[:, 1:] == 0.0).all()
    np.testing.assert_allclose(run.paid[:, 0], [0.01, 0.2 / 12])


# ---- runner: values exactly at DEPLETED


def test_a_value_exactly_at_depleted_after_the_withdrawal_is_depleted(monkeypatch):
    import qrl.decision_rules as dr

    w = 6.0 / 12
    monkeypatch.setattr(dr, "DEPLETED", 1.0 - w)
    run = _monthly([5.0, 0.0], {}, 6.0)
    assert run.depleted[0] == 1  # 0.5 <= 0.5: no +500% return
    assert (run.values == 0.0).all()
    np.testing.assert_array_equal(run.paid[0], [1.0, 0.0])  # the remaining balance
    monkeypatch.setattr(dr, "DEPLETED", np.nextafter(1.0 - w, 0.0))
    assert _monthly([0.0], {}, 6.0).depleted[0] == 0  # one ulp above: survives


def test_a_value_exactly_at_depleted_after_the_return_is_depleted(monkeypatch):
    import qrl.decision_rules as dr

    monkeypatch.setattr(dr, "DEPLETED", 0.25)  # (1 - 0.5) x (1 - 0.5) = 0.25
    run = _monthly([-0.5, 0.0], {}, 6.0)
    assert run.depleted[0] == 1
    np.testing.assert_array_equal(run.paid[0], [0.5, 0.0])  # the full amount
    assert (run.values == 0.0).all()
    monkeypatch.setattr(dr, "DEPLETED", np.nextafter(0.25, 0.0))
    assert _monthly([-0.5], {}, 6.0).depleted[0] == 0  # one ulp above: survives


# ---- views, and exact equality with the existing code


def _daily(seed, mu=0.0003, sigma=0.01, start="2005-01-03", end="2008-12-31") -> pd.Series:
    idx = pd.bdate_range(start, end)
    return pd.Series(np.random.default_rng(seed).normal(mu, sigma, len(idx)), index=idx)


def _varying_cpi(seed: int = 3) -> pd.Series:
    """As decision_helpers.cpi (availability-dated) but with varying monthly
    growth, one negative month included, so every January ratio differs."""
    obs = pd.date_range("1995-01-01", "2021-12-01", freq="MS")
    growth = np.random.default_rng(seed).normal(0.003, 0.004, len(obs))
    growth[100] = -0.01
    values = 100.0 * np.cumprod(1.0 + growth)
    return pd.Series(values, index=obs + pd.offsets.MonthEnd(2), name="CPIAUCNS")


def test_historical_decisions_are_every_january_after_the_first_month():
    index = cpi_series()
    assert sorted(historical_cpi(pd.period_range("2005-01", "2007-03", freq="M"), index)) == [
        12,
        24,
    ]
    assert sorted(historical_cpi(pd.period_range("2005-06", "2007-03", freq="M"), index)) == [
        7,
        19,
    ]


def test_historical_cpi_factor_is_the_one_monthly_withdrawals_applies():
    index = _varying_cpi()
    amounts = monthly_withdrawals(0.12, 2005, 2006, index)
    factor = historical_cpi(pd.period_range("2005-01", "2006-12", freq="M"), index)[12]
    assert amounts[2005] * factor == amounts[2006]


def test_fixed_rule_equals_withdrawal_path_exactly():
    # Compares the value series and the depletion month only, not the income in
    # the depletion month. Random returns never land in the 1e-9 window where
    # run_paths and the spec differ (Open question 1).
    rets, index = _daily(1), _varying_cpi()
    ratios = historical_cpi(pd.period_range("2005-01", "2008-12", freq="M"), index)
    assert len({round(v, 9) for v in ratios.values()}) == len(ratios)  # years differ
    rates = [0.04, 0.5]
    run, months = historical_run(rets, index, rates, "fixed", {})
    ran_out = []
    for i, rate in enumerate(rates):
        path = withdrawal_path(rets, monthly_withdrawals(rate, 2005, 2008, index))
        np.testing.assert_array_equal(run.values[i], path.values.to_numpy())
        assert month_label(int(run.depleted[i]), months) == path.depleted
        ran_out.append(path.depleted is not None)
    assert ran_out == [False, True]  # both the surviving and the depleting branch are compared


def test_longrun_decisions_are_every_12_months_from_month_13():
    cpi_at, levels = longrun_cpi(np.full((2, 36), 0.01))
    assert sorted(cpi_at) == [12, 24]
    np.testing.assert_allclose(cpi_at[12], 1.01**12, rtol=1e-12)
    np.testing.assert_allclose(levels[:, -1], 1.01**36, rtol=1e-12)


def test_fixed_rule_equals_run_paths_exactly():
    rng = np.random.default_rng(2)
    returns = rng.normal(0.004, 0.06, 168)
    inflation = rng.normal(0.002, 0.003, 168)
    idx = month_indices(block_starts(7, 200, 30, 168), 12, 168)
    paths = run_paths(returns, inflation, idx, 0.08)
    cpi_at, levels = longrun_cpi(inflation[idx])
    run = run_rule("fixed", {}, returns[idx], np.ones(360, dtype=bool), cpi_at, 0.08)
    assert (paths.depleted > 0).any()  # the depletion branch is compared
    assert (paths.depleted == 0).any()  # and the surviving branch
    np.testing.assert_array_equal(run.values, paths.nominal)
    np.testing.assert_array_equal(run.depleted, paths.depleted)
    np.testing.assert_array_equal(run.values / levels, paths.real)


@pytest.mark.parametrize("rule", list(PARAMS))
def test_one_path_through_the_vectorised_code_equals_its_own_run(rule):
    rng = np.random.default_rng(4)
    r = rng.normal(0.003, 0.08, (6, 60))
    rates = np.array([0.02, 0.033, 0.04, 0.05, 0.08, 0.15])
    cpi_at = {m: rng.uniform(0.97, 1.08, 6) for m in (12, 24, 36, 48)}
    starts = np.ones(60, dtype=bool)
    together = run_rule(rule, PARAMS[rule], r, starts, cpi_at, rates)
    for i in range(6):
        alone = run_rule(
            rule,
            PARAMS[rule],
            r[i : i + 1],
            starts,
            {m: f[i : i + 1] for m, f in cpi_at.items()},
            rates[i : i + 1],
        )
        np.testing.assert_array_equal(alone.values[0], together.values[i])
        np.testing.assert_array_equal(alone.paid[0], together.paid[i])
        assert alone.depleted[0] == together.depleted[i]


# ---- measures

MONTHS = pd.period_range("2005-01", "2006-12", freq="M")
DAYS = pd.bdate_range("2005-01-03", "2006-12-29")


def _values(zero_from: str | None = None) -> pd.Series:
    v = pd.Series(1.0, index=DAYS)
    if zero_from is not None:
        v[v.index >= zero_from] = 0.0
    return v


def test_historical_measures_by_hand_with_flat_cpi():
    m, below = historical_measures(
        _values(), np.full(24, 0.01), 0, MONTHS, cpi_series(monthly_growth=0.0), 0.12, [0.9, 0.5]
    )
    assert m["depleted"] is None
    assert m["income_low"] == pytest.approx(1.0)
    assert m["income_total"] == pytest.approx(2.0)
    np.testing.assert_array_equal(below, [[False, False], [False, False]])


def test_historical_depleted_year_counts_what_was_received_and_is_below_every_line():
    # depleted 2006-06 (month 18): 2006 received 5 x 0.01 + 0.004 = 0.054 = 45% of 0.12
    paid = np.r_[np.full(17, 0.01), 0.004, np.zeros(6)]
    m, below = historical_measures(
        _values("2006-06-01"), paid, 18, MONTHS, cpi_series(monthly_growth=0.0), 0.12, [0.9, 0.3]
    )
    assert m["depleted"] == "2006-06"
    assert m["end_real"] == 0.0
    assert m["lowest"] == 0.0
    assert m["income_low"] == pytest.approx(0.45)
    assert m["income_total"] == pytest.approx(1.45)
    # 45% is above the 30% line, but 2006 is the depletion year: below every line
    np.testing.assert_array_equal(below, [[False, False], [True, True]])


def test_historical_measures_deflate_each_year_by_the_cpi_usable_on_1_january():
    index = _varying_cpi()

    def usable(day: str) -> float:  # independent of usable_cpi
        return float(index.loc[: pd.Timestamp(day)].iloc[-1])

    deflator = usable("2006-01-01") / usable("2005-01-03")
    m, below = historical_measures(_values(), np.full(24, 0.01), 0, MONTHS, index, 0.12, [0.9])
    assert deflator != pytest.approx(1.0, abs=1e-3)
    assert m["income_low"] == pytest.approx(min(1.0, 1 / deflator), rel=1e-12)
    assert m["income_total"] == pytest.approx(1 + 1 / deflator, rel=1e-12)
    # 2005 is 100% (not below 90%); 2006 is below the line exactly when 1 / deflator < 0.9
    np.testing.assert_array_equal(below, [[False], [1 / deflator < 0.9]])
    _, below_high = historical_measures(
        _values(), np.full(24, 0.01), 0, MONTHS, index, 0.12, [1 / deflator + 1e-6]
    )
    np.testing.assert_array_equal(below_high, [[False], [True]])


def test_historical_measures_end_real_and_lowest_on_a_surviving_path():
    index = _varying_cpi()

    def usable(day: str) -> float:  # independent of usable_cpi
        return float(index.loc[: pd.Timestamp(day)].iloc[-1])

    values = pd.Series(np.linspace(1.0, 0.8, len(DAYS)), index=DAYS)
    m, _ = historical_measures(values, np.full(24, 0.01), 0, MONTHS, index, 0.12, [0.9])
    deflator = usable("2006-12-29") / usable("2005-01-03")
    assert m["depleted"] is None
    assert m["end_real"] == pytest.approx(0.8 / deflator, rel=1e-12)
    assert m["lowest"] == pytest.approx(0.8)


def test_historical_depletion_year_income_is_deflated_under_varying_cpi():
    index = _varying_cpi()

    def usable(day: str) -> float:  # independent of usable_cpi
        return float(index.loc[: pd.Timestamp(day)].iloc[-1])

    paid = np.r_[np.full(17, 0.01), 0.004, np.zeros(6)]  # depleted 2006-06
    m, below = historical_measures(_values("2006-06-01"), paid, 18, MONTHS, index, 0.12, [0.9, 0.3])
    deflator = usable("2006-01-01") / usable("2005-01-03")
    income_2006 = 0.054 / deflator / 0.12
    assert deflator != pytest.approx(1.0, abs=1e-3)
    assert m["depleted"] == "2006-06"
    assert m["income_low"] == pytest.approx(min(1.0, income_2006), rel=1e-12)
    assert m["income_total"] == pytest.approx(1.0 + income_2006, rel=1e-12)
    np.testing.assert_array_equal(below, [[False, False], [True, True]])


def test_historical_depletion_before_the_last_year_zeroes_and_flags_later_years():
    index = _varying_cpi()
    months = pd.period_range("2005-01", "2007-12", freq="M")
    days = pd.bdate_range("2005-01-03", "2007-12-31")
    values = pd.Series(1.0, index=days)
    values[values.index >= "2005-08-01"] = 0.0
    paid = np.r_[np.full(7, 0.01), 0.004, np.zeros(28)]  # depleted 2005-08 (month 8)

    def usable(day: str) -> float:  # independent of usable_cpi
        return float(index.loc[: pd.Timestamp(day)].iloc[-1])

    income_2005 = 0.074 / (usable("2005-01-01") / usable("2005-01-03")) / 0.12
    m, below = historical_measures(values, paid, 8, months, index, 0.12, [0.9, 0.3])
    assert m["depleted"] == "2005-08"
    assert m["income_low"] == 0.0
    assert m["income_total"] == pytest.approx(income_2005, rel=1e-12)
    # 2005 (~62%) is above 30% but is the depletion year; 2006 and 2007 are 0
    assert income_2005 > 0.3
    np.testing.assert_array_equal(below, np.ones((3, 2), dtype=bool))


def test_longrun_measures_by_hand():
    full = np.full(24, 0.01)
    short = np.r_[np.full(18, 0.01), 0.004, np.zeros(5)]  # emptied in month 19
    run = RuleRun(
        np.vstack([np.ones(24), np.r_[np.ones(18), np.zeros(6)]]),
        np.vstack([full, short]),
        np.array([0, 19]),
    )
    m = longrun_measures(run, np.ones((2, 24)), 0.12, [0.9, 0.5], 2)
    low = 0.064 / 0.12  # year 2 of the short path: 6 x 0.01 + 0.004
    assert m["depleted"] == 0.5
    assert m["income_low_median"] == pytest.approx((1.0 + low) / 2)
    assert m["income_low_p5"] == pytest.approx(low + 0.05 * (1.0 - low))
    assert m["income_total_median"] == pytest.approx((2.0 + 1.0 + low) / 2)
    # 53% is above the 50% line, but the path ran out: it counts as below
    assert m["ever_below"] == {0.9: 0.5, 0.5: 0.5}
    assert m["end_real_median"] == pytest.approx(0.5)
    assert m["lowest_median"] == pytest.approx(0.5)
    # two paths: the 5th percentile is the low value + 0.05 of the gap to the high one
    short_total = 1.0 + low
    assert m["income_total_median"] == pytest.approx((2.0 + short_total) / 2)
    assert m["income_total_p5"] == pytest.approx(short_total + 0.05 * (2.0 - short_total))
    assert m["end_real_p5"] == pytest.approx(0.05)  # ends 0 and 1
    assert m["lowest_p5"] == pytest.approx(0.05)  # lowest 0 and 1


def test_longrun_measures_percentiles_differ_from_the_median_with_three_paths():
    # lowest values 0.2, 0.6, 1.0; real ends 0.2, 0.6, 1.0 (flat levels)
    values = np.vstack([np.full(24, 0.2), np.full(24, 0.6), np.ones(24)])
    paid = np.vstack([np.full(24, 0.002), np.full(24, 0.006), np.full(24, 0.01)])
    run = RuleRun(values, paid, np.zeros(3, dtype=np.int64))
    m = longrun_measures(run, np.ones((3, 24)), 0.12, [0.5], 2)
    # yearly income 0.024/0.12 = 0.2, 0.6, 1.0 per year; totals 0.4, 1.2, 2.0
    assert m["end_real_median"] == pytest.approx(0.6)
    assert m["end_real_p5"] == pytest.approx(0.2 + 0.1 * 0.4)  # position 0.1 of 2
    assert m["lowest_median"] == pytest.approx(0.6)
    assert m["lowest_p5"] == pytest.approx(0.2 + 0.1 * 0.4)
    assert m["income_low_median"] == pytest.approx(0.6)
    assert m["income_low_p5"] == pytest.approx(0.2 + 0.1 * 0.4)
    assert m["income_total_median"] == pytest.approx(1.2)
    assert m["income_total_p5"] == pytest.approx(0.4 + 0.1 * 0.8)
    assert m["ever_below"] == {0.5: pytest.approx(1 / 3)}


def test_longrun_measures_horizon_boundary():
    def run_depleted_in(month: int) -> RuleRun:
        paid = np.zeros((1, 24))
        paid[0, : month - 1] = 0.01
        return RuleRun(np.ones((1, 24)), paid, np.array([month]))

    at_horizon = longrun_measures(run_depleted_in(12), np.ones((1, 24)), 0.12, [0.5], 1)
    after = longrun_measures(run_depleted_in(13), np.ones((1, 24)), 0.12, [0.5], 1)
    assert at_horizon["depleted"] == 1.0  # month 12 is the last month of year 1
    assert after["depleted"] == 0.0  # month 13 is outside a 1-year horizon
    assert after["ever_below"] == {0.5: 1.0}  # but ever_below has no horizon limit


def test_longrun_measures_refuses_months_that_are_not_whole_years():
    run = RuleRun(np.ones((1, 25)), np.full((1, 25), 0.01), np.array([0]))
    with pytest.raises(ValueError, match="multiple of 12, got 25"):
        longrun_measures(run, np.ones((1, 25)), 0.12, [0.5], 2)


def test_longrun_measures_refuses_a_horizon_longer_than_the_path():
    run = RuleRun(np.ones((1, 24)), np.full((1, 24), 0.01), np.array([0]))
    with pytest.raises(ValueError, match="horizon_years 3 is longer than the path's 2 years"):
        longrun_measures(run, np.ones((1, 24)), 0.12, [0.5], 3)


def test_longrun_measures_deflate_each_period_by_inflation_to_its_start():
    # level after month t (0-based) is 1 + 0.01 (t + 1): year 2 starts at 1.12
    levels = (1.0 + 0.01 * np.arange(1, 25))[None, :]
    run = RuleRun(np.ones((1, 24)), np.full((1, 24), 0.01), np.array([0]))
    m = longrun_measures(run, levels, 0.12, [0.9, 0.8], 2)
    assert m["income_low_median"] == pytest.approx(1 / 1.12)  # year 1 is not deflated
    assert m["income_total_median"] == pytest.approx(1 + 1 / 1.12)
    assert m["ever_below"] == {0.9: 1.0, 0.8: 0.0}  # 89.3% < 90%, > 80%
    assert m["end_real_median"] == pytest.approx(1 / 1.24)


def test_fixed_rule_keeps_real_income_at_the_starting_income_in_both_views():
    rets, index = _daily(5, mu=0.0004, sigma=0.0), _varying_cpi()
    run, months = historical_run(rets, index, [0.04], "fixed", {})
    m, _ = historical_measures(
        pd.Series(run.values[0], index=rets.index), run.paid[0], 0, months, index, 0.04, [0.9]
    )
    assert m["income_low"] == pytest.approx(1.0, rel=1e-9)
    assert m["income_total"] == pytest.approx(4.0, rel=1e-9)
    pi = np.random.default_rng(6).normal(0.003, 0.004, (3, 360))
    cpi_at, levels = longrun_cpi(pi)
    lr = run_rule("fixed", {}, np.full((3, 360), 0.005), np.ones(360, dtype=bool), cpi_at, 0.04)
    lm = longrun_measures(lr, levels, 0.04, [0.9], 30)
    assert lm["depleted"] == 0.0
    assert lm["income_low_median"] == pytest.approx(1.0, rel=1e-9)
    assert lm["income_total_median"] == pytest.approx(30.0, rel=1e-9)


# ---- run_withdrawal_rules on the offline decision-helper fixtures

RATES = [0.04, 0.05]
YEARS = [2005, 2013]
PIDS = ("A", "CASH")


def _lcfg() -> LongrunConfig:
    return LongrunConfig(
        seed=7,
        n_paths=50,
        block_months=12,
        horizon_years=30,
        real_floor=0.5,
        rates=RATES,
        cash_real_yield=0.01,
        sha256="ab" * 32,
    )


def _rcfg(portfolios: tuple[str, ...] = PIDS) -> RulesConfig:
    return RulesConfig(
        rules={k: dict(v) for k, v in PARAMS.items()},
        income_lines=[0.9, 0.8, 0.7],
        portfolios=list(portfolios),
        sha256="ef" * 32,
    )


@pytest.fixture(scope="module")
def setup(tmp_path_factory):
    full = load(tmp_path_factory.mktemp("rules"))
    by_id = {p.id: p for p in full.portfolios}
    dcfg = replace(full, portfolios=[by_id[pid] for pid in PIDS], rates=RATES, start_years=YEARS)
    return dcfg, prices(), cpi_series()


@pytest.fixture(scope="module")
def report(setup):
    dcfg, data, index = setup
    return run_withdrawal_rules(_rcfg(), dcfg, _lcfg(), data, index, criteria())


def test_rows_one_per_portfolio_rule_and_rate_in_config_order(report):
    hist = [(r["portfolio"], r["rule"], r["rate"]) for r in report["historical"]]
    assert hist == [(p, rule, rate) for p in PIDS for rule in PARAMS for rate in RATES]
    long = [(r["portfolio"], r["rule"], r["rate"]) for r in report["longrun"]]
    assert long == [(p, rule, rate) for rate in RATES for p in PIDS for rule in PARAMS]


def test_report_header_fields(report, setup):
    dcfg, _, _ = setup
    assert report["data_end"] == "2018-12-31"
    assert report["rules_sha256"] == "ef" * 32
    assert report["decision_sha256"] == dcfg.sha256
    assert report["longrun_sha256"] == "ab" * 32
    assert report["cost_bps"] == 5.0
    assert (report["seed"], report["n_paths"], report["block_months"], report["horizon_years"]) == (
        7,
        50,
        12,
        30,
    )
    assert (report["first_month"], report["last_month"], report["n_months"]) == (
        "2005-01",
        "2018-12",
        168,
    )
    assert report["rates"] == RATES
    assert report["start_years"] == YEARS
    assert [p["id"] for p in report["portfolios"]] == list(PIDS)


def test_historical_below_shares_pool_every_start_years_calendar_years(report):
    # 2005 start: calendar years 2005..2018 (14); 2013 start: 2013..2018 (6)
    for row in report["historical"]:
        assert row["years_pooled"] == 20
        assert set(row["below"]) == {0.9, 0.8, 0.7}
        assert all(0.0 <= share <= 1.0 for share in row["below"].values())
        assert row["below"][0.7] <= row["below"][0.8] <= row["below"][0.9]
        assert (row["first_year"], row["worst"]["end_real"] <= row["first"]["end_real"]) == (
            2005,
            True,
        )


@pytest.mark.parametrize("varying", [False, True])
def test_fixed_rule_historical_rows_equal_decision_withdrawal_rows(setup, report, varying):
    dcfg, data, index = setup
    rows = report["historical"]
    if varying:
        index = _varying_cpi()
        rows = run_withdrawal_rules(_rcfg(), dcfg, _lcfg(), data, index, criteria())["historical"]
    theirs = {
        (r["portfolio"], r["rate"]): r for r in withdrawal_rows(dcfg, data, index, criteria())
    }
    for row in (r for r in rows if r["rule"] == "fixed"):
        other = theirs[(row["portfolio"], row["rate"])]
        assert row["first_year"] == other["first_year"]
        for key in ("end_real", "lowest", "depleted"):
            assert row["first"][key] == other["first"][key]
        assert row["worst_year"] == other["worst_year"]
        assert row["worst"]["end_real"] == other["worst_end_real"]


@pytest.mark.parametrize("varying", [False, True])
def test_fixed_rule_longrun_rows_equal_run_longrun_on_the_same_paths(setup, report, varying):
    # run_longrun's other row fields (median_depletion_year, below_floor) have no
    # counterpart in these rows; the shared ones are compared, with the real values
    # deflated by the cumulative inflation, so the CPI alignment is exercised.
    dcfg, data, index = setup
    rows = report["longrun"]
    if varying:
        index = _varying_cpi()
        rows = run_withdrawal_rules(_rcfg(), dcfg, _lcfg(), data, index, criteria())["longrun"]
    theirs = {
        (r["portfolio"], r["rate"]): r
        for r in run_longrun(_lcfg(), dcfg, data, index, criteria())["rows"]
    }
    fixed_rows = [r for r in rows if r["rule"] == "fixed"]
    assert len(fixed_rows) == len(PIDS) * len(RATES)
    for row in fixed_rows:
        other = theirs[(row["portfolio"], row["rate"])]
        assert row["depleted"] == other["depleted_by"][30]
        assert row["end_real_median"] == other["end_real_median"]
        assert row["end_real_p5"] == other["end_real_p5"]


def _measures(end_real: float, lowest: float, income_low: float) -> dict:
    return {
        "depleted": None,
        "end_real": end_real,
        "lowest": lowest,
        "income_low": income_low,
        "income_total": 10.0,
    }


def test_historical_row_pools_years_across_start_years_with_unequal_counts():
    lines = [0.9, 0.8]
    three = np.array([[True, False], [False, False], [True, True]])  # 3 calendar years
    one = np.array([[False, True]])  # 1 calendar year
    per_year = {2000: (_measures(1.0, 0.5, 0.5), three), 2003: (_measures(1.1, 0.6, 0.6), one)}
    row = _historical_row("A", "fixed", 0.04, per_year, lines)
    # Pooled over 4 years: line 0.9 below in 2 of 4, line 0.8 below in 2 of 4.
    # (Mean of per-start-year means would give (2/3 + 0)/2 = 1/3 and (1/3 + 1)/2 = 2/3.)
    assert row["years_pooled"] == 4
    assert row["below"] == {0.9: 0.5, 0.8: 0.5}


def test_historical_row_worst_start_year_is_the_lowest_real_ending_value():
    below = np.array([[False]])
    # The lowest `lowest` is 2000 and the lowest `income_low` is 2002; the lowest
    # end_real is 2001.
    per_year = {
        2000: (_measures(1.5, 0.4, 0.5), below),
        2001: (_measures(0.9, 0.8, 0.6), below),
        2002: (_measures(1.2, 0.9, 0.1), below),
    }
    row = _historical_row("A", "fixed", 0.04, per_year, [0.9])
    assert row["first_year"] == 2000
    assert (row["worst_year"], row["worst"]["end_real"]) == (2001, 0.9)
    assert row["worst"] is per_year[2001][0]


def test_historical_row_worst_start_year_tie_goes_to_the_earlier_year():
    below = np.array([[False]])
    per_year = {  # later year inserted first, so dict order cannot decide
        2003: (_measures(0.9, 0.2, 0.2), below),
        2001: (_measures(0.9, 0.8, 0.8), below),
        2002: (_measures(1.3, 0.9, 0.9), below),
    }
    row = _historical_row("A", "fixed", 0.04, per_year, [0.9])
    assert row["worst_year"] == 2001
    assert row["first_year"] == 2001


def test_run_is_repeatable_and_draws_block_starts_once(report, setup):
    dcfg, data, index = setup
    with patch("qrl.decision_rules.block_starts", wraps=block_starts) as spy:
        again = run_withdrawal_rules(_rcfg(), dcfg, _lcfg(), data, index, criteria())
    assert spy.call_count == 1  # one draw shared by every portfolio and rule (paired)
    assert again == report


def test_run_refuses_unequal_withdrawal_rates(setup):
    dcfg, data, index = setup
    with pytest.raises(ValueError, match="differ"):
        run_withdrawal_rules(_rcfg(), replace(dcfg, rates=[0.04]), _lcfg(), data, index, criteria())


def test_run_refuses_a_portfolio_not_in_decision_yaml(setup):
    dcfg, data, index = setup
    with pytest.raises(ValueError, match="not in decision.yaml"):
        run_withdrawal_rules(_rcfg(("A", "ZZ")), dcfg, _lcfg(), data, index, criteria())


def test_run_refuses_partial_months(setup):
    dcfg, data, index = setup
    short = {k: v.loc[: END - pd.offsets.MonthEnd(1)] for k, v in data.items()}
    with pytest.raises(ValueError, match="months must run"):
        run_withdrawal_rules(_rcfg(), dcfg, _lcfg(), short, index, criteria())


# ---- report: rendered from a small hand-built report dict, compared with strings
# written out by hand (the renderer never produces its own expectations).

# The same pattern as HASH_LINE in tests/test_docs_freshness.py.
HASH_LINE = re.compile(
    r"^- (?:config/)?([\w.]+\.yaml) (?:config )?(?:sha256|hash): `([0-9a-f]{12,64})`"
)
HAND_RATES = [0.04, 0.05]
DEFAULT_FIRST = {
    "depleted": None,
    "end_real": 1.25,
    "lowest": 0.5,
    "income_low": 0.95,
    "income_total": 14.0,
}
DEFAULT_WORST = {
    "depleted": None,
    "end_real": 0.75,
    "lowest": 0.25,
    "income_low": 0.85,
    "income_total": 12.0,
}
DEFAULT_LONG = {
    "depleted": 0.02,
    "end_real_median": 1.5,
    "end_real_p5": 0.6,
    "lowest_median": 0.8,
    "lowest_p5": 0.4,
    "income_low_median": 1.0,
    "income_low_p5": 0.85,
    "income_total_median": 30.0,
    "income_total_p5": 27.5,
    "ever_below": {0.9: 0.05, 0.8: 0.0},
}
ODD_HIST = ("A", "guardrails", 0.05)
ODD_LONG = ("CASH", "pct_of_balance", 0.04)
DEFAULT_HIST_ROW = (
    "| {p} | {r} | - | 125.0% | 50.0% | 95.0% | 1400.0% | 2013 | - | 75.0% | 25.0% | 85.0% "
    "| 1200.0% | 25.0% | 10.0% |"
)
ODD_HIST_ROW = (
    "| A | guardrails | 2010-06 | 125.0% | 50.0% | 95.0% | 1400.0% | 2005 | 2016-03 | 0.0% "
    "| 0.0% | 0.0% | 300.0% | 50.0% | 45.0% |"
)
DEFAULT_LONG_ROW = (
    "| {p} | {r} | 2.0% | 150.0% | 60.0% | 80.0% | 40.0% | 100.0% | 85.0% | 3000.0% "
    "| 2750.0% | 5.0% | 0.0% |"
)
ODD_LONG_ROW = (
    "| CASH | pct_of_balance | 0.0% | 90.0% | 30.0% | 35.0% | 10.0% | 50.0% | 25.0% "
    "| 2000.0% | 1500.0% | 100.0% | 12.5% |"
)


def _hist_row(pid: str, rule: str, rate: float) -> dict:
    row = {
        "portfolio": pid,
        "rule": rule,
        "rate": rate,
        "first_year": 2005,
        "first": dict(DEFAULT_FIRST),
        "worst_year": 2013,
        "worst": dict(DEFAULT_WORST),
        "years_pooled": 20,
        "below": {0.9: 0.25, 0.8: 0.1},
    }
    if (pid, rule, rate) == ODD_HIST:
        row["first"] = {**DEFAULT_FIRST, "depleted": "2010-06"}
        row["worst_year"] = 2005
        row["worst"] = {
            "depleted": "2016-03",
            "end_real": 0.0,
            "lowest": 0.0,
            "income_low": 0.0,
            "income_total": 3.0,
        }
        row["below"] = {0.9: 0.5, 0.8: 0.45}
    return row


def _long_row(pid: str, rule: str, rate: float) -> dict:
    row = {"portfolio": pid, "rule": rule, "rate": rate, **DEFAULT_LONG}
    if (pid, rule, rate) == ODD_LONG:
        row.update(
            depleted=0.0,
            end_real_median=0.9,
            end_real_p5=0.3,
            lowest_median=0.35,
            lowest_p5=0.1,
            income_low_median=0.5,
            income_low_p5=0.25,
            income_total_median=20.0,
            income_total_p5=15.0,
            ever_below={0.9: 1.0, 0.8: 0.125},
        )
    return row


@pytest.fixture(scope="module")
def hand():
    return {
        "data_end": "2018-12-31",
        "rules_sha256": "ef" * 32,
        "decision_sha256": "cd" * 32,
        "longrun_sha256": "ab" * 32,
        "cost_bps": 5.0,
        "seed": 7,
        "n_paths": 50,
        "block_months": 12,
        "horizon_years": 30,
        "first_month": "2005-01",
        "last_month": "2018-12",
        "n_months": 168,
        "rates": HAND_RATES,
        "start_years": YEARS,
        "rules": {k: dict(v) for k, v in PARAMS.items()},
        "income_lines": [0.9, 0.8],
        "portfolios": [
            {"id": "A", "label": "Growth core"},
            {"id": "CASH", "label": "All cash"},
        ],
        "historical": [_hist_row(p, r, k) for p in PIDS for r in PARAMS for k in HAND_RATES],
        "longrun": [_long_row(p, r, k) for k in HAND_RATES for p in PIDS for r in PARAMS],
    }


def _sections(md: str) -> dict[str, list[str]]:
    """Lines of the historical and the long-run section."""
    lines = md.splitlines()
    hist = next(i for i, x in enumerate(lines) if x.startswith("## Historical view"))
    long = next(i for i, x in enumerate(lines) if x.startswith("## Long-run view"))
    return {"hist": lines[hist:long], "long": lines[long:]}


def _tables(lines: list[str]) -> list[list[str]]:
    """Per '### Withdrawal rate' heading: the header line, then the body rows."""
    tables: list[list[str]] = []
    for line in lines:
        if line.startswith("### Withdrawal rate"):
            tables.append([line])
        elif tables and line.startswith("| "):
            tables[-1].append(line)
    return tables


def _hashes(md: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for line in md.splitlines() if (m := HASH_LINE.match(line))}


def test_header_hash_lines_parse_like_the_freshness_check(hand):
    assert _hashes(render_markdown(hand)) == {
        "withdrawal_rules.yaml": "ef" * 32,
        "decision.yaml": "cd" * 32,
        "longrun.yaml": "ab" * 32,
    }


def test_header_lines_are_written_out(hand):
    lines = render_markdown(hand).splitlines()
    assert lines[0] == "# Withdrawal rules: the fixed withdrawal against flexible rules"
    for line in (
        "- data: up to 2018-12-31 only (validation and holdout stay sealed)",
        "- historical view: start years 2005 to 2013, each to 2018-12-31",
        "- long run: 50 paths of 30 years, 12-month blocks drawn from 168 months "
        "(2005-01 to 2018-12, circular), seed 7; the same paths as the long-run report",
        "- trading costs: 5 bps per unit traded",
        "- 2 portfolios x 5 rules x 2 withdrawal rates = 20 rows per view",
        "- portfolios: A (Growth core); CASH (All cash)",
    ):
        assert line in lines, line


def test_counts_are_computed_not_hard_coded(hand):
    one_rate = {**hand, "rates": [0.04], "portfolios": hand["portfolios"][:1]}
    assert "- 1 portfolios x 5 rules x 1 withdrawal rates = 5 rows per view" in render_markdown(
        one_rate
    )


def test_notes_carry_the_plain_words(hand):
    md = render_markdown(hand)
    for text in (
        "recommends nothing",
        "no 15-year exception",
        "not fitted",
        "The long-run decision point is every 12 months, not January.",
        "counts 0 for every later year",
        "The historical view has 2 overlapping start years, so it is 2 related paths, "
        "not 2 independent tests.",
        "taken proportionally from all holdings at no extra cost",
        "bad case (worst 5%) is the value 1 path in 20 is below",
    ):
        assert text in " ".join(md.split()), text


def test_each_rule_is_described_with_its_configured_parameters(hand):
    md = render_markdown(hand)
    assert "- fixed: last year's monthly amount raised by CPI each year;" in md
    assert "- skip_raise_after_loss: as fixed, but no CPI raise after a year" in md
    assert (
        "if 12 x amount / value is above 120.0% of the rate, cut it by 10.0%; "
        "if below 80.0% of the rate, raise it by 10.0%." in md
    )
    assert "- pct_of_balance: each year 12 x amount = rate x value." in md
    assert (
        "- floor_ceiling: rate x value / 12, kept within -2.5% and +5.0% of last "
        "year's amount after CPI" in md
    )


def test_changed_parameters_change_the_rule_text(hand):
    other = {
        **hand,
        "rules": {"guardrails": {"upper": 1.5, "lower": 0.5, "cut": 0.2, "raise": 0.05}},
    }
    md = render_markdown(other)
    assert "above 150.0% of the rate, cut it by 20.0%; if below 50.0% of the rate" in md
    assert "raise it by 5.0%." in md


def test_an_unknown_rule_is_refused(hand):
    with pytest.raises(ValueError, match="unknown rule 'mystery'"):
        render_markdown({**hand, "rules": {"mystery": {}}})


def test_sections_come_historical_then_long_run_one_table_per_rate(hand):
    md = render_markdown(hand)
    assert md.index("## Rules") < md.index("## Notes") < md.index("## Historical view")
    assert md.index("## Historical view") < md.index("## Long-run view")
    assert "## Historical view: start years 2005 to 2013, each to 2018-12-31" in md
    assert "## Long-run view: 30-year resampled paths" in md
    sections = _sections(md)
    for key in ("hist", "long"):
        headings = [t[0] for t in _tables(sections[key])]
        assert headings == [
            "### Withdrawal rate 4.0% per year",
            "### Withdrawal rate 5.0% per year",
        ]


def test_historical_table_header_and_separator_are_written_out(hand):
    table = next(
        i
        for i, x in enumerate(_sections(render_markdown(hand))["hist"])
        if x.startswith("| portfolio")
    )
    lines = _sections(render_markdown(hand))["hist"]
    assert lines[table] == (
        "| portfolio | rule | 2005: ran out | 2005: real value at end | 2005: lowest value "
        "| 2005: lowest yearly real income | 2005: total real income | worst start year "
        "| worst: ran out | worst: real value at end | worst: lowest value "
        "| worst: lowest yearly real income | worst: total real income "
        "| years below 90.0% | years below 80.0% |"
    )
    assert lines[table + 1] == "|" + "---|" * 15


def test_longrun_table_header_and_separator_are_written_out(hand):
    lines = _sections(render_markdown(hand))["long"]
    table = next(i for i, x in enumerate(lines) if x.startswith("| portfolio"))
    assert lines[table] == (
        "| portfolio | rule | ran out by year 30 | real value at year 30: typical "
        "| real value at year 30: bad case (worst 5%) | lowest value: typical "
        "| lowest value: bad case (worst 5%) | lowest yearly real income: typical "
        "| lowest yearly real income: bad case (worst 5%) | total real income: typical "
        "| total real income: bad case (worst 5%) | ever below 90.0% | ever below 80.0% |"
    )
    assert lines[table + 1] == "|" + "---|" * 13


def test_historical_rows_are_grouped_by_portfolio_rules_in_config_order(hand):
    tables = _tables(_sections(render_markdown(hand))["hist"])
    for rate, table in zip(HAND_RATES, tables, strict=True):
        expected = []
        for p in PIDS:
            for r in PARAMS:
                if (p, r, rate) == ODD_HIST:
                    expected.append(ODD_HIST_ROW)
                else:
                    expected.append(DEFAULT_HIST_ROW.format(p=p, r=r))
        assert table[2:] == expected  # [heading, header, rows...]


def test_longrun_rows_are_grouped_by_portfolio_rules_in_config_order(hand):
    tables = _tables(_sections(render_markdown(hand))["long"])
    for rate, table in zip(HAND_RATES, tables, strict=True):
        expected = []
        for p in PIDS:
            for r in PARAMS:
                if (p, r, rate) == ODD_LONG:
                    expected.append(ODD_LONG_ROW)
                else:
                    expected.append(DEFAULT_LONG_ROW.format(p=p, r=r))
        assert table[2:] == expected


def test_output_ends_with_one_newline_and_is_repeatable(hand):
    md = render_markdown(hand)
    assert md.endswith("|\n")
    assert not md.endswith("\n\n")
    assert render_markdown(hand) == md


def test_percentages_round_and_never_show_negative_zero(hand):
    tiny = {**hand, "longrun": [_long_row("A", "fixed", 0.04)]}
    tiny["longrun"][0]["lowest_p5"] = -0.0001
    tiny["rates"] = [0.04]
    tiny["portfolios"] = hand["portfolios"][:1]
    tiny["rules"] = {"fixed": {}}
    tiny["historical"] = [_hist_row("A", "fixed", 0.04)]
    md = render_markdown(tiny)
    assert "| 80.0% | 0.0% | 100.0% |" in md
    assert "-0.0%" not in md
