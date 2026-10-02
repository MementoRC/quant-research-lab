"""Download SEC EDGAR company facts and report, per ticker, which concepts were
found and the earliest `filed` date of each (the earliest a fact can be usable).

Needs a contact email: env SEC_USER_AGENT_EMAIL or gitignored config/sec.local.yaml.

Usage:
    python scripts/fetch_fundamentals.py --tickers AAPL MSFT BRK-B
    python scripts/fetch_fundamentals.py                  # whole config/universe.yaml
    python scripts/fetch_fundamentals.py --refresh        # re-download cached JSON
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qrl.fundamentals import SecIdentityError, load_facts  # noqa: E402
from qrl.universe import load_universe  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tickers", nargs="+", default=None)
    ap.add_argument("--universe", default=str(ROOT / "config" / "universe.yaml"))
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args(argv)

    tickers = args.tickers or load_universe(args.universe)["tickers"]
    try:
        facts = load_facts(tickers, refresh=args.refresh)
    except SecIdentityError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2

    for t in tickers:
        sub = facts[facts["ticker"] == t]
        if sub.empty:
            print(f"{t}: no facts")
            continue
        first = sub.groupby("concept")["filed"].min()
        print(f"{t}: {len(first)} concepts")
        for concept, filed in first.sort_index().items():
            print(f"  {concept:<55} earliest filed {filed.date()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
