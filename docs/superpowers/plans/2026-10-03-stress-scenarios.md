# Stress-Scenario Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A diagnostic `pixi run stress` that reports how much the chosen portfolio (and the core plus each paper-track candidate) would lose under historical shock windows and pre-registered hypothetical shocks, flags losses above the 35% cap, and surfaces breaches/staleness as daily-check warnings.

**Architecture:** Pure functions in `src/qrl/stress.py` (config loading, three loss measures, labels, orchestration, warning text). A thin CLI `scripts/stress.py` wires real data, ledger and configs and writes `reports/stress.json`. `scripts/daily_check.py` reads that JSON and adds a `stress_warnings` channel that never touches `HealthReport.ok` or the exit status.

**Tech Stack:** Python 3.12, pandas, PyYAML, pytest; existing `qrl.engine.run_backtest`, `qrl.portfolio.combine_portfolio`, `qrl.metrics.drawdown`, `qrl.paper`, `qrl.periods.period_bounds`.

**Spec:** `docs/superpowers/specs/2026-10-03-stress-scenarios-design.md`

**Hard rules (AGENTS.md):** do NOT edit `src/qrl/engine.py`, `metrics.py`, `periods.py`, `checks.py`, any existing test, or any locked config (`criteria.yaml`, `combined*.yaml`, `paper.yaml`, `factor.yaml`, `profile.yaml`, `portfolio.yaml`). Never call `slice_period(..., unseal_holdout=True)`. Run commands as `pixi run -e dev ...` (tasks are ambiguous across environments without `-e`).

**Before every commit:** run `pixi run -e dev format` (ruff format; line length 100) and `pixi run -e dev lint`; the code blocks below are not guaranteed to be pre-formatted.

---

## File structure

| File | Action | Responsibility |
|---|---|---|
| `config/stress.yaml` | create | Pre-registered windows, hypotheticals, report max age |
| `src/qrl/stress.py` | create | All stress logic, pure (no network, no file writes) |
| `tests/test_stress.py` | create | Unit tests for `qrl.stress` and the daily-check wiring |
| `scripts/stress.py` | create | CLI: load configs/ledger/data, run, print, write JSON |
| `scripts/daily_check.py` | modify | Add `stress_warnings` to output; exit status unchanged |
| `pixi.toml` | modify | Add `stress` task |
| `docs/superpowers/specs/2026-10-03-stress-scenarios-design.md` | modify | Warm-up 3y → 1y (see Task 1) |

---

### Task 1: Spec correction — warm-up length

The spec says replay warms up 3 calendar years before the window. For `gfc_2008` (start 2007-10-09) that begins 2004-10-09, before GLD's first price (2004-11-18). `run_backtest` raises on a missing price for a held position, so the core's 2008 replay would always be `unavailable`. Two calendar years (~504 trading days) cover every candidate lookback. Step 1 was run by the owner: trend_pullback 150, low_range_close 150, regime_pullback trend_lookback 250 / breadth_ma 100, core_trend 200 (so one year would not cover regime_pullback's 250). 2007-10-09 minus 2 years = 2005-10-09, after GLD's 2004-11 launch.

**Files:** Modify `docs/superpowers/specs/2026-10-03-stress-scenarios-design.md`

- [ ] **Step 1: Check candidate lookbacks fit in one year**

Run:
```bash
pixi run -e dev python -c "
import sys; sys.path.insert(0,'src')
from pathlib import Path
from qrl.ledger import Ledger
from qrl.paper import load_paper_config, load_candidate
cfg,_ = load_paper_config('config/paper.yaml')
led = Ledger(Path('research/ledger.sqlite'))
for e in cfg['candidates']:
    c = load_candidate(led, e)
    print(e['family'], {k:v for k,v in c['params'].items() if k!='tickers'})
"
```
(If `Ledger(...)` takes different arguments, copy the construction from `scripts/paper_track.py`.)
Expected: every lookback/window-like parameter is ≤ 230 trading days. If any exceeds that, STOP and report to the human; do not pick a different warm-up yourself.

- [ ] **Step 2: Edit the spec**

In section "## Loss measures", replace `start 3 calendar years before the window (warm-up for lookbacks)` with `start 2 calendar years before the window (warm-up for lookbacks: the longest is regime_pullback's 250 days; 3 years would precede GLD's 2004-11 launch for gfc_2008)`.

Also align the spec's "## Interfaces" with the plan: `load_stress_config(path, holdout_start)`; `run_stress(...) -> list[Cell]` (the CLI assembles the report dict); and in "## Honesty labels and guards" add `out-of-sample` (a candidate in a window before its research period, e.g. dotcom_2000 if ever replayed). In "## Tests", replace "on `synthetic_prices`" with "on small hand-built frames".

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-10-03-stress-scenarios-design.md
git commit -m "Stress: 2-year replay warm-up (regime_pullback lookback 250)"
```

---

### Task 2: Config file and loader

**Files:**
- Create: `config/stress.yaml`
- Create: `src/qrl/stress.py`
- Create: `tests/test_stress.py`

- [ ] **Step 1: Create `config/stress.yaml`**

```yaml
# PRE-REGISTERED stress scenarios (diagnostic only; spec
# docs/superpowers/specs/2026-10-03-stress-scenarios-design.md, owner
# approval 2026-10-03). Fixed before any result was seen. After the first
# `pixi run stress` report, change only via a dated amendment comment here.
# Every report records this file's sha256; daily-check flags a mismatch.

max_report_age_days: 30

# Historical windows, inclusive. replay: false = frozen-weights only.
# All must end before the holdout start (config/criteria.yaml); the loader
# refuses otherwise.
windows:
  - {name: dotcom_2000, start: "2000-03-24", end: "2002-10-09", replay: false} # GLD absent before 2004-11
  - {name: gfc_2008, start: "2007-10-09", end: "2009-03-09", replay: true}
  - {name: covid_2020, start: "2020-02-19", end: "2020-04-30", replay: true}
  - {name: inflation_2022, start: "2022-01-03", end: "2022-10-31", replay: true}

# Instantaneous shocks per asset class, applied to the latest weights.
# Classes: gold = GLD; equity = every other ticker; cash = unallocated (0%).
# These are judgments, not data.
hypotheticals:
  - {name: no_safe_haven, equity: -0.50, gold: -0.20}       # stocks and gold fall together
  - {name: stagflation, equity: -0.45, gold: 0.10}          # 1973-74-style rotation
  - {name: energy_shock_severe, equity: -0.40, gold: -0.10} # fuel/diesel shock worse than 2022
  - {name: tech_crash, equity: -0.60, gold: 0.0}            # 2000-02-scale equity collapse
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_stress.py`:

```python
"""Tests for the stress-scenario diagnostic (qrl.stress, scripts/stress.py
wiring into scripts/daily_check.py). Offline; small hand-built frames only.
Spec: docs/superpowers/specs/2026-10-03-stress-scenarios-design.md.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from qrl.stress import load_stress_config

ROOT = Path(__file__).resolve().parents[1]
HOLDOUT = pd.Timestamp("2023-01-01")


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "stress.yaml"
    p.write_text(text)
    return p


GOOD = """
max_report_age_days: 30
windows:
  - {name: w1, start: "2008-01-02", end: "2008-06-30", replay: true}
hypotheticals:
  - {name: h1, equity: -0.5, gold: -0.2}
"""


def test_shipped_config_loads():
    cfg, digest = load_stress_config(ROOT / "config" / "stress.yaml", HOLDOUT)
    assert [w.name for w in cfg.windows] == [
        "dotcom_2000",
        "gfc_2008",
        "covid_2020",
        "inflation_2022",
    ]
    assert not cfg.windows[0].replay
    assert {h.name for h in cfg.hypotheticals} == {
        "no_safe_haven",
        "stagflation",
        "energy_shock_severe",
        "tech_crash",
    }
    assert cfg.max_report_age_days == 30
    assert len(digest) == 64  # full sha256


def test_loads_good_config(tmp_path):
    cfg, _ = load_stress_config(_write(tmp_path, GOOD), HOLDOUT)
    w = cfg.windows[0]
    assert (w.start, w.end, w.replay) == (
        pd.Timestamp("2008-01-02"),
        pd.Timestamp("2008-06-30"),
        True,
    )
    assert cfg.hypotheticals[0].shocks == {"equity": -0.5, "gold": -0.2}


def test_rejects_window_reaching_holdout(tmp_path):
    text = GOOD.replace('end: "2008-06-30"', 'end: "2023-01-01"')
    with pytest.raises(ValueError, match="holdout"):
        load_stress_config(_write(tmp_path, text), HOLDOUT)


def test_rejects_start_not_before_end(tmp_path):
    text = GOOD.replace('start: "2008-01-02"', 'start: "2008-07-01"')
    with pytest.raises(ValueError, match="before"):
        load_stress_config(_write(tmp_path, text), HOLDOUT)


def test_rejects_bad_date(tmp_path):
    text = GOOD.replace('"2008-01-02"', '"not-a-date"')
    with pytest.raises(ValueError, match="not-a-date|Unknown|convert|parse"):
        load_stress_config(_write(tmp_path, text), HOLDOUT)


def test_rejects_unknown_class(tmp_path):
    text = GOOD.replace("gold: -0.2", "bonds: -0.2")
    with pytest.raises(ValueError, match="unknown"):
        load_stress_config(_write(tmp_path, text), HOLDOUT)


def test_rejects_shock_at_or_below_minus_one(tmp_path):
    text = GOOD.replace("equity: -0.5", "equity: -1.0")
    with pytest.raises(ValueError, match="-1"):
        load_stress_config(_write(tmp_path, text), HOLDOUT)


def test_rejects_duplicate_names(tmp_path):
    text = GOOD.replace("name: h1", "name: w1")
    with pytest.raises(ValueError, match="duplicate"):
        load_stress_config(_write(tmp_path, text), HOLDOUT)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pixi run -e dev pytest tests/test_stress.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'qrl.stress'`.

- [ ] **Step 4: Implement the loader**

Create `src/qrl/stress.py`:

```python
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
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

SHOCK_CLASSES = ("equity", "gold")


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
        if any(v <= -1 for v in shocks.values()):
            raise ValueError(f"hypothetical {h['name']}: a shock must be above -1 (-100%)")
        hypotheticals.append(Hypothetical(str(h["name"]), shocks))

    names = [w.name for w in windows] + [h.name for h in hypotheticals]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise ValueError(f"duplicate scenario names: {dupes}")

    cfg = StressConfig(windows, hypotheticals, int(doc["max_report_age_days"]))
    return cfg, hashlib.sha256(raw).hexdigest()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pixi run -e dev pytest tests/test_stress.py -v`
Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add config/stress.yaml src/qrl/stress.py tests/test_stress.py
git commit -m "Stress: pre-registered scenario config and loader"
```

---

### Task 3: Window drawdown and hypothetical loss

**Files:** Modify `src/qrl/stress.py`, `tests/test_stress.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_stress.py`; extend the import line to `from qrl.stress import Hypothetical, asset_class, hypothetical_loss, load_stress_config, window_drawdown`)

```python
def test_window_drawdown_counts_first_day_loss():
    # equity 1.0 -> 0.9 -> 0.945; qrl.metrics.drawdown alone would miss day 1.
    r = pd.Series([-0.10, 0.05], index=pd.bdate_range("2020-01-06", periods=2))
    assert window_drawdown(r) == pytest.approx(0.10)


def test_window_drawdown_zero_when_only_rising():
    r = pd.Series([0.01, 0.02], index=pd.bdate_range("2020-01-06", periods=2))
    assert window_drawdown(r) == pytest.approx(0.0)


def test_asset_class():
    assert asset_class("GLD") == "gold"
    assert asset_class("QQQ") == "equity"
    assert asset_class("AAPL") == "equity"


def test_hypothetical_loss_by_class():
    w = pd.Series({"AAA": 0.5, "GLD": 0.3, "BBB": 0.0})  # 0.2 cash
    h = Hypothetical("x", {"equity": -0.5, "gold": -0.2})
    assert hypothetical_loss(w, h) == pytest.approx(0.5 * 0.5 + 0.3 * 0.2)


def test_hypothetical_gain_is_negative_loss():
    w = pd.Series({"GLD": 1.0})
    assert hypothetical_loss(w, Hypothetical("x", {"gold": 0.1})) == pytest.approx(-0.1)
```

- [ ] **Step 2: Run to verify failure**

Run: `pixi run -e dev pytest tests/test_stress.py -v`
Expected: ImportError for `asset_class` / `window_drawdown` / `hypothetical_loss`.

- [ ] **Step 3: Implement** (add to `src/qrl/stress.py`; add `from .metrics import drawdown` to the imports)

```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `pixi run -e dev pytest tests/test_stress.py -v`
Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
git add src/qrl/stress.py tests/test_stress.py
git commit -m "Stress: window drawdown from 1.0 and hypothetical loss"
```

---

### Task 4: Frozen-weights loss with per-class proxies

**Files:** Modify `src/qrl/stress.py`, `tests/test_stress.py`

- [ ] **Step 1: Write the failing tests** (add `Window, frozen_loss` to the import)

```python
def _win(start, end, replay=True, name="w"):
    return Window(name, pd.Timestamp(start), pd.Timestamp(end), replay)


def test_frozen_loss_buy_and_hold_no_rebalance():
    idx = pd.bdate_range("2008-01-07", periods=3)
    close = pd.DataFrame({"AAA": [100.0, 80.0, 90.0], "GLD": [100.0, 100.0, 100.0]}, index=idx)
    w = pd.Series({"AAA": 0.5, "GLD": 0.3})  # 0.2 cash
    loss, detail = frozen_loss(w, close, _win("2008-01-07", "2008-01-09"))
    # value: 1.0 -> 0.5*0.8+0.3+0.2 = 0.9 -> 0.5*0.9+0.5 = 0.95
    assert loss == pytest.approx(0.10)
    assert detail["proxied_share"] == {"equity": 0.0, "gold": 0.0}


def test_frozen_loss_proxies_equity_to_spy_and_gold_to_cash():
    idx = pd.bdate_range("2001-01-08", periods=2)
    close = pd.DataFrame(
        {
            "AAA": [float("nan"), float("nan")],
            "GLD": [float("nan"), float("nan")],
            "SPY": [100.0, 50.0],
        },
        index=idx,
    )
    w = pd.Series({"AAA": 0.6, "GLD": 0.4})
    loss, detail = frozen_loss(w, close, _win("2001-01-08", "2001-01-09"))
    # AAA -> SPY (halves), GLD -> cash: 1.0 -> 0.6*0.5 + 0.4 = 0.7
    assert loss == pytest.approx(0.30)
    assert detail["proxied_share"] == {"equity": pytest.approx(0.6), "gold": pytest.approx(0.4)}


def test_frozen_loss_ticker_absent_from_frame_is_proxied():
    idx = pd.bdate_range("2001-01-08", periods=2)
    close = pd.DataFrame({"SPY": [100.0, 90.0]}, index=idx)
    loss, detail = frozen_loss(pd.Series({"ZZZ": 1.0}), close, _win("2001-01-08", "2001-01-09"))
    assert loss == pytest.approx(0.10)
    assert detail["proxied_share"]["equity"] == pytest.approx(1.0)


def test_frozen_loss_no_prices_in_window_raises():
    close = pd.DataFrame({"SPY": [100.0]}, index=pd.bdate_range("2010-01-04", periods=1))
    with pytest.raises(ValueError, match="no prices"):
        frozen_loss(pd.Series({"SPY": 1.0}), close, _win("2001-01-08", "2001-01-09"))
```

- [ ] **Step 2: Run to verify failure**

Run: `pixi run -e dev pytest tests/test_stress.py -v`
Expected: ImportError for `frozen_loss`.

- [ ] **Step 3: Implement** (add to `src/qrl/stress.py`)

```python
EQUITY_PROXY = "SPY"


def frozen_loss(weights: pd.Series, close: pd.DataFrame, window: Window) -> tuple[float, dict]:
    """Buy `weights` at the window's first close, hold without rebalancing,
    return (worst drawdown inside the window, detail). A ticker with no price
    at the window's first day is replaced per class: equity -> SPY, gold ->
    cash. A position priced at the start but with later gaps is carried at
    its last price (forward-fill). Raises ValueError if the window has no
    prices, or SPY is needed but unpriced."""
    px = close.loc[window.start : window.end]
    if px.empty:
        raise ValueError(f"no prices in window {window.name}")
    first = px.iloc[0]
    w = weights[weights > 0]
    proxied = {c: 0.0 for c in SHOCK_CLASSES}
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
                raise ValueError(
                    f"{EQUITY_PROXY} unpriced at {window.name} start; cannot proxy {ticker}"
                )
            path = px[EQUITY_PROXY].ffill()
        value += wt * path / path.iloc[0]
    return window_drawdown(value.pct_change().iloc[1:]), {"proxied_share": proxied}
```

- [ ] **Step 4: Run to verify pass**

Run: `pixi run -e dev pytest tests/test_stress.py -v`
Expected: 17 passed.

- [ ] **Step 5: Commit**

```bash
git add src/qrl/stress.py tests/test_stress.py
git commit -m "Stress: frozen-weights loss with equity->SPY, gold->cash proxies"
```

---

### Task 5: Rule-replay loss

**Files:** Modify `src/qrl/stress.py`, `tests/test_stress.py`

`run_backtest(open_, close, target_weights, cost_bps=5.0)`: weights decided at close t execute at the next open; `BacktestResult.returns` are daily net returns. It raises `ValueError("Missing price for a held position ...")` on a NaN price for a held position.

- [ ] **Step 1: Write the failing tests** (add `PortfolioDef, priced, replay_loss` to the import)

```python
def _frames(close: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {"open": close.copy(), "close": close}


def _hold(ticker: str, weight: float = 1.0):
    def build(data, keep):
        return pd.DataFrame({ticker: weight}, index=data["close"].index)

    return build


def test_priced_requires_every_day():
    idx = pd.bdate_range("2020-01-01", periods=3)
    close = pd.DataFrame({"A": [1.0, 1.0, 1.0], "B": [float("nan"), 1.0, 1.0]}, index=idx)
    assert priced(close, ["A", "B", "C"]) == ["A"]


def test_replay_loss_measures_inside_window_only():
    idx = pd.bdate_range("2020-01-01", periods=10)  # Jan 1,2,3,6,7,8,9,10,13,14
    c = [100, 100, 100, 100, 90, 80, 85, 100, 10, 10]  # crash on Jan 13 is AFTER the window
    close = pd.DataFrame({"A": [float(x) for x in c]}, index=idx)
    p = PortfolioDef("p", _hold("A"), core_tickers=["A"], sleeve_universe=[], candidate=False)
    loss, detail = replay_loss(_frames(close), p, _win("2020-01-07", "2020-01-10"))
    # in-window equity 1, .9, .8, .85, 1.0 (no costs: only trade is Jan 2)
    assert loss == pytest.approx(0.20)
    assert detail == {"sleeve_dropped": 0, "sleeve_dropped_share": 0.0}


def test_replay_frames_end_at_window_end():
    idx = pd.bdate_range("2020-01-01", periods=10)
    close = pd.DataFrame({"A": 100.0}, index=idx)
    seen = {}

    def build(data, keep):
        seen["last"] = data["close"].index.max()
        return pd.DataFrame({"A": 1.0}, index=data["close"].index)

    p = PortfolioDef("p", build, core_tickers=["A"], sleeve_universe=[], candidate=False)
    replay_loss(_frames(close), p, _win("2020-01-07", "2020-01-08"))
    assert seen["last"] == pd.Timestamp("2020-01-08")


def test_replay_drops_unpriced_sleeve_tickers():
    idx = pd.bdate_range("2020-01-01", periods=5)
    close = pd.DataFrame({"A": 100.0, "S1": 50.0, "S2": [float("nan")] + [50.0] * 4}, index=idx)
    got = {}

    def build(data, keep):
        got["keep"] = keep
        return pd.DataFrame({"A": 1.0}, index=data["close"].index)

    p = PortfolioDef("p", build, core_tickers=["A"], sleeve_universe=["S1", "S2"], candidate=True)
    _, detail = replay_loss(_frames(close), p, _win("2020-01-06", "2020-01-07"))
    assert got["keep"] == ["S1"]
    assert detail == {"sleeve_dropped": 1, "sleeve_dropped_share": 0.5}


def test_replay_unpriced_core_raises():
    idx = pd.bdate_range("2020-01-01", periods=5)
    close = pd.DataFrame({"A": [float("nan")] + [100.0] * 4}, index=idx)
    p = PortfolioDef("p", _hold("A"), core_tickers=["A"], sleeve_universe=[], candidate=False)
    with pytest.raises(ValueError, match="core"):
        replay_loss(_frames(close), p, _win("2020-01-06", "2020-01-07"))
```

- [ ] **Step 2: Run to verify failure**

Run: `pixi run -e dev pytest tests/test_stress.py -v`
Expected: ImportError for `PortfolioDef` / `priced` / `replay_loss`.

- [ ] **Step 3: Implement** (add to `src/qrl/stress.py`; add `from collections.abc import Callable`, `from dataclasses import field` and `from .engine import run_backtest` to the imports)

```python
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
    ticker raises ValueError (the cell becomes `unavailable`)."""
    frames = {k: v.loc[window.start - WARMUP : window.end] for k, v in data.items()}
    close = frames["close"]
    if priced(close, portfolio.core_tickers) != list(portfolio.core_tickers):
        raise ValueError(f"core not fully priced over warm-up + {window.name}")
    keep = priced(close, portfolio.sleeve_universe)
    weights = portfolio.build(frames, keep)
    cols = list(weights.columns)
    result = run_backtest(frames["open"][cols], close[cols], weights)
    loss = window_drawdown(result.returns.loc[window.start : window.end])
    n = len(portfolio.sleeve_universe)
    dropped = n - len(keep)
    return loss, {"sleeve_dropped": dropped, "sleeve_dropped_share": dropped / n if n else 0.0}
```

- [ ] **Step 4: Run to verify pass**

Run: `pixi run -e dev pytest tests/test_stress.py -v`
Expected: 22 passed. If `test_replay_loss_measures_inside_window_only` is off by a cost amount, read `src/qrl/engine.py`'s timing docstring (do NOT edit engine.py) and fix the test's expectation, explaining the timing in a comment.

- [ ] **Step 5: Commit**

```bash
git add src/qrl/stress.py tests/test_stress.py
git commit -m "Stress: rule-replay loss, truncated at window end"
```

---

### Task 6: Labels, cells and orchestration

**Files:** Modify `src/qrl/stress.py`, `tests/test_stress.py`

- [ ] **Step 1: Write the failing tests** (add `replay_label, run_stress, StressConfig` to the import)

```python
CRITERIA = {
    "periods": {
        "research": {"start": "2005-01-01", "end": "2018-12-31"},
        "validation": {"start": "2019-01-01", "end": "2022-12-31"},
        "holdout": {"start": "2023-01-01"},
    }
}


def test_replay_label():
    gfc, covid = _win("2007-10-09", "2009-03-09"), _win("2020-02-19", "2020-04-30")
    assert replay_label(False, gfc, CRITERIA) == "clean"
    assert replay_label(True, gfc, CRITERIA) == "in-sample"
    assert replay_label(True, covid, CRITERIA) == "validation-seen"
    assert replay_label(True, _win("2000-03-24", "2002-10-09"), CRITERIA) == "out-of-sample"


def test_run_stress_cells_labels_and_breach():
    idx = pd.bdate_range("2006-01-02", "2009-12-31")
    close = pd.DataFrame({"AAA": 100.0, "GLD": 100.0, "SPY": 100.0}, index=idx)
    data = _frames(close)
    cfg = StressConfig(
        windows=[
            _win("2003-01-02", "2003-06-30", replay=False, name="early"),  # before data
            _win("2007-10-09", "2009-03-09", replay=True, name="gfc"),
        ],
        hypotheticals=[Hypothetical("crash", {"equity": -0.5})],
        max_report_age_days=30,
    )
    core = PortfolioDef("chosen", _hold("AAA", 1.0), core_tickers=["AAA"])
    cand = PortfolioDef(
        "core+x", _hold("AAA", 1.0), core_tickers=["AAA"], sleeve_universe=["AAA"], candidate=True
    )
    cells = run_stress(cfg, [core, cand], data, max_drawdown=0.35, criteria=CRITERIA)
    by = {(c.portfolio, c.scenario, c.mode): c for c in cells}

    assert ("chosen", "early", "replay") not in by  # frozen-only window
    early = by[("chosen", "early", "frozen")]
    assert early.loss is None and "no prices" in early.unavailable
    assert by[("chosen", "gfc", "replay")].label == "clean"
    assert by[("core+x", "gfc", "replay")].label == "in-sample"
    assert by[("chosen", "gfc", "frozen")].label == "current-weights"
    assert by[("chosen", "gfc", "frozen")].loss == pytest.approx(0.0)
    crash = by[("chosen", "crash", "hypothetical")]
    assert crash.loss == pytest.approx(0.5) and crash.breach is True
    assert by[("chosen", "gfc", "frozen")].breach is False
    assert len(cells) == 2 * (1 + 2 + 1)
```

- [ ] **Step 2: Run to verify failure**

Run: `pixi run -e dev pytest tests/test_stress.py -v`
Expected: ImportError for `replay_label` / `run_stress`.

- [ ] **Step 3: Implement** (add to `src/qrl/stress.py`; add `from .periods import period_bounds`)

```python
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
    except (ValueError, KeyError) as exc:  # missing data -> reported, never dropped
        return Cell(portfolio, scenario, mode, label, None, None, {}, unavailable=str(exc))
    return Cell(portfolio, scenario, mode, label, loss, bool(loss > max_drawdown), detail)


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
        latest = p.build(data, priced(data["close"].tail(1), p.sleeve_universe)).iloc[-1]
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
                    lambda w=w, latest=latest: frozen_loss(latest, data["close"], w),
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
                    lambda h=h, latest=latest: (hypothetical_loss(latest, h), {}),
                    max_drawdown,
                )
            )
    return cells
```

Note: the latest-weights build keeps sleeve tickers priced on the last row only (today's tradable set), not the full history.

- [ ] **Step 4: Run to verify pass**

Run: `pixi run -e dev pytest tests/test_stress.py -v`
Expected: 24 passed.

- [ ] **Step 5: Commit**

```bash
git add src/qrl/stress.py tests/test_stress.py
git commit -m "Stress: honesty labels, unavailable cells, orchestration"
```

---

### Task 7: Report hashes and warning text

**Files:** Modify `src/qrl/stress.py`, `tests/test_stress.py`

- [ ] **Step 1: Write the failing tests** (add `file_hashes, stress_config_paths, stress_warnings` to the import)

```python
NOW = pd.Timestamp("2026-10-03T12:00:00+00:00")
HASHES = {"stress.yaml": "a", "portfolio.yaml": "b", "paper.yaml": "c", "profile.yaml": "d"}


def _report(**over):
    rep = {
        "generated_at": "2026-10-01T12:00:00+00:00",
        "max_report_age_days": 30,
        "max_drawdown": 0.35,
        "hashes": dict(HASHES),
        "cells": [
            {
                "portfolio": "chosen",
                "scenario": "gfc_2008",
                "mode": "frozen",
                "loss": 0.2,
                "breach": False,
            },
        ],
    }
    rep.update(over)
    return rep


def test_stress_config_paths_and_hashes():
    paths = stress_config_paths(ROOT)
    assert set(paths) == set(HASHES)
    hashes = file_hashes(paths)
    assert all(len(h) == 64 for h in hashes.values())


def test_no_warnings_when_fresh_and_clean():
    assert stress_warnings(_report(), HASHES, NOW) == []


def test_missing_report_warns():
    (msg,) = stress_warnings(None, HASHES, NOW)
    assert "missing" in msg


def test_old_report_warns():
    (msg,) = stress_warnings(_report(generated_at="2026-08-01T00:00:00+00:00"), HASHES, NOW)
    assert "days old" in msg


def test_changed_config_warns():
    (msg,) = stress_warnings(_report(), {**HASHES, "portfolio.yaml": "zzz"}, NOW)
    assert "stale" in msg and "portfolio.yaml" in msg


def test_breach_warns():
    cells = [
        {
            "portfolio": "chosen",
            "scenario": "tech_crash",
            "mode": "hypothetical",
            "loss": 0.48,
            "breach": True,
        }
    ]
    (msg,) = stress_warnings(_report(cells=cells), HASHES, NOW)
    assert "BREACH" in msg and "tech_crash" in msg and "48.0%" in msg
```

- [ ] **Step 2: Run to verify failure**

Run: `pixi run -e dev pytest tests/test_stress.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement** (add to `src/qrl/stress.py`)

```python
def stress_config_paths(root: Path) -> dict[str, Path]:
    """Configs whose change makes a stress report stale."""
    cfg = Path(root) / "config"
    return {
        name: cfg / name for name in ("stress.yaml", "portfolio.yaml", "paper.yaml", "profile.yaml")
    }


def file_hashes(paths: dict[str, Path]) -> dict[str, str]:
    """Full sha256 of each file's raw bytes."""
    return {name: hashlib.sha256(Path(p).read_bytes()).hexdigest() for name, p in paths.items()}


def stress_warnings(
    report: dict | None, current_hashes: dict[str, str], now: pd.Timestamp
) -> list[str]:
    """Daily-check warning lines for a saved stress report. Never raises on
    a stale or breaching report; it only describes it."""
    if report is None:
        return ["stress report missing: run `pixi run stress`"]
    out = []
    age = (now - pd.Timestamp(report["generated_at"])).days
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
```

- [ ] **Step 4: Run to verify pass**

Run: `pixi run -e dev pytest tests/test_stress.py -v`
Expected: 30 passed.

- [ ] **Step 5: Commit**

```bash
git add src/qrl/stress.py tests/test_stress.py
git commit -m "Stress: config hashes and daily-check warning text"
```

---

### Task 8: CLI `scripts/stress.py` and pixi task

**Files:** Create `scripts/stress.py`; Modify `pixi.toml`

This script touches the network/cache and the ledger, so it is exercised by a real run (Step 3), not unit tests; all logic it calls is tested above.

- [ ] **Step 1: Create `scripts/stress.py`**

```python
"""Stress-scenario DIAGNOSTIC (spec:
docs/superpowers/specs/2026-10-03-stress-scenarios-design.md). Builds the
chosen portfolio (config/portfolio.yaml) and core + each paper-track
candidate (config/paper.yaml), runs config/stress.yaml's scenarios through
`qrl.stress`, prints a table and writes reports/stress.json (gitignored).
It tunes and selects nothing.

Usage:
    python scripts/stress.py
    python scripts/stress.py --out reports/stress.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qrl.criteria import load_criteria  # noqa: E402
from qrl.data import load_ohlcv  # noqa: E402
from qrl.ledger import Ledger  # noqa: E402
from qrl.paper import candidate_weights, load_candidate, load_paper_config  # noqa: E402
from qrl.periods import period_bounds  # noqa: E402
from qrl.portfolio import combine_portfolio, load_portfolio_config  # noqa: E402
from qrl.profile import load_profile  # noqa: E402
from qrl.strategies import REGISTRY, SLEEVE_REGISTRY  # noqa: E402
from qrl.stress import (  # noqa: E402
    EQUITY_PROXY,
    PortfolioDef,
    file_hashes,
    load_stress_config,
    run_stress,
    stress_config_paths,
)

_ALL_SPECS = {**REGISTRY, **SLEEVE_REGISTRY}


def _member_weights(fn: str, params: dict, data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Same construction scripts/daily_check.py uses for portfolio.yaml members."""
    spec = _ALL_SPECS[fn]
    cols = spec.tickers(params)
    kwargs = {k: v for k, v in params.items() if k != "tickers"}
    return spec.weights(*[data[f][cols] for f in spec.fields], **kwargs)


def _restrict(params: dict, keep: list[str]) -> dict:
    if "tickers" not in params:
        return params
    keep_set = set(keep)
    return {**params, "tickers": [t for t in params["tickers"] if t in keep_set]}


def _portfolios(portfolio_cfg: dict, candidates: list[dict], split: dict) -> list[PortfolioDef]:
    core = portfolio_cfg["core"]
    core_tickers = _ALL_SPECS[core["fn"]].tickers(core["params"])
    members = portfolio_cfg["sleeve"]["strategies"]
    chosen_universe = sorted({t for m in members for t in _ALL_SPECS[m["fn"]].tickers(m["params"])})

    def chosen(data, keep):
        sleeves = [_member_weights(m["fn"], _restrict(m["params"], keep), data) for m in members]
        return combine_portfolio(
            _member_weights(core["fn"], core["params"], data), sleeves, split
        ).combined

    out = [PortfolioDef("chosen", chosen, core_tickers, chosen_universe, candidate=bool(members))]
    for cand in candidates:

        def build(data, keep, cand=cand):
            sleeve = candidate_weights(cand["family"], _restrict(cand["params"], keep), data)
            return combine_portfolio(
                _member_weights(core["fn"], core["params"], data), [sleeve], split
            ).combined

        universe = list(_ALL_SPECS[cand["family"]].tickers(cand["params"]))
        name = f"core+{cand['family']}#{cand['test_id']}"
        out.append(PortfolioDef(name, build, core_tickers, universe, candidate=True))
    return out


def _print(cells, max_drawdown: float) -> None:
    print(f"{'portfolio':<32} {'scenario':<20} {'mode':<12} {'loss':>7}  {'':6} label")
    for c in cells:
        loss = "  n/a" if c.loss is None else f"{c.loss:>6.1%}"
        flag = "BREACH" if c.breach else ("UNAVL" if c.unavailable else "")
        print(f"{c.portfolio:<32} {c.scenario:<20} {c.mode:<12} {loss:>7}  {flag:<6} {c.label}")
    print(f"Cap: max drawdown {max_drawdown:.0%} (config/profile.yaml)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(ROOT / "reports" / "stress.json"))
    args = ap.parse_args(argv)

    criteria, _ = load_criteria(ROOT / "config" / "criteria.yaml")
    holdout_start, _ = period_bounds(criteria, "holdout")
    paths = stress_config_paths(ROOT)
    cfg, _ = load_stress_config(paths["stress.yaml"], holdout_start)
    profile = load_profile(paths["profile.yaml"])
    portfolio_cfg = load_portfolio_config(paths["portfolio.yaml"])
    paper_cfg, _ = load_paper_config(paths["paper.yaml"])
    with Ledger(ROOT / "research" / "ledger.sqlite") as ledger:  # as scripts/paper_track.py
        candidates = [load_candidate(ledger, e) for e in paper_cfg["candidates"]]

    portfolios = _portfolios(portfolio_cfg, candidates, profile["capital_split"])
    tickers = sorted(
        {EQUITY_PROXY}.union(*(set(p.core_tickers) | set(p.sleeve_universe) for p in portfolios))
    )
    data = load_ohlcv(tickers)

    cells = run_stress(cfg, portfolios, data, profile["max_drawdown"], criteria)
    report = {
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "max_report_age_days": cfg.max_report_age_days,
        "max_drawdown": profile["max_drawdown"],
        "hashes": file_hashes(paths),
        "cells": [asdict(c) for c in cells],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str))
    _print(cells, profile["max_drawdown"])
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Before running, confirm against the real code: (a) `Ledger(...)`'s constructor matches `scripts/paper_track.py`; (b) `load_profile`'s path parameter name (`qrl.profile`); (c) `profile["max_drawdown"]` and `profile["capital_split"]` are the right keys. Adjust only the wiring, not `qrl.stress`.

- [ ] **Step 2: Add the pixi task**

In `pixi.toml` `[tasks]`, after `daily-check = ...`, add:
```toml
stress = "python scripts/stress.py"
```

- [ ] **Step 3: Real run**

Run: `pixi run -e dev stress`
Expected: a table of 4 portfolios × (4 frozen + 3 replay + 4 hypothetical) = 44 rows, `Wrote .../reports/stress.json`, exit 0. `unavailable` rows are acceptable only with a reason; record any in the PR description. This first report locks `config/stress.yaml` (amendments only from here).

- [ ] **Step 4: Commit**

```bash
git add scripts/stress.py pixi.toml
git commit -m "Stress: CLI and pixi task"
```

---

### Task 9: Daily-check warnings channel

**Files:** Modify `scripts/daily_check.py`; Modify `tests/test_stress.py`

- [ ] **Step 1: Write the failing tests**

At the top of `tests/test_stress.py`: add `import sys` to the stdlib import block; directly after the line `ROOT = Path(__file__).resolve().parents[1]` add:
```python
sys.path.insert(0, str(ROOT / "scripts"))

import daily_check  # noqa: E402
```
Then append:
```python
def test_daily_check_stress_warnings_missing_report(tmp_path):
    msgs = daily_check._stress_warnings(tmp_path / "nope.json")
    assert len(msgs) == 1 and "missing" in msgs[0]


def test_daily_check_stress_warnings_reports_breach(tmp_path):
    import json

    report = {
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "max_report_age_days": 30,
        "max_drawdown": 0.35,
        "hashes": file_hashes(stress_config_paths(ROOT)),
        "cells": [
            {
                "portfolio": "chosen",
                "scenario": "tech_crash",
                "mode": "hypothetical",
                "loss": 0.48,
                "breach": True,
            }
        ],
    }
    path = tmp_path / "stress.json"
    path.write_text(json.dumps(report))
    (msg,) = daily_check._stress_warnings(path)
    assert msg.startswith("BREACH")


def test_daily_check_exit_status_ignores_stress_warnings():
    src = (ROOT / "scripts" / "daily_check.py").read_text()
    assert "return 0 if report.ok else 1" in src
    assert '"stress_warnings"' in src
```

- [ ] **Step 2: Run to verify failure**

Run: `pixi run -e dev pytest tests/test_stress.py -v`
Expected: `AttributeError: module 'daily_check' has no attribute '_stress_warnings'`.

- [ ] **Step 3: Implement in `scripts/daily_check.py`**

Add to the imports:
```python
from qrl.stress import file_hashes, stress_config_paths, stress_warnings  # noqa: E402
```

Add after `_print_report`:
```python
def _stress_warnings(path: Path = ROOT / "reports" / "stress.json") -> list[str]:
    """Warnings from the last `pixi run stress` report. A separate channel:
    never part of HealthReport.checks, never affects the exit status."""
    report = json.loads(path.read_text()) if path.exists() else None
    return stress_warnings(
        report, file_hashes(stress_config_paths(ROOT)), pd.Timestamp.now(tz="UTC")
    )
```

In `main`, replace:
```python
    out.write_text(json.dumps(report.to_dict(), indent=2, default=str))

    _print_report(report)
```
with:
```python
    warnings_ = _stress_warnings()
    out.write_text(
        json.dumps({**report.to_dict(), "stress_warnings": warnings_}, indent=2, default=str)
    )

    _print_report(report)
    for w in warnings_:
        print(f"  [WARNING] {w}")
```
Leave `return 0 if report.ok else 1` unchanged. Keep the PRIVATE ARTIFACT comment above the write.

- [ ] **Step 4: Run to verify pass**

Run: `pixi run -e dev pytest tests/test_stress.py -v`
Expected: 33 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/daily_check.py tests/test_stress.py
git commit -m "Daily check: stress warnings channel (exit status unchanged)"
```

---

### Task 10: Full verification and PR

- [ ] **Step 1: Full suite** — `pixi run -e dev test` → expected `512 passed` (479 + 33), no failures.
- [ ] **Step 2: Quality gate** — `pixi run -e dev format-check`, `pixi run -e dev lint`, `pixi run -e dev type-check` → all pass (fix findings in new files only; never weaken existing config).
- [ ] **Step 3: Real daily check** — `pixi run -e dev daily-check` → health table, then any `[WARNING]` lines from the stress report; exit status the same as before this change.
- [ ] **Step 4: Locked files untouched** — `git diff development --stat` must list only: `config/stress.yaml`, `src/qrl/stress.py`, `tests/test_stress.py`, `scripts/stress.py`, `scripts/daily_check.py`, `pixi.toml`, `docs/superpowers/**`.
- [ ] **Step 5: Push and open PR into `development`** (never push to development/main directly). PR body: summary, the stress table from Task 8 Step 3 (losses only), any `unavailable` rows with reasons, and the line `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. Do not merge; the owner merges.
