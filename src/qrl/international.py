"""International final test (spec: docs/methodology/international-test.md).

Pure functions apart from `load_international_config` reading its file:
config, rule translation, defensive-leg proxies, the price panel, window
scoring, per-market and per-set verdicts, data freezing and the report.
Callers (`scripts/international.py`) download prices and FRED yields (Treasury
and DTB3) and pass them in. The engine and metrics are used unchanged. Nothing here touches the
US holdout: `qrl.periods` is not used, and foreign markets are sliced by the
config's own windows.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml


@dataclass(frozen=True)
class MarketSet:
    name: str
    markets: tuple[str, ...]
    min_pass: int


@dataclass(frozen=True)
class InternationalConfig:
    sets: tuple[MarketSet, ...]
    windows: tuple[tuple[pd.Timestamp, pd.Timestamp | None], ...]
    excluded: tuple[pd.Timestamp, pd.Timestamp]
    download_start: str
    min_scored_days: int
    sharpe_margin: float
    cagr_tolerance: float
    defensive: frozenset[str]
    covered: frozenset[str]  # covered strategies (REGISTRY names)
    treasury: dict[str, tuple[str, float]]  # fund -> (FRED id, duration)
    cash_fred: str  # FRED id of the cash series (DTB3)
    yield_lag_days: int
    gold_ticker: str
    gold_fund: str
    gold_check: tuple[pd.Timestamp, pd.Timestamp]
    gold_min_correlation: float

    @property
    def set_names(self) -> list[str]:
        return [s.name for s in self.sets]

    def market_set(self, name: str) -> MarketSet:
        for market_set in self.sets:
            if market_set.name == name:
                return market_set
        raise ValueError(f"unknown market set {name!r}; known: {self.set_names}")

    @property
    def funds(self) -> list[str]:
        """Defensive funds with a price history. CASH has no fund: `build_panel`
        prices it from DTB3 over the whole backtest."""
        return sorted(t for t in self.defensive if t != "CASH")

    @property
    def fred_ids(self) -> list[str]:
        """Every FRED series the test downloads: Treasury yields and DTB3."""
        return sorted({fred for fred, _ in self.treasury.values()} | {self.cash_fred})


def _ts(value: object) -> pd.Timestamp:
    return pd.Timestamp(str(value))


def _validate(cfg: InternationalConfig) -> None:
    names = cfg.set_names
    if not names or len(set(names)) != len(names):
        raise ValueError("market sets must be non-empty with unique names")
    seen: set[str] = set()
    for market_set in cfg.sets:
        if not 1 <= market_set.min_pass <= len(market_set.markets):
            raise ValueError(
                f"{market_set.name}: min_pass must be between 1 and {len(market_set.markets)}"
            )
        repeated = seen & set(market_set.markets)
        if repeated:
            raise ValueError(f"{market_set.name} repeats markets {sorted(repeated)}")
        if set(market_set.markets) & cfg.defensive:
            raise ValueError(f"{market_set.name} lists a defensive leg as a market")
        seen |= set(market_set.markets)
    low, high = cfg.excluded
    for start, end in cfg.windows:
        stop = pd.Timestamp.max if end is None else end
        if start <= high and stop >= low:
            raise ValueError("a scoring window overlaps the excluded years")
    if not cfg.windows or cfg.windows[-1][1] is not None:
        raise ValueError("the last window must run to the frozen data end (end: null)")
    if not {*cfg.treasury, cfg.gold_fund} <= cfg.defensive:
        raise ValueError("every proxied fund must be on the defensive list")


def load_international_config(path: str | Path) -> tuple[InternationalConfig, str]:
    """Load `config/international.yaml`; return it with its full sha256."""
    raw = Path(path).read_bytes()
    doc = yaml.safe_load(raw)
    proxies = doc["proxies"]
    gold = proxies["gold"]
    cfg = InternationalConfig(
        sets=tuple(
            MarketSet(str(s["name"]), tuple(str(m) for m in s["markets"]), int(s["min_pass"]))
            for s in doc["sets"]
        ),
        windows=tuple(
            (_ts(w["start"]), None if w["end"] is None else _ts(w["end"])) for w in doc["windows"]
        ),
        excluded=(_ts(doc["excluded"]["start"]), _ts(doc["excluded"]["end"])),
        download_start=str(doc["download_start"]),
        min_scored_days=int(doc["min_scored_days"]),
        sharpe_margin=float(doc["thresholds"]["sharpe_margin"]),
        cagr_tolerance=float(doc["thresholds"]["cagr_tolerance"]),
        defensive=frozenset(str(t) for t in doc["defensive"]),
        covered=frozenset(str(f) for f in doc["covered_strategies"]),
        treasury={
            str(fund): (str(v["fred"]), float(v["duration"]))
            for fund, v in proxies["treasury"].items()
        },
        cash_fred=str(proxies["cash"]["fred"]),
        yield_lag_days=int(proxies["yield_lag_business_days"]),
        gold_ticker=str(gold["ticker"]),
        gold_fund=str(gold["fund"]),
        gold_check=(_ts(gold["check_start"]), _ts(gold["check_end"])),
        gold_min_correlation=float(gold["min_correlation"]),
    )
    _validate(cfg)
    return cfg, hashlib.sha256(raw).hexdigest()
