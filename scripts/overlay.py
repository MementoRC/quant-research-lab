"""Macro overlay on core G (spec: docs/methodology/macro-overlay.md).

    research  the ONE trial vs static G plus the spell-shuffle null, 2005-2018.
    validate  2019-2022, only after a research pass. VALIDATION-SEEN; reported,
              not decisive.
    holdout   2023 to the latest data, only after a research pass, with
              --unseal-holdout-once and a --reason recording the owner's fresh
              go-ahead. Spends the holdout for every future idea.

Each step produces a result once, ever: it is a row of the ledger's overlay_events, recorded
`started` before anything is computed and `done` with its verdict (passes and
failures alike). An unexpected crash is recorded with status `error` (message in
the error column, no result) and does not block a rerun; only a step that
produced a pass/fail result blocks a rerun. validate and holdout refuse if
config/overlay.yaml changed since research. IO and wiring only; the logic lives
in qrl.overlay, qrl.overlay_null and qrl.overlay_eval.

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
from qrl.periods import period_bounds  # noqa: E402

CACHE_DIR = ROOT / "data" / "cache"


def _refusal(ledger: Ledger, step: str, overlay_sha: str) -> str | None:
    # A step that produced a result (or is still running) blocks a rerun. A crash
    # with no result ('error') does not, so the single trial is never lost to a
    # crash; every attempt stays in the ledger. The holdout is always strict.
    prior = [
        e for e in ledger.list_overlay_events(step) if step == "holdout" or e["status"] != "error"
    ]
    if prior:
        last = prior[-1]
        return (
            f"{step} already ran (event {last['event_id']}, {last['status']}, "
            f"{last['created_at']}); each step runs once"
        )
    if step == "research":
        return None
    research = [e for e in ledger.list_overlay_events("research") if e["status"] == "done"]
    if not research:
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


def _coverage_problem(step: str, close: pd.DataFrame, criteria: dict) -> str | None:
    """The evaluated window must start within 7 calendar days of the period
    start and end within 7 days of its end (stale cached data would silently
    shorten it). The holdout runs to the latest data and is not checked."""
    if step == "holdout":
        return None
    start, end = period_bounds(criteria, "research" if step == "research" else "validation")
    if start is None or end is None:
        return f"{step} period bounds are not set in criteria.yaml"
    slack = pd.Timedelta(days=7)
    data = close.dropna()
    if data.empty or data.index[0] > start + slack:
        return f"price data starts too late for {step}: need all assets by {start.date()}"
    if data.index[-1] < end - slack:
        return f"price data ends too early for {step}: need data to {end.date()}"
    return None


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
        problem = _coverage_problem(args.step, frames[1], criteria)
        if problem:  # nothing is spent: refused before the event is recorded
            print(f"refused: {problem}")
            return 1
        event_id = ledger.record_overlay_event(args.step, overlay_sha, reason=reason or None)
        try:
            result = _compute(args.step, ledger, frames, cfg, criteria, reason)
        except (ValueError, RuntimeError) as exc:  # recorded as a failed step, never skipped
            ledger.finish_overlay_event(event_id, passed=False, result={"error": str(exc)})
            print(f"{args.step} errored; recorded as a failure (event {event_id}): {exc}")
            return 1
        except Exception as exc:  # a crash with no result: recorded, does not block a rerun
            ledger.fail_overlay_event(event_id, f"{type(exc).__name__}: {exc}")
            print(f"{args.step} crashed; recorded as error (event {event_id}): {exc}")
            raise
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
