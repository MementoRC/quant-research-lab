"""Point-in-time company fundamentals from SEC EDGAR (XBRL "company facts").

Milestone 1 of the EDGAR factor sleeve: the data layer only. Raw JSON is cached
next to the price cache (`data/cache/sec/`, gitignored); `parse_companyfacts`
turns it into a tidy long table; `pit_panel` / `ttm_panel` turn that into
dates x tickers panels that only ever use information public at each date.

Point-in-time rule: a fact is usable from the first trading day STRICTLY AFTER
its `filed` date (a filing is assumed public no earlier than the next session).
With `dates` a trading-day index this means "usable at t iff filed < t".

SEC fair-access policy requires an identifying User-Agent with a contact email.
The email comes from env `SEC_USER_AGENT_EMAIL`, else the gitignored
`config/sec.local.yaml` (key `contact_email`); with neither, nothing is fetched.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import warnings
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from qrl.data import CACHE_DIR

SEC_CACHE_DIR = CACHE_DIR / "sec"
SEC_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "sec.local.yaml"
EMAIL_ENV_VAR = "SEC_USER_AGENT_EMAIL"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
EXCHANGE_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

MIN_REQUEST_INTERVAL = 0.125  # seconds -> at most 8 requests/second (SEC limit is 10)
MAX_RETRIES = 5

# taxonomy -> concepts parsed. Extend here for later milestones.
CONCEPTS: dict[str, tuple[str, ...]] = {
    "us-gaap": (
        "NetIncomeLoss",
        "GrossProfit",
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
        "CostOfRevenue",
        "Assets",
        "StockholdersEquity",
        "CommonStockSharesOutstanding",
        "WeightedAverageNumberOfSharesOutstandingBasic",
        "CostOfGoodsAndServicesSold",
        "CostOfGoodsSold",
        "OperatingIncomeLoss",
    ),
    "dei": ("EntityCommonStockSharesOutstanding",),
}
# Revenue concept fallbacks, newest tagging first (see `pit_panel_fallback`).
REVENUE_CONCEPTS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
)
SHARES_CONCEPTS = ("EntityCommonStockSharesOutstanding", "CommonStockSharesOutstanding")
# Balance-sheet / cover-page items: a point in time, no meaningful `start`.
INSTANT_CONCEPTS = frozenset(
    {
        "Assets",
        "StockholdersEquity",
        "CommonStockSharesOutstanding",
        "EntityCommonStockSharesOutstanding",
    }
)

FACT_COLUMNS = [
    "ticker",
    "taxonomy",
    "concept",
    "unit",
    "start",
    "end",
    "val",
    "form",
    "fy",
    "fp",
    "filed",
    "accn",
]
QUARTER_DAYS = (80, 100)
ANNUAL_DAYS = (350, 380)
STALENESS_DAYS = 456  # ~15 months after the period end


class SecIdentityError(RuntimeError):
    """No contact email configured; refusing to contact SEC."""


# --------------------------------------------------------------------------- identity & HTTP


def sec_user_agent(config_path: Path = SEC_CONFIG_PATH) -> str:
    """User-Agent string "quant-research-lab <email>"; raises SecIdentityError if no email."""
    email = os.environ.get(EMAIL_ENV_VAR, "").strip()
    if not email and Path(config_path).exists():
        cfg = yaml.safe_load(Path(config_path).read_text()) or {}
        email = str(cfg.get("contact_email") or "").strip()
    if not email:
        raise SecIdentityError(
            f"SEC requires a contact email: set {EMAIL_ENV_VAR} or put `contact_email: ...` "
            f"in {config_path} (gitignored). Refusing to fetch."
        )
    return f"quant-research-lab {email}"


_last_request = 0.0

ALLOWED_HOSTS = frozenset({"www.sec.gov", "data.sec.gov"})


def _validate_url(url: str) -> None:
    """Raise ValueError unless url is https on an allowlisted SEC host."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS:
        raise ValueError(f"refusing URL (https on {sorted(ALLOWED_HOSTS)} only): {url}")


class _AllowlistRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Re-validate every redirect target against the same allowlist."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        _validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_AllowlistRedirectHandler())


def _http_get(url: str, user_agent: str) -> bytes:
    """GET with throttling (<= ~8 req/s) and backoff on 429/5xx. 404 raises HTTPError."""
    global _last_request
    _validate_url(url)
    for attempt in range(MAX_RETRIES):
        wait = MIN_REQUEST_INTERVAL - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()
        # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected -- URL validated against ALLOWED_HOSTS (https only) above
        req = urllib.request.Request(url, headers={"User-Agent": user_agent})  # noqa: S310
        try:
            # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected -- URL validated against ALLOWED_HOSTS (https only) above
            with _OPENER.open(req, timeout=60) as resp:  # noqa: S310
                body: bytes = resp.read()
                return body
        except urllib.error.HTTPError as err:
            if err.code != 429 and err.code < 500:
                raise
            if attempt == MAX_RETRIES - 1:
                raise
        except urllib.error.URLError:
            if attempt == MAX_RETRIES - 1:
                raise
        time.sleep(2**attempt)
    raise RuntimeError("unreachable")  # pragma: no cover


# --------------------------------------------------------------------------- tickers / cache


def normalize_ticker(ticker: str) -> str:
    """Canonical lookup key: upper-case, '.', '/' and '_' folded to '-' (BRK.B == BRK-B)."""
    return re.sub(r"[./_\s]", "-", ticker.strip().upper())


def build_cik_map(payload: dict) -> dict[str, int]:
    """{normalized ticker: CIK} from SEC's company_tickers.json payload."""
    out: dict[str, int] = {}
    for row in payload.values():
        out.setdefault(normalize_ticker(row["ticker"]), int(row["cik_str"]))
    return out


def _cached_json(path: Path, url: str, refresh: bool, fetch: Callable[[str], bytes]) -> dict | None:
    """Read cached JSON, downloading only if missing or `refresh`. None on HTTP 404."""
    if path.exists() and not refresh:
        cached: dict = json.loads(path.read_text())
        return cached
    try:
        raw = fetch(url)
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return None
        raise
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    fresh: dict = json.loads(raw)
    return fresh


def load_cik_map(
    refresh: bool = False,
    cache_dir: Path = SEC_CACHE_DIR,
    config_path: Path = SEC_CONFIG_PATH,
) -> dict[str, int]:
    ua = sec_user_agent(config_path)
    payload = _cached_json(
        cache_dir / "company_tickers.json", TICKERS_URL, refresh, lambda u: _http_get(u, ua)
    )
    return build_cik_map(payload or {})


def load_exchange_tickers(
    refresh: bool = False,
    cache_dir: Path = SEC_CACHE_DIR,
    config_path: Path = SEC_CONFIG_PATH,
) -> dict:
    """SEC's company_tickers_exchange.json payload ({"fields": [...], "data": [[...]]}:
    cik, name, ticker, exchange), cached next to the other SEC downloads."""
    ua = sec_user_agent(config_path)
    payload = _cached_json(
        cache_dir / "company_tickers_exchange.json",
        EXCHANGE_TICKERS_URL,
        refresh,
        lambda u: _http_get(u, ua),
    )
    return payload or {}


def load_company_payload(
    cik: int,
    refresh: bool = False,
    cache_dir: Path = SEC_CACHE_DIR,
    config_path: Path = SEC_CONFIG_PATH,
) -> dict | None:
    """Raw companyfacts JSON for one CIK (cached; None when SEC has none, e.g. funds)."""
    ua = sec_user_agent(config_path)
    path = cache_dir / "facts" / f"CIK{cik:010d}.json"
    return _cached_json(path, FACTS_URL.format(cik=cik), refresh, lambda u: _http_get(u, ua))


# --------------------------------------------------------------------------- parsing


def parse_companyfacts(
    ticker: str,
    payload: dict,
    concepts: dict[str, Iterable[str]] | None = None,
) -> pd.DataFrame:
    """Tidy long table (columns `FACT_COLUMNS`) from one companyfacts JSON payload.

    Concepts a company never reported are simply absent. Instant facts (balance
    sheet, cover page) have no `start` -> NaT. `frame` is dropped: it marks one
    representative fact per period and is not needed for point-in-time use.
    """
    spec: dict[str, Iterable[str]] = dict(concepts or CONCEPTS)
    rows: list[dict] = []
    for taxonomy, names in spec.items():
        tax_facts = payload.get("facts", {}).get(taxonomy, {})
        for concept in names:
            for unit, items in tax_facts.get(concept, {}).get("units", {}).items():
                for it in items:
                    rows.append(
                        {
                            "ticker": ticker,
                            "taxonomy": taxonomy,
                            "concept": concept,
                            "unit": unit,
                            "start": it.get("start"),
                            "end": it.get("end"),
                            "val": it.get("val"),
                            "form": it.get("form"),
                            "fy": it.get("fy"),
                            "fp": it.get("fp"),
                            "filed": it.get("filed"),
                            "accn": it.get("accn"),
                        }
                    )
    df = pd.DataFrame(rows, columns=FACT_COLUMNS)
    for col in ("start", "end", "filed"):
        df[col] = pd.to_datetime(df[col]).astype("datetime64[ns]")
    df["val"] = pd.to_numeric(df["val"], errors="coerce")
    return df


def load_facts(
    tickers: Sequence[str],
    refresh: bool = False,
    cache_dir: Path = SEC_CACHE_DIR,
    config_path: Path = SEC_CONFIG_PATH,
) -> pd.DataFrame:
    """Facts for `tickers` (Yahoo-style accepted), downloading only what is not cached.

    Checks the SEC identity before any request. Tickers with no CIK or no
    companyfacts (ETFs, foreign filers) are skipped with a warning.
    """
    ua = sec_user_agent(config_path)
    fetch = lambda u: _http_get(u, ua)  # noqa: E731
    cik_map = load_cik_map(refresh, cache_dir, config_path)
    frames = []
    for t in tickers:
        cik = cik_map.get(normalize_ticker(t))
        if cik is None:
            warnings.warn(f"{t}: no SEC CIK found, skipped", stacklevel=2)
            continue
        path = cache_dir / "facts" / f"CIK{cik:010d}.json"
        payload = _cached_json(path, FACTS_URL.format(cik=cik), refresh, fetch)
        if payload is None:
            warnings.warn(f"{t}: no SEC company facts (CIK {cik}), skipped", stacklevel=2)
            continue
        frames.append(parse_companyfacts(t, payload))
    if not frames:
        return pd.DataFrame(columns=FACT_COLUMNS)
    return pd.concat(frames, ignore_index=True)


# --------------------------------------------------------------------------- durations


def _duration_days(df: pd.DataFrame) -> pd.Series:
    return (df["end"] - df["start"]).dt.days


def filter_duration(df: pd.DataFrame, kind: str) -> pd.DataFrame:
    """Keep facts of one period length: 'quarterly' (80-100d), 'annual' (350-380d),
    or 'instant' (no filter; balance-sheet items)."""
    if kind == "instant":
        return df
    bounds = {"quarterly": QUARTER_DAYS, "annual": ANNUAL_DAYS}[kind]
    d = _duration_days(df)
    return df[(d >= bounds[0]) & (d <= bounds[1])]


# --------------------------------------------------------------------------- panels


def _map_to_dates(
    filed: np.ndarray,
    end: np.ndarray,
    val: np.ndarray,
    dates: pd.DatetimeIndex,
    staleness_days: int,
) -> np.ndarray:
    """State arrays (sorted by `filed`; state[i] = value known once filing i is public)
    -> value at each date, using the last state with filed < date; NaN when stale."""
    out = np.full(len(dates), np.nan)
    if len(filed) == 0:
        return out
    pos = filed.astype("datetime64[ns]").searchsorted(
        dates.values.astype("datetime64[ns]"), side="left"
    )
    ok = pos > 0
    idx = pos[ok] - 1
    age = (
        (dates.values[ok].astype("datetime64[ns]") - end[idx].astype("datetime64[ns]"))
        .astype("timedelta64[D]")
        .astype(float)
    )
    res = np.where(age <= staleness_days, val[idx], np.nan)
    out[ok] = res
    return out


def _latest_period_states(g: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Running 'latest period end, ties -> latest filed' state, one row per fact."""
    g = g.dropna(subset=["val", "end", "filed"]).sort_values(["filed", "end"], kind="stable")
    cur_key: tuple | None = None
    cur_end = cur_val = None
    ends, vals = [], []
    for end, filed, val in zip(g["end"], g["filed"], g["val"], strict=True):
        if cur_key is None or (end, filed) >= cur_key:
            cur_key, cur_end, cur_val = (end, filed), end, val
        ends.append(cur_end)
        vals.append(cur_val)
    return (
        g["filed"].to_numpy(),
        np.array(ends, dtype="datetime64[ns]"),
        np.array(vals, dtype=float),
    )


def pit_panel(
    facts: pd.DataFrame,
    concept: str,
    dates: pd.Index,
    tickers: Sequence[str],
    duration: str | None = None,
    staleness_days: int = STALENESS_DAYS,
) -> pd.DataFrame:
    """dates x tickers panel of `concept` as known at each date.

    At date t, among facts with filed < t (first trading day strictly after the
    filing), take the one with the latest period `end`; ties go to the latest
    `filed`, so a restatement replaces the original only once it is public.
    `duration` selects period length ('instant', 'quarterly', 'annual'); default
    is 'instant' for balance-sheet/share concepts and 'annual' otherwise (use
    `ttm_panel` for flows). If a concept has several units the facts are mixed;
    the concept list only holds single-unit concepts. NaN where nothing is
    known, or where the latest known period ended more than `staleness_days` ago
    (never forward-filled across a longer gap).
    """
    dates = pd.DatetimeIndex(dates)
    kind = duration or ("instant" if concept in INSTANT_CONCEPTS else "annual")
    sub = facts[facts["concept"] == concept]
    out = pd.DataFrame(np.nan, index=dates, columns=list(tickers))
    for t in tickers:
        g = filter_duration(sub[sub["ticker"] == t], kind)
        if g.empty:
            continue
        filed, end, val = _latest_period_states(g)
        out[t] = _map_to_dates(filed, end, val, dates, staleness_days)
    return out


def pit_panel_fallback(
    facts: pd.DataFrame,
    concepts: Sequence[str],
    dates: pd.Index,
    tickers: Sequence[str],
    duration: str | None = None,
    staleness_days: int = STALENESS_DAYS,
) -> pd.DataFrame:
    """Cell-wise first non-NaN of `pit_panel` over `concepts` in priority order
    (e.g. `REVENUE_CONCEPTS`, `SHARES_CONCEPTS`). Companies retag over time, so
    list the newest tag first; staleness stops an abandoned tag lingering."""
    out = pit_panel(facts, concepts[0], dates, tickers, duration, staleness_days)
    for c in concepts[1:]:
        out = out.fillna(pit_panel(facts, c, dates, tickers, duration, staleness_days))
    return out


def _ttm_state(
    quarters: dict[pd.Timestamp, tuple[pd.Timestamp, float]],
    annuals: dict[pd.Timestamp, tuple[pd.Timestamp, float]],
) -> tuple[pd.Timestamp, float] | None:
    """(period end, TTM value) from the quarterly/annual facts known so far, or None.

    quarters/annuals: end -> (start, val). Q4 = FY - (Q1+Q2+Q3) when exactly three
    quarters lie inside the fiscal year and Q4 itself was not reported. TTM is the
    sum of the four consecutive quarters (ends 70-110 days apart) ending at the
    latest period end; if that end is a fiscal-year end, TTM is simply the FY value.
    """
    q = {e: v for e, (_, v) in quarters.items()}
    for end, (start, fy_val) in annuals.items():
        if end in q:
            continue
        inner = [
            e
            for e, (s, _) in quarters.items()
            if start < e < end - pd.Timedelta(days=30) and s >= start - pd.Timedelta(days=7)
        ]
        if len(inner) == 3:
            q[end] = fy_val - sum(q[e] for e in inner)
    if not q and not annuals:
        return None
    last = max([*q, *annuals])
    if last in annuals:
        return last, annuals[last][1]
    ends = sorted(q)
    if len(ends) < 4:
        return None
    chain = ends[-4:]
    gaps = [(b - a).days for a, b in zip(chain[:-1], chain[1:], strict=True)]
    if not all(70 <= g <= 110 for g in gaps):
        return None
    return last, float(sum(q[e] for e in chain))


def ttm_panel(
    facts: pd.DataFrame,
    concept: str,
    dates: pd.Index,
    tickers: Sequence[str],
    staleness_days: int = STALENESS_DAYS,
) -> pd.DataFrame:
    """dates x tickers trailing-twelve-month value of a flow `concept`, as known at t.

    Only facts with filed < t are used; for each (start, end) period the latest
    filed value wins (restatements). Quarterly facts are 80-100 day periods,
    annual facts 350-380 days. Assumptions: 10-Qs report discrete 3-month values
    (year-to-date-only filers give NaN); Q4 is derived as FY - (Q1+Q2+Q3) when
    only the 10-K reports it; fiscal quarters are consecutive. NaN when four
    consecutive quarters cannot be formed, or when the latest period ended more
    than `staleness_days` before t.
    """
    dates = pd.DatetimeIndex(dates)
    sub = facts[facts["concept"] == concept]
    out = pd.DataFrame(np.nan, index=dates, columns=list(tickers))
    for t in tickers:
        g = sub[sub["ticker"] == t].dropna(subset=["val", "start", "end", "filed"])
        g = g.assign(_days=_duration_days(g)).sort_values(["filed", "end"], kind="stable")
        quarters: dict = {}
        annuals: dict = {}
        f_out: list = []
        e_out: list = []
        v_out: list = []
        for filed, grp in g.groupby("filed", sort=True):
            for start, end, val, days in zip(
                grp["start"], grp["end"], grp["val"], grp["_days"], strict=True
            ):
                if QUARTER_DAYS[0] <= days <= QUARTER_DAYS[1]:
                    quarters[end] = (start, float(val))
                elif ANNUAL_DAYS[0] <= days <= ANNUAL_DAYS[1]:
                    annuals[end] = (start, float(val))
            state = _ttm_state(quarters, annuals)
            f_out.append(filed)
            e_out.append(state[0] if state else pd.NaT)
            v_out.append(state[1] if state else np.nan)
        if not f_out:
            continue
        ends = pd.to_datetime(pd.Series(e_out)).to_numpy().astype("datetime64[ns]")
        # NaT end -> age NaT -> comparison False -> NaN, which is what we want.
        out[t] = _map_to_dates(
            np.array(f_out, dtype="datetime64[ns]"),
            ends,
            np.array(v_out, dtype=float),
            dates,
            staleness_days,
        )
    return out


# --------------------------------------------------------------------------- total shares

DEI_SHARES = "EntityCommonStockSharesOutstanding"
GAAP_SHARES = "CommonStockSharesOutstanding"
_EPOCH = pd.Timestamp("1970-01-01")


def total_shares_facts(facts: pd.DataFrame) -> pd.DataFrame:
    """Cover-page share counts summed across share classes, one row per (ticker, accn, end).

    A multi-class company reports one `EntityCommonStockSharesOutstanding` value per
    class under the same filing (`accn`) and `end`, with no class label; the sum of
    those values is the company's total. Rows share the concept name so the result
    plugs straight into `pit_panel`. Single-class companies pass through unchanged.
    """
    sub = facts[facts["concept"] == DEI_SHARES].dropna(subset=["val", "end", "filed"])
    if sub.empty:
        return pd.DataFrame(columns=FACT_COLUMNS)
    g = sub.groupby(["ticker", "accn", "end"], as_index=False, dropna=False).agg(
        val=("val", "sum"),
        filed=("filed", "max"),
        unit=("unit", "first"),
        form=("form", "first"),
        fy=("fy", "first"),
        fp=("fp", "first"),
    )
    g["taxonomy"] = "dei"
    g["concept"] = DEI_SHARES
    g["start"] = pd.NaT
    return g[FACT_COLUMNS]


def _date_panel(days: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {c: _EPOCH + pd.to_timedelta(days[c], unit="D") for c in days.columns}, index=days.index
    )


WA_SHARES = "WeightedAverageNumberOfSharesOutstandingBasic"
SHARE_SOURCES = ("dei", "us-gaap", "wavg")


def _layer_panels(
    frame: pd.DataFrame,
    concept: str,
    dates: pd.DatetimeIndex,
    tickers: Sequence[str],
    duration: str,
    staleness_days: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(value, end-day, filed-day) panels of one share-count layer."""
    end_days = filed_days = frame
    if not frame.empty:
        end_days = frame.assign(val=(frame["end"] - _EPOCH) / pd.Timedelta(days=1))
        filed_days = frame.assign(val=(frame["filed"] - _EPOCH) / pd.Timedelta(days=1))
    return (
        pit_panel(frame, concept, dates, tickers, duration, staleness_days),
        pit_panel(end_days, concept, dates, tickers, duration, staleness_days),
        pit_panel(filed_days, concept, dates, tickers, duration, staleness_days),
    )


def total_shares_sourced_panels(
    facts: pd.DataFrame,
    dates: pd.Index,
    tickers: Sequence[str],
    staleness_days: int = STALENESS_DAYS,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """`(shares, ends, filed, source)` dates x tickers panels.

    Cell-wise priority chain: (1) dei cover-page counts summed per (accn, end) across
    classes, (2) us-gaap `CommonStockSharesOutstanding`, (3) us-gaap
    `WeightedAverageNumberOfSharesOutstandingBasic`, the latest quarterly (80-100 day)
    fact, else the annual one. All obey filed < t and `staleness_days`. `source` holds
    "dei" / "us-gaap" / "wavg" (None where no count is known). `ends` is the date a
    count refers to and `filed` the date it was filed (NaT where unknown); a count filed
    after a stock split is already post-split, so split adjustment compares ex-dates
    with `filed`.
    """
    idx = pd.DatetimeIndex(dates)
    wa = facts[facts["concept"] == WA_SHARES]
    layers = (
        ("dei", total_shares_facts(facts), DEI_SHARES, "instant"),
        ("us-gaap", facts[facts["concept"] == GAAP_SHARES], GAAP_SHARES, "instant"),
        ("wavg", wa, WA_SHARES, "quarterly"),
        ("wavg", wa, WA_SHARES, "annual"),
    )
    shares = pd.DataFrame(np.nan, index=idx, columns=list(tickers))
    end_days = shares.copy()
    filed_days = shares.copy()
    source = pd.DataFrame(None, index=idx, columns=list(tickers), dtype=object)
    for name, frame, concept, duration in layers:
        v, e, f = _layer_panels(frame, concept, idx, tickers, duration, staleness_days)
        fill = shares.isna() & v.notna()
        source = source.mask(fill, name)
        shares, end_days, filed_days = shares.fillna(v), end_days.fillna(e), filed_days.fillna(f)
    return shares, _date_panel(end_days), _date_panel(filed_days), source


def total_shares_dated_panels(
    facts: pd.DataFrame,
    dates: pd.Index,
    tickers: Sequence[str],
    staleness_days: int = STALENESS_DAYS,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """`(shares, ends, filed)` of `total_shares_sourced_panels` (source dropped)."""
    return total_shares_sourced_panels(facts, dates, tickers, staleness_days)[:3]


def total_shares_panel(
    facts: pd.DataFrame,
    dates: pd.Index,
    tickers: Sequence[str],
    staleness_days: int = STALENESS_DAYS,
) -> pd.DataFrame:
    """dates x tickers TOTAL shares outstanding as known at each date (filed < t).

    Uses dei cover-page counts summed per (accn, end) across share classes
    (`total_shares_facts`), falling back cell-wise to us-gaap
    `CommonStockSharesOutstanding`, then to the weighted-average basic count (see
    `total_shares_sourced_panels`). Same point-in-time and staleness rules as `pit_panel`.
    """
    return total_shares_dated_panels(facts, dates, tickers, staleness_days)[0]
