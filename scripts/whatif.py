"""What-if mix report (spec: docs/methodology/whatif-mix.md). Runs the decision
report's own code on an owner-chosen mix of its portfolios plus true cash, using
data up to the research end (2018-12-31) only, and writes the private file
reports/whatif-<slug>.md. It selects and recommends nothing and changes no
config. IO and wiring only; all logic lives in qrl.whatif and qrl.whatif_report.

Usage:
    python scripts/whatif.py --mix "G=0.5,A=0.3,TCASH=0.2"
    python scripts/whatif.py --mix "A=0.8,CASH=0.2" --rate 0.045
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"  # gitignored: what-if output is private
sys.path.insert(0, str(ROOT / "src"))

from qrl.criteria import load_criteria  # noqa: E402
from qrl.data import load_ohlcv  # noqa: E402
from qrl.decision import data_end, portfolio_tickers, run_decision  # noqa: E402
from qrl.decision_config import load_decision_config  # noqa: E402
from qrl.decision_withdraw import CPI_SERIES  # noqa: E402
from qrl.macro import load_macro  # noqa: E402
from qrl.periods import period_bounds  # noqa: E402
from qrl.stress import EQUITY_PROXY, load_stress_config  # noqa: E402
from qrl.whatif import mix_config, parse_mix, parse_rate, valid_names  # noqa: E402
from qrl.whatif_report import render_whatif, report_path, slug, summary_lines  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mix", default=None, help='e.g. "G=0.5,A=0.3,TCASH=0.2"')
    ap.add_argument("--rate", default=None, help="one extra annual withdrawal rate in (0, 0.10]")
    args = ap.parse_args(argv)

    try:
        criteria, _ = load_criteria(ROOT / "config" / "criteria.yaml")
        holdout_start, _ = period_bounds(criteria, "holdout")
        stress_cfg, stress_hash = load_stress_config(ROOT / "config" / "stress.yaml", holdout_start)
        cfg = load_decision_config(
            ROOT / "config" / "decision.yaml",
            ROOT / "config" / "core_candidates.yaml",
            stress_cfg,
            data_end(criteria),
        )
        given = parse_mix(args.mix, valid_names(cfg))
        mixed = mix_config(cfg, given, parse_rate(args.rate))
        held = {t for p in mixed.portfolios for t in portfolio_tickers(p)}
        tickers = sorted({EQUITY_PROXY} | held)
        # refresh=False: the cache is shared; the 2018-12-31 cut makes newer bars moot
        data = load_ohlcv(tickers, refresh=False, cache_dir=ROOT / "data" / "cache")
        missing = [t for t in tickers if t not in data["close"].columns]
        if missing:
            print(f"refused: no price data for: {missing}")
            return 1
        cpi = load_macro(
            ids=[CPI_SERIES],
            refresh=False,
            cache_dir=ROOT / "data" / "cache",
            config_path=ROOT / "config" / "macro.yaml",
        )[CPI_SERIES]
        report = run_decision(mixed, data, cpi, criteria, stress_hash)
        out = report_path(REPORTS, slug(given))
    except (ValueError, RuntimeError) as exc:  # spec refusal or failed download: nothing written
        print(f"refused: {exc}")
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_whatif(report, given), encoding="utf-8")
    print("\n".join(summary_lines(report, given, out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
