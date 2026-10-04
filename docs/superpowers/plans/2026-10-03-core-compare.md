# Core Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A diagnostic `pixi run core-compare` that evaluates seven pre-registered core candidates (A-G) on research-period metrics and on stress cells that never touch the validation or holdout periods, and writes `research/core_compare.md` plus `reports/core_compare.json`. It selects nothing and changes no locked config.

**Architecture:** A new strategy family `core_mix` (static or trend-switched fixed-weight mixes). A third stress asset class `bonds` in `src/qrl/stress.py` (with a dated amendment to `config/stress.yaml`). A pre-registered `config/core_candidates.yaml`, loaded and run by pure functions in `src/qrl/core_compare.py`, and a thin CLI `scripts/core_compare.py`.

**Tech Stack:** Python 3.12, pandas, numpy, PyYAML, pytest; existing `qrl.engine.run_backtest`, `qrl.portfolio.combine_portfolio`, `qrl.metrics.compute_metrics`, `qrl.periods.period_bounds/slice_period`, `qrl.stress.run_stress/PortfolioDef`.

**Spec:** `docs/superpowers/specs/2026-10-03-core-compare-design.md`

**Hard rules (AGENTS.md):** do NOT edit `src/qrl/engine.py`, `metrics.py`, `periods.py`, `checks.py`, any existing test other than the two allowed edits below, or any locked config (`criteria.yaml`, `combined.yaml`, `combined_null.yaml`, `paper.yaml`, `factor.yaml`, `profile.yaml`, `portfolio.yaml`). Allowed test edits: ADD an entry to `EXAMPLE_PARAMS` in `tests/test_strategies.py` (required for a new strategy), and update `tests/test_stress.py` (the predecessor's new tests) for the new required `bonds` class without weakening any assertion. Allowed config edit: the dated amendment in `config/stress.yaml` (owner-approved 2026-10-03). Never call `slice_period(..., "holdout", unseal_holdout=True)`; never read the validation period. Run commands as `pixi run -e dev ...` (tasks are ambiguous across environments without `-e`). Work on branch `feature/core-compare` (already created from `development`); never push; open no PR (the controller does).

**Test command form:** `pixi run -e dev test -k "<pattern>" -q --no-cov`. **Quality gate** (pixi.toml tasks, env dev): `format-check`, `lint`, `type-check` (`mypy src/qrl`).

**Before every commit:** run `pixi run -e dev format` (ruff format; line length 100) and `pixi run -e dev lint`; the code blocks below are not guaranteed to be pre-formatted. If `format` changes files, they are included in that commit.

**Test counts (new tests added by this plan):** `-k core_mix` 12 (11 in `tests/test_core_mix.py` + the new `test_strategies.py` parametrize id); `tests/test_stress.py` +8; `-k core_compare` 21 (9 after Task 3, 14 after Task 4, 17 after Task 5, 21 after Task 6). Whole suite: baseline + 41.

---

## File structure

| File | Action | Responsibility |
|---|---|---|
| `src/qrl/strategies/core_mix.py` | create | `core_mix` weights + `core_mix_tickers` |
| `src/qrl/strategies/__init__.py` | modify | register `core_mix` in `REGISTRY` |
| `tests/test_core_mix.py` | create | core_mix unit tests |
| `tests/test_strategies.py` | modify | add `core_mix` to `EXAMPLE_PARAMS` (entry only) |
| `src/qrl/stress.py` | modify | `bonds` class: `SHOCK_CLASSES`, `BOND_TICKERS`, `asset_class`, `frozen_loss` proxy |
| `config/stress.yaml` | modify | dated amendment: `bonds` shock in each hypothetical |
| `tests/test_stress.py` | modify | update two-class assumptions, add 8 bonds tests |
| `config/core_candidates.yaml` | create | pre-registered candidates A-G |
| `src/qrl/core_compare.py` | create | loader, window split, research metrics, stress orchestration, markdown |
| `tests/test_core_compare.py` | create | core_compare tests (21) |
| `scripts/core_compare.py` | create | CLI: load data, run, print, write md + json |
| `pixi.toml` | modify | add `core-compare` task |
| `research/core_compare.md` | create (generated, Task 8) | first report, committed by this plan |

---

### Task 1: `core_mix` strategy family

**Files:**
- Create: `src/qrl/strategies/core_mix.py`
- Create: `tests/test_core_mix.py`
- Modify: `src/qrl/strategies/__init__.py`
- Modify: `tests/test_strategies.py` (EXAMPLE_PARAMS entry only)

- [ ] **Step 1: Record the baseline test count and confirm the signatures this task relies on**

Run:
```bash
pixi run -e dev test --co -q --no-cov | tail -1
sed -n 1,31p src/qrl/strategies/core_trend.py
grep -n "synthetic_prices(\[" tests/test_strategies.py
```
Write down the `N tests collected` number (call it BASE). Expected: `core_trend(close, risk_on="QQQ", risk_off="GLD", lookback=200)` returns a frame whose columns are `[risk_on, risk_off]` and NaN-es warm-up rows via `sma.isna() | close[risk_on].isna() | close[risk_off].isna()`; `tests/test_strategies.py`'s look-ahead test builds its frame from `["QQQ", "GLD", "SPY"]` only (so the EXAMPLE_PARAMS entry below must use only those tickers). If either differs, STOP and report to the human.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_core_mix.py`:

```python
"""Tests for the core_mix strategy family (static or trend-switched fixed mixes).
Offline; small hand-built frames and synthetic prices only.
Spec: docs/superpowers/specs/2026-10-03-core-compare-design.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qrl.checks import assert_causal
from qrl.data import synthetic_prices
from qrl.strategies import REGISTRY
from qrl.strategies.core_mix import core_mix, core_mix_tickers
from qrl.strategies.core_trend import core_trend


def _close(**cols: list[float]) -> pd.DataFrame:
    n = len(next(iter(cols.values())))
    return pd.DataFrame(cols, index=pd.bdate_range("2020-01-01", periods=n))


def test_core_mix_static_weights_are_constant():
    close = _close(SPY=[1.0] * 4, IEF=[1.0] * 4)
    w = core_mix(close, {"SPY": 0.6, "IEF": 0.4})
    assert list(w.columns) == ["SPY", "IEF"]
    assert (w["SPY"] == 0.6).all()
    assert (w["IEF"] == 0.4).all()


def test_core_mix_static_is_nan_until_every_held_ticker_is_priced():
    nan = float("nan")
    close = _close(SPY=[1.0] * 4, IEF=[nan, nan, 1.0, 1.0])
    w = core_mix(close, {"SPY": 0.6, "IEF": 0.4})
    assert w.iloc[:2].isna().all().all()
    assert w.iloc[2:].notna().all().all()


def test_core_mix_switches_on_and_off_on_a_hand_built_series():
    # SPY 3-day SMA: nan, nan, 10.00, 10.67, 10.00, 9.67, 9.33
    # SPY close:     10,  10,  10,    12,    8,     9,    11
    # above SMA:      -    -    no     yes    no     no    yes
    close = _close(SPY=[10.0, 10.0, 10.0, 12.0, 8.0, 9.0, 11.0], IEF=[100.0] * 7, GLD=[100.0] * 7)
    w = core_mix(
        close,
        risk_on={"SPY": 0.6, "IEF": 0.4},
        risk_off={"IEF": 0.5, "GLD": 0.5},
        signal="SPY",
        lookback=3,
    )
    on, off, nan = [0.6, 0.4, 0.0], [0.0, 0.5, 0.5], [np.nan] * 3
    expected = pd.DataFrame(
        [nan, nan, off, on, off, off, on], index=close.index, columns=["SPY", "IEF", "GLD"]
    )
    pd.testing.assert_frame_equal(w, expected)


def test_core_mix_one_ticker_each_matches_core_trend():
    _, close = synthetic_prices(["QQQ", "GLD"], start="2010-01-01", end="2014-12-31")
    mixed = core_mix(close, {"QQQ": 1.0}, risk_off={"GLD": 1.0}, signal="QQQ", lookback=50)
    pd.testing.assert_frame_equal(mixed, core_trend(close, "QQQ", "GLD", 50))


def test_core_mix_weights_are_causal():
    _, close = synthetic_prices(["QQQ", "GLD", "SPY"], start="2010-01-01", end="2014-12-31")
    params = {
        "risk_on": {"SPY": 0.6, "QQQ": 0.4},
        "risk_off": {"GLD": 1.0},
        "signal": "SPY",
        "lookback": 50,
    }
    assert_causal(lambda c: core_mix(c, **params), close)


@pytest.mark.parametrize(
    ("risk_on", "risk_off"),
    [
        ({"SPY": 0.7, "IEF": 0.5}, None),
        ({"SPY": 1.0}, {"IEF": 0.6, "GLD": 0.6}),
    ],
)
def test_core_mix_rejects_weights_summing_above_one(risk_on, risk_off):
    close = _close(SPY=[1.0] * 5, IEF=[1.0] * 5, GLD=[1.0] * 5)
    extra = {} if risk_off is None else {"risk_off": risk_off, "signal": "SPY", "lookback": 2}
    with pytest.raises(ValueError, match="above 1"):
        core_mix(close, risk_on, **extra)


def test_core_mix_rejects_negative_weight():
    close = _close(SPY=[1.0] * 5, IEF=[1.0] * 5)
    with pytest.raises(ValueError, match="negative"):
        core_mix(close, {"SPY": 1.2, "IEF": -0.2})


def test_core_mix_switching_requires_signal_and_lookback():
    close = _close(SPY=[1.0] * 5, IEF=[1.0] * 5)
    with pytest.raises(ValueError, match="signal and lookback"):
        core_mix(close, {"SPY": 1.0}, risk_off={"IEF": 1.0})


def test_core_mix_static_mix_rejects_signal():
    close = _close(SPY=[1.0] * 5)
    with pytest.raises(ValueError, match="static mix"):
        core_mix(close, {"SPY": 1.0}, signal="SPY")


def test_core_mix_tickers_include_signal_but_columns_do_not():
    static = {"risk_on": {"SPY": 0.6, "IEF": 0.4}}
    assert core_mix_tickers(static) == ["SPY", "IEF"]
    switching = {
        "risk_on": {"SPY": 0.6, "IEF": 0.4},
        "risk_off": {"IEF": 0.5, "GLD": 0.5},
        "signal": "QQQ",
        "lookback": 3,
    }
    assert REGISTRY["core_mix"].tickers(switching) == ["SPY", "IEF", "GLD", "QQQ"]
    close = _close(SPY=[1.0] * 5, IEF=[1.0] * 5, GLD=[1.0] * 5, QQQ=[1.0] * 5)
    w = core_mix(close, **switching)
    assert list(w.columns) == ["SPY", "IEF", "GLD"]
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `pixi run -e dev test -k core_mix -q --no-cov`
Expected: collection ERROR `ModuleNotFoundError: No module named 'qrl.strategies.core_mix'`; no test passes.

- [ ] **Step 4: Implement `core_mix`**

Create `src/qrl/strategies/core_mix.py`:

```python
"""Static or trend-switched fixed-weight core mix.

risk_on / risk_off map ticker -> weight (non-negative, sum <= 1). With
`risk_off` omitted the mix is static. With it, the rule mirrors `core_trend`:
hold `risk_on` while `signal` closes above its simple moving average over
`lookback` days, else `risk_off`. Rows are NaN during warm-up and whenever a
ticker the rule can hold (or the signal) has no price. Row t uses data up to
the close of day t. Spec: docs/superpowers/specs/2026-10-03-core-compare-design.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

_EPS = 1e-9


def _validated(name: str, mix: dict[str, float]) -> None:
    if not mix:
        raise ValueError(f"{name} must be a non-empty ticker -> weight mapping")
    if any(w < 0 for w in mix.values()):
        raise ValueError(f"{name} has a negative weight; long-only required")
    total = sum(mix.values())
    if total > 1 + _EPS:
        raise ValueError(f"{name} weights sum to {total:.3f}, above 1")


def core_mix(
    close: pd.DataFrame,
    risk_on: dict[str, float],
    risk_off: dict[str, float] | None = None,
    signal: str | None = None,
    lookback: int | None = None,
) -> pd.DataFrame:
    _validated("risk_on", risk_on)
    if risk_off is None:
        if signal is not None or lookback is not None:
            raise ValueError("signal and lookback apply only with risk_off: a static mix never switches")
        cols = list(risk_on)
        static = pd.DataFrame({t: float(x) for t, x in risk_on.items()}, index=close.index)
        static[close[cols].isna().any(axis=1)] = np.nan
        return static

    _validated("risk_off", risk_off)
    if signal is None or lookback is None:
        raise ValueError("risk_off requires both signal and lookback")
    price = close[signal]
    sma = price.rolling(lookback, min_periods=lookback).mean()
    above = (price > sma).to_numpy()

    cols = list(dict.fromkeys([*risk_on, *risk_off]))
    w = pd.DataFrame(0.0, index=close.index, columns=cols)
    for ticker, weight in risk_on.items():
        w[ticker] = w[ticker] + np.where(above, weight, 0.0)
    for ticker, weight in risk_off.items():
        w[ticker] = w[ticker] + np.where(above, 0.0, weight)

    warmup = sma.isna() | price.isna() | close[cols].isna().any(axis=1)
    w[warmup] = np.nan
    return w


def core_mix_tickers(params: dict) -> list[str]:
    """Every ticker whose prices the rule needs: the held tickers, plus the
    signal when the mix switches (callers load `data[f][tickers]`)."""
    names = [*params["risk_on"], *(params.get("risk_off") or {})]
    if params.get("risk_off") is not None and params.get("signal"):
        names.append(params["signal"])
    return list(dict.fromkeys(names))
```

Modify `src/qrl/strategies/__init__.py`: add the import after `from .core_trend import core_trend`:

```python
from .core_mix import core_mix, core_mix_tickers
```
and add this entry to `REGISTRY` after the `"core_trend"` entry:

```python
    # Exploration only (docs/superpowers/specs/2026-10-03-core-compare-design.md):
    # fixed-weight mixes for the core comparison; not searched (empty space).
    "core_mix": StrategySpec(core_mix, core_mix_tickers, fields=("close",)),
```

Modify `tests/test_strategies.py`: add ONLY this entry to `EXAMPLE_PARAMS`, right after the `"core_trend"` line (tickers limited to the QQQ/GLD/SPY frame the existing loop builds):

```python
    "core_mix": {
        "risk_on": {"SPY": 0.6, "QQQ": 0.4},
        "risk_off": {"GLD": 1.0},
        "signal": "SPY",
        "lookback": 200,
    },
```

- [ ] **Step 5: Run the tests**

Run: `pixi run -e dev test -k core_mix -q --no-cov`
Expected: `12 passed` (11 in `tests/test_core_mix.py` + `test_every_registered_strategy_is_causal[core_mix]`).

Run: `pixi run -e dev test -k "every_registered or strategies or profile" -q --no-cov`
Expected: all pass (the existing registry-driven tests now also cover `core_mix`; no other test enumerates `REGISTRY`, confirmed by `grep -rn "in REGISTRY\|REGISTRY\.items\|sorted(REGISTRY" src scripts tests` showing only `tests/test_strategies.py`).

- [ ] **Step 6: Format, lint, type-check, commit**

```bash
pixi run -e dev format
pixi run -e dev lint
pixi run -e dev type-check
git add src/qrl/strategies/core_mix.py src/qrl/strategies/__init__.py tests/test_core_mix.py tests/test_strategies.py
git commit -m "Add core_mix strategy family (static or trend-switched fixed mixes)"
```
Expected: lint/type-check clean. If mypy objects to a pandas-stubs signature in `core_mix.py`, fix the expression (do not add a bare `# type: ignore`; if an ignore is unavoidable, give the error code and a one-line reason).

---

### Task 2: Stress `bonds` class

**Files:**
- Modify: `src/qrl/stress.py`
- Modify: `config/stress.yaml`
- Modify: `tests/test_stress.py`

- [ ] **Step 1: Record the stress test baseline**

Run: `pixi run -e dev test -k stress -q --no-cov | tail -2`
Write down the `M passed` number (call it STRESS_BASE). Expected: all pass.

- [ ] **Step 2: Update the existing two-class assumptions and add the new tests**

Edit `tests/test_stress.py` (no assertion is removed or loosened; each gains the third class):

1. In `GOOD`, replace `  - {name: h1, equity: -0.5, gold: -0.2}` with `  - {name: h1, equity: -0.5, gold: -0.2, bonds: 0.0}`.
2. In `test_loads_good_config`, replace `assert cfg.hypotheticals[0].shocks == {"equity": -0.5, "gold": -0.2}` with `assert cfg.hypotheticals[0].shocks == {"equity": -0.5, "gold": -0.2, "bonds": 0.0}`.
3. In `test_rejects_unknown_class`, replace `text = GOOD.replace("gold: -0.2", "bonds: -0.2")` with `text = GOOD.replace("bonds: 0.0", "crypto: 0.0")` (`bonds` is now a known class; `crypto` is the unknown one; the loader checks unknown classes first, so `match="unknown"` still holds).
4. In `test_frozen_loss_buy_and_hold_no_rebalance` and `test_frozen_loss_spy_held_directly_is_not_proxied`, replace `assert detail["proxied_share"] == {"equity": 0.0, "gold": 0.0}` with `assert detail["proxied_share"] == {"equity": 0.0, "gold": 0.0, "bonds": 0.0}` (two places).
5. In `test_frozen_loss_proxies_equity_to_spy_and_gold_to_cash`, replace `assert detail["proxied_share"] == {"equity": pytest.approx(0.6), "gold": pytest.approx(0.4)}` with:

```python
    assert detail["proxied_share"] == {
        "equity": pytest.approx(0.6),
        "gold": pytest.approx(0.4),
        "bonds": 0.0,
    }
```
6. Append these 8 tests (4 from the parametrize) at the end of the "config" and "measure" areas (anywhere in the file after `_win` is defined; the end of the file is fine):

```python
@pytest.mark.parametrize("ticker", ["IEF", "TLT", "SHY", "AGG"])
def test_asset_class_bonds(ticker):
    assert asset_class(ticker) == "bonds"


def test_hypothetical_loss_includes_bonds_class():
    w = pd.Series({"SPY": 0.5, "IEF": 0.3, "GLD": 0.1})  # 0.1 cash
    h = Hypothetical("x", {"equity": -0.4, "gold": -0.1, "bonds": 0.05})
    # -(0.5 * -0.4 + 0.1 * -0.1 + 0.3 * 0.05)
    assert hypothetical_loss(w, h) == pytest.approx(0.195)


def test_frozen_loss_proxies_bonds_to_cash():
    idx = pd.bdate_range("2001-01-08", periods=2)
    close = pd.DataFrame({"IEF": [float("nan")] * 2, "SPY": [100.0, 50.0]}, index=idx)
    w = pd.Series({"SPY": 0.5, "IEF": 0.5})
    loss, detail = frozen_loss(w, close, _win("2001-01-08", "2001-01-09"))
    # SPY halves, IEF -> cash: 1.0 -> 0.5 * 0.5 + 0.5 = 0.75
    assert loss == pytest.approx(0.25)
    assert detail["proxied_share"] == {"equity": 0.0, "gold": 0.0, "bonds": pytest.approx(0.5)}


def test_rejects_hypothetical_missing_bonds(tmp_path):
    text = GOOD.replace(", bonds: 0.0", "")
    with pytest.raises(ValueError, match="bonds"):
        load_stress_config(_write(tmp_path, text), HOLDOUT)


def test_shipped_config_has_bonds_shocks():
    cfg, _ = load_stress_config(ROOT / "config" / "stress.yaml", HOLDOUT)
    assert {h.name: h.shocks["bonds"] for h in cfg.hypotheticals} == {
        "no_safe_haven": -0.15,
        "stagflation": -0.20,
        "energy_shock_severe": -0.10,
        "tech_crash": 0.05,
    }
```

(`asset_class`, `Hypothetical`, `hypothetical_loss`, `frozen_loss`, `load_stress_config` are already imported by the file; `ROOT`, `HOLDOUT`, `_write`, `GOOD`, `_win` already exist. If the import block does not list one of them, add it.)

- [ ] **Step 3: Run the stress tests to verify they fail**

Run: `pixi run -e dev test -k stress -q --no-cov`
Expected: failures, including `test_asset_class_bonds`, `test_shipped_config_has_bonds_shocks`, `test_loads_good_config` (the loader still rejects the `bonds` key as unknown) and the `proxied_share` assertions. Not all pass.

- [ ] **Step 4: Implement the class in `src/qrl/stress.py`**

Replace `SHOCK_CLASSES = ("equity", "gold")` with `SHOCK_CLASSES = ("equity", "gold", "bonds")`.

Replace the `GOLD_TICKERS`/`asset_class` block with:

```python
GOLD_TICKERS = frozenset({"GLD"})
BOND_TICKERS = frozenset({"IEF", "TLT", "SHY", "AGG"})


def asset_class(ticker: str) -> str:
    if ticker in GOLD_TICKERS:
        return "gold"
    if ticker in BOND_TICKERS:
        return "bonds"
    return "equity"
```

In `frozen_loss`, replace the docstring sentence `A ticker with no price at the window's first day is replaced per class: equity -> SPY, gold -> cash.` with `A ticker with no price at the window's first day is replaced per class: equity -> SPY, gold and bonds -> cash.` and replace

```python
            if cls == "gold":
                value += wt  # gold before GLD existed -> cash
                continue
```
with
```python
            if cls != "equity":
                value += wt  # gold/bonds before their ETF existed -> cash
                continue
```

- [ ] **Step 5: Amend `config/stress.yaml` (dated amendment, owner approval 2026-10-03)**

Replace the hypotheticals section (and the "Classes:" comment line above it) with:

```yaml
# Instantaneous shocks per asset class, applied to the latest weights.
# Classes: gold = GLD; bonds = IEF, TLT, SHY, AGG; equity = every other ticker;
# cash = unallocated (0%). These are judgments, not data.
#
# AMENDMENT 2026-10-03 (owner approval; docs/superpowers/specs/2026-10-03-core-compare-design.md):
# added the `bonds` class and its shock to every hypothetical, for the core
# comparison. Equity and gold shocks are unchanged. The first report was
# already produced before this amendment (the chosen core holds no bonds, so
# its losses are unaffected).
hypotheticals:
  - {name: no_safe_haven, equity: -0.50, gold: -0.20, bonds: -0.15}       # stocks, gold and bonds fall together
  - {name: stagflation, equity: -0.45, gold: 0.10, bonds: -0.20}          # 1973-74-style rotation
  - {name: energy_shock_severe, equity: -0.40, gold: -0.10, bonds: -0.10} # fuel/diesel shock worse than 2022
  - {name: tech_crash, equity: -0.60, gold: 0.0, bonds: 0.05}             # 2000-02-scale equity collapse
```

- [ ] **Step 6: Run the stress tests**

Run: `pixi run -e dev test -k stress -q --no-cov`
Expected: `STRESS_BASE + 8 passed`.

- [ ] **Step 7: Format, lint, type-check, commit**

```bash
pixi run -e dev format
pixi run -e dev lint
pixi run -e dev type-check
git add src/qrl/stress.py config/stress.yaml tests/test_stress.py
git commit -m "Stress: bonds asset class (loader, proxy to cash) and dated stress.yaml amendment"
```

---

### Task 3: Candidates file and loader

**Files:**
- Create: `config/core_candidates.yaml`
- Create: `src/qrl/core_compare.py`
- Create: `tests/test_core_compare.py`

- [ ] **Step 1: Confirm `core_trend` accepts IEF as `risk_off`**

Run: `grep -n "risk_off" src/qrl/strategies/core_trend.py`
Expected: only the `CASH` sentinel is special; any other string is used as a column of `close`. If a restriction exists, express candidate C as `core_mix {risk_on: {SPY: 1.0}, risk_off: {IEF: 1.0}, signal: SPY, lookback: 200}` instead and state so in the file's comment and the commit message.

- [ ] **Step 2: Create `config/core_candidates.yaml`**

```yaml
# PRE-REGISTERED core candidates for the core comparison (EXPLORATION ONLY;
# spec docs/superpowers/specs/2026-10-03-core-compare-design.md, owner approval
# 2026-10-03). Fixed before any result was seen. After the first
# `pixi run core-compare` report, change only via a dated amendment comment here.
# Every report records this file's full sha256 and the trial count (7).
# Each candidate is evaluated as a core-only portfolio at the profile's
# capital_split (core 0.80, empty sleeve -> 20% cash).
version: 1

candidates:
  - {id: A, label: "current: QQQ/GLD 200d trend", fn: core_trend, params: {risk_on: QQQ, risk_off: GLD, lookback: 200}}
  - {id: B, label: "SPY/GLD 200d trend", fn: core_trend, params: {risk_on: SPY, risk_off: GLD, lookback: 200}}
  - {id: C, label: "SPY/IEF 200d trend", fn: core_trend, params: {risk_on: SPY, risk_off: IEF, lookback: 200}}
  - {id: D, label: "static 60/40 SPY/IEF", fn: core_mix, params: {risk_on: {SPY: 0.6, IEF: 0.4}}}
  - {id: E, label: "static SPY 60 / IEF 20 / GLD 20", fn: core_mix, params: {risk_on: {SPY: 0.6, IEF: 0.2, GLD: 0.2}}}
  - id: F
    label: "switched mix, SPY 200d signal"
    fn: core_mix
    params:
      risk_on: {SPY: 0.6, IEF: 0.4}
      risk_off: {IEF: 0.5, GLD: 0.5}
      signal: SPY
      lookback: 200
  - {id: G, label: "static 25% each SPY/TLT/GLD/SHY", fn: core_mix, params: {risk_on: {SPY: 0.25, TLT: 0.25, GLD: 0.25, SHY: 0.25}}}
```

- [ ] **Step 3: Write the failing tests**

Create `tests/test_core_compare.py`:

```python
"""Tests for the core-comparison exploration (qrl.core_compare,
scripts/core_compare.py). Offline; synthetic prices only.
Spec: docs/superpowers/specs/2026-10-03-core-compare-design.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from qrl.core_compare import load_core_candidates

ROOT = Path(__file__).resolve().parents[1]

GOOD = """
version: 1
candidates:
  - {id: T1, label: "trend", fn: core_trend, params: {risk_on: SPY, risk_off: IEF, lookback: 5}}
  - {id: T2, label: "static", fn: core_mix, params: {risk_on: {SPY: 0.6, IEF: 0.4}}}
"""


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "core_candidates.yaml"
    p.write_text(text)
    return p


def test_core_compare_shipped_candidates_load():
    cands, digest = load_core_candidates(ROOT / "config" / "core_candidates.yaml")
    assert [c.id for c in cands] == list("ABCDEFG")
    assert len(digest) == 64  # full sha256
    by_id = {c.id: c for c in cands}
    assert by_id["A"].fn == "core_trend"
    assert by_id["A"].params == {"risk_on": "QQQ", "risk_off": "GLD", "lookback": 200}
    assert by_id["C"].params["risk_off"] == "IEF"
    assert by_id["D"].fn == "core_mix" and "risk_off" not in by_id["D"].params
    assert by_id["F"].params["signal"] == "SPY"


def test_core_compare_rejects_duplicate_ids(tmp_path):
    with pytest.raises(ValueError, match="duplicate"):
        load_core_candidates(_write(tmp_path, GOOD.replace("id: T2", "id: T1")))


def test_core_compare_rejects_unknown_fn(tmp_path):
    with pytest.raises(ValueError, match="fn must be"):
        load_core_candidates(_write(tmp_path, GOOD.replace("fn: core_mix", "fn: buy_and_hold")))


def test_core_compare_rejects_cash_risk_off(tmp_path):
    with pytest.raises(ValueError, match="CASH"):
        load_core_candidates(_write(tmp_path, GOOD.replace("risk_off: IEF", "risk_off: CASH")))


def test_core_compare_rejects_empty_candidates(tmp_path):
    with pytest.raises(ValueError, match="non-empty"):
        load_core_candidates(_write(tmp_path, "version: 1\ncandidates: []\n"))


def test_core_compare_rejects_params_the_strategy_rejects(tmp_path):
    with pytest.raises(ValueError, match="above 1"):
        load_core_candidates(_write(tmp_path, GOOD.replace("IEF: 0.4", "IEF: 0.9")))


def test_core_compare_rejects_bad_id(tmp_path):
    # quoted: an unquoted `T[1]` would be a YAML syntax error, not a bad id
    with pytest.raises(ValueError, match="id"):
        load_core_candidates(_write(tmp_path, GOOD.replace("id: T1", 'id: "T[1]"')))


def test_core_compare_rejects_malformed_yaml(tmp_path):
    with pytest.raises(ValueError, match="valid YAML"):
        load_core_candidates(_write(tmp_path, "version: 1\ncandidates: [unclosed\n"))


def test_core_compare_rejects_non_mapping_params(tmp_path):
    text = GOOD.replace("params: {risk_on: SPY, risk_off: IEF, lookback: 5}", "params: [SPY]")
    with pytest.raises(ValueError, match="mapping"):
        load_core_candidates(_write(tmp_path, text))
```

- [ ] **Step 4: Run to verify the failure**

Run: `pixi run -e dev test -k core_compare -q --no-cov`
Expected: collection ERROR `ModuleNotFoundError: No module named 'qrl.core_compare'`.

- [ ] **Step 5: Implement the loader**

Create `src/qrl/core_compare.py`:

```python
"""Core comparison: an EXPLORATION of alternative, more resilient cores
against the current one (spec: docs/superpowers/specs/2026-10-03-core-compare-design.md).
It forecasts nothing, tunes nothing and selects nothing. Pure functions;
callers inject data and configs. Validation and holdout data never enter
(frames are cut at the research end; windows reaching the validation period
are dropped), and `slice_period(..., unseal_holdout=True)` is never called.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

from .strategies import REGISTRY

CORE_FAMILIES = ("core_trend", "core_mix")
_ID = re.compile(r"[A-Za-z0-9_-]+")
_REQUIRED = {"id", "label", "fn", "params"}


@dataclass(frozen=True)
class Candidate:
    id: str
    label: str
    fn: str
    params: dict


def candidate_weights(cand: Candidate, close: pd.DataFrame) -> pd.DataFrame:
    """The candidate's raw core weights (fractions of the core's own capital),
    built exactly as scripts build `config/portfolio.yaml` members."""
    spec = REGISTRY[cand.fn]
    cols = spec.tickers(cand.params)
    return spec.weights(close[cols], **cand.params)


def _parse_candidate(raw: object) -> Candidate:
    if (
        not isinstance(raw, dict)
        or not _REQUIRED <= raw.keys()
        or not isinstance(raw["params"], dict)
    ):
        raise ValueError(
            f"each candidate needs {sorted(_REQUIRED)} with `params` a mapping, got {raw!r}"
        )
    cand = Candidate(str(raw["id"]), str(raw["label"]), str(raw["fn"]), dict(raw["params"]))
    if not _ID.fullmatch(cand.id):
        raise ValueError(f"candidate id {cand.id!r} must match [A-Za-z0-9_-]+")
    if cand.fn not in CORE_FAMILIES:
        raise ValueError(f"candidate {cand.id}: fn must be one of {CORE_FAMILIES}")
    if cand.params.get("risk_off") == "CASH":
        raise ValueError(f"candidate {cand.id}: CASH risk_off has no priced branch to stress")
    try:
        cols = REGISTRY[cand.fn].tickers(cand.params)
        probe = pd.DataFrame(1.0, index=pd.bdate_range("2020-01-01", periods=3), columns=cols)
        candidate_weights(cand, probe)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"candidate {cand.id}: bad params ({exc})") from exc
    return cand


def load_core_candidates(path: str | Path) -> tuple[list[Candidate], str]:
    """Return (candidates, full sha256 of the raw file bytes). Raises ValueError
    on malformed YAML, a wrong version, a missing/empty list, duplicate or
    malformed ids, an unknown fn, non-mapping params, a CASH risk_off, or params
    the strategy rejects."""
    raw = Path(path).read_bytes()
    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"core candidates file is not valid YAML ({exc})") from exc
    if not isinstance(doc, dict) or doc.get("version") != 1:
        raise ValueError("core candidates file must be a mapping with `version: 1`")
    entries = doc.get("candidates")
    if not isinstance(entries, list) or not entries:
        raise ValueError("core candidates file needs a non-empty `candidates` list")
    cands = [_parse_candidate(e) for e in entries]
    ids = [c.id for c in cands]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ValueError(f"duplicate candidate ids: {dupes}")
    return cands, hashlib.sha256(raw).hexdigest()
```

- [ ] **Step 6: Run the tests**

Run: `pixi run -e dev test -k core_compare -q --no-cov`
Expected: `9 passed`.

- [ ] **Step 7: Format, lint, type-check, commit**

```bash
pixi run -e dev format
pixi run -e dev lint
pixi run -e dev type-check
git add config/core_candidates.yaml src/qrl/core_compare.py tests/test_core_compare.py
git commit -m "Core compare: pre-registered candidates file and validating loader"
```

---

### Task 4: Window split and research-period metrics

**Files:**
- Modify: `src/qrl/core_compare.py`
- Modify: `tests/test_core_compare.py`

- [ ] **Step 1: Confirm the signatures this task relies on**

Run:
```bash
grep -n "^def run_backtest\|cost_bps" src/qrl/engine.py | head -3
grep -n "^def compute_metrics\|^def slice_period\|^def period_bounds" src/qrl/metrics.py src/qrl/periods.py
grep -n "^class Window" -A5 src/qrl/stress.py
```
Expected: `run_backtest(open_, close, target_weights, cost_bps=5.0)`; `compute_metrics(returns, turnover=None, executed=None)`; `slice_period(obj, criteria, name, unseal_holdout=False)`; `period_bounds(criteria, name)`; `Window(name, start, end, replay)` frozen dataclass. If any differs, STOP and report.

- [ ] **Step 2: Write the failing tests**

In `tests/test_core_compare.py` replace the import block (everything from `from __future__` through `ROOT = ...`) with:

```python
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qrl.core_compare import (
    Candidate,
    load_core_candidates,
    research_metrics,
    split_windows,
)
from qrl.criteria import load_criteria
from qrl.data import synthetic_prices
from qrl.stress import Window, load_stress_config

ROOT = Path(__file__).resolve().parents[1]
HOLDOUT = pd.Timestamp("2023-01-01")
SPLIT = {"core": 0.8, "sleeve": 0.2}
TICKERS = ["SPY", "QQQ", "GLD", "IEF", "TLT", "SHY"]
STATIC = Candidate("T", "static", "core_mix", {"risk_on": {"SPY": 0.6, "IEF": 0.4}})


def _criteria() -> dict:
    return load_criteria(ROOT / "config" / "criteria.yaml")[0]


def _data(start: str = "1999-01-01", end: str = "2021-12-31") -> dict[str, pd.DataFrame]:
    open_, close = synthetic_prices(TICKERS, start=start, end=end)
    return {"open": open_, "close": close}
```

(The `GOOD` and `_write` definitions stay below it, unchanged.) Append:

```python
def test_core_compare_split_windows_drops_validation_overlap():
    cfg, _ = load_stress_config(ROOT / "config" / "stress.yaml", HOLDOUT)
    kept, excluded = split_windows(cfg.windows, _criteria())
    assert [w.name for w in kept] == ["dotcom_2000", "gfc_2008"]
    assert [w.name for w in excluded] == ["covid_2020", "inflation_2022"]


def test_core_compare_split_windows_drops_holdout_overlap():
    early = Window("early", pd.Timestamp("2018-01-02"), pd.Timestamp("2018-12-31"), True)
    straddle = Window("straddle", pd.Timestamp("2018-06-01"), pd.Timestamp("2019-02-01"), True)
    late = Window("late", pd.Timestamp("2023-02-01"), pd.Timestamp("2023-03-01"), False)
    kept, excluded = split_windows([early, straddle, late], _criteria())
    assert [w.name for w in kept] == ["early"]
    assert [w.name for w in excluded] == ["straddle", "late"]


def test_core_compare_research_metrics_ignore_later_data():
    data = _data()
    factor = np.where(data["close"].index <= pd.Timestamp("2018-12-31"), 1.0, 5.0)
    poisoned = {k: v.mul(factor, axis=0) for k, v in data.items()}
    assert research_metrics(STATIC, data, _criteria(), SPLIT) == research_metrics(
        STATIC, poisoned, _criteria(), SPLIT
    )


def test_core_compare_research_metrics_stay_inside_research_period():
    m = research_metrics(STATIC, _data(), _criteria(), SPLIT)
    assert m["start"] >= "2005-01-01"
    assert m["end"] <= "2018-12-31"
    assert {"cagr", "sharpe", "max_drawdown", "turnover_per_year"} <= m.keys()


def test_core_compare_research_metrics_reject_unwarmed_candidate():
    late = _data(start="2005-02-01")  # first valid weight is after the research start
    with pytest.raises(ValueError, match="research start"):
        research_metrics(STATIC, late, _criteria(), SPLIT)
```

- [ ] **Step 3: Run to verify the failure**

Run: `pixi run -e dev test -k core_compare -q --no-cov`
Expected: collection ERROR `ImportError: cannot import name 'research_metrics' from 'qrl.core_compare'`.

- [ ] **Step 4: Implement**

In `src/qrl/core_compare.py` replace the import block below the module docstring with:

```python
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

from .engine import run_backtest
from .metrics import compute_metrics
from .periods import period_bounds, slice_period
from .portfolio import combine_portfolio
from .strategies import REGISTRY
from .stress import Window
```

and append:

```python
def split_windows(windows: list[Window], criteria: dict) -> tuple[list[Window], list[Window]]:
    """(kept, excluded). A window is excluded if it ends on/after the validation
    start: that covers any overlap with the validation period and everything
    later (holdout). Order is preserved."""
    vstart, _ = period_bounds(criteria, "validation")
    if vstart is None:
        raise ValueError("criteria has no validation start")
    kept = [w for w in windows if w.end < vstart]
    excluded = [w for w in windows if w.end >= vstart]
    return kept, excluded


def research_metrics(cand: Candidate, data: dict[str, pd.DataFrame], criteria: dict, split: dict) -> dict:
    """Research-period metrics of the candidate as a core-only portfolio.
    Frames are cut at the research end BEFORE weights are built (warm-up rows
    before the research start are allowed); returns are then cut to the
    research period. Raises ValueError if the core's weights are not valid at
    the research start (no silently shortened period)."""
    rstart, rend = period_bounds(criteria, "research")
    if rstart is None or rend is None:
        raise ValueError("criteria research period needs a start and an end")
    close = data["close"].loc[:rend]
    open_ = data["open"].loc[:rend]
    core_w = candidate_weights(cand, close)
    valid = core_w.dropna().index
    if valid.empty or valid[0] > rstart:
        raise ValueError(
            f"candidate {cand.id}: core weights not valid at the research start {rstart.date()}"
        )
    combined = combine_portfolio(core_w, [], split).combined
    cols = list(combined.columns)
    result = run_backtest(
        open_[cols],
        close[cols],
        combined,
        cost_bps=float(criteria["costs"]["bps_per_unit_turnover"]),
    )
    returns = slice_period(result.returns, criteria, "research")
    turnover = slice_period(result.turnover, criteria, "research")
    executed = slice_period(result.executed, criteria, "research")
    return compute_metrics(returns, turnover, executed)
```

- [ ] **Step 5: Run the tests**

Run: `pixi run -e dev test -k core_compare -q --no-cov`
Expected: `14 passed`.

- [ ] **Step 6: Format, lint, type-check, commit**

```bash
pixi run -e dev format
pixi run -e dev lint
pixi run -e dev type-check
git add src/qrl/core_compare.py tests/test_core_compare.py
git commit -m "Core compare: validation-safe window split and research-period metrics"
```

---

### Task 5: Stress portfolios and orchestration

**Files:**
- Modify: `src/qrl/core_compare.py`
- Modify: `tests/test_core_compare.py`

- [ ] **Step 1: Confirm the stress interfaces**

Run:
```bash
grep -n "^def run_stress" -A7 src/qrl/stress.py
grep -n "^class PortfolioDef" -A10 src/qrl/stress.py
grep -n "^class StressConfig" -A5 src/qrl/stress.py
grep -n "^class Cell" -A9 src/qrl/stress.py
```
Expected: `run_stress(cfg, portfolios, data, max_drawdown, criteria) -> list[Cell]`; `PortfolioDef(name, build, core_tickers, sleeve_universe=[], candidate=False)` with `build(data, sleeve_keep)`; `StressConfig(windows, hypotheticals, max_report_age_days)`; `Cell(portfolio, scenario, mode, label, loss, breach, detail, unavailable=None)`. If any differs, STOP and report.

- [ ] **Step 2: Write the failing tests**

In `tests/test_core_compare.py`, replace the `from qrl.core_compare import (...)` block with:

```python
from qrl import core_compare
from qrl.core_compare import (
    Candidate,
    load_core_candidates,
    research_metrics,
    run_core_compare,
    split_windows,
)
```
and append:

```python
ALLOWED_SCENARIOS = {
    "dotcom_2000",
    "gfc_2008",
    "no_safe_haven",
    "stagflation",
    "energy_shock_severe",
    "tech_crash",
}


@pytest.fixture(scope="module")
def compared():
    cands, _ = load_core_candidates(ROOT / "config" / "core_candidates.yaml")
    cfg, _ = load_stress_config(ROOT / "config" / "stress.yaml", HOLDOUT)
    seen: dict = {}
    real = core_compare.run_stress

    def spy(cfg_, portfolios, data, max_drawdown, criteria):
        seen["last_row"] = data["close"].index.max()
        seen["windows"] = [w.name for w in cfg_.windows]
        return real(cfg_, portfolios, data, max_drawdown, criteria)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(core_compare, "run_stress", spy)
        out = run_core_compare(cands, cfg, _data(), _criteria(), SPLIT, 0.35)
    return out, seen


def test_core_compare_stress_never_sees_validation(compared):
    out, seen = compared
    assert seen["last_row"] <= pd.Timestamp("2018-12-31")
    assert seen["windows"] == ["dotcom_2000", "gfc_2008"]
    assert out["excluded_windows"] == ["covid_2020", "inflation_2022"]
    scenarios = {cell["scenario"] for c in out["candidates"] for cell in c["cells"]}
    assert scenarios == ALLOWED_SCENARIOS


def test_core_compare_every_candidate_recorded(compared):
    out, _ = compared
    assert [c["id"] for c in out["candidates"]] == list("ABCDEFG")
    for c in out["candidates"]:
        assert {"cagr", "sharpe", "max_drawdown"} <= c["research"].keys()
        assert c["breach_count"] == c["stress_breaches"] + int(c["research_breach"])


def test_core_compare_switching_candidates_split_into_branches(compared):
    out, _ = compared
    by_id = {c["id"]: c["cells"] for c in out["candidates"]}

    def modes(cells, portfolio):
        return {c["mode"] for c in cells if c["portfolio"] == portfolio}

    assert {c["portfolio"] for c in by_id["F"]} == {"F", "F[risk_on]", "F[risk_off]"}
    assert modes(by_id["F"], "F") == {"replay"}
    assert modes(by_id["F"], "F[risk_on]") == {"frozen", "hypothetical"}
    assert modes(by_id["F"], "F[risk_off]") == {"frozen", "hypothetical"}
    assert {c["portfolio"] for c in by_id["D"]} == {"D"}
    assert modes(by_id["D"], "D") == {"replay", "frozen", "hypothetical"}
    assert {c["portfolio"] for c in by_id["A"]} == {"A", "A[risk_on]", "A[risk_off]"}
```

- [ ] **Step 3: Run to verify the failure**

Run: `pixi run -e dev test -k core_compare -q --no-cov`
Expected: collection ERROR `ImportError: cannot import name 'run_core_compare'`.

- [ ] **Step 4: Implement**

In `src/qrl/core_compare.py` replace the import block with:

```python
from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd
import yaml

from .engine import run_backtest
from .metrics import compute_metrics
from .periods import period_bounds, slice_period
from .portfolio import combine_portfolio
from .strategies import REGISTRY
from .stress import PortfolioDef, StressConfig, Window, run_stress

Build = Callable[[dict[str, pd.DataFrame], list[str]], pd.DataFrame]
ALL_MODES = frozenset({"replay", "frozen", "hypothetical"})
```

and append:

```python
def branch_mixes(cand: Candidate) -> dict[str, dict[str, float]] | None:
    """Static risk_on / risk_off mixes of a switching candidate, or None for a
    static one. A switching rule's latest weight row depends on which branch is
    live, so frozen/hypothetical cells are reported for both branches."""
    p = cand.params
    if cand.fn == "core_trend":
        on, off = p.get("risk_on", "QQQ"), p.get("risk_off", "GLD")
        return {"risk_on": {on: 1.0}, "risk_off": {off: 1.0}}
    if p.get("risk_off") is None:
        return None
    return {"risk_on": dict(p["risk_on"]), "risk_off": dict(p["risk_off"])}


def _rule_build(cand: Candidate, split: dict) -> Build:
    def build(data: dict[str, pd.DataFrame], keep: list[str]) -> pd.DataFrame:
        return combine_portfolio(candidate_weights(cand, data["close"]), [], split).combined

    return build


def _static_build(mix: dict[str, float], split: dict) -> Build:
    def build(data: dict[str, pd.DataFrame], keep: list[str]) -> pd.DataFrame:
        w = pd.DataFrame({t: float(x) for t, x in mix.items()}, index=data["close"].index)
        return combine_portfolio(w, [], split).combined

    return build


def stress_portfolios(
    cands: list[Candidate], split: dict
) -> tuple[list[PortfolioDef], dict[str, frozenset[str]]]:
    """PortfolioDefs for `run_stress` plus, per portfolio name, the cell modes
    to keep. A static candidate X is one portfolio with every mode. A switching
    candidate X is `X` (replay cells only) plus `X[risk_on]` and `X[risk_off]`
    (frozen and hypothetical cells only)."""
    defs: list[PortfolioDef] = []
    modes: dict[str, frozenset[str]] = {}
    for cand in cands:
        tickers = list(REGISTRY[cand.fn].tickers(cand.params))
        defs.append(PortfolioDef(cand.id, _rule_build(cand, split), tickers))
        branches = branch_mixes(cand)
        if branches is None:
            modes[cand.id] = ALL_MODES
            continue
        modes[cand.id] = frozenset({"replay"})
        for state, mix in branches.items():
            name = f"{cand.id}[{state}]"
            defs.append(PortfolioDef(name, _static_build(mix, split), list(mix)))
            modes[name] = frozenset({"frozen", "hypothetical"})
    return defs, modes


def _candidate_result(
    cand: Candidate,
    cells: list,
    data: dict[str, pd.DataFrame],
    criteria: dict,
    split: dict,
    max_drawdown: float,
) -> dict:
    try:
        research = research_metrics(cand, data, criteria, split)
    except ValueError as exc:  # recorded as a failed test, never skipped (AGENTS.md)
        research = {"error": str(exc)}
    research_breach = bool(research.get("max_drawdown", 0.0) > max_drawdown)
    stress_breaches = sum(1 for c in cells if c.breach)
    return {
        "id": cand.id,
        "label": cand.label,
        "fn": cand.fn,
        "params": cand.params,
        "research": research,
        "research_breach": research_breach,
        "stress_breaches": stress_breaches,
        "unavailable": sum(1 for c in cells if c.unavailable is not None),
        "breach_count": stress_breaches + int(research_breach),
        "cells": [asdict(c) for c in cells],
    }


def run_core_compare(
    cands: list[Candidate],
    stress_cfg: StressConfig,
    data: dict[str, pd.DataFrame],
    criteria: dict,
    split: dict,
    max_drawdown: float,
) -> dict:
    """Every candidate: research metrics plus stress cells on windows that do
    not overlap validation/holdout. Stress frames are cut at the research end,
    so no later row reaches `run_stress`."""
    kept, excluded = split_windows(stress_cfg.windows, criteria)
    cfg = StressConfig(kept, stress_cfg.hypotheticals, stress_cfg.max_report_age_days)
    _, rend = period_bounds(criteria, "research")
    stress_data = {k: v.loc[:rend] for k, v in data.items()}
    portfolios, modes = stress_portfolios(cands, split)
    cells = [
        c
        for c in run_stress(cfg, portfolios, stress_data, max_drawdown, criteria)
        if c.mode in modes[c.portfolio]
    ]
    results = [
        _candidate_result(
            cand,
            [c for c in cells if c.portfolio.split("[")[0] == cand.id],
            data,
            criteria,
            split,
            max_drawdown,
        )
        for cand in cands
    ]
    return {"excluded_windows": [w.name for w in excluded], "candidates": results}
```

- [ ] **Step 5: Run the tests**

Run: `pixi run -e dev test -k core_compare -q --no-cov`
Expected: `17 passed`. (The module fixture runs all 7 candidates on 23 years of synthetic daily data; allow up to ~1 minute.)

- [ ] **Step 6: Format, lint, type-check, commit**

```bash
pixi run -e dev format
pixi run -e dev lint
pixi run -e dev type-check
git add src/qrl/core_compare.py tests/test_core_compare.py
git commit -m "Core compare: stress portfolios (branch states) and orchestration"
```

---

### Task 6: Markdown rendering, CLI, pixi task

**Files:**
- Modify: `src/qrl/core_compare.py`
- Create: `scripts/core_compare.py`
- Modify: `pixi.toml`
- Modify: `tests/test_core_compare.py`

- [ ] **Step 1: Confirm the CLI building blocks**

Run:
```bash
grep -n "^def load_profile\b\|^def load_criteria\|^def load_ohlcv" src/qrl/profile.py src/qrl/criteria.py src/qrl/data.py
grep -n "^stress = " pixi.toml
```
Expected: `load_profile(path)` returns a dict with `capital_split` and `max_drawdown`; `load_criteria(path) -> (dict, short_hash)`; `load_ohlcv(tickers, start, refresh, cache_dir)`; the `stress` task line exists to copy the style.

- [ ] **Step 2: Write the failing tests**

In `tests/test_core_compare.py` replace the top import block (through `ROOT = ...`) with:

```python
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qrl import core_compare
from qrl.core_compare import (
    Candidate,
    load_core_candidates,
    render_markdown,
    research_metrics,
    run_core_compare,
    split_windows,
)
from qrl.criteria import load_criteria
from qrl.data import synthetic_prices
from qrl.stress import Window, load_stress_config

ROOT = Path(__file__).resolve().parents[1]
```
(keep the `HOLDOUT`, `SPLIT`, `TICKERS`, `STATIC`, `_criteria`, `_data` definitions that follow it). Append:

```python
def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "core_compare_cli", ROOT / "scripts" / "core_compare.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cli = _load_cli()


def test_core_compare_markdown_records_hash_and_trial_count(compared):
    out, _ = compared
    report = {
        **out,
        "candidates_sha256": "ab" * 32,
        "stress_sha256": "cd" * 32,
        "trial_count": 7,
        "research_period": {"start": "2005-01-01", "end": "2018-12-31"},
        "max_drawdown": 0.35,
        "capital_split": SPLIT,
    }
    md = render_markdown(report)
    assert "ab" * 32 in md
    assert "- trial count: 7" in md
    for cid in "ABCDEFG":
        assert f"| {cid} |" in md
    table_rows = [ln for ln in md.splitlines() if ln.startswith("|")]
    assert not any("covid_2020" in ln or "inflation_2022" in ln for ln in table_rows)
    assert "validation and holdout data never used" in md
    assert "| proxied to cash |" in md
    assert "treated as cash" in md  # footnote: the dotcom cushion is understated
    # synthetic prices cover every ticker, so inject a proxied share into one cell
    cell = report["candidates"][3]["cells"][0]  # candidate D
    cell["detail"] = {"proxied_share": {"equity": 0.0, "gold": 0.2, "bonds": 0.4}}
    row = next(ln for ln in render_markdown(report).splitlines() if "bonds 40%" in ln)
    assert row.startswith("| D |") and "bonds 40%, gold 20%" in row


def _fake_ohlcv(drop: str | None = None):
    def fake(tickers, refresh=False):
        open_, close = synthetic_prices(tickers, start="1999-01-01", end="2021-12-31")
        if drop is not None:
            open_, close = open_.drop(columns=drop), close.drop(columns=drop)
        return {"open": open_, "close": close}

    return fake


def test_core_compare_main_writes_json_and_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "load_ohlcv", _fake_ohlcv())
    out_json, out_md = tmp_path / "r.json", tmp_path / "r.md"
    assert cli.main(["--out-json", str(out_json), "--out-md", str(out_md)]) == 0
    report = json.loads(out_json.read_text())
    assert report["trial_count"] == 7
    assert len(report["candidates_sha256"]) == 64
    assert [c["id"] for c in report["candidates"]] == list("ABCDEFG")
    scenarios = {cell["scenario"] for c in report["candidates"] for cell in c["cells"]}
    assert not scenarios & {"covid_2020", "inflation_2022"}
    assert "- trial count: 7" in out_md.read_text()


def test_core_compare_main_fails_on_missing_ticker(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "load_ohlcv", _fake_ohlcv(drop="IEF"))
    out_json, out_md = tmp_path / "r.json", tmp_path / "r.md"
    assert cli.main(["--out-json", str(out_json), "--out-md", str(out_md)]) == 1
    assert not out_json.exists()
    assert not out_md.exists()


def test_core_compare_main_fails_loudly_on_unpriced_candidate_ticker(
    tmp_path, monkeypatch, capsys
):
    def fake(tickers, refresh=False):
        open_, close = synthetic_prices(tickers, start="1999-01-01", end="2021-12-31")
        close.loc[close.loc[:"2018-12-31"].index[-1], "IEF"] = float("nan")  # unpriced at the end
        return {"open": open_, "close": close}

    def boom(*args, **kwargs):
        raise AssertionError("run_core_compare must not be called")

    monkeypatch.setattr(cli, "load_ohlcv", fake)
    monkeypatch.setattr(cli, "run_core_compare", boom)
    out_json, out_md = tmp_path / "r.json", tmp_path / "r.md"
    assert cli.main(["--out-json", str(out_json), "--out-md", str(out_md)]) == 1
    assert "IEF" in capsys.readouterr().out
    assert not out_json.exists()
    assert not out_md.exists()
```

- [ ] **Step 3: Run to verify the failure**

Run: `pixi run -e dev test -k core_compare -q --no-cov`
Expected: collection ERROR (`cannot import name 'render_markdown'` or missing `scripts/core_compare.py`).

- [ ] **Step 4: Implement `render_markdown`**

Append to `src/qrl/core_compare.py`:

```python
def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x + 0.0:.1%}"  # + 0.0 turns -0.0 into 0.0


def _research_row(c: dict) -> str:
    r = c["research"]
    head = f"| {c['id']} | {c['label']} |"
    if "error" in r:
        return f"{head} error: {r['error']} | | | | {c['breach_count']} |"
    return (
        f"{head} {_pct(r['cagr'])} | {r['sharpe']:.2f} | {_pct(r['max_drawdown'])} | "
        f"{r['turnover_per_year']:.2f} | {c['breach_count']} |"
    )


def _proxied(cell: dict) -> str:
    """Per-class weight shares proxied at the window start, e.g. "bonds 40%, gold 20%"."""
    shares = (cell.get("detail") or {}).get("proxied_share") or {}
    return ", ".join(f"{cls} {share:.0%}" for cls, share in sorted(shares.items()) if share > 0)


def _cell_row(cand_id: str, cell: dict) -> str:
    flag = "BREACH" if cell["breach"] else ("UNAVAILABLE" if cell["unavailable"] else "")
    return (
        f"| {cand_id} | {cell['portfolio']} | {cell['scenario']} | {cell['mode']} | "
        f"{_pct(cell['loss'])} | {_proxied(cell)} | {flag} |"
    )


def render_markdown(report: dict) -> str:
    """Deterministic markdown (no timestamp) so a re-run on the same data diffs."""
    rp, split = report["research_period"], report["capital_split"]
    excluded = ", ".join(report["excluded_windows"]) or "none"
    lines = [
        "# Core comparison (exploration only)",
        "",
        "Diagnostic of the pre-registered cores; it selects nothing. Spec: "
        "docs/superpowers/specs/2026-10-03-core-compare-design.md.",
        "",
        f"- candidates file sha256: `{report['candidates_sha256']}`",
        f"- trial count: {report['trial_count']}",
        f"- stress.yaml sha256: `{report['stress_sha256']}`",
        f"- research period: {rp['start']} to {rp['end']} (validation and holdout data never used "
        "(prices are downloaded in full; every computation is cut at the research end))",
        f"- capital split: core {split['core']:.0%} / sleeve {split['sleeve']:.0%} "
        "(sleeve empty, held as cash)",
        f"- max drawdown cap: {report['max_drawdown']:.0%} (config/profile.yaml)",
        f"- windows not evaluated (overlap validation): {excluded}",
        "",
        "## Research period",
        "",
        "| id | rule | CAGR | Sharpe | max drawdown | turnover/yr | breaches |",
        "|---|---|---|---|---|---|---|",
        *(_research_row(c) for c in report["candidates"]),
        "",
        "## Stress cells",
        "",
        "| id | portfolio | scenario | mode | loss | proxied to cash | flag |",
        "|---|---|---|---|---|---|---|",
        *(_cell_row(c["id"], cell) for c in report["candidates"] for cell in c["cells"]),
        "",
        "Note: in `dotcom_2000` the bond and gold ETFs did not yet exist, so bonds/gold "
        "weights are treated as cash (the \"proxied to cash\" column); this understates "
        "their cushion in that window.",
        "",
    ]
    return "\n".join(lines)
```

- [ ] **Step 5: Create the CLI**

Create `scripts/core_compare.py`:

```python
"""Core-comparison EXPLORATION (spec:
docs/superpowers/specs/2026-10-03-core-compare-design.md). Evaluates the
pre-registered candidates in config/core_candidates.yaml on research-period
metrics and on stress cells that never touch the validation or holdout periods
(covid_2020 and inflation_2022 are computed nowhere here). Prints a table,
writes research/core_compare.md and reports/core_compare.json (gitignored).
It tunes and selects nothing and changes no config.

Usage:
    python scripts/core_compare.py
    python scripts/core_compare.py --out-json reports/core_compare.json --out-md research/core_compare.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qrl.core_compare import (  # noqa: E402
    load_core_candidates,
    render_markdown,
    run_core_compare,
)
from qrl.criteria import load_criteria  # noqa: E402
from qrl.data import load_ohlcv  # noqa: E402
from qrl.periods import period_bounds  # noqa: E402
from qrl.profile import load_profile  # noqa: E402
from qrl.strategies import REGISTRY  # noqa: E402
from qrl.stress import EQUITY_PROXY, load_stress_config  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-json", default=str(ROOT / "reports" / "core_compare.json"))
    ap.add_argument("--out-md", default=str(ROOT / "research" / "core_compare.md"))
    args = ap.parse_args(argv)

    criteria, _ = load_criteria(ROOT / "config" / "criteria.yaml")
    holdout_start, _ = period_bounds(criteria, "holdout")
    rstart, rend = period_bounds(criteria, "research")
    if rstart is None or rend is None:
        raise ValueError("criteria research period needs a start and an end")
    cfg, stress_hash = load_stress_config(ROOT / "config" / "stress.yaml", holdout_start)
    profile = load_profile(ROOT / "config" / "profile.yaml")
    cands, cand_hash = load_core_candidates(ROOT / "config" / "core_candidates.yaml")

    tickers = sorted(
        {EQUITY_PROXY} | {t for c in cands for t in REGISTRY[c.fn].tickers(c.params)}
    )
    data = load_ohlcv(tickers, refresh=True)  # as scripts/stress.py
    missing = [t for t in tickers if t not in data["close"].columns]
    if missing:
        print(f"no price data for: {missing}")  # the loader drops tickers it cannot fetch
        return 1
    # every candidate ticker (signal tickers included) must be priced on the last
    # row at or before the research end, as scripts/stress.py does for the core
    last_row = data["close"].loc[:rend, tickers].iloc[-1]
    if not last_row.notna().all():
        print(f"unpriced at the research end {rend.date()}: {sorted(last_row.index[last_row.isna()])}")
        return 1

    result = run_core_compare(
        cands, cfg, data, criteria, profile["capital_split"], profile["max_drawdown"]
    )
    report = {
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "candidates_file": "config/core_candidates.yaml",
        "candidates_sha256": cand_hash,
        "stress_sha256": stress_hash,
        "trial_count": len(cands),
        "research_period": {"start": str(rstart.date()), "end": str(rend.date())},
        "max_drawdown": profile["max_drawdown"],
        "capital_split": profile["capital_split"],
        **result,
    }
    out_json, out_md = Path(args.out_json), Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    markdown = render_markdown(report)
    out_json.write_text(json.dumps(report, indent=2, default=str))
    out_md.write_text(markdown)
    print(markdown)
    print(f"Wrote {out_json} and {out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Modify `pixi.toml`: add after the `stress = "python scripts/stress.py"` line:

```toml
core-compare = "python scripts/core_compare.py"
```

- [ ] **Step 6: Run the tests**

Run: `pixi run -e dev test -k core_compare -q --no-cov`
Expected: `21 passed` (17 + markdown, main-writes, missing-ticker, unpriced-ticker). (The CLI test runs all 7 candidates on synthetic data; allow up to ~1 minute.)

- [ ] **Step 7: Format, lint, type-check, commit**

```bash
pixi run -e dev format
pixi run -e dev lint
pixi run -e dev type-check
git add src/qrl/core_compare.py scripts/core_compare.py pixi.toml tests/test_core_compare.py
git commit -m "Core compare: markdown report, CLI and core-compare pixi task"
```

---

### Task 7: Quality gate and full suite (once)

- [ ] **Step 1: Quality gate**

Run:
```bash
pixi run -e dev format-check
pixi run -e dev lint
pixi run -e dev type-check
```
Expected: all clean. Fix anything reported (formatting only, in files this plan touched), and commit as `Core compare: quality gate fixes` if there is a diff.

- [ ] **Step 2: Full suite, once**

Run: `pixi run -e dev test -q --no-cov`
Expected: `BASE + 41 passed` with BASE from Task 1 Step 1 (12 core_mix/strategies, 8 stress, 21 core_compare). Any failure in a file this plan did not touch is a regression: STOP and report it with the 15 most relevant log lines.

- [ ] **Step 3: Confirm no locked file changed**

Run: `git diff --stat development -- src/qrl/engine.py src/qrl/metrics.py src/qrl/periods.py src/qrl/checks.py config/criteria.yaml config/profile.yaml config/portfolio.yaml config/paper.yaml config/combined.yaml config/combined_null.yaml config/factor.yaml`
Expected: no output.

---

### Task 8: Generate and commit the first report

**Files:**
- Create (generated): `research/core_compare.md`

- [ ] **Step 1: Confirm real-data start dates**

The candidates need prices from before the research start (2005-01-01) so every core is warm at that date. Run:
```bash
pixi run -e dev python -c "
import sys; sys.path.insert(0,'src')
from qrl.data import load_ohlcv
d = load_ohlcv(['SPY','QQQ','GLD','IEF','TLT','SHY'], refresh=True)['close']
print(d.apply(lambda s: s.first_valid_index().date()).to_string())
"
```
Expected (approximate, from public listing dates): GLD 2004-11-18, IEF/TLT/SHY 2002-07-26, SPY 1993, QQQ 1999. Every date must be before 2005-01-01. If one is later, `core-compare` will record that candidate's research row as an `error` (by design); report which ticker to the human before committing, do not change the candidates.

- [ ] **Step 2: Run the tool**

Run: `pixi run -e dev core-compare`
Expected: exit 0; prints the markdown, writes `research/core_compare.md` and `reports/core_compare.json`. Sanity checks only (do not pick a winner, do not tune): the table has 7 candidate rows A-G; the header shows the candidates sha256 and `trial count: 7`; "windows not evaluated" lists `covid_2020, inflation_2022`; no table row mentions those two; `dotcom_2000` frozen cells show bond/gold weights proxied to cash in the "proxied to cash" column (and as `proxied_share` in the JSON detail), with the footnote below the table. If the run fails or a row shows `error:`, STOP and report the message.

- [ ] **Step 3: Confirm only the markdown is new, then commit**

Run: `git status --short`
Expected: only `?? research/core_compare.md` (`reports/` is gitignored).

```bash
git add research/core_compare.md
git commit -m "Core compare: first generated report (research period and pre-validation stress cells)"
```
Do NOT push and do NOT open a PR; report the commit shas and the generated table's candidate rows to the controller.

---

## Self-review notes (for the plan author)

- Spec coverage: `core_mix` (Task 1), `bonds` class and amendment (Task 2), pre-registered candidates (Task 3), research-only metrics and validation-safe windows (Task 4), stress orchestration with branch states (Task 5), CLI/markdown/task (Task 6), guardrail tests in Tasks 4-5 and 6, final commit (Task 8).
- Locked-file touches are limited to the two allowed test edits and the dated `config/stress.yaml` amendment; Task 7 Step 3 verifies it.
- Known behaviours worth the reviewer's eye: `stress.yaml`'s sha256 changes, so an existing `reports/stress.json` becomes "stale" in the daily check until `pixi run stress` is re-run (not part of this plan); frozen/hypothetical cells for switching candidates are branch-state portfolios, not "today's weights".
