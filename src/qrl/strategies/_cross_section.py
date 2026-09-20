"""Shared cross-sectional sleeve mechanics used by every multi-ticker
strategy family in this package (trend_pullback, low_range_close,
quiet_pullback).

Each family reduces its own logic to four same-shaped frames (rows = dates,
columns = tickers):
    entry       -- bool, True where a name is a candidate to buy today.
    exit_signal -- bool, True where a currently held name's technical exit
                   fires today (independent of how long it has been held).
    score       -- float, used only to rank *candidate* entries on a day with
                   free slots; higher wins. Values for non-candidates are
                   ignored.
    warmup      -- bool, True where the family's own indicators are not yet
                   available for that name (not yet listed, or not enough
                   history for its own rolling windows).

`build_weights` turns those into capped, equal-weight targets. Only the
*leading, contiguous* run of rows where every column is still warming up is
set to NaN -- i.e. the prefix before the first date on which any single
ticker in the universe could act at all. From that first actionable row
onward, every column is numeric, unconditionally, for the rest of the
index: a ticker that is individually still warming up (a late starter), not
entry-eligible, or simply not selected gets 0.0, never NaN -- even if every
column's indicator happens to go NaN again together on some later row (a
shared data gap poisoning every column's rolling window at once). That
later case must NOT be NaN'd out: a name already held keeps its weight
across such a row rather than being silently flattened (and
`engine.run_backtest`'s `tw.fillna(0.0)` would mask a real NaN there
without raising, letting the portfolio silently go flat and pay unwarranted
turnover). This matters for staggered universes (real tickers start on
different dates): gating the whole strategy's start on the *slowest*
ticker's warm-up, rather than the earliest, would silently discard years of
otherwise-usable history (the engine's own start detection requires every
column non-NaN on the first row it uses). A ticker's own warm-up guard
(comparisons against a NaN rolling indicator are false, never true) keeps
it out of `held` until its indicators are ready, so a late starter still
becomes eligible exactly once its own warm-up completes. Delisting/exit
timing is deliberately not duplicated here; `qrl.tradability.
exit_before_delisting` is applied downstream and remains the single place
that forces an exit before a ticker's price history ends.

A name already held stays held until its own exit fires (technical or, if
`exit_days` is given, time-based) -- a new, higher-ranked signal never
bumps out a name that is still valid to hold. Ties in `score` are broken by
column order (ticker name) so runs are reproducible.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _leading_true_run(mask: pd.Series) -> pd.Series:
    """`mask` restricted to its leading contiguous run of True, from row 0.

    Any True values after the first False are dropped: a shared data gap
    poisoning every column's indicator on some later row must not be
    treated the same as the strategy's actual warm-up prefix.
    """
    arr = mask.to_numpy()
    false_positions = np.flatnonzero(~arr)
    first_false = int(false_positions[0]) if false_positions.size else len(arr)
    prefix = np.zeros(len(arr), dtype=bool)
    prefix[:first_false] = True
    return pd.Series(prefix, index=mask.index)


def consecutive_true(mask: pd.DataFrame) -> pd.DataFrame:
    """Per-column count of consecutive True values ending at each row.

    Standard reset-and-cumsum trick: `(~mask).cumsum()` increments a group id
    every time `mask` is False, then summing `mask` within each group counts
    how many True rows have accumulated since the last False.
    """

    def _col(s: pd.Series) -> pd.Series:
        groups = (~s.fillna(False)).cumsum()
        return s.fillna(False).groupby(groups).cumsum()

    return mask.apply(_col)


def build_weights(
    entry: pd.DataFrame,
    exit_signal: pd.DataFrame,
    score: pd.DataFrame,
    warmup: pd.DataFrame,
    *,
    max_positions: int,
    capital: float,
    exit_days: int | None = None,
) -> pd.DataFrame:
    """Rank, cap, and equal-weight cross-sectional entries.

    A held name exits when `exit_signal` fires for it, or (if `exit_days` is
    set) once it has been held for `exit_days` bars, whichever comes first.
    Free slots are then filled from `entry` candidates, best `score` first,
    ties broken by ticker name.

    Only the leading, contiguous prefix of rows where every column is still
    warming up is NaN; from the first actionable row onward every column is
    always a number, even if a later row's `warmup` is all-True again (see
    module docstring).
    """
    cols = list(entry.columns)
    idx = entry.index
    col_pos = {c: j for j, c in enumerate(cols)}

    entry_np = entry.to_numpy()
    exit_np = exit_signal.to_numpy()
    score_np = score.to_numpy()
    out = np.zeros((len(idx), len(cols)))

    held: set[str] = set()
    entered_at: dict[str, int] = {}
    for i in range(len(idx)):
        to_drop = set()
        for c in held:
            j = col_pos[c]
            timed_out = exit_days is not None and (i - entered_at[c]) >= exit_days
            if bool(exit_np[i, j]) or timed_out:
                to_drop.add(c)
        held -= to_drop
        for c in to_drop:
            entered_at.pop(c, None)

        free = max_positions - len(held)
        if free > 0:
            candidates = [c for c in cols if c not in held and bool(entry_np[i, col_pos[c]])]
            candidates.sort(key=lambda c: (-score_np[i, col_pos[c]], c))
            for c in candidates[:free]:
                held.add(c)
                entered_at[c] = i

        if held:
            w = capital / len(held)
            for c in held:
                out[i, col_pos[c]] = w

    weights = pd.DataFrame(out, index=idx, columns=cols)
    # Whole-row NaN only for the leading prefix where every ticker is still
    # warming up. Once any one ticker has been ready on some earlier row,
    # every later row stays numeric (0.0 default from `out`) even if
    # `warmup` happens to be all-True again -- e.g. a data gap that hits
    # every column's rolling window on the same row must not be confused
    # with the strategy's actual start-up warmup.
    leading_warmup = _leading_true_run(warmup.all(axis=1))
    weights.loc[leading_warmup] = np.nan
    return weights
