"""Load the sleeve universe: which tickers backtests may hold, and whether that
universe is survivorship-biased.

Free daily data (`qrl.data`) only has history for tickers that still trade
today, so "today's large caps" silently drops every company that shrank, was
acquired, or went bankrupt since the research period started. `config/
universe.yaml` must say so explicitly with `survivorship_biased`; this module
refuses to load a universe that omits or mistypes that flag, so the bias can
never be silently forgotten by later code (dashboard banners, criteria, etc.).
"""

from __future__ import annotations

from pathlib import Path

import yaml

DEFAULT_UNIVERSE_PATH = Path("config/universe.yaml")


def load_universe(path: str | Path = DEFAULT_UNIVERSE_PATH) -> dict:
    """Load and validate a universe definition.

    Raises ValueError if `survivorship_biased` is missing or not a bool, if
    `tickers` is empty, or if `tickers` contains duplicates.
    """
    raw = Path(path).read_text()
    universe: dict = yaml.safe_load(raw)

    biased = universe.get("survivorship_biased")
    if not isinstance(biased, bool):
        raise ValueError("universe must set survivorship_biased to true or false")

    tickers = universe.get("tickers") or []
    if not tickers:
        raise ValueError("universe has no tickers")

    seen: set[str] = set()
    dupes = {t for t in tickers if t in seen or seen.add(t)}  # type: ignore[func-returns-value]
    if dupes:
        raise ValueError(f"universe has duplicate tickers: {sorted(dupes)}")

    return universe
