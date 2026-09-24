"""Milestone 2.7: combine a core strategy and the selected sleeve into one
target-weight portfolio (PLAN.md section 2.7), using the profile's capital
split (`config/profile.yaml`'s `capital_split`). Sleeve strategies are
equal-weighted within the sleeve's own capital share.

This module only combines already-computed weight FRAMES into one portfolio
and validates `config/portfolio.yaml`'s shape. Turning those frames into
prices, backtests, and dashboard figures -- including the holdout-unsealing
gate by entry kind (AGENTS.md, PLAN.md section 3) -- is the caller's job;
see `scripts/build_site.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

_EPS = 1e-9

_REQUIRED_CORE_KEYS = {"origin", "fn", "params"}
_REQUIRED_PROVENANCE_KEYS = {
    "ledger_run_id",
    "validation_config_hash",
    "selection_date",
    "holdout_unsealed",
}
_VALID_ORIGINS = {"baseline", "search"}


@dataclass(frozen=True)
class PortfolioWeights:
    """The three target-weight frames milestone 2.7's dashboard needs, each
    already scaled to a fraction of TOTAL portfolio capital, long-only, and
    summing to at most 1 per row (`combine_portfolio` checks this)."""

    core: pd.DataFrame  # core's contribution alone
    sleeve: pd.DataFrame  # sleeve's contribution alone (all-zero if no sleeve is selected)
    combined: pd.DataFrame  # core + sleeve


def load_portfolio_config(path: str | Path) -> dict:
    """Load and validate `config/portfolio.yaml`'s shape.

    Raises `ValueError` for anything malformed: a missing top-level key, a
    `core.origin` outside `{"baseline", "search"}`, a sleeve member missing
    `fn`/`params`, or a missing `provenance` field. An EMPTY sleeve list is
    not an error -- it is this file's normal, honest starting state (see its
    header comment).
    """
    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a mapping at the top level.")

    core = raw.get("core")
    if not isinstance(core, dict) or not _REQUIRED_CORE_KEYS.issubset(core):
        raise ValueError(f"{path}: 'core' must be a mapping with {sorted(_REQUIRED_CORE_KEYS)}.")
    if core["origin"] not in _VALID_ORIGINS:
        raise ValueError(f"{path}: core.origin must be one of {sorted(_VALID_ORIGINS)}.")

    sleeve = raw.get("sleeve")
    if not isinstance(sleeve, dict) or "strategies" not in sleeve:
        raise ValueError(f"{path}: 'sleeve' must be a mapping with a 'strategies' list.")
    members = sleeve["strategies"]
    if not isinstance(members, list):
        raise ValueError(f"{path}: sleeve.strategies must be a list (may be empty).")
    for i, member in enumerate(members):
        if not isinstance(member, dict) or not {"fn", "params"}.issubset(member):
            raise ValueError(f"{path}: sleeve.strategies[{i}] must have 'fn' and 'params'.")

    provenance = raw.get("provenance")
    if not isinstance(provenance, dict) or not _REQUIRED_PROVENANCE_KEYS.issubset(provenance):
        raise ValueError(
            f"{path}: 'provenance' must be a mapping with {sorted(_REQUIRED_PROVENANCE_KEYS)}."
        )

    return raw


def _scaled(weights: pd.DataFrame, share: float) -> pd.DataFrame:
    return weights.fillna(0.0) * share


def _assert_valid(name: str, frame: pd.DataFrame) -> None:
    if (frame < -_EPS).any().any():
        raise ValueError(f"portfolio.{name} has a negative (short) weight; long-only required.")
    if (frame.sum(axis=1) > 1 + _EPS).any():
        raise ValueError(f"portfolio.{name} weights sum above 1 on at least one day.")


def combine_portfolio(
    core_weights: pd.DataFrame,
    sleeve_member_weights: list[pd.DataFrame],
    capital_split: dict[str, float],
) -> PortfolioWeights:
    """Combine one core strategy's weights and a (possibly empty) list of
    sleeve members' weights into one target-weight portfolio, using
    `capital_split` (`config/profile.yaml`'s `{core, sleeve}` fractions of
    total capital).

    Sleeve members are equal-weighted within the sleeve's own capital share:
    each of `n` members gets `capital_split["sleeve"] / n`. An empty sleeve
    list degrades to a core-only portfolio: `sleeve` is an all-zero frame
    shaped like the (core-share-scaled) combined frame.

    Every returned frame (`PortfolioWeights.core/sleeve/combined`) is
    checked here to be long-only and to sum to at most 1 per row -- a
    defensive check on top of each component strategy's own contract
    (`qrl/strategies/__init__.py`), not just an assumption.

    Raises `ValueError` if `capital_split["core"] + capital_split["sleeve"]`
    is above 1, or if a component frame violates long-only / sum-to-1.
    """
    total_split = capital_split["core"] + capital_split["sleeve"]
    if total_split > 1 + _EPS:
        raise ValueError(f"capital_split sums to {total_split}, which is above 1.")

    core_scaled = _scaled(core_weights, capital_split["core"])

    if sleeve_member_weights:
        share_per_member = capital_split["sleeve"] / len(sleeve_member_weights)
        index = core_scaled.index
        columns = set(core_scaled.columns)
        for w in sleeve_member_weights:
            index = index.union(w.index)
            columns |= set(w.columns)
        all_columns = sorted(columns)

        sleeve_scaled = pd.DataFrame(0.0, index=index, columns=all_columns)
        for w in sleeve_member_weights:
            member_scaled = _scaled(w, share_per_member).reindex(
                index=index, columns=all_columns, fill_value=0.0
            )
            sleeve_scaled = sleeve_scaled.add(member_scaled, fill_value=0.0)
        core_scaled = core_scaled.reindex(index=index, columns=all_columns, fill_value=0.0)
    else:
        sleeve_scaled = pd.DataFrame(0.0, index=core_scaled.index, columns=core_scaled.columns)

    combined = core_scaled.add(sleeve_scaled, fill_value=0.0)

    for name, frame in (("core", core_scaled), ("sleeve", sleeve_scaled), ("combined", combined)):
        _assert_valid(name, frame)

    return PortfolioWeights(core=core_scaled, sleeve=sleeve_scaled, combined=combined)
