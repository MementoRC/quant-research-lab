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
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import yaml

from .core_compare import Candidate

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
