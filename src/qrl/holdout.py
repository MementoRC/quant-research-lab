"""The single guarded gateway to the sealed holdout period (PLAN.md 2.6, and
section 3's "The holdout was contaminated").

`qrl.periods.slice_period` raises `HoldoutSealedError` for the holdout
period unless its `unseal_holdout` flag is passed as true. `unseal` below is
the ONLY place in `src/` allowed to do that -- see `tests/test_holdout.py`
for the test that enforces it across the whole package, not just this
file.

The holdout is meant to be unsealed exactly once, for the final, already-
chosen walk-forward process (`qrl.walkforward.walk_forward`), never to pick
between candidates or tune meta-settings (that is `qrl.walkforward.
tune_meta`'s job, and it refuses to touch holdout dates on its own). `unseal`
enforces this mechanically:

- refuses outright unless `confirm=True`,
- refuses a second call once `holdout_events` already has a record, unless
  `force=True` AND a `reason` is given -- and even then records the forced
  repeat as a forced event, never silently as an ordinary first one,
- always records what was unsealed, when, the git commit, and the reason,
  before returning the sliced data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .periods import slice_period

if TYPE_CHECKING:
    from .ledger import Ledger

_DEFAULT_WHAT_UNSEALED = "final chosen walk-forward process"


class HoldoutAlreadyUnsealedError(RuntimeError):
    """Raised when the holdout has already been unsealed once and `force`
    was not passed to authorize a repeat."""


def unseal(
    ledger: Ledger,
    obj,
    criteria: dict,
    reason: str,
    *,
    what_unsealed: str = _DEFAULT_WHAT_UNSEALED,
    confirm: bool = False,
    force: bool = False,
    git_commit: str | None = None,
):
    """Unseal the holdout period of `obj` (anything `qrl.periods.slice_period`
    accepts -- a price frame, a weights frame, ...) for the final chosen
    process, and return the holdout-sliced result.

    Refuses (`ValueError`) unless `confirm=True`. Refuses a second call
    (`HoldoutAlreadyUnsealedError`, naming the earlier event's timestamp,
    git commit, and reason) once `ledger.list_holdout_events()` already has
    a record, unless `force=True` and `reason` is non-empty -- a forced
    repeat is itself recorded, with `forced=True`, never merged into or
    mistaken for the honest first unsealing.

    This is the one place in `src/` that sets the `unseal_holdout` flag on
    `qrl.periods.slice_period` -- see this module's docstring and
    `tests/test_holdout.py`.
    """
    if not confirm:
        raise ValueError(
            "holdout.unseal refuses to run without confirm=True -- the holdout is "
            "unsealed exactly once, for the final chosen process (PLAN.md 2.6)."
        )

    prior = ledger.list_holdout_events()
    if prior:
        if not force:
            first = prior[0]
            raise HoldoutAlreadyUnsealedError(
                "The holdout was already unsealed on "
                f"{first['created_at']} (commit {first['git_commit']!r}) for "
                f"{first['what_unsealed']!r}, reason: {first['reason']!r}. Pass "
                "force=True with a new reason to unseal again -- this will itself "
                "be recorded as a forced repeat unsealing."
            )
        if not reason:
            raise ValueError("A forced repeat unsealing still requires a reason.")

    ledger.record_holdout_event(what_unsealed, reason, git_commit=git_commit, forced=bool(prior))
    return slice_period(obj, criteria, "holdout", unseal_holdout=True)
