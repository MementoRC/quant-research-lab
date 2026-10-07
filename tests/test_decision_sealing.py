"""Sealing: altering prices and CPI after 2018-12-31 leaves the decision
report unchanged (spec "Tests"). Offline; full config (12 portfolios, ten
start years, four rates)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from decision_helpers import END, cpi, criteria, load, prices

from qrl.decision import run_decision
from qrl.decision_report import render_markdown

SHA = "cd" * 32


def _scaled(frame: pd.DataFrame, mask: np.ndarray, rng: np.random.Generator) -> pd.DataFrame:
    """Multiply the masked rows of every column by its own wild factors."""
    factors = np.where(mask[:, None], rng.uniform(0.2, 5.0, frame.shape), 1.0)
    return frame * factors


def _render(cfg, data, index) -> str:
    return render_markdown(run_decision(cfg, data, index, criteria(), SHA))


def test_decision_report_ignores_data_after_2018(tmp_path):
    cfg = load(tmp_path)
    data, index = prices(), cpi()
    rng = np.random.default_rng(3)
    after = np.asarray(data["close"].index > END)
    poisoned = {k: _scaled(v, after, rng) for k, v in data.items()}  # open, close; RSP too
    assert set(data) == {"open", "close"}
    assert "RSP" in data["close"].columns
    assert not poisoned["close"].equals(data["close"])
    assert not poisoned["open"].equals(data["open"])
    cpi_after = np.asarray(index.index > END)
    poisoned_cpi = index * np.where(cpi_after, rng.uniform(0.2, 5.0, len(index)), 1.0)
    assert not poisoned_cpi.equals(index)
    base = _render(cfg, data, index)
    assert base == _render(cfg, poisoned, poisoned_cpi)


def test_decision_report_detects_data_on_or_before_2018(tmp_path):
    """The check above can fail: altering a value at the data end changes the report."""
    cfg = load(tmp_path)
    data, index = prices(), cpi()
    base = _render(cfg, data, index)
    altered = {k: v.copy() for k, v in data.items()}
    altered["close"].loc[END, :] *= 0.5
    assert _render(cfg, altered, index) != base
    earlier = index.copy()
    earlier.iloc[(index.index <= END).sum() - 1] *= 3.0
    assert _render(cfg, data, earlier) != base
