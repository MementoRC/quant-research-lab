"""Point-in-time size-ranked US stock universe (Phase 4, milestone 2).

An ADDITION beside `config/universe.yaml` / `qrl.universe`, which are unchanged.
For each month-end from 2009 the top-N companies by market cap *as known then*
(total shares from filings with filed < t, times the close at t) form the
membership for the following month.

Survivors only (owner decision: no delisted companies): the candidate pool is
today's NYSE/Nasdaq listings, so the list stays `survivorship_biased: true`.

Pool rules
- SEC `company_tickers_exchange.json`, NYSE and Nasdaq only.
- One ticker per CIK (multi-class companies such as GOOGL/GOOG or BRK-A/BRK-B):
  the class with the highest median dollar volume over the last ~year on Yahoo.
- Companies without us-gaap `Assets` facts (foreign/IFRS filers, funds) are out.
- Current market cap (latest total shares x latest close) >= `min_cap`. The
  default $2B is deliberately loose, so firms that were big in 2009-2018 but
  shrank since stay in the pool.

Approximation: Yahoo closes are dividend- and split-adjusted. Shares are
multiplied by every split after the date they were filed, which makes
`shares x adjusted close` equal the true market cap up to the dividend
adjustment (a few percent per year of dividends compounded back from today).
"""

from __future__ import annotations

import hashlib
import json
import time
import warnings
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from qrl import data
from qrl import fundamentals as fd

ROOT = Path(__file__).resolve().parents[2]
UNIVERSE_PIT_PATH = ROOT / "config" / "universe_pit.yaml"
MEMBERSHIP_PATH = ROOT / "config" / "universes" / "us_large_cap_pit.csv"
PIT_CACHE_DIR = data.CACHE_DIR / "pit"
EXCHANGES = frozenset({"NYSE", "Nasdaq"})
DEFAULT_TOP_N = 300
DEFAULT_MIN_CAP = 2_000_000_000.0
FIRST_MONTH = pd.Timestamp("2009-01-01")
MEMBERSHIP_COLUMNS = ["month_end", "ticker", "market_cap", "rank", "source"]
FEATURE_COLUMNS = [
    "month_end",
    "ticker",
    "has_price",
    "shares",
    "shares_source",
    "market_cap",
    "ni_ttm",
    "gp_ttm",
    "gp_derivable",
    "op_inc_ttm",
    "assets",
    "assets_1y",
    "ytd_only",
]
SCREEN_CONCEPTS: dict[str, Iterable[str]] = {
    "us-gaap": ("Assets", fd.GAAP_SHARES, fd.WA_SHARES),
    "dei": (fd.DEI_SHARES,),
}
COST_CONCEPTS = ("CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold")
FEATURE_CONCEPTS: dict[str, Iterable[str]] = {
    "us-gaap": (
        "NetIncomeLoss",
        "GrossProfit",
        "OperatingIncomeLoss",
        "Assets",
        fd.GAAP_SHARES,
        fd.WA_SHARES,
        *fd.REVENUE_CONCEPTS,
        *COST_CONCEPTS,
    ),
    "dei": (fd.DEI_SHARES,),
}
# Share classes whose economic size is not (class-B shares x class-B price). Berkshire
# reports its share counts as Class A equivalents (1 Class A = 1,500 Class B) and has no
# companyfacts share count after 2015-09, so BRK-B's market cap is
# (Class A-equivalent weighted-average basic count) x (BRK-A close). The member stays BRK-B
# (the more liquid class). Rules for these tickers: only the listed `concepts` supply shares
# (the dei cover count is Class A only, a different basis); the last count is carried
# forward without a staleness limit (A-equivalents fall only ~1%/yr through buybacks, so the
# carried count overstates a late-year cap by at most ~10-15%); prices, splits and the
# volume-sanity check are skipped for the B class (BRK-A has no splits and thin volume).
# Verified: BRK-B (CIK 1067983) WeightedAverageNumberOfSharesOutstandingBasic is ~1.6 million
# (Class A equivalents) from 2007-12 to 2015-09; no share-count concept exists after that.
CLASS_EQUIVALENTS: dict[str, dict] = {
    "BRK-B": {"price_ticker": "BRK-A", "concepts": [fd.WA_SHARES]},
}
CLASS_EQ_SOURCE = "class-eq"
CLASS_EQ_STALENESS_DAYS = 10**6

# Companies whose SEC history sits under an older CIK than the one SEC lists today
# (ticker -> predecessor CIKs). Predecessor facts are used only before the successor's
# first filing. Each entry was checked against https://data.sec.gov/submissions/CIK<cik>.json
# (entity name, formerNames) and the cached companyfacts (share counts under the old CIK).
CIK_PREDECESSORS: dict[str, list[int]] = {
    # ExxonMobil Holdings Corp (CIK 2115436, ticker XOM, facts from 2026) succeeded
    # EXXON MOBIL CORP (CIK 34088, formerly EXXON CORP), which holds the 2009-2026 filings.
    "XOM": [34088],
    # Alphabet Inc. (CIK 1652044, GOOGL/GOOG, facts from 2014-12) succeeded GOOGLE INC.
    # (CIK 1288776) in the 2015 holding-company reorganization.
    "GOOGL": [1288776],
    "GOOG": [1288776],
    # The rest came from the coverage report's share-count gap detector (cap >= $50B,
    # first usable shares > 2 years after the Yahoo price history starts). Each was checked
    # the same way: the old CIK's submissions JSON names the same business (entity name or
    # formerNames), its companyfacts carry share counts from 2009-2012 up to about when the
    # successor CIK's facts begin, and the ticker's Yahoo history is continuous across it.
    # Lists are newest predecessor first.
    # Broadcom Inc (1730168, 2018-06) <- Broadcom Pte. Ltd. (1649338, formerly Broadcom Ltd,
    # filings 2016-03..2018-03) <- Avago Technologies Ltd (1441634, filings to 2015-12).
    "AVGO": [1649338, 1441634],
    # Marvell Technology, Inc. (1835632, 2021-06) <- Marvell Technology Group Ltd (1058057).
    "MRVL": [1058057],
    # Linde plc (1707925, 2017-10) <- Linde Inc, formerly Praxair Inc (884905).
    "LIN": [884905],
    # Walt Disney Co (1744489, 2019-05, formerly TWDC Holdco 613) <- TWDC Enterprises 18 Corp,
    # formerly The Walt Disney Co (1001039).
    "DIS": [1001039],
    # Eaton Corp plc (1551182, 2012-11) <- Eaton Corp (31277).
    "ETN": [31277],
    # Medtronic plc (1613103, 2015-02) <- Medtronic Inc (64670).
    "MDT": [64670],
    # Intercontinental Exchange, Inc. (1571949, 2013-08) <- Intercontinental Exchange Holdings,
    # formerly IntercontinentalExchange Inc (1174746).
    "ICE": [1174746],
    # Cigna Group (1739940, 2019-02) <- Cigna Holding Co, formerly Cigna Corp (701221).
    "CI": [701221],
    # Apollo Global Management, Inc. (1858681, 2022-05) <- Apollo Asset Management, Inc.,
    # formerly Apollo Global Management, Inc. / LLC (1411494).
    "APO": [1411494],
    # Baker Hughes Co (1701605, 2017-07) <- Baker Hughes Holdings LLC, formerly Baker Hughes
    # Inc (808362).
    "BKR": [808362],
}
VOLUME_WINDOW = 252
MIN_VOLUME_BARS = 60
# shares / median daily volume outside [MIN, MAX] means a mis-scaled count (see fix_share_scale)
MAX_SHARES_PER_VOLUME = 10_000.0
MIN_SHARES_PER_VOLUME = 1.0
GOOD_SHARES_PER_VOLUME = 10.0
LIQUIDITY_BARS = 252
MIN_LIQUIDITY_BARS = 20
MAX_PRICE_STALENESS_DAYS = 10
PRICE_FFILL_LIMIT = 5
SPLIT_FETCH_FRACTION = 0.1  # fetch splits for candidates above this share of min_cap

Log = Callable[[str], None]


# --------------------------------------------------------------------------- pool: tickers


def parse_exchange_tickers(payload: Mapping) -> pd.DataFrame:
    """NYSE/Nasdaq rows of SEC's company_tickers_exchange.json as cik/name/ticker/exchange,
    tickers in Yahoo style (`BRK.B` -> `BRK-B`), duplicate tickers dropped."""
    fields = payload.get("fields") or ["cik", "name", "ticker", "exchange"]
    df = pd.DataFrame(payload.get("data") or [], columns=fields)
    df = df[df["exchange"].isin(EXCHANGES)].copy()
    df["cik"] = df["cik"].astype(int)
    df["ticker"] = df["ticker"].map(fd.normalize_ticker)
    return df.drop_duplicates("ticker").sort_values(["cik", "ticker"]).reset_index(drop=True)


def select_one_per_cik(table: pd.DataFrame, dollar_volume: Mapping[str, float]) -> pd.DataFrame:
    """One row per CIK: the share class with the highest median dollar volume.

    Rule: among a CIK's tickers keep the one with the largest `dollar_volume`;
    ties go to the alphabetically first ticker; tickers without a value (no Yahoo
    data) lose to any ticker with one, and a CIK with no value at all is dropped.
    """
    out = table.assign(dollar_volume=table["ticker"].map(dollar_volume).astype(float))
    out = out.dropna(subset=["dollar_volume"])
    out = out.sort_values(["cik", "dollar_volume", "ticker"], ascending=[True, False, True])
    return out.drop_duplicates("cik").sort_values("ticker").reset_index(drop=True)


def pool_filter(market_cap: pd.Series, min_cap: float = DEFAULT_MIN_CAP) -> list[str]:
    """Tickers (sorted) whose current market cap is at least `min_cap`; NaN never qualifies."""
    return sorted(market_cap[market_cap >= min_cap].index)


# --------------------------------------------------------------------------- shares & splits


def _split_factor(splits: pd.Series | None, ends: np.ndarray) -> np.ndarray:
    """Product of split ratios with ex-date strictly after each `ends` entry (1.0 if none/NaT)."""
    if splits is None or splits.empty:
        return np.ones(len(ends))
    s = splits.sort_index()
    ex_dates = s.index.to_numpy("datetime64[ns]")
    suffix = np.append(np.cumprod(s.to_numpy(float)[::-1])[::-1], 1.0)
    return suffix[np.searchsorted(ex_dates, ends.astype("datetime64[ns]"), side="right")]


def split_adjust_shares(
    shares: pd.DataFrame, filed: pd.DataFrame, splits: Mapping[str, pd.Series]
) -> pd.DataFrame:
    """Shares restated to today's share basis: each count times the splits with an ex-date
    after the day it was filed (a count filed after a split is already post-split), so it
    pairs with a split-adjusted close."""
    out = shares.copy()
    for t in shares.columns:
        out[t] = shares[t].to_numpy() * _split_factor(splits.get(t), filed[t].to_numpy())
    return out


def month_end_dates(index: pd.DatetimeIndex, first: pd.Timestamp = FIRST_MONTH) -> pd.DatetimeIndex:
    """Last trading day of each complete month in `index` from `first` on. The
    final month counts only if the index reaches that month's last business day."""
    s = pd.Series(index, index=index)
    last = s.groupby([index.year, index.month]).max()
    ends = pd.DatetimeIndex(last.to_numpy())
    if len(ends) and ends[-1] != ends[-1] + pd.offsets.BMonthEnd(0):
        ends = ends[:-1]
    return ends[ends >= first]


def _month_end_prices(close: pd.DataFrame, month_ends: pd.DatetimeIndex) -> pd.DataFrame:
    """Close at each month-end, using the last close <= t (forward-fill only, <= 5 bars)."""
    return close.ffill(limit=PRICE_FFILL_LIMIT).reindex(month_ends)


def monthly_median_volume(volume: pd.DataFrame, month_ends: pd.DatetimeIndex) -> pd.DataFrame:
    """Trailing ~1-year median daily volume at each month-end (uses bars <= t only)."""
    med = volume.rolling(VOLUME_WINDOW, min_periods=MIN_VOLUME_BARS).median()
    return med.ffill(limit=PRICE_FFILL_LIMIT).reindex(month_ends)


def fix_share_scale(shares: pd.DataFrame, volume_median: pd.DataFrame) -> pd.DataFrame:
    """Repair or drop share counts whose scale contradicts trading volume.

    Filers sometimes mis-scale the cover-page count by a power of 1,000 (Garmin's
    2018 10-Qs say 198 billion shares, AEP's 2010 ones 480 trillion). A real count
    is always larger than the daily volume and rarely more than ~10,000x it. Where
    `shares / median volume` is outside [MIN, MAX] try dividing/multiplying by
    1,000 (up to 1,000^3) to land in [GOOD_MIN, MAX]; otherwise NaN. Cells
    without a volume reading are left unchanged.
    """
    ratio = shares / volume_median
    bad = (ratio > MAX_SHARES_PER_VOLUME) | (ratio < MIN_SHARES_PER_VOLUME)
    out = shares.copy()
    for k in (1, 2, 3):
        for scale in (1000.0**k, 1000.0**-k):
            r = ratio * scale
            fixed = bad & (r <= MAX_SHARES_PER_VOLUME) & (r >= GOOD_SHARES_PER_VOLUME)
            out = out.mask(fixed, shares * scale)
            bad = bad & ~fixed
    return out.mask(bad)


def effective_shares(
    facts: pd.DataFrame,
    month_ends: pd.DatetimeIndex,
    tickers: Sequence[str],
    splits: Mapping[str, pd.Series] | None = None,
    volume: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """month_ends x tickers total shares known at t (filed < t), adjusted for later
    splits and, when `volume` (daily, split-adjusted) is given, scale-checked."""
    return effective_shares_sourced(facts, month_ends, tickers, splits, volume)[0]


def effective_shares_sourced(
    facts: pd.DataFrame,
    month_ends: pd.DatetimeIndex,
    tickers: Sequence[str],
    splits: Mapping[str, pd.Series] | None = None,
    volume: pd.DataFrame | None = None,
    staleness_days: int = fd.STALENESS_DAYS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """`(effective shares, source)`: as `effective_shares`, plus which chain step
    ("dei" / "us-gaap" / "wavg") supplied each count (None where no usable count)."""
    shares, _, filed, source = fd.total_shares_sourced_panels(
        facts, month_ends, list(tickers), staleness_days
    )
    eff = split_adjust_shares(shares, filed, splits or {})
    if volume is not None:
        eff = fix_share_scale(eff, monthly_median_volume(volume, month_ends))
    return eff, source.mask(eff.isna())


def market_cap_panel(
    facts: pd.DataFrame,
    close: pd.DataFrame,
    month_ends: pd.DatetimeIndex,
    splits: Mapping[str, pd.Series] | None = None,
    volume: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """month_ends x tickers market cap: total shares known at t (filed < t, adjusted
    for later splits) times the close at t (<= t). NaN where either is missing."""
    eff = effective_shares(facts, month_ends, list(close.columns), splits, volume)
    return eff * _month_end_prices(close, month_ends)


# --------------------------------------------------------------------------- ranking


def rank_membership(
    caps: pd.DataFrame, top_n: int = DEFAULT_TOP_N, sources: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Long table (month_end, ticker, market_cap, rank, source): the `top_n` largest market
    caps in each row of `caps` (rank 1 = largest; ties broken by ticker; NaN/<=0 excluded).
    `source` is the share-count source from `sources` (same shape as `caps`), else ""."""
    rows = []
    aligned = None if sources is None else sources.reindex(index=caps.index, columns=caps.columns)
    for i in range(len(caps)):
        month_end = caps.index[i]
        s = caps.iloc[i].dropna()
        s = s[s > 0].sort_index().sort_values(ascending=False, kind="stable").head(top_n)
        src = [""] * len(s) if aligned is None else aligned.iloc[i].reindex(s.index)
        rows.append(
            pd.DataFrame(
                {
                    "month_end": month_end,
                    "ticker": s.index,
                    "market_cap": s.to_numpy(),
                    "rank": np.arange(1, len(s) + 1),
                    "source": np.asarray(src, dtype=object),
                }
            )
        )
    if not rows:
        return pd.DataFrame(columns=MEMBERSHIP_COLUMNS)
    return pd.concat(rows, ignore_index=True)[MEMBERSHIP_COLUMNS]


def membership_mask(
    membership: pd.DataFrame, dates: pd.Index, tickers: Sequence[str]
) -> pd.DataFrame:
    """Daily bool dates x tickers mask. A month-end's membership applies from the next
    trading day through the next month-end (dates d with m_i < d <= m_{i+1}); the last
    month-end's applies to all later dates; dates on/before the first month-end are False."""
    dates = pd.DatetimeIndex(dates)
    month_ends = pd.DatetimeIndex(sorted(membership["month_end"].unique()))
    flags = pd.crosstab(membership["month_end"], membership["ticker"]).gt(0)
    flags = flags.reindex(index=month_ends, columns=list(tickers), fill_value=False)
    pos = month_ends.searchsorted(dates, side="left") - 1  # last month-end strictly before d
    values = np.zeros((len(dates), len(tickers)), dtype=bool)
    ok = pos >= 0
    values[ok] = flags.to_numpy()[pos[ok]]
    return pd.DataFrame(values, index=dates, columns=list(tickers))


# --------------------------------------------------------------------------- files


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_membership(membership: pd.DataFrame, path: Path = MEMBERSHIP_PATH) -> str:
    """Write the long table as a deterministic CSV (integer-dollar caps); returns its sha256."""
    out = membership.reindex(columns=MEMBERSHIP_COLUMNS)
    out["source"] = out["source"].fillna("")
    out["market_cap"] = out["market_cap"].round(0).astype("int64")
    out["month_end"] = pd.to_datetime(out["month_end"]).dt.strftime("%Y-%m-%d")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False, lineterminator="\n")
    return file_sha256(path)


def write_universe_meta(meta: Mapping, path: Path = UNIVERSE_PIT_PATH) -> None:
    header = (
        "# Point-in-time size-ranked universe (Phase 4, milestone 2). Written by\n"
        "# `pixi run build-pit-universe`; loaded by `qrl.pit_universe.load_pit_universe`,\n"
        "# which refuses a membership CSV whose sha256 differs from the one below.\n"
        "# An ADDITION beside config/universe.yaml, which is unchanged.\n"
    )
    Path(path).write_text(header + yaml.safe_dump(dict(meta), sort_keys=False, width=100))


def load_pit_universe(path: str | Path = UNIVERSE_PIT_PATH) -> tuple[dict, pd.DataFrame]:
    """Load (meta, membership). `membership_file` is relative to the repo root (the parent
    of the yaml's directory) unless absolute. Raises ValueError if `survivorship_biased`
    is not a bool, or if the CSV's sha256 differs from `membership_sha256`."""
    yaml_path = Path(path).resolve()
    meta: dict = yaml.safe_load(yaml_path.read_text()) or {}
    if not isinstance(meta.get("survivorship_biased"), bool):
        raise ValueError("pit universe must set survivorship_biased to true or false")
    csv_path = Path(meta["membership_file"])
    if not csv_path.is_absolute():
        csv_path = yaml_path.parent.parent / csv_path
    actual = file_sha256(csv_path)
    if actual != meta.get("membership_sha256"):
        raise ValueError(
            f"{csv_path} sha256 {actual} does not match membership_sha256 in {yaml_path}"
        )
    membership = pd.read_csv(csv_path, parse_dates=["month_end"])
    return meta, membership


# --------------------------------------------------------------------------- SEC screening


def screen_payload(payload: Mapping) -> dict:
    """Cheap per-company screen: has us-gaap Assets facts; whether any of them came from a
    10-K/10-Q (`domestic_filer`: 20-F/40-F filers report ordinary shares while Yahoo
    prices ADSs, so their market cap would be wrong); and the latest known total shares
    (any age) with the date it refers to."""
    facts = fd.parse_companyfacts("X", dict(payload), SCREEN_CONCEPTS)
    assets = facts[(facts["concept"] == "Assets") & facts["val"].notna()]
    has_assets = not assets.empty
    domestic = bool(assets["form"].fillna("").str.startswith(("10-K", "10-Q")).any())
    far = pd.DatetimeIndex([pd.Timestamp("2100-01-01")])
    shares, ends, filed, source = fd.total_shares_sourced_panels(
        facts, far, ["X"], staleness_days=10**9
    )
    value = float(shares.to_numpy(dtype=float)[0, 0])
    src = source.iloc[0, 0]
    end = pd.Timestamp(ends.to_numpy(dtype="datetime64[ns]")[0, 0])
    filed_on = pd.Timestamp(filed.to_numpy(dtype="datetime64[ns]")[0, 0])
    return {
        "has_assets": has_assets,
        "domestic_filer": domestic,
        "shares": None if np.isnan(value) else value,
        "shares_end": None if pd.isna(end) else end.strftime("%Y-%m-%d"),
        "shares_filed": None if pd.isna(filed_on) else filed_on.strftime("%Y-%m-%d"),
        "shares_source": None if pd.isna(src) else str(src),
    }


def screen_ciks(
    ciks: Sequence[int],
    refresh: bool,
    cache_dir: Path,
    log: Log,
    config_path: Path = fd.SEC_CONFIG_PATH,
) -> dict[int, dict]:
    """Download (cached) companyfacts for every CIK and screen it; results are cached
    in `screen.json` so an interrupted run resumes where it stopped."""
    path = cache_dir / "screen.json"
    done: dict[str, dict] = {}
    if path.exists() and not refresh:
        done = json.loads(path.read_text())
    todo = [c for c in ciks if "shares_source" not in done.get(str(c), {})]
    log(f"screen: {len(ciks) - len(todo)} cached, {len(todo)} to screen")
    cache_dir.mkdir(parents=True, exist_ok=True)
    for i, cik in enumerate(todo, 1):
        payload = fd.load_company_payload(cik, refresh, config_path=config_path)
        done[str(cik)] = (
            screen_payload(payload)
            if payload is not None
            else {
                "has_assets": False,
                "domestic_filer": False,
                "shares": None,
                "shares_end": None,
                "shares_filed": None,
                "shares_source": None,
            }
        )
        if i % 250 == 0:
            path.write_text(json.dumps(done))
            log(f"screen: {i}/{len(todo)}")
    path.write_text(json.dumps(done))
    return {int(k): v for k, v in done.items()}


# --------------------------------------------------------------------------- Yahoo


def _batch_series(frames: Mapping[str, pd.DataFrame]) -> tuple[dict, dict, dict]:
    closes: dict[str, pd.Series] = {}
    volumes: dict[str, pd.Series] = {}
    dvol: dict[str, float] = {}
    for t, f in frames.items():
        closes[t] = f["Close"]
        volumes[t] = f["Volume"]
        recent = (f["Close"] * f["Volume"]).dropna().tail(LIQUIDITY_BARS)
        if len(recent) >= MIN_LIQUIDITY_BARS:
            dvol[t] = float(recent.median())
    return closes, volumes, dvol


def load_price_panels(
    tickers: Sequence[str], refresh: bool, cache_dir: Path, log: Log
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float], list[str]]:
    """(close panel, volume panel, {ticker: median dollar volume, last year}, tickers with
    no Yahoo data).

    Goes through `qrl.data.load_ohlcv` in batches of `data.CHUNK_SIZE` (shared parquet
    cache, so it resumes). Tickers Yahoo has nothing for are remembered in
    `no_yahoo.txt` and skipped on later runs; a batch where *nothing* came back is
    treated as rate limiting: not remembered, back off 2 minutes, retried next run.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    skip_path = cache_dir / "no_yahoo.txt"
    known_missing = (
        set(skip_path.read_text().split()) if skip_path.exists() and not refresh else set()
    )
    wanted = [t for t in sorted(set(tickers)) if t not in known_missing]
    closes: dict[str, pd.Series] = {}
    volumes: dict[str, pd.Series] = {}
    dvol: dict[str, float] = {}
    missing = set(known_missing) & set(tickers)
    step = data.CHUNK_SIZE
    for i in range(0, len(wanted), step):
        batch = wanted[i : i + step]
        fresh = [t for t in batch if refresh or not (data.CACHE_DIR / f"{t}.parquet").exists()]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            frames = data._load_frames(batch, "1999-01-01", refresh, data.CACHE_DIR, data._BARS)
        got = set(frames)
        gone = set(batch) - got
        if gone and not got and len(fresh) == len(batch):
            log(f"prices: whole batch at {i} empty -> assuming rate limit, sleeping 120s")
            time.sleep(120)
        else:
            missing |= gone
        c, v, d = _batch_series(frames)
        closes.update(c)
        volumes.update(v)
        dvol.update(d)
        if fresh:
            time.sleep(1.0)
        if (i // step) % 10 == 0:
            log(f"prices: {min(i + step, len(wanted))}/{len(wanted)} ({len(missing)} missing)")
    skip_path.write_text("\n".join(sorted(missing)))
    close = pd.DataFrame(closes).sort_index()
    volume = pd.DataFrame(volumes).sort_index().reindex(close.index)
    return close, volume, dvol, sorted(missing)


def load_splits(ticker: str, cache_dir: Path, refresh: bool = False, retries: int = 4) -> pd.Series:
    """Stock splits (ex-date -> ratio, tz-naive) from Yahoo, cached as CSV (an empty file
    means "no splits"). Backs off on failures; raises RuntimeError after `retries`."""
    path = cache_dir / "splits" / f"{ticker}.csv"
    if path.exists() and not refresh:
        df = pd.read_csv(path, parse_dates=["date"])
        return pd.Series(df["ratio"].to_numpy(float), index=pd.DatetimeIndex(df["date"]))
    import yfinance as yf

    last: Exception | None = None
    for attempt in range(retries):
        try:
            s = yf.Ticker(ticker).splits
            idx = pd.to_datetime(s.index).tz_localize(None).normalize()
            out = pd.Series(s.to_numpy(float), index=idx, name="ratio")
            out.index.name = "date"
            path.parent.mkdir(parents=True, exist_ok=True)
            out.reset_index().to_csv(path, index=False)
            return out
        except Exception as err:  # rate limits / network
            last = err
            time.sleep(5 * 3**attempt)
    raise RuntimeError(f"splits for {ticker}: {last}")


def fetch_splits(
    tickers: Sequence[str], cache_dir: Path, refresh: bool, log: Log
) -> tuple[dict[str, pd.Series], list[str]]:
    out: dict[str, pd.Series] = {}
    failed: list[str] = []
    for i, t in enumerate(tickers, 1):
        try:
            out[t] = load_splits(t, cache_dir, refresh)
        except RuntimeError:
            failed.append(t)
        if i % 200 == 0:
            log(f"splits: {i}/{len(tickers)} ({len(failed)} failed)")
    return out, failed


# --------------------------------------------------------------------------- per-company features


def _ytd_only(facts: pd.DataFrame, ni_ttm: pd.Series) -> pd.Series:
    """True where TTM net income is NaN although a 10-Q net-income fact was filed in the
    prior year: the filer reports year-to-date figures only, so quarters cannot be formed."""
    q = facts[
        (facts["concept"] == "NetIncomeLoss") & facts["form"].fillna("").str.startswith("10-Q")
    ]
    filed = np.sort(q["filed"].dropna().to_numpy("datetime64[ns]"))
    dates = ni_ttm.index.to_numpy("datetime64[ns]")
    hi = np.searchsorted(filed, dates, side="left")
    lo = np.searchsorted(filed, dates - np.timedelta64(365, "D"), side="left")
    return pd.Series(ni_ttm.isna().to_numpy() & (hi > lo), index=ni_ttm.index)


def merge_predecessor_facts(facts: pd.DataFrame, predecessor: pd.DataFrame) -> pd.DataFrame:
    """Facts of a company's own CIK plus its predecessor CIK's facts filed strictly before
    the successor's first filing (the predecessor's later filings, if any, are dropped so
    the two histories never overlap). Both frames must carry the same `ticker` label."""
    if facts.empty:
        return predecessor
    cutoff = facts["filed"].min()
    kept = predecessor[predecessor["filed"] < cutoff]
    return pd.DataFrame(pd.concat([kept, facts], ignore_index=True))


def _ttm_chain(
    facts: pd.DataFrame, concepts: Sequence[str], month_ends: pd.DatetimeIndex, ticker: str
) -> pd.Series:
    """TTM of the first concept in priority order that has a value (cell-wise)."""
    out = fd.ttm_panel(facts, concepts[0], month_ends, [ticker])
    for c in concepts[1:]:
        out = out.fillna(fd.ttm_panel(facts, c, month_ends, [ticker]))
    return out[ticker]


def company_features(
    ticker: str,
    payload: Mapping,
    close: pd.Series,
    month_ends: pd.DatetimeIndex,
    splits: pd.Series | None,
    volume: pd.Series | None = None,
    predecessors: Sequence[Mapping] = (),
) -> pd.DataFrame:
    """One row per month-end (`FEATURE_COLUMNS`) for one company, point-in-time. `shares`
    is the split-adjusted, scale-checked total (today's share basis) and `shares_source`
    the chain step that supplied it. `gp_derivable`: GrossProfit TTM, else revenue TTM
    minus cost-of-revenue TTM, is available. `predecessors`: payloads of older CIKs."""
    facts = fd.parse_companyfacts(ticker, dict(payload), FEATURE_CONCEPTS)
    for old in predecessors:
        old_facts = fd.parse_companyfacts(ticker, dict(old), FEATURE_CONCEPTS)
        facts = merge_predecessor_facts(facts, old_facts)
    px = close.to_frame(ticker)
    vol = None if volume is None else volume.to_frame(ticker)
    class_eq = CLASS_EQUIVALENTS.get(ticker)
    if class_eq is None:
        shares, source = effective_shares_sourced(
            facts, month_ends, [ticker], {ticker: splits} if splits is not None else {}, vol
        )
    else:  # `close` is the price_ticker's close; see CLASS_EQUIVALENTS
        own = facts[facts["concept"].isin(class_eq["concepts"])]
        shares, source = effective_shares_sourced(
            own, month_ends, [ticker], None, None, CLASS_EQ_STALENESS_DAYS
        )
        source = source.mask(source.notna(), CLASS_EQ_SOURCE)
    cap = shares * _month_end_prices(px, month_ends)
    ni = fd.ttm_panel(facts, "NetIncomeLoss", month_ends, [ticker])[ticker]
    gp = fd.ttm_panel(facts, "GrossProfit", month_ends, [ticker])[ticker]
    revenue = _ttm_chain(facts, fd.REVENUE_CONCEPTS, month_ends, ticker)
    cost = _ttm_chain(facts, COST_CONCEPTS, month_ends, ticker)
    prior = fd.pit_panel(facts, "Assets", month_ends - pd.DateOffset(years=1), [ticker])
    prior.index = month_ends
    return pd.DataFrame(
        {
            "month_end": month_ends,
            "ticker": ticker,
            "has_price": _month_end_prices(px, month_ends)[ticker].notna().to_numpy(),
            "shares": shares[ticker].to_numpy(),
            "shares_source": source[ticker].to_numpy(),
            "market_cap": cap[ticker].to_numpy(),
            "ni_ttm": ni.to_numpy(),
            "gp_ttm": gp.to_numpy(),
            "gp_derivable": (gp.notna() | (revenue.notna() & cost.notna())).to_numpy(),
            "op_inc_ttm": fd.ttm_panel(facts, "OperatingIncomeLoss", month_ends, [ticker])[
                ticker
            ].to_numpy(),
            "assets": fd.pit_panel(facts, "Assets", month_ends, [ticker])[ticker].to_numpy(),
            "assets_1y": prior[ticker].to_numpy(),
            "ytd_only": _ytd_only(facts, ni).to_numpy(),
        }
    )[FEATURE_COLUMNS]


# --------------------------------------------------------------------------- build


def latest_market_caps(
    table: pd.DataFrame,
    screen: Mapping[int, dict],
    close: pd.DataFrame,
    splits: Mapping[str, pd.Series],
) -> pd.DataFrame:
    """Adds `shares`, `shares_end`, `last_close`, `last_date`, `market_cap` (latest total
    shares, split-adjusted, x latest close) and `stale` (price or shares too old)."""
    out = table.copy()
    rec = out["cik"].map(screen)
    out["shares"] = rec.map(lambda r: r.get("shares") if r else None).astype(float)
    out["shares_end"] = pd.to_datetime(rec.map(lambda r: r.get("shares_end") if r else None))
    out["shares_filed"] = pd.to_datetime(rec.map(lambda r: r.get("shares_filed") if r else None))
    last = close.apply(lambda s: s.last_valid_index())
    out["last_date"] = out["ticker"].map(last)
    out["last_close"] = out["ticker"].map(
        lambda t: close[t].dropna().iloc[-1] if t in close else np.nan
    )
    factor = np.array(
        [
            _split_factor(splits.get(t), np.array([e], dtype="datetime64[ns]"))[0]
            for t, e in zip(out["ticker"], out["shares_filed"].to_numpy(), strict=True)
        ]
    )
    out["market_cap"] = out["shares"] * factor * out["last_close"]
    frame_end = close.index[-1]
    price_old = (frame_end - out["last_date"]).dt.days > MAX_PRICE_STALENESS_DAYS
    shares_old = (frame_end - out["shares_end"]).dt.days > fd.STALENESS_DAYS
    out["stale"] = price_old | shares_old
    return out


def apply_class_equivalents(full: pd.DataFrame, close: pd.DataFrame) -> pd.DataFrame:
    """Re-price `CLASS_EQUIVALENTS` tickers present in `full`: latest class-equivalent share
    count (any age) x latest close of the price ticker; never stale."""
    out = full.copy()
    for t, ce in CLASS_EQUIVALENTS.items():
        rows = out.index[out["ticker"] == t]
        if rows.empty or ce["price_ticker"] not in close:
            continue
        payload = fd.load_company_payload(int(out.loc[rows[0], "cik"]))
        if payload is None:
            continue
        facts = fd.parse_companyfacts(t, payload, FEATURE_CONCEPTS)
        own = facts[facts["concept"].isin(ce["concepts"])]
        far = pd.DatetimeIndex([pd.Timestamp("2100-01-01")])
        shares = fd.total_shares_panel(own, far, [t], CLASS_EQ_STALENESS_DAYS).iloc[0, 0]
        last_close = close[ce["price_ticker"]].dropna().iloc[-1]
        out.loc[rows, "shares"] = shares
        out.loc[rows, "market_cap"] = shares * last_close
        out.loc[rows, "stale"] = False
    return out


def build_pool(
    min_cap: float, refresh: bool, cache_dir: Path, log: Log
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, pd.Series], dict]:
    """(pool table, close panel, volume panel, splits, diagnostics). See the module docstring."""
    table = parse_exchange_tickers(fd.load_exchange_tickers(refresh))
    log(f"exchange list: {len(table)} NYSE/Nasdaq tickers, {table['cik'].nunique()} CIKs")
    screen = screen_ciks(sorted(table["cik"].unique()), refresh, cache_dir, log)
    ok = table["cik"].map(
        lambda c: (
            bool(screen[c]["has_assets"])
            and bool(screen[c]["domestic_filer"])
            and screen[c]["shares"] is not None
        )
    )
    diag: dict = {"exchange_tickers": len(table), "with_assets_and_shares": int(ok.sum())}
    table = table[ok].reset_index(drop=True)
    close, volume, dvol, missing = load_price_panels(
        table["ticker"].tolist(), refresh, cache_dir, log
    )
    diag["no_yahoo_data"] = missing
    table = select_one_per_cik(table, dvol)
    log(f"one ticker per CIK: {len(table)} companies with Yahoo data")
    rough = latest_market_caps(table, screen, close, {})
    candidates = rough.loc[rough["market_cap"] >= min_cap * SPLIT_FETCH_FRACTION, "ticker"]
    splits, failed = fetch_splits(sorted(candidates), cache_dir, refresh, log)
    diag["split_fetch_failed"] = failed
    full = apply_class_equivalents(latest_market_caps(table, screen, close, splits), close)
    diag["stale_dropped"] = int(((full["market_cap"] >= min_cap) & full["stale"]).sum())
    pool = full[(full["market_cap"] >= min_cap) & ~full["stale"]].reset_index(drop=True)
    diag["pool_size"] = len(pool)
    log(
        f"pool: {len(pool)} companies >= ${min_cap / 1e9:.1f}B (stale dropped {diag['stale_dropped']})"
    )
    return pool, close, volume, splits, diag


def build_features(
    pool: pd.DataFrame,
    close: pd.DataFrame,
    volume: pd.DataFrame,
    splits: Mapping[str, pd.Series],
    month_ends: pd.DatetimeIndex,
    log: Log,
) -> pd.DataFrame:
    frames = []
    for i, (t, cik) in enumerate(zip(pool["ticker"], pool["cik"], strict=True), 1):
        payload = fd.load_company_payload(int(cik))
        if payload is not None:
            old = [fd.load_company_payload(c) for c in CIK_PREDECESSORS.get(t, [])]
            ce = CLASS_EQUIVALENTS.get(t)
            pt = t if ce is None else ce["price_ticker"]
            frames.append(
                company_features(
                    t,
                    payload,
                    close[pt],
                    month_ends,
                    splits.get(pt),
                    None if ce else volume[t],
                    [p for p in old if p is not None],
                )
            )
        if i % 100 == 0:
            log(f"features: {i}/{len(pool)}")
    return pd.concat(frames, ignore_index=True)


def make_meta(
    membership: pd.DataFrame, sha: str, top_n: int, min_cap: float, pool_size: int, as_of: str
) -> dict:
    return {
        "name": "us_large_cap_pit",
        "as_of": as_of,
        "method": (
            "Top-N US NYSE/Nasdaq common stocks by point-in-time market cap, re-ranked at each "
            "month-end from 2009 (total shares from SEC filings with filed < t, summed across "
            "share classes, adjusted for later splits and scale-checked against trading volume, "
            "x Yahoo close at t); a month-end's membership applies from the next trading day to "
            "the next month-end. Candidate pool: today's listed 10-K/10-Q filers with us-gaap "
            "Assets facts (no 20-F/40-F filers) and a current market cap above "
            "pool_min_market_cap, one ticker per CIK (most liquid class). Share counts: dei "
            "cover page, else us-gaap CommonStockSharesOutstanding, else weighted-average basic "
            "(source column in the CSV); a small CIK_PREDECESSORS map stitches histories split "
            "across CIKs. Companies SEC companyfacts has no count for are missing in those years."
        ),
        "survivorship_biased": True,
        "top_n": top_n,
        "pool_min_market_cap": float(min_cap),
        "pool_size": pool_size,
        "first_month_end": membership["month_end"].min().strftime("%Y-%m-%d"),
        "last_month_end": membership["month_end"].max().strftime("%Y-%m-%d"),
        "membership_file": "config/universes/us_large_cap_pit.csv",
        "membership_sha256": sha,
    }


def run_build(
    top_n: int = DEFAULT_TOP_N,
    min_cap: float = DEFAULT_MIN_CAP,
    refresh: bool = False,
    log: Log = print,
    cache_dir: Path = PIT_CACHE_DIR,
) -> dict:
    """Fetch, rank, and write the CSV, yaml and feature cache. Returns diagnostics."""
    pool, close, volume, splits, diag = build_pool(min_cap, refresh, cache_dir, log)
    month_ends = month_end_dates(pd.DatetimeIndex(close.index))
    features = build_features(pool, close, volume, splits, month_ends, log)
    caps = features.pivot(index="month_end", columns="ticker", values="market_cap")
    sources = features.pivot(index="month_end", columns="ticker", values="shares_source")
    membership = rank_membership(caps, top_n, sources)
    sha = write_membership(membership)
    info = pool[["ticker", "cik", "market_cap"]].assign(
        first_price=[close[t].first_valid_index() for t in pool["ticker"]]
    )
    info.to_csv(cache_dir / "pool.csv", index=False)
    as_of = close.index[-1].strftime("%Y-%m-%d")
    write_universe_meta(make_meta(membership, sha, top_n, min_cap, len(pool), as_of))
    features.to_parquet(cache_dir / "features.parquet")
    diag.update(rows=len(membership), month_ends=len(month_ends), sha256=sha, as_of=as_of)
    return diag


# --------------------------------------------------------------------------- coverage


def coverage_table(
    membership: pd.DataFrame, features: pd.DataFrame, today_tickers: Sequence[str]
) -> pd.DataFrame:
    """Per-year coverage of the members (averaged over the year's month-ends): average
    member count, % with each input, % YTD-only filers, and overlap with today's list."""
    m = membership.merge(features, on=["month_end", "ticker"], how="left")
    today = {fd.normalize_ticker(t) for t in today_tickers}
    m["year"] = m["month_end"].dt.year
    flags = pd.DataFrame(
        {
            "year": m["year"],
            "price": m["has_price"].fillna(False).astype(bool),
            "shares": m["shares"].notna(),
            "net_income_ttm": m["ni_ttm"].notna(),
            "gross_profit_ttm": m["gp_ttm"].notna(),
            "gp_derivable": m["gp_derivable"].fillna(False).astype(bool),
            "op_income_ttm": m["op_inc_ttm"].notna(),
            "src_dei": m["source"] == "dei",
            "src_gaap": m["source"] == "us-gaap",
            "src_wavg": m["source"] == "wavg",
            "assets": m["assets"].notna(),
            "assets_1y_ago": m["assets_1y"].notna(),
            "ytd_only_10q": m["ytd_only"].fillna(False).astype(bool),
            "in_today_list": m["ticker"].isin(today),
        }
    )
    g = flags.groupby("year")
    months = m.groupby("year")["month_end"].nunique()
    out = (g.mean() * 100).round(1)
    out.insert(0, "members_avg", (g.size() / months).round(1))
    out["in_today_avg"] = (g["in_today_list"].sum() / months).round(1)
    out["not_in_today_avg"] = (out["members_avg"] - out["in_today_avg"]).round(1)
    out["unique_members"] = m.groupby("year")["ticker"].nunique()
    pool = features[features["month_end"] >= membership["month_end"].min()]
    pool_shares = pool["shares"].notna().groupby(pool["month_end"].dt.year).mean() * 100
    out["pool_shares_pct"] = pool_shares.round(1)
    return out.drop(columns=["in_today_list"])


def shares_gap_detector(
    features: pd.DataFrame,
    pool_info: pd.DataFrame,
    min_cap: float = 50e9,
    gap_years: float = 2.0,
) -> pd.DataFrame:
    """Pool companies worth >= `min_cap` today whose first usable share count comes more
    than `gap_years` after their Yahoo price history starts (price start clipped to the
    first month-end), or never: likely CIK changes or tagging gaps in SEC companyfacts."""
    first_ok = features.loc[features["shares"].notna()].groupby("ticker")["month_end"].min()
    floor = features["month_end"].min()
    info = pool_info[pool_info["market_cap"] >= min_cap].copy()
    info["first_price"] = pd.to_datetime(info["first_price"])
    info["first_shares"] = info["ticker"].map(first_ok)
    start = info["first_price"].clip(lower=floor)
    late = (info["first_shares"] - start).dt.days.gt(gap_years * 365.25)
    out = info[late | info["first_shares"].isna()]
    return pd.DataFrame(out.sort_values("market_cap", ascending=False).reset_index(drop=True))


def _true_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """(start, end) index pairs, end inclusive, of each run of True in a bool array."""
    padded = np.concatenate([[0], mask.astype(int), [0]])
    edges = np.diff(padded)
    return list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1) - 1, strict=True))


def shares_stale_detector(
    features: pd.DataFrame,
    pool_info: pd.DataFrame,
    min_cap: float = 50e9,
    max_months: int = 6,
) -> pd.DataFrame:
    """Internal and trailing gaps: pool companies worth >= `min_cap` today whose share count
    is unusable (NaN) for more than `max_months` consecutive month-ends, after the first
    usable count, while the Yahoo price continues."""
    big = pool_info[pool_info["market_cap"] >= min_cap]
    caps = dict(zip(big["ticker"], big["market_cap"], strict=True))
    ciks = dict(zip(big["ticker"], big["cik"], strict=True))
    rows = []
    for t, g in features[features["ticker"].isin(caps)].groupby("ticker"):
        g = g.sort_values("month_end")
        ok = g["shares"].notna().to_numpy()
        if not ok.any():
            continue
        bad = ~ok & g["has_price"].fillna(False).to_numpy(bool)
        bad[: int(ok.argmax())] = False  # leading gap: see shares_gap_detector
        months = g["month_end"].to_numpy()
        for a, b in _true_runs(bad):
            if b - a + 1 > max_months:
                rows.append(
                    {
                        "ticker": t,
                        "cik": ciks[t],
                        "market_cap": caps[t],
                        "run_start": pd.Timestamp(months[a]),
                        "run_end": pd.Timestamp(months[b]),
                        "months": int(b - a + 1),
                    }
                )
    cols = ["ticker", "cik", "market_cap", "run_start", "run_end", "months"]
    out = pd.DataFrame(rows, columns=cols)
    return pd.DataFrame(out.sort_values("market_cap", ascending=False).reset_index(drop=True))


def format_stale(stale: pd.DataFrame) -> list[str]:
    lines = [
        "",
        "Share-count stale-run detector (pool companies >= $50B today with a usable count that "
        "later goes missing for > 6 consecutive month-ends while the price continues):",
    ]
    if stale.empty:
        return [*lines, "  none"]
    for r in stale.to_dict("records"):
        lines.append(
            f"  {r['ticker']:<7} cik {int(r['cik']):>8}  cap ${r['market_cap'] / 1e9:,.0f}B  "
            f"no count {r['run_start']:%Y-%m} .. {r['run_end']:%Y-%m} ({r['months']} months)"
        )
    return lines


def format_gaps(gaps: pd.DataFrame) -> list[str]:
    lines = [
        "",
        "Share-count gap detector (pool companies >= $50B today whose first usable share count "
        "is > 2 years after their Yahoo price history starts, or never):",
    ]
    if gaps.empty:
        return [*lines, "  none"]
    for r in gaps.to_dict("records"):
        first = "never" if pd.isna(r["first_shares"]) else f"{r['first_shares']:%Y-%m}"
        lines.append(
            f"  {r['ticker']:<7} cik {int(r['cik']):>8}  cap ${r['market_cap'] / 1e9:,.0f}B  "
            f"price from {r['first_price']:%Y-%m}  shares from {first}"
        )
    return lines


def format_coverage(
    table: pd.DataFrame,
    membership: pd.DataFrame,
    today_tickers: Sequence[str],
    meta: Mapping,
    gaps: pd.DataFrame | None = None,
    stale: pd.DataFrame | None = None,
) -> str:
    today = {fd.normalize_ticker(t) for t in today_tickers}
    ever = set(membership["ticker"])
    latest = membership[membership["month_end"] == membership["month_end"].max()]
    head = [
        f"PIT universe coverage: {meta['name']} (as_of {meta['as_of']}, top_n {meta['top_n']}, "
        f"pool {meta['pool_size']} companies >= ${meta['pool_min_market_cap'] / 1e9:.1f}B)",
        f"membership {meta['first_month_end']} .. {meta['last_month_end']}, {len(membership)} rows, "
        f"survivorship_biased={meta['survivorship_biased']}",
        "Per year, averaged over its month-ends. Columns after members_avg are % of members "
        "(ytd_only_10q: TTM NaN although 10-Qs were filed in the prior year; gp_derivable: "
        "GrossProfit TTM, else revenue TTM minus cost-of-revenue TTM; src_*: share-count source).",
        "in_today_avg / not_in_today_avg: members inside / outside config/universe.yaml.",
        "shares/price are 100% for members by construction (no value, no rank). "
        "pool_shares_pct: % of ALL pool companies with a usable total share count; the gap to "
        "100 is firms not yet public/filing that year plus firms SEC companyfacts lacks counts for.",
        "",
    ]
    tail = [
        "",
        f"Unique tickers ever a member: {len(ever)}; of those in today's {len(today)}-stock "
        f"list: {len(ever & today)}; today's list not in the PIT universe at any month-end: "
        f"{len(today - ever)}.",
        f"Latest month-end ({meta['last_month_end']}): {len(latest)} members, "
        f"{len(set(latest['ticker']) & today)} in today's list.",
    ]
    gap_lines = [] if gaps is None else format_gaps(gaps)
    stale_lines = [] if stale is None else format_stale(stale)
    return "\n".join([*head, table.to_string(), *tail, *gap_lines, *stale_lines]) + "\n"
