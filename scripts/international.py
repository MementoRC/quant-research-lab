"""International final test (spec: docs/methodology/international-test.md).

    check-data  download and report coverage for one market set: dates, bar
                counts, gaps, proxy coverage and the GC=F vs GLD daily
                correlation. Never prints or stores a result.
    run         the one sealed run of an accepted rule on one market set. The
                first confirmed run pins config/international.yaml's sha256
                in the ledger; later runs refuse if it differs.

IO and wiring only; the logic lives in qrl.international.

Usage:
    python scripts/international.py check-data --set main
    python scripts/international.py run --set main --test-id 123 \\
        --reason "owner go-ahead <date>" --confirm
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qrl.data import coverage_report, load_prices  # noqa: E402
from qrl.international import (  # noqa: E402
    InternationalConfig,
    build_panel,
    gold_correlation,
    load_international_config,
)
from qrl.ledger import DEFAULT_LEDGER_PATH  # noqa: E402  (Task 11 adds Ledger, LedgerError)
from qrl.macro import fetch_series  # noqa: E402

CACHE_DIR = ROOT / "data" / "cache"
PIN_NAME = "international"


def load_raw(
    cfg: InternationalConfig, set_name: str, refresh: bool, cache_dir: Path
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, dict[str, pd.Series]]:
    """Prices for one set's markets and the defensive funds, the gold proxy
    and the FRED series (Treasury yields and DTB3). Refuses (RuntimeError) if
    anything is missing."""
    tickers = [*cfg.market_set(set_name).markets, *cfg.funds]
    open_, close = load_prices(
        tickers, start=cfg.download_start, refresh=refresh, cache_dir=cache_dir
    )
    missing = [t for t in tickers if t not in close.columns]
    if missing:  # the loader drops tickers it cannot fetch
        raise RuntimeError(f"no price data for: {missing}")
    _, gold = load_prices(
        [cfg.gold_ticker], start=cfg.download_start, refresh=refresh, cache_dir=cache_dir
    )
    if cfg.gold_ticker not in gold.columns:
        raise RuntimeError(f"no price data for: {cfg.gold_ticker}")
    yields = {
        fred: fetch_series(fred, refresh=refresh, cache_dir=cache_dir) for fred in cfg.fred_ids
    }
    return open_[tickers], close[tickers], gold[cfg.gold_ticker], yields


def _span(series: pd.Series) -> str:
    valid = series.dropna()
    if valid.empty:
        return "no data"
    return f"{valid.index[0].date()} to {valid.index[-1].date()}, {len(valid)} bars"


def check_data(cfg: InternationalConfig, set_name: str, refresh: bool, cache_dir: Path) -> int:
    try:
        cfg.market_set(set_name)
        fund_open, fund_close, gold, yields = load_raw(cfg, set_name, refresh, cache_dir)
    except (RuntimeError, ValueError) as exc:
        print(f"refused: {exc}")
        return 1
    print(f"Coverage, set {set_name} (dates and bar counts only):")
    table = coverage_report(fund_open, fund_close)[["first_date", "last_date", "n_bars", "gaps"]]
    print(table.to_string())
    print(f"{cfg.gold_ticker}: {_span(gold)}")
    for fred, series in yields.items():
        print(f"FRED {fred}: {_span(series)}")
    _, panel_close = build_panel(fund_open, fund_close, yields, gold, cfg)
    print("Defensive legs with proxies spliced in, first date per leg:")
    for fund in [*cfg.funds, "CASH"]:
        print(f"  {fund}: {panel_close[fund].first_valid_index()}")
    start, end = cfg.gold_check
    corr = gold_correlation(panel_close[cfg.gold_ticker], panel_close[cfg.gold_fund], start, end)
    ok = corr is not None and corr >= cfg.gold_min_correlation
    shown = "n/a" if corr is None else f"{corr:.3f}"
    note = "ok" if ok else "below the minimum: gold-holding rules use the late window only"
    print(
        f"{cfg.gold_ticker} vs {cfg.gold_fund} daily correlation {start.date()} to "
        f"{end.date()}: {shown} ({note})"
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", default=str(ROOT / "config" / "international.yaml"))
    common.add_argument("--ledger", default=str(ROOT / DEFAULT_LEDGER_PATH))
    common.add_argument("--cache-dir", default=str(CACHE_DIR))
    common.add_argument("--out-dir", default=str(ROOT / "research"))
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="command", required=True)
    p_check = sub.add_parser("check-data", parents=[common])
    p_check.add_argument("--set", required=True)
    p_check.add_argument("--refresh", action="store_true")
    p_run = sub.add_parser("run", parents=[common])
    p_run.add_argument("--set", required=True)
    p_run.add_argument("--test-id", type=int, required=True)
    p_run.add_argument("--reason", default="", help="the owner's go-ahead and acceptance evidence")
    p_run.add_argument("--confirm", action="store_true")
    return ap


def run(args: argparse.Namespace, cfg: InternationalConfig, cfg_sha: str) -> int:
    raise NotImplementedError  # Task 11


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        cfg, cfg_sha = load_international_config(args.config)
    except (ValueError, KeyError, OSError) as exc:
        print(f"refused: {exc}")
        return 1
    if args.command == "check-data":
        return check_data(cfg, args.set, args.refresh, Path(args.cache_dir))
    return run(args, cfg, cfg_sha)


if __name__ == "__main__":
    sys.exit(main())
