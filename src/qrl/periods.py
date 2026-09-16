"""Period slicing with a sealed holdout.

The holdout exists to answer one question, once: does the final choice still
work on data it has never influenced? Every peek makes that answer less honest,
so slicing it requires an explicit, deliberate flag.
"""

from __future__ import annotations

import pandas as pd

PERIOD_NAMES = ("research", "validation", "holdout")


class HoldoutSealedError(RuntimeError):
    pass


def period_bounds(criteria: dict, name: str) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    p = criteria["periods"][name]
    start = pd.Timestamp(p["start"]) if p.get("start") else None
    end = pd.Timestamp(p["end"]) if p.get("end") else None
    return start, end


def slice_period(obj, criteria: dict, name: str, unseal_holdout: bool = False):
    if name not in PERIOD_NAMES:
        raise KeyError(f"Unknown period '{name}'. Use one of {PERIOD_NAMES}.")
    if name == "holdout" and not unseal_holdout:
        raise HoldoutSealedError(
            "The holdout period is sealed. Pass unseal_holdout=True only for fixed "
            "baselines or a one-time final check of a finished portfolio."
        )
    start, end = period_bounds(criteria, name)
    return obj.loc[start:end]
