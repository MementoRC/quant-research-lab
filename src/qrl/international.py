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

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .engine import run_backtest
from .macro import align_to_trading_days, lag_to_availability
from .metrics import TRADING_DAYS, compute_metrics
from .strategies import REGISTRY
from .strategies.buy_and_hold import buy_and_hold


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


_LEG_PARAMS = ("risk_on", "risk_off", "signal")


class NotCovered(ValueError):  # noqa: N818 - name fixed by the plan and spec
    """The rule cannot be translated mechanically (spec: Scope, Translation)."""


@dataclass(frozen=True)
class Rule:
    family: str  # REGISTRY name of the strategy
    params: dict

    @property
    def sha256(self) -> str:
        payload = json.dumps(
            {"family": self.family, "params": self.params}, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def tickers(self) -> list[str]:
        """Every ticker named in risk_on, risk_off (string or dict keys) and signal."""
        found: list[str] = []
        for key in _LEG_PARAMS:
            value = self.params.get(key)
            if isinstance(value, str):
                found.append(value)
            elif isinstance(value, dict):
                found.extend(str(t) for t in value)
        return found


def derive_equity_leg(rule: Rule, cfg: InternationalConfig) -> str:
    """The rule's single non-defensive ticker. Refuses (NotCovered) a strategy
    that is not covered, and a rule with zero or more than one such ticker."""
    if rule.family not in cfg.covered:
        raise NotCovered(
            f"strategy {rule.family!r} is not covered (covered: {sorted(cfg.covered)})"
        )
    others = sorted({t for t in rule.tickers() if t not in cfg.defensive})
    if len(others) != 1:
        raise NotCovered(
            f"the rule's non-defensive tickers are {others}; exactly one equity leg is required"
        )
    return others[0]


def _swap(value: object, old: str, new: str) -> object:
    if isinstance(value, str):
        return new if value == old else value
    if isinstance(value, dict):
        return {_swap(k, old, new): _swap(v, old, new) for k, v in value.items()}
    if isinstance(value, list):
        return [_swap(v, old, new) for v in value]
    return value


def translate(rule: Rule, equity_leg: str, market: str) -> Rule:
    """The same rule with every occurrence of `equity_leg` replaced by `market`
    (risk_on, risk_off and signal alike). No other parameter changes. Refuses a
    rule whose equity leg is only a default."""
    params = _swap(copy.deepcopy(rule.params), equity_leg, market)
    if not isinstance(params, dict):
        raise NotCovered("the rule's params must be a mapping")
    out = Rule(rule.family, params)
    tickers = out.tickers()
    if equity_leg in tickers or market not in tickers:
        raise NotCovered(
            f"{equity_leg} is not named in the rule's params (a default?); it cannot be swapped"
        )
    return out


def holds_gold(rule: Rule, cfg: InternationalConfig) -> bool:
    return cfg.gold_fund in rule.tickers()


CASH = "CASH"  # the strategies' cash sentinel; here a priced column


def lagged_close(series: pd.Series, lag_days: int, index: pd.DatetimeIndex) -> pd.Series:
    """`series` moved `lag_days` business days later and forward-filled onto `index`."""
    avail = lag_to_availability(series.dropna(), {"unit": "business_days", "value": lag_days})
    return align_to_trading_days(avail, index)


def yield_proxy_close(
    yields_pct: pd.Series, duration: float, lag_days: int, index: pd.DatetimeIndex
) -> pd.Series:
    """Total-return price index from a FRED constant-maturity yield in percent:
    daily return = previous yield / 252 - duration x yield change, each yield
    lagged `lag_days` business days (FRED publishes H.15 rates the next day)."""
    y = lagged_close(yields_pct / 100.0, lag_days, index)
    returns = (y.shift(1) / TRADING_DAYS - duration * y.diff()).dropna()
    return (1.0 + returns).cumprod().reindex(index)


def splice(proxy: pd.Series, fund: pd.Series) -> pd.Series:
    """The fund from its first close on; before it, the proxy scaled to meet
    that close, so the joined price has no jump."""
    real = fund.dropna()
    if real.empty:
        return proxy.copy()
    first = real.index[0]
    before = proxy.loc[:first].dropna()
    if before.empty or before.index[-1] != first:
        return real
    scaled = before * (real.iloc[0] / before.iloc[-1])
    return pd.concat([scaled.iloc[:-1], real]).sort_index()


def gold_correlation(
    gold: pd.Series, fund: pd.Series, start: pd.Timestamp, end: pd.Timestamp
) -> float | None:
    """Daily-return correlation of the gold proxy against the gold fund over
    [start, end]: a data check only. None with fewer than 20 common days."""
    a = gold.loc[start:end].pct_change(fill_method=None)
    b = fund.loc[start:end].pct_change(fill_method=None)
    both = pd.concat([a, b], axis=1, join="inner").dropna()
    if len(both) < 20:
        return None
    return float(both.iloc[:, 0].corr(both.iloc[:, 1]))


def build_panel(
    fund_open: pd.DataFrame,
    fund_close: pd.DataFrame,
    yields: dict[str, pd.Series],
    gold: pd.Series,
    cfg: InternationalConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Open/close for every market and defensive fund on `fund_close`'s trading
    days, with proxies spliced in before each fund's first date. A proxy day's
    open is the previous close (no overnight gap). Yields (Treasury and DTB3)
    are lagged `yield_lag_days` business days; the GC=F gold proxy is not (a
    futures settlement is known at the close). A priced `CASH` column is built
    from DTB3 over the whole backtest (duration 0: daily return = previous
    yield / 252). The raw gold series is kept as its own close column for the
    gold check."""
    index = fund_close.index
    close = fund_close.copy()
    open_ = fund_open.reindex(index=index, columns=fund_close.columns).copy()
    proxies = {
        fund: yield_proxy_close(yields[fred], duration, cfg.yield_lag_days, index)
        for fund, (fred, duration) in cfg.treasury.items()
    }
    proxies[cfg.gold_fund] = gold.reindex(index)
    for fund, proxy in proxies.items():
        first = fund_close[fund].first_valid_index()
        close[fund] = splice(proxy, fund_close[fund]).reindex(index)
        proxy_open = close[fund].shift(1)
        open_[fund] = proxy_open if first is None else proxy_open.where(index < first, open_[fund])
    close[cfg.gold_ticker] = gold.reindex(index)
    open_[cfg.gold_ticker] = float("nan")
    close[CASH] = yield_proxy_close(yields[cfg.cash_fred], 0.0, cfg.yield_lag_days, index)
    open_[CASH] = close[CASH].shift(1)
    return open_, close


def with_cash(weights: pd.DataFrame) -> pd.DataFrame:
    """The strategy's weights plus a `CASH` column holding whatever is left
    uninvested (1 - row sum, floored at 0): weights summing below 1, or
    `core_trend`'s `risk_off: "CASH"` (the full weight when off). Warm-up rows
    stay NaN. Done here, not in the engine, which still pays 0% on uninvested
    weight; after this step there is none."""
    base = weights.drop(columns=[CASH], errors="ignore")
    out = base.copy()
    out[CASH] = (1.0 - base.sum(axis=1, skipna=False)).clip(lower=0.0)
    return out


def _window_stop(end: pd.Timestamp | None, data_end: pd.Timestamp) -> pd.Timestamp:
    return data_end if end is None else min(end, data_end)


def scoring_index(
    index: pd.DatetimeIndex,
    windows: tuple[tuple[pd.Timestamp, pd.Timestamp | None], ...],
    data_end: pd.Timestamp,
) -> pd.DatetimeIndex:
    """The dates of `index` inside any scoring window. Nothing else is scored."""
    keep = np.zeros(len(index), dtype=bool)
    for start, end in windows:
        keep |= (index >= start) & (index <= _window_stop(end, data_end))
    return index[keep]


def market_checks(rule_m: dict, bh_m: dict, cfg: InternationalConfig) -> dict[str, bool]:
    """The core thresholds, one set for every covered rule kind."""
    return {
        "sharpe": rule_m["sharpe"] >= bh_m["sharpe"] + cfg.sharpe_margin,
        "max_drawdown": rule_m["max_drawdown"] <= bh_m["max_drawdown"],
        "cagr": rule_m["cagr"] >= bh_m["cagr"] - cfg.cagr_tolerance,
    }


def evaluate_market(
    open_: pd.DataFrame,
    close: pd.DataFrame,
    rule: Rule,
    market: str,
    cfg: InternationalConfig,
    data_end: pd.Timestamp,
    *,
    late_only: bool = False,
) -> dict:
    """Backtest the translated rule (uninvested weight assigned to the priced
    `CASH` column) and buy-and-hold of `market` on the continuous series
    (engine default costs), then score both on the same joined window dates.
    Scoring starts once the rule's lookbacks are filled (the engine's first
    execution day)."""
    windows = cfg.windows[-1:] if late_only else cfg.windows
    empty = {
        "market": market,
        "days": 0,
        "enough_data": False,
        "passed": False,
        "sharpe_gain": None,
        "checks": {},
        "rule": {},
        "buy_and_hold": {},
        "windows": [],
        "late_only": late_only,
    }
    try:
        weights = with_cash(REGISTRY[rule.family].weights(close, **rule.params))
        rule_bt = run_backtest(open_, close, weights)
        bh_bt = run_backtest(open_, close, buy_and_hold(close, market))
    except ValueError as exc:  # no usable data for this market: it does not pass
        return {**empty, "error": str(exc)}
    dates = scoring_index(rule_bt.returns.index, windows, data_end).intersection(
        bh_bt.returns.index
    )
    rule_r = rule_bt.returns.reindex(dates)
    bh_r = bh_bt.returns.reindex(dates)
    rule_m = compute_metrics(rule_r, rule_bt.turnover, rule_bt.executed)
    bh_m = compute_metrics(bh_r)
    enough = len(dates) >= cfg.min_scored_days
    checks = market_checks(rule_m, bh_m, cfg) if enough else {}
    per_window = []
    for start, end in windows:
        stop = _window_stop(end, data_end)
        per_window.append(
            {
                "start": str(start.date()),
                "end": str(stop.date()),
                "days": int(((dates >= start) & (dates <= stop)).sum()),
                "rule": compute_metrics(rule_r.loc[start:stop]),
                "buy_and_hold": compute_metrics(bh_r.loc[start:stop]),
            }
        )
    return {
        **empty,
        "days": len(dates),
        "enough_data": enough,
        "passed": bool(enough and all(checks.values())),
        "sharpe_gain": rule_m["sharpe"] - bh_m["sharpe"] if enough else None,
        "checks": checks,
        "rule": rule_m,
        "buy_and_hold": bh_m,
        "windows": per_window,
    }


def set_verdict(results: list[dict], market_set: MarketSet) -> dict:
    """Count of passed markets AND a positive average Sharpe gain over the
    markets with enough data. A market below the minimum counts as not passed;
    the denominator stays the set size."""
    count = sum(1 for r in results if r["passed"])
    gains = [r["sharpe_gain"] for r in results if r["enough_data"]]
    average = sum(gains) / len(gains) if gains else None
    return {
        "set": market_set.name,
        "passed_markets": count,
        "markets": len(results),
        "required": market_set.min_pass,
        "average_sharpe_gain": average,
        "passed": bool(count >= market_set.min_pass and average is not None and average > 0),
    }
