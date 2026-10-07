"""Macro overlay on core G (spec: docs/methodology/macro-overlay.md).

A slow, de-risk-only overlay: three signals (trend, volatility, inflation)
move fixed slices of the static base mix into the safe asset (SHY), capped at
`cap` in total. Signals are read at the close of each month's last trading
day and the weights are held until the next month end; the engine's 1-day
shift handles execution. Pure functions apart from `load_overlay_config`
reading its file; callers inject prices and the availability-dated CPI series
(`qrl.macro.load_macro` without a trading index). Row t uses data up to the
close of day t. Not a REGISTRY strategy: the strategy contract passes prices
only, and the overlay needs CPI.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .core_compare import Candidate
from .macro import align_to_trading_days
from .metrics import TRADING_DAYS

_EPS = 1e-9


@dataclass(frozen=True)
class OverlayConfig:
    base_id: str
    base: dict[str, float]
    safe: str
    cap: float
    cost_bps: float
    trend_assets: tuple[str, ...]
    trend_sma_days: int
    trend_move: float
    vol_asset: str
    vol_days: int
    vol_median_days: int
    vol_ratio: float
    vol_move: float
    cpi_series: str
    inflation_asset: str
    inflation_yoy: float
    inflation_lookback_months: int
    inflation_move: float
    min_sharpe_gain: float
    max_cagr_shortfall: float
    null_percentile: float
    null_seed: int
    null_draws: int


def _base_mix(base_id: str, candidates: list[Candidate]) -> dict[str, float]:
    by_id = {c.id: c for c in candidates}
    if base_id not in by_id:
        raise ValueError(f"overlay base_id {base_id!r} is not in the candidates file")
    cand = by_id[base_id]
    if cand.fn != "core_mix" or cand.params.get("risk_off") is not None:
        raise ValueError(f"overlay base {base_id!r} must be a static core_mix")
    base = {str(t): float(w) for t, w in cand.params["risk_on"].items()}
    if abs(sum(base.values()) - 1.0) > _EPS:
        raise ValueError(f"overlay base {base_id!r} must be fully invested")
    return base


def _share(value: object) -> Fraction:
    """An exact fraction like "1/3" (so 3 x cap/3 is the cap, not 0.2001)."""
    try:
        share = Fraction(str(value))
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(f"trend move_share_of_cap must be a fraction like '1/3', got {value!r}") from exc
    if not 0 < share <= 1:
        raise ValueError(f"trend move_share_of_cap must be in (0, 1], got {value!r}")
    return share


def _parse(doc: dict, base: dict[str, float]) -> OverlayConfig:
    signals, rule, null = doc["signals"], doc["pass_rule"], doc["random_null"]
    trend, vol, infl = signals["trend"], signals["volatility"], signals["inflation"]
    cap = float(doc["cap"])
    return OverlayConfig(
        base_id=str(doc["base_id"]),
        base=base,
        safe=str(doc["safe_asset"]),
        cap=cap,
        cost_bps=float(doc["cost_bps"]),
        trend_assets=tuple(str(a) for a in trend["assets"]),
        trend_sma_days=int(trend["sma_days"]),
        trend_move=cap * float(_share(trend["move_share_of_cap"])),
        vol_asset=str(vol["asset"]),
        vol_days=int(vol["vol_days"]),
        vol_median_days=int(vol["median_days"]),
        vol_ratio=float(vol["ratio"]),
        vol_move=float(vol["move"]),
        cpi_series=str(infl["series"]),
        inflation_asset=str(infl["asset"]),
        inflation_yoy=float(infl["yoy_above"]),
        inflation_lookback_months=int(infl["rising_vs_months_ago"]),
        inflation_move=float(infl["move"]),
        min_sharpe_gain=float(rule["min_sharpe_gain"]),
        max_cagr_shortfall=float(rule["max_cagr_shortfall"]),
        null_percentile=float(rule["null_percentile"]),
        null_seed=int(null["seed"]),
        null_draws=int(null["n_draws"]),
    )


def _check_assets(cfg: OverlayConfig) -> None:
    """Every moved asset and the safe asset are in the base, the safe asset is
    never de-risked, and no asset can lose more than its base weight (so the
    weights can never go negative, even before the cap)."""
    moved = {*cfg.trend_assets, cfg.vol_asset, cfg.inflation_asset}
    missing = sorted((moved | {cfg.safe}) - set(cfg.base))
    if missing:
        raise ValueError(f"overlay assets not in the base mix: {missing}")
    if cfg.safe in moved:
        raise ValueError("the safe asset cannot also be de-risked")
    worst = dict.fromkeys(moved, 0.0)
    for a in cfg.trend_assets:
        worst[a] += cfg.trend_move
    worst[cfg.vol_asset] += cfg.vol_move
    worst[cfg.inflation_asset] += cfg.inflation_move
    over = sorted(a for a, m in worst.items() if m > cfg.base[a] + _EPS)
    if over:
        raise ValueError(f"overlay moves exceed the base weight of: {over}")


def load_overlay_config(
    path: str | Path, candidates: list[Candidate]
) -> tuple[OverlayConfig, str]:
    """Return (config, full sha256 of the raw file bytes). The base mix is read
    from the candidates file (id `base_id`), never duplicated. Raises
    ValueError on malformed YAML, a wrong version, a missing field, a base that
    is not a fully invested static core_mix, or an overlay asset not in it."""
    raw = Path(path).read_bytes()
    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"overlay config is not valid YAML ({exc})") from exc
    if not isinstance(doc, dict) or doc.get("version") != 1:
        raise ValueError("overlay config must be a mapping with `version: 1`")
    try:
        cfg = _parse(doc, _base_mix(str(doc["base_id"]), candidates))
    except (KeyError, TypeError) as exc:
        raise ValueError(f"overlay config is missing or malformed: {exc}") from exc
    _check_assets(cfg)
    return cfg, hashlib.sha256(raw).hexdigest()


def trend_states(close: pd.DataFrame, assets: tuple[str, ...], sma_days: int) -> pd.DataFrame:
    """True while an asset closes below its `sma_days` simple moving average;
    False at or above it, in warm-up or while unpriced (undefined means off)."""
    px = close[list(assets)]
    sma = px.rolling(sma_days, min_periods=sma_days).mean()
    return px < sma


def vol_state(
    close: pd.DataFrame, asset: str, vol_days: int, median_days: int, ratio: float
) -> pd.Series:
    """True while the asset's `vol_days` realized vol (annualized std of daily
    returns) is above `ratio` x its trailing `median_days` median of that same
    vol series; False otherwise, including until both are defined."""
    returns = close[asset].pct_change(fill_method=None)
    vol = returns.rolling(vol_days, min_periods=vol_days).std() * math.sqrt(TRADING_DAYS)
    median = vol.rolling(median_days, min_periods=median_days).median()
    return vol > ratio * median


def inflation_state(
    cpi: pd.Series, index: pd.DatetimeIndex, yoy_above: float, lookback_months: int
) -> pd.Series:
    """True while CPI YoY is above `yoy_above` AND above its value
    `lookback_months` prints earlier, on `index`. False before the first
    defined print and for a missing print (undefined means off).

    `cpi` must be availability-dated on month ends (`qrl.macro.lag_to_availability`
    with macro.yaml's `month_ends` lag), so day t only sees prints published by t.
    `align_to_trading_days` forward-fills the last print, so a stale feed holds
    its last state."""
    cpi = cpi.sort_index()
    if cpi.dropna().empty:
        return pd.Series(False, index=index)
    if not pd.DatetimeIndex(cpi.index).is_month_end.all():
        raise ValueError("CPI must be availability-dated on month ends (macro.yaml month_ends lag)")
    grid = pd.date_range(cpi.index[0], cpi.index[-1], freq=pd.offsets.MonthEnd())
    level = cpi.reindex(grid)
    yoy = level / level.shift(12) - 1
    state = (yoy > yoy_above) & (yoy > yoy.shift(lookback_months))
    return align_to_trading_days(state.astype(float), index).fillna(0.0).astype(bool)


def signal_columns(cfg: OverlayConfig) -> list[str]:
    return [*(f"trend_{a}" for a in cfg.trend_assets), "vol", "inflation"]


def month_end_mask(index: pd.DatetimeIndex) -> np.ndarray:
    """True on the last trading day of each month. The frame's last row is a
    month end only if the next business day falls in a new month, so a day's
    mask never depends on whether later rows exist."""
    if len(index) == 0:
        return np.zeros(0, dtype=bool)
    following = np.append(index[1:].month, (index[-1] + pd.offsets.BDay(1)).month)
    return np.asarray(index.month != following)


def daily_states(close: pd.DataFrame, cpi: pd.Series, cfg: OverlayConfig) -> pd.DataFrame:
    """Every signal on every trading day: True on, False off (undefined is off)."""
    trend = trend_states(close, cfg.trend_assets, cfg.trend_sma_days)
    out = pd.DataFrame({f"trend_{a}": trend[a] for a in cfg.trend_assets}, index=close.index)
    out["vol"] = vol_state(close, cfg.vol_asset, cfg.vol_days, cfg.vol_median_days, cfg.vol_ratio)
    out["inflation"] = inflation_state(
        cpi, pd.DatetimeIndex(close.index), cfg.inflation_yoy, cfg.inflation_lookback_months
    )
    return out


def monthly_states(close: pd.DataFrame, cpi: pd.Series, cfg: OverlayConfig) -> pd.DataFrame:
    """Signal states read at each month's last trading day close."""
    states = daily_states(close, cpi, cfg)
    return states.loc[month_end_mask(pd.DatetimeIndex(states.index))]


def overlay_weights(
    monthly: pd.DataFrame, close: pd.DataFrame, cfg: OverlayConfig
) -> pd.DataFrame:
    """Daily target weights from month-end states. An undefined state counts
    as off. Moves go to the safe asset only; if they sum above `cfg.cap`,
    every move is scaled by cap/sum. Each month end's weights are held until
    the next one. Rows before the first month end, and rows where a base
    asset is unpriced, are NaN."""
    on = monthly.fillna(0.0).astype(float)
    moves = pd.DataFrame(0.0, index=on.index, columns=list(cfg.base))
    for a in cfg.trend_assets:
        moves[a] += on[f"trend_{a}"] * cfg.trend_move
    moves[cfg.vol_asset] += on["vol"] * cfg.vol_move
    moves[cfg.inflation_asset] += on["inflation"] * cfg.inflation_move
    total = moves.sum(axis=1)
    # _EPS: three trend moves of cap/3 sum to the cap up to float rounding; never scale those
    moves = moves.mul((cfg.cap / total.where(total > cfg.cap + _EPS)).fillna(1.0), axis=0)
    w = pd.DataFrame({t: x - moves[t] for t, x in cfg.base.items()}, index=on.index)
    w[cfg.safe] += moves.sum(axis=1)
    daily = w.reindex(close.index).ffill()
    daily[close[list(cfg.base)].isna().any(axis=1)] = np.nan
    return daily


def build_overlay(close: pd.DataFrame, cpi: pd.Series, cfg: OverlayConfig) -> pd.DataFrame:
    return overlay_weights(monthly_states(close, cpi, cfg), close, cfg)
