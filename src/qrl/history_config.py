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


def _leg(fund: str, position: int, raw: object) -> Leg:
    if not isinstance(raw, dict) or not {"fred", "duration"} <= raw.keys():
        raise ValueError(f"history config treasury {fund}: each leg needs fred and duration")
    duration = float(raw["duration"])
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError(f"history config treasury {fund}: duration must be positive")
    start = _ts(raw["start"], f"{fund} start") if "start" in raw else None
    end = _ts(raw["end"], f"{fund} end") if "end" in raw else None
    if position == 0 and (start or end):
        raise ValueError(f"history config treasury {fund}: the base leg has no window")
    if position > 0 and (start is None or end is None or start > end):
        raise ValueError(f"history config treasury {fund}: a later leg needs a start <= end window")
    return Leg(str(raw["fred"]), duration, start, end)


def _treasury(raw: object) -> dict[str, tuple[Leg, ...]]:
    if not isinstance(raw, dict) or not raw:
        raise ValueError("history config `treasury` must be a non-empty mapping")
    out = {}
    for fund, legs in raw.items():
        if not isinstance(legs, list) or not legs:
            raise ValueError(f"history config treasury {fund}: legs must be a non-empty list")
        out[str(fund)] = tuple(_leg(str(fund), i, leg) for i, leg in enumerate(legs))
    return out


def _source(raw: object, what: str) -> Source:
    if not isinstance(raw, dict) or not raw.keys() >= _SOURCE_KEYS:
        raise ValueError(f"history config `{what}` needs {sorted(_SOURCE_KEYS)}")
    columns = raw["columns"]
    if not isinstance(columns, dict) or not columns:
        raise ValueError(f"history config `{what}.columns` must be a non-empty mapping")
    return Source(
        str(raw["url"]),
        str(raw["sheet"]),
        int(raw["skiprows"]),
        dict(columns),
        _ts(raw["max_first_date"], f"{what}.max_first_date"),
    )


def _positive_list(doc: dict, key: str, kind: type) -> tuple:
    raw = doc[key]
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"history config `{key}` must be a non-empty list")
    values = tuple(kind(v) for v in raw)
    if any(v <= 0 for v in values):
        raise ValueError(f"history config `{key}` values must be positive")
    return values


def load_history_config(path: str | Path) -> HistoryConfig:
    """Parse and validate `config/history.yaml`. Raises ValueError on malformed
    YAML, a wrong version, a missing key, a threshold outside (0, 1), rates not
    in (0, 1), non-positive horizons, a correlation bar outside (0, 1], a
    negative gap limit, or a malformed leg or source."""
    raw = Path(path).read_bytes()
    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"history config is not valid YAML ({exc})") from exc
    if not isinstance(doc, dict) or doc.get("version") != 1:
        raise ValueError("history config must be a mapping with `version: 1`")
    missing = sorted(_KEYS - doc.keys())
    if missing:
        raise ValueError(f"history config is missing key(s) {missing}")
    episodes, panel = doc["episodes"], doc["panel"]
    threshold = float(episodes["threshold"])
    if not 0 < threshold < 1:
        raise ValueError("history config threshold must be strictly between 0 and 1")
    rates = _positive_list(doc, "withdrawal_rates", float)
    if any(r >= 1 for r in rates):
        raise ValueError("history config withdrawal_rates must be fractions below 1")
    min_corr = float(doc["min_correlation"])
    if not 0 < min_corr <= 1:
        raise ValueError("history config min_correlation must be in (0, 1]")
    max_gap = int(doc["max_gap_days"])
    if max_gap < 0:
        raise ValueError("history config max_gap_days must not be negative")
    return HistoryConfig(
        index_ticker=str(episodes["index"]),
        threshold=threshold,
        episode_start=_ts(episodes["start"], "episodes.start"),
        horizon_years=int(episodes["horizon_years"]),
        panel_start=_ts(panel["start"], "panel.start"),
        lead_in_start=_ts(panel["lead_in_start"], "panel.lead_in_start"),
        portfolios=tuple(str(p) for p in doc["portfolios"]),
        rates=rates,
        income_years=_positive_list(doc, "income_horizons_years", int),
        min_correlation=min_corr,
        max_gap_days=max_gap,
        cache_dir=str(doc["cache_dir"]),
        download_start=str(doc["download_start"]),
        cpi_max_first_date=_ts(doc["cpi_max_first_date"], "cpi_max_first_date"),
        yahoo=_dates(doc["yahoo"], "yahoo"),
        fred=_dates(doc["fred"], "fred"),
        yield_lag_days=int(doc["yield_lag_business_days"]),
        treasury=_treasury(doc["treasury"]),
        gold_futures=str(doc["gold"]["futures"]),
        gold_fund=str(doc["gold"]["fund"]),
        shiller=_source(doc["shiller"], "shiller"),
        worldbank=_source(doc["worldbank"], "worldbank"),
        sha256=hashlib.sha256(raw).hexdigest(),
    )
