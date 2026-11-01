"""Configuration of the history-grounded scenarios (spec:
docs/methodology/history-scenarios.md). Pure parsing; the sha256 of the file's
bytes is recorded in the report."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

_KEYS = frozenset(
    {
        "version",
        "episodes",
        "panel",
        "portfolios",
        "withdrawal_rates",
        "income_horizons_years",
        "min_correlation",
        "max_gap_days",
        "cache_dir",
        "download_start",
        "cpi_max_first_date",
        "yahoo",
        "fred",
        "yield_lag_business_days",
        "treasury",
        "gold",
        "shiller",
        "worldbank",
    }
)
_SOURCE_KEYS = frozenset({"url", "sheet", "skiprows", "columns", "max_first_date"})
_EPISODE_KEYS = frozenset({"index", "threshold", "start", "horizon_years"})
_PANEL_KEYS = frozenset({"start", "lead_in_start"})
_GOLD_KEYS = frozenset({"futures", "fund"})
_LEG_KEYS = frozenset({"fred", "duration", "start", "end"})


@dataclass(frozen=True)
class Leg:
    """One FRED yield used for a Treasury fund; `start`/`end` bound its use (None: the base leg)."""

    fred: str
    duration: float
    start: pd.Timestamp | None = None
    end: pd.Timestamp | None = None


@dataclass(frozen=True)
class Source:
    """A spreadsheet download: where, which sheet, how many rows to skip, which columns."""

    url: str
    sheet: str
    skiprows: int
    columns: dict[str, str | int]
    max_first_date: pd.Timestamp


@dataclass(frozen=True)
class HistoryConfig:
    index_ticker: str
    threshold: float
    episode_start: pd.Timestamp
    horizon_years: int
    panel_start: pd.Timestamp
    lead_in_start: pd.Timestamp
    portfolios: tuple[str, ...]
    rates: tuple[float, ...]
    income_years: tuple[int, ...]
    min_correlation: float
    max_gap_days: int
    cache_dir: str
    download_start: str
    cpi_max_first_date: pd.Timestamp
    yahoo: dict[str, pd.Timestamp]
    fred: dict[str, pd.Timestamp]
    yield_lag_days: int
    treasury: dict[str, tuple[Leg, ...]]
    gold_futures: str
    gold_fund: str
    shiller: Source
    worldbank: Source
    sha256: str


def _ts(value: object, what: str) -> pd.Timestamp:
    try:
        return pd.Timestamp(str(value))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"history config: {what} {value!r} is not a date") from exc


def _dates(raw: object, what: str) -> dict[str, pd.Timestamp]:
    if not isinstance(raw, dict) or not raw:
        raise ValueError(f"history config `{what}` must be a non-empty mapping")
    return {str(k): _ts(v, f"{what}.{k}") for k, v in raw.items()}


def _check_keys(raw: dict[str, object], keys: frozenset[str], what: str) -> None:
    """Refuse missing and unknown keys, naming them."""
    missing = sorted(keys - raw.keys())
    if missing:
        raise ValueError(f"history config `{what}` is missing key(s) {missing}")
    unknown = sorted(str(k) for k in raw.keys() - keys)
    if unknown:
        raise ValueError(f"history config `{what}` has unknown key(s) {unknown}")


def _section(doc: dict[str, object], key: str, keys: frozenset[str]) -> dict[str, object]:
    raw = doc[key]
    if not isinstance(raw, dict):
        raise ValueError(f"history config `{key}` must be a mapping")
    _check_keys(raw, keys, key)
    return raw


def _num(section: dict[str, object], key: str, where: str, kind: type = float) -> float:
    """A finite number (int or float, not bool) under `key`; ValueError naming `where.key`."""
    value = section.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise ValueError(f"history config `{where}.{key}` must be a finite number, got {value!r}")
    if kind is int and value != int(value):
        raise ValueError(f"history config `{where}.{key}` must be a whole number, got {value!r}")
    return kind(value)


def _leg(fund: str, position: int, raw: object, fred: dict[str, pd.Timestamp]) -> Leg:
    if not isinstance(raw, dict) or not {"fred", "duration"} <= raw.keys():
        raise ValueError(f"history config treasury {fund}: each leg needs fred and duration")
    unknown = sorted(str(k) for k in raw.keys() - _LEG_KEYS)
    if unknown:
        raise ValueError(f"history config treasury {fund}: unknown leg key(s) {unknown}")
    if str(raw["fred"]) not in fred:
        raise ValueError(f"history config treasury {fund}: {raw['fred']} is not in `fred`")
    duration = _num(raw, "duration", f"treasury.{fund}")
    if duration <= 0:
        raise ValueError(f"history config treasury {fund}: duration must be positive")
    start = _ts(raw["start"], f"{fund} start") if "start" in raw else None
    end = _ts(raw["end"], f"{fund} end") if "end" in raw else None
    if position == 0 and (start is not None or end is not None):
        raise ValueError(f"history config treasury {fund}: the base leg has no window")
    if position > 0 and (start is None or end is None or start > end):
        raise ValueError(f"history config treasury {fund}: a later leg needs a start <= end window")
    return Leg(str(raw["fred"]), duration, start, end)


def _treasury(raw: object, fred: dict[str, pd.Timestamp]) -> dict[str, tuple[Leg, ...]]:
    if not isinstance(raw, dict) or not raw:
        raise ValueError("history config `treasury` must be a non-empty mapping")
    out: dict[str, tuple[Leg, ...]] = {}
    for fund, legs in raw.items():
        if not isinstance(legs, list) or not legs:
            raise ValueError(f"history config treasury {fund}: legs must be a non-empty list")
        out[str(fund)] = tuple(_leg(str(fund), i, leg, fred) for i, leg in enumerate(legs))
    return out


def _source(doc: dict[str, object], what: str) -> Source:
    raw = _section(doc, what, _SOURCE_KEYS)
    columns = raw["columns"]
    if not isinstance(columns, dict) or not columns:
        raise ValueError(f"history config `{what}.columns` must be a non-empty mapping")
    return Source(
        str(raw["url"]),
        str(raw["sheet"]),
        int(_num(raw, "skiprows", what, int)),
        dict(columns),
        _ts(raw["max_first_date"], f"{what}.max_first_date"),
    )


def _positive_list(doc: dict[str, object], key: str, kind: type) -> tuple[float, ...]:
    raw = doc[key]
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"history config `{key}` must be a non-empty list")
    values = tuple(_num({key: v}, key, "list", kind) for v in raw)
    if any(v <= 0 for v in values):
        raise ValueError(f"history config `{key}` values must be positive")
    return values


def _portfolios(doc: dict[str, object]) -> tuple[str, ...]:
    raw = doc["portfolios"]
    if not isinstance(raw, list) or not raw or not all(isinstance(p, str) for p in raw):
        raise ValueError("history config `portfolios` must be a non-empty list of strings")
    if len(set(raw)) != len(raw):
        raise ValueError("history config `portfolios` must not repeat an id")
    return tuple(raw)


def load_history_config(path: str | Path) -> HistoryConfig:
    """Parse and validate `config/history.yaml`. Raises ValueError, naming the
    key, on malformed YAML, a wrong version, a missing or unknown key, a
    non-numeric value, a threshold outside (0, 1), rates not in (0, 1),
    non-positive horizons, a correlation bar outside (0, 1], a negative gap
    limit or lag, bad portfolio ids, or a malformed leg or source."""
    raw = Path(path).read_bytes()
    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"history config is not valid YAML ({exc})") from exc
    if not isinstance(doc, dict) or doc.get("version") != 1:
        raise ValueError("history config must be a mapping with `version: 1`")
    _check_keys(doc, _KEYS, "top level")
    episodes = _section(doc, "episodes", _EPISODE_KEYS)
    panel = _section(doc, "panel", _PANEL_KEYS)
    gold = _section(doc, "gold", _GOLD_KEYS)
    threshold = _num(episodes, "threshold", "episodes")
    if not 0 < threshold < 1:
        raise ValueError("history config threshold must be strictly between 0 and 1")
    horizon = int(_num(episodes, "horizon_years", "episodes", int))
    if horizon <= 0:
        raise ValueError("history config horizon_years must be positive")
    rates = _positive_list(doc, "withdrawal_rates", float)
    if any(r >= 1 for r in rates):
        raise ValueError("history config withdrawal_rates must be fractions below 1")
    min_corr = _num(doc, "min_correlation", "top level")
    if not 0 < min_corr <= 1:
        raise ValueError("history config min_correlation must be in (0, 1]")
    max_gap = int(_num(doc, "max_gap_days", "top level", int))
    if max_gap < 0:
        raise ValueError("history config max_gap_days must not be negative")
    lag = int(_num(doc, "yield_lag_business_days", "top level", int))
    if lag < 0:
        raise ValueError("history config yield_lag_business_days must not be negative")
    fred = _dates(doc["fred"], "fred")
    return HistoryConfig(
        index_ticker=str(episodes["index"]),
        threshold=threshold,
        episode_start=_ts(episodes["start"], "episodes.start"),
        horizon_years=horizon,
        panel_start=_ts(panel["start"], "panel.start"),
        lead_in_start=_ts(panel["lead_in_start"], "panel.lead_in_start"),
        portfolios=_portfolios(doc),
        rates=rates,
        income_years=tuple(int(v) for v in _positive_list(doc, "income_horizons_years", int)),
        min_correlation=min_corr,
        max_gap_days=max_gap,
        cache_dir=str(doc["cache_dir"]),
        download_start=str(doc["download_start"]),
        cpi_max_first_date=_ts(doc["cpi_max_first_date"], "cpi_max_first_date"),
        yahoo=_dates(doc["yahoo"], "yahoo"),
        fred=fred,
        yield_lag_days=lag,
        treasury=_treasury(doc["treasury"], fred),
        gold_futures=str(gold["futures"]),
        gold_fund=str(gold["fund"]),
        shiller=_source(doc, "shiller"),
        worldbank=_source(doc, "worldbank"),
        sha256=hashlib.sha256(raw).hexdigest(),
    )
