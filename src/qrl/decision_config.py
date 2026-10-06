"""Decision helper configuration and portfolio model (spec:
docs/methodology/decision-helper.md).

Every portfolio is 100% of capital and is a list of (candidate, share) parts:
A-G come from `config/core_candidates.yaml` unchanged, static mixes are
`core_mix` candidates, and a blend is the share-weighted union of its
components' parts. Pure functions only.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

from .core_compare import Candidate, branch_mixes


@dataclass(frozen=True)
class Portfolio:
    """100% of capital: `parts` are (candidate, share of capital) pairs whose
    shares sum to 1. A-G and static mixes have one part; a blend has several."""

    id: str
    label: str
    parts: tuple[tuple[Candidate, float], ...]


def portfolio_states(p: Portfolio) -> dict[str, dict[str, float]]:
    """Fixed weights (fractions of capital) per state. A portfolio without a
    switching part has one state, `static`. A switching part contributes its
    risk_on / risk_off branches (`core_compare.branch_mixes`), combined with
    the other parts' fixed weights, so a blend with one switching part has
    exactly two states."""
    options: list[list[tuple[str, dict[str, float]]]] = []
    for cand, share in p.parts:
        branches = branch_mixes(cand) or {"": dict(cand.params["risk_on"])}
        options.append(
            [
                (name, {t: share * float(w) for t, w in mix.items()})
                for name, mix in branches.items()
            ]
        )
    states: dict[str, dict[str, float]] = {}
    for combo in itertools.product(*options):
        name = "+".join(n for n, _ in combo if n) or "static"
        mix: dict[str, float] = {}
        for _, part in combo:
            for ticker, weight in part.items():
                mix[ticker] = mix.get(ticker, 0.0) + weight
        states[name] = mix
    return states


def held_tickers(portfolios: list[Portfolio]) -> set[str]:
    """Every fund any portfolio holds in any state (signal-only tickers excluded)."""
    return {
        t
        for p in portfolios
        for mix in portfolio_states(p).values()
        for t, w in mix.items()
        if w > 0
    }
