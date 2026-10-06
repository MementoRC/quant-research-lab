"""Core comparison: an EXPLORATION of alternative, more resilient cores
against the current one (spec: docs/superpowers/specs/2026-10-03-core-compare-design.md).
It forecasts nothing, tunes nothing and selects nothing. Pure functions;
callers inject data and configs. Validation and holdout data never enter
(frames are cut at the research end; windows reaching the validation period
are dropped), and `slice_period(..., unseal_holdout=True)` is never called.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd
import yaml

from .engine import run_backtest
from .metrics import compute_metrics
from .periods import period_bounds, slice_period
from .portfolio import combine_portfolio
from .strategies import REGISTRY
from .stress import PortfolioDef, StressConfig, Window, run_stress

Build = Callable[[dict[str, pd.DataFrame], list[str]], pd.DataFrame]
ALL_MODES = frozenset({"replay", "frozen", "hypothetical"})
CORE_FAMILIES = ("core_trend", "core_mix")
_ID = re.compile(r"[A-Za-z0-9_-]+")
_REQUIRED = {"id", "label", "fn", "params"}


@dataclass(frozen=True)
class Candidate:
    id: str
    label: str
    fn: str
    params: dict


def candidate_weights(cand: Candidate, close: pd.DataFrame) -> pd.DataFrame:
    """The candidate's raw core weights (fractions of the core's own capital),
    built exactly as scripts build `config/portfolio.yaml` members."""
    spec = REGISTRY[cand.fn]
    cols = spec.tickers(cand.params)
    weights: pd.DataFrame = spec.weights(close[cols], **cand.params)
    return weights


def _parse_candidate(raw: object) -> Candidate:
    if (
        not isinstance(raw, dict)
        or not raw.keys() >= _REQUIRED
        or not isinstance(raw["params"], dict)
    ):
        raise ValueError(
            f"each candidate needs {sorted(_REQUIRED)} with `params` a mapping, got {raw!r}"
        )
    cand = Candidate(str(raw["id"]), str(raw["label"]), str(raw["fn"]), dict(raw["params"]))
    if not _ID.fullmatch(cand.id):
        raise ValueError(f"candidate id {cand.id!r} must match [A-Za-z0-9_-]+")
    if cand.fn not in CORE_FAMILIES:
        raise ValueError(f"candidate {cand.id}: fn must be one of {CORE_FAMILIES}")
    if cand.params.get("risk_off") == "CASH":
        raise ValueError(f"candidate {cand.id}: CASH risk_off has no priced branch to stress")
    try:
        cols = REGISTRY[cand.fn].tickers(cand.params)
        probe = pd.DataFrame(1.0, index=pd.bdate_range("2020-01-01", periods=3), columns=cols)
        candidate_weights(cand, probe)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"candidate {cand.id}: bad params ({exc})") from exc
    return cand


def load_core_candidates(path: str | Path) -> tuple[list[Candidate], str]:
    """Return (candidates, full sha256 of the raw file bytes). Raises ValueError
    on malformed YAML, a wrong version, a missing/empty list, duplicate or
    malformed ids, an unknown fn, non-mapping params, a CASH risk_off, or params
    the strategy rejects."""
    raw = Path(path).read_bytes()
    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"core candidates file is not valid YAML ({exc})") from exc
    if not isinstance(doc, dict) or doc.get("version") != 1:
        raise ValueError("core candidates file must be a mapping with `version: 1`")
    entries = doc.get("candidates")
    if not isinstance(entries, list) or not entries:
        raise ValueError("core candidates file needs a non-empty `candidates` list")
    cands = [_parse_candidate(e) for e in entries]
    ids = [c.id for c in cands]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ValueError(f"duplicate candidate ids: {dupes}")
    return cands, hashlib.sha256(raw).hexdigest()


def split_windows(windows: list[Window], criteria: dict) -> tuple[list[Window], list[Window]]:
    """(kept, excluded). A window is excluded if it ends on/after the validation
    start: that covers any overlap with the validation period and everything
    later (holdout). Order is preserved."""
    vstart, _ = period_bounds(criteria, "validation")
    if vstart is None:
        raise ValueError("criteria has no validation start")
    kept = [w for w in windows if w.end < vstart]
    excluded = [w for w in windows if w.end >= vstart]
    return kept, excluded


def research_metrics(
    cand: Candidate, data: dict[str, pd.DataFrame], criteria: dict, split: dict
) -> dict:
    """Research-period metrics of the candidate as a core-only portfolio.
    Frames are cut at the research end BEFORE weights are built (warm-up rows
    before the research start are allowed); returns are then cut to the
    research period. Raises ValueError if the core's weights are not valid at
    the research start (no silently shortened period)."""
    rstart, rend = period_bounds(criteria, "research")
    if rstart is None or rend is None:
        raise ValueError("criteria research period needs a start and an end")
    close = data["close"].loc[:rend]
    open_ = data["open"].loc[:rend]
    core_w = candidate_weights(cand, close)
    valid = core_w.dropna().index
    if valid.empty or valid[0] > rstart:
        raise ValueError(
            f"candidate {cand.id}: core weights not valid at the research start {rstart.date()}"
        )
    if core_w.loc[rstart:].isna().any(axis=None):
        raise ValueError(
            f"candidate {cand.id}: core weights contain NaN inside the research period "
            "(would be zero-filled into cash)"
        )
    combined = combine_portfolio(core_w, [], split).combined
    cols = list(combined.columns)
    result = run_backtest(
        open_[cols],
        close[cols],
        combined,
        cost_bps=float(criteria["costs"]["bps_per_unit_turnover"]),
    )
    returns = slice_period(result.returns, criteria, "research")
    turnover = slice_period(result.turnover, criteria, "research")
    executed = slice_period(result.executed, criteria, "research")
    metrics = compute_metrics(returns, turnover, executed)
    if "cagr" not in metrics:
        raise ValueError(f"candidate {cand.id}: too few research days for metrics")
    return metrics


def branch_mixes(cand: Candidate) -> dict[str, dict[str, float]] | None:
    """Static risk_on / risk_off mixes of a switching candidate, or None for a
    static one. A switching rule's latest weight row depends on which branch is
    live, so frozen/hypothetical cells are reported for both branches."""
    p = cand.params
    if cand.fn == "core_trend":
        on, off = p.get("risk_on", "QQQ"), p.get("risk_off", "GLD")
        return {"risk_on": {on: 1.0}, "risk_off": {off: 1.0}}
    if p.get("risk_off") is None:
        return None
    return {"risk_on": dict(p["risk_on"]), "risk_off": dict(p["risk_off"])}


def _rule_build(cand: Candidate, split: dict) -> Build:
    def build(data: dict[str, pd.DataFrame], keep: list[str]) -> pd.DataFrame:
        return combine_portfolio(candidate_weights(cand, data["close"]), [], split).combined

    return build


def _static_build(mix: dict[str, float], split: dict) -> Build:
    def build(data: dict[str, pd.DataFrame], keep: list[str]) -> pd.DataFrame:
        w = pd.DataFrame({t: float(x) for t, x in mix.items()}, index=data["close"].index)
        return combine_portfolio(w, [], split).combined

    return build


def stress_portfolios(
    cands: list[Candidate], split: dict
) -> tuple[list[PortfolioDef], dict[str, frozenset[str]]]:
    """PortfolioDefs for `run_stress` plus, per portfolio name, the cell modes
    to keep. A static candidate X is one portfolio with every mode. A switching
    candidate X is `X` (replay cells only) plus `X[risk_on]` and `X[risk_off]`
    (frozen and hypothetical cells only)."""
    defs: list[PortfolioDef] = []
    modes: dict[str, frozenset[str]] = {}
    for cand in cands:
        tickers = list(REGISTRY[cand.fn].tickers(cand.params))
        defs.append(PortfolioDef(cand.id, _rule_build(cand, split), tickers))
        branches = branch_mixes(cand)
        if branches is None:
            modes[cand.id] = ALL_MODES
            continue
        modes[cand.id] = frozenset({"replay"})
        for state, mix in branches.items():
            name = f"{cand.id}[{state}]"
            defs.append(PortfolioDef(name, _static_build(mix, split), list(mix)))
            modes[name] = frozenset({"frozen", "hypothetical"})
    return defs, modes


def _candidate_result(
    cand: Candidate,
    cells: list,
    data: dict[str, pd.DataFrame],
    criteria: dict,
    split: dict,
    max_drawdown: float,
) -> dict:
    try:
        research = research_metrics(cand, data, criteria, split)
    except ValueError as exc:  # recorded as a failed test, never skipped (AGENTS.md)
        research = {"error": str(exc)}
    research_breach = bool(research.get("max_drawdown", 0.0) > max_drawdown)
    stress_breaches = sum(1 for c in cells if c.breach)
    return {
        "id": cand.id,
        "label": cand.label,
        "fn": cand.fn,
        "params": cand.params,
        "research": research,
        "research_breach": research_breach,
        "stress_breaches": stress_breaches,
        "unavailable": sum(1 for c in cells if c.unavailable is not None),
        "breach_count": stress_breaches + int(research_breach),
        "cells": [asdict(c) for c in cells],
    }


def run_core_compare(
    cands: list[Candidate],
    stress_cfg: StressConfig,
    data: dict[str, pd.DataFrame],
    criteria: dict,
    split: dict,
    max_drawdown: float,
) -> dict:
    """Every candidate: research metrics plus stress cells on windows that do
    not overlap validation/holdout. Stress frames are cut at the research end,
    so no later row reaches `run_stress`."""
    kept, excluded = split_windows(stress_cfg.windows, criteria)
    cfg = StressConfig(kept, stress_cfg.hypotheticals, stress_cfg.max_report_age_days)
    _, rend = period_bounds(criteria, "research")
    stress_data = {k: v.loc[:rend] for k, v in data.items()}
    portfolios, modes = stress_portfolios(cands, split)
    cells = [
        c
        for c in run_stress(cfg, portfolios, stress_data, max_drawdown, criteria)
        if c.mode in modes[c.portfolio]
    ]
    results = [
        _candidate_result(
            cand,
            [c for c in cells if c.portfolio.split("[")[0] == cand.id],
            data,
            criteria,
            split,
            max_drawdown,
        )
        for cand in cands
    ]
    return {"excluded_windows": [w.name for w in excluded], "candidates": results}


def benchmark_metrics(
    data: dict[str, pd.DataFrame], criteria: dict, split: dict, ticker: str, max_drawdown: float
) -> list[dict]:
    """Reference rows (NOT candidates, not counted in the trial count): plain
    `ticker` buy-and-hold over the research period, at the core share of the
    split (rest cash; like-for-like with the candidate rows) and at 100%."""
    mix = Candidate("benchmark", "benchmark", "core_mix", {"risk_on": {ticker: 1.0}})
    variants = (
        (f"{ticker}@split", f"{ticker} buy-and-hold at core share (rest cash)", split),
        (f"{ticker}@100", f"{ticker} buy-and-hold, 100%", {"core": 1.0, "sleeve": 0.0}),
    )
    rows = []
    for row_id, label, row_split in variants:
        try:
            research = research_metrics(mix, data, criteria, row_split)
        except ValueError as exc:  # recorded, never skipped (AGENTS.md)
            research = {"error": str(exc)}
        breach = bool(research.get("max_drawdown", 0.0) > max_drawdown)
        rows.append(
            {
                "id": row_id,
                "label": label,
                "research": research,
                "research_breach": breach,
                "breach_count": int(breach),
            }
        )
    return rows


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x + 0.0:.1%}"  # + 0.0 turns -0.0 into 0.0


def _research_row(c: dict) -> str:
    r = c["research"]
    head = f"| {c['id']} | {c['label']} |"
    if "error" in r:
        return f"{head} error: {r['error']} | | | | {c['breach_count']} |"
    return (
        f"{head} {_pct(r['cagr'])} | {r['sharpe']:.2f} | {_pct(r['max_drawdown'])} | "
        f"{r['turnover_per_year']:.2f} | {c['breach_count']} |"
    )


def _proxied(cell: dict) -> str:
    """Per-class weight shares proxied at the window start, e.g. "bonds 40%, gold 20%"."""
    shares = (cell.get("detail") or {}).get("proxied_share") or {}
    return ", ".join(f"{cls} {share:.0%}" for cls, share in sorted(shares.items()) if share > 0)


def _cell_row(cand_id: str, cell: dict) -> str:
    flag = "BREACH" if cell["breach"] else ("UNAVAILABLE" if cell["unavailable"] else "")
    return (
        f"| {cand_id} | {cell['portfolio']} | {cell['scenario']} | {cell['mode']} | "
        f"{_pct(cell['loss'])} | {_proxied(cell)} | {flag} |"
    )


def _benchmark_section(rows: list[dict] | None) -> list[str]:
    if not rows:
        return []
    return [
        "## Benchmark (not a candidate; not counted in the trial count)",
        "",
        "| id | rule | CAGR | Sharpe | max drawdown | turnover/yr | breaches |",
        "|---|---|---|---|---|---|---|",
        *(_research_row(r) for r in rows),
        "",
        "Breaches: research-period drawdown vs the cap only (0/1). Stress cells for 80% QQQ "
        "equal candidate A's `A[risk_on]` rows above.",
        "",
    ]


def render_markdown(report: dict) -> str:
    """Deterministic markdown (no timestamp) so a re-run on the same data diffs."""
    rp, split = report["research_period"], report["capital_split"]
    excluded = ", ".join(report["excluded_windows"]) or "none"
    lines = [
        "# Core comparison (exploration only)",
        "",
        "Diagnostic of the pre-registered cores; it selects nothing. Spec: "
        "docs/superpowers/specs/2026-10-03-core-compare-design.md.",
        "",
        f"- candidates file sha256: `{report['candidates_sha256']}`",
        f"- trial count: {report['trial_count']}",
        f"- stress.yaml sha256: `{report['stress_sha256']}`",
        f"- research period: {rp['start']} to {rp['end']} (validation and holdout data never used "
        "(prices are downloaded in full; every computation is cut at the research end))",
        f"- capital split: core {split['core']:.0%} / sleeve {split['sleeve']:.0%} "
        "(sleeve empty, held as cash)",
        f"- max drawdown cap: {report['max_drawdown']:.0%} (config/profile.yaml)",
        f"- windows not evaluated (overlap validation): {excluded}",
        "",
        "## Research period",
        "",
        "| id | rule | CAGR | Sharpe | max drawdown | turnover/yr | breaches |",
        "|---|---|---|---|---|---|---|",
        *(_research_row(c) for c in report["candidates"]),
        "",
        *_benchmark_section(report.get("benchmark")),
        "## Stress cells",
        "",
        "| id | portfolio | scenario | mode | loss | proxied to cash | flag |",
        "|---|---|---|---|---|---|---|",
        *(_cell_row(c["id"], cell) for c in report["candidates"] for cell in c["cells"]),
        "",
        "Note: in `dotcom_2000` the bond and gold ETFs did not yet exist, so bonds/gold "
        'weights are treated as cash (the "proxied to cash" column); this understates '
        "their cushion in that window.",
        "",
        "Note: for switching candidates the breach count covers the replay cell plus both "
        "branch cells (`[risk_on]`, `[risk_off]`), plus the research-period breach.",
        "",
    ]
    return "\n".join(lines)
