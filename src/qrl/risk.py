"""Risk limits: no-leverage sizing caps, scoped to the frame each cap was
actually derived against (PLAN.md section 3.1).

Owner decision, 2026-09-24: NO LEVERAGE. `src/qrl/engine.py:63-64` already
raises if any weight row sums above 1.0, so `leverage_ceiling` and
`max_gross_exposure` are pinned at 1.0 here -- this module does not change
the engine, it only makes the existing constraint an explicit, checkable
config value instead of an implicit one.

Scope matters: each cap in `config/profile.yaml`'s `risk:` block was derived
against a specific frame, and applying it to the wrong one is a bug, not a
conservative extra check.

- `max_gross_exposure` / `leverage_ceiling` are whole-portfolio constraints
  and apply to the COMBINED (core + sleeve) frame -- `check_gross_exposure`.
- `max_loss_per_trade` and `max_open_positions` were derived from the
  SLEEVE's own capital share and the sleeve strategy families' declared
  `max_positions` search space (see profile.yaml's comments): 0.04 =
  capital_split.sleeve / the most concentrated sleeve max_positions (5); 15
  is the top of the sleeve families' max_positions space [5, 10, 15]. They
  apply to the SLEEVE frame ONLY -- `check_sleeve_positions`.

The core is deliberately exempt from `max_loss_per_trade` and
`max_open_positions`: it is a single, ~80%-of-capital, rarely-trading
holding (QQQ or GLD), not a "trade" in the sense those two caps govern, and
neither cap's derivation above ever considered the core's weight. Checking
the core against them is not stricter risk management, it is checking a cap
against a frame it was never sized for -- which is exactly the bug this
module fixes.

`check_gross_exposure`/`check_sleeve_positions`/`check_portfolio` are
read-only checks over already computed weights frames; they never mutate
weights or decide what to do about a violation, so they compose cleanly with
any caller (portfolio combination, a search loop, a dashboard build).
`assert_portfolio_within_limits` is the raising counterpart of
`check_portfolio`.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

_EPS = 1e-9
_MAX_EXAMPLES_PER_KIND = 5


@dataclass(frozen=True)
class RiskLimits:
    """Portfolio-wide risk caps loaded from `config/profile.yaml`'s `risk:` block."""

    leverage_ceiling: float
    max_gross_exposure: float
    borrowing_cost_bps: float
    max_loss_per_trade: float
    max_open_positions: int


_REQUIRED_RISK_KEYS = {
    "leverage_ceiling",
    "max_gross_exposure",
    "borrowing_cost_bps",
    "max_loss_per_trade",
    "max_open_positions",
}


def load_risk_limits(profile: dict) -> RiskLimits:
    """Read and validate the `risk:` block of a loaded profile dict.

    Raises `ValueError` if the block is missing, incomplete, or any value is
    outside its valid range.
    """
    risk = profile.get("risk")
    if not isinstance(risk, dict):
        raise ValueError("profile is missing a 'risk' block.")
    missing = _REQUIRED_RISK_KEYS - risk.keys()
    if missing:
        raise ValueError(f"profile.risk is missing keys: {sorted(missing)}")

    leverage_ceiling = float(risk["leverage_ceiling"])
    max_gross_exposure = float(risk["max_gross_exposure"])
    borrowing_cost_bps = float(risk["borrowing_cost_bps"])
    max_loss_per_trade = float(risk["max_loss_per_trade"])
    max_open_positions = int(risk["max_open_positions"])

    if leverage_ceiling <= 0:
        raise ValueError(f"risk.leverage_ceiling must be > 0, got {leverage_ceiling}.")
    if max_gross_exposure <= 0:
        raise ValueError(f"risk.max_gross_exposure must be > 0, got {max_gross_exposure}.")
    if max_gross_exposure > leverage_ceiling:
        raise ValueError(
            f"risk.max_gross_exposure ({max_gross_exposure}) must not exceed "
            f"risk.leverage_ceiling ({leverage_ceiling})."
        )
    if borrowing_cost_bps < 0:
        raise ValueError(f"risk.borrowing_cost_bps must be >= 0, got {borrowing_cost_bps}.")
    if not (0 < max_loss_per_trade <= 1):
        raise ValueError(
            f"risk.max_loss_per_trade must be within (0, 1], got {max_loss_per_trade}."
        )
    if max_open_positions < 1:
        raise ValueError(f"risk.max_open_positions must be >= 1, got {max_open_positions}.")

    return RiskLimits(
        leverage_ceiling=leverage_ceiling,
        max_gross_exposure=max_gross_exposure,
        borrowing_cost_bps=borrowing_cost_bps,
        max_loss_per_trade=max_loss_per_trade,
        max_open_positions=max_open_positions,
    )


def _gross_exposure_violations(weights: pd.DataFrame, limits: RiskLimits) -> list[str]:
    gross = weights.sum(axis=1)
    breached = gross[gross > limits.max_gross_exposure + _EPS]
    out = []
    for date, value in breached.head(_MAX_EXAMPLES_PER_KIND).items():
        out.append(
            f"{date}: gross exposure {value:.4f} exceeds max_gross_exposure "
            f"{limits.max_gross_exposure:.4f}"
        )
    return out


def _open_positions_violations(weights: pd.DataFrame, limits: RiskLimits) -> list[str]:
    counts = (weights.abs() > _EPS).sum(axis=1)
    breached = counts[counts > limits.max_open_positions]
    out = []
    for date, value in breached.head(_MAX_EXAMPLES_PER_KIND).items():
        out.append(
            f"{date}: {int(value)} open positions exceeds max_open_positions "
            f"{limits.max_open_positions}"
        )
    return out


def _per_position_violations(weights: pd.DataFrame, limits: RiskLimits) -> list[str]:
    out: list[str] = []
    for column in weights.columns:
        offending = weights.loc[weights[column] > limits.max_loss_per_trade + _EPS, column]
        for date, value in offending.items():
            if len(out) >= _MAX_EXAMPLES_PER_KIND:
                return out
            out.append(
                f"{date}: position {column!r} weight {value:.4f} exceeds max_loss_per_trade "
                f"{limits.max_loss_per_trade:.4f}"
            )
    return out


def check_gross_exposure(combined: pd.DataFrame, limits: RiskLimits) -> list[str]:
    """Return violation strings for `combined` (core + sleeve) exceeding
    `max_gross_exposure` on any row. An empty list means the frame is clean.
    Capped at the first few offending dates so the result cannot explode on
    a large frame.
    """
    return _gross_exposure_violations(combined, limits)


def check_sleeve_positions(sleeve: pd.DataFrame, limits: RiskLimits) -> list[str]:
    """Return violation strings for `sleeve` alone against the two
    sleeve-derived caps: count of non-zero positions above
    `max_open_positions`, and any single position weight above
    `max_loss_per_trade`. An empty (all-zero, e.g. no sleeve selected)
    frame is always clean. Each violation kind is capped at its first few
    offending dates so the result cannot explode on a large frame.
    """
    violations: list[str] = []
    violations.extend(_open_positions_violations(sleeve, limits))
    violations.extend(_per_position_violations(sleeve, limits))
    return violations


def check_portfolio(
    *, combined: pd.DataFrame, sleeve: pd.DataFrame, limits: RiskLimits
) -> list[str]:
    """Return all violation strings for a portfolio, routing each cap to
    the frame it was derived against: `max_gross_exposure`/
    `leverage_ceiling` against `combined`, `max_loss_per_trade`/
    `max_open_positions` against `sleeve` only (see module docstring for
    why the core is exempt from the latter two).
    """
    violations: list[str] = []
    violations.extend(check_gross_exposure(combined, limits))
    violations.extend(check_sleeve_positions(sleeve, limits))
    return violations


def assert_portfolio_within_limits(
    *, combined: pd.DataFrame, sleeve: pd.DataFrame, limits: RiskLimits
) -> None:
    """Raise `ValueError` joining all violations found by `check_portfolio`."""
    violations = check_portfolio(combined=combined, sleeve=sleeve, limits=limits)
    if violations:
        raise ValueError("Risk limit violations:\n" + "\n".join(violations))
