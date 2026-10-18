"""What-if shock report (spec: docs/methodology/whatif-shock.md). Puts an
owner-defined stretch of bad years (a YAML file) in front of each start year's
real history and runs the decision report's own withdrawal code, using data up
to the research end (2018-12-31) only. Writes the private file
reports/whatif-shock-<name>.md. It selects and recommends nothing and changes no
config or shock file. IO and wiring only; the logic lives in qrl.shock and
qrl.shock_report.

Usage:
    python scripts/whatif_shock.py --shock my-shock.yaml
    python scripts/whatif_shock.py --shock my-shock.yaml --mix "G=0.5,A=0.3,TCASH=0.2" --rate 0.045
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
from qrl.decision import data_end, portfolio_tickers  # noqa: E402
from qrl.decision_config import load_decision_config  # noqa: E402
from qrl.decision_withdraw import CPI_SERIES  # noqa: E402
from qrl.macro import load_macro  # noqa: E402
from qrl.periods import period_bounds  # noqa: E402
from qrl.shock import check_fund_map, extend_config, load_shock, run_shock  # noqa: E402
from qrl.shock_report import render_shock, summary_lines  # noqa: E402
from qrl.stress import EQUITY_PROXY, load_stress_config  # noqa: E402
from qrl.whatif import parse_mix, parse_rate, valid_names  # noqa: E402
from qrl.whatif_report import report_path  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--shock", default=None, help="YAML shock file (read only; relative to cwd)")
    ap.add_argument("--mix", default=None, help='optional, e.g. "G=0.5,A=0.3,TCASH=0.2"')
    ap.add_argument("--rate", default=None, help="one extra annual withdrawal rate in (0, 0.10]")
    args = ap.parse_args(argv)

    try:
        if args.shock is None:
            raise ValueError("--shock is required, e.g. --shock my-shock.yaml")
        shock = load_shock(Path(args.shock))
        criteria, _ = load_criteria(ROOT / "config" / "criteria.yaml")
        holdout_start, _ = period_bounds(criteria, "holdout")
        stress_cfg, stress_hash = load_stress_config(ROOT / "config" / "stress.yaml", holdout_start)
        cfg = load_decision_config(
            ROOT / "config" / "decision.yaml",
            ROOT / "config" / "core_candidates.yaml",
            stress_cfg,
            data_end(criteria),
        )
        given = None if args.mix is None else parse_mix(args.mix, valid_names(cfg))
        shocked = extend_config(cfg, given, parse_rate(args.rate))
        check_fund_map(shocked.portfolios)
        held = {t for p in shocked.portfolios for t in portfolio_tickers(p)}
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
        report = run_shock(shocked, data, cpi, criteria, shock, stress_hash)
        out = report_path(REPORTS, f"shock-{shock.name}")
    except (ValueError, RuntimeError) as exc:  # spec refusal or failed download: nothing written
        print(f"refused: {exc}")
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_shock(report, given), encoding="utf-8")
    print("\n".join(summary_lines(report, out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
