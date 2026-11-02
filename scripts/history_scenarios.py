"""History-grounded scenarios report (spec: docs/methodology/history-scenarios.md).
Shows, for the 12 portfolios of config/decision.yaml, what happened in every
15% S&P 500 fall since 1971 (fall, time to recover, real balance of a
CPI-indexed withdrawal), with stand-in data before the funds existed. Uses data
up to the research end (2018-12-31) only and writes research/history_scenarios.md.
It selects and recommends nothing and changes no config. IO and wiring only; all
logic lives in qrl.history, qrl.history_data, qrl.history_config and
qrl.history_report. Writes nothing if any check fails.

Usage:
    python scripts/history_scenarios.py
    python scripts/history_scenarios.py --config config/history.yaml --out-md research/history_scenarios.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qrl.criteria import load_criteria  # noqa: E402
from qrl.decision import data_end  # noqa: E402
from qrl.decision_config import load_decision_config  # noqa: E402
from qrl.decision_withdraw import CPI_SERIES  # noqa: E402
from qrl.history import run_history  # noqa: E402
from qrl.history_config import load_history_config  # noqa: E402
from qrl.history_data import load_raw  # noqa: E402
from qrl.history_report import render_markdown  # noqa: E402
from qrl.macro import load_macro  # noqa: E402
from qrl.periods import period_bounds  # noqa: E402
from qrl.stress import load_stress_config  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=str(ROOT / "config" / "history.yaml"))
    ap.add_argument("--decision-config", default=str(ROOT / "config" / "decision.yaml"))
    ap.add_argument("--out-md", default=str(ROOT / "research" / "history_scenarios.md"))
    ap.add_argument("--refresh", action="store_true", help="download every series again")
    args = ap.parse_args(argv)

    try:
        criteria, _ = load_criteria(ROOT / "config" / "criteria.yaml")
        holdout_start, _ = period_bounds(criteria, "holdout")
        stress_cfg, _ = load_stress_config(ROOT / "config" / "stress.yaml", holdout_start)
        end = data_end(criteria)
        dcfg = load_decision_config(
            args.decision_config, ROOT / "config" / "core_candidates.yaml", stress_cfg, end
        )
        hcfg = load_history_config(args.config)
        cache_dir = ROOT / hcfg.cache_dir
        raw = load_raw(hcfg, end, cache_dir, refresh=args.refresh)
        # the whole CPI history is fetched into the history cache; usable_cpi's
        # availability dating plus the cut at the end keep later values out
        cpi = load_macro(
            ids=[CPI_SERIES],
            refresh=args.refresh,
            cache_dir=cache_dir,
            config_path=ROOT / "config" / "macro.yaml",
        )[CPI_SERIES]
        report = run_history(hcfg, dcfg, raw, cpi, criteria)
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
