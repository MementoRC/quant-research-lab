"""Stress-scenario DIAGNOSTIC (spec:
docs/methodology/stress-scenarios.md). Builds the
chosen portfolio (config/portfolio.yaml) and core + each paper-track
candidate (config/paper.yaml), runs config/stress.yaml's scenarios through
`qrl.stress`, prints a table and writes reports/stress.json (gitignored).
It tunes and selects nothing.

Usage:
    python scripts/stress.py
    python scripts/stress.py --out reports/stress.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qrl.criteria import load_criteria  # noqa: E402
from qrl.data import load_ohlcv  # noqa: E402
from qrl.ledger import DEFAULT_LEDGER_PATH, Ledger  # noqa: E402
from qrl.paper import candidate_weights, load_candidate, load_paper_config  # noqa: E402
from qrl.periods import period_bounds  # noqa: E402
from qrl.portfolio import combine_portfolio, load_portfolio_config  # noqa: E402
from qrl.profile import load_profile  # noqa: E402
from qrl.strategies import REGISTRY, SLEEVE_REGISTRY  # noqa: E402
from qrl.stress import (  # noqa: E402
    EQUITY_PROXY,
    Cell,
    PortfolioDef,
    file_hashes,
    load_stress_config,
    run_stress,
    stress_config_paths,
)

_ALL_SPECS = {**REGISTRY, **SLEEVE_REGISTRY}


def _member_weights(fn: str, params: dict, data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Same construction scripts/daily_check.py uses for portfolio.yaml members."""
    spec = _ALL_SPECS[fn]
    cols = spec.tickers(params)
    kwargs = {k: v for k, v in params.items() if k != "tickers"}
    return spec.weights(*[data[f][cols] for f in spec.fields], **kwargs)


def _restrict(params: dict, keep: list[str]) -> dict:
    if "tickers" not in params:
        return params
    keep_set = set(keep)
    return {**params, "tickers": [t for t in params["tickers"] if t in keep_set]}


def _portfolios(portfolio_cfg: dict, candidates: list[dict], split: dict) -> list[PortfolioDef]:
    core = portfolio_cfg["core"]
    core_tickers = list(_ALL_SPECS[core["fn"]].tickers(core["params"]))
    members = portfolio_cfg["sleeve"]["strategies"]
    chosen_universe = sorted({t for m in members for t in _ALL_SPECS[m["fn"]].tickers(m["params"])})

    def chosen(data, keep):
        sleeves = [_member_weights(m["fn"], _restrict(m["params"], keep), data) for m in members]
        core_w = _member_weights(core["fn"], core["params"], data)
        return combine_portfolio(core_w, sleeves, split).combined

    out = [PortfolioDef("chosen", chosen, core_tickers, chosen_universe, candidate=bool(members))]
    for cand in candidates:

        def build(data, keep, cand=cand):
            sleeve = candidate_weights(cand["family"], _restrict(cand["params"], keep), data)
            core_w = _member_weights(core["fn"], core["params"], data)
            return combine_portfolio(core_w, [sleeve], split).combined

        universe = list(_ALL_SPECS[cand["family"]].tickers(cand["params"]))
        name = f"core+{cand['family']}#{cand['test_id']}"
        out.append(PortfolioDef(name, build, core_tickers, universe, candidate=True))
    return out


def _print(cells: list[Cell], max_drawdown: float) -> None:
    print(f"{'portfolio':<32} {'scenario':<20} {'mode':<12} {'loss':>7}  {'flag':<6} label")
    for c in cells:
        loss = "n/a" if c.loss is None else f"{c.loss + 0.0:.1%}"  # + 0.0 turns -0.0 into 0.0
        flag = "BREACH" if c.breach else ("UNAVL" if c.unavailable else "")
        extra = f"  [{c.unavailable}]" if c.unavailable else ""
        print(
            f"{c.portfolio:<32} {c.scenario:<20} {c.mode:<12} {loss:>7}  {flag:<6} {c.label}{extra}"
        )
        if c.detail:
            print(f"{'':<32} detail: {c.detail}")
    print(f"Cap: max drawdown {max_drawdown:.0%} (config/profile.yaml)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(ROOT / "reports" / "stress.json"))
    args = ap.parse_args(argv)

    criteria, _ = load_criteria(ROOT / "config" / "criteria.yaml")
    holdout_start, _ = period_bounds(criteria, "holdout")
    paths = stress_config_paths(ROOT)
    cfg, _ = load_stress_config(paths["stress.yaml"], holdout_start)
    profile = load_profile(paths["profile.yaml"])
    portfolio_cfg = load_portfolio_config(paths["portfolio.yaml"])
    paper_cfg, _ = load_paper_config(paths["paper.yaml"])
    with Ledger(ROOT / DEFAULT_LEDGER_PATH) as ledger:  # as scripts/paper_track.py
        candidates = [load_candidate(ledger, e) for e in paper_cfg["candidates"]]

    portfolios = _portfolios(portfolio_cfg, candidates, profile["capital_split"])
    tickers = sorted(
        {EQUITY_PROXY}.union(*(set(p.core_tickers) | set(p.sleeve_universe) for p in portfolios))
    )
    data = load_ohlcv(tickers, refresh=True)  # as scripts/paper_track.py: latest weights need today
    # combine_portfolio zeroes NaN weights upstream, so a stale core price would
    # silently read as "all cash"; fail loudly instead.
    unpriced = sorted(
        {t for p in portfolios for t in p.core_tickers if pd.isna(data["close"][t].iloc[-1])}
    )
    if unpriced:
        print(f"core tickers unpriced on {data['close'].index[-1].date()}: {unpriced}")
        return 1

    cells = run_stress(cfg, portfolios, data, profile["max_drawdown"], criteria)
    report = {
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "max_report_age_days": cfg.max_report_age_days,
        "max_drawdown": profile["max_drawdown"],
        "hashes": file_hashes(paths),
        "cells": [asdict(c) for c in cells],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str))
    _print(cells, profile["max_drawdown"])
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
