"""Tests for qrl.history_config (docs/methodology/history-scenarios.md). Offline."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest
import yaml

from qrl.history_config import load_history_config

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "history.yaml"


def _variant(tmp_path: Path, old: str, new: str) -> Path:
    text = CONFIG.read_text(encoding="utf-8")
    assert old in text
    path = tmp_path / "history.yaml"
    path.write_text(text.replace(old, new), encoding="utf-8")
    return path


def test_config_loads_as_pre_registered():
    cfg = load_history_config(CONFIG)
    assert cfg.sha256 == hashlib.sha256(CONFIG.read_bytes()).hexdigest()
    assert cfg.index_ticker == "^GSPC"
    assert cfg.threshold == 0.15
    assert cfg.episode_start == pd.Timestamp("1971-01-01")
    assert cfg.horizon_years == 10
    assert cfg.portfolios == (
        "A", "B", "C", "D", "E", "F", "G", "CASH", "G-EW", "AG", "G-CASH", "A-CASH",
    )  # fmt: skip
    assert cfg.rates == (0.02, 0.033, 0.04, 0.05)
    assert cfg.income_years == (5, 10)
    assert cfg.min_correlation == 0.95
    assert cfg.max_gap_days == 1
    assert set(cfg.treasury) == {"SHY", "IEF", "TLT"}


def test_tlt_has_a_switch_window_for_the_second_leg():
    legs = load_history_config(CONFIG).treasury["TLT"]
    assert [leg.fred for leg in legs] == ["DGS20", "DGS30"]
    assert legs[0].start is None
    assert legs[1].start == pd.Timestamp("1987-01-01")
    assert legs[1].end == pd.Timestamp("1993-09-30")


def test_shy_switches_from_dgs1_to_dgs2_on_the_first_dgs2_date():
    legs = load_history_config(CONFIG).treasury["SHY"]
    assert [leg.fred for leg in legs] == ["DGS1", "DGS2"]
    assert legs[0].start is None
    assert legs[1].start == pd.Timestamp("1976-06-01")
    assert legs[1].end == pd.Timestamp("2018-12-31")


def test_every_fred_leg_has_a_first_date_bound():
    cfg = load_history_config(CONFIG)
    legs = {leg.fred for legs in cfg.treasury.values() for leg in legs}
    assert legs <= set(cfg.fred)


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("version: 1", "version: 2", "version"),
        ("threshold: 0.15", "threshold: 1.5", "threshold"),
        ("min_correlation: 0.95", "min_correlation: 0", "min_correlation"),
        ("max_gap_days: 1", "max_gap_days: -1", "max_gap_days"),
        ("withdrawal_rates: [0.02, 0.033, 0.04, 0.05]", "withdrawal_rates: []", "withdrawal_rates"),
        ("income_horizons_years: [5, 10]", "income_horizons_years: [0]", "income_horizons_years"),
    ],
)
def test_bad_values_are_refused(tmp_path, old, new, message):
    with pytest.raises(ValueError, match=message):
        load_history_config(_variant(tmp_path, old, new))


def test_missing_key_is_refused(tmp_path):
    doc = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    del doc["min_correlation"]
    path = tmp_path / "history.yaml"
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="missing key"):
        load_history_config(path)


def test_panel_starts_on_or_after_the_episode_data_and_the_lead_in_precedes_it():
    cfg = load_history_config(CONFIG)
    assert cfg.lead_in_start < cfg.panel_start


def test_a_second_leg_without_a_window_is_refused(tmp_path):
    path = _variant(tmp_path, ', start: "1987-01-01", end: "1993-09-30"}', "}")
    with pytest.raises(ValueError, match="window"):
        load_history_config(path)
