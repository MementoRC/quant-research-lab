"""Core shortlist reveal: the owner's ONE look at the covid_2020 and
inflation_2022 stress windows for the cores in config/core_shortlist.yaml
(spec: docs/methodology/core-reveal.md). EXPLORATION
ONLY: it selects nothing and changes no config. The look is recorded in the
ledger BEFORE anything is computed; any existing core_reveal event refuses a
re-run unless --force is given with a non-empty --reason.

Usage:
    python scripts/core_reveal.py --confirm
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qrl.core_compare import load_core_candidates  # noqa: E402
from qrl.core_reveal import (  # noqa: E402
    load_core_shortlist,
    preflight,
    render_markdown,
    run_core_reveal,
)
from qrl.criteria import load_criteria  # noqa: E402
from qrl.data import load_ohlcv  # noqa: E402
from qrl.ledger import DEFAULT_LEDGER_PATH, Ledger  # noqa: E402
from qrl.periods import period_bounds  # noqa: E402
from qrl.profile import load_profile  # noqa: E402
from qrl.strategies import REGISTRY  # noqa: E402
from qrl.stress import EQUITY_PROXY, load_stress_config  # noqa: E402

KIND = "core_reveal"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--confirm", action="store_true", help="required: this spends the one look")
    ap.add_argument("--force", action="store_true", help="re-run after an earlier reveal")
    ap.add_argument("--reason", default="", help="required with --force")
    ap.add_argument("--ledger", default=str(ROOT / DEFAULT_LEDGER_PATH))
    ap.add_argument("--out-json", default=str(ROOT / "reports" / "core_reveal.json"))
    ap.add_argument("--out-md", default=str(ROOT / "research" / "core_reveal.md"))
    args = ap.parse_args(argv)

    if not args.confirm:
        print("refused: pass --confirm to spend the one look at the validation-window cells")
        return 2
    if args.force and not args.reason.strip():
        print("refused: --force needs a non-empty --reason")
        return 2

    criteria, _ = load_criteria(ROOT / "config" / "criteria.yaml")
    holdout_start, _ = period_bounds(criteria, "holdout")
    cfg, stress_hash = load_stress_config(ROOT / "config" / "stress.yaml", holdout_start)
    profile = load_profile(ROOT / "config" / "profile.yaml")
    cands, cand_hash = load_core_candidates(ROOT / "config" / "core_candidates.yaml")
    shortlist, shortlist_hash = load_core_shortlist(
        ROOT / "config" / "core_shortlist.yaml", cands, cand_hash, cfg, criteria
    )
    chosen = [c for c in cands if c.id in shortlist.ids]
    rend = max(w.end for w in cfg.windows if w.name in shortlist.windows)

    tickers = sorted({EQUITY_PROXY} | {t for c in chosen for t in REGISTRY[c.fn].tickers(c.params)})
    data = load_ohlcv(tickers, refresh=True)
    missing = [t for t in tickers if t not in data["close"].columns]
    if missing:
        print(f"no price data for: {missing}")
        return 1
    last_row = data["close"].loc[:rend, tickers].iloc[-1]
    if not last_row.notna().all():
        unpriced = sorted(last_row.index[last_row.isna()])
        print(f"unpriced at the last revealed window end {rend.date()}: {unpriced}")
        return 1

    try:  # anything that can fail without revealing a number fails BEFORE the lock
        preflight(shortlist, cands, cfg, data, profile["capital_split"])
    except ValueError as exc:
        print(f"preflight failed, the look is NOT spent: {exc}")
        return 1

    with Ledger(args.ledger) as ledger:
        prior = ledger.list_reveal_events(KIND)
        if prior and not args.force:
            last = prior[-1]
            print(
                f"refused: the one look is already spent (event {last['event_id']}, "
                f"{last['status']}, {last['created_at']}); --force with --reason to override"
            )
            return 1
        event_id = ledger.record_reveal_event(
            KIND,
            shortlist_hash,
            cand_hash,
            stress_hash,
            shortlist.ids,
            shortlist.windows,
            forced=bool(prior),
            reason=args.reason.strip() or None,
        )
        result = run_core_reveal(
            shortlist,
            cands,
            cfg,
            data,
            criteria,
            profile["capital_split"],
            profile["max_drawdown"],
        )
        report = {
            "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
            "event_id": event_id,
            "shortlist_sha256": shortlist_hash,
            "candidates_sha256": cand_hash,
            "stress_sha256": stress_hash,
            "trial_count": len(cands),
            "shortlist_size": len(shortlist.ids),
            "max_drawdown": profile["max_drawdown"],
            "capital_split": profile["capital_split"],
            "params": {"force": args.force, "reason": args.reason.strip()},
            **result,
        }
        out_json, out_md = Path(args.out_json), Path(args.out_md)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        markdown = render_markdown(report)
        out_json.write_text(json.dumps(report, indent=2, default=str))
        out_md.write_text(markdown)
        ledger.finish_reveal_event(event_id)
    print(markdown)
    print(f"Wrote {out_json} and {out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
