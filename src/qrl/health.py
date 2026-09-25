"""Milestone 3.2's DAILY health checks (PLAN.md section 3.2), and ONLY the
daily half: "data arrived, signals computed, no errors" (plus risk-cap
compliance, which the owner decided should be its own failing check rather
than folded into "no errors").

Deliberately NOT here (owner decision 2026-09-24): the monthly live-versus-
expected review, the quarterly sleeve reselection, and the kill rule tied to
backtested drawdown. All three need a live/paper track record that does not
exist yet -- there is nothing to compare against, and nothing has ever
traded. They are a later milestone, once `scripts/daily_check.py` has
actually been running for a while.

Freshness rule, in words: a data feed is "fresh enough" if its latest bar is
no older than `max_staleness_bdays` business days behind the most recent
business day on or before `as_of` (normally today). One business day of
staleness is tolerated by default -- a slightly late data provider on the
calendar day the check happens to run is not, by itself, a failure -- but
going stale by more than that IS a failure, not a warning: nothing else in
this pipeline can quietly self-correct from stale data, so it needs an
operator's attention immediately, not at the next screen refresh.

Every function here is pure: pandas frames and plain callables/arguments in,
dataclasses out, no file or network IO anywhere in this module. That is
deliberate, not an oversight (see AGENTS.md's milestone-3.1 postmortem this
module is a direct response to): logic that lives in a script instead of a
library is invisible to `pytest --cov=qrl`, so `run_daily_health` takes its
inputs as callables (`load_close`, `build_weights`, `combine`) precisely so
tests can wire in fakes -- including fakes that raise or warn -- and prove
every failure path actually fires, without ever touching the network.
`scripts/daily_check.py` wires in the real objects; it must never grow
threshold or check logic of its own.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import pandas as pd

from qrl.risk import RiskLimits, check_portfolio

_EPS = 1e-9
_MAX_NAMES = 5


def _format_names(names: Sequence[str]) -> str:
    names = list(names)
    shown = names[:_MAX_NAMES]
    text = ", ".join(shown)
    remaining = len(names) - len(shown)
    if remaining > 0:
        text += f", and {remaining} more"
    return text


@dataclass(frozen=True)
class CheckResult:
    """One health check's outcome. `status` is one of "ok" / "fail" /
    "skipped" -- a check that never ran must say so, not report "ok"."""

    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class HealthReport:
    """All of a single day's checks, in the stable order data/signals/risk/
    errors (see `run_daily_health`)."""

    as_of: pd.Timestamp
    checks: tuple[CheckResult, ...]

    @property
    def ok(self) -> bool:
        """True only if EVERY check is "ok". A "skipped" stage is treated
        as NOT ok: a check that never ran must never look healthy."""
        return all(c.status == "ok" for c in self.checks)

    def to_dict(self) -> dict:
        """JSON-serialisable primitives only: check names/statuses/details
        and an ISO date.

        WARNING, this promise is narrower than it sounds: `detail` strings
        are operator-facing, not scrubbed, and -- when `check_risk` reports
        a cap breach -- embed the offending ticker symbol and its exact
        position weight verbatim (`qrl.risk`'s violation strings, forwarded
        unchanged; see `check_risk`'s docstring). That is intentional: an
        on-call operator needs the real weight to judge severity, and
        stripping it would make the monitor worse. The consequence is that
        this dict, and the `reports/daily_health.json` file built from it,
        is PRIVATE -- gitignored -- and must NEVER be published to `site/`
        or any other public dashboard (PLAN.md 3.4). Only the ABSENCE of a
        risk-cap breach keeps this particular output free of position data.
        """
        return {
            "as_of": self.as_of.date().isoformat(),
            "ok": self.ok,
            "checks": [
                {"name": c.name, "status": c.status, "detail": c.detail} for c in self.checks
            ],
        }


def expected_last_bar(as_of: pd.Timestamp, *, max_staleness_bdays: int = 1) -> pd.Timestamp:
    """The oldest date a fresh feed may carry as its latest bar: `as_of`
    rolled back to the most recent business day, then back
    `max_staleness_bdays` more business days.
    """
    if max_staleness_bdays < 0:
        raise ValueError(f"max_staleness_bdays must be >= 0, got {max_staleness_bdays}.")
    normalized = pd.Timestamp(as_of).normalize()
    rolled = pd.offsets.BDay().rollback(normalized)
    return rolled - pd.offsets.BDay(max_staleness_bdays)


def check_data_arrived(
    close: pd.DataFrame, *, as_of: pd.Timestamp, max_staleness_bdays: int = 1
) -> CheckResult:
    """Fails if `close` is empty, if any ticker column is entirely NaN, or
    if any ticker's last non-NaN close is older than `expected_last_bar`.
    """
    name = "data_arrived"
    if close.empty:
        return CheckResult(name, "fail", "close is empty; no price data loaded.")

    expected = expected_last_bar(as_of, max_staleness_bdays=max_staleness_bdays)
    all_nan: list[str] = []
    stale: list[str] = []
    for ticker in close.columns:
        valid = close[ticker].dropna()
        if valid.empty:
            all_nan.append(ticker)
            continue
        last = valid.index[-1]
        if last < expected:
            stale.append(f"{ticker} ({last.date()})")

    if all_nan or stale:
        parts = []
        if all_nan:
            parts.append(f"all-NaN tickers: {_format_names(sorted(all_nan))}")
        if stale:
            parts.append(f"stale (before {expected.date()}): {_format_names(sorted(stale))}")
        return CheckResult(name, "fail", "; ".join(parts))
    return CheckResult(name, "ok", f"all {close.shape[1]} ticker(s) fresh as of {expected.date()}.")


def check_signals_computed(
    weights: Mapping[str, pd.DataFrame], *, as_of: pd.Timestamp
) -> CheckResult:
    """Fails if `weights` is empty, or if any strategy's LAST row is still
    in warm-up (any NaN), negative anywhere, or sums above 1."""
    name = "signals_computed"
    if not weights:
        return CheckResult(name, "fail", "no strategy weights were computed.")

    problems: list[str] = []
    for strategy_name, frame in weights.items():
        if frame.empty:
            problems.append(f"{strategy_name}: no rows")
            continue
        last_row = frame.iloc[-1]
        if last_row.isna().any():
            problems.append(f"{strategy_name}: still in warm-up (NaN in last row)")
        elif (last_row < -_EPS).any():
            problems.append(f"{strategy_name}: negative weight in last row")
        elif last_row.sum() > 1.0 + _EPS:
            problems.append(f"{strategy_name}: last row sums to {last_row.sum():.4f} > 1.0")

    if problems:
        return CheckResult(name, "fail", "; ".join(problems))
    return CheckResult(name, "ok", f"{len(weights)} strategy(ies) have a valid last-row signal.")


def check_risk(*, combined: pd.DataFrame, sleeve: pd.DataFrame, limits: RiskLimits) -> CheckResult:
    """Evaluates ONLY the latest row of `combined`/`sleeve` against
    `limits`, delegating entirely to `qrl.risk.check_portfolio` (never
    reimplementing cap logic here). Scoped to today's row rather than the
    whole history because `check_portfolio` scans every row it is given --
    handing it full history would let one breach from years ago turn the
    daily report red forever, which is alert fatigue, not a *daily* check.

    Returns "skipped" -- never "ok" -- if the latest row cannot be
    evaluated: either frame is empty, or the latest row has any NaN in
    either frame (still in warm-up, or stale data). NaN comparisons are
    False and a NaN row sums to 0.0 under pandas' default skipna=True, so
    handing such a row to `check_portfolio` would silently report "ok" on a
    portfolio it never actually checked. `check_signals_computed` already
    owns reporting *why* the weights are NaN; this check only refuses to
    claim a clean bill of health it cannot back up.

    NOTE: in the live path (`run_daily_health` via `combine_portfolio`),
    warm-up NaN is scrubbed to 0.0 before it ever reaches this function, so
    `run_daily_health` gates on `signals_computed`'s status instead of
    relying on this NaN check. This guard is defence-in-depth for any other
    caller that hands `check_risk` unscrubbed frames directly -- it is not
    dead code, and it is not the mechanism that catches the live warm-up
    case.
    """
    if combined.empty or sleeve.empty:
        return CheckResult("risk", "skipped", "empty weights frame; caps not evaluated.")

    latest_combined = combined.tail(1)
    latest_sleeve = sleeve.tail(1)
    if latest_combined.isna().any().any() or latest_sleeve.isna().any().any():
        as_of_date = latest_combined.index[-1]
        return CheckResult(
            "risk", "skipped", f"{as_of_date.date()}: weights are NaN; caps not evaluated."
        )

    violations = check_portfolio(combined=latest_combined, sleeve=latest_sleeve, limits=limits)
    if violations:
        return CheckResult("risk", "fail", "; ".join(violations))
    return CheckResult("risk", "ok", "within all risk limits (latest row only).")


def check_no_errors(errors: Sequence[str]) -> CheckResult:
    """Fails if `errors` is non-empty."""
    if errors:
        return CheckResult("errors", "fail", "; ".join(errors))
    return CheckResult("errors", "ok", "no errors.")


def run_daily_health(
    *,
    load_close: Callable[[], pd.DataFrame],
    build_weights: Mapping[str, Callable[[pd.DataFrame], pd.DataFrame]],
    combine: Callable[[Mapping[str, pd.DataFrame]], tuple[pd.DataFrame, pd.DataFrame]] | None,
    limits: RiskLimits | None,
    as_of: pd.Timestamp | None = None,
    max_staleness_bdays: int = 1,
) -> HealthReport:
    """Orchestrate a full daily health run, catching every stage's
    exceptions and warnings here (in the library) rather than leaving them
    to escape into the caller/script.

    - If `load_close` raises, `data_arrived` is "fail" and both
      `signals_computed` and `risk` are "skipped" (not silently ok).
    - A `build_weights` entry that raises is recorded as an error and
      excluded from the weights passed on to `combine`; it does not abort
      the other strategies.
    - `risk` is "skipped" for one of these reasons, checked in this order
      (first match wins):
        1. data failed to load ("data did not load.");
        2. data loaded but `check_data_arrived` itself reported "fail" --
           e.g. a stale or all-NaN ticker -- ("data_arrived check failed;
           caps not evaluated."). Reproduction this closes: a ticker whose
           last valid bar is 2 business days old plus a weight generator
           that happens to produce a valid non-NaN last row must NOT let
           `risk` fall through to "ok" -- `check_signals_computed` never
           inspects staleness, so it cannot be relied on to catch this;
        3. `signals_computed` did not come back "ok" ("signals not
           computed; caps not evaluated.") -- `combine_portfolio` fills NaN
           weights with 0.0 for warm-up strategies (correct for backtests,
           where warm-up means flat), so once weights reach `check_risk`
           they are clean zeros, not NaN. Evaluating caps against that
           scrubbed frame would report "ok" on a portfolio that was never
           the real one -- a true statement that implies false assurance.
           Gating on `signals_computed` instead of on NaN detection is what
           makes the report honest: "caps not evaluated" rather than a
           misleading "ok". This check fires regardless of whether
           `combine`/`limits` are configured, since there is nothing
           meaningful to evaluate either way;
        4. `combine` is None or `limits` is None ("no combine/limits
           configured.");
        5. `combine` itself raises ("combine raised an error.").
      Otherwise `risk` is actually evaluated via `check_risk` (see its
      NaN guard for the defence-in-depth case, which should not normally
      fire given reasons 2 and 3 above).

      Asymmetry, by design: `signals_computed` is still evaluated even when
      `data_arrived` failed -- "signals computed on stale data" is true and
      useful information, worth keeping rather than discarding. It is
      specifically `risk`, which makes a policy-compliance claim ("within
      all risk limits"), that must stay silent once ANY upstream input
      (data or signals) is untrustworthy. This is a decision, not an
      oversight: blanket-skipping every downstream check on the first
      failure would throw away real signal for no safety gain.
    - Warnings raised anywhere during the run (e.g. by `qrl.data`) are
      captured into the `errors` check.
    """
    resolved_as_of = (
        pd.Timestamp.today().normalize() if as_of is None else pd.Timestamp(as_of).normalize()
    )
    errors: list[str] = []

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")

        close: pd.DataFrame | None
        try:
            close = load_close()
        except Exception as exc:
            close = None
            data_check = CheckResult("data_arrived", "fail", f"load_close raised: {exc}")
        else:
            data_check = check_data_arrived(
                close, as_of=resolved_as_of, max_staleness_bdays=max_staleness_bdays
            )

        weights: dict[str, pd.DataFrame] = {}
        if close is None:
            signals_check = CheckResult("signals_computed", "skipped", "data did not load.")
        else:
            for strategy_name, fn in build_weights.items():
                try:
                    weights[strategy_name] = fn(close)
                except Exception as exc:
                    errors.append(f"{strategy_name}: {exc}")
            signals_check = check_signals_computed(weights, as_of=resolved_as_of)

        if close is None:
            risk_check = CheckResult("risk", "skipped", "data did not load.")
        elif data_check.status != "ok":
            risk_check = CheckResult(
                "risk", "skipped", "data_arrived check failed; caps not evaluated."
            )
        elif signals_check.status != "ok":
            risk_check = CheckResult("risk", "skipped", "signals not computed; caps not evaluated.")
        elif combine is None or limits is None:
            risk_check = CheckResult("risk", "skipped", "no combine/limits configured.")
        else:
            try:
                combined, sleeve = combine(weights)
            except Exception as exc:
                errors.append(f"combine: {exc}")
                risk_check = CheckResult("risk", "skipped", "combine raised an error.")
            else:
                risk_check = check_risk(combined=combined, sleeve=sleeve, limits=limits)

        for w in caught:
            errors.append(str(w.message))

    errors_check = check_no_errors(errors)

    return HealthReport(
        as_of=resolved_as_of, checks=(data_check, signals_check, risk_check, errors_check)
    )
