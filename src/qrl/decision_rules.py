"""Withdrawal rules (spec: docs/methodology/withdrawal-rules.md): the fixed
CPI-indexed withdrawal against four flexible rules, per portfolio, rule and
rate, in the decision helper's historical view and the long run's resampled
paths. A comparison: no pass/fail rule, no search trial; it selects and
recommends nothing. Pure functions; callers inject data and configs. Every
price and CPI frame is cut at the research end (2018-12-31) before use, so
validation and holdout data never enter. The fixed rule is an independent
re-implementation that equals `withdrawal_path` and `run_paths` exactly; that
code and every number it publishes are unchanged.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import yaml

_KEYS = ("version", "decision_sha256", "longrun_sha256", "rules", "income_lines", "portfolios")
RULE_PARAMS: dict[str, tuple[str, ...]] = {
    "fixed": (),
    "skip_raise_after_loss": (),
    "guardrails": ("upper", "lower", "cut", "raise"),
    "pct_of_balance": (),
    "floor_ceiling": ("max_real_cut", "max_real_raise"),
}
_WHERE = "withdrawal_rules.yaml"


@dataclass(frozen=True)
class RulesConfig:
    rules: dict[str, dict[str, float]]  # rule id -> parameters, in config order
    income_lines: list[float]  # fractions of the starting income
    portfolios: list[str]  # decision.yaml portfolio ids, in config order
    sha256: str


def _read(path: str | Path) -> tuple[dict, bytes]:
    try:
        raw = Path(path).read_bytes()
        doc = yaml.safe_load(raw)
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"{_WHERE}: cannot be loaded ({exc})") from exc
    if not isinstance(doc, dict):
        raise ValueError(f"{_WHERE}: cannot be loaded (not a mapping)")
    return doc, raw


def _check_params(rule: str, p: dict[str, float]) -> None:
    """Spec "Configuration" ranges. Written as `not (in range)` so NaN is refused too."""
    if rule == "guardrails":
        if not p["upper"] > 1:
            raise ValueError(f"{_WHERE}: guardrails upper {p['upper']} must be above 1")
        if not p["lower"] < 1:
            raise ValueError(f"{_WHERE}: guardrails lower {p['lower']} must be below 1")
        for key in ("cut", "raise"):
            if not 0 < p[key] < 1:
                raise ValueError(
                    f"{_WHERE}: guardrails {key} {p[key]} must be strictly between 0 and 1"
                )
    if rule == "floor_ceiling":
        for key in ("max_real_cut", "max_real_raise"):
            if not p[key] >= 0:
                raise ValueError(f"{_WHERE}: floor_ceiling {key} {p[key]} must be 0 or more")


def _rules(raw: object) -> dict[str, dict[str, float]]:
    if not isinstance(raw, dict) or not raw:
        raise ValueError(f"{_WHERE}: `rules` must be a non-empty mapping")
    out: dict[str, dict[str, float]] = {}
    for rule, params in raw.items():
        if rule not in RULE_PARAMS:
            raise ValueError(f"{_WHERE}: unknown rule {rule!r}")
        if not isinstance(params, dict) or set(params) != set(RULE_PARAMS[rule]):
            raise ValueError(
                f"{_WHERE}: rule {rule} needs parameters {sorted(RULE_PARAMS[rule])}, "
                f"got {params!r}"
            )
        values = {str(k): _number(v, f"rule {rule} parameters") for k, v in params.items()}
        _check_params(rule, values)
        out[str(rule)] = values
    return out


def _number(value: object, what: str) -> float:
    """A real, finite YAML number: not a bool, a string or null."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{_WHERE}: {what} must be numbers, got {value!r}")
    if not math.isfinite(value):
        raise ValueError(f"{_WHERE}: {what} must be finite, got {value!r}")
    return float(value)


def _list(doc: dict, key: str) -> list:
    value = doc[key]
    if not isinstance(value, list) or not value:
        raise ValueError(f"{_WHERE}: `{key}` must be a non-empty list")
    return value


def _no_duplicates(key: str, values: list) -> None:
    dupes = sorted({str(v) for v in values if values.count(v) > 1})
    if dupes:
        raise ValueError(f"{_WHERE}: duplicate `{key}` entries {dupes}")


def _income_lines(doc: dict) -> list[float]:
    lines = [_number(x, "`income_lines` entries") for x in _list(doc, "income_lines")]
    _no_duplicates("income_lines", lines)
    bad = [x for x in lines if not 0 < x < 1]
    if bad:
        raise ValueError(f"{_WHERE}: income line(s) {bad} must be strictly between 0 and 1")
    return lines


def load_rules_config(
    path: str | Path, decision_sha256: str, longrun_sha256: str, portfolio_ids: Iterable[str]
) -> RulesConfig:
    """Read config/withdrawal_rules.yaml (spec "Configuration"). Raises
    ValueError if it cannot be loaded, has an unknown or a missing key, a
    version other than 1, a decision.yaml or longrun.yaml pin that does not
    match the given sha256, an unknown rule or a rule with a wrong parameter
    set, a parameter out of range (guardrails upper <= 1, lower >= 1, cut or
    raise outside (0, 1); floor_ceiling bands negative), an empty or
    duplicated list, an income line outside (0, 1), or a portfolio id not in
    `portfolio_ids` (decision.yaml's)."""
    doc, raw = _read(path)
    unknown = sorted(str(k) for k in doc.keys() - set(_KEYS))
    if unknown:
        raise ValueError(f"{_WHERE}: unknown key(s) {unknown}")
    missing = [k for k in _KEYS if k not in doc]
    if missing:
        raise ValueError(f"{_WHERE}: missing key(s) {missing}")
    if doc["version"] != 1:
        raise ValueError(f"{_WHERE}: unsupported version {doc['version']}")
    if doc["decision_sha256"] != decision_sha256:
        raise ValueError(f"decision.yaml changed: its sha256 does not match {_WHERE}'s pin")
    if doc["longrun_sha256"] != longrun_sha256:
        raise ValueError(f"longrun.yaml changed: its sha256 does not match {_WHERE}'s pin")
    known = set(portfolio_ids)
    portfolios = [str(p) for p in _list(doc, "portfolios")]
    _no_duplicates("portfolios", portfolios)
    strangers = [p for p in portfolios if p not in known]
    if strangers:
        raise ValueError(f"{_WHERE}: portfolio(s) {strangers} not in decision.yaml")
    return RulesConfig(
        rules=_rules(doc["rules"]),
        income_lines=_income_lines(doc),
        portfolios=portfolios,
        sha256=hashlib.sha256(raw).hexdigest(),
    )
