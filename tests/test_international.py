"""Tests for qrl.international (docs/methodology/international-test.md).
Synthetic data only; nothing here downloads."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from qrl.international import load_international_config

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "international.yaml"


def _cfg():
    return load_international_config(CONFIG)[0]


def _variant(tmp_path: Path, old: str, new: str) -> Path:
    text = CONFIG.read_text(encoding="utf-8")
    assert old in text
    path = tmp_path / "international.yaml"
    path.write_text(text.replace(old, new), encoding="utf-8")
    return path


def test_config_loads_as_pre_registered():
    cfg, sha = load_international_config(CONFIG)
    assert len(sha) == 64
    assert cfg.set_names == ["main", "reserve_1", "reserve_2"]
    assert cfg.market_set("main").markets == ("EWJ", "EWU", "EWG", "EWC", "EWA", "EWL", "EWQ")
    assert [s.min_pass for s in cfg.sets] == [5, 4, 3]
    assert cfg.windows == (
        (pd.Timestamp("1997-01-01"), pd.Timestamp("2004-12-31")),
        (pd.Timestamp("2023-01-01"), None),
    )
    assert cfg.min_scored_days == 500
    assert cfg.treasury == {"SHY": ("DGS2", 1.9), "IEF": ("DGS10", 7.5), "TLT": ("DGS20", 17.0)}
    assert cfg.funds == ["GLD", "IEF", "SHY", "TLT"]
    assert cfg.covered == frozenset({"core_trend", "core_mix"})
    assert cfg.cash_fred == "DTB3"
    assert cfg.fred_ids == ["DGS10", "DGS2", "DGS20", "DTB3"]
    assert cfg.gold_ticker == "GC=F"
    assert not hasattr(cfg, "equity_leg")
    assert not hasattr(cfg, "gold_lag_days")


def test_unknown_set_is_refused():
    with pytest.raises(ValueError, match="unknown market set"):
        _cfg().market_set("nicer_one")


def test_window_overlapping_excluded_years_is_refused(tmp_path):
    path = _variant(tmp_path, 'end: "2004-12-31"', 'end: "2005-06-30"')
    with pytest.raises(ValueError, match="excluded"):
        load_international_config(path)


def test_market_repeated_across_sets_is_refused(tmp_path):
    path = _variant(tmp_path, "markets: [EWN,", "markets: [EWJ,")
    with pytest.raises(ValueError, match="repeats"):
        load_international_config(path)


def test_min_pass_above_set_size_is_refused(tmp_path):
    path = _variant(tmp_path, "min_pass: 3", "min_pass: 5")
    with pytest.raises(ValueError, match="min_pass"):
        load_international_config(path)
