"""Withdrawal rules (qrl.decision_rules, qrl.withdrawal_rules_report). Offline;
synthetic returns, prices and CPI only. Spec:
docs/methodology/withdrawal-rules.md ("Tests")."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import numpy as np
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
    pct_of_balance,
    skip_raise_after_loss,
)
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
