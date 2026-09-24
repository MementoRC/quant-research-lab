"""Load the trader profile and report what it implies, plus any conflicts.

The profile (`config/profile.yaml`) describes the human, not the backtest: goal,
trade frequency, holding period, overnight-hold policy, drawdown tolerance, the
core/sleeve capital split, and data budget. `analyze_profile` turns those choices
into plain-English implications (bar size, data source, which strategy families
fit) and flags conflicts, such as wanting intraday trading on a free data budget.
This module is pure, offline, and deterministic: no network calls, no randomness.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from qrl.risk import load_risk_limits
from qrl.strategies import REGISTRY, SLEEVE_REGISTRY

DEFAULT_PROFILE_PATH = Path("config/profile.yaml")

_RISK_EPS = 1e-9

REQUIRED_KEYS = {
    "version",
    "goal",
    "trades_per_week",
    "holding_period_days",
    "overnight_holds",
    "max_drawdown",
    "assets",
    "data_budget",
    "capital_split",
    "risk",
}
VALID_GOALS = {"growth", "income", "conservative"}
VALID_DATA_BUDGETS = {"free", "paid"}

# Sleeve families that need only daily bars, overnight holds, and short holds.
SLEEVE_SWING_FAMILIES = ("trend_pullback", "low_range_close", "quiet_pullback")


@dataclass
class ProfileReport:
    """Result of analyzing a trader profile."""

    implications: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    risk: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.conflicts


def load_profile(path: str | Path = DEFAULT_PROFILE_PATH) -> dict:
    """Load `config/profile.yaml` and check it is structurally complete.

    Raises ValueError if required keys are missing or an enum field holds an
    unrecognized value. Does not check cross-field logic (see analyze_profile).
    """
    raw = Path(path).read_text()
    profile: dict = yaml.safe_load(raw)
    missing = REQUIRED_KEYS - profile.keys()
    if missing:
        raise ValueError(f"profile is missing required keys: {sorted(missing)}")
    if profile["goal"] not in VALID_GOALS:
        raise ValueError(f"goal must be one of {sorted(VALID_GOALS)}, got {profile['goal']!r}")
    if profile["data_budget"] not in VALID_DATA_BUDGETS:
        raise ValueError(
            f"data_budget must be one of {sorted(VALID_DATA_BUDGETS)}, "
            f"got {profile['data_budget']!r}"
        )
    for field_name, required in (
        ("holding_period_days", {"min", "max"}),
        ("capital_split", {"core", "sleeve"}),
        ("assets", {"core", "sleeve"}),
    ):
        sub_missing = required - profile[field_name].keys()
        if sub_missing:
            raise ValueError(f"{field_name} is missing keys: {sorted(sub_missing)}")
    return profile


def load_profile_with_hash(path: str | Path = DEFAULT_PROFILE_PATH) -> tuple[dict, str]:
    """Like `load_profile`, but also returns a short content hash of the raw
    file bytes, mirroring `qrl.criteria.load_criteria`. Risk limits (the
    `risk:` block) gate portfolio construction, so an edit to this file
    should be as visible as an edit to criteria.yaml is to the ledger.

    Additive: `load_profile`'s signature and return shape are unchanged, so
    every existing caller keeps working exactly as before.
    """
    raw = Path(path).read_bytes()
    profile = load_profile(path)
    return profile, hashlib.sha256(raw).hexdigest()[:12]


def _needs_intraday(profile: dict) -> bool:
    hp = profile["holding_period_days"]
    return (not profile["overnight_holds"]) or hp["min"] < 1 or profile["trades_per_week"] > 25


def _check_bar_size_and_data(profile: dict, report: ProfileReport) -> bool:
    """Record bar-size and data-source implications; return whether intraday is needed."""
    intraday = _needs_intraday(profile)
    report.implications.append(f"Bar size needed: {'intraday' if intraday else 'daily'} bars.")
    if profile["data_budget"] == "free":
        report.implications.append("Data source: free daily bars (Yahoo) plus FRED macro series.")
        if intraday:
            report.conflicts.append(
                "Intraday bars are needed but data_budget is free; free sources lack "
                "deep intraday history."
            )
    else:
        report.implications.append("Data source: paid budget, so intraday vendors are an option.")
    return intraday


def _check_capital_split(profile: dict, report: ProfileReport) -> None:
    split = profile["capital_split"]
    core, sleeve = split["core"], split["sleeve"]
    if not (0 <= core <= 1) or not (0 <= sleeve <= 1):
        report.conflicts.append("capital_split values must each be within [0, 1].")
    if abs(core + sleeve - 1) > 1e-9:
        report.conflicts.append("capital_split core + sleeve must sum to 1.")
    goal = profile["goal"]
    if goal == "conservative" and sleeve > 0.20:
        report.warnings.append("Goal is conservative but sleeve share exceeds 0.20.")
    if goal == "growth" and sleeve == 0:
        report.warnings.append("Goal is growth but sleeve share is 0; no swing-trade contribution.")


def _check_max_drawdown(profile: dict, criteria: dict | None, report: ProfileReport) -> None:
    md = profile["max_drawdown"]
    if not (0 < md < 1):
        report.conflicts.append("max_drawdown must be strictly between 0 and 1.")
        return
    if criteria is None:
        return
    crit_md = criteria["pass"]["max_drawdown"]
    if md < crit_md:
        report.conflicts.append(
            f"Profile max_drawdown ({md}) is tighter than criteria's pass threshold "
            f"({crit_md}); criteria would pass strategies you can't tolerate."
        )
    else:
        report.implications.append(
            f"Profile max_drawdown ({md}) covers criteria's pass threshold ({crit_md})."
        )


def _sleeve_families(profile: dict, intraday: bool) -> list[str]:
    hp = profile["holding_period_days"]
    if not intraday and profile["overnight_holds"] and hp["max"] <= 20:
        return list(SLEEVE_SWING_FAMILIES)
    return []


def _check_holding_period(profile: dict, intraday: bool, report: ProfileReport) -> None:
    hp = profile["holding_period_days"]
    if hp["min"] > hp["max"]:
        report.conflicts.append("holding_period_days.min must be <= holding_period_days.max.")

    sleeve_families = _sleeve_families(profile, intraday)
    families = list(sleeve_families)
    if profile["capital_split"]["core"] > 0:
        families.append("core_trend")
    if families:
        report.implications.append(f"Strategy families that fit: {', '.join(families)}.")

    if profile["goal"] == "income":
        report.warnings.append("Goal is income but no income-oriented strategy families exist yet.")

    if profile["capital_split"]["sleeve"] > 0 and not sleeve_families:
        report.conflicts.append(
            "Sleeve capital is allocated but no sleeve strategy family fits this profile "
            "(needs daily bars, overnight holds, and holding_period_days.max <= 20)."
        )


def _check_frequency(profile: dict, report: ProfileReport) -> None:
    hp = profile["holding_period_days"]
    if profile["trades_per_week"] * hp["min"] > 25:
        report.warnings.append(
            "trades_per_week * holding_period_days.min > 25; implies many concurrent "
            "sleeve positions for a small sleeve."
        )


def _families_with_max_positions() -> dict[str, list[int]]:
    """Registered strategy families (both registries) that declare a
    `max_positions` search space, keyed by family name."""
    all_families = {**REGISTRY, **SLEEVE_REGISTRY}
    return {
        name: spec.space["max_positions"]
        for name, spec in all_families.items()
        if "max_positions" in spec.space
    }


def _check_risk(profile: dict, report: ProfileReport) -> None:
    """Load and summarize the profile's risk block, appending any conflicts
    or warnings to `report`, and the summary lines to `report.risk`.
    """
    limits = load_risk_limits(profile)
    report.risk.extend(
        [
            f"leverage_ceiling: {limits.leverage_ceiling}",
            f"max_gross_exposure: {limits.max_gross_exposure}",
            f"max_loss_per_trade: {limits.max_loss_per_trade}",
            f"max_open_positions: {limits.max_open_positions}",
            f"borrowing_cost_bps: {limits.borrowing_cost_bps}",
        ]
    )

    # max_gross_exposure > leverage_ceiling is already rejected by
    # qrl.risk.load_risk_limits before this function runs, so it is not
    # re-checked here; do not re-add a duplicate check for it.

    if limits.leverage_ceiling > 1.0 + _RISK_EPS:
        report.conflicts.append(
            f"risk.leverage_ceiling ({limits.leverage_ceiling}) is above 1.0, but "
            "src/qrl/engine.py:63-64 rejects any weight set summing above 1.0 "
            "(no leverage support); lower leverage_ceiling to 1.0 or change the engine."
        )

    sleeve_share = profile["capital_split"]["sleeve"]
    families = _families_with_max_positions()
    if families:
        smallest_max_positions = min(min(values) for values in families.values())
        if smallest_max_positions > 0:
            implied_min_loss = sleeve_share / smallest_max_positions
            if implied_min_loss > limits.max_loss_per_trade + _RISK_EPS:
                report.conflicts.append(
                    f"capital_split.sleeve ({sleeve_share}) / smallest max_positions in any "
                    f"family's search space ({smallest_max_positions}) = "
                    f"{implied_min_loss:.4f}, which exceeds risk.max_loss_per_trade "
                    f"({limits.max_loss_per_trade})."
                )

        for name, values in families.items():
            family_max = max(values)
            if family_max > limits.max_open_positions:
                report.conflicts.append(
                    f"strategy family {name!r} search space allows max_positions up to "
                    f"{family_max}, which exceeds risk.max_open_positions "
                    f"({limits.max_open_positions})."
                )

    if limits.borrowing_cost_bps > 0 and abs(limits.leverage_ceiling - 1.0) < _RISK_EPS:
        report.warnings.append(
            f"risk.borrowing_cost_bps ({limits.borrowing_cost_bps}) is set but "
            "leverage_ceiling is 1.0, so it can never be charged."
        )


def analyze_profile(profile: dict, criteria: dict | None = None) -> ProfileReport:
    """Derive implications and flag conflicts in a trader profile.

    `criteria`, if given (the loaded config/criteria.yaml), is used only to check
    that the profile's drawdown tolerance is not tighter than the pass threshold.
    """
    report = ProfileReport()
    intraday = _check_bar_size_and_data(profile, report)
    _check_capital_split(profile, report)
    _check_max_drawdown(profile, criteria, report)
    _check_holding_period(profile, intraday, report)
    _check_frequency(profile, report)
    _check_risk(profile, report)
    return report
