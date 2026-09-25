"""Milestone 3.2's DAILY health check: data arrived, signals computed, no
errors, and risk-cap compliance (PLAN.md section 3.2). Wires the real
universe, prices, chosen portfolio, and risk limits into
`qrl.health.run_daily_health`, then writes a JSON report to `reports/`.

That report is PRIVATE, not merely "no positions/balances/weights": when a
risk cap is breached, `check_risk`'s detail embeds the offending ticker and
its exact position weight VERBATIM (see `qrl.health.HealthReport.to_dict`'s
docstring). That is intentional -- an on-call operator needs the real
weight -- but it means this file must stay under `reports/` (gitignored)
and must NEVER be wired into `scripts/build_site.py` or any other public
`site/` output (PLAN.md 3.4). See the comment at the write call below.

All check logic lives in `qrl.health`; this script does IO, wiring, and
formatting only.

Usage:
    python scripts/daily_check.py                          # real data, config/ as-shipped
    python scripts/daily_check.py --as-of 2026-09-24        # pretend "today" is this date
    python scripts/daily_check.py --max-staleness-bdays 2   # looser freshness tolerance
    python scripts/daily_check.py --out reports/health.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qrl.data import load_ohlcv, load_prices  # noqa: E402
from qrl.health import HealthReport, run_daily_health  # noqa: E402
from qrl.portfolio import combine_portfolio, load_portfolio_config  # noqa: E402
from qrl.profile import load_profile_with_hash  # noqa: E402
from qrl.risk import load_risk_limits  # noqa: E402
from qrl.strategies import REGISTRY, SLEEVE_REGISTRY  # noqa: E402
from qrl.universe import load_universe  # noqa: E402

_ALL_SPECS = {**REGISTRY, **SLEEVE_REGISTRY}


def _member_tickers(members: list[dict]) -> list[str]:
    return sorted({t for m in members for t in _ALL_SPECS[m["fn"]].tickers(m["params"])})


def _extra_fields(members: list[dict]) -> set[str]:
    """Fields beyond "close" (high/low/volume) any configured member's
    family declares needing."""
    return {f for m in members for f in _ALL_SPECS[m["fn"]].fields} - {"close"}


def _member_weights_fn(
    member: dict, extra_frames: dict[str, pd.DataFrame]
) -> Callable[[pd.DataFrame], pd.DataFrame]:
    """A close-only callable matching `run_daily_health`'s `build_weights`
    contract, closing over any non-close fields this member's family needs
    (fetched once up front, see `_extra_fields`)."""
    spec = _ALL_SPECS[member["fn"]]
    cols = spec.tickers(member["params"])
    weight_kwargs = {k: v for k, v in member["params"].items() if k != "tickers"}

    def _weights(close: pd.DataFrame) -> pd.DataFrame:
        frames = [close[cols] if f == "close" else extra_frames[f][cols] for f in spec.fields]
        return spec.weights(*frames, **weight_kwargs)

    return _weights


def _print_report(report: HealthReport) -> None:
    for check in report.checks:
        print(f"  [{check.status:>7}] {check.name}: {check.detail}")
    print(f"Overall: {'OK' if report.ok else 'FAIL'} (as of {report.as_of.date()})")


def _build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(ROOT / "reports" / "daily_health.json"))
    ap.add_argument("--as-of", default=None, help="ISO date to pretend is 'today' (testing).")
    ap.add_argument("--max-staleness-bdays", type=int, default=1)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    universe = load_universe()
    portfolio_cfg = load_portfolio_config(ROOT / "config" / "portfolio.yaml")
    profile, _ = load_profile_with_hash()
    limits = load_risk_limits(profile)

    core = portfolio_cfg["core"]
    sleeve_members = portfolio_cfg["sleeve"]["strategies"]
    all_members = [core, *sleeve_members]
    all_tickers = sorted(set(universe["tickers"]) | set(_member_tickers(all_members)))

    extra_fields = _extra_fields(all_members)
    extra_frames: dict[str, pd.DataFrame] = {}
    if extra_fields:
        ohlcv = load_ohlcv(_member_tickers(all_members))
        extra_frames = {f: ohlcv[f] for f in extra_fields}

    def load_close() -> pd.DataFrame:
        _, close = load_prices(all_tickers)
        return close

    build_weights = {"core": _member_weights_fn(core, extra_frames)}
    for i, member in enumerate(sleeve_members):
        build_weights[f"sleeve_{i}_{member['fn']}"] = _member_weights_fn(member, extra_frames)

    def combine(weights: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
        if "core" not in weights:
            raise RuntimeError("core weights unavailable; core strategy failed earlier.")
        core_weights = weights["core"]
        sleeve_weights = [w for key, w in weights.items() if key != "core"]
        pw = combine_portfolio(core_weights, sleeve_weights, profile["capital_split"])
        return pw.combined, pw.sleeve

    as_of = pd.Timestamp(args.as_of) if args.as_of else None
    report = run_daily_health(
        load_close=load_close,
        build_weights=build_weights,
        combine=combine,
        limits=limits,
        as_of=as_of,
        max_staleness_bdays=args.max_staleness_bdays,
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # PRIVATE ARTIFACT -- do not wire this into scripts/build_site.py or any
    # other public site/ output. report.to_dict()'s check details MAY embed
    # ticker symbols and exact position weights verbatim when a risk cap is
    # breached (see qrl.health.HealthReport.to_dict's docstring); this file
    # must stay under reports/ and gitignored (PLAN.md 3.4).
    out.write_text(json.dumps(report.to_dict(), indent=2, default=str))

    _print_report(report)
    print(f"Wrote {out}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
