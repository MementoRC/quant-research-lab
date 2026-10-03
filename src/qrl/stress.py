"""Stress scenarios: a DIAGNOSTIC of how much the current portfolio loses
under historical shock windows and pre-registered hypothetical shocks,
against the profile's max-drawdown cap. It forecasts nothing, tunes nothing
and selects nothing (spec: docs/superpowers/specs/2026-10-03-stress-scenarios-design.md).

Pure functions only: callers inject data and configs. Never slices the
holdout: windows ending on/after the holdout start are refused at load, and
replay frames are truncated by index at the window end.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

from .engine import run_backtest
from .metrics import drawdown
from .periods import period_bounds

SHOCK_CLASSES = ("equity", "gold")


class DataUnavailable(Exception):  # noqa: N818 (name fixed by the review spec)
    """Price data cannot support a scenario; the cell is reported `unavailable`.
    Anything else (a bug, a malformed frame) propagates and fails the run."""


@dataclass(frozen=True)
class Window:
    name: str
    start: pd.Timestamp
    end: pd.Timestamp
    replay: bool


@dataclass(frozen=True)
class Hypothetical:
    name: str
    shocks: dict[str, float]


@dataclass(frozen=True)
class StressConfig:
    windows: list[Window]
    hypotheticals: list[Hypothetical]
    max_report_age_days: int


def load_stress_config(path: str | Path, holdout_start: pd.Timestamp) -> tuple[StressConfig, str]:
    """Return (config, full sha256 of the raw file bytes). Raises ValueError
    on a window reaching the holdout, start >= end, a bad date, an unknown
    shock class, a shock <= -1, or a duplicate scenario name."""
    raw = Path(path).read_bytes()
    doc = yaml.safe_load(raw)
    for key in ("windows", "hypotheticals", "max_report_age_days"):
        if not isinstance(doc, dict) or key not in doc:
            raise ValueError(f"stress config is missing required key `{key}`")

    windows = []
    for w in doc["windows"]:
        start, end = pd.Timestamp(w["start"]), pd.Timestamp(w["end"])
        if start >= end:
            raise ValueError(f"window {w['name']}: start must be before end")
        if end >= holdout_start:
            raise ValueError(
                f"window {w['name']} reaches the sealed holdout (starts {holdout_start.date()})"
            )
        windows.append(Window(str(w["name"]), start, end, bool(w["replay"])))

    hypotheticals = []
    for h in doc["hypotheticals"]:
        shocks = {k: float(v) for k, v in h.items() if k != "name"}
        unknown = set(shocks) - set(SHOCK_CLASSES)
        if unknown:
            raise ValueError(f"hypothetical {h['name']}: unknown classes {sorted(unknown)}")
        missing = set(SHOCK_CLASSES) - set(shocks)
        if missing:
            raise ValueError(f"hypothetical {h['name']}: missing classes {sorted(missing)}")
        if any(v <= -1 for v in shocks.values()):
            raise ValueError(f"hypothetical {h['name']}: a shock must be above -1 (-100%)")
        hypotheticals.append(Hypothetical(str(h["name"]), shocks))

    names = [w.name for w in windows] + [h.name for h in hypotheticals]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise ValueError(f"duplicate scenario names: {dupes}")

    cfg = StressConfig(windows, hypotheticals, int(doc["max_report_age_days"]))
    return cfg, hashlib.sha256(raw).hexdigest()


GOLD_TICKERS = frozenset({"GLD"})


def asset_class(ticker: str) -> str:
    return "gold" if ticker in GOLD_TICKERS else "equity"


def window_drawdown(returns: pd.Series) -> float:
    """Worst peak-to-trough loss (positive fraction) of an equity curve that
    starts at 1.0 on the window's first day: a 0.0 return is prepended so a
    first-day loss counts (`qrl.metrics.drawdown`'s peak excludes the start)."""
    r = pd.concat([pd.Series([0.0]), returns.reset_index(drop=True)], ignore_index=True)
    return float(-drawdown(r).min())


def hypothetical_loss(weights: pd.Series, hyp: Hypothetical) -> float:
    """Single-step loss = -sum(weight x class shock); cash (unallocated) is 0%.
    Negative means a gain."""
    w = weights[weights > 0]
    return float(-sum(wt * hyp.shocks.get(asset_class(t), 0.0) for t, wt in w.items()))


EQUITY_PROXY = "SPY"


def frozen_loss(weights: pd.Series, close: pd.DataFrame, window: Window) -> tuple[float, dict]:
    """Buy `weights` at the window's first close, hold without rebalancing,
    return (worst drawdown inside the window, detail). A ticker with no price
    at the window's first day is replaced per class: equity -> SPY, gold ->
    cash. A position priced at the start but with later gaps is carried at
    its last price (forward-fill). Raises DataUnavailable if the window has
    no prices, or SPY is needed but unpriced."""
    px = close.loc[window.start : window.end]
    if px.empty:
        raise DataUnavailable(f"no prices in window {window.name}")
    first = px.iloc[0]
    w = weights[weights > 0]
    proxied = dict.fromkeys(SHOCK_CLASSES, 0.0)
    value = pd.Series(1.0 - float(w.sum()), index=px.index)  # cash
    for ticker, wt in w.items():
        if ticker in px.columns and pd.notna(first[ticker]):
            path = px[ticker].ffill()
        else:
            cls = asset_class(ticker)
            proxied[cls] += float(wt)
            if cls == "gold":
                value += wt  # gold before GLD existed -> cash
                continue
            if EQUITY_PROXY not in px.columns or pd.isna(first[EQUITY_PROXY]):
                raise DataUnavailable(
                    f"{EQUITY_PROXY} unpriced at {window.name} start; cannot proxy {ticker}"
                )
            path = px[EQUITY_PROXY].ffill()
        value += wt * path / path.iloc[0]
    return window_drawdown(value.pct_change().iloc[1:]), {"proxied_share": proxied}


WARMUP = pd.DateOffset(years=2)  # >= regime_pullback's 250-day lookback; see spec


@dataclass(frozen=True)
class PortfolioDef:
    """A portfolio to stress. `build(data, sleeve_keep)` returns COMBINED
    target weights (fractions of total capital) for the frames in `data`,
    using only `sleeve_keep` from the sleeve's universe."""

    name: str
    build: Callable[[dict[str, pd.DataFrame], list[str]], pd.DataFrame]
    core_tickers: list[str]
    sleeve_universe: list[str] = field(default_factory=list)
    candidate: bool = False  # True if a searched paper-track candidate is in the sleeve


def priced(close: pd.DataFrame, tickers: list[str]) -> list[str]:
    """Tickers with a price on every row of `close`."""
    return [t for t in tickers if t in close.columns and bool(close[t].notna().all())]


def replay_loss(
    data: dict[str, pd.DataFrame], portfolio: PortfolioDef, window: Window
) -> tuple[float, dict]:
    """Run the portfolio's rules through the window: frames are truncated by
    index at the window end (nothing later enters) and start WARMUP before
    the window start. Returns (worst drawdown inside the window, detail).
    Sleeve tickers not priced on every day are dropped; an unpriced core
    ticker, a truncated warm-up, or an empty in-window return series raises
    DataUnavailable (the cell becomes `unavailable`)."""
    warm_start = window.start - WARMUP
    frames = {k: v.loc[warm_start : window.end] for k, v in data.items()}
    close = frames["close"]
    if close.empty or close.index[0] > warm_start + pd.Timedelta(days=7):
        raise DataUnavailable(f"warm-up truncated for {window.name}: data starts too late")
    if priced(close, portfolio.core_tickers) != list(portfolio.core_tickers):
        raise DataUnavailable(f"core not fully priced over warm-up + {window.name}")
    keep = priced(close, portfolio.sleeve_universe)
    weights = portfolio.build(frames, keep)
    cols = list(weights.columns)
    try:
        result = run_backtest(frames["open"][cols], close[cols], weights)
    except ValueError as exc:
        # Prefix of the message raised by src/qrl/engine.py ("Missing price for a
        # held position at ..."); engine.py is locked, so match its text here.
        if str(exc).startswith("Missing price"):
            raise DataUnavailable(str(exc)) from exc
        raise
    returns = result.returns.loc[window.start : window.end]
    if returns.empty:
        raise DataUnavailable(f"no returns inside {window.name}")
    loss = window_drawdown(returns)
    n = len(portfolio.sleeve_universe)
    dropped = n - len(keep)
    return loss, {"sleeve_dropped": dropped, "sleeve_dropped_share": dropped / n if n else 0.0}


@dataclass
class Cell:
    portfolio: str
    scenario: str
    mode: str  # replay | frozen | hypothetical
    label: str
    loss: float | None
    breach: bool | None
    detail: dict
    unavailable: str | None = None


def _overlaps(window: Window, criteria: dict, period: str) -> bool:
    start, end = period_bounds(criteria, period)
    return (end is None or window.start <= end) and (start is None or window.end >= start)


def replay_label(candidate: bool, window: Window, criteria: dict) -> str:
    """`clean` for the core alone (a baseline, never searched); for a
    portfolio holding a searched candidate, which selection data the window
    falls in."""
    if not candidate:
        return "clean"
    if _overlaps(window, criteria, "research"):
        return "in-sample"
    if _overlaps(window, criteria, "validation"):
        return "validation-seen"
    return "out-of-sample"


def _cell(portfolio: str, scenario: str, mode: str, label: str, run, max_drawdown: float) -> Cell:
    try:
        loss, detail = run()
    except DataUnavailable as exc:  # missing data -> reported, never dropped
        return Cell(portfolio, scenario, mode, label, None, None, {}, unavailable=str(exc))
    return Cell(portfolio, scenario, mode, label, loss, bool(loss > max_drawdown), detail)


def _latest_weights(
    p: PortfolioDef, data: dict[str, pd.DataFrame]
) -> tuple[pd.Series | None, str | None, int]:
    """(latest weight row or None, reason if None, sleeve tickers dropped by
    today's tradable set). NaN in the row means the weights are unusable."""
    keep = priced(data["close"].tail(1), p.sleeve_universe)
    dropped = len(p.sleeve_universe) - len(keep)
    try:
        latest = p.build(data, keep).iloc[-1]
    except DataUnavailable as exc:
        return None, str(exc), dropped
    if latest.isna().any():
        bad = sorted(latest.index[latest.isna()])
        return None, f"latest weights contain NaN for {bad}", dropped
    return latest, None, dropped


def run_stress(
    cfg: StressConfig,
    portfolios: list[PortfolioDef],
    data: dict[str, pd.DataFrame],
    max_drawdown: float,
    criteria: dict,
) -> list[Cell]:
    """Every portfolio x scenario x applicable mode. `data` holds frames
    through today; only the frozen/hypothetical modes use the latest weight
    row built from it."""
    cells: list[Cell] = []
    for p in portfolios:
        latest, reason, dropped = _latest_weights(p, data)

        def static(fn, latest=latest, reason=reason, dropped=dropped):
            """Wrap a latest-weights measure: unavailable if the weights are,
            and record how many sleeve tickers today's tradable set dropped."""

            def run():
                if latest is None:
                    raise DataUnavailable(reason)
                loss, detail = fn(latest)
                return loss, {**detail, "latest_sleeve_dropped": dropped}

            return run

        for w in cfg.windows:
            if w.replay:
                cells.append(
                    _cell(
                        p.name,
                        w.name,
                        "replay",
                        replay_label(p.candidate, w, criteria),
                        lambda p=p, w=w: replay_loss(data, p, w),
                        max_drawdown,
                    )
                )
            cells.append(
                _cell(
                    p.name,
                    w.name,
                    "frozen",
                    "current-weights",
                    static(lambda lt, w=w: frozen_loss(lt, data["close"], w)),
                    max_drawdown,
                )
            )
        for h in cfg.hypotheticals:
            cells.append(
                _cell(
                    p.name,
                    h.name,
                    "hypothetical",
                    "current-weights",
                    static(lambda lt, h=h: (hypothetical_loss(lt, h), {})),
                    max_drawdown,
                )
            )
    return cells


def stress_config_paths(root: Path) -> dict[str, Path]:
    """Configs whose change makes a stress report stale."""
    cfg = Path(root) / "config"
    return {
        name: cfg / name for name in ("stress.yaml", "portfolio.yaml", "paper.yaml", "profile.yaml")
    }


def file_hashes(paths: dict[str, Path]) -> dict[str, str]:
    """Full sha256 of each file's raw bytes."""
    return {name: hashlib.sha256(Path(p).read_bytes()).hexdigest() for name, p in paths.items()}


def _utc(ts: pd.Timestamp) -> pd.Timestamp:
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def stress_warnings(
    report: dict | None, current_hashes: dict[str, str], now: pd.Timestamp
) -> list[str]:
    """Daily-check warning lines for a saved stress report. Never raises on
    a stale or breaching report; it only describes it."""
    if report is None:
        return ["stress report missing: run `pixi run stress`"]
    out = []
    age = (_utc(now) - _utc(pd.Timestamp(report["generated_at"]))).days
    if age > report["max_report_age_days"]:
        out.append(
            f"stress report is {age} days old (max {report['max_report_age_days']}): "
            "re-run `pixi run stress`"
        )
    changed = sorted(k for k, h in current_hashes.items() if report["hashes"].get(k) != h)
    if changed:
        out.append(f"stress report stale, changed since it was made: {', '.join(changed)}")
    for c in report["cells"]:
        if c["breach"]:
            out.append(
                f"BREACH {c['portfolio']} / {c['scenario']} ({c['mode']}): "
                f"loss {c['loss']:.1%} > cap {report['max_drawdown']:.0%}"
            )
    return out
