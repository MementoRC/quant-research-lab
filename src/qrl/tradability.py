"""Exit positions before a ticker's price history ends (delisting/acquisition).

Free daily data has no forward-looking corporate-actions calendar: when a
stock is delisted or acquired, its history in `qrl.data` simply stops. Backtesting
a strategy that keeps a nonzero target weight after that point asks the engine
to price a position it has no data for, which `qrl.engine.run_backtest`
correctly refuses to do (it raises on a missing price for a held position,
rather than silently treating it as a zero return).

`exit_before_delisting` uses knowledge of *where each ticker's series ends* to
force an exit before the last bar. This is a deliberate, documented look-ahead:
it does not use any future price information to decide which stocks to hold,
size, or enter -- only the timing of the exit from a position the strategy
already chose to hold. It approximates what an announced delisting or
acquisition would have done to a real portfolio (an early, forced sale), not a
free early-warning signal.
"""

from __future__ import annotations

import pandas as pd


def exit_before_delisting(
    weights: pd.DataFrame, open_: pd.DataFrame, close: pd.DataFrame
) -> pd.DataFrame:
    """Zero target weights so a truncated ticker is sold before its last close.

    The engine executes `weights.loc[t]` at the open of day t+1. For a ticker
    whose last valid bar (both open and close present) is day L earlier than
    the frame's last day, this forces the target weight to 0 from row L-1
    onward -- so the position is sold at the open of day L, one day before the
    final close -- and on any row t whose t+1 bar is not fully priced, so the
    engine is never asked to execute into a day it cannot price.
    """
    idx = weights.index
    cols = list(weights.columns)
    open_ = open_.reindex(index=idx, columns=cols)
    close = close.reindex(index=idx, columns=cols)
    out = weights.copy()

    priced = open_.notna() & close.notna()
    # A row's own next-day price is unknown for the very last row of the frame;
    # treat that as fine (it is the strategy's live, not-yet-executed signal),
    # not as a reason to force an exit.
    next_priced = priced.shift(-1, fill_value=True)

    for col in cols:
        col_priced = priced[col]
        if not col_priced.any():
            out[col] = 0.0
            continue
        last_pos = int(col_priced.to_numpy().nonzero()[0][-1])
        if last_pos < len(idx) - 1:
            exit_from = max(last_pos - 1, 0)
            out.loc[idx[exit_from:], col] = 0.0
        out.loc[~next_priced[col], col] = 0.0

    return out
