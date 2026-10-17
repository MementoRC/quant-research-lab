"""What-if mix (spec: docs/methodology/whatif-mix.md): an owner-chosen blend of
the decision report's portfolios plus true cash, built by the loader's own
`_blend` / `_check_full` and run through `qrl.decision.run_decision`. No new
maths. Pure functions; the script does the IO.
"""

from __future__ import annotations

import math
from dataclasses import replace

from .core_compare import Candidate
from .decision_config import (
    SUM_TOLERANCE,
    DecisionConfig,
    Portfolio,
    blend_portfolio,
    check_full,
)

TCASH = "TCASH"  # true cash: the cash leg of the cash-assumption rows
MIX_ID = "MIX"
MIX_CASH_ID = "MIX-TCASH"
MAX_RATE = 0.10  # whatif's own bound on --rate (the loader accepts (0, 1))

Shares = list[tuple[str, float]]  # (name, share) in input order


def _item(raw: str) -> tuple[str, float]:
    name, sep, text = raw.partition("=")
    name, text = name.strip(), text.strip()
    if not sep or not name or not text or "=" in text:
        raise ValueError(f"mix item {raw.strip()!r} is not NAME=SHARE")
    try:
        share = float(text)
    except ValueError:
        raise ValueError(f"mix share {text!r} for {name} is not a number") from None
    if not math.isfinite(share) or share < 0:
        raise ValueError(f"mix share for {name} must be a finite number >= 0, got {text!r}")
    return name, share


def parse_mix(text: str | None, valid: list[str]) -> Shares:
    """`NAME=SHARE,...` as (name, share) in input order, zero shares dropped
    after being checked like the others. Raises ValueError (a refusal) on a
    missing or empty mix, a bad item or share, a repeated or unknown name, or
    shares not summing to 1 within the loader's 1e-9."""
    if text is None or not text.strip():
        raise ValueError('--mix is required, e.g. --mix "G=0.5,A=0.3,TCASH=0.2"')
    items = [_item(raw) for raw in text.split(",")]
    names = [name for name, _ in items]
    repeated = sorted({n for n in names if names.count(n) > 1})
    if repeated:
        raise ValueError(f"mix names repeated: {repeated}")
    unknown = sorted(set(names) - set(valid))
    if unknown:
        raise ValueError(f"unknown mix name(s) {unknown}; valid names: {', '.join(valid)}")
    total = sum(share for _, share in items)
    if abs(total - 1.0) > SUM_TOLERANCE:
        raise ValueError(f"mix shares sum to {total:.12g}, not 1")
    return [(name, share) for name, share in items if share > 0]


def parse_rate(text: str | None) -> float | None:
    """The optional `--rate`: a number in (0, MAX_RATE]; None when absent."""
    if text is None:
        return None
    try:
        rate = float(text)
    except ValueError:
        raise ValueError(f"--rate {text!r} is not a number") from None
    if not (math.isfinite(rate) and 0 < rate <= MAX_RATE):
        raise ValueError(f"--rate must be in (0, {MAX_RATE:g}], got {text!r}")
    return rate


def split_shares(given: Shares) -> tuple[Shares, float]:
    """(the non-cash shares renormalised to sum to 1, the TCASH share). With no
    non-cash part the first element is empty. The TCASH share is clamped to 1 so a
    sum within the 1e-9 input tolerance above 1 cannot trip the cash row's check."""
    tcash = min(sum(share for name, share in given if name == TCASH), 1.0)
    noncash = [(name, share) for name, share in given if name != TCASH]
    total = sum(share for _, share in noncash)
    return [(name, share / total) for name, share in noncash], tcash


def merge_parts(
    parts: tuple[tuple[Candidate, float], ...],
) -> tuple[tuple[Candidate, float], ...]:
    """Parts with the same candidate id summed, in first-appearance order, so a
    switching candidate is never held twice (it would give impossible states)."""
    merged: dict[str, tuple[Candidate, float]] = {}
    for cand, share in parts:
        first, total = merged.get(cand.id, (cand, 0.0))
        merged[cand.id] = (first, total + share)
    return tuple(merged.values())


def mix_portfolio(noncash: Shares, cfg: DecisionConfig) -> Portfolio | None:
    """`MIX`: the renormalised non-cash shares, flattened as `_blend` flattens a
    blend, same-candidate parts merged, checked fully invested in every state.
    None without a non-cash part."""
    if not noncash:
        return None
    label = "Your mix: " + " + ".join(f"{share * 100:.4g}% {name}" for name, share in noncash)
    raw = {"id": MIX_ID, "label": label, "parts": dict(noncash)}
    flat = blend_portfolio(raw, {p.id: p for p in cfg.portfolios})
    mix = replace(flat, parts=merge_parts(flat.parts))
    check_full(mix)
    return mix
