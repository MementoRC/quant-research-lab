"""The library half of the milestone 2.4 search loop (milestone 2.4).

Two pieces live here, both pure and deterministic given a fixed seed:

- `evaluate_candidate`: backtest one (family, params) candidate on a named
  period (`"research"` by default) and grade it against
  `config/criteria.yaml`. `"holdout"` is refused outright with a `ValueError`
  raised before any backtest runs -- this is the one shared evaluation path
  the milestone 2.4 search loop and milestone 2.5's `qrl.validation` both
  call (for the research and validation periods respectively), so it must
  never become a back door into the sealed holdout. Otherwise never raises:
  any other exception is caught and reported as a failed test, because one
  bad parameter combination must not stop an unattended overnight batch.
- `propose_batch`: given the run's ledger history so far and each family's
  parameter space, deterministically propose the next batch of candidates
  (see its docstring for the exact rules).

`SearchData` loads OHLCV once per batch and hands out ticker-column slices,
so a batch of a few hundred candidates does not re-fetch or re-generate
prices per candidate.

Nothing here ever unseals the holdout period (see `qrl.periods.slice_period`);
only the research period is ever sliced.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import zip_longest

import numpy as np
import pandas as pd

from .combined import baseline_label, combined_evaluation
from .criteria import evaluate as evaluate_criteria
from .data import load_ohlcv, synthetic_ohlcv
from .engine import run_backtest
from .factor_data import FactorData, default_provider
from .ledger import candidate_key
from .metrics import compute_metrics
from .periods import slice_period
from .strategies import REGISTRY, SLEEVE_REGISTRY, StrategySpec, iter_grid
from .strategies.buy_and_hold import buy_and_hold
from .tradability import exit_before_delisting

SLEEVE_FAMILIES = frozenset(SLEEVE_REGISTRY)
_ALL_SPECS: dict[str, StrategySpec] = {**REGISTRY, **SLEEVE_REGISTRY}

_RULE_CODES = {
    "Enough trades": "min_trades",
    "Sharpe ratio": "min_sharpe",
    "Max drawdown": "max_drawdown",
}


def _spec_for(family: str) -> StrategySpec:
    try:
        return _ALL_SPECS[family]
    except KeyError:
        raise KeyError(f"Unknown strategy family: {family!r}") from None


def _failure_code(rule: str) -> str:
    if rule in _RULE_CODES:
        return _RULE_CODES[rule]
    if rule.startswith("Beats "):
        return "beat_benchmark"
    return rule


@dataclass(frozen=True)
class SearchData:
    """Every ticker's OHLCV a search batch might need, loaded exactly once.

    Downloading (or synthesizing) prices per candidate would make a batch of
    a few hundred candidates unusable; a batch loads this once up front and
    every candidate slices columns out of it.
    """

    open_: pd.DataFrame
    high: pd.DataFrame
    low: pd.DataFrame
    close: pd.DataFrame
    volume: pd.DataFrame
    # Factor-field source for a factor run (built over the run's own hashed
    # membership, `qrl.factor_run`); None falls back to `default_provider()`.
    provider: FactorData | None = None

    @classmethod
    def load(
        cls,
        tickers: list[str],
        *,
        synthetic: bool = False,
        start: str = "1999-01-01",
        refresh: bool = False,
        provider: FactorData | None = None,
    ) -> SearchData:
        unique = sorted(set(tickers))
        frames = (
            synthetic_ohlcv(unique, start=start)
            if synthetic
            else load_ohlcv(unique, start=start, refresh=refresh)
        )
        return cls(
            open_=frames["open"],
            high=frames["high"],
            low=frames["low"],
            close=frames["close"],
            volume=frames["volume"],
            provider=provider,
        )

    def fields(self, names: tuple[str, ...], tickers: list[str]) -> list[pd.DataFrame]:
        mapping = {
            "open": self.open_,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }
        # Names outside the OHLCV set are factor fields (pit_member, fund_*), built
        # on the price index by qrl.factor_data; price-only families never reach it.
        return [
            mapping[name][tickers]
            if name in mapping
            else self._factor_provider().panel(
                name, self.close.index, tickers, self.volume[tickers]
            )
            for name in names
        ]

    def _factor_provider(self) -> FactorData:
        return self.provider if self.provider is not None else default_provider()


def compute_benchmark_metrics(data: SearchData, criteria: dict) -> dict:
    """Research-period metrics for criteria's `beat_benchmark` ticker.

    Computed once per run/batch and passed into every `evaluate_candidate`
    call as `benchmark_metrics`, rather than re-backtesting the benchmark
    once per candidate.
    """
    ticker = criteria["pass"]["beat_benchmark"]
    close = data.close[[ticker]]
    weights = slice_period(buy_and_hold(close, ticker=ticker), criteria, "research")
    result = run_backtest(
        data.open_[[ticker]],
        close,
        weights,
        cost_bps=criteria["costs"]["bps_per_unit_turnover"],
    )
    return compute_metrics(result.returns, result.turnover, result.executed)


def evaluate_candidate(
    family: str,
    params: dict,
    data: SearchData,
    criteria: dict,
    benchmark_metrics: dict | None = None,
    period: str = "research",
    *,
    combined_cfg: dict | None = None,
) -> dict:
    """Backtest and grade one (family, params) candidate on `period`
    (`"research"` by default; `qrl.validation.validate_survivors` also calls
    this with `period="validation"` for the one-time validation-period
    check and for neighbour evaluations). This is the ONE place that builds
    weights, applies delisting exits, slices a period, runs the backtest,
    and computes metrics -- kept singular on purpose, so a research-period
    result and a validation-period result are always graded by the exact
    same cost setting and treatment, never two copies that could drift
    apart (see milestone 2.5).

    `period="holdout"` is refused outright: raises `ValueError` before any
    backtest runs, rather than letting `qrl.periods.slice_period`'s
    `HoldoutSealedError` be caught below and silently turned into an
    ordinary failed-candidate result. The holdout stays sealed through
    milestones 2.4 and 2.5; unsealing it is milestone 2.6's job alone, and
    never through this shared path.

    Returns a dict with `metrics`, `passed`, `failure_reasons` (a
    comma-joined set of short codes, or None if it passed), `checks` (the
    raw per-rule results from `qrl.criteria.evaluate`), and `returns` (the
    raw daily return series, for `qrl.validation.correlation_filter`).

    Otherwise never raises: any exception raised while building weights,
    applying delisting exits, or running the backtest (bad params, a
    strategy with no valid signal in this window, a missing ticker, ...) is
    caught and returned as a failed candidate with the error text as its
    failure reason. One bad combination must never kill an unattended
    overnight run.

    `combined_cfg` (from `qrl.combined.load_combined_config`) switches to the
    combined pass rule for runs seeded with it: the standalone metrics are
    still computed and stored as above, `metrics` gains `combined_*`,
    `core_*` and `improvement_sharpe` keys, the result gains `improvement`
    (the combined-minus-core daily series), and `passed`/`failure_reasons`/
    `checks` come from `qrl.combined.combined_evaluation` only -- the
    standalone criteria are not graded. When None (the default) behaviour is
    exactly as before.
    """
    if period == "holdout":
        raise ValueError(
            "evaluate_candidate refuses period='holdout' -- the holdout stays "
            "sealed through milestones 2.4 and 2.5 (see qrl.periods.slice_period)."
        )
    try:
        spec = _spec_for(family)
        tickers = spec.tickers(params)
        weight_kwargs = {k: v for k, v in params.items() if k != "tickers"}
        frames = data.fields(spec.fields, tickers)
        weights = spec.weights(*frames, **weight_kwargs)
        weights = exit_before_delisting(weights, data.open_[tickers], data.close[tickers])
        sliced = slice_period(weights, criteria, period)

        result = run_backtest(
            data.open_[tickers],
            data.close[tickers],
            sliced,
            cost_bps=criteria["costs"]["bps_per_unit_turnover"],
        )
        metrics = compute_metrics(result.returns, result.turnover, result.executed)
        if combined_cfg is not None:
            return _combined_outcome(
                metrics, result.returns, weights, data, criteria, combined_cfg, period
            )
        checks = evaluate_criteria(metrics, benchmark_metrics, criteria)
        passed = all(c["passed"] for c in checks)
        failure_reasons = (
            None
            if passed
            else ",".join(_failure_code(c["rule"]) for c in checks if not c["passed"])
        )
        return {
            "metrics": metrics,
            "passed": passed,
            "failure_reasons": failure_reasons,
            "checks": checks,
            "returns": result.returns,
        }
    except Exception as exc:  # a bad candidate must never kill an overnight batch
        failed: dict = {
            "metrics": {"error": str(exc)},
            "passed": False,
            "failure_reasons": f"error: {exc}",
            "checks": [],
            "returns": pd.Series(dtype=float),
        }
        if combined_cfg is not None:
            failed["improvement"] = pd.Series(dtype=float)
        return failed


def _combined_outcome(
    metrics: dict,
    returns: pd.Series,
    weights: pd.DataFrame,
    data: SearchData,
    criteria: dict,
    combined_cfg: dict,
    period: str,
) -> dict:
    """`evaluate_candidate`'s result under the combined pass rule: the
    standalone `metrics` plus prefixed combined/core metrics and
    `improvement_sharpe`; pass/fail from the combined checks only. Baseline
    metrics are prefixed `core_` (combined) or `null_` (combined_null)."""
    label = baseline_label(combined_cfg)
    ce = combined_evaluation(
        weights,
        data.open_,
        data.close,
        combined_cfg["core"],
        combined_cfg["capital_split"],
        criteria,
        combined_cfg,
        period=period,
        sleeve_trades=int(metrics.get("trades", 0)),
    )
    merged = {
        **metrics,
        **{f"combined_{k}": v for k, v in ce["combined_metrics"].items()},
        **{f"{label}_{k}": v for k, v in ce[f"{label}_metrics"].items()},
        "improvement_sharpe": ce["improvement_sharpe"],
    }
    return {
        "metrics": merged,
        "passed": ce["passed"],
        "failure_reasons": ce["failure_reasons"],
        "checks": ce["checks"],
        "returns": returns,
        "improvement": ce["improvement"],
    }


def pruned_regions(
    history: list[dict], spaces: dict[str, dict[str, list]], min_attempts: int = 5
) -> set[tuple[str, str, object]]:
    """(family, parameter, value) triples that have been tried at least
    `min_attempts` times and have never once passed -- a region worth
    skipping rather than re-testing.
    """
    counts: dict[tuple[str, str, object], list[int]] = {}
    for row in history:
        space = spaces.get(row["family"])
        if not space:
            continue
        for key in space:
            if key not in row["params"]:
                continue
            bucket = counts.setdefault((row["family"], key, row["params"][key]), [0, 0])
            bucket[0] += 1
            if not row["passed"]:
                bucket[1] += 1
    return {
        k
        for k, (attempts, fails) in counts.items()
        if attempts >= min_attempts and fails == attempts
    }


def _has_pruned_value(
    family: str,
    params: dict,
    pruned: set[tuple[str, str, object]],
    space: dict[str, list],
) -> bool:
    # Scoped to the family's declared space keys on purpose: `pruned_regions`
    # only ever stores triples for keys in `space` (see line 230 above), so a
    # non-space param (e.g. the sleeve "tickers" list attached after this
    # check runs, at line 405-406 below) can never match a pruned entry --
    # and some non-space values (like that list) are not hashable anyway.
    # Iterating all of `params` here would be both meaningless and crash-prone.
    return any((family, key, params[key]) in pruned for key in space if key in params)


def _random_params(space: dict[str, list], rng: np.random.Generator) -> dict:
    return {key: values[int(rng.integers(len(values)))] for key, values in space.items()}


def _mutate(row: dict, space: dict[str, list], rng: np.random.Generator) -> dict:
    """Move one parameter of a passing candidate one step up or down in its
    own space, bouncing back if that step would fall off an edge.

    Returns only the family's space keys (matching `_random_params` and
    `_recombine`) -- a parent row's non-space keys (e.g. the sleeve
    "tickers" list) are never carried forward, since `propose_batch`
    re-attaches "tickers" for sleeve families after this call anyway
    (line 405-406 below), so carrying a stale copy forward would only ever
    be overwritten.
    """
    params = {k: v for k, v in row["params"].items() if k in space}
    keys = [k for k in space if k in params and params[k] in space[k]]
    if not keys:
        return params
    key = keys[int(rng.integers(len(keys)))]
    values = space[key]
    idx = values.index(params[key])
    step = 1 if rng.random() < 0.5 else -1
    new_idx = idx + step
    if not (0 <= new_idx < len(values)):
        new_idx = idx - step
    new_idx = max(0, min(len(values) - 1, new_idx))
    params[key] = values[new_idx]
    return params


def _recombine(row_a: dict, row_b: dict, space: dict[str, list], rng: np.random.Generator) -> dict:
    """Take each parameter independently from either parent, at random."""
    params = {}
    for key in space:
        a_has, b_has = key in row_a["params"], key in row_b["params"]
        if a_has and b_has:
            params[key] = row_a["params"][key] if rng.random() < 0.5 else row_b["params"][key]
        elif a_has:
            params[key] = row_a["params"][key]
        elif b_has:
            params[key] = row_b["params"][key]
    return params


def _group_by_family(rows: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(row["family"], []).append(row)
    return groups


def _propose_one(
    rng: np.random.Generator,
    families: list[str],
    spaces: dict[str, dict[str, list]],
    passing_by_family: dict[str, list[dict]],
    partial_by_family: dict[str, list[dict]],
    seed_phase: bool,
    pruned: set[tuple[str, str, object]],
) -> tuple[str, dict] | None:
    if not seed_phase and passing_by_family and rng.random() < 0.4:
        fam = list(passing_by_family)[int(rng.integers(len(passing_by_family)))]
        rows = passing_by_family[fam]
        params = _mutate(rows[int(rng.integers(len(rows)))], spaces[fam], rng)
        return None if _has_pruned_value(fam, params, pruned, spaces[fam]) else (fam, params)

    eligible = {f: rows for f, rows in partial_by_family.items() if len(rows) >= 2}
    if not seed_phase and eligible and rng.random() < 0.5:
        fam = list(eligible)[int(rng.integers(len(eligible)))]
        rows = eligible[fam]
        i, j = rng.choice(len(rows), size=2, replace=False)
        params = _recombine(rows[int(i)], rows[int(j)], spaces[fam], rng)
        return None if _has_pruned_value(fam, params, pruned, spaces[fam]) else (fam, params)

    fam = families[int(rng.integers(len(families)))]
    params = _random_params(spaces[fam], rng)
    return None if _has_pruned_value(fam, params, pruned, spaces[fam]) else (fam, params)


def _grid_queue(
    spaces: dict[str, dict[str, list]],
    grid_families: frozenset[str],
    pruned: set[tuple[str, str, object]],
    rng: np.random.Generator,
) -> list[tuple[str, dict]]:
    """Every point of each `grid_families` family's full grid (unpruned),
    shuffled within a family and interleaved round-robin across families."""
    per_family: list[list[tuple[str, dict]]] = []
    for family in spaces:
        if family not in grid_families:
            continue
        points = iter_grid(spaces[family])
        order = rng.permutation(len(points))
        per_family.append(
            [
                (family, points[int(i)])
                for i in order
                if not _has_pruned_value(family, points[int(i)], pruned, spaces[family])
            ]
        )
    return [item for row in zip_longest(*per_family) for item in row if item is not None]


def propose_batch(
    history: list[dict],
    spaces: dict[str, dict[str, list]],
    n: int,
    seed: int,
    *,
    universe: str,
    sleeve_tickers: list[str] | None = None,
    prune_min_attempts: int = 5,
    max_attempts_factor: int = 20,
    grid_families: frozenset[str] = frozenset(),
) -> list[tuple[str, dict]]:
    """Deterministically propose up to `n` new (family, params) candidates.

    `history` is the run's ledger tests so far, each a dict with at least
    `family`, `params`, `passed`, `failure_reasons`, and `candidate_key`
    (see `Ledger.list_tests`). `spaces` maps family name to its parameter
    space (`StrategySpec.space`).

    Protocol, applied in this order:

    1. SKIP -- a candidate whose `qrl.ledger.candidate_key` already appears
       in `history`, or was already proposed earlier in this same batch, is
       never proposed again.
    2. PRUNE -- any (family, parameter, value) triple attempted at least
       `prune_min_attempts` times that has *never once* passed is excluded
       from every later proposal for that family (random, mutated, and
       recombined alike).
    3. SEED (random/grid) -- while `history` has fewer than `n` prior tests
       for the run ("thin"), every proposal is a uniform-random point drawn
       independently per parameter from `spaces` (pruning-aware). This
       bootstraps the ledger before there is anything to learn from.
    4. Once history is no longer thin, each proposal is one of:
       - MUTATE (40%): pick a random *passing* candidate and move one of its
         parameters one step up or down in its own space (bouncing back at
         an edge rather than going out of range).
       - RECOMBINE (30%): pick two *partial winners* (failed on exactly one
         criterion) of the same family and take each parameter independently
         from either parent.
       - random sampling otherwise, or whenever no passing/partial-winner
         candidates exist yet for any family.

    Sleeve families (`family in SLEEVE_FAMILIES`) always get the current
    `sleeve_tickers` universe attached as `params["tickers"]`, overriding
    whatever a mutated/recombined parent's `tickers` happened to be, so a
    run's sleeve universe stays fixed across a batch.

    `grid_families` (default empty: nothing below changes, and the random
    stream is untouched) names families whose whole grid is small enough to
    enumerate -- the Phase 4 factor families, 2 x 2 x 2 = 8 points each. Their
    untested, unpruned grid points are proposed first (shuffled, interleaved
    across families), before the rules above fill whatever is left.

    Stops early (returning fewer than `n` candidates) once
    `n * max_attempts_factor` proposal attempts have been spent without
    reaching `n` unique, unpruned candidates -- for example once a small
    grid is nearly exhausted.
    """
    rng = np.random.default_rng(seed)
    families = list(spaces.keys())
    if not families or n <= 0:
        return []

    pruned = pruned_regions(history, spaces, prune_min_attempts)
    tested_keys = {row["candidate_key"] for row in history}
    seed_phase = len(history) < n
    passing_by_family = _group_by_family(
        [row for row in history if row["passed"] and row["family"] in spaces]
    )
    partial_by_family = _group_by_family(
        [
            row
            for row in history
            if not row["passed"]
            and row["family"] in spaces
            and row["failure_reasons"]
            and "," not in row["failure_reasons"]
        ]
    )

    proposed: list[tuple[str, dict]] = []
    seen_this_batch: set[str] = set()
    max_attempts = n * max_attempts_factor
    attempts = 0
    queue = _grid_queue(spaces, grid_families, pruned, rng) if grid_families else []
    while len(proposed) < n and attempts < max_attempts:
        attempts += 1
        proposal = (
            queue.pop(0)
            if queue
            else _propose_one(
                rng, families, spaces, passing_by_family, partial_by_family, seed_phase, pruned
            )
        )
        if proposal is None:
            continue
        family, params = proposal
        if family in SLEEVE_FAMILIES:
            params = {**params, "tickers": list(sleeve_tickers or [])}
        key = candidate_key(family, params, universe, "research")
        if key in tested_keys or key in seen_this_batch:
            continue
        seen_this_batch.add(key)
        proposed.append((family, params))
    return proposed
