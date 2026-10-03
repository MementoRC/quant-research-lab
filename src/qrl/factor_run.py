"""The locked configuration of a factor run (Phase 4, milestone 4).

A factor run searches the Phase 4 factor families (`value_ey`, `profitability`,
`low_investment`) over the point-in-time universe, from a later research start
than the price runs (owner decision 2026-10-02: XBRL era, 2009-01-01), judged
under `combined_null`. Everything that defines it lives in `config/factor.yaml`,
which is locked for any run seeded with it, exactly like `combined_null.yaml`:

- Hash binding: the sha256 of `factor.yaml`'s raw bytes and of the membership CSV
  (`config/universes/us_large_cap_pit.csv`, via `config/universe_pit.yaml`).
  `search seed --factor-config` stores both in the run's `data_source`
  fingerprint (`factor_data_source`), so `search batch` and `validate` refuse
  if either changed (`check_factor_run`). No ledger schema change: runs 1-5 keep
  the fingerprints they were seeded with.
- `effective_criteria`: `config/criteria.yaml` with ONLY `periods.research.start`
  replaced by `research_start`. `qrl.periods.slice_period` takes the criteria
  dict, so `periods.py` and `criteria.yaml` are untouched; validation and
  holdout bounds are the ones in `criteria.yaml` (holdout stays sealed). The
  difference is verified in code, not trusted.
- Null baseline: `pit_equal_weight`, the equal weight of each day's point-in-time
  members (`qrl.controls.null_sleeve_weights(..., member_mask=...)`), the
  factor-run reading of "equal weight of the same universe": the candidate can
  only hold that day's members, so the null may not hold the ever-members
  either. `combined_null.yaml` only says `baseline: null_equal_weight`, so no
  edit to it is needed.
- Factor families are usable only in factor runs and price families never in
  them (`check_family_mix`).
"""

from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

from .factor_data import FactorData, factor_universe
from .ledger import data_source_fingerprint
from .pit_universe import ROOT, load_pit_universe
from .strategies import FACTOR_FAMILIES

FACTOR_CONFIG_PATH = ROOT / "config" / "factor.yaml"
PIT_NULL_BASELINE = "pit_equal_weight"
_REQUIRED_KEYS = (
    "research_start",
    "universe",
    "universe_membership_sha256",
    "families",
    "null_baseline",
)


@dataclass(frozen=True)
class FactorRun:
    """A loaded, verified `config/factor.yaml`."""

    research_start: str
    families: list[str]
    universe: dict  # {"name": ..., "tickers": every ticker ever a member}
    membership: pd.DataFrame
    config_sha256: str
    membership_sha256: str


def _resolve(path: str | Path, base: Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else base.parent.parent / p


def load_factor_run(path: str | Path = FACTOR_CONFIG_PATH) -> FactorRun:
    """Load and verify `factor.yaml`. Raises `ValueError` for a missing key, an
    unsupported baseline or family, an unparseable start, a membership CSV that
    does not match its yaml (`load_pit_universe`), or one that does not match
    the `universe_membership_sha256` recorded in factor.yaml."""
    yaml_path = Path(path).resolve()
    raw = yaml_path.read_bytes()
    cfg = yaml.safe_load(raw)
    if not isinstance(cfg, dict) or not set(_REQUIRED_KEYS) <= set(cfg):
        raise ValueError(f"{path}: expected a mapping with {list(_REQUIRED_KEYS)}.")
    if cfg["null_baseline"] != PIT_NULL_BASELINE:
        raise ValueError(f"{path}: null_baseline must be {PIT_NULL_BASELINE!r}.")
    families = [str(f) for f in cfg["families"]]
    if not families or not set(families) <= FACTOR_FAMILIES:
        raise ValueError(
            f"{path}: families must be a non-empty subset of {sorted(FACTOR_FAMILIES)}."
        )
    pd.Timestamp(cfg["research_start"])  # raises ValueError if not a date
    meta, membership = load_pit_universe(_resolve(cfg["universe"], yaml_path))
    if meta["membership_sha256"] != cfg["universe_membership_sha256"]:
        raise ValueError(
            f"{path}: universe_membership_sha256 {cfg['universe_membership_sha256']} does not "
            f"match the universe's membership_sha256 {meta['membership_sha256']}."
        )
    return FactorRun(
        research_start=str(cfg["research_start"]),
        families=families,
        universe={"name": meta["name"], "tickers": factor_universe(membership)},
        membership=membership,
        config_sha256=hashlib.sha256(raw).hexdigest(),
        membership_sha256=str(meta["membership_sha256"]),
    )


def build_provider(run: FactorRun) -> FactorData:
    """Factor-field provider over the run's own (hashed) membership."""
    return FactorData(run.membership)


def effective_criteria(criteria: dict, research_start: str) -> dict:
    """`criteria` with only `periods.research.start` replaced by `research_start`.
    Raises `ValueError` if anything else would differ, or if the new start is not
    before the research end."""
    effective = copy.deepcopy(criteria)
    effective["periods"]["research"]["start"] = research_start
    _require_only_start_differs(criteria, effective)
    end = criteria["periods"]["research"].get("end")
    if end and pd.Timestamp(research_start) >= pd.Timestamp(end):
        raise ValueError(f"research_start {research_start} must be before research end {end}")
    return effective


def _require_only_start_differs(base: dict, effective: dict) -> None:
    left, right = copy.deepcopy(base), copy.deepcopy(effective)
    for d in (left, right):
        d["periods"]["research"].pop("start", None)
    if left != right:
        raise ValueError("effective criteria differ from criteria.yaml beyond research start")


def factor_data_source(synthetic: bool, run: FactorRun) -> dict:
    """The run's data-source fingerprint: the usual one plus both factor hashes,
    so `Ledger.check_data_source` also refuses a mismatch."""
    return {
        **data_source_fingerprint(synthetic, run.universe["name"], run.universe["tickers"]),
        "factor_config_sha256": run.config_sha256,
        "membership_sha256": run.membership_sha256,
    }


def is_factor_run(run: dict) -> bool:
    """True for a ledger run row seeded with `--factor-config`."""
    return bool((run.get("data_source") or {}).get("factor_config_sha256"))


def check_factor_run(run: dict, config_path: str | Path | None) -> FactorRun | None:
    """The `FactorRun` for a factor run row (None for any other run). Raises
    `ValueError` if the current factor.yaml or membership hash differs from the
    one recorded at seed time, or if a config path is given for a run that was
    not seeded as a factor run."""
    recorded = run.get("data_source") or {}
    if not is_factor_run(run):
        if config_path:
            raise ValueError(f"run {run.get('run_id')} was not seeded with --factor-config.")
        return None
    current = load_factor_run(config_path or FACTOR_CONFIG_PATH)
    if current.config_sha256 != recorded["factor_config_sha256"]:
        raise ValueError(
            f"factor.yaml hash has changed since run {run.get('run_id')} started "
            f"({recorded['factor_config_sha256']} -> {current.config_sha256}); refusing to continue."
        )
    if current.membership_sha256 != recorded["membership_sha256"]:
        raise ValueError(
            f"Universe membership CSV hash has changed since run {run.get('run_id')} started "
            f"({recorded['membership_sha256']} -> {current.membership_sha256}); "
            "refusing to continue."
        )
    return current


def check_family_mix(families: list[str], *, factor_run: bool) -> None:
    """Factor families only in factor runs, price families never in them."""
    factor = sorted(set(families) & FACTOR_FAMILIES)
    price = sorted(set(families) - FACTOR_FAMILIES)
    if factor_run and price:
        raise ValueError(f"price families cannot be used in a factor run: {price}")
    if not factor_run and factor:
        raise ValueError(
            f"factor families can only be used in a factor run (seed with --factor-config): "
            f"{factor}"
        )
