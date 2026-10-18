"""What-if shock (spec: docs/methodology/whatif-shock.md): qrl.shock and its three
public aliases. Offline: the shipped config/decision.yaml plus synthetic prices
and CPI. Existing tests are untouched."""

from __future__ import annotations

from qrl import decision, decision_config, decision_report


def test_shock_public_aliases_are_the_private_objects():
    assert decision.first_years is decision._first_years
    assert decision_config.ID_PATTERN is decision_config._ID
    assert decision_report.below_peak is decision_report._below_peak
