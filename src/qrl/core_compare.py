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
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

from .strategies import REGISTRY

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
