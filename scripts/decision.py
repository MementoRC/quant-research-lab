"""Decision helper report (spec: docs/methodology/decision-helper.md).
Compares the fixed portfolios of config/decision.yaml (A-G from
config/core_candidates.yaml, read unchanged) under historical windows,
judgement-based shocks and CPI-indexed withdrawals, using data up to the
research end (2018-12-31) only, and writes research/decision.md. It selects
and recommends nothing and changes no config. IO and wiring only; all logic
lives in qrl.decision, qrl.decision_config, qrl.decision_withdraw and
qrl.decision_report.

Usage:
    python scripts/decision.py
    python scripts/decision.py --config config/decision.yaml --out-md research/decision.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qrl.criteria import load_criteria  # noqa: E402
from qrl.data import load_ohlcv  # noqa: E402
from qrl.decision import data_end, portfolio_tickers, run_decision  # noqa: E402
from qrl.decision_config import load_decision_config  # noqa: E402
from qrl.decision_report import render_markdown  # noqa: E402
from qrl.decision_withdraw import CPI_SERIES  # noqa: E402
from qrl.macro import load_macro  # noqa: E402
from qrl.periods import period_bounds  # noqa: E402
from qrl.stress import EQUITY_PROXY, load_stress_config  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=str(ROOT / "config" / "decision.yaml"))
    ap.add_argument("--out-md", default=str(ROOT / "research" / "decision.md"))
    args = ap.parse_args(argv)

    try:
        criteria, _ = load_criteria(ROOT / "config" / "criteria.yaml")
        holdout_start, _ = period_bounds(criteria, "holdout")
        stress_cfg, stress_hash = load_stress_config(ROOT / "config" / "stress.yaml", holdout_start)
        cfg = load_decision_config(
            args.config, ROOT / "config" / "core_candidates.yaml", stress_cfg, data_end(criteria)
        )
        tickers = sorted({EQUITY_PROXY} | {t for p in cfg.portfolios for t in portfolio_tickers(p)})
        # refresh=False: the cache is shared with other runs, so only tickers not
        # yet cached (e.g. RSP) are fetched; the 2018-12-31 cut makes newer bars moot
        data = load_ohlcv(tickers, refresh=False, cache_dir=ROOT / "data" / "cache")
        missing = [t for t in tickers if t not in data["close"].columns]
        if missing:
            # the loader drops tickers it cannot fetch
            print(f"refused: no price data for: {missing}")
            return 1
        cpi = load_macro(
            ids=[CPI_SERIES],
            refresh=True,
            cache_dir=ROOT / "data" / "cache",
            config_path=ROOT / "config" / "macro.yaml",
        )[CPI_SERIES]
        report = run_decision(cfg, data, cpi, criteria, stress_hash)
    except ValueError as exc:  # a spec refusal (config or run): nothing is written
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
