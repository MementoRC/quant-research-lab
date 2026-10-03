"""Smoke run for the factor families (Phase 4, milestone 3): weights for the LATEST
date only, from cached prices, cached SEC facts and the checked-in PIT membership.

    python scripts/factor_smoke.py

Prints, per family with default params, how many names are held and the first five
tickers, and checks they are current members and the weights sum to <= 1. It computes
no returns and no metrics: any performance number must come from the search ledger.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qrl.data import load_ohlcv  # noqa: E402
from qrl.factor_data import default_provider, factor_universe  # noqa: E402
from qrl.strategies import FACTOR_FAMILIES, SLEEVE_REGISTRY  # noqa: E402

TAIL_ROWS = 400  # enough for the latest rebalance and the volume scale check


def main() -> int:
    provider = default_provider()
    tickers = factor_universe(provider.membership)
    frames = load_ohlcv(tickers)
    close = frames["close"].tail(TAIL_ROWS)
    volume = frames["volume"].reindex(close.index)
    cols = [t for t in tickers if t in close.columns]
    print(
        f"universe {len(tickers)} tickers ever a member, {len(cols)} with prices; "
        f"latest date {close.index[-1].date()}"
    )
    for name in sorted(FACTOR_FAMILIES):
        spec = SLEEVE_REGISTRY[name]
        args = [
            close[cols] if f == "close" else provider.panel(f, close.index, cols, volume[cols])
            for f in spec.fields
        ]
        member = args[1]
        last = spec.weights(*args).iloc[-1]
        names = list(last.index[last > 0])
        assert names, f"{name}: no names held"
        assert last.sum() <= 1 + 1e-9, f"{name}: weights sum to {last.sum()}"
        assert member.iloc[-1][names].all(), f"{name}: holds a non-member"
        print(f"{name}: {len(names)} names held, sum {last.sum():.3f}, first 5: {names[:5]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
