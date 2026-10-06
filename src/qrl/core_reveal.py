"""Core shortlist reveal: ONE look at the covid_2020 and inflation_2022 stress
windows (inside the validation period) for the owner-shortlisted cores
(spec: docs/methodology/core-reveal.md). EXPLORATION
ONLY: it selects nothing and changes no config. Pure functions apart from
`load_core_shortlist` reading its file; callers inject data and configs. Every
frame is cut at the last revealed window's end, so neither later validation
data nor the holdout enters any computation.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import NamedTuple

import numpy as np
import pandas as pd
import yaml

from .core_compare import Candidate, _cell_row, stress_portfolios
from .periods import period_bounds
from .stress import PortfolioDef, StressConfig, Window, run_stress

GUARD_TOL = 1e-12


@dataclass(frozen=True)
class Shortlist:
    version: int
    date: str
    decided_by: str
    candidates_sha256: str
    ids: list[str]
    windows: list[str]


def _unique_list(doc: dict, key: str) -> list[str]:
    value = doc.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"core shortlist needs a non-empty `{key}` list")
    items = [str(v) for v in value]
    dupes = sorted({i for i in items if items.count(i) > 1})
    if dupes:
        raise ValueError(f"duplicate {key} in core shortlist: {dupes}")
    return items


def load_core_shortlist(
    path: str | Path,
    candidates: list[Candidate],
    candidates_sha256: str,
    stress_cfg: StressConfig,
    criteria: dict,
) -> tuple[Shortlist, str]:
    """Return (shortlist, full sha256 of the raw file bytes). Raises ValueError
    on a wrong version, empty/duplicate ids or windows, an id not in the
    candidates file, a stale candidates hash, a window not in stress.yaml, a
    window that ends before the validation start, or one ending on/after the
    holdout start."""
    raw = Path(path).read_bytes()
    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"core shortlist is not valid YAML ({exc})") from exc
    if not isinstance(doc, dict) or doc.get("version") != 1:
        raise ValueError("core shortlist must be a mapping with `version: 1`")
    ids = _unique_list(doc, "ids")
    unknown = sorted(set(ids) - {c.id for c in candidates})
    if unknown:
        raise ValueError(f"shortlist ids not in the candidates file: {unknown}")
    if doc.get("candidates_sha256") != candidates_sha256:
        raise ValueError("shortlist candidates_sha256 differs from the candidates file's hash")
    names = _unique_list(doc, "windows")
    by_name = {w.name: w for w in stress_cfg.windows}
    missing = sorted(set(names) - set(by_name))
    if missing:
        raise ValueError(f"shortlist windows not in stress.yaml: {missing}")
    vstart, _ = period_bounds(criteria, "validation")
    hstart, _ = period_bounds(criteria, "holdout")
    if vstart is None or hstart is None:
        raise ValueError("criteria needs a validation start and a holdout start")
    for name in names:
        if by_name[name].end < vstart:
            raise ValueError(f"window {name} ends before the validation start: nothing to reveal")
        if by_name[name].end >= hstart:
            raise ValueError(f"window {name} reaches the sealed holdout")
    shortlist = Shortlist(
        1,
        str(doc.get("date")),
        str(doc.get("decided_by")),
        str(doc["candidates_sha256"]),
        ids,
        names,
    )
    return shortlist, hashlib.sha256(raw).hexdigest()


def guard(
    portfolios: list[PortfolioDef],
    modes: dict[str, frozenset[str]],
    data: dict[str, pd.DataFrame],
) -> None:
    """Look-ahead guard for frozen cells. `run_stress` buys the LAST weight row
    at each window's first close; that is legitimate only if the weights are
    constant over the frame.

    `p.build` goes through `combine_portfolio`, which ZERO-FILLS the NaN rows a
    strategy emits while a held ticker is unpriced or warming up (e.g. before
    GLD existed): those rows come back all-zero or partial, never NaN. So the
    compared rows start at the first date on which every ticker the portfolio
    can hold is priced in `data["close"]` and the weights sum to more than ~0
    (something is held); from there on every row must be identical (tolerance
    1e-12). Raises ValueError for a frozen-mode portfolio that is never fully
    invested or whose invested rows are not constant."""
    for p in portfolios:
        if "frozen" not in modes[p.name]:
            continue
        built = p.build(data, list(p.sleeve_universe))
        close = data["close"]
        held = list(p.sleeve_universe)
        priced = close[held].reindex(built.index).notna().all(axis=1)
        valid = (priced & (built.sum(axis=1) > GUARD_TOL)).to_numpy()
        if not valid.any():
            raise ValueError(f"portfolio {p.name}: no valid weight rows to freeze")
        rows = built.iloc[int(np.argmax(valid)) :]
        spread = float(np.abs(rows.to_numpy() - rows.iloc[0].to_numpy()).max())
        if spread > GUARD_TOL:
            raise ValueError(
                f"portfolio {p.name}: weights are not constant over the frame; frozen cells "
                "would use information from after the window start (look-ahead)"
            )


class Prepared(NamedTuple):
    selected: list[Candidate]
    cfg: StressConfig
    rend: pd.Timestamp
    frames: dict[str, pd.DataFrame]
    portfolios: list[PortfolioDef]
    modes: dict[str, frozenset[str]]


def preflight(
    shortlist: Shortlist,
    cands: list[Candidate],
    stress_cfg: StressConfig,
    data: dict[str, pd.DataFrame],
    split: dict,
) -> Prepared:
    """Everything that can fail without revealing a number: selection, the cut
    at the last window end, the stress portfolios and the look-ahead guard.
    The CLI runs this BEFORE taking the ledger lock; `run_core_reveal` reuses it."""
    by_id = {c.id: c for c in cands}
    selected = [by_id[i] for i in shortlist.ids]
    by_name = {w.name: w for w in stress_cfg.windows}
    windows: list[Window] = [by_name[n] for n in shortlist.windows]
    rend = max(w.end for w in windows)
    frames = {k: v.loc[:rend] for k, v in data.items()}
    cfg = StressConfig(windows, [], stress_cfg.max_report_age_days)
    portfolios, modes = stress_portfolios(selected, split)
    guard(portfolios, modes, frames)
    return Prepared(selected, cfg, rend, frames, portfolios, modes)


def run_core_reveal(
    shortlist: Shortlist,
    cands: list[Candidate],
    stress_cfg: StressConfig,
    data: dict[str, pd.DataFrame],
    criteria: dict,
    split: dict,
    max_drawdown: float,
) -> dict:
    """Replay/frozen cells of the shortlisted cores on the named windows only.
    Frames are cut at the last revealed window's end before any use."""
    selected, cfg, rend, frames, portfolios, modes = preflight(
        shortlist, cands, stress_cfg, data, split
    )
    names = set(shortlist.windows)
    cells = [
        c
        for c in run_stress(cfg, portfolios, frames, max_drawdown, criteria)
        if c.mode in modes[c.portfolio] and c.scenario in names
    ]
    assert all(c.mode != "hypothetical" and c.scenario in names for c in cells)
    results = []
    for cand in selected:
        own = [c for c in cells if c.portfolio.split("[")[0] == cand.id]
        results.append(
            {
                "id": cand.id,
                "label": cand.label,
                "fn": cand.fn,
                "params": cand.params,
                "breach_count": sum(1 for c in own if c.breach),
                "unavailable": sum(1 for c in own if c.unavailable is not None),
                "cells": [asdict(c) for c in own],
            }
        )
    return {
        "revealed_through": str(rend.date()),
        "windows": list(shortlist.windows),
        "candidates": results,
    }


def render_markdown(report: dict) -> str:
    """Deterministic markdown apart from the event id."""
    lines = [
        "# Core shortlist reveal (exploration only)",
        "",
        f"> VALIDATION-SEEN: these cells use validation-period data (2020, 2022). One "
        f"look, recorded in the ledger (event id {report['event_id']}).",
        "",
        "Diagnostic of the shortlisted cores; it selects nothing. Spec: "
        "docs/methodology/core-reveal.md.",
        "",
        f"- shortlist sha256: `{report['shortlist_sha256']}`",
        f"- candidates file sha256: `{report['candidates_sha256']}`",
        f"- stress.yaml sha256: `{report['stress_sha256']}`",
        f"- max drawdown cap: {report['max_drawdown']:.0%} (config/profile.yaml)",
        f"- trial count of the original comparison: {report['trial_count']}",
        f"- shortlist size: {report['shortlist_size']}",
        f"- windows revealed: {', '.join(report['windows'])} (data cut at "
        f"{report['revealed_through']})",
        "",
        "## Stress cells",
        "",
        "| id | portfolio | scenario | mode | loss | proxied to cash | flag |",
        "|---|---|---|---|---|---|---|",
        *(_cell_row(c["id"], cell) for c in report["candidates"] for cell in c["cells"]),
        "",
        "## Breaches",
        "",
        "| id | breaches over revealed cells |",
        "|---|---|",
        *(f"| {c['id']} | {c['breach_count']} |" for c in report["candidates"]),
        "",
        "Note: for the switching candidate the replay cell is the rule itself; frozen "
        "cells are the static branches (`[risk_on]`, `[risk_off]`).",
        "",
    ]
    return "\n".join(lines)
