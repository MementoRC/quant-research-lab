"""Tests for milestone 3.2's DAILY health checks (qrl.health, PLAN.md
section 3.2). Every check test asserts the check actually FIRES on a
crafted failing input, not merely that it passes on good input -- a check
that cannot fail is worse than no check (see health.py's module docstring).
All frames here are small and hand-built with `pd.bdate_range`; nothing
touches the network.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pandas as pd
import pytest

from qrl.health import (
    CheckResult,
    HealthReport,
    check_data_arrived,
    check_no_errors,
    check_risk,
    check_signals_computed,
    expected_last_bar,
    run_daily_health,
)
from qrl.profile import load_profile
from qrl.risk import RiskLimits, load_risk_limits

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

# 10 business days ending on a fixed Friday, so tests never depend on when
# they happen to run.
IDX = pd.bdate_range(end="2026-09-25", periods=10)


@pytest.fixture
def example_profile() -> dict:
    return load_profile(ROOT / "config" / "profile.yaml")


@pytest.fixture
def shipped_limits(example_profile) -> RiskLimits:
    return load_risk_limits(example_profile)


@pytest.fixture
def permissive_limits() -> RiskLimits:
    """Caps loose enough that only a check under test can trip them --
    used by the `run_daily_health` orchestration tests, which are not
    themselves testing risk-cap math."""
    return RiskLimits(
        leverage_ceiling=1.0,
        max_gross_exposure=1.0,
        borrowing_cost_bps=0.0,
        max_loss_per_trade=1.0,
        max_open_positions=100,
    )


# ---------------------------------------------------------------------------
# expected_last_bar
# ---------------------------------------------------------------------------


def test_expected_last_bar_wednesday_tolerance_one_is_tuesday():
    wednesday = pd.Timestamp("2026-09-23")
    assert expected_last_bar(wednesday, max_staleness_bdays=1) == pd.Timestamp("2026-09-22")


def test_expected_last_bar_saturday_rolls_back_to_friday_then_minus_one():
    saturday = pd.Timestamp("2026-09-26")
    assert expected_last_bar(saturday, max_staleness_bdays=1) == pd.Timestamp("2026-09-24")


def test_expected_last_bar_tolerance_zero_is_rolled_back_day_itself():
    saturday = pd.Timestamp("2026-09-26")
    assert expected_last_bar(saturday, max_staleness_bdays=0) == pd.Timestamp("2026-09-25")


def test_expected_last_bar_negative_tolerance_raises():
    with pytest.raises(ValueError, match="max_staleness_bdays"):
        expected_last_bar(pd.Timestamp("2026-09-23"), max_staleness_bdays=-1)


def test_expected_last_bar_sunday_rolls_back_to_friday_then_minus_one():
    """Fix 5: pin the Sunday edge distinctly from the existing Saturday
    test -- both weekend days must roll back to the same prior Friday."""
    sunday = pd.Timestamp("2026-09-27")
    assert expected_last_bar(sunday, max_staleness_bdays=1) == pd.Timestamp("2026-09-24")


def test_expected_last_bar_monday_minus_one_is_friday():
    """Fix 5: a Monday `as_of` is already a business day, so rollback is a
    no-op and tolerance=1 steps back across the weekend to Friday."""
    monday = pd.Timestamp("2026-09-28")
    assert expected_last_bar(monday, max_staleness_bdays=1) == pd.Timestamp("2026-09-25")


# ---------------------------------------------------------------------------
# check_data_arrived
# ---------------------------------------------------------------------------


def test_check_data_arrived_fresh_frame_passes():
    close = pd.DataFrame({"AAA": range(10)}, index=IDX, dtype=float)
    result = check_data_arrived(close, as_of=pd.Timestamp("2026-09-25"), max_staleness_bdays=1)
    assert result.status == "ok"


def test_check_data_arrived_two_bdays_stale_fails():
    stale_idx = IDX[:-2]  # last bar is 2 business days behind the frame's would-be last day
    close = pd.DataFrame({"AAA": range(len(stale_idx))}, index=stale_idx, dtype=float)
    result = check_data_arrived(close, as_of=pd.Timestamp("2026-09-25"), max_staleness_bdays=1)
    assert result.status == "fail"
    assert "AAA" in result.detail


def test_check_data_arrived_last_bar_exactly_at_expected_boundary_passes():
    """Fix 5 boundary: a ticker whose last valid bar is EXACTLY
    `expected_last_bar` must PASS -- the rule is "no older than" (strict
    `<`), not "newer than". Code inspection said `<` is correct; this pins
    it so it stays correct."""
    idx = pd.bdate_range(end="2026-09-22", periods=5)
    close = pd.DataFrame({"AAA": range(5)}, index=idx, dtype=float)
    result = check_data_arrived(close, as_of=pd.Timestamp("2026-09-23"), max_staleness_bdays=1)
    assert result.status == "ok"


def test_check_data_arrived_all_nan_ticker_fails():
    close = pd.DataFrame(
        {"AAA": list(range(10)), "BBB": [float("nan")] * 10}, index=IDX, dtype=float
    )
    result = check_data_arrived(close, as_of=pd.Timestamp("2026-09-25"), max_staleness_bdays=1)
    assert result.status == "fail"
    assert "BBB" in result.detail


def test_check_data_arrived_empty_frame_fails():
    result = check_data_arrived(pd.DataFrame(), as_of=pd.Timestamp("2026-09-25"))
    assert result.status == "fail"


def test_check_data_arrived_truncates_long_offender_list():
    """More than 5 stale tickers: the detail must say 'and N more' rather
    than listing every one, so the check stays readable on a large
    universe."""
    stale_idx = IDX[:-2]
    columns = [f"T{i}" for i in range(8)]
    close = pd.DataFrame(0.0, index=stale_idx, columns=columns)
    result = check_data_arrived(close, as_of=pd.Timestamp("2026-09-25"), max_staleness_bdays=1)
    assert result.status == "fail"
    assert "and 3 more" in result.detail


# ---------------------------------------------------------------------------
# check_signals_computed
# ---------------------------------------------------------------------------


def test_check_signals_computed_valid_last_row_passes():
    idx = pd.bdate_range("2026-09-01", periods=5)
    weights = {"strat": pd.DataFrame({"AAA": [None, None, 0.5, 0.5, 0.5]}, index=idx)}
    result = check_signals_computed(weights, as_of=pd.Timestamp("2026-09-25"))
    assert result.status == "ok"


def test_check_signals_computed_warmup_last_row_fails():
    idx = pd.bdate_range("2026-09-01", periods=3)
    weights = {"strat": pd.DataFrame({"AAA": [None, None, None]}, index=idx)}
    result = check_signals_computed(weights, as_of=pd.Timestamp("2026-09-25"))
    assert result.status == "fail"
    assert "strat" in result.detail


def test_check_signals_computed_over_budget_sum_fails():
    idx = pd.bdate_range("2026-09-01", periods=2)
    weights = {"strat": pd.DataFrame({"AAA": [0.5, 0.8], "BBB": [0.5, 0.7]}, index=idx)}
    result = check_signals_computed(weights, as_of=pd.Timestamp("2026-09-25"))
    assert result.status == "fail"
    # Fix 4: pin the branch -- last row (0.8+0.7=1.5) is non-NaN and
    # non-negative, so only the sum-over-budget branch can produce this.
    assert "sums to 1.5000" in result.detail


def test_check_signals_computed_negative_weight_fails():
    idx = pd.bdate_range("2026-09-01", periods=2)
    weights = {"strat": pd.DataFrame({"AAA": [0.5, -0.1]}, index=idx)}
    result = check_signals_computed(weights, as_of=pd.Timestamp("2026-09-25"))
    assert result.status == "fail"
    # Fix 4: pin the branch -- must be the negative-weight message, not a
    # coincidental NaN or over-budget-sum hit.
    assert "negative weight in last row" in result.detail


def test_check_signals_computed_empty_mapping_fails():
    result = check_signals_computed({}, as_of=pd.Timestamp("2026-09-25"))
    assert result.status == "fail"


def test_check_signals_computed_strategy_with_no_rows_fails():
    weights = {"strat": pd.DataFrame(columns=["AAA"])}
    result = check_signals_computed(weights, as_of=pd.Timestamp("2026-09-25"))
    assert result.status == "fail"
    assert "no rows" in result.detail


# ---------------------------------------------------------------------------
# check_risk
# ---------------------------------------------------------------------------


def test_check_risk_passes_on_clean_portfolio(shipped_limits):
    idx = pd.bdate_range("2026-09-01", periods=3)
    clean = pd.DataFrame(0.0, index=idx, columns=["QQQ"])
    result = check_risk(combined=clean, sleeve=clean, limits=shipped_limits)
    assert result.status == "ok"


def test_check_risk_fails_on_breach_of_shipped_limits(shipped_limits):
    """A sleeve position weight above the shipped max_loss_per_trade
    (0.04) on the LATEST row must fail, mirroring test_risk.py's approach.
    The breach is placed on the last row (not the first) because `check_risk`
    now scopes evaluation to the latest row only -- see
    `test_check_risk_early_row_breach_but_clean_latest_row_is_ok`."""
    idx = pd.bdate_range("2026-09-01", periods=3)
    combined = pd.DataFrame({"AAA": [0.0, 0.0, 0.10]}, index=idx)
    sleeve = combined
    result = check_risk(combined=combined, sleeve=sleeve, limits=shipped_limits)
    assert result.status == "fail"
    assert "max_loss_per_trade" in result.detail


def test_check_risk_all_nan_last_row_is_skipped_not_ok(shipped_limits):
    """Defect regression (was: a portfolio whose LAST row is all-NaN, e.g.
    warm-up/stale data, sailed through as "ok" -- NaN comparisons are False
    and a NaN row sums to 0.0 under pandas' skipna=True). The caps cannot be
    evaluated on a NaN row, so the check must say "skipped", never "ok"."""
    idx = pd.bdate_range("2026-09-01", periods=3)
    nan_row = pd.DataFrame({"AAA": [0.0, 0.0, float("nan")]}, index=idx)
    result = check_risk(combined=nan_row, sleeve=nan_row, limits=shipped_limits)
    assert result.status == "skipped"
    assert "NaN" in result.detail


def test_check_risk_nan_in_only_one_column_is_still_skipped(shipped_limits):
    """A single NaN column in the latest row must not be partially
    evaluated -- the whole row is unusable."""
    idx = pd.bdate_range("2026-09-01", periods=2)
    combined = pd.DataFrame({"AAA": [0.0, 0.0], "BBB": [0.0, float("nan")]}, index=idx)
    sleeve = combined
    result = check_risk(combined=combined, sleeve=sleeve, limits=shipped_limits)
    assert result.status == "skipped"
    assert "NaN" in result.detail


def test_check_risk_empty_frame_is_skipped(shipped_limits):
    empty = pd.DataFrame(columns=["AAA"])
    result = check_risk(combined=empty, sleeve=empty, limits=shipped_limits)
    assert result.status == "skipped"


def test_risk_detail_embeds_ticker_weights_so_artifact_must_stay_private(shipped_limits):
    """Fix 1 (audit): `check_risk` forwards `check_portfolio`'s violation
    strings verbatim, and those strings embed the offending ticker and its
    exact weight. This is NOT a leak to plug -- an on-call operator needs
    the real weight to judge severity -- it is a DELIBERATE, documented
    property that makes `reports/daily_health.json` private (gitignored)
    and unfit to ever publish to `site/` (PLAN.md 3.4). This test pins the
    embedding so nobody "fixes" it into a scrubbed message later."""
    idx = pd.bdate_range("2026-09-01", periods=3)
    breaching = pd.DataFrame({"ZZZ_TICKER": [0.0, 0.0, 0.10]}, index=idx)
    result = check_risk(combined=breaching, sleeve=breaching, limits=shipped_limits)
    assert result.status == "fail"
    assert "ZZZ_TICKER" in result.detail
    assert "0.1000" in result.detail


def test_check_risk_early_row_breach_but_clean_latest_row_is_ok(shipped_limits):
    """Scope regression, the important one: `check_portfolio` scans every
    row it is given, so handing it the full history would make one breach
    from long ago turn the daily report red forever. `check_risk` must pass
    only the LATEST row -- a portfolio that breached a cap early on but is
    clean today must report "ok"."""
    idx = pd.bdate_range("2026-09-01", periods=3)
    combined = pd.DataFrame({"AAA": [0.10, 0.0, 0.0]}, index=idx)  # 0.10 breaches on day 1 only
    sleeve = combined
    result = check_risk(combined=combined, sleeve=sleeve, limits=shipped_limits)
    assert result.status == "ok"


# ---------------------------------------------------------------------------
# check_no_errors
# ---------------------------------------------------------------------------


def test_check_no_errors_passes_on_empty_sequence():
    assert check_no_errors([]).status == "ok"


def test_check_no_errors_fails_on_nonempty_sequence():
    result = check_no_errors(["boom"])
    assert result.status == "fail"
    assert "boom" in result.detail


# ---------------------------------------------------------------------------
# HealthReport.ok / to_dict
# ---------------------------------------------------------------------------


def test_health_report_ok_false_when_any_check_skipped():
    checks = (
        CheckResult("data_arrived", "ok", ""),
        CheckResult("signals_computed", "skipped", ""),
        CheckResult("risk", "ok", ""),
        CheckResult("errors", "ok", ""),
    )
    report = HealthReport(as_of=pd.Timestamp("2026-09-25"), checks=checks)
    assert report.ok is False


def test_health_report_ok_true_when_all_ok():
    checks = tuple(CheckResult(n, "ok", "") for n in ("a", "b"))
    report = HealthReport(as_of=pd.Timestamp("2026-09-25"), checks=checks)
    assert report.ok is True


def test_health_report_to_dict_uses_iso_date_and_plain_dicts():
    checks = (CheckResult("data_arrived", "ok", "fine"),)
    report = HealthReport(as_of=pd.Timestamp("2026-09-25"), checks=checks)
    d = report.to_dict()
    assert d["as_of"] == "2026-09-25"
    assert d["ok"] is True
    assert d["checks"] == [{"name": "data_arrived", "status": "ok", "detail": "fine"}]


# ---------------------------------------------------------------------------
# run_daily_health integration
# ---------------------------------------------------------------------------


def _good_close() -> pd.DataFrame:
    return pd.DataFrame({"AAA": range(10), "BBB": range(10)}, index=IDX, dtype=float)


def _good_weights(close: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(0.5, index=close.index, columns=["AAA"])


def _combine_from(name: str):
    def _combine(weights: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
        frame = weights[name]
        return frame, frame

    return _combine


def test_run_daily_health_all_good_is_ok(permissive_limits):
    report = run_daily_health(
        load_close=_good_close,
        build_weights={"core": _good_weights},
        combine=_combine_from("core"),
        limits=permissive_limits,
        as_of=pd.Timestamp("2026-09-25"),
    )
    assert report.ok is True


def test_run_daily_health_load_close_raises_skips_signals_and_risk(permissive_limits):
    def _raising_close() -> pd.DataFrame:
        raise RuntimeError("network down")

    report = run_daily_health(
        load_close=_raising_close,
        build_weights={"core": _good_weights},
        combine=_combine_from("core"),
        limits=permissive_limits,
        as_of=pd.Timestamp("2026-09-25"),
    )
    by_name = {c.name: c for c in report.checks}
    assert by_name["data_arrived"].status == "fail"
    assert by_name["signals_computed"].status == "skipped"
    assert by_name["risk"].status == "skipped"
    assert report.ok is False


def test_run_daily_health_one_strategy_raises_other_still_evaluated(permissive_limits):
    def _raising(close: pd.DataFrame) -> pd.DataFrame:
        raise RuntimeError("boom")

    report = run_daily_health(
        load_close=_good_close,
        build_weights={"good": _good_weights, "bad": _raising},
        combine=_combine_from("good"),
        limits=permissive_limits,
        as_of=pd.Timestamp("2026-09-25"),
    )
    by_name = {c.name: c for c in report.checks}
    assert "bad" in by_name["errors"].detail
    assert "boom" in by_name["errors"].detail
    assert by_name["signals_computed"].status == "ok"
    assert report.ok is False


def test_run_daily_health_warning_in_load_close_fails_errors_check(permissive_limits):
    def _warning_close() -> pd.DataFrame:
        warnings.warn("stale ticker XYZ dropped", stacklevel=2)
        return _good_close()

    report = run_daily_health(
        load_close=_warning_close,
        build_weights={"core": _good_weights},
        combine=_combine_from("core"),
        limits=permissive_limits,
        as_of=pd.Timestamp("2026-09-25"),
    )
    by_name = {c.name: c for c in report.checks}
    assert by_name["errors"].status == "fail"
    assert "stale ticker XYZ" in by_name["errors"].detail
    assert report.ok is False


def test_run_daily_health_limits_none_skips_risk():
    report = run_daily_health(
        load_close=_good_close,
        build_weights={"core": _good_weights},
        combine=_combine_from("core"),
        limits=None,
        as_of=pd.Timestamp("2026-09-25"),
    )
    by_name = {c.name: c for c in report.checks}
    assert by_name["risk"].status == "skipped"
    assert report.ok is False


def test_run_daily_health_nan_latest_weights_skips_risk_on_signals_gate(permissive_limits):
    """A `combine` whose latest row is still raw NaN (e.g. still in
    warm-up, unscrubbed) makes `signals_computed` fail, and `risk` is
    gated on that failure -- "skipped" with the signals reason, not a
    false "ok" and not the (now secondary) NaN-guard message. See
    `test_run_daily_health_live_warmup_zeroed_by_combine_skips_risk_not_ok`
    for the realistic live shape, where `combine` scrubs NaN to 0.0 the
    way `combine_portfolio` does."""

    def _warmup_weights(close: pd.DataFrame) -> pd.DataFrame:
        frame = pd.DataFrame(0.5, index=close.index, columns=["AAA"])
        frame.iloc[-1] = float("nan")
        return frame

    report = run_daily_health(
        load_close=_good_close,
        build_weights={"core": _warmup_weights},
        combine=_combine_from("core"),
        limits=permissive_limits,
        as_of=pd.Timestamp("2026-09-25"),
    )
    by_name = {c.name: c for c in report.checks}
    assert by_name["signals_computed"].status == "fail"
    assert by_name["risk"].status == "skipped"
    assert "signals not computed" in by_name["risk"].detail
    assert report.ok is False


def test_run_daily_health_live_warmup_zeroed_by_combine_skips_risk_not_ok(permissive_limits):
    """The regression test that matters: `build_weights` yields a frame
    whose last row is NaN (still in warm-up), and `combine` ZEROES that
    NaN exactly like `qrl.portfolio.combine_portfolio` does
    (`weights.fillna(0.0) * share`). The frames reaching `check_risk` are
    therefore clean all-zero, not NaN -- so `check_risk`'s own NaN guard
    cannot and should not be what catches this. The risk check must still
    be "skipped" with the signals reason (not a false "ok" on a portfolio
    that was never the real one), and the overall report must be not ok."""

    def _warmup_weights(close: pd.DataFrame) -> pd.DataFrame:
        frame = pd.DataFrame(0.5, index=close.index, columns=["AAA"])
        frame.iloc[-1] = float("nan")
        return frame

    def _zeroing_combine(weights: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
        frame = weights["core"].fillna(0.0)
        return frame, frame

    report = run_daily_health(
        load_close=_good_close,
        build_weights={"core": _warmup_weights},
        combine=_zeroing_combine,
        limits=permissive_limits,
        as_of=pd.Timestamp("2026-09-25"),
    )
    by_name = {c.name: c for c in report.checks}
    assert by_name["signals_computed"].status == "fail"
    assert not by_name["risk"].detail.count("NaN")
    assert by_name["risk"].status == "skipped"
    assert "signals not computed" in by_name["risk"].detail
    assert report.ok is False


def test_run_daily_health_signals_ok_risk_actually_evaluated(permissive_limits):
    """The healthy-path counterpart to the gate tests above: when signals
    are "ok" and `combine`/`limits` are configured, `risk` must actually
    be evaluated (either "ok" or "fail"), never "skipped" -- a gate that
    skips everything is as useless as one that never fires."""
    report = run_daily_health(
        load_close=_good_close,
        build_weights={"core": _good_weights},
        combine=_combine_from("core"),
        limits=permissive_limits,
        as_of=pd.Timestamp("2026-09-25"),
    )
    by_name = {c.name: c for c in report.checks}
    assert by_name["signals_computed"].status == "ok"
    # Fix 4: with permissive limits and a clean frame the only correct
    # outcome is "ok"; a bug that always failed check_risk would previously
    # have slipped past the looser `in ("ok", "fail")` assertion.
    assert by_name["risk"].status == "ok"


def test_run_daily_health_data_failure_takes_precedence_over_signals_reason(permissive_limits):
    """Precedence: when data fails to load, `risk` must be skipped with
    the data reason, not the signals reason -- even though signals also
    never computed. First match wins, and it must be the data reason."""

    def _raising_close() -> pd.DataFrame:
        raise RuntimeError("network down")

    report = run_daily_health(
        load_close=_raising_close,
        build_weights={"core": _good_weights},
        combine=_combine_from("core"),
        limits=permissive_limits,
        as_of=pd.Timestamp("2026-09-25"),
    )
    by_name = {c.name: c for c in report.checks}
    assert by_name["risk"].status == "skipped"
    assert by_name["risk"].detail == "data did not load."
    assert "signals" not in by_name["risk"].detail


def test_run_daily_health_combine_none_skips_risk(permissive_limits):
    """Fix 3: the `combine is None` half of `combine is None or limits is
    None` had no direct test (only `limits=None` did), even though it is
    reachable through the public API."""
    report = run_daily_health(
        load_close=_good_close,
        build_weights={"core": _good_weights},
        combine=None,
        limits=permissive_limits,
        as_of=pd.Timestamp("2026-09-25"),
    )
    by_name = {c.name: c for c in report.checks}
    assert by_name["risk"].status == "skipped"
    assert report.ok is False


def test_run_daily_health_stale_data_skips_risk_even_when_signals_pass(permissive_limits):
    """Fix 2 (audit reproduction): `load_close` succeeds but
    `check_data_arrived` reports "fail" (a ticker 2 business days stale),
    while `check_signals_computed` still passes -- it only inspects the
    last row's NaN/negative/sum, never staleness. `risk` must be "skipped"
    naming the data_arrived failure, never a false "ok" built from weights
    derived off data already known to be untrustworthy."""
    stale_idx = IDX[:-2]

    def _stale_close() -> pd.DataFrame:
        return pd.DataFrame({"AAA": range(len(stale_idx))}, index=stale_idx, dtype=float)

    def _weights(close: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(0.5, index=close.index, columns=["AAA"])

    report = run_daily_health(
        load_close=_stale_close,
        build_weights={"core": _weights},
        combine=_combine_from("core"),
        limits=permissive_limits,
        as_of=pd.Timestamp("2026-09-25"),
    )
    by_name = {c.name: c for c in report.checks}
    assert by_name["data_arrived"].status == "fail"
    assert by_name["signals_computed"].status == "ok"
    assert by_name["risk"].status == "skipped"
    assert "data_arrived" in by_name["risk"].detail
    assert report.ok is False


def test_daily_check_default_out_path_is_under_reports_not_site():
    """Fix 1: `reports/daily_health.json` can embed ticker/weight data on a
    risk breach (see
    `test_risk_detail_embeds_ticker_weights_so_artifact_must_stay_private`)
    and must never default under the public `site/` directory."""
    from daily_check import _build_arg_parser

    args = _build_arg_parser().parse_args([])
    out_parts = Path(args.out).parts
    assert "reports" in out_parts
    assert "site" not in out_parts


def test_run_daily_health_combine_raising_is_captured_as_error(permissive_limits):
    """Bonus coverage beyond the required scenarios: `combine` is wrapped in
    the same try/except as every other stage, so a bug in portfolio
    combination is recorded, not left to crash the whole run."""

    def _raising_combine(weights: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
        raise RuntimeError("combine boom")

    report = run_daily_health(
        load_close=_good_close,
        build_weights={"core": _good_weights},
        combine=_raising_combine,
        limits=permissive_limits,
        as_of=pd.Timestamp("2026-09-25"),
    )
    by_name = {c.name: c for c in report.checks}
    assert "combine boom" in by_name["errors"].detail
    assert by_name["risk"].status == "skipped"
    assert report.ok is False
