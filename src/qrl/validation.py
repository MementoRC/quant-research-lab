"""Milestone 2.5: validate research survivors honestly (PLAN.md section 2.5,
and section 3's "Thousands of candidates guarantee lucky winners" /
"The holdout was contaminated").

Four checks, applied to top research survivors in rank order:

- `neighbourhood_check`: a candidate's one-step parameter neighbours must
  mostly also pass the research criteria, or it is rejected as a lone spike.
  Neighbour evaluations are recorded in the ledger as ordinary research
  tests, so they count toward the deflated Sharpe ratio's trial total too.
- One evaluation on the validation period, recorded via
  `Ledger.record_validation` -- validation data is touched exactly once per
  candidate, enforced by that table's UNIQUE constraint on `test_id`
  (`Ledger.is_validated` lets `validate_survivors` skip a candidate before
  attempting a second validation, rather than relying on catching the
  resulting error).
- `deflated_sharpe_ratio`: Bailey & Lopez de Prado's multiple-testing
  correction, using the run's total test count and trial Sharpe
  distribution from the ledger.
- `correlation_filter`: drop a candidate whose validation-period daily
  returns correlate too highly with an already-accepted, stronger survivor.

`config/validation.yaml` holds these thresholds in a file separate from the
locked `config/criteria.yaml` -- see that file's header comment and PLAN.md
2.5 for why. `load_validation_config` hashes it exactly like
`qrl.criteria.load_criteria` hashes criteria.yaml.

No dependency on scipy (not in this project's dependencies): the normal CDF
uses `math.erf` and the inverse CDF (probit) uses Peter Acklam's rational
approximation, both implemented below.

Every backtest here -- neighbour evaluations and the single validation-period
check alike -- goes through `qrl.search.evaluate_candidate` (given
`period="research"` or `period="validation"`), the SAME function the search
loop uses for research-period candidates. Deliberately not duplicated: two
copies of "build weights, apply delisting exits, slice a period, backtest,
compute metrics" could silently drift (a different cost setting, a
different delisting treatment, ...), which would make validation-period
numbers stop being honestly comparable to research-period numbers -- the
entire point of this milestone. `evaluate_candidate` refuses
`period="holdout"` outright, so this shared path can never become a way to
reach the sealed holdout.
"""

from __future__ import annotations

import hashlib
import math
import statistics
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import yaml

from .metrics import TRADING_DAYS
from .search import evaluate_candidate

if TYPE_CHECKING:
    from collections.abc import Callable

    from .ledger import Ledger
    from .search import SearchData

EULER_MASCHERONI = 0.5772156649015329


def load_validation_config(path: str | Path) -> tuple[dict, str]:
    """Load `config/validation.yaml` and hash it exactly like
    `qrl.criteria.load_criteria` hashes `criteria.yaml` -- see that file's
    header comment for why it is a separate, separately-hashed file."""
    raw = Path(path).read_bytes()
    return yaml.safe_load(raw), hashlib.sha256(raw).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Normal CDF / inverse CDF, no scipy dependency.
# ---------------------------------------------------------------------------


def _normal_cdf(x: float) -> float:
    """Standard normal CDF via `math.erf` (exact, not an approximation)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


# Peter Acklam's rational approximation to the standard normal inverse CDF
# (probit), accurate to about 1.15e-9 relative error -- more than enough
# precision for a pass/fail threshold, without adding scipy as a dependency.
_ACKLAM_A = (
    -3.969683028665376e01,
    2.209460984245205e02,
    -2.759285104469687e02,
    1.383577518672690e02,
    -3.066479806614716e01,
    2.506628277459239e00,
)
_ACKLAM_B = (
    -5.447609879822406e01,
    1.615858368580409e02,
    -1.556989798598866e02,
    6.680131188771972e01,
    -1.328068155288572e01,
)
_ACKLAM_C = (
    -7.784894002430293e-03,
    -3.223964580411365e-01,
    -2.400758277161838e00,
    -2.549732539343734e00,
    4.374664141464968e00,
    2.938163982698783e00,
)
_ACKLAM_D = (
    7.784695709041462e-03,
    3.224671290700398e-01,
    2.445134137142996e00,
    3.754408661907416e00,
)
_ACKLAM_P_LOW = 0.02425


def _normal_ppf(p: float) -> float:
    """Standard normal inverse CDF (probit) via Acklam's approximation."""
    if not 0.0 < p < 1.0:
        raise ValueError(f"p must be in (0, 1), got {p!r}")
    c, d = _ACKLAM_C, _ACKLAM_D
    if p < _ACKLAM_P_LOW:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    if p <= 1 - _ACKLAM_P_LOW:
        q = p - 0.5
        r = q * q
        a, b = _ACKLAM_A, _ACKLAM_B
        numerator = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
        denominator = ((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1
        return numerator / denominator
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
        (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
    )


# ---------------------------------------------------------------------------
# Deflated Sharpe ratio (Bailey & Lopez de Prado, "The Deflated Sharpe
# Ratio", 2014).
# ---------------------------------------------------------------------------


def annualized_to_daily_sharpe(sharpe_annualized: float) -> float:
    """`qrl.metrics.compute_metrics` reports `sharpe` annualized as
    `mean / std * sqrt(TRADING_DAYS)` (see `qrl/metrics.py`). The deflated
    Sharpe formula below operates on the PER-PERIOD (daily) Sharpe and its
    moments, so this divides the `sqrt(TRADING_DAYS)` annualization factor
    back out. An annualized Sharpe of 1.0 is a daily Sharpe of roughly
    0.063, not 1.0 -- skipping this conversion would badly overstate the
    numerator of the deflated Sharpe ratio below.
    """
    return sharpe_annualized / math.sqrt(TRADING_DAYS)


def expected_max_sharpe(daily_trial_sharpes: list[float]) -> float:
    """SR0: the expected maximum Sharpe ratio across `len(daily_trial_sharpes)`
    independent trials whose true Sharpe is zero (Bailey & Lopez de Prado,
    eq. 8), using the standard deviation of the observed trial Sharpes as
    the per-trial Sharpe estimator's variance:

        SR0 = sd(trials) * ((1 - gamma) * Z(1 - 1/N) + gamma * Z(1 - 1/(N*e)))

    with `gamma` the Euler-Mascheroni constant. `daily_trial_sharpes` must
    already be in daily (not annualized) units -- see
    `annualized_to_daily_sharpe`. Fewer than 2 trials gives SR0 = 0 (nothing
    to deflate against yet).
    """
    n = len(daily_trial_sharpes)
    if n < 2:
        return 0.0
    sr_std = statistics.pstdev(daily_trial_sharpes)
    if sr_std == 0.0:
        return 0.0
    z_n = _normal_ppf(1 - 1 / n)
    z_ne = _normal_ppf(1 - 1 / (n * math.e))
    return sr_std * ((1 - EULER_MASCHERONI) * z_n + EULER_MASCHERONI * z_ne)


def deflated_sharpe_ratio(
    observed_sr: float,
    trial_srs: list[float],
    n_obs: int,
    skew: float,
    kurtosis: float,
) -> float:
    """Probability (0-1) that `observed_sr` reflects real skill rather than
    the best of `len(trial_srs)` random trials (Bailey & Lopez de Prado
    2014):

        DSR = Phi( (SR - SR0) * sqrt(n_obs - 1)
                   / sqrt(1 - skew*SR + ((kurtosis - 1) / 4) * SR^2) )

    Units, all PER-PERIOD (daily), not annualized:
    - `observed_sr` and every value in `trial_srs` are ANNUALIZED Sharpes,
      exactly as `qrl.metrics.compute_metrics` reports them; this function
      converts both to daily via `annualized_to_daily_sharpe` before using
      them, per Bailey & Lopez de Prado's derivation (their SR, moments, and
      `n_obs` all refer to one return-generating period, here a trading
      day).
    - `n_obs` is the number of daily return observations the *observed*
      Sharpe was measured over (e.g. the validation period's trading days).
    - `skew` and `kurtosis` are the skewness and (regular, not excess --
      normal = 3) kurtosis of that same daily return series.
    - `trial_srs` should have one entry per test in the run (see
      `Ledger.trial_sharpes`), so `len(trial_srs)` is the multiple-testing
      trial count N PLAN.md 2.3-2.5 requires.
    """
    daily_sr = annualized_to_daily_sharpe(observed_sr)
    daily_trials = [annualized_to_daily_sharpe(sr) for sr in trial_srs]
    sr0 = expected_max_sharpe(daily_trials)
    variance_term = 1 - skew * daily_sr + ((kurtosis - 1) / 4) * daily_sr**2
    denominator = math.sqrt(max(variance_term, 1e-12))
    numerator = (daily_sr - sr0) * math.sqrt(max(n_obs - 1, 0))
    return _normal_cdf(numerator / denominator)


# ---------------------------------------------------------------------------
# Neighbourhood check.
# ---------------------------------------------------------------------------


def _one_step_neighbours(params: dict, space: dict[str, list]) -> list[dict]:
    """Every candidate reachable by moving exactly one parameter one step up
    or down in its own space (no wraparound at an edge -- a parameter
    already at its space's minimum has no "down" neighbour)."""
    neighbours = []
    for key, values in space.items():
        if key not in params or params[key] not in values:
            continue
        idx = values.index(params[key])
        for step in (-1, 1):
            new_idx = idx + step
            if 0 <= new_idx < len(values):
                neighbour = dict(params)
                neighbour[key] = values[new_idx]
                neighbours.append(neighbour)
    return neighbours


def neighbourhood_check(
    family: str,
    params: dict,
    space: dict[str, list],
    evaluate_fn: Callable[[str, dict], dict],
    fraction_required: float,
) -> dict:
    """Vary each parameter of `params` one step up and down within `space`
    (one parameter at a time), evaluate every neighbour with `evaluate_fn`
    (research-period only -- the caller decides that, this function just
    calls whatever it is given), and require at least `fraction_required`
    of them to also pass. A lone spike surrounded by failing neighbours is
    rejected even if its own result looked good.

    A family with no space to vary (or a `params` with nothing to vary --
    an empty grid) has nothing to compare against and passes vacuously.

    Returns `{"passed": bool, "fraction_passed": float, "neighbours": [...]}`
    where each entry of `neighbours` is `{"params": ..., "outcome": ...}`.
    """
    neighbours = _one_step_neighbours(params, space)
    if not neighbours:
        return {"passed": True, "fraction_passed": 1.0, "neighbours": []}
    results = [
        {"params": neighbour, "outcome": evaluate_fn(family, neighbour)} for neighbour in neighbours
    ]
    passed_count = sum(1 for r in results if r["outcome"]["passed"])
    fraction = passed_count / len(results)
    return {
        "passed": fraction >= fraction_required,
        "fraction_passed": fraction,
        "neighbours": results,
    }


# ---------------------------------------------------------------------------
# Correlation filter.
# ---------------------------------------------------------------------------


def correlation_filter(
    candidate_returns: pd.Series,
    accepted_returns: list[pd.Series],
    max_correlation: float,
) -> dict:
    """Reject `candidate_returns` if it correlates above `max_correlation`
    with any series in `accepted_returns`.

    Callers are expected to process candidates strongest-first (as
    `validate_survivors` does, ranking by `rank_by` before validating), so
    anything already in `accepted_returns` is a stronger or equally-ranked
    earlier survivor -- this function only ever drops the later, weaker one
    of a correlated pair, never the one already accepted.

    Returns `{"passed": bool, "correlation": float | None}`; `correlation`
    is the highest correlation found among `accepted_returns` (None if
    `accepted_returns` is empty or no overlapping data existed to compare).
    """
    worst = None
    for other in accepted_returns:
        aligned = pd.concat([candidate_returns, other], axis=1, join="inner").dropna()
        if len(aligned) < 2:
            continue
        raw_corr = aligned.iloc[:, 0].corr(aligned.iloc[:, 1])
        if raw_corr is None or math.isnan(raw_corr):
            continue
        corr = float(raw_corr)
        if worst is None or corr > worst:
            worst = corr
    passed = bool(worst is None or worst <= max_correlation)
    return {"passed": passed, "correlation": worst}


# ---------------------------------------------------------------------------
# End-to-end validation of a run's research survivors.
# ---------------------------------------------------------------------------


def _reject(
    rejected: list[dict], candidate: dict, stage: str, reason: str, funnel_order: list[dict]
) -> None:
    entry = {
        "test_id": candidate["test_id"],
        "family": candidate["family"],
        "params": candidate["params"],
        "stage": stage,
        "reason": reason,
    }
    rejected.append(entry)
    funnel_order.append(entry)


def validate_survivors(
    ledger: Ledger,
    run_id: int,
    data: SearchData,
    criteria: dict,
    validation_config: dict,
    validation_hash: str,
    *,
    criteria_hash: str,
    universe_name: str,
    spaces: dict[str, dict[str, list]],
    benchmark_metrics: dict | None = None,
) -> dict:
    """Rank `run_id`'s research survivors, take the top
    `validation_config["top_n_to_validate"]`, and for each in order (best
    first):

    1. Neighbourhood check on the research period (`neighbourhood_check`).
       Each neighbour evaluated is recorded in `ledger` as an ordinary
       research test (`Ledger.record_test`), so it counts toward the run's
       total trial count for the deflated Sharpe ratio.
    2. If already validated (`Ledger.is_validated`), skip with a clear
       reason -- never re-validate. Otherwise exactly one evaluation on the
       validation period, recorded via `Ledger.record_validation`.
    3. Deflated Sharpe ratio on that validation-period result, using the
       run's total trial Sharpe distribution (`Ledger.trial_sharpes`).
    4. Correlation filter against already-accepted survivors' validation
       returns.

    Returns a report: `{"funnel": {...}, "accepted": [...], "rejected":
    [...]}`. `funnel` gives a per-stage count (survivors, passed
    neighbourhood, validated, passed deflated Sharpe, passed correlation,
    accepted); `rejected` entries carry the stage and reason each candidate
    stopped at, in survivor rank order.
    """
    top_n = validation_config["top_n_to_validate"]
    rank_by = validation_config["rank_by"]
    fraction_required = validation_config["neighborhood"]["fraction_required"]
    min_dsr = validation_config["min_deflated_sharpe"]
    max_corr = validation_config["max_correlation"]

    survivors = [
        c for c in ledger.top_candidates(run_id=run_id, n=top_n, order_by=rank_by) if c["passed"]
    ]

    funnel = {
        "survivors": len(survivors),
        "passed_neighbourhood": 0,
        "validated": 0,
        "passed_deflated_sharpe": 0,
        "passed_correlation": 0,
        "accepted": 0,
    }
    accepted: list[dict] = []
    rejected: list[dict] = []
    funnel_order: list[dict] = []
    accepted_returns: list[pd.Series] = []

    for candidate in survivors:
        test_id, family, params = candidate["test_id"], candidate["family"], candidate["params"]

        if ledger.is_validated(test_id):
            _reject(
                rejected,
                candidate,
                "already_validated",
                "test already has a validation event; skipped, never re-validated",
                funnel_order,
            )
            continue

        space = spaces.get(family, {})

        def _eval_and_record(fam: str, p: dict) -> dict:
            outcome = evaluate_candidate(
                fam, p, data, criteria, benchmark_metrics, period="research"
            )
            ledger.record_test(
                run_id,
                criteria_hash,
                fam,
                p,
                universe_name,
                outcome["metrics"],
                outcome["passed"],
                outcome["failure_reasons"],
            )
            return outcome

        neighbour_result = neighbourhood_check(
            family, params, space, _eval_and_record, fraction_required
        )
        if not neighbour_result["passed"]:
            pct = neighbour_result["fraction_passed"]
            _reject(
                rejected,
                candidate,
                "neighbourhood",
                f"only {pct:.0%} of neighbours passed research criteria "
                f"(need {fraction_required:.0%})",
                funnel_order,
            )
            continue
        funnel["passed_neighbourhood"] += 1

        val_outcome = evaluate_candidate(
            family, params, data, criteria, benchmark_metrics, period="validation"
        )
        ledger.record_validation(test_id, val_outcome["metrics"], validation_hash)
        funnel["validated"] += 1

        daily_returns = val_outcome["returns"].dropna()
        val_sharpe = val_outcome["metrics"].get("sharpe")
        if val_sharpe is None or len(daily_returns) < 3:
            _reject(
                rejected,
                candidate,
                "deflated_sharpe",
                "validation period had too few observations to compute a Sharpe",
                funnel_order,
            )
            continue

        trial_srs = ledger.trial_sharpes(run_id)
        skew = float(daily_returns.skew())
        # pandas' .kurtosis() is EXCESS kurtosis (normal = 0); the deflated
        # Sharpe formula wants regular kurtosis (normal = 3).
        kurtosis = float(daily_returns.kurtosis()) + 3.0
        dsr = deflated_sharpe_ratio(val_sharpe, trial_srs, len(daily_returns), skew, kurtosis)
        if dsr < min_dsr:
            _reject(
                rejected,
                candidate,
                "deflated_sharpe",
                f"deflated Sharpe {dsr:.3f} < required {min_dsr}",
                funnel_order,
            )
            continue
        funnel["passed_deflated_sharpe"] += 1

        corr_result = correlation_filter(daily_returns, accepted_returns, max_corr)
        if not corr_result["passed"]:
            _reject(
                rejected,
                candidate,
                "correlation",
                f"correlates {corr_result['correlation']:.2f} with an accepted "
                f"survivor (limit {max_corr})",
                funnel_order,
            )
            continue
        funnel["passed_correlation"] += 1
        funnel["accepted"] += 1

        entry = {
            "test_id": test_id,
            "family": family,
            "params": params,
            "validation_sharpe": val_sharpe,
            "deflated_sharpe": dsr,
        }
        accepted.append(entry)
        funnel_order.append({**entry, "stage": "accepted", "reason": None})
        accepted_returns.append(daily_returns)

    # `funnel_order` was appended to exactly once per survivor, in the same
    # order `survivors` was iterated, so it is already in rank order.
    return {
        "funnel": funnel,
        "accepted": accepted,
        "rejected": rejected,
        "candidates": funnel_order,
    }
