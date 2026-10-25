"""Staged entry report (spec: docs/methodology/staged-entry.md). Compares
investing the starting cash at once with equal monthly tranches over the
periods of config/staged_entry.yaml, while drawing the fixed CPI-indexed
income, in the decision helper's historical view and the long run's resampled
paths. It uses data up to the research end (2018-12-31) only and writes
research/staged_entry.md. It selects and recommends nothing and changes no
config. IO and wiring only; all logic lives in qrl.decision_staged and
qrl.staged_entry_report.

Usage:
    python scripts/staged_entry.py
    python scripts/staged_entry.py --staged-config config/staged_entry.yaml --out-md research/staged_entry.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qrl.criteria import load_criteria  # noqa: E402
from qrl.data import load_ohlcv  # noqa: E402
from qrl.decision import data_end, portfolio_tickers  # noqa: E402
from qrl.decision_config import load_decision_config  # noqa: E402
from qrl.decision_staged import load_staged_config, run_staged_entry  # noqa: E402
from qrl.decision_withdraw import CPI_SERIES  # noqa: E402
from qrl.longrun import CASH_ID, check_withdrawal_rates, load_longrun_config  # noqa: E402
from qrl.macro import load_macro  # noqa: E402
from qrl.periods import period_bounds  # noqa: E402
from qrl.staged_entry_report import render_markdown  # noqa: E402
from qrl.stress import load_stress_config  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=str(ROOT / "config" / "decision.yaml"))
    ap.add_argument("--longrun-config", default=str(ROOT / "config" / "longrun.yaml"))
    ap.add_argument("--staged-config", default=str(ROOT / "config" / "staged_entry.yaml"))
    ap.add_argument("--out-md", default=str(ROOT / "research" / "staged_entry.md"))
    args = ap.parse_args(argv)

    try:
        criteria, _ = load_criteria(ROOT / "config" / "criteria.yaml")
        holdout_start, _ = period_bounds(criteria, "holdout")
        stress_cfg, _ = load_stress_config(ROOT / "config" / "stress.yaml", holdout_start)
        cfg = load_decision_config(
            args.config, ROOT / "config" / "core_candidates.yaml", stress_cfg, data_end(criteria)
        )
        lcfg = load_longrun_config(args.longrun_config, cfg.sha256)
        check_withdrawal_rates(lcfg, cfg)
        scfg = load_staged_config(args.staged_config, cfg, lcfg)
        by_id = {p.id: p for p in cfg.portfolios}
        tickers = sorted(
            {t for pid in [*scfg.portfolios, CASH_ID] for t in portfolio_tickers(by_id[pid])}
        )
        # refresh=False: the cache is shared with other runs, so only tickers not
        # yet cached are fetched; the 2018-12-31 cut makes newer bars moot
        data = load_ohlcv(tickers, refresh=False, cache_dir=ROOT / "data" / "cache")
        missing = [t for t in tickers if t not in data["close"].columns]
        if missing:
            # the loader drops tickers it cannot fetch
            print(f"refused: no price data for: {missing}")
            return 1
        # refresh=False: the cache is shared; only an uncached series is fetched, and
        # the 2018-12-31 cut makes newer values moot
        cpi = load_macro(
            ids=[CPI_SERIES],
            refresh=False,
            cache_dir=ROOT / "data" / "cache",
            config_path=ROOT / "config" / "macro.yaml",
        )[CPI_SERIES]
        report = run_staged_entry(scfg, cfg, lcfg, data, cpi, criteria)
    except (ValueError, RuntimeError) as exc:  # spec refusal or failed download: nothing written
        print(f"refused: {exc}")
        return 1
    markdown = render_markdown(report)
    out = Path(args.out_md)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
