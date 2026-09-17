"""FRED macro series (yield-curve spread, credit spread, jobless claims),
fetched from FRED's free keyless CSV endpoint and lagged to the date each
observation actually becomes available, so a backtest can never see a value
before it was published.

Residual bias, documented on purpose: FRED's CSV endpoint serves the latest
*revised* value for each observation date, not the value as first published
(point-in-time correctness needs ALFRED, FRED's vintage archive, which needs a
registered key -- out of scope). The lagging here is about publication
*timing*, not about undoing later revisions. See `config/macro.yaml`.
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import yaml

CACHE_DIR = Path("data/cache")
DEFAULT_MACRO_CONFIG = Path("config/macro.yaml")
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"


def load_macro_config(path: str | Path = DEFAULT_MACRO_CONFIG) -> dict:
    raw = Path(path).read_text()
    config: dict = yaml.safe_load(raw)
    if not config.get("series"):
        raise ValueError("macro config has no series defined")
    return config


def _fetch_one(series_id: str, retries: int = 3) -> pd.Series:
    last_err: Exception | None = None
    url = FRED_CSV_URL.format(series_id=series_id)
    for attempt in range(retries):
        try:
            raw = pd.read_csv(url, na_values=["."])
            date_col, value_col = raw.columns[0], raw.columns[1]
            s = pd.Series(
                raw[value_col].to_numpy(dtype=float),
                index=pd.to_datetime(raw[date_col]),
                name=series_id,
            ).sort_index()
            if s.dropna().empty:
                raise RuntimeError(f"No usable rows returned for {series_id}")
            return s
        except Exception as err:  # network hiccups are common
            last_err = err
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {series_id}: {last_err}")


def fetch_series(series_id: str, refresh: bool = False, cache_dir: Path = CACHE_DIR) -> pd.Series:
    """Return a raw FRED series indexed by observation date (not yet lagged)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"macro_{series_id}.parquet"
    if path.exists() and not refresh:
        return pd.read_parquet(path)[series_id]
    s = _fetch_one(series_id)
    s.to_frame().to_parquet(path)
    return s


def lag_to_availability(series: pd.Series, lag: dict) -> pd.Series:
    """Reindex `series` from observation date to the date it becomes known.

    `lag` is a mapping like `{"unit": "business_days"|"calendar_days", "value": N}`,
    matching the `lag:` block of a series in `config/macro.yaml`.
    """
    unit, value = lag["unit"], lag["value"]
    out = series.copy()
    if unit == "business_days":
        out.index = series.index + pd.tseries.offsets.BDay(value)
    elif unit == "calendar_days":
        out.index = series.index + pd.Timedelta(days=value)
    else:
        raise ValueError(f"Unknown lag unit: {unit!r}")
    # A few real FRED series (e.g. an ICE credit-spread index) occasionally
    # stamp a value on a weekend, repeating the prior close. Business-day
    # rollover can then map two different observation dates onto the same
    # availability date; keep the later observation (the more current value)
    # for that date. `out` is still in ascending observation-date order here,
    # so `keep="last"` keeps the later one.
    out = out[~out.index.duplicated(keep="last")]
    return out.sort_index()


def align_to_trading_days(series: pd.Series, trading_index: pd.DatetimeIndex) -> pd.Series:
    """Forward-fill an availability-dated `series` onto `trading_index`.

    The value used on trading day t is the most recent observation whose
    availability date is <= t; trading days before the first availability
    date get NaN. `series` must already be indexed by availability date (see
    `lag_to_availability`), not by observation date.
    """
    combined = trading_index.union(pd.DatetimeIndex(series.index))
    return series.reindex(combined).ffill().reindex(trading_index)


def load_macro(
    ids: list[str] | None = None,
    trading_index: pd.DatetimeIndex | None = None,
    refresh: bool = False,
    cache_dir: Path = CACHE_DIR,
    config_path: str | Path = DEFAULT_MACRO_CONFIG,
) -> pd.DataFrame:
    """Load, lag, and align FRED macro series. Columns are series ids.

    If `ids` is None, loads every series in `config_path`. If `trading_index`
    is None, returns the lagged (availability-dated, not-yet-aligned) series.
    """
    config = load_macro_config(config_path)
    series_cfg = config["series"]
    chosen = ids if ids is not None else list(series_cfg)
    unknown = set(chosen) - series_cfg.keys()
    if unknown:
        raise ValueError(f"Unknown macro series id(s): {sorted(unknown)}")

    lagged = {}
    for series_id in chosen:
        raw = fetch_series(series_id, refresh=refresh, cache_dir=cache_dir)
        lagged[series_id] = lag_to_availability(raw, series_cfg[series_id]["lag"])

    if trading_index is None:
        return pd.DataFrame(lagged).sort_index()
    return pd.DataFrame(
        {sid: align_to_trading_days(s, trading_index) for sid, s in lagged.items()},
        index=trading_index,
    )
