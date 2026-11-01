"""Stand-in data for the history-grounded scenarios (spec:
docs/methodology/history-scenarios.md, "Stand-in data"). Pure builders and a
panel assembler, plus thin loaders at the end of the file. Every series is cut
at the research end (2018-12-31) right after loading."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import numpy as np
import pandas as pd

from .history_config import HistoryConfig, Leg
from .international import fill_proxy_gaps, splice, yield_proxy_close

DIVIDEND_DAYS = 252  # trading days a year: the daily dividend accrual is yield / 252


def _require_increasing(index: pd.Index, name: str) -> None:
    if not index.is_monotonic_increasing or index.has_duplicates:
        raise ValueError(f"{name} index must be strictly increasing (sorted, no duplicates)")


def interpolate_monthly(monthly: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    """Each monthly figure placed on its month's last trading day in `index`,
    the days between filled at a constant daily rate (geometric interpolation),
    so each month end equals that month's figure. NaN before the first and
    after the last month end. `monthly` is indexed by any date in the month.

    Each figure is a monthly average placed on the month end, and the days
    before it are interpolated toward that NEXT month-end anchor: an accepted
    lookahead for a stand-in (see the methodology caveat). If `index` ends
    mid-month, the last month's figure lands on the last day of `index`, which
    is not its real month end. A month missing from `monthly` is bridged
    geometrically between its neighbours. Raises ValueError on a non-positive
    figure, an unsorted or duplicated `index`, or two figures in one month."""
    _require_increasing(index, "index")
    if (monthly <= 0).any():
        raise ValueError("monthly figures must be positive (geometric interpolation)")
    figure = pd.Series(
        monthly.to_numpy(dtype=float), index=pd.PeriodIndex(monthly.index, freq="M")
    )
    if figure.index.has_duplicates:
        raise ValueError("monthly figures have more than one figure in a month")
    last_day = pd.Series(index, index=index.to_period("M")).groupby(level=0).max()
    anchors = figure.reindex(last_day.index).dropna()
    logs = pd.Series(np.nan, index=index)
    logs.loc[last_day.loc[anchors.index].to_numpy()] = np.log(anchors.to_numpy())
    filled = logs.interpolate(method="linear", limit_area="inside")
    return pd.Series(np.exp(filled.to_numpy(dtype=float)), index=index)


def sp_with_dividends(price: pd.Series, annual_yield: pd.Series) -> pd.Series:
    """The S&P 500 price plus its dividend yield accrued daily: daily return =
    price return + yield / 252, starting at 1.0. `annual_yield` is the monthly
    series (any date in the month, fraction a year); each day uses the previous
    month's value, known at the start of its month. Raises ValueError on a
    empty, unsorted or duplicated price, a missing price or yield, or two
    yield figures in one month."""
    _require_increasing(price.index, "price")
    if len(price) == 0:
        raise ValueError("the S&P 500 price is empty")
    if price.isna().any():
        raise ValueError("the S&P 500 price has missing days")
    by_month = pd.Series(
        annual_yield.to_numpy(dtype=float), index=pd.PeriodIndex(annual_yield.index, freq="M")
    )
    if by_month.index.has_duplicates:
        raise ValueError("dividend yield has more than one figure in a month")
    previous = pd.DatetimeIndex(price.index).to_period("M") - 1
    daily = pd.Series(by_month.reindex(previous).to_numpy(), index=price.index)
    if daily.isna().any():
        raise ValueError(f"dividend yield missing on {int(daily.isna().sum())} days")
    returns = price.pct_change(fill_method=None) + daily / DIVIDEND_DAYS
    returns.iloc[0] = 0.0
    return (1.0 + returns).cumprod()


FUNDS = ("SPY", "QQQ", "SHY", "IEF", "TLT", "GLD", "RSP")  # every ticker the 12 portfolios use
SP_TR = "^SP500TR"
NASDAQ = "^IXIC"


@dataclass(frozen=True)
class RawData:
    """Raw series, already cut at the data end. `open`/`close`: Yahoo frames,
    one column per ticker; `fred`: yields in percent by FRED id; `shiller_yield`
    and `worldbank_gold`: monthly series (any date in the month)."""

    open: pd.DataFrame
    close: pd.DataFrame
    fred: dict[str, pd.Series]
    shiller_yield: pd.Series
    worldbank_gold: pd.Series


@dataclass(frozen=True)
class Link:
    """A stand-in and the series that follows it, to be checked where they
    overlap. `frequency` "monthly": month-end (`last`) or monthly mean (`mean`)
    values, per side, then month-to-month returns."""

    label: str
    standin: pd.Series
    fund: pd.Series
    frequency: str  # "daily" | "monthly"
    fund_how: str = "last"  # monthly only: "last" | "mean"


@dataclass(frozen=True)
class Panel:
    open: pd.DataFrame  # FUNDS columns, panel start to data end
    close: pd.DataFrame
    own_start: dict[str, pd.Timestamp]  # first real price of each fund
    gold_futures_start: pd.Timestamp  # first GC=F close
    links: tuple[Link, ...]


def _leg_days(leg: Leg, lag_days: int, index: pd.DatetimeIndex) -> pd.Series:
    """Days a later leg's returns are used: its window plus the `lag_days + 1`
    trading days after `end`, while the base leg's lagged yield is still catching
    up (its first fresh value would otherwise be a spurious jump)."""
    if leg.start is None or leg.end is None:
        raise ValueError(f"leg {leg.fred} has no window")
    after = int(index.searchsorted(leg.end, side="right"))
    in_use = (index >= leg.start) & (np.arange(len(index)) < after + lag_days + 1)
    return pd.Series(in_use, index=index)


def treasury_proxy(
    legs: tuple[Leg, ...], yields: dict[str, pd.Series], lag_days: int, index: pd.DatetimeIndex
) -> pd.Series:
    """Total-return price index for a Treasury fund: `international.yield_proxy_close`
    of the base leg, with each later leg's daily returns used inside its window,
    so the joined price has no jump. A single leg is the plain proxy."""
    closes = {
        leg.fred: yield_proxy_close(yields[leg.fred], leg.duration, lag_days, index)
        for leg in legs
    }
    base = closes[legs[0].fred]
    if len(legs) == 1:
        return base
    returns = base.pct_change(fill_method=None)
    for leg in legs[1:]:
        leg_returns = closes[leg.fred].pct_change(fill_method=None)
        # A leg has no return on its first yield day(s); the base return stands in there.
        use = _leg_days(leg, lag_days, index) & leg_returns.notna()
        returns = returns.where(~use, leg_returns)
    chained = (1.0 + returns.fillna(0.0)).cumprod()
    return chained.where(base.notna())


def _need(frame: pd.DataFrame, columns: list[str]) -> None:
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise ValueError(f"missing raw series: {missing}")


def _standins(
    raw: RawData, cfg: HistoryConfig, index: pd.DatetimeIndex
) -> tuple[dict[str, pd.Series], list[Link]]:
    """Per fund, the stand-in used before its first real price, and the links to check."""
    close = raw.close.reindex(index)
    gspc = close[cfg.index_ticker]
    sp_div = sp_with_dividends(gspc, raw.shiller_yield)
    spy_chain = splice(splice(sp_div, close[SP_TR]), close["SPY"])
    gold = interpolate_monthly(raw.worldbank_gold, index)
    standins = {
        "SPY": splice(sp_div, close[SP_TR]),
        "QQQ": close[NASDAQ],
        "GLD": splice(gold, close[cfg.gold_futures]),
        "RSP": spy_chain,
    }
    links = [
        Link("SPY: ^SP500TR against SPY", close[SP_TR], close["SPY"], "daily"),
        Link("SPY: S&P 500 + Shiller dividends against ^SP500TR", sp_div, close[SP_TR], "daily"),
        Link("QQQ: ^IXIC against QQQ", close[NASDAQ], close["QQQ"], "daily"),
        Link(
            "Gold: World Bank monthly figure against the monthly mean of GC=F",
            raw.worldbank_gold,
            close[cfg.gold_futures],
            "monthly",
            "mean",
        ),
        Link(
            "Gold: month-end GC=F against month-end GLD",
            close[cfg.gold_futures],
            close[cfg.gold_fund],
            "monthly",
        ),
    ]
    for fund, legs in cfg.treasury.items():
        proxy = treasury_proxy(legs, raw.fred, cfg.yield_lag_days, index)
        standins[fund] = proxy
        # bond checks are on month-end returns (spec); SPY and QQQ stay daily. The
        # overlap with the fund starts in 2002, where the chained proxy is the last
        # leg's own proxy (DGS2 for SHY), so the check compares the fund with the
        # DGS2 piece only; the DGS1 piece predates SHY.
        links.append(Link(f"{fund}: yield proxy against {fund}", proxy, close[fund], "monthly"))
    return standins, links


def assemble_panel(raw: RawData, cfg: HistoryConfig, end: pd.Timestamp) -> Panel:
    """Daily open/close for every fund on the S&P 500's trading days from the
    panel start to `end`. Each fund's own prices from its first trading day; before
    that its stand-in (spliced without a jump), in the order SPY: S&P 500 plus
    Shiller dividends, then ^SP500TR, then SPY; GLD: World Bank, then GC=F, then
    GLD; RSP: the SPY chain. On every stand-in day the open is the previous close.
    Interior stand-in gaps of at most `cfg.max_gap_days` are forward-filled
    (`international.fill_proxy_gaps`), longer ones raise; a fund unpriced on any
    panel day raises."""
    _need(raw.close, [cfg.index_ticker, SP_TR, NASDAQ, cfg.gold_futures, *FUNDS])
    gspc = raw.close[cfg.index_ticker].dropna()
    days = pd.DatetimeIndex(gspc.index[(gspc.index >= cfg.lead_in_start) & (gspc.index <= end)])
    standins, links = _standins(raw, cfg, days)
    fund_close = raw.close.reindex(days)
    fund_open = raw.open.reindex(days)
    close = pd.DataFrame(index=days, columns=list(FUNDS), dtype=float)
    open_ = pd.DataFrame(index=days, columns=list(FUNDS), dtype=float)
    own_start: dict[str, pd.Timestamp] = {}
    for fund in FUNDS:
        first = cast("pd.Timestamp | None", fund_close[fund].first_valid_index())
        if first is None:
            raise ValueError(f"{fund}: no prices")
        own_start[fund] = pd.Timestamp(first)
        close[fund] = splice(standins[fund], fund_close[fund]).reindex(days)
        open_[fund] = close[fund].shift(1).where(days < first, fund_open[fund])
    start = days[days >= cfg.panel_start][0]
    open_, close = open_.loc[start:], close.loc[start:]
    open_, close = fill_proxy_gaps(open_, close, list(FUNDS), own_start, limit=cfg.max_gap_days)
    for fund in FUNDS:
        bad = close.index[close[fund].isna() | open_[fund].isna()]
        if len(bad):
            raise ValueError(
                f"{fund}: not priced on {len(bad)} panel days from {bad[0].date()} "
                f"(a stand-in must reach the panel start {start.date()}; "
                f"real-fund days must be complete)"
            )
    gold_start = cast("pd.Timestamp | None", fund_close[cfg.gold_futures].first_valid_index())
    if gold_start is None:
        raise ValueError(f"{cfg.gold_futures}: no prices")
    return Panel(open_, close, own_start, gold_start, tuple(links))


MIN_DAILY_OBS = 20
MIN_MONTHLY_OBS = 12


@dataclass(frozen=True)
class CheckResult:
    label: str
    frequency: str
    start: str  # first common return date (YYYY-MM-DD, or YYYY-MM for monthly)
    end: str
    n: int
    correlation: float


def _monthly(series: pd.Series, how: str) -> pd.Series:
    # The first GC=F or GLD month may be partial (the mean or last close covers only
    # the days it traded); accepted for a stand-in check, which spans many months.
    grouped = series.dropna().groupby(pd.DatetimeIndex(series.dropna().index).to_period("M"))
    return grouped.mean() if how == "mean" else grouped.last()


def _returns(link: Link, end: pd.Timestamp) -> tuple[pd.Series, pd.Series]:
    if link.frequency == "daily":
        a = link.standin.loc[:end].pct_change(fill_method=None)
        b = link.fund.loc[:end].pct_change(fill_method=None)
        return a, b
    if link.frequency != "monthly":
        raise ValueError(f"unknown check frequency {link.frequency!r}")
    a = _monthly(link.standin.loc[:end], "last").pct_change()
    b = _monthly(link.fund.loc[:end], link.fund_how).pct_change()
    return a, b


def _check(link: Link, end: pd.Timestamp) -> CheckResult:
    a, b = _returns(link, end)
    both = pd.concat([a, b], axis=1, join="inner").dropna()
    minimum = MIN_DAILY_OBS if link.frequency == "daily" else MIN_MONTHLY_OBS
    if len(both) < minimum:
        raise ValueError(f"{link.label}: overlap of {len(both)} returns is below {minimum}")
    corr = float(both.iloc[:, 0].corr(both.iloc[:, 1]))
    return CheckResult(
        link.label,
        link.frequency,
        str(both.index[0])[:10],
        str(both.index[-1])[:10],
        len(both),
        corr,
    )


def run_checks(
    links: list[Link] | tuple[Link, ...], end: pd.Timestamp, bar: float
) -> list[CheckResult]:
    """Correlation of each stand-in's returns with the series that follows it,
    over their whole overlap up to `end`. Raises ValueError, listing every link
    below `bar` (a NaN correlation fails), so no report is written."""
    results = [_check(link, end) for link in links]
    failed = [r for r in results if not r.correlation >= bar]
    if failed:
        listing = "; ".join(f"{r.label}: {r.correlation:.4f}" for r in failed)
        raise ValueError(f"stand-in check below the {bar} bar: {listing}")
    return results
