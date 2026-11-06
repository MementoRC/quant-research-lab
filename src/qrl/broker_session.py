"""Dates of the IB paper rebalancer (spec "Evening run" step 2): the
America/New_York calendar date of a UTC instant, and the session date, the
latest bar shared by the held and non-zero-target symbols (never the
wall-clock date). A stale symbol that is neither held nor targeted is not
passed in, so it is ignored."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd

NEW_YORK = ZoneInfo("America/New_York")


def ny_time(now: datetime) -> datetime:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("the clock must return a timezone-aware datetime")
    return now.astimezone(NEW_YORK)


def ny_date(now: datetime) -> date:
    return ny_time(now).date()


def session_date(close: pd.DataFrame, symbols: Iterable[str]) -> date:
    """The earliest of the symbols' last valid close dates. Symbols without a
    column or without any close are skipped (sizing refuses them); with none
    left, the frame's last date. An empty frame has no session."""
    if len(close.index) == 0:
        raise ValueError("the closes frame is empty; there is no session date")
    lasts: list[pd.Timestamp] = []
    for symbol in symbols:
        if symbol in close.columns:
            valid = close.index[close[symbol].notna()]
            if len(valid):
                lasts.append(pd.Timestamp(valid[-1]))
    last = min(lasts) if lasts else pd.Timestamp(close.index[-1])
    return last.date()
