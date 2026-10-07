"""Tests for the macro overlay (qrl.overlay). Offline; synthetic prices and a
synthetic CPI only. Spec: docs/methodology/macro-overlay.md.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from qrl.core_compare import Candidate, load_core_candidates
from qrl.overlay import load_overlay_config

ROOT = Path(__file__).resolve().parents[1]
SHIPPED = (ROOT / "config" / "overlay.yaml").read_text()
CANDS, _ = load_core_candidates(ROOT / "config" / "core_candidates.yaml")


def _load(tmp_path: Path, text: str, cands=None):
    p = tmp_path / "overlay.yaml"
    p.write_text(text)
    return load_overlay_config(p, cands or CANDS)


def test_shipped_config_loads_with_every_spec_number():
    cfg, sha = load_overlay_config(ROOT / "config" / "overlay.yaml", CANDS)
    raw = (ROOT / "config" / "overlay.yaml").read_bytes()
    assert sha == hashlib.sha256(raw).hexdigest()
    assert cfg.base == {"SPY": 0.25, "TLT": 0.25, "GLD": 0.25, "SHY": 0.25}
    assert cfg.safe == "SHY"
    assert cfg.cap == 0.20
    assert cfg.cost_bps == 5
    assert cfg.trend_assets == ("SPY", "TLT", "GLD")
    assert cfg.trend_sma_days == 210
    assert cfg.trend_move == pytest.approx(0.20 / 3)  # exactly 20/3 points
    assert (cfg.vol_asset, cfg.vol_days, cfg.vol_median_days) == ("SPY", 63, 1260)
    assert (cfg.vol_ratio, cfg.vol_move) == (1.5, 0.05)
    assert (cfg.cpi_series, cfg.inflation_asset) == ("CPIAUCNS", "TLT")
    assert (cfg.inflation_yoy, cfg.inflation_lookback_months) == (0.04, 3)
    assert cfg.inflation_move == 0.05
    assert (cfg.min_sharpe_gain, cfg.max_cagr_shortfall) == (0.05, 0.01)
    assert cfg.null_percentile == 95
    assert (cfg.null_seed, cfg.null_draws) == (20261007, 1000)


def test_config_rejects_wrong_version(tmp_path):
    with pytest.raises(ValueError, match="version"):
        _load(tmp_path, SHIPPED.replace("version: 1", "version: 2"))


def test_config_rejects_missing_field(tmp_path):
    with pytest.raises(ValueError, match="missing or malformed"):
        _load(tmp_path, SHIPPED.replace("  seed: 20261007\n", ""))


def test_config_rejects_a_non_fraction_share(tmp_path):
    with pytest.raises(ValueError, match="move_share_of_cap"):
        _load(tmp_path, SHIPPED.replace('move_share_of_cap: "1/3"', 'move_share_of_cap: "a third"'))


def test_config_rejects_unknown_base(tmp_path):
    with pytest.raises(ValueError, match="not in the candidates file"):
        _load(tmp_path, SHIPPED.replace("base_id: G", "base_id: ZZ"))


def test_config_rejects_switching_base(tmp_path):
    switching = Candidate(
        "G",
        "switching",
        "core_mix",
        {"risk_on": {"SPY": 1.0}, "risk_off": {"SHY": 1.0}, "signal": "SPY", "lookback": 200},
    )
    with pytest.raises(ValueError, match="static core_mix"):
        _load(tmp_path, SHIPPED, [switching])


def test_config_rejects_asset_outside_the_base(tmp_path):
    with pytest.raises(ValueError, match="not in the base mix"):
        _load(tmp_path, SHIPPED.replace("safe_asset: SHY", "safe_asset: IEF"))
