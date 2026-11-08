"""Evening IB PAPER rebalancer (spec: docs/methodology/broker-rebalancer.md).
IO and wiring only: every rule lives in qrl.broker_run, qrl.broker_gate,
qrl.rebalance and qrl.broker_journal. Journals and events go to
reports/broker/ (private, gitignored; never wire them into site/).

Usage (environment `broker`; cron example in the spec):
    pixi run -e broker rebalance                     # evening run, after the close
    pixi run -e broker rebalance --flatten           # kill switch
    pixi run -e broker rebalance --accept-positions  # accept IB's positions after a mismatch
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from contextlib import AbstractContextManager, ExitStack
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qrl.broker import Broker  # noqa: E402
from qrl.broker_config import BrokerConfig, broker_config_path, load_broker_config  # noqa: E402
from qrl.broker_journal import append_event, utc_iso  # noqa: E402
from qrl.broker_run import (  # noqa: E402
    RunContext,
    accept_positions_run,
    evening_run,
    flatten_run,
)
from qrl.data import load_ohlcv  # noqa: E402
from qrl.live_weights import (  # noqa: E402
    Market,
    build_market,
    extra_fields,
    make_combine,
    member_tickers,
    weight_fns,
)
from qrl.portfolio import load_portfolio_config  # noqa: E402
from qrl.profile import load_profile_with_hash  # noqa: E402
from qrl.risk import RiskLimits, load_risk_limits  # noqa: E402


def _market_loader(
    portfolio_cfg: dict, capital_split: dict[str, float], limits: RiskLimits
) -> Callable[[date], Market]:
    core = portfolio_cfg["core"]
    sleeve = portfolio_cfg["sleeve"]["strategies"]
    members = [core, *sleeve]

    def load(today: date) -> Market:
        # refresh=True: the cache never refreshes itself, and the run needs today's bar.
        ohlcv = load_ohlcv(member_tickers(members), refresh=True)
        extra = {f: ohlcv[f] for f in extra_fields(members)}
        return build_market(
            close=ohlcv["close"],
            fns=weight_fns(core, sleeve, extra),
            combine=make_combine(capital_split),
            limits=limits,
            as_of=pd.Timestamp(today),
        )

    return load


def _open_broker(cfg: BrokerConfig) -> AbstractContextManager[Broker]:
    """The IB adapter, a context manager: one connected gateway for the whole run."""
    try:
        from qrl.broker_ib import IbBroker
    except ImportError as exc:
        raise SystemExit(
            f"IB adapter unavailable ({exc}); run `pixi run -e broker rebalance`."
        ) from exc
    return IbBroker(cfg)


def _stop_run(root: Path, status: str, detail: str) -> int:
    """End a run before it reaches `qrl.broker_run`: one events line, one printed
    line, exit 1, instead of a traceback."""
    append_event(
        root, {"recorded_at": utc_iso(datetime.now(UTC)), "status": status, "detail": detail}
    )
    print(f"{status}: {detail}")
    return 1


def _connect_failed(cfg: BrokerConfig, exc: Exception, root: Path) -> int:
    """Connecting to the gateway failed (refused, timeout, auth)."""
    return _stop_run(
        root, "error", f"could not connect to IB gateway at {cfg.host}:{cfg.port}: {exc!r}"
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--flatten", action="store_true", help="kill switch: cancel all, sell longs")
    mode.add_argument(
        "--accept-positions", action="store_true", help="accept IB's positions; trades nothing"
    )
    ap.add_argument("--journal-dir", default=str(ROOT / "reports" / "broker"))
    return ap


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    root = Path(args.journal_dir)
    try:
        cfg = load_broker_config(broker_config_path(ROOT))
        profile, _ = load_profile_with_hash(ROOT / "config" / "profile.yaml")
        limits = load_risk_limits(profile)
        portfolio_cfg = load_portfolio_config(ROOT / "config" / "portfolio.yaml")
    except Exception as exc:
        return _stop_run(root, "error", f"could not load the configuration: {exc!r}")
    if args.flatten:
        run = flatten_run
    elif args.accept_positions:
        run = accept_positions_run
    else:
        run = evening_run
        if not cfg.enabled:  # the Gate's own refusal, before any connection is opened
            return _stop_run(root, "refused", "disabled: `enabled` is false in the broker config")
    try:
        manager = _open_broker(cfg)
    except ValueError as exc:  # the adapter's paper-only refusal of a hand-built config
        return _stop_run(root, "refused", str(exc))
    with ExitStack() as stack:
        try:
            broker = stack.enter_context(manager)
        except Exception as exc:
            return _connect_failed(cfg, exc, root)
        result = run(
            RunContext(
                cfg=cfg,
                broker=broker,
                load_market=_market_loader(portfolio_cfg, profile["capital_split"], limits),
                limits=limits,
                root=root,
                now=lambda: datetime.now(UTC),
            )
        )
    print(f"{result.status}: {result.detail}")
    if result.path is not None:
        print(f"Wrote {result.path}")
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
