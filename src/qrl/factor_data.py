"""Date x ticker fundamentals / membership panels for the factor strategies
(Phase 4, milestone 3).

Strategy `fields` normally name price frames (`"close"`, ...). The factor
families additionally name the fields in `FACTOR_FIELDS`; `FactorData.panel`
resolves each to a frame aligned to a price index, exactly like a price frame:

    pit_member        bool    in the point-in-time top-N universe on that day
                              (`pit_universe.membership_mask`)
    fund_ni_ttm       float   NetIncomeLoss, trailing twelve months
    fund_opinc_ttm    float   OperatingIncomeLoss, trailing twelve months
    fund_assets       float   Assets (latest balance sheet)
    fund_assets_lag1y float   Assets one year before the latest balance sheet
    fund_shares       float   total shares, split-adjusted to today's basis, so
                              `fund_shares * close` is the market cap at t

Every value at date t uses only filings with `filed < t` (see
`qrl.fundamentals`). Hook: `qrl.search.SearchData.fields` resolves names outside
the OHLCV set through `default_provider().panel(...)`. Built panels are cached
as parquet under `data/cache/factor/` (gitignored), keyed by the inputs.

`assets_lag1y_panel` definition ("Assets one year earlier"): at date t let E be
the period end of the latest Assets balance sheet filed before t. The value is
the Assets for the period end closest to E minus one year (within +-45 days),
using the latest filing before t for that period end (so restatements count
once public); NaN if no such period end is known. This is not a 252-day lag of
the `fund_assets` panel.

Share counts follow `pit_universe` (dei / us-gaap / weighted-average chain,
`CIK_PREDECESSORS`, split adjustment, volume scale check). `CLASS_EQUIVALENTS`
tickers (BRK-B) use the Class A-equivalent count times `CLASS_PER_PRICE_TICKER`
so that count x the ticker's own close approximates the sizing used for the
universe (A-equivalent count x BRK-A close).
"""

from __future__ import annotations

import functools
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from qrl import data
from qrl import fundamentals as fd
from qrl import pit_universe as pu

FACTOR_CACHE_DIR = data.CACHE_DIR / "factor"
FUND_FIELDS = (
    "fund_ni_ttm",
    "fund_opinc_ttm",
    "fund_assets",
    "fund_assets_lag1y",
    "fund_shares",
)
FACTOR_FIELDS = ("pit_member", *FUND_FIELDS)
ASSETS_LAG_TOLERANCE_DAYS = 45
# Class-B shares per class of the price ticker used by `pit_universe.CLASS_EQUIVALENTS`
# (1 Berkshire Class A = 1,500 Class B).
CLASS_PER_PRICE_TICKER: dict[str, float] = {"BRK-B": 1500.0}


def factor_universe(membership: pd.DataFrame) -> list[str]:
    """Every ticker that was ever a member: the `tickers` param of the factor families."""
    return sorted(set(membership["ticker"]))


# --------------------------------------------------------------------------- panels


def assets_lag1y_panel(
    facts: pd.DataFrame,
    dates: pd.Index,
    tickers: Sequence[str],
    staleness_days: int = fd.STALENESS_DAYS,
    tolerance_days: int = ASSETS_LAG_TOLERANCE_DAYS,
) -> pd.DataFrame:
    """dates x tickers Assets one year before the latest known balance sheet (see the
    module docstring for the exact definition). Staleness is measured from the latest
    period end E, as in `fd.pit_panel`."""
    dates = pd.DatetimeIndex(dates)
    sub = facts[facts["concept"] == "Assets"]
    out = pd.DataFrame(np.nan, index=dates, columns=list(tickers))
    tol = pd.Timedelta(days=tolerance_days)
    for t in tickers:
        g = sub[sub["ticker"] == t].dropna(subset=["val", "end", "filed"])
        if g.empty:
            continue
        g = g.sort_values(["filed", "end"], kind="stable")
        known: dict[pd.Timestamp, float] = {}
        f_out: list = []
        e_out: list = []
        v_out: list = []
        for filed, grp in g.groupby("filed", sort=True):
            for end, val in zip(grp["end"], grp["val"], strict=True):
                known[end] = float(val)
            latest = max(known)
            target = latest - pd.DateOffset(years=1)
            near = sorted(
                (abs(e - target), e) for e in known if abs(e - target) <= tol and e < latest
            )
            f_out.append(filed)
            e_out.append(latest)
            v_out.append(known[near[0][1]] if near else np.nan)
        out[t] = fd._map_to_dates(
            np.array(f_out, dtype="datetime64[ns]"),
            np.array(e_out, dtype="datetime64[ns]"),
            np.array(v_out, dtype=float),
            dates,
            staleness_days,
        )
    return out


def shares_panel(
    facts: pd.DataFrame,
    dates: pd.Index,
    tickers: Sequence[str],
    splits: Mapping[str, pd.Series] | None = None,
    volume: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """dates x tickers total shares known at t (filed < t), split-adjusted so that
    `shares * close` is the market cap; scale-checked against `volume` when given."""
    idx = pd.DatetimeIndex(dates)
    plain = [t for t in tickers if t not in pu.CLASS_EQUIVALENTS]
    vol = None
    if volume is not None:
        vol = (
            volume.rolling(pu.VOLUME_WINDOW, min_periods=pu.MIN_VOLUME_BARS)
            .median()
            .ffill(limit=pu.PRICE_FFILL_LIMIT)
            .reindex(index=idx, columns=plain)
        )
    out = pd.DataFrame(np.nan, index=idx, columns=list(tickers))
    if plain:
        shares, _, filed, _ = fd.total_shares_sourced_panels(facts, idx, plain)
        eff = pu.split_adjust_shares(shares, filed, splits or {})
        out[plain] = eff if vol is None else pu.fix_share_scale(eff, vol)
    for t in tickers:
        if t in pu.CLASS_EQUIVALENTS:
            own = facts[facts["concept"].isin(pu.CLASS_EQUIVALENTS[t]["concepts"])]
            a_eq = fd.total_shares_panel(own, idx, [t], pu.CLASS_EQ_STALENESS_DAYS)[t]
            out[t] = a_eq * CLASS_PER_PRICE_TICKER.get(t, 1.0)
    return out


def build_panel(
    name: str,
    facts: pd.DataFrame,
    dates: pd.Index,
    tickers: Sequence[str],
    splits: Mapping[str, pd.Series] | None = None,
    volume: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """One fundamentals panel (`FUND_FIELDS`), uncached, dates x tickers."""
    if name == "fund_ni_ttm":
        return fd.ttm_panel(facts, "NetIncomeLoss", dates, tickers)
    if name == "fund_opinc_ttm":
        return fd.ttm_panel(facts, "OperatingIncomeLoss", dates, tickers)
    if name == "fund_assets":
        return fd.pit_panel(facts, "Assets", dates, tickers)
    if name == "fund_assets_lag1y":
        return assets_lag1y_panel(facts, dates, tickers)
    if name == "fund_shares":
        return shares_panel(facts, dates, tickers, splits, volume)
    raise KeyError(f"Unknown factor field: {name!r}")


# --------------------------------------------------------------------------- facts loading


def _read_cached_payload(cik: int, sec_dir: Path) -> dict | None:
    path = sec_dir / "facts" / f"CIK{cik:010d}.json"
    if not path.exists():
        return None
    payload: dict = json.loads(path.read_text())
    return payload


def payload_files_fingerprint(
    tickers: Sequence[str],
    pool_path: Path | None = None,
    sec_dir: Path | None = None,
) -> str:
    """Hash of (ticker, CIK, file size, mtime) of every cached payload `load_factor_facts`
    would read, without parsing any of them."""
    pool = pd.read_csv(pool_path or pu.PIT_CACHE_DIR / "pool.csv")
    ciks = dict(zip(pool["ticker"], pool["cik"].astype(int), strict=True))
    sec = sec_dir or fd.SEC_CACHE_DIR
    parts: list[str] = []
    for t in tickers:
        for cik in [ciks.get(t), *pu.CIK_PREDECESSORS.get(t, [])]:
            path = None if cik is None else sec / "facts" / f"CIK{cik:010d}.json"
            if path is not None and path.exists():
                st = path.stat()
                parts.append(f"{t}:{cik}:{st.st_size}:{st.st_mtime_ns}")
    return _fingerprint(*parts)


def load_factor_facts(
    tickers: Sequence[str],
    pool_path: Path | None = None,
    sec_dir: Path | None = None,
) -> pd.DataFrame:
    """Long facts table for `tickers` from the local SEC cache only (never the network):
    ticker -> CIK from the PIT build's `pool.csv`, plus `CIK_PREDECESSORS` histories.
    Tickers with no cached payload are simply absent (their panels are NaN)."""
    pool = pd.read_csv(pool_path or pu.PIT_CACHE_DIR / "pool.csv")
    ciks = dict(zip(pool["ticker"], pool["cik"].astype(int), strict=True))
    sec = sec_dir or fd.SEC_CACHE_DIR
    frames = []
    for t in tickers:
        payload = _read_cached_payload(ciks[t], sec) if t in ciks else None
        if payload is None:
            continue
        facts = fd.parse_companyfacts(t, payload, pu.FEATURE_CONCEPTS)
        for old_cik in pu.CIK_PREDECESSORS.get(t, []):
            old = _read_cached_payload(old_cik, sec)
            if old is not None:
                old_facts = fd.parse_companyfacts(t, old, pu.FEATURE_CONCEPTS)
                facts = pu.merge_predecessor_facts(facts, old_facts)
        frames.append(facts)
    if not frames:
        return pd.DataFrame(columns=fd.FACT_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def load_cached_splits(tickers: Sequence[str], cache_dir: Path | None = None) -> dict:
    """Splits from the PIT build's CSV cache (no network); a ticker without a file has none,
    as in the build (splits were only fetched for the larger candidates)."""
    root = (cache_dir or pu.PIT_CACHE_DIR) / "splits"
    out: dict[str, pd.Series] = {}
    for t in tickers:
        path = root / f"{t}.csv"
        if path.exists():
            df = pd.read_csv(path, parse_dates=["date"])
            out[t] = pd.Series(df["ratio"].to_numpy(float), index=pd.DatetimeIndex(df["date"]))
    return out


# --------------------------------------------------------------------------- provider


def _fingerprint(*parts: object) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:16]


class FactorData:
    """Builds and caches the `FACTOR_FIELDS` panels from a facts table and a membership table.

    `facts` is built lazily (`facts_loader`) because reading hundreds of cached SEC
    payloads is slow and only needed on a cache miss.
    """

    def __init__(
        self,
        membership: pd.DataFrame,
        facts: pd.DataFrame | None = None,
        splits: Mapping[str, pd.Series] | None = None,
        cache_dir: Path | None = FACTOR_CACHE_DIR,
    ) -> None:
        self.membership = membership
        self._facts = facts
        self._splits = splits
        self.cache_dir = cache_dir
        self._memo: dict[str, pd.DataFrame] = {}
        self._facts_key: str | None = None

    @property
    def facts(self) -> pd.DataFrame:
        if self._facts is None:
            self._facts = load_factor_facts(factor_universe(self.membership))
        return self._facts

    def _splits_for(self) -> Mapping[str, pd.Series]:
        if self._splits is None:
            self._splits = load_cached_splits(factor_universe(self.membership))
        return self._splits

    def _facts_fingerprint(self) -> str:
        """Identity of the facts behind the panels. Facts loaded lazily from the SEC cache
        are fingerprinted by their payload files (size + mtime), so a cache hit never
        parses hundreds of JSON files; a facts table passed in is hashed by content."""
        if self._facts_key is None:
            if self._facts is None:
                self._facts_key = payload_files_fingerprint(factor_universe(self.membership))
            else:
                cols = self._facts[["ticker", "concept", "end", "filed", "val"]]
                h = int(pd.util.hash_pandas_object(cols, index=False).sum())
                self._facts_key = _fingerprint(len(cols), h)
        return self._facts_key

    def _key(
        self,
        name: str,
        dates: pd.DatetimeIndex,
        tickers: Sequence[str],
        volume: pd.DataFrame | None,
    ) -> str:
        vol = "" if volume is None else float(np.nansum(volume.to_numpy(dtype=float)))
        return _fingerprint(
            name, dates[0], dates[-1], len(dates), ",".join(tickers), vol, self._facts_fingerprint()
        )

    def panel(
        self,
        name: str,
        dates: pd.Index,
        tickers: Sequence[str],
        volume: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """`name` (one of `FACTOR_FIELDS`) as a dates x tickers frame aligned to `dates`.
        `volume` (daily, same index convention as prices) enables the share-count scale
        check for `fund_shares`; it is ignored by every other field."""
        idx = pd.DatetimeIndex(dates)
        cols = list(tickers)
        if name == "pit_member":
            return pu.membership_mask(self.membership, idx, cols)
        if name not in FUND_FIELDS:
            raise KeyError(f"Unknown factor field: {name!r}")
        if name != "fund_shares":
            volume = None
        elif volume is not None:
            volume = volume.reindex(index=idx)
        key = self._key(name, idx, cols, volume)
        if key in self._memo:
            return self._memo[key]
        path = None if self.cache_dir is None else self.cache_dir / f"{name}_{key}.parquet"
        if path is not None and path.exists():
            out = pd.read_parquet(path)
        else:
            splits = self._splits_for() if name == "fund_shares" else None
            out = build_panel(name, self.facts, idx, cols, splits, volume)
            if path is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                out.to_parquet(path)
        out = out.reindex(index=idx, columns=cols)
        self._memo[key] = out
        return out


@functools.cache
def default_provider() -> FactorData:
    """Provider over the checked-in membership (`config/universe_pit.yaml`, sha-verified),
    the local SEC cache, and the PIT build's split cache."""
    _, membership = pu.load_pit_universe()
    return FactorData(membership)
