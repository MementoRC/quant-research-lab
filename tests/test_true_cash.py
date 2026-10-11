"""True-cash assumption row (spec: docs/methodology/true-cash-sleeve.md): the
optional cash_assumption key, the cash leg (CPI inflation plus a real yield),
and the row in the decision and long-run reports. Offline: synthetic prices,
synthetic CPI and fixture configs only (never market data); research period
only."""

from __future__ import annotations

from qrl import decision_withdraw, longrun


def test_monthly_inflation_lives_in_decision_withdraw_and_longrun_reuses_it():
    assert longrun.monthly_inflation is decision_withdraw.monthly_inflation
