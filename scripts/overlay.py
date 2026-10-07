"""Macro overlay on core G (spec: docs/methodology/macro-overlay.md).

    research  the ONE trial vs static G plus the spell-shuffle null, 2005-2018.
    validate  2019-2022, only after a research pass. VALIDATION-SEEN; reported,
              not decisive.
    holdout   2023 to the latest data, only after a research pass, with
              --unseal-holdout-once and a --reason recording the owner's fresh
              go-ahead. Spends the holdout for every future idea.

Each step runs once, ever: it is a row of the ledger's overlay_events, recorded
`started` before anything is computed and `done` with its verdict (passes and
failures alike; an error is recorded as a failure). validate and holdout
refuse if config/overlay.yaml changed since research. IO and wiring only; the
logic lives in qrl.overlay, qrl.overlay_null and qrl.overlay_eval.

Usage:
    python scripts/overlay.py research
    python scripts/overlay.py validate
    python scripts/overlay.py holdout --unseal-holdout-once --reason "owner go-ahead <date>"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qrl.core_compare import load_core_candidates  # noqa: E402
from qrl.criteria import load_criteria  # noqa: E402
from qrl.data import load_prices  # noqa: E402
from qrl.holdout import unseal  # noqa: E402
from qrl.ledger import DEFAULT_LEDGER_PATH, OVERLAY_KINDS, Ledger  # noqa: E402
from qrl.macro import load_macro  # noqa: E402
from qrl.overlay import OverlayConfig, load_overlay_config  # noqa: E402
from qrl.overlay_eval import (  # noqa: E402
    holdout_returns,
    render_markdown,
    research_result,
    validation_result,
    window_result,
)

CACHE_DIR = ROOT / "data" / "cache"


def _refusal(ledger: Ledger, step: str, overlay_sha: str) -> str | None:
    prior = ledger.list_overlay_events(step)
    if prior:
        last = prior[-1]
        return (
            f"{step} already ran (event {last['event_id']}, {last['status']}, "
            f"{last['created_at']}); each step runs once"
        )
    if step == "research":
        return None
    research = ledger.list_overlay_events("research")
    if not research or research[0]["status"] != "done":
        return "research has not completed"
    if research[0]["overlay_sha256"] != overlay_sha:
        return "config/overlay.yaml changed since research; the pre-registered spec is void"
    if not research[0]["passed"]:
        return "research failed: the overlay track is closed (no retries, no tweaks)"
    unsealed = ledger.list_holdout_events()
    if step == "holdout" and unsealed:
        return (
            f"the holdout was already unsealed ({unsealed[0]['created_at']}, "
            f"{unsealed[0]['what_unsealed']!r})"
        )
    return None


def _load(cfg: OverlayConfig, refresh: bool) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    tickers = sorted(cfg.base)
    open_, close = load_prices(tickers, refresh=refresh, cache_dir=CACHE_DIR)
    missing = [t for t in tickers if t not in close.columns]
    if missing:  # the loader drops tickers it cannot fetch
        raise RuntimeError(f"no price data for: {missing}")
    cpi = load_macro(
        ids=[cfg.cpi_series],
        refresh=refresh,
        cache_dir=CACHE_DIR,
        config_path=ROOT / "config" / "macro.yaml",
    )[cfg.cpi_series]
    return open_[tickers], close[tickers], cpi


def _compute(
    step: str, ledger: Ledger, frames: tuple, cfg: OverlayConfig, criteria: dict, reason: str
) -> dict:
    open_, close, cpi = frames
    if step == "research":
        return research_result(open_, close, cpi, cfg, criteria)
    if step == "validate":
        return validation_result(open_, close, cpi, cfg, criteria)
    window = unseal(
        ledger,
        holdout_returns(open_, close, cpi, cfg),
        criteria,
        reason,
        what_unsealed=f"macro overlay on {cfg.base_id} vs static {cfg.base_id}",
        confirm=True,
    )
    return window_result(window, cfg)


def _write_report(ledger: Ledger, out_md: Path, header: dict) -> str:
    steps = {}
    for step in OVERLAY_KINDS:
        done = [e for e in ledger.list_overlay_events(step) if e["status"] == "done"]
        if done:
            steps[step] = done[0]
    markdown = render_markdown(steps, header)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(markdown, encoding="utf-8")
    return markdown


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("step", choices=list(OVERLAY_KINDS))
    ap.add_argument(
        "--unseal-holdout-once", action="store_true", help="holdout only: spends the holdout"
    )
    ap.add_argument("--reason", default="", help="holdout only: the owner's go-ahead")
    ap.add_argument("--config", default=str(ROOT / "config" / "overlay.yaml"))
    ap.add_argument("--ledger", default=str(ROOT / DEFAULT_LEDGER_PATH))
    ap.add_argument("--out-md", default=str(ROOT / "research" / "overlay.md"))
    args = ap.parse_args(argv)
    reason = args.reason.strip()

    if args.step == "holdout" and not (args.unseal_holdout_once and reason):
        print(
            "refused: holdout needs --unseal-holdout-once and a non-empty --reason (owner go-ahead)"
        )
        return 2
    try:
        criteria, criteria_hash = load_criteria(ROOT / "config" / "criteria.yaml")
        cands, cand_sha = load_core_candidates(ROOT / "config" / "core_candidates.yaml")
        cfg, overlay_sha = load_overlay_config(args.config, cands)
    except ValueError as exc:
        print(f"refused: {exc}")
        return 1

    with Ledger(args.ledger) as ledger:
        refusal = _refusal(ledger, args.step, overlay_sha)
        if refusal:
            print(f"refused: {refusal}")
            return 1
        try:  # a failed download spends nothing: the event is recorded after this
            frames = _load(cfg, refresh=args.step == "holdout")
        except (ValueError, RuntimeError) as exc:
            print(f"refused: {exc}")
            return 1
        event_id = ledger.record_overlay_event(args.step, overlay_sha, reason=reason or None)
        try:
            result = _compute(args.step, ledger, frames, cfg, criteria, reason)
        except (ValueError, RuntimeError) as exc:  # recorded as a failed step, never skipped
            ledger.finish_overlay_event(event_id, passed=False, result={"error": str(exc)})
            print(f"{args.step} errored; recorded as a failure (event {event_id}): {exc}")
            return 1
        ledger.finish_overlay_event(event_id, passed=result["passed"], result=result)
        header = {
            "overlay_sha256": overlay_sha,
            "candidates_sha256": cand_sha,
            "criteria_hash": criteria_hash,
        }
        markdown = _write_report(ledger, Path(args.out_md), header)
    print(markdown)
    print(f"Wrote {args.out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
