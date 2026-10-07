"""Tests for the macro overlay's spell-shuffle null (qrl.overlay_null).
Offline; synthetic data only. Spec: docs/methodology/macro-overlay.md.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import pandas as pd

from qrl.core_compare import load_core_candidates
from qrl.criteria import load_criteria
from qrl.data import synthetic_prices
from qrl.macro import lag_to_availability, load_macro_config
from qrl.overlay import load_overlay_config, monthly_states
from qrl.overlay_null import null_improvements, shuffle_spells, shuffle_states

ROOT = Path(__file__).resolve().parents[1]
CANDS, _ = load_core_candidates(ROOT / "config" / "core_candidates.yaml")
CFG, _ = load_overlay_config(ROOT / "config" / "overlay.yaml", CANDS)
CRITERIA = load_criteria(ROOT / "config" / "criteria.yaml")[0]
CPI_LAG = load_macro_config(ROOT / "config" / "macro.yaml")["series"]["CPIAUCNS"]["lag"]
MONTHS = pd.date_range("2000-01-31", periods=24, freq=pd.offsets.MonthEnd())
SERIES = pd.Series(
    [np.nan] * 4 + [0, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0, 1, 1, 0, 1, 1, 1, 1, 0, 0],
    index=MONTHS,
    dtype=float,
)


def _runs(values: np.ndarray) -> tuple[list[int], list[int]]:
    """(sorted on-spell lengths, sorted off-spell lengths)."""
    change = np.flatnonzero(np.diff(values)) + 1
    bounds = np.concatenate([[0], change, [len(values)]])
    lengths, kinds = np.diff(bounds), values[bounds[:-1]]
    return sorted(lengths[kinds == 1].tolist()), sorted(lengths[kinds == 0].tolist())


def test_shuffle_preserves_on_fraction_spell_lengths_and_undefined_positions():
    rng = np.random.default_rng(1)
    for _ in range(50):
        out = shuffle_spells(SERIES, rng)
        assert out.isna().equals(SERIES.isna())
        assert out.dropna().mean() == SERIES.dropna().mean()
        assert _runs(out.dropna().to_numpy()) == _runs(SERIES.dropna().to_numpy())


def test_shuffle_is_seeded_and_actually_reorders():
    a = shuffle_spells(SERIES, np.random.default_rng(7))
    b = shuffle_spells(SERIES, np.random.default_rng(7))
    assert a.equals(b)
    rng = np.random.default_rng(7)
    assert any(not shuffle_spells(SERIES, rng).equals(SERIES) for _ in range(20))


def test_shuffle_states_leaves_rows_before_start_untouched():
    frame = pd.DataFrame({"a": SERIES, "b": SERIES.shift(1)})
    start = MONTHS[10]
    out = shuffle_states(frame, np.random.default_rng(0), start)
    pd.testing.assert_frame_equal(out.loc[: MONTHS[9]], frame.loc[: MONTHS[9]])


def test_shuffle_states_accepts_the_bool_states_of_the_signal_layer():
    frame = pd.DataFrame({"a": SERIES.fillna(0.0).astype(bool)})
    out = shuffle_states(frame, np.random.default_rng(0), MONTHS[4])
    assert out["a"].sum() == frame["a"].sum()


def test_null_improvements_are_seeded_and_sized():
    open_, close = synthetic_prices(["GLD", "SHY", "SPY", "TLT"], "1999-01-01", "2018-12-31")
    obs = pd.date_range("1990-01-01", "2018-10-01", freq="MS")
    cpi = lag_to_availability(pd.Series(100 * 1.02 ** (np.arange(len(obs)) / 12), index=obs), CPI_LAG)
    cfg = dataclasses.replace(CFG, null_draws=4)
    monthly = monthly_states(close, cpi, cfg)
    a = null_improvements(monthly, open_, close, cfg, CRITERIA, "research", 0.5)
    b = null_improvements(monthly, open_, close, cfg, CRITERIA, "research", 0.5)
    assert a.shape == (4,)
    assert np.isfinite(a).all()
    assert np.array_equal(a, b)
