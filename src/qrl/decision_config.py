"""Decision helper configuration and portfolio model (spec:
docs/methodology/decision-helper.md).

Every portfolio is 100% of capital and is a list of (candidate, share) parts:
A-G come from `config/core_candidates.yaml` unchanged (its sha256 is checked
against the value pinned in `config/decision.yaml`), static mixes are
`core_mix` candidates, and a blend is the share-weighted union of its
components' parts. The loader also reads the historical windows (by name from
`config/stress.yaml`), the judgement-based scenarios, the withdrawal rates and
the start years, and refuses anything past the data end (the research end).
Pure functions only.
"""

from __future__ import annotations

import hashlib
import itertools
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

from .core_compare import Candidate, branch_mixes, load_core_candidates
from .stress import StressConfig, Window

_ID = re.compile(r"[A-Za-z0-9_-]+")
_EPS = 1e-9
_KEYS = frozenset(
    {
        "version",
        "candidates_sha256",
        "static",
        "blends",
        "windows",
        "proxied_indicative_above",
        "scenarios",
        "withdrawal_rates",
        "start_years",
    }
)


@dataclass(frozen=True)
class Portfolio:
    """100% of capital: `parts` are (candidate, share of capital) pairs whose
    shares sum to 1. A-G and static mixes have one part; a blend has several."""

    id: str
    label: str
    parts: tuple[tuple[Candidate, float], ...]


@dataclass(frozen=True)
class Scenario:
    name: str
    label: str
    returns: dict[str, float]  # one-year total return per fund
    inflation: float  # one-year inflation


@dataclass(frozen=True)
class DecisionConfig:
    portfolios: list[Portfolio]
    windows: list[Window]
    scenarios: list[Scenario]
    rates: list[float]
    start_years: list[int]
    proxied_threshold: float
    candidate_count: int
    candidates_sha256: str
    sha256: str


def portfolio_states(p: Portfolio) -> dict[str, dict[str, float]]:
    """Fixed weights (fractions of capital) per state. A portfolio without a
    switching part has one state, `static`. A switching part contributes its
    risk_on / risk_off branches (`core_compare.branch_mixes`), combined with
    the other parts' fixed weights, so a blend with one switching part has
    exactly two states."""
    options: list[list[tuple[str, dict[str, float]]]] = []
    for cand, share in p.parts:
        branches = branch_mixes(cand) or {"": dict(cand.params["risk_on"])}
        options.append(
            [
                (name, {t: share * float(w) for t, w in mix.items()})
                for name, mix in branches.items()
            ]
        )
    states: dict[str, dict[str, float]] = {}
    for combo in itertools.product(*options):
        name = "+".join(n for n, _ in combo if n) or "static"
        mix: dict[str, float] = {}
        for _, part in combo:
            for ticker, weight in part.items():
                mix[ticker] = mix.get(ticker, 0.0) + weight
        states[name] = mix
    return states


def held_tickers(portfolios: list[Portfolio]) -> set[str]:
    """Every fund any portfolio holds in any state (signal-only tickers excluded)."""
    return {
        t
        for p in portfolios
        for mix in portfolio_states(p).values()
        for t, w in mix.items()
        if w > 0
    }


def _list(doc: dict, key: str) -> list:
    value = doc[key]
    if not isinstance(value, list):
        raise ValueError(f"decision config `{key}` must be a list")
    return value


def _entry(raw: object, keys: set[str], what: str) -> dict:
    if not isinstance(raw, dict) or not raw.keys() >= keys:
        raise ValueError(f"each {what} needs {sorted(keys)}, got {raw!r}")
    if not _ID.fullmatch(str(raw["id"])):
        raise ValueError(f"{what} id {raw['id']!r} must match [A-Za-z0-9_-]+")
    return raw


def _positive(raw: object, what: str) -> dict[str, float]:
    if not isinstance(raw, dict) or not raw:
        raise ValueError(f"{what} must be a non-empty mapping")
    out = {str(k): float(v) for k, v in raw.items()}
    if any(v <= 0 for v in out.values()):
        raise ValueError(f"{what}: every weight must be positive")
    return out


def _static(raw: object) -> Portfolio:
    e = _entry(raw, {"id", "label", "mix"}, "static portfolio")
    mix = _positive(e["mix"], f"static portfolio {e['id']} mix")
    cand = Candidate(str(e["id"]), str(e["label"]), "core_mix", {"risk_on": mix})
    return Portfolio(cand.id, cand.label, ((cand, 1.0),))


def _blend(raw: object, known: dict[str, Portfolio]) -> Portfolio:
    e = _entry(raw, {"id", "label", "parts"}, "blend")
    shares = _positive(e["parts"], f"blend {e['id']} parts")
    unknown = sorted(set(shares) - known.keys())
    if unknown:
        raise ValueError(f"blend {e['id']}: unknown component(s) {unknown}")
    parts = tuple(
        (cand, share * inner) for comp, share in shares.items() for cand, inner in known[comp].parts
    )
    return Portfolio(str(e["id"]), str(e["label"]), parts)


def _add(portfolios: dict[str, Portfolio], p: Portfolio) -> None:
    if p.id in portfolios:
        raise ValueError(f"duplicate portfolio id {p.id!r}")
    portfolios[p.id] = p


def _check_full(p: Portfolio) -> None:
    for state, mix in portfolio_states(p).items():
        total = sum(mix.values())
        if abs(total - 1.0) > _EPS:
            raise ValueError(f"portfolio {p.id} [{state}] holds {total:.3f} of capital, not 100%")


def _portfolios(cands: list[Candidate], static: list, blends: list) -> list[Portfolio]:
    """A-G, then static mixes, then blends (of A-G and static mixes only)."""
    portfolios: dict[str, Portfolio] = {}
    for cand in cands:
        _add(portfolios, Portfolio(cand.id, cand.label, ((cand, 1.0),)))
    for entry in static:
        _add(portfolios, _static(entry))
    base = dict(portfolios)
    for entry in blends:
        _add(portfolios, _blend(entry, base))
    for p in portfolios.values():
        _check_full(p)
    return list(portfolios.values())


def _scenario(raw: object, held: set[str]) -> Scenario:
    keys = {"name", "label", "returns", "inflation"}
    if not isinstance(raw, dict) or not raw.keys() >= keys or not isinstance(raw["returns"], dict):
        raise ValueError(
            f"each scenario needs {sorted(keys)} with `returns` a mapping, got {raw!r}"
        )
    name = str(raw["name"])
    returns = {str(t): float(v) for t, v in raw["returns"].items()}
    missing = sorted(held - returns.keys())
    if missing:
        raise ValueError(
            f"scenario {name}: missing held fund(s) {missing} (no default asset class)"
        )
    inflation = float(raw["inflation"])
    if any(v <= -1 for v in returns.values()) or inflation <= -1:
        raise ValueError(
            f"scenario {name}: every return and the inflation must be above -1 (-100%)"
        )
    return Scenario(name, str(raw["label"]), returns, inflation)


def _scenarios(entries: list, held: set[str]) -> list[Scenario]:
    scenarios = [_scenario(e, held) for e in entries]
    names = [s.name for s in scenarios]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise ValueError(f"duplicate scenario names: {dupes}")
    return scenarios


def _windows(names: list, stress_cfg: StressConfig, end: pd.Timestamp) -> list[Window]:
    by_name = {w.name: w for w in stress_cfg.windows}
    windows = []
    for name in names:
        window = by_name.get(str(name))
        if window is None:
            raise ValueError(f"window {name} is not in stress.yaml")
        if window.end > end:
            raise ValueError(
                f"window {window.name} ends {window.end.date()}, past the data end {end.date()}"
            )
        windows.append(window)
    return windows


def _rates(raw: list) -> list[float]:
    rates = [float(r) for r in raw]
    if not rates or any(not 0 < r < 1 for r in rates):
        raise ValueError("withdrawal_rates must be a non-empty list of fractions between 0 and 1")
    return rates


def _start_years(raw: list, end: pd.Timestamp) -> list[int]:
    years = [int(y) for y in raw]
    if not years:
        raise ValueError("start_years must be a non-empty list")
    late = [y for y in years if pd.Timestamp(year=y, month=1, day=1) > end]
    if late:
        raise ValueError(f"start year(s) {late} past the data end {end.date()}")
    return years


def load_decision_config(
    path: str | Path, candidates_path: str | Path, stress_cfg: StressConfig, end: pd.Timestamp
) -> DecisionConfig:
    """Parse and validate `config/decision.yaml`. Raises ValueError on
    malformed YAML, a wrong version, a missing key, a core_candidates.yaml
    sha256 mismatch, a bad or duplicate id, a portfolio not at 100% of
    capital, an unknown blend component, a scenario missing a held fund or
    with a return/inflation <= -1, a duplicate scenario name, an unknown
    window, or a window or start year past `end`."""
    raw = Path(path).read_bytes()
    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"decision config is not valid YAML ({exc})") from exc
    if not isinstance(doc, dict) or doc.get("version") != 1:
        raise ValueError("decision config must be a mapping with `version: 1`")
    missing = sorted(_KEYS - doc.keys())
    if missing:
        raise ValueError(f"decision config is missing key(s) {missing}")
    cands, cand_hash = load_core_candidates(candidates_path)
    if cand_hash != doc["candidates_sha256"]:
        raise ValueError(
            f"core_candidates.yaml sha256 mismatch: file {cand_hash}, "
            f"decision.yaml pins {doc['candidates_sha256']}"
        )
    portfolios = _portfolios(cands, _list(doc, "static"), _list(doc, "blends"))
    return DecisionConfig(
        portfolios=portfolios,
        windows=_windows(_list(doc, "windows"), stress_cfg, end),
        scenarios=_scenarios(_list(doc, "scenarios"), held_tickers(portfolios)),
        rates=_rates(_list(doc, "withdrawal_rates")),
        start_years=_start_years(_list(doc, "start_years"), end),
        proxied_threshold=float(doc["proxied_indicative_above"]),
        candidate_count=len(cands),
        candidates_sha256=cand_hash,
        sha256=hashlib.sha256(raw).hexdigest(),
    )
