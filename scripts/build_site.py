"""Run all configured strategies and benchmarks, then write site/data/results.json.

Usage:
    python scripts/build_site.py              # real data from Yahoo (cached)
    python scripts/build_site.py --refresh    # re-download prices
    python scripts/build_site.py --synthetic  # offline random-walk demo data
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qrl.combined import build_core_weights  # noqa: E402
from qrl.criteria import evaluate, load_criteria  # noqa: E402
from qrl.data import load_ohlcv, load_prices, synthetic_ohlcv, synthetic_prices  # noqa: E402
from qrl.engine import run_backtest  # noqa: E402
from qrl.metrics import compute_metrics, drawdown  # noqa: E402
from qrl.periods import PERIOD_NAMES, period_bounds, slice_period  # noqa: E402
from qrl.pit_universe import load_pit_universe  # noqa: E402
from qrl.portfolio import combine_portfolio, load_portfolio_config  # noqa: E402
from qrl.site_core import (  # noqa: E402
    build_core_comparison,
    build_decision,
    build_fragility,
    build_longrun,
    build_rsp_sleeve,
    build_staged_entry,
    build_withdrawal_rules,
)
from qrl.strategies import REGISTRY, SLEEVE_REGISTRY  # noqa: E402
from qrl.universe import load_universe  # noqa: E402

_ALL_SPECS = {**REGISTRY, **SLEEVE_REGISTRY}

# The research funnel panel's canonical stage order (milestone 2.7). Today's
# scripts/export_ledger.py only writes "tested" / "passed_research" /
# "validated" (milestone 2.3's summary shape); "passed_robustness" and
# "selected" are read if a future export adds them, and shown as "unknown"
# otherwise -- see `_research_funnel`.
_FUNNEL_STAGES = (
    ("tested", "Tested"),
    ("passed_research", "Passed research"),
    ("passed_validation", "Evaluated on validation"),
    ("passed_robustness", "Passed robustness"),
    ("selected", "Selected"),
)


def _round(x, nd=6):
    return None if x is None or pd.isna(x) else round(float(x), nd)


def _universe_flags(root: Path) -> dict[str, bool]:
    """Map each configured universe name to its `survivorship_biased` flag.
    A config that exists but fails to load counts as biased (fail closed)."""
    sources = (
        (root / "config" / "universe.yaml", load_universe),
        (root / "config" / "universe_pit.yaml", lambda p: load_pit_universe(p)[0]),
    )
    flags: dict[str, bool] = {}
    for path, loader in sources:
        if not path.exists():
            continue
        name = (yaml.safe_load(path.read_text()) or {}).get("name")
        if not name:
            continue
        try:
            flags[name] = bool(loader(path)["survivorship_biased"])
        except Exception:
            flags[name] = True
    return flags


def _ledger_universes(ledger_path: Path) -> list[dict] | None:
    """Each distinct `tests.universe` in the ledger with its test count, or
    None if the ledger is missing or unreadable. Read-only: never creates or
    migrates the ledger."""
    if not ledger_path.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{ledger_path}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                "SELECT universe, COUNT(*) FROM tests GROUP BY universe ORDER BY universe"
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    return [{"name": name, "tests": n} for name, n in rows]


def _research_survivorship(universes: list[dict] | None, root: Path) -> dict:
    """Whether the research record behind the funnel is survivorship-biased,
    from the universes the ledger says were tested (see `_ledger_universes`),
    not from a file CI never builds. Fails closed: a universe with no config
    or a config that fails to load counts as biased, and so does a missing or
    unreadable ledger (`universes` is None)."""
    if universes is None:
        return {"biased": True, "universes": []}
    flags = _universe_flags(root)
    shown = [
        {
            "name": u["name"],
            "tests": u["tests"],
            "survivorship_biased": flags.get(u["name"], True),
        }
        for u in universes
    ]
    return {"biased": any(u["survivorship_biased"] for u in shown), "universes": shown}


def _search_origin_biased(provenance: dict, survivorship: dict | None) -> bool:
    """A search-origin portfolio entry is biased unless its provenance names a
    ledger run and every tested universe is configured unbiased."""
    if provenance.get("ledger_run_id") is None or survivorship is None:
        return True
    return survivorship["biased"]


def _visible_end(r: dict, criteria: dict, common_end: pd.Timestamp) -> pd.Timestamp:
    """Last date an entry's figures may show: the whole common window when the
    entry has holdout clearance, otherwise the end of the validation period."""
    if r["allow_holdout"]:
        return common_end
    return min(common_end, period_bounds(criteria, "validation")[1])


def _holdout_event_count(ledger_path: Path) -> int | None:
    """Rows in the ledger's `holdout_events`, or None if there is no ledger
    file. Read-only: never creates or migrates the ledger."""
    if not ledger_path.exists():
        return None
    conn = sqlite3.connect(f"file:{ledger_path}?mode=ro", uri=True)
    try:
        return conn.execute("SELECT COUNT(*) FROM holdout_events").fetchone()[0]
    except sqlite3.OperationalError:
        return 0
    finally:
        conn.close()


def _check_holdout_clearance(provenance: dict, ledger_path: Path) -> None:
    """`holdout_unsealed: true` in the portfolio config only grants holdout
    figures if the ledger recorded an unsealing. Raises on a mismatch rather
    than publishing. Runs only when the ledger file exists (it is tracked in
    git, so real builds have it)."""
    if not provenance.get("holdout_unsealed"):
        return
    if _holdout_event_count(ledger_path) == 0:
        raise RuntimeError(
            "config/portfolio.yaml says holdout_unsealed: true, but the ledger "
            f"({ledger_path}) has no holdout_events row. Run qrl.holdout.unseal or "
            "set holdout_unsealed back to false; refusing to publish holdout figures."
        )


def _research_funnel(data_dir: Path, root: Path | None = None) -> dict:
    """Read `research.json` (milestone 2.3's ledger export, normally
    alongside `results.json` in `site/data/`) if present, and shape its
    funnel counts + total attempt count for the dashboard. Never runs a
    search itself -- Actions must never do that. With `root`, also adds the
    research record's survivorship label (`_research_survivorship`)."""
    path = data_dir / "research.json"
    if not path.exists():
        return {"available": False, "total_attempts": None, "stages": []}

    data = json.loads(path.read_text())
    funnel = data.get("funnel", {})
    # export_ledger.py's current key for "evaluated on the validation
    # period" is "validated"; accept it as this panel's "passed_validation"
    # stage so today's real research.json renders without every stage.
    passed_validation = funnel.get("passed_validation", funnel.get("validated"))
    counts = {**funnel, "passed_validation": passed_validation}
    stages = [
        {"key": key, "label": label, "count": counts.get(key)} for key, label in _FUNNEL_STAGES
    ]
    funnel_payload = {
        "available": True,
        "total_attempts": data.get("total_attempts"),
        "stages": stages,
    }
    if root is not None:
        ledger_path = root / "research" / "ledger.sqlite"
        funnel_payload["survivorship"] = _research_survivorship(
            _ledger_universes(ledger_path), root
        )
    return funnel_payload


def _sleeve_extra_fields(sleeve_members: list[dict]) -> set[str]:
    """Every field a sleeve family's `StrategySpec.fields` declares needing,
    beyond `close` (already loaded for every run): `low_range_close` needs
    high/low, `quiet_pullback` (quiet_by="volume") needs volume."""
    fields: set[str] = set()
    for member in sleeve_members:
        fields |= set(_ALL_SPECS[member["fn"]].fields)
    return fields - {"close"}


def _sleeve_only_tickers(sleeve_members: list[dict]) -> list[str]:
    return sorted({t for m in sleeve_members for t in _ALL_SPECS[m["fn"]].tickers(m["params"])})


def _sleeve_member_weights(member: dict, field_frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    spec = _ALL_SPECS[member["fn"]]
    cols = spec.tickers(member["params"])
    weight_kwargs = {k: v for k, v in member["params"].items() if k != "tickers"}
    frames = [field_frames[f][cols] for f in spec.fields]
    return spec.weights(*frames, **weight_kwargs)


def _portfolio_tickers(portfolio_cfg: dict) -> set[str]:
    members = [portfolio_cfg["core"], *portfolio_cfg["sleeve"]["strategies"]]
    return {t for m in members for t in _ALL_SPECS[m["fn"]].tickers(m["params"])}


def _portfolio_entries(
    portfolio_cfg: dict,
    capital_split: dict,
    open_: pd.DataFrame,
    close: pd.DataFrame,
    cost_bps: float,
    *,
    synthetic: bool,
    refresh: bool,
) -> tuple[list[dict], dict, list[dict], float]:
    """Build the core-alone and core+sleeve backtests for the dashboard.

    "Core alone" is the core strategy at FULL capital -- what running with
    no sleeve at all would look like -- never the core's scaled SHARE of
    the split (that share only makes sense as part of the combined
    portfolio). This is what lets the dashboard show what the sleeve adds
    (milestone 2.7): comparing core alone against core+sleeve.

    A non-empty sleeve's extra price fields (high/low/volume, beyond the
    `close` every run already loads) are fetched via `qrl.data.load_ohlcv`
    for the sleeve's own tickers only, and ONLY when a configured member
    actually needs them -- Actions must never fetch more than the chosen
    portfolio requires, and an empty sleeve fetches nothing extra at all.

    Returns `(descriptors, results_extra, sleeve_holdings, idle_cash_pct)`:
    `descriptors` are lightweight run dicts (mirroring `runs` below, with
    an `allow_holdout` flag gating each entry by kind -- research rules),
    `results_extra` maps their ids to `BacktestResult`,
    `sleeve_holdings` is the current sleeve's next-open target weights
    (empty if no sleeve is selected), and `idle_cash_pct` is the fraction
    of capital sitting in cash in the combined line because no sleeve is
    selected (0.0 once a sleeve is chosen).
    """
    core = portfolio_cfg["core"]
    core_tickers, core_weights = build_core_weights(core, close)

    sleeve_members = portfolio_cfg["sleeve"]["strategies"]
    field_frames: dict[str, pd.DataFrame] = {"close": close}
    if sleeve_members:
        extra_fields = _sleeve_extra_fields(sleeve_members)
        if extra_fields:
            sleeve_tickers = _sleeve_only_tickers(sleeve_members)
            ohlcv = (
                synthetic_ohlcv(sleeve_tickers)
                if synthetic
                else load_ohlcv(sleeve_tickers, refresh=refresh)
            )
            field_frames.update({f: ohlcv[f] for f in extra_fields})

    sleeve_frames = [_sleeve_member_weights(m, field_frames) for m in sleeve_members]

    pw = combine_portfolio(core_weights, sleeve_frames, capital_split)

    core_alone = run_backtest(
        open_[core_tickers], close[core_tickers], core_weights, cost_bps=cost_bps
    )
    combined_cols = pw.combined.columns
    combined = run_backtest(
        open_[combined_cols], close[combined_cols], pw.combined, cost_bps=cost_bps
    )

    holdout_unsealed = bool(portfolio_cfg["provenance"].get("holdout_unsealed"))
    core_is_baseline = core["origin"] == "baseline"
    core_allow_holdout = core_is_baseline or holdout_unsealed
    combined_allow_holdout = (core_is_baseline and not sleeve_members) or holdout_unsealed

    idle_cash_pct = 0.0 if sleeve_members else capital_split["sleeve"]
    combined_name = (
        "Core + sleeve (actual portfolio)"
        if sleeve_members
        else (
            f"Core + sleeve ({idle_cash_pct:.0%} idle cash, no sleeve selected yet "
            "-- trails core alone)"
        )
    )

    results_extra = {"portfolio_core": core_alone, "portfolio_combined": combined}
    descriptors = [
        {
            "id": "portfolio_core",
            "name": "Core alone (100% of capital, no sleeve)",
            "kind": "portfolio_core",
            "fn": core["fn"],
            "params": core["params"],
            "allow_holdout": core_allow_holdout,
            "search_origin": not core_is_baseline,
        },
        {
            "id": "portfolio_combined",
            "name": combined_name,
            "kind": "portfolio_combined",
            "fn": "portfolio",
            "params": {},
            "allow_holdout": combined_allow_holdout,
            "search_origin": not core_is_baseline or bool(sleeve_members),
        },
    ]

    holdings: list[dict] = []
    if sleeve_members:
        last = pw.sleeve.iloc[-1]
        holdings = [{"ticker": t, "target_weight": _round(v, 4)} for t, v in last.items() if v > 0]

    return descriptors, results_extra, holdings, idle_cash_pct


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "site" / "data" / "results.json"))
    args = ap.parse_args()

    criteria, criteria_hash = load_criteria(ROOT / "config" / "criteria.yaml")
    configs = yaml.safe_load((ROOT / "config" / "strategies.yaml").read_text())["strategies"]
    cost_bps = criteria["costs"]["bps_per_unit_turnover"]
    profile = yaml.safe_load((ROOT / "config" / "profile.yaml").read_text())
    capital_split = profile["capital_split"]
    portfolio_cfg = load_portfolio_config(ROOT / "config" / "portfolio.yaml")

    # Fixed baselines (config/strategies.yaml, benchmarks) are never searched
    # or tuned, so showing their holdout does not leak anything -- they keep
    # today's behaviour. Anything from the search/selection process gets its
    # own allow_holdout below (see `_portfolio_entries`); research rules
    # ("The holdout was contaminated").
    runs = [dict(c, kind="strategy", allow_holdout=True) for c in configs]
    for b in criteria["benchmarks"]:
        runs.append(
            {
                "id": f"bh_{b.lower()}",
                "name": f"{b} buy and hold",
                "fn": "buy_and_hold",
                "params": {"ticker": b},
                "kind": "benchmark",
                "allow_holdout": True,
            }
        )

    tickers = sorted(
        {t for r in runs for t in REGISTRY[r["fn"]].tickers(r["params"])}
        | _portfolio_tickers(portfolio_cfg)
    )
    if args.synthetic:
        open_, close = synthetic_prices(tickers)
    else:
        open_, close = load_prices(tickers, refresh=args.refresh)

    results = {}
    for r in runs:
        spec = REGISTRY[r["fn"]]
        cols = spec.tickers(r["params"])
        target = spec.weights(close[cols], **r["params"])
        results[r["id"]] = run_backtest(open_[cols], close[cols], target, cost_bps=cost_bps)

    _check_holdout_clearance(portfolio_cfg["provenance"], ROOT / "research" / "ledger.sqlite")
    portfolio_descriptors, portfolio_results, sleeve_holdings, idle_cash_pct = _portfolio_entries(
        portfolio_cfg,
        capital_split,
        open_,
        close,
        cost_bps,
        synthetic=args.synthetic,
        refresh=args.refresh,
    )
    runs.extend(portfolio_descriptors)
    results.update(portfolio_results)

    # Compare everything over the same window.
    common_start = max(res.returns.index[0] for res in results.values())
    common_end = min(res.returns.index[-1] for res in results.values())

    def window(res):
        return (
            res.returns.loc[common_start:common_end],
            res.turnover.loc[common_start:common_end],
            res.executed.loc[common_start:common_end],
        )

    data_dir = Path(args.out).parent
    research_funnel = _research_funnel(data_dir, ROOT)

    period_metrics = {}
    for r in runs:
        ret, turn, ex = window(results[r["id"]])
        # "Full" stops at the validation end for an entry without holdout
        # clearance, so its 2023+ performance is never published.
        visible_end = _visible_end(r, criteria, common_end)
        pm = {
            "full": compute_metrics(
                ret.loc[:visible_end], turn.loc[:visible_end], ex.loc[:visible_end]
            )
        }
        if not r["allow_holdout"]:
            pm["full"]["through"] = visible_end.strftime("%Y-%m-%d")
        names = PERIOD_NAMES if r["allow_holdout"] else ("research", "validation")
        for name in names:
            # Only reached with "holdout" in `names` when r["allow_holdout"] is
            # true: fixed baselines and benchmarks were never searched or tuned
            # (see `runs` above), so they may show holdout without
            # qrl.holdout.unseal. Searched entries get it only via the
            # ledger-checked holdout_unsealed provenance.
            sliced = slice_period(ret, criteria, name, unseal_holdout=True)
            if len(sliced) > 20:
                pm[name] = compute_metrics(sliced, turn, ex)
        period_metrics[r["id"]] = pm

    search_biased = _search_origin_biased(
        portfolio_cfg["provenance"], research_funnel.get("survivorship")
    )
    bench_id = f"bh_{criteria['pass']['beat_benchmark'].lower()}"
    out_strats = []
    for r in runs:
        res = results[r["id"]]
        pm = period_metrics[r["id"]]
        checks = {}
        if r["kind"] == "strategy":
            for name in ("full",) + PERIOD_NAMES:
                if name in pm and name in period_metrics[bench_id]:
                    checks[name] = evaluate(pm[name], period_metrics[bench_id][name], criteria)

        target = res.target.dropna()
        last = target.iloc[-1]
        changed = (target != target.shift(1)).any(axis=1)
        since = changed[changed].index[-1] if changed.iloc[1:].any() else target.index[0]
        entry = {
            "id": r["id"],
            "name": r["name"],
            "kind": r["kind"],
            "fn": r["fn"],
            "params": r["params"],
            "metrics": {
                k: {kk: (_round(vv) if isinstance(vv, float) else vv) for kk, vv in v.items()}
                for k, v in pm.items()
            },
            "checks": checks,
            "current": {
                "decided_on": target.index[-1].strftime("%Y-%m-%d"),
                "weights": {k: _round(v, 4) for k, v in last.items() if v > 0},
                "since": since.strftime("%Y-%m-%d"),
            },
        }
        if r.get("search_origin"):
            entry["survivorship_biased"] = search_biased
        out_strats.append(entry)

    # Weekly series keep the JSON small; drawdown keeps each week's worst point.
    series = {"dates": None, "equity": {}, "drawdown": {}}
    for r in runs:
        ret, _, _ = window(results[r["id"]])
        eq = (1 + ret).cumprod().resample("W-FRI").last()
        dd = drawdown(ret).resample("W-FRI").min()
        # Shared dates; past its visible end an entry's values are null, which
        # Chart.js draws as a gap.
        if not r["allow_holdout"]:
            beyond = eq.index > _visible_end(r, criteria, common_end)
            eq, dd = eq.mask(beyond), dd.mask(beyond)
        series["dates"] = [d.strftime("%Y-%m-%d") for d in eq.index]
        series["equity"][r["id"]] = [_round(v, 4) for v in eq]
        series["drawdown"][r["id"]] = [_round(v, 4) for v in dd]

    payload = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data_source": "synthetic" if args.synthetic else "yahoo",
        "data_through": close.dropna(how="all").index[-1].strftime("%Y-%m-%d"),
        "window": {
            "start": common_start.strftime("%Y-%m-%d"),
            "end": common_end.strftime("%Y-%m-%d"),
        },
        "criteria_hash": criteria_hash,
        "criteria": criteria,
        "strategies": out_strats,
        "series": series,
        "survivorship_biased": None,
        "research_funnel": research_funnel,
        "portfolio": {
            "capital_split": capital_split,
            "core": {"origin": portfolio_cfg["core"]["origin"], "fn": portfolio_cfg["core"]["fn"]},
            "sleeve": {"count": len(portfolio_cfg["sleeve"]["strategies"])},
            "provenance": portfolio_cfg["provenance"],
            "sleeve_holdings": sleeve_holdings,
            "idle_cash_pct": idle_cash_pct,
        },
    }
    print(
        f"Research funnel: {'available' if research_funnel['available'] else 'no run yet'}"
        f" (total attempts {research_funnel['total_attempts']})"
    )
    print(f"Sleeve holdings: {len(sleeve_holdings)}")

    coverage_path = data_dir / "universe_coverage.json"
    if coverage_path.exists():
        coverage = json.loads(coverage_path.read_text())
        payload["universe"] = {
            "name": coverage["name"],
            "as_of": coverage["as_of"],
            "survivorship_biased": coverage["survivorship_biased"],
            "requested": coverage["requested"],
            "loaded": coverage["loaded"],
            "failed": coverage["failed"],
            "late_starters": coverage["late_starters"],
            "ended_early": coverage["ended_early"],
        }
        payload["survivorship_biased"] = coverage["survivorship_biased"]
        bias = (
            "SURVIVORSHIP-BIASED" if coverage["survivorship_biased"] else "not survivorship-biased"
        )
        print(
            f"Universe {coverage['name']} ({bias}): {coverage['loaded']}/{coverage['requested']} "
            f"loaded, {coverage['late_starters']} late starters, {coverage['ended_early']} ended early"
        )

    core_comparison = build_core_comparison(ROOT)
    if core_comparison is not None:
        payload["core_comparison"] = core_comparison
        print(f"Core comparison: {', '.join(sorted(core_comparison['sources']))}")

    fragility = build_fragility(ROOT)
    if fragility is not None:
        payload["fragility"] = fragility
        print(f"Fragility screen: as of {fragility['header'].get('as-of date', 'unknown')}")

    decision = build_decision(ROOT)
    if decision is not None:
        payload["decision"] = decision
        print(f"Decision helper: {len(decision['sections'])} sections")

    longrun = build_longrun(ROOT)
    if longrun is not None:
        payload["longrun"] = longrun
        print(f"Long-run withdrawals: {len(longrun['sections'])} sections")

    rsp_sleeve = build_rsp_sleeve(ROOT)
    if rsp_sleeve is not None:
        payload["rsp_sleeve"] = rsp_sleeve
        print(f"RSP sleeve: {rsp_sleeve['header'].get('verdict', 'unknown')}")

    withdrawal_rules = build_withdrawal_rules(ROOT)
    if withdrawal_rules is not None:
        payload["withdrawal_rules"] = withdrawal_rules
        print(f"Withdrawal rules: {len(withdrawal_rules['sections'])} sections")

    staged_entry = build_staged_entry(ROOT)
    if staged_entry is not None:
        payload["staged_entry"] = staged_entry
        print(f"Staged entry: {len(staged_entry['sections'])} sections")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, separators=(",", ":"), default=str))
    print(
        f"Wrote {out} ({out.stat().st_size / 1024:.0f} KB), data through {payload['data_through']}"
    )
    for s in out_strats:
        f = s["metrics"]["full"]
        print(
            f"  {s['name']:<60} CAGR {f['cagr']:6.1%}  Sharpe {f['sharpe']:.2f}  "
            f"MaxDD {f['max_drawdown']:6.1%}  trades {f.get('trades')}"
        )


if __name__ == "__main__":
    main()
