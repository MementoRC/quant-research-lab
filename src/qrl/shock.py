"""What-if shock (spec: docs/methodology/whatif-shock.md): an owner-defined
stretch of bad years put in front of each start year's real history, then the
decision report's own withdrawal code. The only new calculations are the stretch
returns, the synthetic CPI and the splice factor. Pure functions; the script does
the IO. Every price and CPI frame is cut at the research end (2018-12-31) as
`qrl.decision.withdrawal_rows` cuts it, and nothing is ever unsealed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .decision_config import ID_PATTERN, Portfolio, held_tickers
from .decision_withdraw import CPI_SERIES

GROUPS = ("stocks", "gold", "long_bonds", "short_bonds")
YEAR_KEYS = (*GROUPS, "inflation")
FILE_KEYS = ("name", "years")
MAX_YEARS = 10
MAX_RETURN = 2.0  # +200%
MIN_INFLATION, MAX_INFLATION = -0.10, 0.30


@dataclass(frozen=True)
class Shock:
    name: str
    years: tuple[dict[str, float], ...]  # in order; each has exactly YEAR_KEYS


def _exact_keys(raw: object, keys: tuple[str, ...], what: str) -> dict:
    if not isinstance(raw, dict):
        raise ValueError(f"{what} must be a mapping with exactly the keys {list(keys)}")
    unknown = sorted(str(k) for k in raw if k not in keys)
    missing = [k for k in keys if k not in raw]
    if unknown or missing:
        raise ValueError(f"{what}: unknown key(s) {unknown}, missing key(s) {missing}")
    return raw


def _number(value: object, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{what}: {value!r} is not a finite number")
    try:
        number = float(value)  # a huge int overflows here
    except OverflowError as exc:
        raise ValueError(f"{what}: {str(value)[:20]}... is not a finite number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{what}: {value!r} is not a finite number")
    return number


def _year(raw: object, k: int) -> dict[str, float]:
    what = f"shock year {k}"
    entry = _exact_keys(raw, YEAR_KEYS, what)
    year = {key: _number(entry[key], f"{what} {key}") for key in YEAR_KEYS}
    for group in GROUPS:
        if not -1 < year[group] <= MAX_RETURN:
            raise ValueError(
                f"{what} {group} {year[group]:g} must be above -1 and at most {MAX_RETURN:g}"
            )
    if not MIN_INFLATION <= year["inflation"] <= MAX_INFLATION:
        raise ValueError(
            f"{what} inflation {year['inflation']:g} must be in "
            f"[{MIN_INFLATION:g}, {MAX_INFLATION:g}]"
        )
    return year


def load_shock(path: str | Path) -> Shock:
    """Parse and validate a shock file (read only). Raises ValueError (a refusal)
    on a missing or unreadable file, invalid YAML, keys other than exactly `name`
    and `years`, a name not matching [A-Za-z0-9_-]+, `years` not a list of 1 to 10
    entries, a year whose keys are not exactly the four groups plus `inflation`,
    a value that is not a finite number (booleans and strings refused), a return
    not in (-1, 2] or an inflation not in [-0.10, 0.30]."""
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise ValueError(f"shock file {path} cannot be read ({exc.strerror or exc})") from exc
    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"shock file is not valid YAML ({exc})") from exc
    doc = _exact_keys(doc, FILE_KEYS, "shock file")
    name = doc["name"]
    if not isinstance(name, str) or not ID_PATTERN.fullmatch(name):
        raise ValueError(f"shock name {name!r} must match [A-Za-z0-9_-]+")
    years = doc["years"]
    if not isinstance(years, list) or not 1 <= len(years) <= MAX_YEARS:
        raise ValueError(f"shock `years` must be a list of 1 to {MAX_YEARS} entries")
    return Shock(name, tuple(_year(entry, k) for k, entry in enumerate(years, 1)))


# Each held fund takes one group's yearly return; IEF the midpoint (mean) of long
# and short bonds. Flagged caveats (spec): QQQ is treated like SPY, and IEF at the
# midpoint is a rough duration guess, not data.
FUND_GROUP: dict[str, tuple[str, ...]] = {
    "SPY": ("stocks",),
    "QQQ": ("stocks",),
    "RSP": ("stocks",),
    "GLD": ("gold",),
    "TLT": ("long_bonds",),
    "SHY": ("short_bonds",),
    "IEF": ("long_bonds", "short_bonds"),
}


def fund_return(fund: str, year: dict[str, float]) -> float:
    """A fund's return in one shock year: the arithmetic mean of its groups'
    returns (one group, or IEF's two)."""
    groups = FUND_GROUP.get(fund)
    if groups is None:
        raise ValueError(f"held fund {fund!r} has no shock group (fund map: {sorted(FUND_GROUP)})")
    return sum(year[g] for g in groups) / len(groups)


def check_fund_map(portfolios: list[Portfolio]) -> None:
    """Refuse a held fund (any state, weight > 0) that is not in FUND_GROUP.
    Signal-only tickers need no group: the stretch uses fixed weights."""
    unmapped = sorted(held_tickers(portfolios) - FUND_GROUP.keys())
    if unmapped:
        raise ValueError(
            f"held fund(s) {unmapped} have no shock group "
            f"(fund map: {', '.join(sorted(FUND_GROUP))})"
        )


def stretch_days(start_year: int, n: int) -> pd.DatetimeIndex:
    """The made-up stretch for real start year `start_year` and an `n`-year
    shock: weekdays (Monday to Friday, holidays included) from the first weekday
    on or after 2 January of start_year - n to 31 December of start_year - 1.
    1 January of the first year is skipped, as a real path's first trading day
    is never 1 January; later years include it when it is a weekday."""
    return pd.bdate_range(
        pd.Timestamp(year=start_year - n, month=1, day=2),
        pd.Timestamp(year=start_year - 1, month=12, day=31),
    )


def _spread(yearly: list[float], days: pd.DatetimeIndex) -> np.ndarray:
    """yearly[k] spread evenly and geometrically over the days of calendar year
    first + k: (1 + r)^(1/n) - 1 on each of its n days, so the year compounds to
    exactly 1 + r (the `cash_leg_returns` convention, year by year)."""
    years = pd.DatetimeIndex(days).year.to_numpy()
    first = int(years[0])
    if sorted(set(years.tolist())) != list(range(first, first + len(yearly))):
        raise ValueError(f"stretch days must cover exactly {len(yearly)} calendar year(s)")
    out = np.empty(len(years))
    for k, r in enumerate(yearly):
        mask = years == first + k
        out[mask] = (1.0 + r) ** (1.0 / mask.sum()) - 1.0
    return out


def stretch_returns(mix: dict[str, float], shock: Shock, days: pd.DatetimeIndex) -> pd.Series:
    """Daily returns of one state's fixed weights `mix` in the stretch,
    rebalanced daily with no costs: the weighted sum of each fund's spread daily
    return. A year therefore does not compound to the weighted sum of the
    yearly returns (it would with a yearly rebalance)."""
    total = np.zeros(len(days))
    for fund, weight in mix.items():
        total = total + weight * _spread([fund_return(fund, y) for y in shock.years], days)
    return pd.Series(total, index=days, dtype=float)


def cash_returns(shock: Shock, days: pd.DatetimeIndex) -> pd.Series:
    """The true-cash leg in the stretch: the `short_bonds` return, spread daily."""
    return pd.Series(
        _spread([y["short_bonds"] for y in shock.years], days), index=days, dtype=float
    )


def stretch_cpi(shock: Shock, start_year: int) -> pd.Series:
    """The stretch's CPI, dated by availability like the real series (month M's
    value on the last day of M+1). Level 100 for November of start_year - N - 1,
    dated 31 December of that year; then per shock year k twelve values (the
    observations December of the year before to November of k, dated 31 January
    to 31 December of k), each the previous one times (1 + inflation_k)^(1/12).
    So the CPI usable on 1 January of k+1 over that of k is 1 + inflation_k, and
    the last value, dated 31 December of start_year - 1, is the end level."""
    first = start_year - len(shock.years)
    dates = [pd.Timestamp(year=first - 1, month=12, day=31)]
    values = [100.0]
    for k, year in enumerate(shock.years):
        step = (1.0 + year["inflation"]) ** (1 / 12)
        for month in range(1, 13):
            dates.append(pd.Timestamp(year=first + k, month=month, day=1) + pd.offsets.MonthEnd(0))
            values.append(values[-1] * step)
    return pd.Series(values, index=pd.DatetimeIndex(dates), name=CPI_SERIES, dtype=float)


def shocked_path(real_cpi: pd.Series, shock: Shock, start_year: int) -> pd.Series:
    """The CPI of one shocked path (the splice): the stretch's CPI dated up to
    and including 31 December of start_year - 1 (the single join date), then the
    real values dated after it times f = stretch end level / the real value dated
    exactly 31 December of start_year - 1 (November's, usable on 1 January of
    start_year). The real 31 December value is dropped; the end level takes its
    place and equals it times f, so no step is added. `real_cpi` must already be
    cut at the data end. Raises "missing CPI" if no real value (non-NaN) is dated
    exactly on the join date: the join is strict, no older value is used."""
    join = pd.Timestamp(year=start_year - 1, month=12, day=31)
    known = real_cpi.dropna()
    if join not in known.index:
        raise ValueError(f"missing CPI: no {CPI_SERIES} value dated {join.date()} for the join")
    synthetic = stretch_cpi(shock, start_year)
    factor = float(synthetic.iloc[-1]) / float(known.loc[join])
    after = real_cpi.loc[real_cpi.index > join] * factor
    spliced: pd.Series = pd.concat([synthetic, after]).rename(CPI_SERIES)
    return spliced


def join_returns(stretch: pd.Series, real: pd.Series) -> pd.Series:
    """The stretch's daily returns followed by the real ones (one path). The
    join charges no extra cost: the real series keeps its own day-one purchase."""
    if not stretch.index[-1] < real.index[0]:
        raise ValueError(
            f"the stretch must end before the real start {pd.Timestamp(real.index[0]).date()}"
        )
    joined: pd.Series = pd.concat([stretch, real])
    return joined
