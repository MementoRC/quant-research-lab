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
    python scripts/international.py run --set main --designated \\
        --reason "owner go-ahead <date>" --confirm   # unvalidated subject, labelled
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
    NotCovered,
    Rule,
    build_panel,
    data_end_before,
    derive_equity_leg,
    evaluate_market,
    freeze,
    gold_correlation,
    holds_gold,
    load_international_config,
    render_report,
    set_verdict,
    translate,
)
from qrl.ledger import DEFAULT_LEDGER_PATH, Ledger, LedgerError  # noqa: E402
from qrl.macro import fetch_series  # noqa: E402

CACHE_DIR = ROOT / "data" / "cache"
PIN_NAME = "international"
DESIGNATED_STATUS = "designated_unvalidated"
DESIGNATED_NOTE = (
    "subject not validated (owner-designated; failed fixed standalone attempt, test {test_id})"
)


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
    subject = p_run.add_mutually_exclusive_group(required=True)
    subject.add_argument("--test-id", type=int)
    subject.add_argument(
        "--designated",
        action="store_true",
        help="the owner-designated, unvalidated core from config's designated_core "
        "(spec amendment 2026-10-22)",
    )
    p_run.add_argument("--reason", default="", help="the owner's go-ahead and acceptance evidence")
    p_run.add_argument("--confirm", action="store_true")
    return ap


def write_snapshot(path: Path, open_: pd.DataFrame, close: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    both = pd.concat({"open": open_, "close": close}, axis=1)
    both.columns = [f"{field}|{ticker}" for field, ticker in both.columns]
    both.to_parquet(path)


def read_snapshot(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    both = pd.read_parquet(path)

    def part(field: str) -> pd.DataFrame:
        cols = [c for c in both.columns if c.startswith(f"{field}|")]
        return both[cols].rename(columns=lambda c: c.split("|", 1)[1])

    return part("open"), part("close")


def _rule_refusal(
    ledger: Ledger, args: argparse.Namespace, cfg: InternationalConfig, cfg_sha: str
) -> tuple[str | None, Rule | None, str | None]:
    """(refusal, rule, derived equity leg); the refusal is None when the run may go on."""
    pinned = ledger.config_pin(PIN_NAME)
    if pinned is not None and pinned["sha256"] != cfg_sha:
        return (
            "config/international.yaml differs from the pinned hash; the spec is void",
            None,
            None,
        )
    test = ledger.get_test(args.test_id)
    if test is None:
        return f"no ledger test {args.test_id}", None, None
    if not ledger.is_validated(args.test_id):
        return f"ledger test {args.test_id} has no validation event", None, None
    if ledger.validation_passed(args.test_id) is not True:  # False, or None on a legacy row
        return f"ledger test {args.test_id} did not pass validation (passed is not 1)", None, None
    rule = Rule(test["family"], test["params"])
    try:
        leg = derive_equity_leg(rule, cfg)
        translate(rule, leg, cfg.market_set(args.set).markets[0])
    except NotCovered as exc:
        return str(exc), None, None
    return None, rule, leg


def _designated_refusal(
    ledger: Ledger, args: argparse.Namespace, cfg: InternationalConfig, cfg_sha: str
) -> tuple[str | None, Rule | None, str | None]:
    """Like `_rule_refusal`, for `--designated`: the rule comes only from the
    config's designated_core, whose referenced attempt must be a recorded,
    identical, failed test."""
    pinned = ledger.config_pin(PIN_NAME)
    if pinned is not None and pinned["sha256"] != cfg_sha:
        return (
            "config/international.yaml differs from the pinned hash; the spec is void",
            None,
            None,
        )
    designated = cfg.designated_core
    if designated is None:
        return "config/international.yaml has no designated_core", None, None
    test_id = designated.failed_attempt_test_id
    test = ledger.get_test(test_id)
    if test is None:
        return f"no ledger test {test_id} (designated_core.failed_attempt_test_id)", None, None
    if (test["family"], test["params"]) != (designated.family, designated.params):
        return f"ledger test {test_id} is not the designated core's family and params", None, None
    if test["passed"]:
        return f"ledger test {test_id} passed; a passed rule must go through --test-id", None, None
    rule = Rule(designated.family, designated.params)
    try:
        leg = derive_equity_leg(rule, cfg)
        translate(rule, leg, cfg.market_set(args.set).markets[0])
    except NotCovered as exc:
        return str(exc), None, None
    return None, rule, leg


def _rule_id(args: argparse.Namespace, cfg: InternationalConfig) -> str:
    """The ledger's rule_id; a designated subject carries its label here."""
    note = _subject_note(args, cfg)
    return f"ledger test {args.test_id}" if note is None else f"designated core: {note}"


def _subject_note(args: argparse.Namespace, cfg: InternationalConfig) -> str | None:
    if args.designated and cfg.designated_core is not None:
        return DESIGNATED_NOTE.format(test_id=cfg.designated_core.failed_attempt_test_id)
    return None


def _pin_on_first_run(ledger: Ledger, cfg_sha: str) -> None:
    """The first confirmed run pins international.yaml's sha256 (never overwritten)."""
    if ledger.config_pin(PIN_NAME) is None:
        ledger.pin_config(PIN_NAME, cfg_sha, source="scripts/international.py run")


def _order_refusal(events: dict[str, dict], set_name: str, order: list[str]) -> str | None:
    unused = [s for s in order[: order.index(set_name)] if s not in events]
    return f"sets run in order: {unused[0]!r} is unused" if unused else None


def _start(
    ledger: Ledger,
    args: argparse.Namespace,
    cfg: InternationalConfig,
    cfg_sha: str,
    rule: Rule,
    events: dict[str, dict],
    snapshot: Path,
) -> tuple[int, pd.DataFrame, pd.DataFrame, pd.Timestamp, str] | str:
    """Download, freeze and snapshot the data, then record the event. Returns
    (event_id, open, close, data_end, data_sha) or a refusal message. Nothing
    is scored before the event row exists."""
    refusal = _order_refusal(events, args.set, cfg.set_names)
    if refusal:
        return refusal
    try:
        fund_open, fund_close, gold, yields = load_raw(cfg, args.set, True, Path(args.cache_dir))
        open_, close = build_panel(fund_open, fund_close, yields, gold, cfg)
        data_end = data_end_before(close, cfg.market_set(args.set).markets, pd.Timestamp.now())
    except (RuntimeError, ValueError, KeyError) as exc:
        return str(exc)
    open_, close, data_sha = freeze(open_, close, data_end)
    write_snapshot(snapshot, open_, close)
    try:
        _pin_on_first_run(ledger, cfg_sha)
        event_id = ledger.record_international_event(
            set_name=args.set,
            set_order=cfg.set_names,
            rule_id=_rule_id(args, cfg),
            rule_sha256=rule.sha256,
            config_sha256=cfg_sha,
            data_end=str(data_end.date()),
            data_sha256=data_sha,
            reason=args.reason.strip(),
        )
    except LedgerError as exc:
        return str(exc)
    return event_id, open_, close, data_end, data_sha


def _resume(
    event: dict, args: argparse.Namespace, cfg_sha: str, rule: Rule, snapshot: Path
) -> tuple[int, pd.DataFrame, pd.DataFrame, pd.Timestamp, str] | str:
    """Recompute after a crash: the same rule, config and frozen data only."""
    if event["status"] == "completed":
        return (
            f"set {args.set!r} already ran (event {event['event_id']}, "
            f"{event['created_at']}); each set runs once"
        )
    if (event["rule_sha256"], event["config_sha256"]) != (rule.sha256, cfg_sha):
        return "a rerun after a crash must use the same rule and config"
    if not snapshot.exists():
        return f"the frozen data snapshot {snapshot} is missing"
    data_end = pd.Timestamp(event["data_end"])
    open_, close, data_sha = freeze(*read_snapshot(snapshot), data_end)
    if data_sha != event["data_sha256"]:
        return "the frozen data changed; a rerun must use identical data"
    return event["event_id"], open_, close, data_end, data_sha


def _score_and_record(
    ledger: Ledger,
    args: argparse.Namespace,
    cfg: InternationalConfig,
    cfg_sha: str,
    rule: Rule,
    equity_leg: str,
    frozen: tuple[int, pd.DataFrame, pd.DataFrame, pd.Timestamp, str],
) -> str:
    """Score, write the report and complete the event; returns the markdown.
    From here the set is spent. A crash leaves the event 'started'; only a
    recompute with the same rule, config and data can finish it.
    `evaluate_market` does not catch engine or strategy errors (only thin data
    is a not-passed, with a `reason`), so a code bug raises here and leaves the
    event 'started' rather than completing it as a fail."""
    event_id, open_, close, data_end, data_sha = frozen
    market_set = cfg.market_set(args.set)
    corr = None
    late_only = False
    if holds_gold(rule, cfg):
        start, end = cfg.gold_check
        corr = gold_correlation(close[cfg.gold_ticker], close[cfg.gold_fund], start, end)
        late_only = corr is None or corr < cfg.gold_min_correlation
    markets = [
        evaluate_market(
            open_,
            close,
            translate(rule, equity_leg, market),
            market,
            cfg,
            data_end,
            late_only=late_only,
        )
        for market in market_set.markets
    ]
    verdict = set_verdict(markets, market_set)
    header = {
        "set": args.set,
        "event_id": event_id,
        "rule_id": _rule_id(args, cfg),
        "subject_note": _subject_note(args, cfg),
        "family": rule.family,
        "params": rule.params,
        "equity_leg": equity_leg,  # derived from the rule
        "config_sha256": cfg_sha,
        "rule_sha256": rule.sha256,
        "data_sha256": data_sha,
        "data_end": str(data_end.date()),
        "late_only": late_only,
        "gold_correlation": corr,
    }
    markdown = render_report(header, verdict, markets)
    out = Path(args.out_dir) / f"international_{args.set}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    result = {
        "verdict": verdict,
        "markets": markets,
        "late_only": late_only,
        "gold_correlation": corr,
    }
    note = _subject_note(args, cfg)
    if note is not None:
        result |= {"subject_status": DESIGNATED_STATUS, "subject_note": note}
    ledger.complete_international_event(event_id, result, str(out))
    return f"{markdown}\nWrote {out}"


def run(args: argparse.Namespace, cfg: InternationalConfig, cfg_sha: str) -> int:
    reason = args.reason.strip()
    if not (args.confirm and reason):
        print("refused: run needs --confirm and a non-empty --reason (the owner's go-ahead)")
        return 2
    try:
        cfg.market_set(args.set)
    except ValueError as exc:
        print(f"refused: {exc}")
        return 1
    snapshot = Path(args.cache_dir) / "international" / f"{args.set}_frozen.parquet"
    with Ledger(args.ledger) as ledger:
        check = _designated_refusal if args.designated else _rule_refusal
        refusal, rule, equity_leg = check(ledger, args, cfg, cfg_sha)
        if refusal is not None or rule is None or equity_leg is None:
            print(f"refused: {refusal}")
            return 1
        events = {e["set_name"]: e for e in ledger.list_international_events()}
        event = events.get(args.set)
        if event is None:
            frozen = _start(ledger, args, cfg, cfg_sha, rule, events, snapshot)
        else:
            frozen = _resume(event, args, cfg_sha, rule, snapshot)
        if isinstance(frozen, str):
            print(f"refused: {frozen}")
            return 1
        output = _score_and_record(ledger, args, cfg, cfg_sha, rule, equity_leg, frozen)
    print(output)
    return 0


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
