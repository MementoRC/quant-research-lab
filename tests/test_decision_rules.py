"""Withdrawal rules (qrl.decision_rules, qrl.withdrawal_rules_report). Offline;
synthetic returns, prices and CPI only. Spec:
docs/methodology/withdrawal-rules.md ("Tests")."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest
from decision_helpers import CANDIDATES, END, ROOT, stress_cfg

from qrl.decision_config import load_decision_config
from qrl.decision_rules import RULE_PARAMS, RulesConfig, load_rules_config
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
