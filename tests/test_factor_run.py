"""Tests for the factor run config (Phase 4, milestone 4): the effective
criteria, hash binding, the point-in-time null sleeve, the family guard, the
factor grid and a synthetic seed -> batch -> summary -> validate run.
Offline, synthetic data, tmp ledgers only; nothing here reads real prices or
fundamentals or opens the tracked ledger."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from qrl import factor_run as fr
from qrl import pit_universe as pu
from qrl.combined import null_baseline_sleeve
from qrl.controls import null_sleeve_weights
from qrl.criteria import load_criteria
from qrl.data import synthetic_prices
from qrl.ledger import Ledger
from qrl.periods import slice_period
from qrl.search import propose_batch
from qrl.strategies import FACTOR_FAMILIES, SLEEVE_REGISTRY, iter_grid

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
sys.path.insert(0, str(ROOT / "scripts"))

from search import SEARCHABLE_SPACES  # noqa: E402
from search import main as search_main  # noqa: E402
from test_combined import _write_tiny_universe  # noqa: E402
from test_combined_null import LOOSE_NULL, _cfg_args, _copy_configs  # noqa: E402
from validate import main as validate_main  # noqa: E402

FACTORS = ["value_ey", "profitability", "low_investment"]
TICKS = ["F1", "F2", "F3", "F4", "F5", "F6"]


@pytest.fixture(scope="module")
def criteria() -> dict:
    return load_criteria(CONFIG / "criteria.yaml")[0]


def _membership(tickers: list[str] = TICKS, per_month: int = 4) -> pd.DataFrame:
    """Rotating membership: each month-end `per_month` of the tickers are members."""
    month_ends = pd.date_range("2008-12-31", "2026-12-31", freq=pd.offsets.BMonthEnd())
    rows = []
    for i, me in enumerate(month_ends):
        chosen = [t for j, t in enumerate(tickers) if (i + j) % len(tickers) < per_month]
        rows += [
            {"month_end": me, "ticker": t, "market_cap": 1_000_000 + r, "rank": r + 1, "source": ""}
            for r, t in enumerate(chosen)
        ]
    return pd.DataFrame(rows)


def _write_setup(tmp_path: Path, membership: pd.DataFrame | None = None) -> Path:
    """A factor.yaml (plus universe yaml and membership CSV) under tmp_path."""
    membership = _membership() if membership is None else membership
    csv = tmp_path / "universes" / "synthetic_pit.csv"
    sha = pu.write_membership(membership, csv)
    uni = tmp_path / "config" / "universe_pit.yaml"
    uni.parent.mkdir(parents=True, exist_ok=True)
    pu.write_universe_meta(
        {
            "name": "synthetic_pit",
            "survivorship_biased": True,
            "membership_file": str(csv),
            "membership_sha256": sha,
        },
        uni,
    )
    cfg = {
        "version": 1,
        "research_start": "2009-01-01",
        "universe": str(uni),
        "universe_membership_sha256": sha,
        "families": FACTORS,
        "null_baseline": "pit_equal_weight",
    }
    path = tmp_path / "config" / "factor.yaml"
    path.write_text(yaml.safe_dump(cfg))
    return path


class StubProvider:
    """Synthetic factor panels over a real membership (no SEC data)."""

    def __init__(self, membership: pd.DataFrame) -> None:
        self.membership = membership

    def panel(self, name, dates, tickers, volume=None) -> pd.DataFrame:
        idx, cols = pd.DatetimeIndex(dates), list(tickers)
        if name == "pit_member":
            return pu.membership_mask(self.membership, idx, cols)
        rng = np.random.default_rng(sum(map(ord, name)))
        base = 1.0 + rng.random(len(cols))
        drift = 1.0 + 0.2 * np.sin(np.arange(len(idx)) / 120.0)
        values = np.outer(drift, base)
        if name == "fund_assets_lag1y":
            values = values * 0.9
        return pd.DataFrame(values, index=idx, columns=cols)


@pytest.fixture
def stub_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fr, "FactorData", StubProvider)


# ---------------------------------------------------------------------------
# Config, effective criteria, hash binding.
# ---------------------------------------------------------------------------


def test_checked_in_factor_yaml_loads_and_matches_the_universe():
    run = fr.load_factor_run(CONFIG / "factor.yaml")
    assert run.research_start == "2009-01-01"
    assert run.families == FACTORS
    assert run.universe["name"] == "us_large_cap_pit"
    meta, _ = pu.load_pit_universe()
    assert run.membership_sha256 == meta["membership_sha256"]
    assert len(run.config_sha256) == 64
    assert len(run.membership_sha256) == 64


def _flatten(d: dict, prefix: str = "") -> dict:
    out: dict = {}
    for key, value in d.items():
        if isinstance(value, dict):
            out.update(_flatten(value, f"{prefix}{key}."))
        else:
            out[f"{prefix}{key}"] = value
    return out


def test_effective_criteria_differ_only_in_research_start(criteria):
    before = copy.deepcopy(criteria)
    effective = fr.effective_criteria(criteria, "2009-01-01")
    assert criteria == before  # the input is not mutated
    base, eff = _flatten(criteria), _flatten(effective)
    assert base.keys() == eff.keys()
    assert {k for k in base if base[k] != eff[k]} == {"periods.research.start"}
    assert eff["periods.research.start"] == "2009-01-01"
    assert base["periods.research.start"] == "2005-01-01"
    for period in ("validation", "holdout"):
        assert effective["periods"][period] == criteria["periods"][period]


def test_effective_criteria_slices_research_from_the_new_start(criteria):
    effective = fr.effective_criteria(criteria, "2009-01-01")
    idx = pd.bdate_range("2005-01-03", "2022-12-30")
    frame = pd.DataFrame(1.0, index=idx, columns=["A"])
    research = slice_period(frame, effective, "research")
    assert research.index[0] == pd.Timestamp("2009-01-01")
    assert research.index[-1] == pd.Timestamp("2018-12-31")
    assert slice_period(frame, effective, "validation").equals(
        slice_period(frame, criteria, "validation")
    )
    with pytest.raises(Exception, match="sealed"):
        slice_period(frame, effective, "holdout")


def test_effective_criteria_guards(criteria):
    with pytest.raises(ValueError, match="before research end"):
        fr.effective_criteria(criteria, "2019-01-01")
    tampered = copy.deepcopy(criteria)
    tampered["costs"]["bps_per_unit_turnover"] = 1
    with pytest.raises(ValueError, match="beyond research start"):
        fr._require_only_start_differs(criteria, tampered)


def test_load_factor_run_rejects_bad_configs(tmp_path):
    path = _write_setup(tmp_path)
    for edit, match in (
        ({"null_baseline": "all_tickers"}, "null_baseline"),
        ({"families": ["value_ey", "trend_pullback"]}, "families"),
        ({"universe_membership_sha256": "0" * 64}, "does not"),
        ({"research_start": "not-a-date"}, ""),
    ):
        cfg = yaml.safe_load(path.read_text())
        bad = tmp_path / "bad.yaml"
        bad.write_text(yaml.safe_dump({**cfg, **edit}))
        with pytest.raises(ValueError, match=match):
            fr.load_factor_run(bad)


def _seed_factor(tmp_path: Path, paths: dict, factor: Path, extra: list[str] | None = None) -> int:
    ledger_path = tmp_path / "ledger.sqlite"
    argv = [
        "--ledger",
        str(ledger_path),
        "seed",
        "--lane",
        "A",
        "--synthetic",
        "--factor-config",
        str(factor),
        "--pass-rule",
        "combined_null",
        "--description",
        "run 6 test; prior runs 1-5 disclosed",
        *_cfg_args(paths, profile=False),
        *(extra or []),
    ]
    return search_main(argv)


def _batch_argv(tmp_path: Path, paths: dict, factor: Path, run_id: int, n: int) -> list[str]:
    return [
        "--ledger",
        str(tmp_path / "ledger.sqlite"),
        "batch",
        "--run",
        str(run_id),
        "--n",
        str(n),
        "--synthetic",
        "--factor-config",
        str(factor),
        "--seed",
        "3",
        *_cfg_args(paths),
    ]


def _validate_argv(tmp_path: Path, paths: dict, factor: Path, run_id: int) -> list[str]:
    return [
        "--run",
        str(run_id),
        "--ledger",
        str(tmp_path / "ledger.sqlite"),
        "--synthetic",
        "--factor-config",
        str(factor),
        *_cfg_args(paths),
    ]


def test_seed_stores_both_hashes_and_defaults_families(tmp_path):
    paths = _copy_configs(tmp_path, combined_null=LOOSE_NULL)
    factor = _write_setup(tmp_path)
    assert _seed_factor(tmp_path, paths, factor) == 0
    loaded = fr.load_factor_run(factor)
    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        run = ledger.list_runs()[-1]
    assert run["data_source"]["factor_config_sha256"] == loaded.config_sha256
    assert run["data_source"]["membership_sha256"] == loaded.membership_sha256
    assert run["data_source"]["universe"] == "synthetic_pit"
    assert run["pass_rule"] == "combined_null"
    assert json.loads(run["seed_description"])["families"] == FACTORS
    assert "prior runs 1-5 disclosed" in run["seed_description"]


def test_batch_and_validate_refuse_when_factor_yaml_changes(tmp_path):
    paths = _copy_configs(tmp_path, combined_null=LOOSE_NULL)
    factor = _write_setup(tmp_path)
    assert _seed_factor(tmp_path, paths, factor) == 0
    factor.write_text(factor.read_text() + "# edited after seeding\n")

    assert search_main(_batch_argv(tmp_path, paths, factor, 1, 3)) == 2
    assert validate_main(_validate_argv(tmp_path, paths, factor, 1)) == 2
    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        assert ledger.list_tests(1) == []


def test_batch_and_validate_refuse_when_membership_csv_changes(tmp_path):
    paths = _copy_configs(tmp_path, combined_null=LOOSE_NULL)
    factor = _write_setup(tmp_path)
    assert _seed_factor(tmp_path, paths, factor) == 0
    csv = tmp_path / "universes" / "synthetic_pit.csv"
    csv.write_text(csv.read_text() + "2026-12-31,F1,1,1,\n")

    assert search_main(_batch_argv(tmp_path, paths, factor, 1, 3)) == 2
    assert validate_main(_validate_argv(tmp_path, paths, factor, 1)) == 2
    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        assert ledger.list_tests(1) == []


def test_check_factor_run_names_each_changed_hash(tmp_path):
    factor = _write_setup(tmp_path)
    current = fr.load_factor_run(factor)
    ok = {
        "run_id": 6,
        "data_source": {
            "factor_config_sha256": current.config_sha256,
            "membership_sha256": current.membership_sha256,
        },
    }
    assert fr.check_factor_run(ok, factor) is not None
    bad_cfg = {"run_id": 6, "data_source": {**ok["data_source"], "factor_config_sha256": "x"}}
    with pytest.raises(ValueError, match="factor.yaml hash has changed"):
        fr.check_factor_run(bad_cfg, factor)
    bad_csv = {"run_id": 6, "data_source": {**ok["data_source"], "membership_sha256": "x"}}
    with pytest.raises(ValueError, match="membership CSV hash has changed"):
        fr.check_factor_run(bad_csv, factor)
    price_run = {"run_id": 2, "data_source": {"synthetic": False}}
    assert fr.check_factor_run(price_run, None) is None
    with pytest.raises(ValueError, match="not seeded with --factor-config"):
        fr.check_factor_run(price_run, factor)


# ---------------------------------------------------------------------------
# The point-in-time null sleeve.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def prices() -> tuple[pd.DataFrame, pd.DataFrame]:
    return synthetic_prices(TICKS, start="2008-06-02", end="2012-12-31")


def _non_member_weights(weights: pd.DataFrame, mask: pd.DataFrame) -> float:
    """Largest absolute weight sitting on a non-member cell."""
    outside = weights.to_numpy()[~mask.to_numpy()]
    return float(np.abs(outside).max()) if outside.size else 0.0


def test_null_weights_without_a_mask_are_unchanged(prices):
    _, close = prices
    plain = null_sleeve_weights(close, TICKS, "equal_weight")
    expected = close.notna().astype(float).div(close.notna().sum(axis=1), axis=0)
    pd.testing.assert_frame_equal(plain, expected)
    all_true = pd.DataFrame(True, index=close.index, columns=TICKS)
    pd.testing.assert_frame_equal(
        null_sleeve_weights(close, TICKS, "equal_weight", member_mask=all_true), plain
    )


def test_pit_null_holds_only_members_at_equal_weight(prices):
    open_, close = prices
    membership = _membership()
    mask = pu.membership_mask(membership, close.index, TICKS)
    weights = null_sleeve_weights(close, TICKS, "equal_weight", member_mask=mask)

    assert _non_member_weights(weights, mask) == 0.0  # non-members never held
    counts = mask.sum(axis=1)
    live = counts > 0
    assert live.any()
    assert (counts[live] == 4).all()
    held = weights[live]
    np.testing.assert_allclose(held.sum(axis=1), 1.0)
    np.testing.assert_allclose(held.where(mask[live]).max(axis=1), 0.25)
    np.testing.assert_allclose(held.where(mask[live]).min(axis=1), 0.25)
    assert (weights[~live] == 0.0).all(axis=None)  # before the first month-end: cash
    # the membership rotates, so ever-member equal weight (1/6 each) is a different sleeve
    assert not np.allclose(weights.loc[live].to_numpy(), 1.0 / 6.0)

    sleeve = null_baseline_sleeve(open_, close, TICKS, membership)
    assert _non_member_weights(sleeve, mask) == 0.0
    assert (sleeve.sum(axis=1) <= 1.0 + 1e-9).all()


def test_pit_null_handles_trend_kind_and_missing_mask_cells(prices):
    _, close = prices
    mask = pu.membership_mask(_membership(), close.index, TICKS[:3])  # only 3 columns
    weights = null_sleeve_weights(close, TICKS, "equal_weight_trend", member_mask=mask)
    assert (weights[TICKS[3:]] == 0.0).all().all()  # columns absent from the mask: non-members


def test_combined_null_yaml_does_not_fix_the_baseline_universe():
    cfg = yaml.safe_load((CONFIG / "combined_null.yaml").read_text())
    assert cfg["baseline"] == "null_equal_weight"
    assert not {"null_tickers", "tickers", "universe"} & set(cfg)


# ---------------------------------------------------------------------------
# Families and the grid.
# ---------------------------------------------------------------------------


def test_check_family_mix():
    fr.check_family_mix(FACTORS, factor_run=True)
    fr.check_family_mix(["trend_pullback", "core_trend"], factor_run=False)
    with pytest.raises(ValueError, match="price families cannot be used in a factor run"):
        fr.check_family_mix(["value_ey", "trend_pullback"], factor_run=True)
    with pytest.raises(ValueError, match="only be used in a factor run"):
        fr.check_family_mix(["trend_pullback", "profitability"], factor_run=False)


def test_seed_and_batch_refuse_mixed_families(tmp_path):
    paths = _copy_configs(tmp_path, combined_null=LOOSE_NULL)
    factor = _write_setup(tmp_path)
    ledger_path = tmp_path / "ledger.sqlite"
    universe = _write_tiny_universe(tmp_path / "universe.yaml")

    # factor family in a price run
    price_seed = ["--ledger", str(ledger_path), "seed", "--lane", "B", "--synthetic"]
    price_seed += ["--universe", str(universe), "--families", "trend_pullback,value_ey"]
    assert search_main(price_seed) == 2
    # price family in a factor run
    assert _seed_factor(tmp_path, paths, factor, ["--families", "value_ey,trend_pullback"]) == 2
    # a factor run is judged under combined_null only
    standalone = ["--ledger", str(ledger_path), "seed", "--lane", "A", "--synthetic"]
    assert search_main([*standalone, "--factor-config", str(factor)]) == 2
    with Ledger(ledger_path) as ledger:
        assert ledger.list_runs() == []

    assert _seed_factor(tmp_path, paths, factor) == 0
    override = _batch_argv(tmp_path, paths, factor, 1, 2) + ["--families", "trend_pullback"]
    assert search_main(override) == 2
    with Ledger(ledger_path) as ledger:
        assert ledger.list_tests(1) == []


def test_factor_grid_is_eight_points_per_family():
    for family in FACTOR_FAMILIES:
        grid = iter_grid(SLEEVE_REGISTRY[family].space)
        assert len(grid) == 8
        assert {(g["n_hold"], g["rebalance"], g["trend_filter"]) for g in grid} == {
            (n, r, t) for n in (30, 50) for r in ("monthly", "quarterly") for t in (False, True)
        }


def test_propose_batch_enumerates_each_factor_grid_first():
    spaces = {f: SEARCHABLE_SPACES[f] for f in FACTORS}
    kwargs = {"universe": "u", "sleeve_tickers": TICKS, "grid_families": frozenset(FACTORS)}
    batch = propose_batch([], spaces, 24, seed=1, **kwargs)
    assert len(batch) == 24
    for family in FACTORS:
        mine = [p for f, p in batch if f == family]
        assert len(mine) == 8
        assert {(p["n_hold"], p["rebalance"], p["trend_filter"]) for p in mine} == {
            (g["n_hold"], g["rebalance"], g["trend_filter"])
            for g in iter_grid(SLEEVE_REGISTRY[family].space)
        }
        assert all(p["tickers"] == TICKS for p in mine)
    assert propose_batch([], spaces, 24, seed=1, **kwargs) == batch  # deterministic
    # a small first batch still spreads over the families
    assert {f for f, _ in propose_batch([], spaces, 3, seed=1, **kwargs)} == set(FACTORS)


def test_propose_batch_without_grid_families_is_unchanged():
    spaces = {"trend_pullback": SEARCHABLE_SPACES["trend_pullback"]}
    kwargs = {"universe": "u", "sleeve_tickers": TICKS}
    default = propose_batch([], spaces, 10, seed=5, **kwargs)
    assert default == propose_batch([], spaces, 10, seed=5, grid_families=frozenset(), **kwargs)
    assert len(default) == 10


# ---------------------------------------------------------------------------
# End to end on synthetic data.
# ---------------------------------------------------------------------------


def test_factor_run_end_to_end(tmp_path, monkeypatch, stub_provider, capsys):
    paths = _copy_configs(tmp_path, combined_null=LOOSE_NULL)
    factor = _write_setup(tmp_path)

    slices: list[tuple[str, bool, str]] = []
    real_slice = slice_period

    def spy(obj, crit, name, unseal_holdout=False):
        slices.append((name, unseal_holdout, crit["periods"]["research"]["start"]))
        return real_slice(obj, crit, name, unseal_holdout)

    masks: list[bool] = []
    import qrl.combined as combined_module

    real_null = combined_module.null_sleeve_weights

    def null_spy(close, tickers, kind, member_mask=None):
        masks.append(member_mask is not None)
        return real_null(close, tickers, kind, member_mask=member_mask)

    monkeypatch.setattr("qrl.search.slice_period", spy)
    monkeypatch.setattr("qrl.combined.slice_period", spy)
    monkeypatch.setattr("qrl.combined.null_sleeve_weights", null_spy)

    assert _seed_factor(tmp_path, paths, factor) == 0
    assert search_main(_batch_argv(tmp_path, paths, factor, 1, 6)) == 0

    ledger_path = tmp_path / "ledger.sqlite"
    with Ledger(ledger_path) as ledger:
        history = ledger.list_tests(1)
        trials = ledger.trial_sharpes(1, key="improvement_sharpe")
    assert len(history) == 6 == len(trials)
    assert {row["family"] for row in history} <= set(FACTORS)
    assert all(not (row["failure_reasons"] or "").startswith("error") for row in history)
    assert all(row["universe"] == "synthetic_pit" for row in history)

    capsys.readouterr()
    assert search_main(["--ledger", str(ledger_path), "summary", "--run", "1"]) == 0
    out = capsys.readouterr().out
    assert "Factor run: factor.yaml sha256" in out
    assert "Pass rule: combined_null" in out

    assert validate_main(_validate_argv(tmp_path, paths, factor, 1)) == 0
    assert "Validation funnel:" in capsys.readouterr().out

    with Ledger(ledger_path) as ledger:
        assert len(ledger.list_tests(1)) >= 6  # neighbours add trials, never remove
        assert ledger.list_holdout_events() == []
    names = {name for name, _, _ in slices}
    assert names <= {"research", "validation"}
    assert "research" in names
    assert not any(unseal for _, unseal, _ in slices)
    assert {start for _, _, start in slices} == {"2009-01-01"}
    assert masks  # the null sleeve was built...
    assert all(masks)  # ...and every time as the point-in-time one


# ---------------------------------------------------------------------------
# Non-factor runs behave as before.
# ---------------------------------------------------------------------------


def test_non_factor_run_is_unchanged(tmp_path, criteria):
    paths = _copy_configs(tmp_path, combined_null=LOOSE_NULL)
    ledger_path = tmp_path / "ledger.sqlite"
    universe = _write_tiny_universe(tmp_path / "universe.yaml")
    seed = ["--ledger", str(ledger_path), "seed", "--lane", "B", "--families", "trend_pullback"]
    seed += ["--synthetic", "--universe", str(universe), "--pass-rule", "combined_null"]
    assert search_main([*seed, *_cfg_args(paths, profile=False)]) == 0
    batch = ["--ledger", str(ledger_path), "batch", "--run", "1", "--n", "3", "--synthetic"]
    batch += ["--universe", str(universe), "--seed", "3", *_cfg_args(paths)]
    assert search_main(batch) == 0

    with Ledger(ledger_path) as ledger:
        run = ledger.list_runs()[-1]
        history = ledger.list_tests(1)
    assert set(run["data_source"]) == {"synthetic", "universe", "tickers_hash"}
    assert not fr.is_factor_run(run)
    assert len(history) == 3
    assert all(row["family"] == "trend_pullback" for row in history)
    assert all(row["universe"] == "tiny_test_universe" for row in history)
    # --factor-config on a price run is refused
    refused = [*batch, "--factor-config", str(CONFIG / "factor.yaml")]
    assert search_main(refused) == 2
    with Ledger(ledger_path) as ledger:
        assert len(ledger.list_tests(1)) == 3
    # criteria for a price run are the file's own
    assert criteria["periods"]["research"]["start"] == "2005-01-01"
